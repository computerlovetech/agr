"""CLI tests for Cursor tool support.

Cursor uses flat naming like Claude: skills are direct children of the
skills directory.  Per the Cursor docs, skill identifiers are "lowercase
letters, numbers, and hyphens only" and must match the parent folder name.
"""

import pytest

from tests.cli.assertions import assert_cli


class TestCursorAdd:
    """Tests for agr add with Cursor tool."""

    def test_add_local_skill_to_cursor_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add local skill installs to .cursor/skills/<name>/."""
        cli_config('tools = ["cursor"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        # Cursor uses flat structure: <name>
        installed = cli_project / ".cursor" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()

    @pytest.mark.network
    def test_add_remote_skill_to_cursor_flat_structure(
        self, agr, cli_project, cli_config
    ):
        """agr add remote skill installs to .cursor/skills/<name>/."""
        cli_config('tools = ["cursor"]\ndependencies = []')

        result = agr("add", "kasperjunge/agent-resources-public-test-repo/test-skill")

        assert_cli(result).succeeded()
        # Cursor uses flat structure: <name>
        installed = cli_project / ".cursor" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()


class TestCursorSync:
    """Tests for agr sync with Cursor tool."""

    def test_sync_installs_to_cursor_when_configured(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync installs to Cursor when configured in agr.toml."""
        cli_config(
            """
tools = ["cursor"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        installed = cli_project / ".cursor" / "skills" / "test-skill"
        assert installed.exists()

    def test_sync_creates_cursor_skills_directory(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync creates .cursor/skills/ if it doesn't exist."""
        cli_config(
            """
tools = ["cursor"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Ensure no .cursor directory exists
        cursor_dir = cli_project / ".cursor"
        assert not cursor_dir.exists()

        result = agr("sync")

        assert_cli(result).succeeded()
        assert cursor_dir.exists()
        assert (cursor_dir / "skills" / "test-skill").exists()


class TestCursorRemove:
    """Tests for agr remove with Cursor tool."""

    def test_remove_cleans_up_cursor_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove removes skill from Cursor flat structure."""
        cli_config('tools = ["cursor"]\ndependencies = []')
        agr("add", "./skills/test-skill")

        installed = cli_project / ".cursor" / "skills" / "test-skill"
        assert installed.exists()

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert not installed.exists()


class TestMultiToolCursorClaude:
    """Tests for multi-tool scenarios with Cursor and Claude."""

    def test_add_installs_to_both_claude_and_cursor(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add with tools = ["claude", "cursor"] installs to both."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()

        # Claude uses flat structure
        claude_installed = cli_project / ".claude" / "skills" / "test-skill"
        assert claude_installed.exists()
        assert (claude_installed / "SKILL.md").exists()

        # Cursor also uses flat structure
        cursor_installed = cli_project / ".cursor" / "skills" / "test-skill"
        assert cursor_installed.exists()
        assert (cursor_installed / "SKILL.md").exists()

    def test_sync_installs_to_both_tools(self, agr, cli_project, cli_skill, cli_config):
        """agr sync with multiple tools installs to all configured tools."""
        cli_config(
            """
tools = ["claude", "cursor"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        assert (cli_project / ".claude" / "skills" / "test-skill").exists()
        assert (cli_project / ".cursor" / "skills" / "test-skill").exists()

    def test_remove_removes_from_both_tools(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove removes skill from all configured tools."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')
        agr("add", "./skills/test-skill")

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert not (cli_project / ".claude" / "skills" / "test-skill").exists()
        assert not (cli_project / ".cursor" / "skills" / "test-skill").exists()


class TestCursorErrors:
    """Tests for error handling with Cursor tool."""

    def test_invalid_tool_name_in_config_fails(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """Invalid tool name in config fails with clear error."""
        cli_config('tools = ["cursor", "invalid"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).failed().stderr_contains("Unknown tool")
