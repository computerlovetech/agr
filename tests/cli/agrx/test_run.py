"""CLI tests for agrx command."""

import subprocess

import pytest

from tests.cli.assertions import assert_cli
from tests.cli.runner import run_cli


class TestAgrxBasic:
    """Basic agrx tests (no external CLI required)."""

    def test_agrx_help(self):
        """agrx --help shows help."""
        result = run_cli(["agrx", "--help"])

        assert_cli(result).succeeded().stdout_contains("Run a skill temporarily")

    def test_agrx_invalid_handle_fails(self, agrx):
        """agrx with invalid handle fails."""
        result = agrx("not-valid-handle")

        assert_cli(result).failed()

    def test_agrx_local_path_fails(self, agrx, cli_skill):
        """agrx with local path fails (only remote handles)."""
        result = agrx("./skills/test-skill")

        assert_cli(result).failed().stdout_contains("only works with remote handles")

    def test_agrx_outside_git_repo_without_global_fails(self, tmp_path):
        """agrx outside git repo without --global fails."""
        result = run_cli(["agrx", "user/skill"], cwd=tmp_path)

        assert_cli(result).failed().stdout_contains("Not in a git repository")


@pytest.mark.network
@pytest.mark.requires_cli("claude")
class TestAgrxWithClaude:
    """agrx tests that require Claude CLI."""

    def test_agrx_downloads_skill(self, agrx, cli_project):
        """agrx downloads and installs skill temporarily."""
        # This test requires a real skill that exists
        # Using a known public skill
        # Note: agrx runs claude interactively, so it will timeout
        # We just verify it starts downloading correctly
        try:
            result = agrx("maragudk/skills/collaboration", timeout=5)
            # If it completes quickly, check for expected output
            assert "Downloading" in result.stdout_raw or result.returncode == 0
        except subprocess.TimeoutExpired as e:
            # Expected - agrx runs claude interactively
            # Verify it started downloading before the timeout
            stdout = ""
            if e.stdout:
                stdout = (
                    e.stdout.decode("utf-8", errors="replace")
                    if isinstance(e.stdout, bytes)
                    else e.stdout
                )
            assert "Downloading" in stdout, (
                f"Expected download to start, got: {stdout!r}"
            )
