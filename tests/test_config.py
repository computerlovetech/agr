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
        dep = Dependency(type="skill", handle="kasperjunge/commit")
        assert dep.is_remote
        assert not dep.is_local
        assert dep.identifier == "kasperjunge/commit"

    def test_local_dependency(self):
        """Create a local dependency."""
        dep = Dependency(type="skill", path="./my-skill")
        assert dep.is_local
        assert not dep.is_remote
        assert dep.identifier == "./my-skill"

    def test_both_handle_and_path_raises(self):
        """Cannot have both handle and path."""
        with pytest.raises(ValueError, match="cannot have both"):
            Dependency(type="skill", handle="user/skill", path="./local")

    def test_neither_handle_nor_path_raises(self):
        """Must have either handle or path."""
        with pytest.raises(ValueError, match="must have either"):
            Dependency(type="skill")

    def test_local_with_source_raises(self):
        """Local dependency cannot specify a source."""
        with pytest.raises(
            ValueError, match="Local dependency cannot specify a source"
        ):
            Dependency(type="skill", path="./my-skill", source="github")

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
        assert config.sync_instructions is None
        assert config.canonical_instructions is None

    def test_load_with_dependencies(self, tmp_path):
        """Load config with dependencies."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("""
dependencies = [
    { handle = "kasperjunge/commit", type = "skill" },
    { path = "./my-skill", type = "skill" },
]
""")
        config = AgrConfig.load(config_path)
        assert len(config.dependencies) == 2
        assert config.dependencies[0].handle == "kasperjunge/commit"
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
        config.add_dependency(Dependency(type="skill", handle="kasperjunge/commit"))
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        # Reload and verify
        loaded = AgrConfig.load(config_path)
        assert len(loaded.dependencies) == 1
        assert loaded.dependencies[0].handle == "kasperjunge/commit"
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

    def test_default_tools_not_written_to_file(self, tmp_path):
        """Default tools array not written to file."""
        config = AgrConfig()
        config_path = tmp_path / "agr.toml"
        config.save(config_path)

        content = config_path.read_text()
        assert "tools" not in content
        assert "default_source" in content
        assert "[[source]]" in content

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
