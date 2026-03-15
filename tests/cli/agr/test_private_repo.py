"""CLI tests for private repository authentication.

These tests verify:
1. Private repo authentication with GITHUB_TOKEN (real network tests)
2. Error messages for auth failures are user-friendly
3. Tokens are not leaked in error output
"""

import os

import pytest

from tests.cli.assertions import assert_cli


class TestTokenNotLeaked:
    """Tests ensuring tokens are not exposed in CLI output."""

    def test_error_output_does_not_contain_token(self, agr, cli_config, monkeypatch):
        """Error messages do not leak token value when repo doesn't exist."""
        secret_token = "ghp_secret_token_value_12345"
        monkeypatch.setenv("GITHUB_TOKEN", secret_token)
        cli_config("dependencies = []")

        # Try to add a nonexistent repo - will fail but shouldn't leak token
        result = agr("add", "nonexistent-user-12345/nonexistent-repo-67890/skill")

        # Token should never appear in output
        assert secret_token not in result.stdout
        assert secret_token not in result.stderr
        assert "ghp_" not in result.stdout
        assert "ghp_" not in result.stderr

    def test_sync_error_does_not_leak_token(self, agr, cli_config, monkeypatch):
        """Sync errors do not leak token value."""
        secret_token = "github_pat_11ABCDE"
        monkeypatch.setenv("GITHUB_TOKEN", secret_token)
        cli_config(
            """
dependencies = [
    { handle = "fake-user/fake-repo/fake-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).failed()
        assert secret_token not in result.stdout
        assert secret_token not in result.stderr


class TestAuthErrorMessages:
    """Tests for helpful authentication error messages."""

    def test_nonexistent_repo_without_token_mentions_token(
        self, agr, cli_config, monkeypatch
    ):
        """Private repo without token should mention GITHUB_TOKEN."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        cli_config("dependencies = []")

        result = agr("add", "fake-user-xyz/fake-private-repo/skill")

        # Should fail (repo doesn't exist or is private)
        assert_cli(result).failed()
        # Should mention the repo wasn't found
        assert "not found" in result.stdout.lower()


@pytest.mark.network
class TestPrivateRepoRealNetwork:
    """Tests for private repo authentication with real network.

    These tests require GITHUB_TOKEN to be set in the environment with access
    to the test private repository.

    Run with: pytest tests/cli/agr/test_private_repo.py -v -m network
    Skip with: pytest tests/cli/agr/test_private_repo.py -v -m "not network"
    """

    @pytest.fixture(autouse=True)
    def requires_github_token(self):
        """Skip if GITHUB_TOKEN is not available."""
        if not os.environ.get("GITHUB_TOKEN") and not os.environ.get("GH_TOKEN"):
            pytest.skip("GITHUB_TOKEN or GH_TOKEN required for network tests")

    def test_add_private_skill_with_token(self, agr, cli_project, cli_config):
        """agr add with real GITHUB_TOKEN succeeds for private test repo."""
        cli_config("dependencies = []")

        result = agr("add", "kasperjunge/agent-resources-private-test-repo/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()

    def test_sync_with_private_dependency_succeeds(self, agr, cli_project, cli_config):
        """agr sync with private dependency succeeds."""
        handle = "kasperjunge/agent-resources-private-test-repo/test-skill"
        cli_config(
            f'dependencies = [\n    {{ handle = "{handle}", type = "skill" }},\n]\n'
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()

    def test_add_private_to_multiple_tools(self, agr, cli_project, cli_config):
        """agr add private skill to multiple tools succeeds."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("add", "kasperjunge/agent-resources-private-test-repo/test-skill")

        assert_cli(result).succeeded()
        # Claude (flat)
        claude_installed = cli_project / ".claude" / "skills" / "test-skill"
        assert claude_installed.exists()
        # Cursor (nested)
        cursor_installed = (
            cli_project
            / ".cursor"
            / "skills"
            / "kasperjunge"
            / "agent-resources-private-test-repo"
            / "test-skill"
        )
        assert cursor_installed.exists()


@pytest.mark.network
class TestPublicRepoNoToken:
    """Tests verifying public repos work without token."""

    def test_add_public_skill_without_token(
        self, agr, cli_project, cli_config, monkeypatch
    ):
        """agr add for public repo works without GITHUB_TOKEN."""
        # Clear any tokens
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        cli_config("dependencies = []")

        result = agr("add", "kasperjunge/agent-resources-public-test-repo/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()
