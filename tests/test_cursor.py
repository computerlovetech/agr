"""Tests for Cursor support with flat directory structures.

Cursor uses flat naming like Claude: skills are direct children of the
skills directory.  Per the Cursor docs, skill identifiers are "lowercase
letters, numbers, and hyphens only" and must match the parent folder name.
"""

from pathlib import Path

import pytest

from agr.config import AgrConfig
from agr.fetcher import (
    fetch_and_install,
    install_local_skill,
    is_skill_installed,
    uninstall_skill,
)
from agr.handle import ParsedHandle
from agr.skill import SKILL_MARKER
from agr.tool import CLAUDE, CURSOR, get_tool


class TestToolConfig:
    """Tests for tool configuration."""

    def test_claude_is_flat(self):
        """Claude uses flat directory structure."""
        assert not CLAUDE.supports_nested

    def test_cursor_is_flat(self):
        """Cursor uses flat directory structure per Cursor docs."""
        assert not CURSOR.supports_nested

    def test_get_tool_claude(self):
        """Get Claude tool config by name."""
        tool = get_tool("claude")
        assert tool == CLAUDE

    def test_get_tool_cursor(self):
        """Get Cursor tool config by name."""
        tool = get_tool("cursor")
        assert tool == CURSOR

    def test_get_tool_unknown_raises(self):
        """Getting unknown tool raises."""
        from agr.exceptions import AgrError

        with pytest.raises(AgrError, match="Unknown tool"):
            get_tool("unknown")


class TestFlatPaths:
    """Tests for flat path generation for Cursor."""

    def test_remote_skill_flat_path_claude(self):
        """Remote skill gets flat path for Claude."""
        h = ParsedHandle(username="maragudk", repo="skills", name="collab")
        assert h.to_skill_path(CLAUDE) == Path("collab")

    def test_remote_skill_flat_path_cursor(self):
        """Remote skill gets flat path for Cursor."""
        h = ParsedHandle(username="maragudk", repo="skills", name="collab")
        assert h.to_skill_path(CURSOR) == Path("collab")

    def test_remote_skill_no_repo_flat_claude(self):
        """Remote skill without repo gets flat path for Claude."""
        h = ParsedHandle(username="kasperjunge", name="commit")
        assert h.to_skill_path(CLAUDE) == Path("commit")

    def test_remote_skill_no_repo_flat_cursor(self):
        """Remote skill without repo gets flat path for Cursor."""
        h = ParsedHandle(username="kasperjunge", name="commit")
        assert h.to_skill_path(CURSOR) == Path("commit")

    def test_local_skill_flat_path_claude(self):
        """Local skill gets flat path for Claude."""
        h = ParsedHandle(is_local=True, name="my-skill")
        assert h.to_skill_path(CLAUDE) == Path("my-skill")

    def test_local_skill_flat_path_cursor(self):
        """Local skill gets flat path for Cursor."""
        h = ParsedHandle(is_local=True, name="my-skill")
        assert h.to_skill_path(CURSOR) == Path("my-skill")



class TestCursorInstallation:
    """Tests for installing skills to Cursor (flat naming)."""

    def test_install_local_skill_to_cursor(self, tmp_path, skill_fixture):
        """Install a local skill with flat structure."""
        dest_dir = tmp_path / ".cursor" / "skills"
        dest_dir.mkdir(parents=True)

        installed_path = install_local_skill(skill_fixture, dest_dir, CURSOR)

        # Should be flat: test-skill/ (same as Claude)
        assert installed_path == dest_dir / skill_fixture.name
        assert installed_path.exists()
        assert (installed_path / SKILL_MARKER).exists()

    def test_install_preserves_flat_structure(self, tmp_path, skill_fixture):
        """Flat installation creates skill as direct child."""
        dest_dir = tmp_path / ".cursor" / "skills"
        dest_dir.mkdir(parents=True)

        install_local_skill(skill_fixture, dest_dir, CURSOR)

        # Verify directory structure is flat (no local/ parent)
        assert (dest_dir / skill_fixture.name).is_dir()
        assert not (dest_dir / "local").exists()


class TestCursorUninstallation:
    """Tests for uninstalling skills from Cursor."""

    def test_uninstall_flat_skill(self, tmp_path, skill_fixture):
        """Uninstalling from Cursor removes the flat skill directory."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        skills_dir = repo_root / ".cursor" / "skills"
        skills_dir.mkdir(parents=True)

        # Install skill
        install_local_skill(skill_fixture, skills_dir, CURSOR)

        # Verify flat structure exists
        assert (skills_dir / skill_fixture.name).exists()

        # Uninstall
        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )
        removed = uninstall_skill(handle, repo_root, CURSOR)

        assert removed
        assert not (skills_dir / skill_fixture.name).exists()


class TestMultiToolInstallation:
    """Tests for installing to multiple tools."""

    def test_install_to_both_tools(self, tmp_path, skill_fixture):
        """Installing to both Claude and Cursor creates same structure."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        # Install to Claude
        claude_skills = repo_root / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        install_local_skill(skill_fixture, claude_skills, CLAUDE)

        # Install to Cursor
        cursor_skills = repo_root / ".cursor" / "skills"
        cursor_skills.mkdir(parents=True)
        install_local_skill(skill_fixture, cursor_skills, CURSOR)

        # Verify both have flat structure
        claude_path = claude_skills / skill_fixture.name
        assert claude_path.exists()
        assert (claude_path / SKILL_MARKER).exists()

        cursor_path = cursor_skills / skill_fixture.name
        assert cursor_path.exists()
        assert (cursor_path / SKILL_MARKER).exists()


class TestIsSkillInstalledFlat:
    """Tests for is_skill_installed with flat Cursor structure."""

    def test_check_flat_skill(self, tmp_path, skill_fixture):
        """Check if flat Cursor skill is installed."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        skills_dir = repo_root / ".cursor" / "skills"
        skills_dir.mkdir(parents=True)

        install_local_skill(skill_fixture, skills_dir, CURSOR)

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )
        assert is_skill_installed(handle, repo_root, CURSOR)


class TestFlattenNestedCursorSkills:
    """Tests for migrating legacy nested Cursor skill dirs to flat naming."""

    def test_flatten_nested_user_repo_skill(self, tmp_path):
        """Nested user/repo/skill/ is flattened to skill/."""
        from agr.commands.migrations import _flatten_nested_skills

        skills_dir = tmp_path / ".cursor" / "skills"
        nested = skills_dir / "maragudk" / "skills" / "collab"
        nested.mkdir(parents=True)
        (nested / SKILL_MARKER).write_text("---\nname: collab\n---\n# Test")

        _flatten_nested_skills(skills_dir)

        assert (skills_dir / "collab" / SKILL_MARKER).exists()
        assert not (skills_dir / "maragudk").exists()

    def test_flatten_nested_local_skill(self, tmp_path):
        """Nested local/skill/ is flattened to skill/."""
        from agr.commands.migrations import _flatten_nested_skills

        skills_dir = tmp_path / ".cursor" / "skills"
        nested = skills_dir / "local" / "my-skill"
        nested.mkdir(parents=True)
        (nested / SKILL_MARKER).write_text("---\nname: my-skill\n---\n# Test")

        _flatten_nested_skills(skills_dir)

        assert (skills_dir / "my-skill" / SKILL_MARKER).exists()
        assert not (skills_dir / "local").exists()

    def test_flatten_falls_back_to_qualified_name_on_collision(self, tmp_path):
        """When plain name is taken, uses user--repo--skill form."""
        from agr.commands.migrations import _flatten_nested_skills

        skills_dir = tmp_path / ".cursor" / "skills"

        # Existing flat skill occupying the name
        existing = skills_dir / "collab"
        existing.mkdir(parents=True)
        (existing / SKILL_MARKER).write_text("---\nname: collab\n---\n# Existing")

        # Nested skill with same name
        nested = skills_dir / "maragudk" / "skills" / "collab"
        nested.mkdir(parents=True)
        (nested / SKILL_MARKER).write_text("---\nname: collab\n---\n# Nested")

        _flatten_nested_skills(skills_dir)

        # Original stays
        assert (skills_dir / "collab" / SKILL_MARKER).exists()
        # Nested moved to qualified name
        assert (skills_dir / "maragudk--skills--collab" / SKILL_MARKER).exists()
        assert not (skills_dir / "maragudk").exists()

    def test_flatten_skips_nonexistent_dir(self, tmp_path):
        """No error when skills directory does not exist."""
        from agr.commands.migrations import _flatten_nested_skills

        _flatten_nested_skills(tmp_path / "nonexistent")

    def test_flatten_ignores_already_flat_skills(self, tmp_path):
        """Flat skills (depth=1) are left untouched."""
        from agr.commands.migrations import _flatten_nested_skills

        skills_dir = tmp_path / ".cursor" / "skills"
        flat = skills_dir / "my-skill"
        flat.mkdir(parents=True)
        (flat / SKILL_MARKER).write_text("---\nname: my-skill\n---\n# Flat")

        _flatten_nested_skills(skills_dir)

        assert (skills_dir / "my-skill" / SKILL_MARKER).exists()


class TestConfigTools:
    """Tests for tools field in config."""

    def test_default_tools(self, tmp_path):
        """Default tools is just Claude."""
        config = AgrConfig()
        assert config.tools == ["claude"]

    def test_load_tools_from_config(self, tmp_path):
        """Load tools list from config file."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            """
tools = ["claude", "cursor"]
dependencies = []
"""
        )

        config = AgrConfig.load(config_path)
        assert config.tools == ["claude", "cursor"]

    def test_save_non_default_tools(self, tmp_path):
        """Save tools array when not default."""
        config_path = tmp_path / "agr.toml"

        config = AgrConfig()
        config.tools = ["claude", "cursor"]
        config.save(config_path)

        content = config_path.read_text()
        assert 'tools = ["claude", "cursor"]' in content

    def test_save_default_tools_omits(self, tmp_path):
        """Default tools (just claude) is not saved."""
        config_path = tmp_path / "agr.toml"

        config = AgrConfig()
        config.tools = ["claude"]
        config.save(config_path)

        content = config_path.read_text()
        assert "tools" not in content


class TestFetchAndInstallWithTool:
    """Tests for fetch_and_install with tool parameter."""

    def test_fetch_local_with_cursor(self, tmp_path, skill_fixture):
        """Fetch and install local skill to Cursor (flat)."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )

        installed_path = fetch_and_install(handle, repo_root, CURSOR)

        # Should be flat structure
        expected = repo_root / ".cursor" / "skills" / skill_fixture.name
        assert installed_path == expected
        assert installed_path.exists()
