"""Tests for agr.skill_installer module (direct imports)."""

import pytest

from agr.exceptions import SkillNotFoundError
from agr.handle import ParsedHandle
from agr.skill import SKILL_MARKER
from agr.skill_installer import (
    _find_local_name_conflicts,
    fetch_and_install,
    install_local_skill,
    is_skill_installed,
    skill_not_found_message,
    uninstall_skill,
)
from agr.tool import CLAUDE


class TestDirectImportSmoke:
    """Smoke tests verifying direct imports from agr.skill_installer work."""

    def test_install_and_uninstall(self, tmp_path, skill_fixture):
        """Install and uninstall a local skill via direct imports."""
        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        path = install_local_skill(skill_fixture, dest_dir, CLAUDE)
        assert path.exists()
        assert (path / SKILL_MARKER).exists()

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )
        assert is_skill_installed(handle, tmp_path, CLAUDE, skills_dir=dest_dir)

        removed = uninstall_skill(handle, tmp_path, CLAUDE, skills_dir=dest_dir)
        assert removed is True
        assert not path.exists()

    def test_install_invalid_raises(self, tmp_path):
        """Installing non-skill raises SkillNotFoundError."""
        source = tmp_path / "not-a-skill"
        source.mkdir()
        dest = tmp_path / ".claude" / "skills"
        dest.mkdir(parents=True)

        with pytest.raises(SkillNotFoundError):
            install_local_skill(source, dest, CLAUDE)

    def test_skill_not_found_message(self):
        msg = skill_not_found_message("missing-skill")
        assert "missing-skill" in msg
        assert "SKILL.md" in msg

    def test_fetch_and_install_local(self, tmp_path, skill_fixture):
        """fetch_and_install works for local handles via direct import."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )
        path = fetch_and_install(handle, repo_root, CLAUDE)
        assert path.exists()
        assert (path / SKILL_MARKER).exists()


class TestFindLocalNameConflictsFlat:
    """Local name conflict detection for flat tools."""

    def test_unknown_skill_at_dest_is_conflict(self, tmp_path):
        """A skill at the destination path without metadata is a conflict.

        Without metadata we cannot determine ownership, so it must be
        flagged to avoid silently overwriting someone else's work.
        """
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Place a valid skill at the destination path *without* metadata
        existing = skills_dir / "my-skill"
        existing.mkdir()
        (existing / SKILL_MARKER).write_text("---\nname: my-skill\n---\n")

        handle = ParsedHandle(
            is_local=True,
            name="my-skill",
            local_path=tmp_path / "src" / "my-skill",
        )

        conflicts, has_unknown = _find_local_name_conflicts(
            handle, skills_dir, CLAUDE, tmp_path
        )
        assert conflicts == [existing]
        assert has_unknown is True
