from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from cli.config import CLIConfig, LOCAL_API_URL
from cli.main import cli

SECRET_TOKEN = "super-secret-token-value"

# Valid JSON apart from a missing comma; deliberately embeds a token so we can
# assert the diagnostics never echo secret material.
CORRUPT_JSON_WITH_TOKEN = (
    "{\n"
    '  "api_url": "http://localhost:9999",\n'
    f'  "access_token": "{SECRET_TOKEN}"\n'
    '  "refresh_token": "rt"\n'
    "}\n"
)


class DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, object]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


# --- Unit coverage for CLIConfig.load_status -------------------------------


def test_load_status_missing_file(tmp_path: Path) -> None:
    config = CLIConfig(config_path=tmp_path / "config.json")

    status = config.load_status
    assert status.state == "missing"
    assert status.ok is True
    assert status.has_issue is False
    assert status.detail is None
    # Default behaviour is preserved.
    assert config.api_url == LOCAL_API_URL


def test_load_status_loaded_valid(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"api_url": "http://localhost:9999", "access_token": "tok"}),
        encoding="utf-8",
    )

    config = CLIConfig(config_path=config_path)

    status = config.load_status
    assert status.state == "loaded"
    assert status.ok is True
    assert status.has_issue is False
    assert status.detail is None
    assert config.api_url == "http://localhost:9999"
    assert config.access_token == "tok"


def test_load_status_invalid_json_falls_back_to_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(CORRUPT_JSON_WITH_TOKEN, encoding="utf-8")

    config = CLIConfig(config_path=config_path)

    status = config.load_status
    assert status.state == "invalid_json"
    assert status.has_issue is True
    assert status.detail is not None
    assert "line" in status.detail
    # Compatibility: corrupt file is ignored and defaults are used.
    assert config.api_url == LOCAL_API_URL
    assert config.access_token is None
    # The diagnostic must never leak token material.
    assert SECRET_TOKEN not in status.detail


def test_load_status_invalid_shape(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    config = CLIConfig(config_path=config_path)

    status = config.load_status
    assert status.state == "invalid_shape"
    assert status.has_issue is True
    assert "list" in (status.detail or "")
    assert config.api_url == LOCAL_API_URL


def test_load_status_unreadable_path(tmp_path: Path) -> None:
    # A directory at the config path exists() but cannot be opened as a file,
    # which deterministically exercises the OSError branch on POSIX systems.
    config_path = tmp_path / "config.json"
    config_path.mkdir()

    config = CLIConfig(config_path=config_path)

    status = config.load_status
    assert status.state == "unreadable"
    assert status.has_issue is True
    assert status.detail
    assert config.api_url == LOCAL_API_URL


# --- `mutx config show` ----------------------------------------------------


def test_config_show_reports_loaded(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"api_url": "http://localhost:9999"}), encoding="utf-8")
    config = CLIConfig(config_path=config_path)
    monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

    result = CliRunner().invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert "Config Source:  loaded from file" in result.output
    assert "Config Detail:" not in result.output


def test_config_show_reports_missing(monkeypatch, tmp_path: Path) -> None:
    config = CLIConfig(config_path=tmp_path / "config.json")
    monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

    result = CliRunner().invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert "no config file found" in result.output


def test_config_show_reports_invalid_json_without_leaking_token(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(CORRUPT_JSON_WITH_TOKEN, encoding="utf-8")
    config = CLIConfig(config_path=config_path)
    monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

    result = CliRunner().invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert "invalid JSON" in result.output
    assert "Config Detail:" in result.output
    assert str(config_path) in result.output
    assert SECRET_TOKEN not in result.output


# --- `mutx doctor` ---------------------------------------------------------


def _stub_doctor_dependencies(monkeypatch) -> None:
    class DummyService:
        def __init__(self, *args, **kwargs):
            pass

        def status(self):
            return SimpleNamespace(authenticated=False)

    monkeypatch.setattr("cli.commands.doctor.AuthService", DummyService)
    monkeypatch.setattr("cli.commands.doctor.AssistantService", DummyService)
    monkeypatch.setattr("cli.commands.doctor.RuntimeStateService", DummyService)
    monkeypatch.setattr(
        "cli.commands.doctor.prepare_runtime_state_sync",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "cli.commands.doctor.get_gateway_health",
        lambda: SimpleNamespace(
            to_payload=lambda: {
                "status": "unknown",
                "gateway_url": None,
                "onboarded": False,
            }
        ),
    )
    monkeypatch.setattr(
        "cli.commands.doctor.collect_openclaw_runtime_snapshot",
        lambda: SimpleNamespace(
            to_payload=lambda: {
                "binding_count": 0,
                "binary_path": None,
                "home_path": None,
                "last_seen_at": None,
                "privacy_summary": None,
            }
        ),
    )
    monkeypatch.setattr(
        "cli.commands.doctor.get_document_engine_readiness",
        lambda: SimpleNamespace(
            to_payload=lambda: {
                "enabled": False,
                "ready": False,
                "driver": "unavailable",
                "deno_available": False,
                "predict_rlm_available": False,
                "credentials_ok": False,
            }
        ),
    )
    monkeypatch.setattr(
        "cli.commands.doctor.httpx.get",
        lambda url, timeout=2.0: DummyResponse(200, {"status": "healthy"}),
    )


def test_doctor_json_reports_invalid_config_without_leaking_token(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(CORRUPT_JSON_WITH_TOKEN, encoding="utf-8")
    config = CLIConfig(config_path=config_path)
    monkeypatch.setattr("cli.main.CLIConfig", lambda: config)
    _stub_doctor_dependencies(monkeypatch)

    result = CliRunner().invoke(cli, ["doctor", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_source"]["state"] == "invalid_json"
    assert payload["config_source"]["path"] == str(config_path)
    assert payload["config_source"]["detail"]
    assert SECRET_TOKEN not in result.output


def test_doctor_table_reports_config_issue(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(CORRUPT_JSON_WITH_TOKEN, encoding="utf-8")
    config = CLIConfig(config_path=config_path)
    monkeypatch.setattr("cli.main.CLIConfig", lambda: config)
    _stub_doctor_dependencies(monkeypatch)

    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "Config Source: config file ignored: invalid JSON" in result.output
    assert "Config Issue:" in result.output
    assert SECRET_TOKEN not in result.output
