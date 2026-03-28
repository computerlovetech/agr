"""CLI tests for agr config command group."""

from agr.config import AgrConfig
from tests.cli.assertions import assert_cli


# ---------- Existing deprecated sub-Typer tests ----------


class TestAgrConfigTools:
    """Tests for agr config tools commands (deprecated sub-Typer)."""

    def test_config_tools_default_lists_tools(self, agr, cli_config):
        """agr config tools defaults to list behavior."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("config", "tools")

        assert_cli(result).succeeded().stdout_contains("Configured tools:")
        assert_cli(result).stdout_contains("claude")
        assert_cli(result).stdout_contains("cursor")

    def test_config_tools_set_replaces_tool_list(self, agr, cli_project, cli_config):
        """agr config tools set replaces configured tools."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')

        result = agr("config", "tools", "set", "codex", "opencode")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["codex", "opencode"]

    def test_config_tools_unset_aliases_remove(self, agr, cli_project, cli_config):
        """agr config tools unset behaves like remove."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "tools", "unset", "codex")

        assert_cli(result).succeeded().stdout_contains("Removed:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]

    def test_config_tools_remove_updates_default_tool(
        self, agr, cli_project, cli_config
    ):
        """Removing the default tool updates default_tool safely."""
        cli_config(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []'
        )

        result = agr("config", "tools", "remove", "codex")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]
        assert config.default_tool == "claude"


class TestAgrConfigDefaultTool:
    """Tests for agr config default-tool commands (deprecated sub-Typer)."""

    def test_default_tool_set(self, agr, cli_project, cli_config):
        """agr config default-tool set stores default_tool."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "default-tool", "set", "codex")

        assert_cli(result).succeeded().stdout_contains("Default tool set:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool == "codex"

    def test_default_tool_set_requires_configured_tool(self, agr, cli_config):
        """agr config default-tool set rejects tools not in tools list."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "default-tool", "set", "codex")

        assert_cli(result).failed().stdout_contains("is not configured")

    def test_default_tool_unset(self, agr, cli_project, cli_config):
        """agr config default-tool unset clears default_tool."""
        cli_config(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []'
        )

        result = agr("config", "default-tool", "unset")

        assert_cli(result).succeeded().stdout_contains("Default tool unset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool is None


class TestAgrToolsAlias:
    """Tests for deprecated agr tools alias."""

    def test_tools_alias_prints_deprecation_warning(self, agr, cli_config):
        """agr tools warns about deprecation and still works."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("tools")

        assert_cli(result).succeeded().stdout_contains("deprecated")
        assert_cli(result).stdout_contains("agr config tools")


# ---------- New unified config command tests ----------


class TestAgrConfigShow:
    """Tests for agr config show."""

    def test_show_prints_all_config_values(self, agr, cli_config):
        """agr config show prints formatted config with all keys."""
        cli_config(
            'tools = ["claude", "codex"]\n'
            'default_tool = "claude"\n'
            "sync_instructions = true\n"
            'canonical_instructions = "CLAUDE.md"\n'
            "dependencies = []"
        )

        result = agr("config", "show")

        assert_cli(result).succeeded()
        assert_cli(result).stdout_contains("tools")
        assert_cli(result).stdout_contains("claude")
        assert_cli(result).stdout_contains("codex")
        assert_cli(result).stdout_contains("default_tool")
        assert_cli(result).stdout_contains("sync_instructions")
        assert_cli(result).stdout_contains("true")
        assert_cli(result).stdout_contains("canonical_instructions")
        assert_cli(result).stdout_contains("CLAUDE.md")

    def test_show_no_config_errors(self, agr):
        """agr config show errors when no agr.toml exists."""
        result = agr("config", "show")

        assert_cli(result).failed().stdout_contains("No agr.toml found")


class TestAgrConfigPath:
    """Tests for agr config path."""

    def test_path_prints_local_config_path(self, agr, cli_project, cli_config):
        """agr config path prints resolved agr.toml path."""
        cli_config("dependencies = []")

        result = agr("config", "path")

        assert_cli(result).succeeded()
        assert "agr.toml" in result.stdout

    def test_path_no_config_errors(self, agr):
        """agr config path errors when no agr.toml exists."""
        result = agr("config", "path")

        assert_cli(result).failed().stdout_contains("No agr.toml found")


class TestAgrConfigGet:
    """Tests for agr config get."""

    def test_get_tools(self, agr, cli_config):
        """agr config get tools prints tool list."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "get", "tools")

        assert_cli(result).succeeded()
        assert "claude" in result.stdout
        assert "codex" in result.stdout

    def test_get_scalar_value(self, agr, cli_config):
        """agr config get default_tool prints scalar."""
        cli_config(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []'
        )

        result = agr("config", "get", "default_tool")

        assert_cli(result).succeeded()
        assert "codex" in result.stdout

    def test_get_unset_scalar(self, agr, cli_config):
        """agr config get for unset scalar prints '(not set)'."""
        cli_config("dependencies = []")

        result = agr("config", "get", "default_tool")

        assert_cli(result).succeeded()
        assert "(not set)" in result.stdout

    def test_get_sources(self, agr, cli_config):
        """agr config get sources prints source list."""
        cli_config("dependencies = []")

        result = agr("config", "get", "sources")

        assert_cli(result).succeeded()
        assert "github" in result.stdout

    def test_get_unknown_key_errors(self, agr, cli_config):
        """agr config get with unknown key errors."""
        cli_config("dependencies = []")

        result = agr("config", "get", "bogus_key")

        assert_cli(result).failed().stdout_contains("Unknown config key")


class TestAgrConfigSet:
    """Tests for agr config set."""

    def test_set_tools_replaces_list(self, agr, cli_project, cli_config):
        """agr config set tools replaces tool list."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "set", "tools", "codex", "opencode")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["codex", "opencode"]

    def test_set_default_tool(self, agr, cli_project, cli_config):
        """agr config set default_tool stores scalar."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "set", "default_tool", "codex")

        assert_cli(result).succeeded().stdout_contains("Set:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool == "codex"

    def test_set_sync_instructions_true(self, agr, cli_project, cli_config):
        """agr config set sync_instructions true works."""
        cli_config("dependencies = []")

        result = agr("config", "set", "sync_instructions", "true")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.sync_instructions is True

    def test_set_sync_instructions_invalid(self, agr, cli_config):
        """agr config set sync_instructions rejects bad value."""
        cli_config("dependencies = []")

        result = agr("config", "set", "sync_instructions", "maybe")

        assert_cli(result).failed().stdout_contains("must be 'true' or 'false'")

    def test_set_canonical_instructions_valid(self, agr, cli_project, cli_config):
        """agr config set canonical_instructions accepts AGENTS.md/CLAUDE.md."""
        cli_config("dependencies = []")

        result = agr("config", "set", "canonical_instructions", "AGENTS.md")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.canonical_instructions == "AGENTS.md"

    def test_set_canonical_instructions_invalid(self, agr, cli_config):
        """agr config set canonical_instructions rejects bad value."""
        cli_config("dependencies = []")

        result = agr("config", "set", "canonical_instructions", "README.md")

        assert_cli(result).failed().stdout_contains("canonical_instructions must be")

    def test_set_default_tool_must_be_in_tools(self, agr, cli_config):
        """agr config set default_tool fails if not in tools list."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "set", "default_tool", "codex")

        assert_cli(result).failed().stdout_contains("not in configured tools")

    def test_set_tools_validates_names(self, agr, cli_config):
        """agr config set tools rejects unknown tool names."""
        cli_config("dependencies = []")

        result = agr("config", "set", "tools", "notarealtools")

        assert_cli(result).failed().stdout_contains("Unknown tool")

    def test_set_tools_requires_at_least_one(self, agr, cli_config):
        """agr config set tools with no values errors."""
        cli_config("dependencies = []")

        # Typer requires at least one argument for list[str], so this should error
        result = agr("config", "set", "tools")

        assert_cli(result).failed()

    def test_set_sources_errors(self, agr, cli_config):
        """agr config set sources is not supported."""
        cli_config("dependencies = []")

        result = agr("config", "set", "sources", "myname")

        assert_cli(result).failed().stdout_contains("Cannot set sources directly")


class TestAgrConfigUnset:
    """Tests for agr config unset."""

    def test_unset_scalar_clears_value(self, agr, cli_project, cli_config):
        """agr config unset default_tool clears value."""
        cli_config(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []'
        )

        result = agr("config", "unset", "default_tool")

        assert_cli(result).succeeded().stdout_contains("Unset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool is None

    def test_unset_already_none_message(self, agr, cli_config):
        """agr config unset on already-None scalar prints message."""
        cli_config("dependencies = []")

        result = agr("config", "unset", "default_tool")

        assert_cli(result).succeeded().stdout_contains("already unset")

    def test_unset_tools_resets_to_default(self, agr, cli_project, cli_config):
        """agr config unset tools resets to default ["claude"]."""
        cli_config('tools = ["codex", "opencode"]\ndependencies = []')

        result = agr("config", "unset", "tools")

        assert_cli(result).succeeded().stdout_contains("Reset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]

    def test_unset_tools_updates_default_tool_when_invalid(
        self, agr, cli_project, cli_config
    ):
        """agr config unset tools updates default_tool if it's no longer valid."""
        cli_config(
            'tools = ["claude", "cursor"]\n'
            'default_tool = "cursor"\n'
            "dependencies = []"
        )

        result = agr("config", "unset", "tools")

        assert_cli(result).succeeded().stdout_contains("Reset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]
        # default_tool should be updated to a valid tool, not left as "cursor"
        assert config.default_tool != "cursor"

    def test_unset_sources_errors(self, agr, cli_config):
        """agr config unset sources is not supported."""
        cli_config("dependencies = []")

        result = agr("config", "unset", "sources")

        assert_cli(result).failed().stdout_contains("Cannot unset sources")


class TestAgrConfigAdd:
    """Tests for agr config add."""

    def test_add_tools_appends(self, agr, cli_project, cli_config):
        """agr config add tools appends new tools."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "add", "tools", "codex")

        assert_cli(result).succeeded().stdout_contains("Added:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "codex" in config.tools

    def test_add_tools_multiple_values(self, agr, cli_project, cli_config):
        """agr config add tools accepts multiple values."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "add", "tools", "codex", "opencode")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude", "codex", "opencode"]

    def test_add_tools_skips_duplicates(self, agr, cli_config):
        """agr config add tools skips already-configured tools."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "add", "tools", "claude")

        assert_cli(result).succeeded().stdout_contains("Already configured:")

    def test_add_sources_with_flags(self, agr, cli_project, cli_config):
        """agr config add sources with --type and --url works."""
        cli_config("dependencies = []")

        result = agr(
            "config",
            "add",
            "sources",
            "gitlab",
            "--type",
            "git",
            "--url",
            "https://gitlab.com/{owner}/{repo}.git",
        )

        assert_cli(result).succeeded().stdout_contains("Added source:")
        config = AgrConfig.load(cli_project / "agr.toml")
        source_names = [s.name for s in config.sources]
        assert "gitlab" in source_names

    def test_add_sources_missing_url_errors(self, agr, cli_config):
        """agr config add sources without --url errors."""
        cli_config("dependencies = []")

        result = agr("config", "add", "sources", "gitlab")

        assert_cli(result).failed().stdout_contains("--url is required")

    def test_add_sources_duplicate_name_errors(self, agr, cli_config):
        """agr config add sources with duplicate name errors."""
        cli_config("dependencies = []")

        result = agr(
            "config",
            "add",
            "sources",
            "github",
            "--url",
            "https://example.com/{owner}/{repo}.git",
        )

        assert_cli(result).failed().stdout_contains("already exists")

    def test_add_scalar_errors(self, agr, cli_config):
        """agr config add on scalar key errors."""
        cli_config("dependencies = []")

        result = agr("config", "add", "default_tool", "claude")

        assert_cli(result).failed().stdout_contains("scalar")


class TestAgrConfigRemove:
    """Tests for agr config remove."""

    def test_remove_tools(self, agr, cli_project, cli_config):
        """agr config remove tools removes a tool."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "remove", "tools", "codex")

        assert_cli(result).succeeded().stdout_contains("Removed:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.tools == ["claude"]

    def test_remove_tools_cannot_remove_all(self, agr, cli_config):
        """agr config remove tools cannot remove all tools."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "remove", "tools", "claude")

        assert_cli(result).failed().stdout_contains("Cannot remove all tools")

    def test_remove_tools_updates_default_tool(self, agr, cli_project, cli_config):
        """Removing the default tool updates default_tool."""
        cli_config(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []'
        )

        result = agr("config", "remove", "tools", "codex")

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool == "claude"

    def test_remove_sources(self, agr, cli_project, cli_config):
        """agr config remove sources removes a non-default source."""
        cli_config(
            "dependencies = []\n\n"
            "[[source]]\n"
            'name = "github"\n'
            'type = "git"\n'
            'url = "https://github.com/{owner}/{repo}.git"\n\n'
            "[[source]]\n"
            'name = "gitlab"\n'
            'type = "git"\n'
            'url = "https://gitlab.com/{owner}/{repo}.git"\n'
        )

        result = agr("config", "remove", "sources", "gitlab")

        assert_cli(result).succeeded().stdout_contains("Removed source:")
        config = AgrConfig.load(cli_project / "agr.toml")
        source_names = [s.name for s in config.sources]
        assert "gitlab" not in source_names

    def test_remove_default_source_errors(self, agr, cli_config):
        """agr config remove sources cannot remove default source."""
        cli_config("dependencies = []")

        result = agr("config", "remove", "sources", "github")

        assert_cli(result).failed().stdout_contains("Cannot remove default source")

    def test_remove_scalar_errors(self, agr, cli_config):
        """agr config remove on scalar key errors."""
        cli_config("dependencies = []")

        result = agr("config", "remove", "default_tool", "claude")

        assert_cli(result).failed().stdout_contains("scalar")


class TestAgrConfigDeprecation:
    """Tests for deprecation warnings on old config subcommands."""

    def test_deprecated_config_tools_list_warns(self, agr, cli_config):
        """agr config tools list prints deprecation warning."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "tools", "list")

        assert_cli(result).succeeded().stdout_contains("deprecated")
        assert_cli(result).stdout_contains("agr config get tools")

    def test_deprecated_config_tools_add_warns(self, agr, cli_config):
        """agr config tools add prints deprecation warning."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "tools", "add", "codex")

        assert_cli(result).succeeded().stdout_contains("deprecated")
        assert_cli(result).stdout_contains("agr config add tools")

    def test_deprecated_config_default_tool_set_warns(self, agr, cli_config):
        """agr config default-tool set prints deprecation warning."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "default-tool", "set", "codex")

        assert_cli(result).succeeded().stdout_contains("deprecated")
        assert_cli(result).stdout_contains("agr config set default_tool")

    def test_deprecated_config_default_tool_unset_warns(self, agr, cli_config):
        """agr config default-tool unset prints deprecation warning."""
        cli_config(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []'
        )

        result = agr("config", "default-tool", "unset")

        assert_cli(result).succeeded().stdout_contains("deprecated")
        assert_cli(result).stdout_contains("agr config unset default_tool")


class TestAgrConfigEdit:
    """Tests for agr config edit."""

    def test_edit_no_editor_set_errors(self, agr, cli_config):
        """agr config edit errors when no $EDITOR/$VISUAL is set."""
        cli_config("dependencies = []")

        result = agr("config", "edit", env={"EDITOR": "", "VISUAL": ""})

        assert_cli(result).failed().stdout_contains("EDITOR")

    def test_edit_no_config_errors(self, agr):
        """agr config edit errors when no agr.toml exists."""
        result = agr("config", "edit", env={"EDITOR": "true"})

        assert_cli(result).failed().stdout_contains("No agr.toml found")

    def test_edit_launches_editor(self, agr, cli_config):
        """agr config edit launches editor and exits successfully."""
        cli_config("dependencies = []")

        result = agr("config", "edit", env={"EDITOR": "true"})

        assert_cli(result).succeeded()


class TestAgrConfigSetAdditional:
    """Additional tests for agr config set."""

    def test_set_default_source(self, agr, cli_project, cli_config):
        """agr config set default_source stores scalar."""
        cli_config(
            "dependencies = []\n\n"
            "[[source]]\n"
            'name = "github"\n'
            'type = "git"\n'
            'url = "https://github.com/{owner}/{repo}.git"\n\n'
            "[[source]]\n"
            'name = "gitlab"\n'
            'type = "git"\n'
            'url = "https://gitlab.com/{owner}/{repo}.git"\n'
        )

        result = agr("config", "set", "default_source", "gitlab")

        assert_cli(result).succeeded().stdout_contains("Set:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_source == "gitlab"

    def test_set_default_source_not_in_sources_errors(self, agr, cli_config):
        """agr config set default_source errors when source not in list."""
        cli_config("dependencies = []")

        result = agr("config", "set", "default_source", "nonexistent")

        assert_cli(result).failed().stdout_contains("not found in sources")


class TestAgrConfigUnsetAdditional:
    """Additional tests for agr config unset."""

    def test_unset_sync_instructions(self, agr, cli_project, cli_config):
        """agr config unset sync_instructions clears value."""
        cli_config("sync_instructions = true\ndependencies = []")

        result = agr("config", "unset", "sync_instructions")

        assert_cli(result).succeeded().stdout_contains("Unset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.sync_instructions is None

    def test_unset_canonical_instructions(self, agr, cli_project, cli_config):
        """agr config unset canonical_instructions clears value."""
        cli_config('canonical_instructions = "CLAUDE.md"\ndependencies = []')

        result = agr("config", "unset", "canonical_instructions")

        assert_cli(result).succeeded().stdout_contains("Unset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.canonical_instructions is None

    def test_unset_default_source_resets(self, agr, cli_project, cli_config):
        """agr config unset default_source resets to default."""
        cli_config(
            'default_source = "gitlab"\n'
            "dependencies = []\n\n"
            "[[source]]\n"
            'name = "github"\n'
            'type = "git"\n'
            'url = "https://github.com/{owner}/{repo}.git"\n\n'
            "[[source]]\n"
            'name = "gitlab"\n'
            'type = "git"\n'
            'url = "https://gitlab.com/{owner}/{repo}.git"\n'
        )

        result = agr("config", "unset", "default_source")

        assert_cli(result).succeeded().stdout_contains("Reset:")
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_source == "github"


class TestAgrConfigAddAdditional:
    """Additional tests for agr config add."""

    def test_add_tools_rejects_type_flag(self, agr, cli_config):
        """agr config add tools with --type flag errors."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("config", "add", "tools", "codex", "--type", "git")

        assert_cli(result).failed().stdout_contains("only valid for 'sources'")

    def test_add_sources_unsupported_type_errors(self, agr, cli_config):
        """agr config add sources with unsupported --type errors."""
        cli_config("dependencies = []")

        result = agr(
            "config",
            "add",
            "sources",
            "custom",
            "--type",
            "notgit",
            "--url",
            "https://example.com",
        )

        assert_cli(result).failed().stdout_contains("Unsupported source type")


class TestAgrConfigRemoveAdditional:
    """Additional tests for agr config remove."""

    def test_remove_tools_not_configured_prints_message(self, agr, cli_config):
        """agr config remove tools prints message for unconfigured tool."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("config", "remove", "tools", "opencode")

        assert_cli(result).succeeded().stdout_contains("Not configured:")

    def test_remove_sources_not_found_errors(self, agr, cli_config):
        """agr config remove sources errors when source not found."""
        cli_config("dependencies = []")

        result = agr("config", "remove", "sources", "nonexistent")

        assert_cli(result).failed().stdout_contains("not found")

    def test_remove_sources_rejects_extra_values(self, agr, cli_config):
        """agr config remove sources errors with multiple names."""
        cli_config("dependencies = []")

        result = agr("config", "remove", "sources", "one", "two")

        assert_cli(result).failed().stdout_contains("Only one source name")
