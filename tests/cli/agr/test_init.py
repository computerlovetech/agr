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

    def test_init_detects_tools_from_config_dirs(self, agr, cli_project):
        """agr init detects tools when .claude/ and .cursor/ exist."""
        (cli_project / ".claude").mkdir()
        (cli_project / ".cursor").mkdir()

        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "claude" in config.tools
        assert "cursor" in config.tools

    def test_init_detects_tools_from_instruction_files(self, agr, cli_project):
        """agr init detects claude from CLAUDE.md file."""
        (cli_project / "CLAUDE.md").write_text("# Instructions\n")

        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "claude" in config.tools

    def test_init_detects_tools_from_cursorrules(self, agr, cli_project):
        """agr init detects cursor from .cursorrules file."""
        (cli_project / ".cursorrules").write_text("rules\n")

        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "cursor" in config.tools

    def test_init_no_tools_detected_defaults_to_claude(self, agr, cli_project):
        """agr init with no signals defaults to claude."""
        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]

    def test_init_tools_flag_overrides_detection(self, agr, cli_project):
        """agr init --tools codex ignores detected tools."""
        (cli_project / ".claude").mkdir()

        result = agr("init", "--tools", "codex")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["codex"]

    def test_init_does_not_discover_skills(self, agr, cli_project, cli_skill):
        """agr init does NOT add discovered skills to config (onboard's job)."""
        result = agr("init")

        assert_cli(result).succeeded()
        config = (cli_project / "agr.toml").read_text()
        assert "skills/test-skill" not in config

    def test_init_existing_config_no_overwrite(self, agr, cli_project, cli_config):
        """agr init with existing config prints 'Already exists' and exits 0."""
        cli_config("dependencies = []")

        result = agr("init")

        assert_cli(result).succeeded().stdout_contains("Already exists")

    def test_init_quiet_suppresses_output(self, agr, cli_project):
        """agr -q init produces no stdout output."""
        result = agr("-q", "init")

        assert_cli(result).succeeded().stdout_is_empty()
        assert (cli_project / "agr.toml").exists()

    def test_init_skill_scaffold_unchanged(self, agr, cli_project):
        """agr init <name> still creates skill scaffold."""
        result = agr("init", "my-new-skill")

        assert_cli(result).succeeded()
        skill_dir = cli_project / "my-new-skill"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()

    def test_init_no_interactive_flag(self, agr):
        """agr init -i is rejected as unknown option."""
        result = agr("init", "-i")

        assert_cli(result).failed()

    def test_init_no_migrate_flag(self, agr):
        """agr init --migrate is rejected as unknown option."""
        result = agr("init", "--migrate")

        assert_cli(result).failed()

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
        """Init with explicit flags configures tools and instruction sync."""
        (cli_project / "CLAUDE.md").write_text("Claude instructions\n")
        (cli_project / "AGENTS.md").write_text("Agents instructions\n")

        result = agr(
            "init",
            "--tools",
            "claude,codex",
            "--default-tool",
            "claude",
            "--sync-instructions",
        )

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude", "codex"]
        assert config.default_tool == "claude"
        assert config.sync_instructions is True
        assert config.canonical_instructions == "CLAUDE.md"

    def test_init_detects_antigravity_tools(self, agr, cli_project):
        """agr init detects Antigravity tools when .gemini/ exists."""
        (cli_project / ".gemini").mkdir()

        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "antigravity" in config.tools

    def test_init_detects_antigravity_from_agents_dir(self, agr, cli_project):
        """agr init detects Antigravity from .agents/ directory (shared with Codex)."""
        (cli_project / ".agents").mkdir()

        result = agr("init")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "antigravity" in config.tools
