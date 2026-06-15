from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from cli.config import CLIConfig
from cli.main import cli

DEFAULT_API_URL = "http://localhost:8000"


def _combined(result) -> str:
    """Return stdout+stderr regardless of how the Click version routes them.

    Click >= 8.2 captures stderr separately; older Click mixes it into stdout and
    raises when stderr is accessed. This keeps assertions stable across both.
    """
    text = getattr(result, "output", "") or ""
    try:
        err = result.stderr or ""
    except Exception:  # pragma: no cover - depends on Click version
        err = ""
    if err and err not in text:
        text += err
    return text


def _use_temp_config(monkeypatch, tmp_path: Path) -> CLIConfig:
    """Point the CLI at an isolated, on-disk config for the duration of a test."""
    config = CLIConfig(config_path=tmp_path / "config.json")
    monkeypatch.setattr("cli.main.CLIConfig", lambda: config)
    return config


def test_config_set_api_url_accepts_valid_url(monkeypatch, tmp_path: Path) -> None:
    config = _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "api_url", "https://api.example.com"])

    assert result.exit_code == 0
    assert "API URL set to: https://api.example.com" in _combined(result)
    assert "Traceback" not in _combined(result)
    assert config.api_url == "https://api.example.com"


def test_config_set_api_url_rejects_missing_value(monkeypatch, tmp_path: Path) -> None:
    config = _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "api_url"])

    assert result.exit_code == 0
    assert "A value is required" in _combined(result)
    assert "Traceback" not in _combined(result)
    # A missing value must not silently overwrite the existing configuration.
    assert config.api_url == DEFAULT_API_URL


def test_config_set_api_url_rejects_blank_value(monkeypatch, tmp_path: Path) -> None:
    config = _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "api_url", "   "])

    assert result.exit_code == 0
    assert "A value is required" in _combined(result)
    assert "Traceback" not in _combined(result)
    assert config.api_url == DEFAULT_API_URL


def test_config_set_api_url_rejects_value_without_scheme(monkeypatch, tmp_path: Path) -> None:
    config = _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "api_url", "localhost:8000"])

    assert result.exit_code == 0
    assert "Invalid api_url" in _combined(result)
    assert "http://" in _combined(result)
    assert "Traceback" not in _combined(result)
    assert config.api_url == DEFAULT_API_URL


def test_config_set_api_url_rejects_non_url_value(monkeypatch, tmp_path: Path) -> None:
    config = _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "api_url", "not-a-url"])

    assert result.exit_code == 0
    assert "Invalid api_url" in _combined(result)
    assert "Traceback" not in _combined(result)
    assert config.api_url == DEFAULT_API_URL


def test_config_set_rejects_unknown_key(monkeypatch, tmp_path: Path) -> None:
    _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "bogus", "value"])

    assert result.exit_code == 0
    assert "Invalid key 'bogus'" in _combined(result)
    assert "Traceback" not in _combined(result)


def test_config_get_rejects_unknown_key(monkeypatch, tmp_path: Path) -> None:
    _use_temp_config(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "get", "bogus"])

    assert result.exit_code == 0
    assert "Invalid key 'bogus'" in _combined(result)
    assert "Traceback" not in _combined(result)
