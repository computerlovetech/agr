"""Tests for GitHub Copilot support."""

from pathlib import Path


from agr.config import AgrConfig
from agr.fetcher import (
    install_local_skill,
    is_skill_installed,
)
from agr.handle import ParsedHandle
from agr.skill import SKILL_MARKER
from agr.tool import CLAUDE, COPILOT, CURSOR, get_tool


class TestCopilotToolConfig:
    """Tests for Copilot tool configuration."""

    def test_copilot_is_flat(self):
        """Copilot uses flat directory structure like Claude."""
        assert not COPILOT.supports_nested

    def test_copilot_config_dir(self):
        """Copilot uses .github for project skills."""
        assert COPILOT.config_dir == ".github"

    def test_copilot_global_config_dir(self):
        """Copilot uses .copilot for personal skills."""
        assert COPILOT.global_config_dir == ".copilot"

    def test_get_tool_copilot(self):
        """Get Copilot tool config by name."""
        tool = get_tool("copilot")
        assert tool == COPILOT

    def test_copilot_project_skills_dir(self, tmp_path):
        """Copilot project skills go to .github/skills/."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        skills_dir = COPILOT.get_skills_dir(repo_root)
        assert skills_dir == repo_root / ".github" / "skills"

    def test_copilot_global_skills_dir(self, monkeypatch, tmp_path):
        """Copilot personal skills go to ~/.copilot/skills/."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        global_dir = COPILOT.get_global_skills_dir()
        assert global_dir == tmp_path / ".copilot" / "skills"

    def test_copilot_global_dir_differs_from_project(self, monkeypatch, tmp_path):
        """Copilot global path (~/.copilot/) differs from project path (.github/)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        project_dir = COPILOT.get_skills_dir(repo_root)
        global_dir = COPILOT.get_global_skills_dir()

        # Project uses .github
        assert ".github" in str(project_dir)
        # Global uses .copilot
        assert ".copilot" in str(global_dir)
        assert ".github" not in str(global_dir)


class TestCopilotPaths:
    """Tests for Copilot path generation."""

    def test_remote_skill_flat_path(self):
        """Remote skill gets flat path for Copilot."""
        h = ParsedHandle(username="maragudk", repo="skills", name="bluesky")
        assert h.to_skill_path(COPILOT) == Path("bluesky")

    def test_remote_skill_no_repo_flat(self):
        """Remote skill without repo gets flat path for Copilot."""
        h = ParsedHandle(username="kasperjunge", name="commit")
        assert h.to_skill_path(COPILOT) == Path("commit")

    def test_local_skill_flat_path(self):
        """Local skill gets flat path for Copilot."""
        h = ParsedHandle(is_local=True, name="my-skill")
        assert h.to_skill_path(COPILOT) == Path("my-skill")

    def test_copilot_paths_match_claude(self):
        """Copilot uses same path format as Claude (both flat)."""
        handles = [
            ParsedHandle(username="maragudk", repo="skills", name="bluesky"),
            ParsedHandle(username="kasperjunge", name="commit"),
            ParsedHandle(is_local=True, name="my-skill"),
        ]
        for h in handles:
            assert h.to_skill_path(COPILOT) == h.to_skill_path(CLAUDE)

    def test_copilot_paths_match_cursor(self):
        """Both Copilot and Cursor use flat paths."""
        h = ParsedHandle(username="maragudk", repo="skills", name="bluesky")
        assert h.to_skill_path(COPILOT) == Path("bluesky")
        assert h.to_skill_path(CURSOR) == Path("bluesky")



class TestCopilotInstallation:
    """Tests for installing skills to Copilot."""

    def test_install_local_skill_to_copilot(self, tmp_path, skill_fixture):
        """Install a local skill with flat structure."""
        dest_dir = tmp_path / ".github" / "skills"
        dest_dir.mkdir(parents=True)

        installed_path = install_local_skill(skill_fixture, dest_dir, COPILOT)

        # Should be flat: test-skill/
        assert installed_path == dest_dir / skill_fixture.name
        assert installed_path.exists()
        assert (installed_path / SKILL_MARKER).exists()

    def test_install_creates_flat_structure(self, tmp_path, skill_fixture):
        """Flat installation creates single-level directory."""
        dest_dir = tmp_path / ".github" / "skills"
        dest_dir.mkdir(parents=True)

        install_local_skill(skill_fixture, dest_dir, COPILOT)

        # Verify flat structure (no "local" parent directory)
        assert not (dest_dir / "local").exists()
        assert (dest_dir / skill_fixture.name).is_dir()


class TestCopilotVsClaude:
    """Tests comparing Copilot and Claude behavior."""

    def test_both_flat_same_structure(self, tmp_path, skill_fixture):
        """Both Claude and Copilot create same flat structure."""
        # Install to Claude
        claude_skills = tmp_path / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        claude_path = install_local_skill(skill_fixture, claude_skills, CLAUDE)

        # Install to Copilot
        copilot_skills = tmp_path / ".github" / "skills"
        copilot_skills.mkdir(parents=True)
        copilot_path = install_local_skill(skill_fixture, copilot_skills, COPILOT)

        # Both should have same directory name (just different parent)
        assert claude_path.name == copilot_path.name
        assert claude_path.name == skill_fixture.name


class TestCopilotIsSkillInstalled:
    """Tests for is_skill_installed with Copilot."""

    def test_check_copilot_skill(self, tmp_path, skill_fixture):
        """Check if Copilot skill is installed."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        skills_dir = repo_root / ".github" / "skills"
        skills_dir.mkdir(parents=True)

        install_local_skill(skill_fixture, skills_dir, COPILOT)

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )
        assert is_skill_installed(handle, repo_root, COPILOT)


class TestCopilotConfigTools:
    """Tests for copilot in tools field."""

    def test_load_copilot_from_config(self, tmp_path):
        """Load tools list with copilot from config file."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            """
tools = ["copilot"]
dependencies = []
"""
        )

        config = AgrConfig.load(config_path)
        assert config.tools == ["copilot"]

    def test_load_multiple_tools_with_copilot(self, tmp_path):
        """Load tools list with multiple tools including copilot."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            """
tools = ["claude", "cursor", "copilot"]
dependencies = []
"""
        )

        config = AgrConfig.load(config_path)
        assert "copilot" in config.tools
        assert len(config.tools) == 3

    def test_save_copilot_tools(self, tmp_path):
        """Save tools array with copilot."""
        config_path = tmp_path / "agr.toml"

        config = AgrConfig()
        config.tools = ["copilot"]
        config.save(config_path)

        content = config_path.read_text()
        assert 'tools = ["copilot"]' in content


class TestGlobalConfigDirBackwardsCompatibility:
    """Tests that global_config_dir doesn't break existing tools."""

    def test_claude_global_dir_unchanged(self, monkeypatch, tmp_path):
        """Claude global dir still uses .claude (no global_config_dir set)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert CLAUDE.global_config_dir is None
        global_dir = CLAUDE.get_global_skills_dir()
        assert global_dir == tmp_path / ".claude" / "skills"

    def test_cursor_global_dir_unchanged(self, monkeypatch, tmp_path):
        """Cursor global dir still uses .cursor (no global_config_dir set)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert CURSOR.global_config_dir is None
        global_dir = CURSOR.get_global_skills_dir()
        assert global_dir == tmp_path / ".cursor" / "skills"
