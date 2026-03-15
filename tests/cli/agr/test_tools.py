"""CLI tests for agr tools command."""

from tests.cli.assertions import assert_cli


class TestAgrToolsList:
    """Tests for agr tools list command."""

    def test_tools_list_default(self, agr, cli_config):
        """agr tools shows configured tools."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("tools")

        assert_cli(result).succeeded().stdout_contains("Configured tools:")
        assert_cli(result).stdout_contains("claude")
        assert_cli(result).stdout_contains("cursor")

    def test_tools_list_explicit(self, agr, cli_config):
        """agr tools list shows configured tools."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("tools", "list")

        assert_cli(result).succeeded().stdout_contains("Configured tools:")
        assert_cli(result).stdout_contains("claude")

    def test_tools_list_no_config(self, agr):
        """agr tools without config shows defaults."""
        result = agr("tools")

        assert_cli(result).succeeded().stdout_contains("No agr.toml")
        assert_cli(result).stdout_contains("claude")

    def test_tools_list_shows_available(self, agr, cli_config):
        """agr tools shows available tools not configured."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("tools")

        assert_cli(result).succeeded().stdout_contains("Available tools:")
        # cursor, codex, opencode, copilot, and antigravity should be available
        assert_cli(result).stdout_contains("cursor")
        assert_cli(result).stdout_contains("codex")
        assert_cli(result).stdout_contains("opencode")
        assert_cli(result).stdout_contains("copilot")
        assert_cli(result).stdout_contains("antigravity")


class TestAgrToolsAdd:
    """Tests for agr tools add command."""

    def test_tools_add_single(self, agr, cli_config, cli_project):
        """agr tools add adds a single tool."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("tools", "add", "cursor")

        assert_cli(result).succeeded().stdout_contains("Added:")
        assert_cli(result).stdout_contains("cursor")

        # Verify config was updated
        config_content = (cli_project / "agr.toml").read_text()
        assert "cursor" in config_content

    def test_tools_add_multiple(self, agr, cli_config, cli_project):
        """agr tools add adds multiple tools."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr(
            "tools", "add", "cursor", "codex", "opencode", "copilot", "antigravity"
        )

        assert_cli(result).succeeded()
        assert "cursor" in result.stdout
        assert "codex" in result.stdout
        assert "opencode" in result.stdout
        assert "copilot" in result.stdout
        assert "antigravity" in result.stdout

    def test_tools_add_already_configured(self, agr, cli_config):
        """agr tools add skips already configured tools."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("tools", "add", "cursor")

        assert_cli(result).succeeded().stdout_contains("Already configured:")

    def test_tools_add_invalid(self, agr, cli_config):
        """agr tools add rejects unknown tools."""
        cli_config("dependencies = []")

        result = agr("tools", "add", "invalid-tool")

        assert_cli(result).failed().stdout_contains("Unknown tool")

    def test_tools_add_no_config(self, agr):
        """agr tools add fails without agr.toml."""
        result = agr("tools", "add", "cursor")

        assert_cli(result).failed().stdout_contains("No agr.toml")

    def test_tools_add_triggers_sync(self, agr, cli_project, cli_skill):
        """agr tools add syncs existing dependencies to new tools."""
        # Add a local skill first
        agr("add", "./skills/test-skill")

        # Now add cursor tool
        result = agr("tools", "add", "cursor")

        assert_cli(result).succeeded()
        # Should report syncing
        assert "Syncing" in result.stdout or "Installed" in result.stdout

        # Verify skill was installed to cursor (nested path: local/test-skill)
        cursor_skill = cli_project / ".cursor" / "skills" / "local" / "test-skill"
        assert cursor_skill.exists()

    def test_tools_add_sync_partial_failure_exits_nonzero(
        self, agr, cli_config, cli_project
    ):
        """agr tools add exits 1 when sync partially fails."""
        # Setup config with invalid remote dependency
        cli_config("""
tools = ["claude"]
dependencies = [
    {handle = "nonexistent/invalid-repo-12345", type = "skill"},
]
""")

        result = agr("tools", "add", "cursor")

        # Should fail because sync failed
        assert_cli(result).failed()
        assert "failed" in result.stdout.lower() or "error" in result.stdout.lower()


class TestAgrToolsRemove:
    """Tests for agr tools remove command."""

    def test_tools_remove_single(self, agr, cli_config, cli_project):
        """agr tools remove removes a tool."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("tools", "remove", "cursor")

        assert_cli(result).succeeded().stdout_contains("Removed:")

        # Verify config was updated
        config_content = (cli_project / "agr.toml").read_text()
        assert "cursor" not in config_content

    def test_tools_remove_last_tool_fails(self, agr, cli_config):
        """agr tools remove fails if removing last tool."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("tools", "remove", "claude")

        assert_cli(result).failed().stdout_contains("Cannot remove all tools")

    def test_tools_remove_not_configured(self, agr, cli_config):
        """agr tools remove reports not configured tools."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("tools", "remove", "cursor")

        assert_cli(result).succeeded().stdout_contains("Not configured:")

    def test_tools_remove_invalid(self, agr, cli_config):
        """agr tools remove rejects unknown tools."""
        cli_config("dependencies = []")

        result = agr("tools", "remove", "invalid-tool")

        assert_cli(result).failed().stdout_contains("Unknown tool")

    def test_tools_remove_deletes_skills(self, agr, cli_project, cli_skill):
        """agr tools remove deletes skills from removed tool."""
        # Setup: add skill and cursor tool
        agr("add", "./skills/test-skill")
        agr("tools", "add", "cursor")

        # Verify cursor skill exists
        cursor_skill_dir = cli_project / ".cursor" / "skills"
        assert cursor_skill_dir.exists()

        # Remove cursor tool
        result = agr("tools", "remove", "cursor")

        assert_cli(result).succeeded().stdout_contains("Deleted")

        # Verify cursor skills directory was removed
        assert not cursor_skill_dir.exists()

    def test_tools_remove_no_config(self, agr):
        """agr tools remove fails without agr.toml."""
        result = agr("tools", "remove", "claude")

        assert_cli(result).failed().stdout_contains("No agr.toml")

    def test_tools_remove_keeps_config_on_deletion_failure(
        self, cli_project, cli_skill, monkeypatch, capsys
    ):
        """agr tools remove keeps tool in config if skill deletion fails."""
        import shutil

        from agr.commands import _tool_helpers as helpers_module
        from agr.commands.add import run_add
        from agr.commands.tools import run_tools_add, run_tools_remove
        from agr.config import AgrConfig

        # Initialize config and change to project directory
        monkeypatch.chdir(cli_project)
        config = AgrConfig(tools=["claude"])
        config.save(cli_project / "agr.toml")

        # Setup: add skill and cursor tool
        run_add(["./skills/test-skill"])
        run_tools_add(["cursor"])

        # Make rmtree fail for cursor directory
        original_rmtree = shutil.rmtree

        def failing_rmtree(path, *args, **kwargs):
            if ".cursor" in str(path):
                raise OSError("Permission denied")
            return original_rmtree(path, *args, **kwargs)

        # Patch in the module where delete_tool_skills is defined
        monkeypatch.setattr(helpers_module.shutil, "rmtree", failing_rmtree)

        # Try to remove cursor
        run_tools_remove(["cursor"])

        # Capture output
        captured = capsys.readouterr()

        # Should show error
        assert "Error" in captured.out or "error" in captured.out.lower()

        # Cursor should still be in config
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "cursor" in config.tools
