"""CLI tests for agr add command."""

from agr.config import DEPENDENCY_TYPE_RALPH, AgrConfig
from tests.cli.assertions import assert_cli


class TestAgrAdd:
    """Tests for agr add command."""

    def test_add_local_skill_succeeds(self, agr, cli_skill):
        """agr add ./path adds local skill."""
        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded().stdout_contains("Added:")

    def test_add_local_skill_creates_installed_dir(self, agr, cli_project, cli_skill):
        """agr add creates skill in .claude/skills."""
        agr("add", "./skills/test-skill")

        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()

    def test_add_local_skill_updates_config(self, agr, cli_project, cli_skill):
        """agr add updates agr.toml."""
        agr("add", "./skills/test-skill")

        config = (cli_project / "agr.toml").read_text()
        assert "skills/test-skill" in config

    def test_add_nonexistent_skill_fails(self, agr):
        """agr add nonexistent path fails."""
        result = agr("add", "./nonexistent")

        assert_cli(result).failed()

    def test_add_invalid_handle_fails(self, agr):
        """agr add with invalid handle fails."""
        result = agr("add", "not-a-valid-handle")

        assert_cli(result).failed()

    def test_add_outside_git_repo_fails(self, tmp_path):
        """agr add outside git repo fails."""
        from tests.cli.runner import run_cli

        result = run_cli(["agr", "add", "./skill"], cwd=tmp_path)

        assert_cli(result).failed().stdout_contains("Not in a git repository")

    def test_add_skill_already_installed_fails(self, agr, cli_skill):
        """agr add on already installed skill fails and suggests --overwrite."""
        agr("add", "./skills/test-skill")
        result = agr("add", "./skills/test-skill")

        assert_cli(result).failed().stdout_contains("--overwrite")

    def test_add_local_skill_duplicate_name_fails(self, agr, cli_project, cli_skill):
        """agr add rejects a second local skill with the same name."""
        dup_dir = cli_project / "other" / "test-skill"
        dup_dir.mkdir(parents=True)
        (dup_dir / "SKILL.md").write_text("# Duplicate")

        agr("add", "./skills/test-skill")
        result = agr("add", "./other/test-skill")

        assert_cli(result).failed().stdout_contains("only one local skill")

    def test_add_first_run_detects_tools(self, agr, cli_project, cli_skill):
        """agr add with no config detects tools from repo signals."""
        (cli_project / ".cursor").mkdir()

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "cursor" in config.tools

    def test_add_existing_config_keeps_tools(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add with existing config doesn't change tools."""
        cli_config('tools = ["claude"]\ndependencies = []\n')
        (cli_project / ".cursor").mkdir()

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]


class TestAgrAddRalph:
    """Tests for agr add with ralph type."""

    def test_add_local_ralph_succeeds(self, agr, cli_ralph):
        """agr add ./path adds local ralph."""
        result = agr("add", "./ralphs/test-ralph")
        assert_cli(result).succeeded().stdout_contains("Added:")

    def test_add_local_ralph_creates_installed_dir(self, agr, cli_project, cli_ralph):
        """agr add creates ralph in .agents/ralphs."""
        agr("add", "./ralphs/test-ralph")
        installed = cli_project / ".agents" / "ralphs" / "test-ralph"
        assert installed.exists()
        assert (installed / "RALPH.md").exists()

    def test_add_local_ralph_updates_config_with_ralph_type(
        self, agr, cli_project, cli_ralph
    ):
        """agr add updates agr.toml with type = ralph."""
        agr("add", "./ralphs/test-ralph")
        config = AgrConfig.load(cli_project / "agr.toml")
        ralph_deps = [d for d in config.dependencies if d.type == DEPENDENCY_TYPE_RALPH]
        assert len(ralph_deps) == 1
        assert ralph_deps[0].path == "./ralphs/test-ralph"

    def test_add_local_ralph_not_installed_to_tools(self, agr, cli_project, cli_ralph):
        """Ralphs should NOT be installed to .claude/skills/."""
        agr("add", "./ralphs/test-ralph")
        tool_dir = cli_project / ".claude" / "skills" / "test-ralph"
        assert not tool_dir.exists()

    def test_add_both_markers_fails(self, agr, cli_project):
        """agr add fails when directory has both SKILL.md and RALPH.md."""
        both_dir = cli_project / "both-type"
        both_dir.mkdir()
        (both_dir / "SKILL.md").write_text("# Skill")
        (both_dir / "RALPH.md").write_text("# Ralph")

        result = agr("add", "./both-type")

        assert_cli(result).failed().stdout_contains("SKILL.md and RALPH.md")
