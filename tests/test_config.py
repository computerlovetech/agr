"""Tests for agr.config module."""

import pytest

from agr.config import (
    AgrConfig,
    Dependency,
    find_config,
    find_repo_root,
)
from agr.exceptions import AgrError, ConfigError
from agr.tool import ToolConfig


class TestDependency:
    """Tests for Dependency dataclass."""

    def test_remote_dependency(self):
        """Create a remote dependency."""
        dep = Dependency(type="skill", handle="vercel-labs/agent-browser/agent-browser")
        assert dep.is_remote
        assert not dep.is_local
        assert dep.identifier == "vercel-labs/agent-browser/agent-browser"

    def test_local_dependency(self):
        """Create a local dependency."""
        dep = Dependency(type="skill", path="./my-skill")
        assert dep.is_local
        assert not dep.is_remote
        assert dep.identifier == "./my-skill"

    def test_both_handle_and_path_raises(self):
        """Cannot have both handle and path."""
        with pytest.raises(ConfigError, match="cannot have both"):
            Dependency(type="skill", handle="user/skill", path="./local")

    def test_neither_handle_nor_path_raises(self):
        """Must have either handle or path."""
        with pytest.raises(ConfigError, match="must have either"):
            Dependency(type="skill")

    def test_local_with_source_raises(self):
        """Local dependency cannot specify a source."""
        with pytest.raises(
            ConfigError, match="Local dependency cannot specify a source"
        ):
            Dependency(type="skill", path="./my-skill", source="github")

    def test_installed_name_remote_two_part(self):
        """Two-part handle returns the skill name."""
        dep = Dependency(type="skill", handle="owner/skill-name")
        assert dep.installed_name == "skill-name"

    def test_installed_name_remote_three_part(self):
        """Three-part handle returns the last segment."""
        dep = Dependency(type="skill", handle="owner/repo/skill-name")
        assert dep.installed_name == "skill-name"

    def test_installed_name_local(self):
        """Local dependency returns the directory name."""
        dep = Dependency(type="skill", path="./my-skill")
        assert dep.installed_name == "my-skill"

    def test_installed_name_local_nested(self):
        """Nested local path returns the leaf directory name."""
        dep = Dependency(type="skill", path="./some/nested/my-skill")
        assert dep.installed_name == "my-skill"

    def test_installed_name_matches_to_parsed_handle(self):
        """installed_name matches to_parsed_handle().name for valid deps."""
        cases = [
            Dependency(type="skill", handle="owner/skill"),
            Dependency(type="skill", handle="owner/repo/skill"),
            Dependency(type="skill", path="./my-skill"),
            Dependency(type="ralph", handle="owner/my-ralph"),
        ]
        for dep in cases:
            assert dep.installed_name == dep.to_parsed_handle().name

    def test_installed_name_trailing_slash(self):
        """Trailing slash in remote handle does not break installed_name."""
        dep = Dependency(type="skill", handle="owner/repo/skill/")
        assert dep.installed_name == "skill"

    def test_to_parsed_handle_remote_two_part(self):
        """Remote two-part handle converts to ParsedHandle."""
        dep = Dependency(type="skill", handle="owner/skill-name")
        parsed = dep.to_parsed_handle()
        assert not parsed.is_local
        assert parsed.username == "owner"
        assert parsed.name == "skill-name"
        assert parsed.repo is None

    def test_to_parsed_handle_remote_three_part(self):
        """Remote three-part handle converts to ParsedHandle."""
        dep = Dependency(type="skill", handle="owner/repo/skill-name")
        parsed = dep.to_parsed_handle()
        assert not parsed.is_local
        assert parsed.username == "owner"
        assert parsed.repo == "repo"
        assert parsed.name == "skill-name"

    def test_to_parsed_handle_local(self):
        """Local dependency converts to ParsedHandle with is_local=True."""
        dep = Dependency(type="skill", path="./my-skill")
        parsed = dep.to_parsed_handle()
        assert parsed.is_local
        assert parsed.name == "my-skill"
        assert parsed.local_path is not None

    def test_resolve_source_name_remote_explicit(self):
        """Remote dependency with explicit source returns that source."""
        dep = Dependency(type="skill", handle="owner/skill", source="custom")
        assert dep.resolve_source_name("github") == "custom"

    def test_resolve_source_name_remote_default(self):
        """Remote dependency without source falls back to default."""
        dep = Dependency(type="skill", handle="owner/skill")
        assert dep.resolve_source_name("github") == "github"

    def test_resolve_source_name_remote_no_default(self):
        """Remote dependency without source or default returns None."""
        dep = Dependency(type="skill", handle="owner/skill")
        assert dep.resolve_source_name() is None

    def test_resolve_source_name_local(self):
        """Local dependency always returns None for source."""
        dep = Dependency(type="skill", path="./my-skill")
        assert dep.resolve_source_name("github") is None

    def test_resolve_remote(self):
        """resolve() returns parsed handle and source name together."""
        dep = Dependency(type="skill", handle="owner/repo/skill", source="custom")
        handle, source_name = dep.resolve("github")
        assert handle.username == "owner"
        assert handle.repo == "repo"
        assert handle.name == "skill"
        assert source_name == "custom"

    def test_resolve_remote_default_source(self):
        """resolve() falls back to default source for remote deps."""
        dep = Dependency(type="skill", handle="owner/skill")
        handle, source_name = dep.resolve("github")
        assert handle.username == "owner"
        assert handle.name == "skill"
        assert source_name == "github"

    def test_resolve_local(self):
        """resolve() returns local handle with None source."""
        dep = Dependency(type="skill", path="./my-skill")
        handle, source_name = dep.resolve("github")
        assert handle.is_local
        assert handle.name == "my-skill"
        assert source_name is None

    def test_to_parsed_handle_dot_path_raises(self):
        """Local dependency with path='.' must raise due to empty resource name."""
        dep = Dependency(type="skill", path=".")
        with pytest.raises(AgrError, match="empty resource name"):
            dep.to_parsed_handle()

    def test_to_parsed_handle_dotdot_path_raises(self):
        """Local dependency with path='..' must raise due to invalid resource name."""
        dep = Dependency(type="skill", path="..")
        with pytest.raises(AgrError, match="empty resource name"):
            dep.to_parsed_handle()

    def test_to_parsed_handle_local_rejects_separator_in_name(self):
        """Local path with '--' in name must be rejected by to_parsed_handle.

        parse_handle() validates this, but Dependency.to_parsed_handle() must
        also reject names containing the reserved '--' separator to prevent
        ambiguous installed directory names.
        """
        dep = Dependency(type="skill", path="./my--skill")
        with pytest.raises(AgrError, match="reserved sequence"):
            dep.to_parsed_handle()

    def test_to_toml_dict_remote(self):
        """Remote dependency serializes handle, type, and optional source."""
        dep = Dependency(type="skill", handle="owner/repo/skill")
        result = dep.to_toml_dict()
        assert result == {"handle": "owner/repo/skill", "type": "skill"}

    def test_to_toml_dict_remote_with_source(self):
        """Remote dependency with explicit source includes it."""
        dep = Dependency(type="skill", handle="owner/skill", source="custom")
        result = dep.to_toml_dict()
        assert result == {
            "handle": "owner/skill",
            "source": "custom",
            "type": "skill",
        }

    def test_to_toml_dict_local(self):
        """Local dependency serializes path and type."""
        dep = Dependency(type="skill", path="./my-skill")
        result = dep.to_toml_dict()
        assert result == {"path": "./my-skill", "type": "skill"}

    def test_to_toml_dict_ralph(self):
        """Ralph dependency preserves the type."""
        dep = Dependency(type="ralph", handle="owner/repo/my-ralph")
        result = dep.to_toml_dict()
        assert result == {"handle": "owner/repo/my-ralph", "type": "ralph"}

    def test_from_toml_dict_remote(self):
        """Deserialize a remote dependency from TOML dict."""
        dep = Dependency.from_toml_dict({"handle": "owner/repo/skill", "type": "skill"})
        assert dep.handle == "owner/repo/skill"
        assert dep.type == "skill"
        assert dep.path is None
        assert dep.source is None

    def test_from_toml_dict_local(self):
        """Deserialize a local dependency from TOML dict."""
        dep = Dependency.from_toml_dict({"path": "./my-skill", "type": "skill"})
        assert dep.path == "./my-skill"
        assert dep.type == "skill"
        assert dep.handle is None

    def test_from_toml_dict_with_source(self):
        """Deserialize a remote dependency with explicit source."""
        dep = Dependency.from_toml_dict(
            {"handle": "owner/skill", "type": "skill", "source": "custom"}
        )
        assert dep.source == "custom"

    def test_from_toml_dict_defaults_to_skill(self):
        """Missing type defaults to skill."""
        dep = Dependency.from_toml_dict({"handle": "owner/skill"})
        assert dep.type == "skill"

    def test_from_toml_dict_unknown_type_raises(self):
        """Unknown dependency type raises ConfigError."""
        with pytest.raises(ConfigError, match="Unknown dependency type"):
            Dependency.from_toml_dict({"handle": "owner/skill", "type": "unknown"})

    def test_to_toml_dict_roundtrip(self):
        """Serialization and deserialization produce equivalent objects."""
        original = Dependency(type="skill", handle="owner/repo/skill", source="custom")
        restored = Dependency.from_toml_dict(original.to_toml_dict())
        assert restored.handle == original.handle
        assert restored.path == original.path
        assert restored.source == original.source
        assert restored.type == original.type


class TestRalphDependency:
    """Tests for ralph dependency type."""

    def test_ralph_remote_dependency(self):
        """Create a remote ralph dependency."""
        dep = Dependency(type="ralph", handle="user/repo/my-ralph")
        assert dep.is_remote
        assert dep.type == "ralph"
        assert dep.identifier == "user/repo/my-ralph"

    def test_ralph_local_dependency(self):
        """Create a local ralph dependency."""
        dep = Dependency(type="ralph", path="./my-ralph")
        assert dep.is_local
        assert dep.type == "ralph"

    def test_unknown_type_in_toml(self, tmp_path):
        """Unknown dependency type raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'dependencies = [{handle = "user/repo/foo", type = "unknown"}]\n'
        )
        with pytest.raises(ConfigError, match="Unknown dependency type"):
            AgrConfig.load(config_path)

    def test_ralph_type_in_toml(self, tmp_path):
        """Ralph type parses successfully."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'dependencies = [{handle = "user/repo/my-ralph", type = "ralph"}]\n'
        )
        config = AgrConfig.load(config_path)
        assert len(config.dependencies) == 1
        assert config.dependencies[0].type == "ralph"
        assert config.dependencies[0].handle == "user/repo/my-ralph"

    def test_mixed_skill_and_ralph(self, tmp_path):
        """Config with both skill and ralph deps."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            "dependencies = [\n"
            '    {handle = "user/repo/my-skill", type = "skill"},\n'
            '    {handle = "user/repo/my-ralph", type = "ralph"},\n'
            "]\n"
        )
        config = AgrConfig.load(config_path)
        assert len(config.dependencies) == 2
        assert config.dependencies[0].type == "skill"
        assert config.dependencies[1].type == "ralph"


class TestAgrConfig:
    """Tests for AgrConfig class."""

    def test_load_nonexistent(self, tmp_path):
        """Loading nonexistent file returns empty config."""
        config = AgrConfig.load(tmp_path / "agr.toml")
        assert config.dependencies == []
        assert config.default_source == "github"
        assert config.sources[0].name == "github"

    def test_load_empty(self, tmp_path):
        """Loading empty file returns empty config."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []")
        config = AgrConfig.load(config_path)
        assert config.dependencies == []
        assert config.default_source == "github"
        assert config.sources[0].name == "github"
        assert config.default_tool is None
        assert config.default_owner == "computerlovetech"
        assert config.sync_instructions is None
        assert config.canonical_instructions is None

    def test_load_with_dependencies(self, tmp_path):
        """Load config with dependencies."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("""
dependencies = [
    { handle = "vercel-labs/agent-browser/agent-browser", type = "skill" },
    { path = "./my-skill", type = "skill" },
]
""")
        config = AgrConfig.load(config_path)
        assert len(config.dependencies) == 2
        assert (
            config.dependencies[0].handle == "vercel-labs/agent-browser/agent-browser"
        )
        assert config.dependencies[1].path == "./my-skill"

    def test_load_default_tool(self, tmp_path):
        """Load config with default_tool."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'tools = ["claude", "codex"]\ndefault_tool = "codex"\ndependencies = []\n'
        )
        config = AgrConfig.load(config_path)
        assert config.default_tool == "codex"

    def test_load_invalid_default_tool_raises(self, tmp_path):
        """Invalid default_tool raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_tool = "unknown"\ndependencies = []\n')
        with pytest.raises(ConfigError, match="Unknown default_tool"):
            AgrConfig.load(config_path)

    def test_load_canonical_instructions(self, tmp_path):
        """Load config with canonical_instructions."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'canonical_instructions = "AGENTS.md"\ndependencies = []\n'
        )
        config = AgrConfig.load(config_path)
        assert config.canonical_instructions == "AGENTS.md"

    def test_load_canonical_instructions_gemini(self, tmp_path):
        """Load config with GEMINI.md as canonical_instructions."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'canonical_instructions = "GEMINI.md"\ndependencies = []\n'
        )
        config = AgrConfig.load(config_path)
        assert config.canonical_instructions == "GEMINI.md"

    def test_load_invalid_canonical_instructions_raises(self, tmp_path):
        """Invalid canonical_instructions raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'canonical_instructions = "README.md"\ndependencies = []\n'
        )
        with pytest.raises(ConfigError, match="canonical_instructions"):
            AgrConfig.load(config_path)

    def test_load_local_dep_with_source_raises(self, tmp_path):
        """Local dependency with source in TOML raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("""
dependencies = [
    { path = "./my-skill", type = "skill", source = "github" },
]
""")
        with pytest.raises(
            ConfigError, match="Local dependency cannot specify a source"
        ):
            AgrConfig.load(config_path)

    def test_load_invalid_toml_raises(self, tmp_path):
        """Loading invalid TOML raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("invalid toml [")
        with pytest.raises(ConfigError):
            AgrConfig.load(config_path)

    def test_dependency_unknown_source_raises(self, tmp_path):
        """Unknown dependency source raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            """
default_source = "github"

dependencies = [
    { handle = "user/skill", type = "skill", source = "gitlab" },
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
"""
        )
        with pytest.raises(ConfigError, match="Unknown source"):
            AgrConfig.load(config_path)

    def test_save(self, tmp_path):
        """Save config to file."""
        config = AgrConfig()
        config.add_dependency(
            Dependency(type="skill", handle="vercel-labs/agent-browser/agent-browser")
        )
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        # Reload and verify
        loaded = AgrConfig.load(config_path)
        assert len(loaded.dependencies) == 1
        assert (
            loaded.dependencies[0].handle == "vercel-labs/agent-browser/agent-browser"
        )
        assert loaded.default_source == "github"
        assert loaded.sources[0].name == "github"

    def test_add_dependency(self):
        """Add a dependency."""
        config = AgrConfig()
        config.add_dependency(Dependency(type="skill", handle="user/skill"))
        assert len(config.dependencies) == 1

    def test_add_dependency_replaces_existing(self):
        """Adding duplicate identifier replaces existing."""
        config = AgrConfig()
        config.add_dependency(Dependency(type="skill", handle="user/skill"))
        config.add_dependency(Dependency(type="skill", handle="user/skill"))
        assert len(config.dependencies) == 1

    def test_remove_dependency(self):
        """Remove a dependency."""
        config = AgrConfig()
        config.add_dependency(Dependency(type="skill", handle="user/skill"))
        removed = config.remove_dependency("user/skill")
        assert removed
        assert len(config.dependencies) == 0

    def test_remove_nonexistent(self):
        """Removing nonexistent returns False."""
        config = AgrConfig()
        removed = config.remove_dependency("user/skill")
        assert not removed

    def test_get_by_identifier(self):
        """Find dependency by identifier."""
        config = AgrConfig()
        config.add_dependency(Dependency(type="skill", handle="user/skill"))
        dep = config.get_by_identifier("user/skill")
        assert dep is not None
        assert dep.handle == "user/skill"

    def test_get_by_identifier_not_found(self):
        """Returns None for nonexistent identifier."""
        config = AgrConfig()
        dep = config.get_by_identifier("user/skill")
        assert dep is None


class TestFindConfig:
    """Tests for find_config function."""

    def test_find_in_current_dir(self, tmp_path, monkeypatch):
        """Find config in current directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []")

        found = find_config()
        assert found == config_path

    def test_find_in_parent_dir(self, tmp_path, monkeypatch):
        """Find config in parent directory."""
        (tmp_path / ".git").mkdir()
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        found = find_config()
        assert found == config_path

    def test_not_found_at_git_root(self, tmp_path, monkeypatch):
        """Returns None when not found at git root."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        found = find_config()
        assert found is None


class TestFindRepoRoot:
    """Tests for find_repo_root function."""

    def test_find_repo_root(self, tmp_path, monkeypatch):
        """Find git repository root."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        root = find_repo_root()
        assert root == tmp_path

    def test_find_from_subdir(self, tmp_path, monkeypatch):
        """Find repo root from subdirectory."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        root = find_repo_root()
        assert root == tmp_path

    def test_not_in_repo(self, tmp_path, monkeypatch):
        """Returns None when not in a git repo."""
        monkeypatch.chdir(tmp_path)

        root = find_repo_root()
        assert root is None


class TestGetTools:
    """Tests for AgrConfig.get_tools method."""

    def test_returns_tool_configs(self):
        """get_tools returns ToolConfig instances."""
        config = AgrConfig()
        tools = config.get_tools()
        assert len(tools) == 1
        assert all(isinstance(t, ToolConfig) for t in tools)
        assert tools[0].name == "claude"

    def test_multiple_tools(self):
        """get_tools works with multiple configured tools."""
        config = AgrConfig()
        config.tools = ["claude", "cursor"]
        tools = config.get_tools()
        assert len(tools) == 2
        assert tools[0].name == "claude"
        assert tools[1].name == "cursor"

    def test_invalid_tool_raises(self):
        """get_tools raises AgrError for invalid tool name."""
        config = AgrConfig()
        config.tools = ["invalid_tool"]
        with pytest.raises(AgrError, match="Unknown tool"):
            config.get_tools()

    def test_load_validates_tool_names(self, tmp_path):
        """Invalid tool name in config raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('tools = ["invalid_tool"]\ndependencies = []')
        with pytest.raises(ConfigError, match="Unknown tool"):
            AgrConfig.load(config_path)

    def test_save_and_load_tools_roundtrip(self, tmp_path):
        """Tools array persists through save/load."""
        config = AgrConfig()
        config.tools = ["claude", "cursor"]
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        loaded = AgrConfig.load(config_path)
        assert loaded.tools == ["claude", "cursor"]

    def test_all_options_written_to_file(self, tmp_path):
        """All config options are written to file with comments."""
        config = AgrConfig()
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert "tools" in content
        assert "default_source" in content
        assert "default_owner" in content
        assert "default_repo" in content
        assert "[[source]]" in content
        # Unset options appear as comments
        assert "# sync_instructions" in content
        assert "# canonical_instructions" in content
        assert "# default_tool" in content

    def test_commented_canonical_instructions_example_is_valid(self, tmp_path):
        """Commented-out canonical_instructions example must be a valid value.

        When agr saves a config without canonical_instructions set, it writes
        a commented example. If a user uncomments it, the resulting value must
        pass validation (i.e. be a valid instruction filename, not a tool name).
        """
        config = AgrConfig()
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        # Uncomment the canonical_instructions line
        content = config_path.read_text()
        content = content.replace("# canonical_instructions", "canonical_instructions")
        config_path.write_text(content)

        # Should load without error — the example value must be valid
        loaded = AgrConfig.load(config_path)
        assert loaded.canonical_instructions is not None

    def test_dependency_with_source_roundtrip(self, tmp_path):
        """Dependency source persists through save/load."""
        config = AgrConfig()
        config.sources = [
            *config.sources,
        ]
        config.add_dependency(
            Dependency(type="skill", handle="user/skill", source="github")
        )
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        loaded = AgrConfig.load(config_path)
        assert loaded.dependencies[0].source == "github"

    def test_default_owner_defaults_to_computerlovetech(self):
        """Default owner is computerlovetech."""
        config = AgrConfig()
        assert config.default_owner == "computerlovetech"

    def test_load_default_owner(self, tmp_path):
        """Load config with custom default_owner."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_owner = "myorg"\ndependencies = []\n')
        config = AgrConfig.load(config_path)
        assert config.default_owner == "myorg"

    def test_save_and_load_default_owner_roundtrip(self, tmp_path):
        """Custom default_owner persists through save/load."""
        config = AgrConfig()
        config.default_owner = "myorg"
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        loaded = AgrConfig.load(config_path)
        assert loaded.default_owner == "myorg"

    def test_default_owner_always_written(self, tmp_path):
        """Default owner value is always written for discoverability."""
        config = AgrConfig()
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert 'default_owner = "computerlovetech"' in content

    def test_default_owner_written_when_custom(self, tmp_path):
        """Custom default_owner is written to file."""
        config = AgrConfig()
        config.default_owner = "myorg"
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert 'default_owner = "myorg"' in content

    def test_load_empty_default_owner_raises(self, tmp_path):
        """Empty default_owner in config raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_owner = ""\ndependencies = []\n')
        with pytest.raises(ConfigError, match="default_owner cannot be empty"):
            AgrConfig.load(config_path)

    def test_load_default_owner_with_slash_raises(self, tmp_path):
        """default_owner containing '/' raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_owner = "foo/bar"\ndependencies = []\n')
        with pytest.raises(ConfigError, match="cannot contain '/'"):
            AgrConfig.load(config_path)

    def test_load_default_owner_with_separator_raises(self, tmp_path):
        """default_owner containing '--' raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_owner = "foo--bar"\ndependencies = []\n')
        with pytest.raises(ConfigError, match="cannot contain '--'"):
            AgrConfig.load(config_path)

    def test_to_parsed_handle_with_default_owner(self):
        """Dependency.to_parsed_handle passes default_owner through."""
        dep = Dependency(type="skill", handle="setup")
        # Without default_owner, this would raise for a 1-part handle
        parsed = dep.to_parsed_handle(default_owner="myorg")
        assert parsed.username == "myorg"
        assert parsed.name == "setup"

    def test_add_dependency_deduplicates_one_part_handle(self):
        """Adding a normalized handle replaces a 1-part handle via also_matches."""
        config = AgrConfig()
        config.add_dependency(Dependency(type="skill", handle="setup"))
        assert len(config.dependencies) == 1

        config.add_dependency(
            Dependency(type="skill", handle="computerlovetech/setup"),
            also_matches=["setup"],
        )
        assert len(config.dependencies) == 1
        assert config.dependencies[0].handle == "computerlovetech/setup"

    # --- default_repo ---

    def test_default_repo_defaults_to_skills(self):
        """Default repo is 'skills'."""
        config = AgrConfig()
        assert config.default_repo == "skills"

    def test_load_default_repo(self, tmp_path):
        """Load config with custom default_repo."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_repo = "my-repo"\ndependencies = []\n')
        config = AgrConfig.load(config_path)
        assert config.default_repo == "my-repo"

    def test_save_and_load_default_repo_roundtrip(self, tmp_path):
        """Custom default_repo persists through save/load."""
        config = AgrConfig()
        config.default_repo = "my-repo"
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        loaded = AgrConfig.load(config_path)
        assert loaded.default_repo == "my-repo"

    def test_default_repo_always_written(self, tmp_path):
        """Default repo value is always written for discoverability."""
        config = AgrConfig()
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert 'default_repo = "skills"' in content

    def test_default_repo_written_when_custom(self, tmp_path):
        """Custom default_repo is written to file."""
        config = AgrConfig()
        config.default_repo = "my-repo"
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert 'default_repo = "my-repo"' in content

    def test_load_empty_default_repo_raises(self, tmp_path):
        """Empty default_repo in config raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_repo = ""\ndependencies = []\n')
        with pytest.raises(ConfigError, match="default_repo cannot be empty"):
            AgrConfig.load(config_path)

    def test_load_default_repo_with_slash_raises(self, tmp_path):
        """default_repo containing '/' raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_repo = "foo/bar"\ndependencies = []\n')
        with pytest.raises(ConfigError, match="cannot contain '/'"):
            AgrConfig.load(config_path)

    def test_load_default_repo_with_separator_raises(self, tmp_path):
        """default_repo containing '--' raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('default_repo = "foo--bar"\ndependencies = []\n')
        with pytest.raises(ConfigError, match="cannot contain '--'"):
            AgrConfig.load(config_path)

    def test_save_writes_comments(self, tmp_path):
        """Save writes explanatory comments for all config options."""
        config = AgrConfig()
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert "# Source to fetch skills from" in content
        assert "# Tools to install skills to" in content
        assert "# Default GitHub owner" in content
        assert "# Default GitHub repo" in content
        assert "# Sync instruction files" in content
        assert "# Which tool's instruction file" in content
        assert "# Primary tool for instruction sync" in content


class TestPackageDependency:
    """Tests for package dependency type."""

    def test_package_remote_dependency(self):
        """Create a remote package dependency."""
        dep = Dependency(type="package", handle="user/repo/bundle")
        assert dep.is_remote
        assert dep.is_package
        assert not dep.is_skill
        assert not dep.is_ralph
        assert dep.identifier == "user/repo/bundle"

    def test_package_type_in_toml(self, tmp_path):
        """Package type parses successfully from agr.toml."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'dependencies = [{handle = "user/repo/bundle", type = "package"}]\n'
        )
        config = AgrConfig.load(config_path)
        assert len(config.dependencies) == 1
        assert config.dependencies[0].type == "package"
        assert config.dependencies[0].is_package

    def test_package_type_from_toml_dict(self):
        """Deserialize a package dependency from TOML dict."""
        dep = Dependency.from_toml_dict(
            {"handle": "user/repo/bundle", "type": "package"}
        )
        assert dep.type == "package"
        assert dep.is_package

    def test_package_type_to_toml_dict(self):
        """Serialize a package dependency to TOML dict."""
        dep = Dependency(type="package", handle="user/repo/bundle")
        result = dep.to_toml_dict()
        assert result == {"handle": "user/repo/bundle", "type": "package"}

    def test_package_type_roundtrip(self):
        """Serialization and deserialization roundtrip for package type."""
        original = Dependency(type="package", handle="user/repo/bundle")
        restored = Dependency.from_toml_dict(original.to_toml_dict())
        assert restored.type == original.type
        assert restored.handle == original.handle

    def test_mixed_skill_ralph_package(self, tmp_path):
        """Config with skill, ralph, and package deps."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            "dependencies = [\n"
            '    {handle = "user/repo/my-skill", type = "skill"},\n'
            '    {handle = "user/repo/my-ralph", type = "ralph"},\n'
            '    {handle = "user/repo/my-bundle", type = "package"},\n'
            "]\n"
        )
        config = AgrConfig.load(config_path)
        assert len(config.dependencies) == 3
        assert config.dependencies[0].is_skill
        assert config.dependencies[1].is_ralph
        assert config.dependencies[2].is_package

    def test_package_installed_name(self):
        """Package installed_name returns the last segment."""
        dep = Dependency(type="package", handle="user/repo/my-bundle")
        assert dep.installed_name == "my-bundle"

    def test_load_sub_manifest_ignores_tools(self, tmp_path):
        """load_sub_manifest ignores invalid tool names."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'tools = ["nonexistent"]\n'
            'dependencies = [{handle = "a/b/c", type = "skill"}]\n'
        )
        # Full load would raise; sub_manifest should succeed
        config = AgrConfig.load_sub_manifest(config_path)
        assert len(config.dependencies) == 1

    def test_load_sub_manifest_ignores_sources(self, tmp_path):
        """load_sub_manifest ignores source blocks."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'dependencies = [{handle = "a/b/c", type = "skill"}]\n'
            "[[source]]\n"
            'name = "custom"\ntype = "git"\n'
            'url = "https://example.com/{owner}/{repo}.git"\n'
        )
        config = AgrConfig.load_sub_manifest(config_path)
        assert len(config.dependencies) == 1
        # Should use defaults, not the custom source
        assert config.sources[0].name == "github"
