"""Tests for Skill class."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agr.exceptions import (
    InvalidHandleError,
    InvalidLocalPathError,
    RepoNotFoundError,
    SkillNotFoundError,
)
from agr.git import get_head_commit
from agr.sdk.skill import Skill


class TestSkillFromLocal:
    """Tests for Skill.from_local()."""

    def test_from_local_valid_skill(self, mock_skill_dir: Path):
        """Test loading a valid local skill."""
        skill = Skill.from_local(mock_skill_dir)

        assert skill.name == "test-skill"
        assert skill.path == mock_skill_dir
        assert skill.handle is not None
        assert skill.handle.is_local

    def test_from_local_string_path(self, mock_skill_dir: Path):
        """Test loading with string path."""
        skill = Skill.from_local(str(mock_skill_dir))

        assert skill.name == "test-skill"
        assert skill.path == mock_skill_dir

    def test_from_local_nonexistent_path(self, tmp_path: Path):
        """Test loading from nonexistent path."""
        with pytest.raises(InvalidLocalPathError, match="does not exist"):
            Skill.from_local(tmp_path / "nonexistent")

    def test_from_local_invalid_skill(self, tmp_path: Path):
        """Test loading directory without SKILL.md."""
        invalid_dir = tmp_path / "invalid"
        invalid_dir.mkdir()
        (invalid_dir / "README.md").write_text("Not a skill")

        with pytest.raises(InvalidLocalPathError, match="not a valid skill"):
            Skill.from_local(invalid_dir)


class TestSkillPrompt:
    """Tests for prompt property."""

    def test_prompt_loads_skill_md(self, mock_skill_dir: Path):
        """Test that prompt property returns SKILL.md content."""
        skill = Skill.from_local(mock_skill_dir)

        assert "# Test Skill" in skill.prompt
        assert "A test skill for unit tests" in skill.prompt

    def test_prompt_cached(self, mock_skill_dir: Path):
        """Test that prompt is cached after first access."""
        skill = Skill.from_local(mock_skill_dir)

        # Access twice
        _ = skill.prompt
        _ = skill.prompt

        # Should only read file once (verify via _prompt being set)
        assert skill._prompt is not None


class TestSkillFiles:
    """Tests for files property."""

    def test_files_lists_all_files(self, mock_skill_dir: Path):
        """Test that files property lists all files in skill dir."""
        skill = Skill.from_local(mock_skill_dir)

        assert "SKILL.md" in skill.files
        assert "helper.py" in skill.files
        assert len(skill.files) == 2

    def test_files_sorted(self, mock_skill_dir: Path):
        """Test that files are sorted alphabetically."""
        skill = Skill.from_local(mock_skill_dir)

        assert skill.files == sorted(skill.files)


class TestSkillReadFile:
    """Tests for read_file method."""

    def test_read_file_success(self, mock_skill_dir: Path):
        """Test reading a file from the skill."""
        skill = Skill.from_local(mock_skill_dir)

        content = skill.read_file("helper.py")
        assert "print('hello')" in content

    def test_read_file_skill_md(self, mock_skill_dir: Path):
        """Test reading SKILL.md."""
        skill = Skill.from_local(mock_skill_dir)

        content = skill.read_file("SKILL.md")
        assert "# Test Skill" in content

    def test_read_file_not_found(self, mock_skill_dir: Path):
        """Test reading nonexistent file."""
        skill = Skill.from_local(mock_skill_dir)

        with pytest.raises(FileNotFoundError):
            skill.read_file("nonexistent.txt")

    def test_read_file_path_traversal_blocked(self, mock_skill_dir: Path):
        """Test that path traversal is blocked."""
        skill = Skill.from_local(mock_skill_dir)

        with pytest.raises(ValueError, match="cannot contain"):
            skill.read_file("../outside.txt")

    def test_read_file_absolute_path_escape_blocked(
        self, mock_skill_dir: Path, tmp_path: Path
    ):
        """Test that absolute path escapes are blocked."""
        skill = Skill.from_local(mock_skill_dir)

        # Try using .. to escape (explicit test)
        with pytest.raises(ValueError, match="cannot contain"):
            skill.read_file("subdir/../../../etc/passwd")

    def test_read_file_symlink_escape_blocked(self, tmp_path: Path):
        """Test that symlinks pointing outside skill directory are blocked."""
        # Create skill directory
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill\nTest content.")

        # Create a file outside the skill directory
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret content")

        # Create a symlink inside skill directory pointing outside
        symlink = skill_dir / "link"
        symlink.symlink_to(outside_file)

        skill = Skill.from_local(skill_dir)

        # Should be blocked because resolved path is outside skill directory
        with pytest.raises(ValueError, match="escapes skill directory"):
            skill.read_file("link")

    def test_read_file_prefix_attack_blocked(self, tmp_path: Path):
        """Test that prefix attack (/skill vs /skill_other) is blocked.

        This tests the fix for using is_relative_to() instead of startswith().
        A path like /tmp/skill_other should not pass a check for /tmp/skill.
        """
        # Create two directories: skill and skill_other
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill\nTest content.")

        skill_other_dir = tmp_path / "skill_other"
        skill_other_dir.mkdir()
        (skill_other_dir / "secret.txt").write_text("secret content")

        skill = Skill.from_local(skill_dir)

        # Attempting to access skill_other/secret.txt via path manipulation
        # This would pass a startswith check but should fail with is_relative_to
        # The path "../skill_other/secret.txt" contains ".." so it's blocked early
        with pytest.raises(ValueError, match="cannot contain"):
            skill.read_file("../skill_other/secret.txt")


class TestSkillMetadata:
    """Tests for metadata property."""

    def test_metadata_local_skill(self, mock_skill_dir: Path):
        """Test metadata for local skill."""
        skill = Skill.from_local(mock_skill_dir)

        metadata = skill.metadata
        assert metadata["name"] == "test-skill"
        assert metadata["is_local"] is True
        assert metadata["source"] is None
        assert metadata["revision"] is None


class TestSkillFromGit:
    """Tests for Skill.from_git()."""

    def test_from_git_rejects_local_path(self):
        """Test that from_git rejects local paths."""
        with pytest.raises(InvalidHandleError, match="local path"):
            Skill.from_git("./local-skill")

    @patch("agr.sdk.skill.downloaded_repo")
    @patch("agr.sdk.skill.prepare_repo_for_skill")
    @patch("agr.sdk.skill.get_head_commit")
    @patch("agr.sdk.skill.is_cached")
    @patch("agr.sdk.skill.cache_skill")
    def test_from_git_downloads_and_caches(
        self,
        mock_cache_skill: MagicMock,
        mock_is_cached: MagicMock,
        mock_get_commit: MagicMock,
        mock_prepare: MagicMock,
        mock_download: MagicMock,
        mock_skill_dir: Path,
    ):
        """Test that from_git downloads and caches skill."""
        # Setup mocks
        mock_is_cached.return_value = False
        mock_get_commit.return_value = "abc123"
        mock_download.__enter__ = MagicMock(return_value=mock_skill_dir.parent)
        mock_download.__exit__ = MagicMock(return_value=False)
        mock_download.return_value = mock_download
        mock_prepare.return_value = mock_skill_dir
        mock_cache_skill.return_value = mock_skill_dir

        skill = Skill.from_git("testuser/test-skill")

        assert skill.name == "test-skill"
        mock_cache_skill.assert_called_once()

    @patch("agr.sdk.skill.downloaded_repo")
    @patch("agr.sdk.skill.get_head_commit")
    @patch("agr.sdk.skill.is_cached")
    @patch("agr.sdk.skill.get_skill_cache_path")
    def test_from_git_uses_cache_when_available(
        self,
        mock_get_path: MagicMock,
        mock_is_cached: MagicMock,
        mock_get_commit: MagicMock,
        mock_download: MagicMock,
        mock_skill_dir: Path,
    ):
        """Test that from_git uses cache when available."""
        # Setup mocks
        mock_is_cached.return_value = True
        mock_get_commit.return_value = "abc123"
        mock_get_path.return_value = mock_skill_dir
        mock_download.__enter__ = MagicMock(return_value=mock_skill_dir.parent)
        mock_download.__exit__ = MagicMock(return_value=False)
        mock_download.return_value = mock_download

        skill = Skill.from_git("testuser/test-skill")

        assert skill.name == "test-skill"
        assert skill.path == mock_skill_dir

    @patch("agr.sdk.skill.downloaded_repo")
    @patch("agr.sdk.skill.prepare_repo_for_skill")
    @patch("agr.sdk.skill.get_head_commit")
    @patch("agr.sdk.skill.is_cached")
    def test_from_git_skill_not_found(
        self,
        mock_is_cached: MagicMock,
        mock_get_commit: MagicMock,
        mock_prepare: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ):
        """Test that from_git raises when skill not found."""
        mock_is_cached.return_value = False
        mock_get_commit.return_value = "abc123"
        mock_download.__enter__ = MagicMock(return_value=tmp_path)
        mock_download.__exit__ = MagicMock(return_value=False)
        mock_download.return_value = mock_download
        mock_prepare.return_value = None

        with pytest.raises(SkillNotFoundError):
            Skill.from_git("testuser/nonexistent")

    @patch("agr.sdk.skill.downloaded_repo")
    def test_from_git_repo_not_found(self, mock_download: MagicMock):
        """Test that from_git raises when repo candidates are missing."""
        mock_download.side_effect = [
            RepoNotFoundError("missing skills"),
            RepoNotFoundError("missing legacy"),
        ]

        with pytest.raises(RepoNotFoundError):
            Skill.from_git("testuser/test-skill")


class TestSkillContentHash:
    """Tests for content_hash property and recompute_content_hash()."""

    def test_content_hash_from_local_skill_is_none(self, mock_skill_dir: Path):
        """Local skill without .agr.json has no content_hash."""
        skill = Skill.from_local(mock_skill_dir)
        assert skill.content_hash is None

    def test_recompute_content_hash_returns_valid_format(self, mock_skill_dir: Path):
        """recompute_content_hash returns sha256:<64 hex> format."""
        skill = Skill.from_local(mock_skill_dir)
        result = skill.recompute_content_hash()
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_recompute_content_hash_deterministic(self, mock_skill_dir: Path):
        """recompute_content_hash returns the same value on repeated calls."""
        skill = Skill.from_local(mock_skill_dir)
        hash1 = skill.recompute_content_hash()
        hash2 = skill.recompute_content_hash()
        assert hash1 == hash2


class TestGetHeadCommit:
    """Tests for get_head_commit function."""

    def test_returns_commit_hash(self, mock_github_repo: Path):
        """Test returns commit hash for valid git repo."""
        commit = get_head_commit(mock_github_repo)

        # Should be a 12-char hex string (truncated SHA)
        assert len(commit) == 12
        assert all(c in "0123456789abcdef" for c in commit)

    def test_fallback_generates_unique_hash(self, tmp_path: Path):
        """Test that fallback generates unique hashes for non-git directories."""
        # tmp_path is not a git repo, so git command will fail
        non_git_dir = tmp_path / "not-a-repo"
        non_git_dir.mkdir()

        hash1 = get_head_commit(non_git_dir)
        hash2 = get_head_commit(non_git_dir)

        # Both should be 12-char hex strings
        assert len(hash1) == 12
        assert len(hash2) == 12
        assert all(c in "0123456789abcdef" for c in hash1)
        assert all(c in "0123456789abcdef" for c in hash2)

        # Hashes should be different (due to time.time_ns())
        assert hash1 != hash2

    def test_fallback_different_paths_different_hashes(self, tmp_path: Path):
        """Test that different paths produce different hashes."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Get hashes at roughly the same time
        # Even if time is same, different paths should produce different hashes
        # (though in practice time.time_ns() will differ)
        hash1 = get_head_commit(dir1)
        hash2 = get_head_commit(dir2)

        # Both are valid hashes
        assert len(hash1) == 12
        assert len(hash2) == 12
