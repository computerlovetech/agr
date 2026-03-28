"""CLI tests for Antigravity tool support."""

from tests.cli.assertions import assert_cli


class TestAntigravityAdd:
    """Tests for agr add with Antigravity tool."""

    def test_add_local_skill_to_antigravity_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add local skill installs to .gemini/skills/<name>/."""
        cli_config('tools = ["antigravity"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".gemini" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()


class TestAntigravitySync:
    """Tests for agr sync with Antigravity tool."""

    def test_sync_installs_to_antigravity_when_configured(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync with tools = ["antigravity"] installs to correct path."""
        cli_config(
            """
tools = ["antigravity"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        installed = cli_project / ".gemini" / "skills" / "test-skill"
        assert installed.exists()


class TestAntigravityRemove:
    """Tests for agr remove with Antigravity tool."""

    def test_remove_cleans_up_antigravity_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove removes skill from .gemini/skills/."""
        cli_config('tools = ["antigravity"]\ndependencies = []')
        agr("add", "./skills/test-skill")

        installed = cli_project / ".gemini" / "skills" / "test-skill"
        assert installed.exists()

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert not installed.exists()


class TestMultiToolAntigravityClaude:
    """Tests for multi-tool scenarios with Antigravity and Claude."""

    def test_add_installs_to_both_claude_and_antigravity(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add with tools = ["claude", "antigravity"] installs to both."""
        cli_config('tools = ["claude", "antigravity"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert (cli_project / ".claude" / "skills" / "test-skill").exists()
        assert (cli_project / ".gemini" / "skills" / "test-skill").exists()
