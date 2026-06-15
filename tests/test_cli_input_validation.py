"""Tests for CLI input validation and user-readable error handling.

Covers the ``config`` command group and ``login`` command to ensure that
invalid arguments, empty values, and malformed URLs produce clear error
messages with non-zero exit codes and *no* Python tracebacks.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import click
from click.testing import CliRunner

from cli.config import CLIConfig
from cli.main import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path: Path) -> CLIConfig:
    """Return a ``CLIConfig`` backed by *tmp_path*."""
    return CLIConfig(config_path=tmp_path / "config.json")


def _assert_no_traceback(result) -> None:
    """Fail the test if *result* contains a Python traceback."""
    assert "Traceback" not in result.output, (
        f"Unexpected traceback in output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# config get
# ---------------------------------------------------------------------------

class TestConfigGet:
    def test_invalid_key_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "get", "bogus_key"])

        assert result.exit_code != 0
        assert "Invalid key 'bogus_key'" in result.output
        _assert_no_traceback(result)

    def test_empty_key_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "get", "   "])

        assert result.exit_code != 0
        assert "must not be empty" in result.output.lower()
        _assert_no_traceback(result)

    def test_valid_key_succeeds(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "get", "api_url"])

        assert result.exit_code == 0
        assert "http" in result.output
        _assert_no_traceback(result)


# ---------------------------------------------------------------------------
# config set
# ---------------------------------------------------------------------------

class TestConfigSet:
    def test_invalid_key_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "access_token", "some-value"])

        assert result.exit_code != 0
        assert "Invalid key 'access_token'" in result.output
        _assert_no_traceback(result)

    def test_empty_value_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_url"])

        assert result.exit_code != 0
        assert "VALUE must not be empty" in result.output
        _assert_no_traceback(result)

    def test_whitespace_only_value_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_url", "   "])

        assert result.exit_code != 0
        assert "VALUE must not be empty" in result.output
        _assert_no_traceback(result)

    def test_invalid_url_returns_bad_parameter(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_url", "not-a-url"])

        assert result.exit_code != 0
        assert "not a valid URL" in result.output
        _assert_no_traceback(result)

    def test_url_without_scheme_returns_bad_parameter(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_url", "example.com"])

        assert result.exit_code != 0
        assert "not a valid URL" in result.output
        _assert_no_traceback(result)

    def test_valid_url_succeeds(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_url", "https://api.example.com"])

        assert result.exit_code == 0
        assert "API URL set to:" in result.output
        _assert_no_traceback(result)

    def test_unset_flag_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_url", "--unset"])

        assert result.exit_code != 0
        assert "Cannot unset" in result.output
        _assert_no_traceback(result)


# ---------------------------------------------------------------------------
# config unset
# ---------------------------------------------------------------------------

class TestConfigUnset:
    def test_invalid_key_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "unset", "api_url", "--force"])

        assert result.exit_code != 0
        assert "Invalid key 'api_url'" in result.output
        _assert_no_traceback(result)

    def test_empty_key_returns_usage_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "unset", "   ", "--force"])

        assert result.exit_code != 0
        assert "must not be empty" in result.output.lower()
        _assert_no_traceback(result)

    def test_valid_key_with_force_succeeds(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        config.access_token = "test-token"
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "unset", "access_token", "--force"])

        assert result.exit_code == 0
        assert "Unset access_token" in result.output
        _assert_no_traceback(result)


# ---------------------------------------------------------------------------
# login (empty input validation)
# ---------------------------------------------------------------------------

class TestLoginValidation:
    def test_empty_email_returns_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["login", "--email", "", "--password", "password"])

        assert "Email must not be empty" in result.output
        _assert_no_traceback(result)

    def test_whitespace_email_returns_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["login", "--email", "   ", "--password", "password"])

        assert "Email must not be empty" in result.output
        _assert_no_traceback(result)

    def test_empty_password_returns_error(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["login", "--email", "user@example.com", "--password", ""])

        assert "Password must not be empty" in result.output
        _assert_no_traceback(result)


# ---------------------------------------------------------------------------
# config show (sanity check — no validation needed, just ensure it works)
# ---------------------------------------------------------------------------

class TestConfigShow:
    def test_show_succeeds(self, monkeypatch, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        monkeypatch.setattr("cli.main.CLIConfig", lambda: config)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "API URL:" in result.output
        _assert_no_traceback(result)
