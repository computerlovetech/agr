"""CLI tests for agr init command."""

from agr.config import AgrConfig
from tests.cli.assertions import assert_cli


class TestAgrInit:
    """Tests for agr init command."""

    def test_init_creates_agr_toml(self, agr, cli_project):
        """agr init creates agr.toml file."""
        result = agr("init")

        assert_cli(result).succeeded()
        assert (cli_project / "agr.toml").exists()

    def test_init_detects_antigravity_tools(self, agr, cli_project):
        """agr init detects Antigravity tools when .agent/skills exists."""
        skill_dir = cli_project / ".agent" / "skills" / "alpha"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: alpha\n---\n\n# alpha\n")

        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "antigravity" in config.tools

    def test_init_adds_discovered_skills(self, agr, cli_project, cli_skill):
        """agr init adds discovered skills to agr.toml."""
        result = agr("init")

        assert_cli(result).succeeded()
        config = (cli_project / "agr.toml").read_text()
        assert "skills/test-skill" in config

    def test_init_does_not_duplicate_paths(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr init avoids duplicating local dependency paths."""
        content = 'dependencies = [{ path = "skills/test-skill", type = "skill" }]\n'
        cli_config(content)

        result = agr("init")

        assert_cli(result).succeeded()
        assert (cli_project / "agr.toml").read_text() == content

    def test_init_existing_returns_existing(self, agr, cli_project, cli_config):
        """agr init with existing config returns it."""
        cli_config("dependencies = []")

        result = agr("init")

        assert_cli(result).succeeded().stdout_contains("Already exists")

    def test_init_skill_creates_scaffold(self, agr, cli_project):
        """agr init <name> creates skill scaffold."""
        result = agr("init", "my-new-skill")

        assert_cli(result).succeeded()
        skill_dir = cli_project / "my-new-skill"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()

    def test_init_skill_invalid_name_fails(self, agr):
        """agr init with invalid skill name fails."""
        result = agr("init", "invalid name with spaces")

        assert_cli(result).failed().stdout_contains("Invalid skill name")

    def test_init_skill_existing_directory_fails(self, agr, cli_project):
        """agr init with existing directory fails."""
        (cli_project / "existing-skill").mkdir()
        result = agr("init", "existing-skill")

        assert_cli(result).failed()

    def test_init_default_tool_not_in_tools_fails(self, agr):
        """agr init fails when default_tool is not in tools."""
        result = agr("init", "--default-tool", "codex")

        assert_cli(result).failed().stdout_contains(
            "default_tool must be listed in tools"
        )

    def test_init_discovers_tools_and_syncs_instructions(self, agr, cli_project):
        """Onboarding flow discovers skills, configures tools, and syncs instructions."""
        claude_skill = cli_project / ".claude" / "skills" / "alpha"
        codex_skill = cli_project / ".agents" / "skills" / "beta"
        for skill_dir in [claude_skill, codex_skill]:
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {skill_dir.name}\n---\n\n# {skill_dir.name}\n"
            )

        (cli_project / "CLAUDE.md").write_text("Claude instructions\n")
        (cli_project / "AGENTS.md").write_text("Agents instructions\n")

        result = agr(
            "init",
            "--tools",
            "claude,codex",
            "--default-tool",
            "claude",
            "--sync-instructions",
            "--migrate",
        )

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        paths = {dep.path for dep in config.dependencies if dep.path}
        assert "./skills/alpha" in paths
        assert "./skills/beta" in paths
        assert config.tools == ["claude", "codex"]
        assert config.default_tool == "claude"
        assert config.sync_instructions is True
        assert config.canonical_instructions == "CLAUDE.md"

        sync_result = agr("sync")
        assert_cli(sync_result).succeeded()
        assert (cli_project / "AGENTS.md").read_text() == (
            cli_project / "CLAUDE.md"
        ).read_text()
        assert (claude_skill / ".agr.json").exists()
        assert (codex_skill / ".agr.json").exists()
