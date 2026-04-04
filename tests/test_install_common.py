"""Tests for agr._install_common module (direct imports)."""

import shutil
from unittest.mock import patch

import pytest

from agr._install_common import (
    _RemoteDepLocation,
    _dir_matches_handle,
    _dep_not_found_message,
    _rollback_on_failure,
    cleanup_empty_parents,
)
from agr.metadata import METADATA_KEY_ID
from agr.source import SourceConfig


class TestRemoteDepLocation:
    """Tests for _RemoteDepLocation named tuple."""

    def test_construction_and_field_access(self, tmp_path):
        source_cfg = SourceConfig(
            name="github", type="git", url="https://github.com/{owner}/{repo}"
        )
        loc = _RemoteDepLocation(
            repo_dir=tmp_path,
            source_path=tmp_path / "skill",
            source_config=source_cfg,
            is_legacy=False,
            commit="abc123",
        )
        assert loc.repo_dir == tmp_path
        assert loc.source_path == tmp_path / "skill"
        assert loc.source_config.name == "github"
        assert loc.is_legacy is False
        assert loc.commit == "abc123"

    def test_commit_defaults_to_none(self, tmp_path):
        source_cfg = SourceConfig(
            name="github", type="git", url="https://github.com/{owner}/{repo}"
        )
        loc = _RemoteDepLocation(
            repo_dir=tmp_path,
            source_path=tmp_path / "skill",
            source_config=source_cfg,
            is_legacy=False,
        )
        assert loc.commit is None


class TestDirMatchesHandle:
    """Tests for _dir_matches_handle."""

    def test_matches_when_metadata_id_present(self, tmp_path):
        dep_dir = tmp_path / "my-skill"
        dep_dir.mkdir()
        with patch("agr._install_common.read_resource_metadata") as mock_meta:
            mock_meta.return_value = {METADATA_KEY_ID: "user/repo/my-skill"}
            assert _dir_matches_handle(dep_dir, ["user/repo/my-skill"]) is True

    def test_no_match_when_id_differs(self, tmp_path):
        dep_dir = tmp_path / "my-skill"
        dep_dir.mkdir()
        with patch("agr._install_common.read_resource_metadata") as mock_meta:
            mock_meta.return_value = {METADATA_KEY_ID: "other/repo/my-skill"}
            assert _dir_matches_handle(dep_dir, ["user/repo/my-skill"]) is False

    def test_no_match_when_no_metadata(self, tmp_path):
        dep_dir = tmp_path / "my-skill"
        dep_dir.mkdir()
        with patch("agr._install_common.read_resource_metadata") as mock_meta:
            mock_meta.return_value = None
            assert _dir_matches_handle(dep_dir, ["user/repo/my-skill"]) is False


class TestDepNotFoundMessage:
    """Tests for _dep_not_found_message."""

    def test_skill_message(self):
        msg = _dep_not_found_message("Skill", "my-skill", "SKILL.md", "skills")
        assert "Skill 'my-skill' not found" in msg
        assert "SKILL.md" in msg
        assert "skills/my-skill/SKILL.md" in msg

    def test_ralph_message(self):
        msg = _dep_not_found_message("Ralph", "my-ralph", "RALPH.md", "ralphs")
        assert "Ralph 'my-ralph' not found" in msg
        assert "RALPH.md" in msg
        assert "ralphs/my-ralph/RALPH.md" in msg


class TestRollbackOnFailure:
    """Tests for _rollback_on_failure context manager."""

    def test_no_rollback_on_success(self, tmp_path):
        """Installed paths are kept when no exception occurs."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# test")

        with _rollback_on_failure() as installed:
            installed["claude"] = skill_dir

        assert skill_dir.exists()

    def test_rollback_on_exception(self, tmp_path):
        """All tracked paths are removed when an exception occurs."""
        dir_a = tmp_path / "skill-a"
        dir_b = tmp_path / "skill-b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "SKILL.md").write_text("# a")
        (dir_b / "SKILL.md").write_text("# b")

        with pytest.raises(RuntimeError):
            with _rollback_on_failure() as installed:
                installed["claude"] = dir_a
                installed["cursor"] = dir_b
                raise RuntimeError("simulated failure")

        assert not dir_a.exists()
        assert not dir_b.exists()

    def test_rollback_tolerates_missing_dir(self, tmp_path):
        """Rollback doesn't crash if a tracked dir was already removed."""
        dir_a = tmp_path / "skill-a"
        dir_a.mkdir()

        with pytest.raises(RuntimeError):
            with _rollback_on_failure() as installed:
                installed["claude"] = dir_a
                shutil.rmtree(dir_a)
                raise RuntimeError("simulated failure")


class TestCleanupEmptyParents:
    """Tests for cleanup_empty_parents (direct import)."""

    def test_stops_at_boundary(self, tmp_path):
        stop_at = tmp_path / "skills"
        stop_at.mkdir()
        nested = stop_at / "a" / "b" / "c"
        nested.mkdir(parents=True)

        cleanup_empty_parents(nested, stop_at)

        assert not (stop_at / "a").exists()
        assert stop_at.exists()

    def test_handles_non_empty_dir(self, tmp_path):
        stop_at = tmp_path / "skills"
        stop_at.mkdir()
        nested = stop_at / "a" / "b"
        nested.mkdir(parents=True)
        (stop_at / "a" / "file.txt").write_text("content")

        cleanup_empty_parents(nested, stop_at)

        assert not (stop_at / "a" / "b").exists()
        assert (stop_at / "a").exists()
        assert (stop_at / "a" / "file.txt").exists()
