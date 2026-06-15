import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import click
import httpx

LOCAL_API_URL = "http://localhost:8000"
HOSTED_API_URL = "https://api.mutx.dev"

_CONFIG_STATE_LABELS = {
    "loaded": "loaded from file",
    "missing": "no config file found (using defaults)",
    "invalid_json": "config file ignored: invalid JSON (using defaults)",
    "unreadable": "config file ignored: unreadable (using defaults)",
    "invalid_shape": "config file ignored: not a JSON object (using defaults)",
}


def _normalize_api_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return normalized or None


@dataclass(frozen=True)
class ConfigLoadStatus:
    """Diagnostic describing how the local config file was loaded.

    ``detail`` only ever contains parser/IO summaries (never file contents),
    so it is safe to surface in ``config show`` / ``doctor`` output.
    """

    state: str
    path: str
    detail: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.state in ("loaded", "missing")

    @property
    def has_issue(self) -> bool:
        return self.state in ("invalid_json", "unreadable", "invalid_shape")

    def describe(self) -> str:
        return _CONFIG_STATE_LABELS.get(self.state, self.state)

    def to_payload(self) -> dict[str, Optional[str]]:
        return {"state": self.state, "path": self.path, "detail": self.detail}


class CLIConfig:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / ".mutx" / "config.json"
        self.config_path = config_path
        self._runtime_api_url_override = _normalize_api_url(os.getenv("MUTX_API_URL"))
        self._load_status = ConfigLoadStatus(state="missing", path=str(config_path))
        self._config = self._load()

    def _default_config(self) -> dict[str, Any]:
        return {
            "api_url": LOCAL_API_URL,
            "access_token": None,
            "refresh_token": None,
            "assistant_defaults": {
                "provider": "openclaw",
                "template": "personal_assistant",
                "runtime": "openclaw",
                "model": "openai/gpt-5",
            },
        }

    def _load(self) -> dict[str, Any]:
        payload: dict[str, Any] = self._default_config()
        migrated = False
        path_str = str(self.config_path)

        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as handle:
                    loaded = json.load(handle)
            except json.JSONDecodeError as exc:
                self._load_status = ConfigLoadStatus(
                    state="invalid_json",
                    path=path_str,
                    detail=f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                )
            except OSError as exc:
                self._load_status = ConfigLoadStatus(
                    state="unreadable",
                    path=path_str,
                    detail=exc.strerror or "could not read configuration file",
                )
            else:
                if isinstance(loaded, dict):
                    payload.update(loaded)
                    self._load_status = ConfigLoadStatus(state="loaded", path=path_str)
                else:
                    self._load_status = ConfigLoadStatus(
                        state="invalid_shape",
                        path=path_str,
                        detail=f"Expected a JSON object but found {type(loaded).__name__}",
                    )
        else:
            self._load_status = ConfigLoadStatus(state="missing", path=path_str)

        if payload.get("api_key") and not payload.get("access_token"):
            payload["access_token"] = payload.get("api_key")
            migrated = True

        if "api_key" in payload:
            payload.pop("api_key", None)
            migrated = True

        payload["api_url"] = _normalize_api_url(payload.get("api_url")) or LOCAL_API_URL
        payload.setdefault("assistant_defaults", self._default_config()["assistant_defaults"])

        if migrated:
            self._config = payload
            self.save()

        return payload

    @property
    def load_status(self) -> ConfigLoadStatus:
        return self._load_status

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(self._config)
        payload.pop("api_key", None)
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    @property
    def api_url(self) -> str:
        if self._runtime_api_url_override:
            return self._runtime_api_url_override
        return _normalize_api_url(self._config.get("api_url")) or LOCAL_API_URL

    @property
    def api_url_source(self) -> str:
        if self._runtime_api_url_override:
            return "environment" if os.getenv("MUTX_API_URL") else "flag"
        return "config"

    @api_url.setter
    def api_url(self, value: str):
        self._config["api_url"] = _normalize_api_url(value) or LOCAL_API_URL
        self.save()

    def set_runtime_api_url(self, value: str):
        self._runtime_api_url_override = _normalize_api_url(value)

    @property
    def access_token(self) -> Optional[str]:
        return self._config.get("access_token")

    @access_token.setter
    def access_token(self, value: Optional[str]):
        self._config["access_token"] = value
        self.save()

    @property
    def api_key(self) -> Optional[str]:
        return self.access_token

    @api_key.setter
    def api_key(self, value: Optional[str]):
        self.access_token = value

    @property
    def refresh_token(self) -> Optional[str]:
        return self._config.get("refresh_token")

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]):
        self._config["refresh_token"] = value
        self.save()

    @property
    def assistant_defaults(self) -> dict[str, Any]:
        payload = self._config.get("assistant_defaults")
        if isinstance(payload, dict):
            return dict(payload)
        return dict(self._default_config()["assistant_defaults"])

    def clear_auth(self):
        self._config["access_token"] = None
        self._config["refresh_token"] = None
        self.save()

    def is_authenticated(self) -> bool:
        return bool(self.access_token and self.refresh_token)


def current_config() -> CLIConfig:
    ctx = click.get_current_context(silent=True)
    if ctx and isinstance(ctx.obj, dict):
        config = ctx.obj.get("config")
        if isinstance(config, CLIConfig):
            return config
    return CLIConfig()


def resolve_hosted_api_url(config: CLIConfig, override: str | None = None) -> str:
    if override:
        return _normalize_api_url(override) or HOSTED_API_URL

    current = _normalize_api_url(config.api_url)
    if current and current != LOCAL_API_URL:
        return current

    return HOSTED_API_URL


def get_client(config: Optional[CLIConfig] = None) -> httpx.Client:
    if config is None:
        config = current_config()

    headers = {}
    if config.access_token:
        headers["Authorization"] = f"Bearer {config.access_token}"

    return httpx.Client(
        base_url=config.api_url,
        headers=headers,
        timeout=30.0,
    )
