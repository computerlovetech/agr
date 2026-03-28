"""CLI tests for agrx --tool flag."""

import shutil

import pytest

from tests.cli.assertions import assert_cli
from tests.cli.runner import run_cli


class TestAgrxToolFlag:
    """Tests for agrx --tool flag."""

    def test_agrx_help_shows_tool_option(self):
        """agrx --help shows --tool option."""
        result = run_cli(["agrx", "--help"])

        assert_cli(result).succeeded().stdout_contains("--tool")
        assert_cli(result).stdout_contains("-t")

    def test_agrx_invalid_tool_fails(self, agrx):
        """agrx with invalid tool fails."""
        result = agrx("user/skill", "--tool", "invalid-tool")

        assert_cli(result).failed().stdout_contains("Unknown tool")

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_agrx_tool_cli_not_found_cursor(self, agrx):
        """agrx --tool cursor fails when agent CLI not found."""
        result = agrx("user/skill", "--tool", "cursor")

        assert_cli(result).failed().stdout_contains("agent CLI not found")

    @pytest.mark.skipif(
        shutil.which("copilot") is not None, reason="copilot CLI is installed"
    )
    def test_agrx_tool_cli_not_found_copilot(self, agrx):
        """agrx --tool copilot fails when copilot CLI not found."""
        result = agrx("user/skill", "--tool", "copilot")

        assert_cli(result).failed().stdout_contains("copilot CLI not found")

    @pytest.mark.skipif(
        shutil.which("codex") is not None, reason="codex CLI is installed"
    )
    def test_agrx_tool_cli_not_found_codex(self, agrx):
        """agrx --tool codex fails when codex CLI not found."""
        result = agrx("user/skill", "--tool", "codex")

        assert_cli(result).failed().stdout_contains("codex CLI not found")

    @pytest.mark.skipif(
        shutil.which("opencode") is not None, reason="opencode CLI is installed"
    )
    def test_agrx_tool_cli_not_found_opencode(self, agrx):
        """agrx --tool opencode fails when opencode CLI not found."""
        result = agrx("user/skill", "--tool", "opencode")

        assert_cli(result).failed().stdout_contains("opencode CLI not found")

    def test_agrx_tool_no_cli_antigravity(self, agrx):
        """agrx --tool antigravity fails when no CLI is configured."""
        result = agrx("user/skill", "--tool", "antigravity")

        assert_cli(result).failed().stdout_contains("has no CLI command configured")


class TestAgrxToolFromConfig:
    """Tests for agrx using tool from agr.toml."""

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_agrx_default_tool_from_config(self, agrx, cli_config):
        """agrx uses first tool from agr.toml as default."""
        # Configure cursor as first tool
        cli_config('tools = ["cursor", "claude"]\ndependencies = []')

        result = agrx("user/skill")

        # Should try to use cursor (first in config) and fail since not installed
        assert_cli(result).failed().stdout_contains("agent CLI not found")

    @pytest.mark.skipif(
        shutil.which("claude") is not None, reason="claude CLI is installed"
    )
    def test_agrx_default_tool_fallback_claude(self, agrx):
        """agrx falls back to claude when no agr.toml."""
        result = agrx("user/skill")

        # Should try to use claude (default) and fail since not installed
        assert_cli(result).failed().stdout_contains("claude CLI not found")

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_agrx_tool_flag_overrides_config(self, agrx, cli_config):
        """agrx --tool overrides agr.toml config."""
        # Configure claude as first tool
        cli_config('tools = ["claude"]\ndependencies = []')

        # Explicitly use cursor, should try agent CLI
        result = agrx("user/skill", "--tool", "cursor")

        assert_cli(result).failed().stdout_contains("agent CLI not found")

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_agrx_default_tool_override(self, agrx, cli_config):
        """agrx uses default_tool from agr.toml when set."""
        cli_config(
            'tools = ["claude", "cursor"]\ndefault_tool = "cursor"\ndependencies = []'
        )

        result = agrx("user/skill")

        assert_cli(result).failed().stdout_contains("agent CLI not found")
