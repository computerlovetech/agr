"""CLI tests for Pi tool support."""

from tests.cli.assertions import assert_cli


class TestPiAdd:
    """Tests for agr add with Pi tool."""

    def test_add_local_skill_to_pi_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add local skill installs to .pi/skills/<name>/."""
        cli_config('tools = ["pi"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".pi" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()


class TestPiSync:
    """Tests for agr sync with Pi tool."""

    def test_sync_installs_to_pi_when_configured(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync with tools = ["pi"] installs to correct path."""
        cli_config(
            """
tools = ["pi"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        installed = cli_project / ".pi" / "skills" / "test-skill"
        assert installed.exists()


class TestPiRemove:
    """Tests for agr remove with Pi tool."""

    def test_remove_cleans_up_pi_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove removes skill from .pi/skills/."""
        cli_config('tools = ["pi"]\ndependencies = []')
        agr("add", "./skills/test-skill")

        installed = cli_project / ".pi" / "skills" / "test-skill"
        assert installed.exists()

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert not installed.exists()


class TestMultiToolPiClaude:
    """Tests for multi-tool scenarios with Pi and Claude."""

    def test_add_installs_to_both_claude_and_pi(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add with tools = ["claude", "pi"] installs to both."""
        cli_config('tools = ["claude", "pi"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert (cli_project / ".claude" / "skills" / "test-skill").exists()
        assert (cli_project / ".pi" / "skills" / "test-skill").exists()
