"""Tests that verify CLI help text includes scenario-oriented guidance.

These tests ensure that `mutx --help` and subcommand help output contain
clear pointers to the right commands for common developer tasks (setup,
diagnose, status, runtime inspection).
"""
from __future__ import annotations

import re

from click.testing import CliRunner

from cli.main import cli


def _help_output(args: list[str]) -> str:
    runner = CliRunner()
    result = runner.invoke(cli, args + ["--help"])
    assert result.exit_code == 0, f"help failed for {args}: {result.output}"
    return result.output


def _norm(text: str) -> str:
    """Collapse whitespace (including newlines inserted by Click wrapping)."""
    return re.sub(r"\s+", " ", text)


class TestTopLevelHelp:
    def test_includes_getting_started_section(self) -> None:
        output = _help_output([])
        assert "Getting started" in output

    def test_mentions_setup_hosted(self) -> None:
        assert "mutx setup hosted" in _norm(_help_output([]))

    def test_mentions_setup_local(self) -> None:
        assert "mutx setup local" in _norm(_help_output([]))

    def test_mentions_doctor(self) -> None:
        assert "mutx doctor" in _norm(_help_output([]))

    def test_mentions_status(self) -> None:
        assert "mutx status" in _norm(_help_output([]))

    def test_mentions_onboard(self) -> None:
        assert "mutx onboard" in _norm(_help_output([]))


class TestDoctorHelp:
    def test_describes_diagnostic_purpose(self) -> None:
        output = _help_output(["doctor"])
        assert "Diagnose" in output

    def test_lists_checks(self) -> None:
        output = _help_output(["doctor"])
        assert "API URL" in output
        assert "Authentication" in output
        assert "OpenClaw" in output

    def test_recommends_running_after_setup(self) -> None:
        assert "mutx setup" in _norm(_help_output(["doctor"]))


class TestSetupHelp:
    def test_setup_group_mentions_both_paths(self) -> None:
        n = _norm(_help_output(["setup"]))
        assert "mutx setup hosted" in n
        assert "mutx setup local" in n

    def test_setup_group_recommends_doctor(self) -> None:
        assert "mutx doctor" in _norm(_help_output(["setup"]))


class TestSetupHostedHelp:
    def test_describes_hosted_use_case(self) -> None:
        output = _help_output(["setup", "hosted"])
        assert "hosted" in output.lower()

    def test_recommends_doctor_after_setup(self) -> None:
        assert "mutx doctor" in _norm(_help_output(["setup", "hosted"]))


class TestSetupLocalHelp:
    def test_describes_local_use_case(self) -> None:
        output = _help_output(["setup", "local"])
        assert "local" in output.lower()
        assert "Docker" in output

    def test_recommends_doctor_after_setup(self) -> None:
        assert "mutx doctor" in _norm(_help_output(["setup", "local"]))


class TestStatusHelp:
    def test_describes_what_status_shows(self) -> None:
        output = _help_output(["status"])
        assert "API URL" in output

    def test_explains_when_to_run(self) -> None:
        output = _help_output(["status"])
        assert "auth" in output.lower() or "credential" in output.lower()


class TestRuntimeHelp:
    def test_lists_common_commands(self) -> None:
        n = _norm(_help_output(["runtime"]))
        assert "mutx runtime list" in n
        assert "mutx runtime inspect" in n

    def test_recommends_inspect_after_setup(self) -> None:
        output = _help_output(["runtime"])
        assert "setup" in output.lower()
