"""Tests for agr._install_common module (direct imports)."""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from agr._install_common import (
    RemoteDepLocation,
    _dir_matches_handle,
    check_self_install,
    cleanup_empty_parents,
    dep_not_found_message,
    prepare_local_handle,
    rollback_on_failure,
)
from agr.handle import ParsedHandle
from agr.metadata import METADATA_KEY_ID
from agr.source import SourceConfig


class TestRemoteDepLocation:
    """Tests for RemoteDepLocation named tuple."""

    def test_construction_and_field_access(self, tmp_path):
        source_cfg = SourceConfig(
            name="github", type="git", url="https://github.com/{owner}/{repo}"
        )
        loc = RemoteDepLocation(
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
        loc = RemoteDepLocation(
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
    """Tests for dep_not_found_message."""

    def test_skill_message(self):
        msg = dep_not_found_message("Skill", "my-skill", "SKILL.md", "skills")
        assert "Skill 'my-skill' not found" in msg
        assert "SKILL.md" in msg
        assert "skills/my-skill/SKILL.md" in msg

    def test_ralph_message(self):
        msg = dep_not_found_message("Ralph", "my-ralph", "RALPH.md", "ralphs")
        assert "Ralph 'my-ralph' not found" in msg
        assert "RALPH.md" in msg
        assert "ralphs/my-ralph/RALPH.md" in msg


class TestRollbackOnFailure:
    """Tests for rollback_on_failure context manager."""

    def test_no_rollback_on_success(self, tmp_path):
        """Installed paths are kept when no exception occurs."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# test")

        with rollback_on_failure() as installed:
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
            with rollback_on_failure() as installed:
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
            with rollback_on_failure() as installed:
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


class TestPrepareLocalHandle:
    """Tests for prepare_local_handle."""

    def test_creates_handle_from_source_path(self, tmp_path):
        source = tmp_path / "my-skill"
        source.mkdir()
        handle, repo_root = prepare_local_handle(source, None, None)
        assert handle.is_local
        assert handle.name == "my-skill"
        assert handle.local_path == source
        assert repo_root == Path.cwd()

    def test_preserves_existing_handle(self, tmp_path):
        source = tmp_path / "my-skill"
        source.mkdir()
        existing = ParsedHandle(is_local=True, name="custom-name", local_path=source)
        handle, repo_root = prepare_local_handle(source, existing, tmp_path)
        assert handle is existing
        assert handle.name == "custom-name"
        assert repo_root == tmp_path

    def test_defaults_repo_root_to_cwd(self, tmp_path):
        source = tmp_path / "my-skill"
        source.mkdir()
        _, repo_root = prepare_local_handle(source, None, None)
        assert repo_root == Path.cwd()

    def test_preserves_explicit_repo_root(self, tmp_path):
        source = tmp_path / "my-skill"
        source.mkdir()
        _, repo_root = prepare_local_handle(source, None, tmp_path)
        assert repo_root == tmp_path


class TestCheckSelfInstall:
    """Tests for check_self_install."""

    def test_returns_path_on_self_install(self, tmp_path):
        """When source IS the destination, returns the path."""
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# test")

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=skill_dir)
        result = check_self_install(
            skill_dir, skill_dir, handle, tmp_path, lambda p: (p / "SKILL.md").exists()
        )
        assert result == skill_dir

    def test_stamps_metadata_on_self_install(self, tmp_path):
        """Self-install stamps metadata when none exists."""
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# test")

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=skill_dir)
        with patch("agr._install_common.read_resource_metadata", return_value=None):
            with patch("agr._install_common.stamp_resource_metadata") as mock_stamp:
                check_self_install(
                    skill_dir,
                    skill_dir,
                    handle,
                    tmp_path,
                    lambda p: (p / "SKILL.md").exists(),
                    tool_name="claude",
                )
                mock_stamp.assert_called_once_with(
                    skill_dir, handle, tmp_path, "my-skill", tool_name="claude"
                )

    def test_skips_stamp_when_metadata_exists(self, tmp_path):
        """Self-install skips stamp when metadata already present."""
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# test")

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=skill_dir)
        with patch(
            "agr._install_common.read_resource_metadata", return_value={"id": "x"}
        ):
            with patch("agr._install_common.stamp_resource_metadata") as mock_stamp:
                result = check_self_install(
                    skill_dir,
                    skill_dir,
                    handle,
                    tmp_path,
                    lambda p: (p / "SKILL.md").exists(),
                )
                assert result == skill_dir
                mock_stamp.assert_not_called()

    def test_returns_none_when_paths_differ(self, tmp_path):
        """Returns None when source and destination are different paths."""
        source = tmp_path / "source" / "my-skill"
        dest = tmp_path / "dest" / "my-skill"
        source.mkdir(parents=True)

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=source)
        result = check_self_install(source, dest, handle, tmp_path, lambda p: True)
        assert result is None

    def test_returns_none_when_dest_invalid(self, tmp_path):
        """Returns None when destination fails validation."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=skill_dir)
        result = check_self_install(
            skill_dir, skill_dir, handle, tmp_path, lambda p: False
        )
        assert result is None
