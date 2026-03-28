"""Tests for cache module."""

import importlib
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from agr.exceptions import CacheError
from agr.sdk.cache import (
    _sanitize_path_component,
    cache,
    cache_skill,
    clear_cache,
    get_cache_dir,
    get_skill_cache_path,
    is_cached,
)

cache_module = importlib.import_module("agr.sdk.cache")


class TestGetCacheDir:
    """Tests for get_cache_dir()."""

    def test_returns_home_cache_agr(self):
        """Test cache dir is ~/.cache/agr."""
        cache_dir = get_cache_dir()
        assert cache_dir == Path.home() / ".cache" / "agr"


class TestSanitizePathComponent:
    """Tests for _sanitize_path_component()."""

    def test_valid_component(self):
        """Test that valid components pass through."""
        assert _sanitize_path_component("owner", "owner") == "owner"
        assert _sanitize_path_component("my-repo", "repo") == "my-repo"
        assert _sanitize_path_component("skill_v2", "skill") == "skill_v2"
        assert _sanitize_path_component("abc123", "revision") == "abc123"
        assert _sanitize_path_component("v1.2.3", "version") == "v1.2.3"

    def test_empty_component_rejected(self):
        """Test that empty components are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _sanitize_path_component("", "owner")

    def test_null_byte_rejected(self):
        """Test that null bytes are rejected."""
        with pytest.raises(ValueError, match="cannot contain null bytes"):
            _sanitize_path_component("owner\x00evil", "owner")

    def test_path_traversal_rejected(self):
        """Test that path traversal is rejected."""
        with pytest.raises(ValueError, match="cannot contain '..'"):
            _sanitize_path_component("..", "owner")
        with pytest.raises(ValueError, match="cannot contain '..'"):
            _sanitize_path_component("../evil", "owner")
        # "owner/../evil" is caught by the path separator check (/)
        # rather than the '..' check, but it's still rejected
        with pytest.raises(ValueError):
            _sanitize_path_component("owner/../evil", "owner")

    def test_consecutive_dots_in_valid_name_accepted(self):
        """Test that names containing '..' as a substring are accepted.

        GitHub allows consecutive dots in repo names (e.g., 'v2..rc1').
        The path traversal check should only reject the literal '..'
        component, not any name that happens to contain consecutive dots.
        Since path separators are already blocked, embedded '..' in a
        name cannot cause traversal.
        """
        assert _sanitize_path_component("v2..rc1", "repo") == "v2..rc1"
        assert _sanitize_path_component("a..b", "repo") == "a..b"
        assert _sanitize_path_component("test..name", "repo") == "test..name"

    def test_path_separators_rejected(self):
        """Test that path separators are rejected."""
        with pytest.raises(ValueError, match="cannot contain path separators"):
            _sanitize_path_component("owner/evil", "owner")
        with pytest.raises(ValueError, match="cannot contain path separators"):
            _sanitize_path_component("owner\\evil", "owner")

    def test_invalid_characters_rejected(self):
        """Test that invalid characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            _sanitize_path_component("owner$evil", "owner")
        with pytest.raises(ValueError, match="invalid characters"):
            _sanitize_path_component("owner evil", "owner")  # space
        with pytest.raises(ValueError, match="invalid characters"):
            _sanitize_path_component("owner:evil", "owner")  # colon


class TestGetSkillCachePath:
    """Tests for get_skill_cache_path()."""

    def test_returns_correct_path(self):
        """Test cache path structure."""
        path = get_skill_cache_path("owner", "repo", "skill", "abc123")

        expected = (
            Path.home()
            / ".cache"
            / "agr"
            / "skills"
            / "github"
            / "owner"
            / "repo"
            / "skill"
            / "abc123"
        )
        assert path == expected

    def test_rejects_path_traversal(self):
        """Test that path traversal in any component is rejected."""
        with pytest.raises(ValueError):
            get_skill_cache_path("../evil", "repo", "skill", "abc123")
        with pytest.raises(ValueError):
            get_skill_cache_path("owner", "../evil", "skill", "abc123")
        with pytest.raises(ValueError):
            get_skill_cache_path("owner", "repo", "../evil", "abc123")
        with pytest.raises(ValueError):
            get_skill_cache_path("owner", "repo", "skill", "../evil")

    def test_rejects_null_bytes(self):
        """Test that null bytes in any component are rejected."""
        with pytest.raises(ValueError):
            get_skill_cache_path("owner\x00evil", "repo", "skill", "abc123")


class TestIsCached:
    """Tests for is_cached()."""

    def test_returns_false_when_not_cached(self, tmp_path: Path):
        """Test returns False when skill not in cache."""
        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            assert is_cached("owner", "repo", "skill", "abc123") is False

    def test_returns_true_when_cached(self, tmp_path: Path):
        """Test returns True when skill is cached."""
        # Create cached skill
        skill_path = (
            tmp_path / "skills" / "github" / "owner" / "repo" / "skill" / "abc123"
        )
        skill_path.mkdir(parents=True)
        (skill_path / "SKILL.md").write_text("# Skill")

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            assert is_cached("owner", "repo", "skill", "abc123") is True

    def test_returns_false_when_missing_skill_md(self, tmp_path: Path):
        """Test returns False when directory exists but SKILL.md missing."""
        skill_path = (
            tmp_path / "skills" / "github" / "owner" / "repo" / "skill" / "abc123"
        )
        skill_path.mkdir(parents=True)

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            assert is_cached("owner", "repo", "skill", "abc123") is False


class TestCacheSkill:
    """Tests for cache_skill()."""

    def test_caches_skill_atomically(self, tmp_path: Path, mock_skill_dir: Path):
        """Test that skill is cached."""
        cache_base = tmp_path / "cache"
        cache_base.mkdir()

        with patch("agr.sdk.cache.get_cache_dir", return_value=cache_base):
            result = cache_skill(mock_skill_dir, "owner", "repo", "skill", "abc123")

            assert result.exists()
            assert (result / "SKILL.md").exists()
            assert "owner" in str(result)
            assert "repo" in str(result)

    def test_returns_existing_cache(self, tmp_path: Path, mock_skill_dir: Path):
        """Test returns existing cache without re-copying."""
        cache_base = tmp_path / "cache"

        # Pre-create cache
        cached = (
            cache_base / "skills" / "github" / "owner" / "repo" / "skill" / "abc123"
        )
        cached.mkdir(parents=True)
        (cached / "SKILL.md").write_text("# Already cached")

        with patch("agr.sdk.cache.get_cache_dir", return_value=cache_base):
            result = cache_skill(mock_skill_dir, "owner", "repo", "skill", "abc123")

            # Should return existing, not overwrite
            assert (result / "SKILL.md").read_text() == "# Already cached"

    def test_raises_cache_error_on_failure(self, tmp_path: Path, mock_skill_dir: Path):
        """Test raises CacheError on failure."""
        cache_base = tmp_path / "cache"

        # Make a file where a directory should be created to cause failure
        cache_base.mkdir()
        blocking_file = cache_base / "skills"
        blocking_file.write_text("blocking")  # File instead of directory

        with (
            patch("agr.sdk.cache.get_cache_dir", return_value=cache_base),
            pytest.raises(CacheError),
        ):
            cache_skill(mock_skill_dir, "owner", "repo", "skill", "abc123")


class TestFileLocking:
    """Tests for platform lock backend wrappers."""

    def test_windows_lock_backend(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Windows backend uses msvcrt.locking."""

        class DummyMsvcrt:
            LK_LOCK = 1
            LK_UNLCK = 2

            def __init__(self):
                self.calls: list[tuple[int, int, int]] = []

            def locking(self, fileno: int, mode: int, size: int) -> None:
                self.calls.append((fileno, mode, size))

        dummy = DummyMsvcrt()
        monkeypatch.setattr(cache_module, "_LOCKS_USE_MSVCRT", True)
        monkeypatch.setattr(cache_module, "_msvcrt", dummy)
        monkeypatch.setattr(cache_module, "_fcntl", None)

        lock_file = tmp_path / "lockfile"
        with lock_file.open("w+") as lock_fd:
            cache_module._acquire_file_lock(lock_fd)
            cache_module._release_file_lock(lock_fd)

        assert len(dummy.calls) == 2
        assert dummy.calls[0][1] == dummy.LK_LOCK
        assert dummy.calls[0][2] == 1
        assert dummy.calls[1][1] == dummy.LK_UNLCK
        assert dummy.calls[1][2] == 1

    def test_posix_lock_backend(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """POSIX backend uses fcntl.flock."""

        class DummyFcntl:
            LOCK_EX = 1
            LOCK_UN = 2

            def __init__(self):
                self.calls: list[tuple[int, int]] = []

            def flock(self, fileno: int, mode: int) -> None:
                self.calls.append((fileno, mode))

        dummy = DummyFcntl()
        monkeypatch.setattr(cache_module, "_LOCKS_USE_MSVCRT", False)
        monkeypatch.setattr(cache_module, "_fcntl", dummy)
        monkeypatch.setattr(cache_module, "_msvcrt", None)

        lock_file = tmp_path / "lockfile"
        with lock_file.open("w+") as lock_fd:
            cache_module._acquire_file_lock(lock_fd)
            cache_module._release_file_lock(lock_fd)

        assert len(dummy.calls) == 2
        assert dummy.calls[0][1] == dummy.LOCK_EX
        assert dummy.calls[1][1] == dummy.LOCK_UN


class TestClearCache:
    """Tests for clear_cache()."""

    def test_clear_all(self, tmp_path: Path):
        """Test clearing all cache."""
        # Create multiple cached skills
        for i in range(3):
            skill_path = (
                tmp_path / "skills" / "github" / "owner" / "repo" / f"skill{i}" / "abc"
            )
            skill_path.mkdir(parents=True)
            (skill_path / "SKILL.md").write_text(f"# Skill {i}")

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            count = clear_cache()

            assert count == 3
            # Skills dir should be empty of skill directories
            github_dir = tmp_path / "skills" / "github" / "owner" / "repo"
            remaining = [d for d in github_dir.iterdir() if d.is_dir()]
            assert len(remaining) == 0

    def test_clear_with_pattern(self, tmp_path: Path):
        """Test clearing cache with pattern."""
        # Create skills from different owners
        for owner in ["owner1", "owner2"]:
            skill_path = (
                tmp_path / "skills" / "github" / owner / "repo" / "skill" / "abc"
            )
            skill_path.mkdir(parents=True)
            (skill_path / "SKILL.md").write_text("# Skill")

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            count = clear_cache("owner1/*")

            assert count == 1
            # owner1's skill should be gone
            assert not (
                tmp_path / "skills" / "github" / "owner1" / "repo" / "skill" / "abc"
            ).exists()
            # owner2's skill should remain
            assert (
                tmp_path / "skills" / "github" / "owner2" / "repo" / "skill" / "abc"
            ).exists()

    def test_clear_empty_cache(self, tmp_path: Path):
        """Test clearing empty cache."""
        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            count = clear_cache()
            assert count == 0


class TestCacheManager:
    """Tests for _CacheManager class."""

    def test_path_property(self):
        """Test path property returns cache dir."""
        assert cache.path == get_cache_dir()

    def test_info_empty_cache(self, tmp_path: Path):
        """Test info on empty cache."""
        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            info = cache.info()

            assert info["path"] == str(tmp_path)
            assert info["skills_count"] == 0
            assert info["size_bytes"] == 0

    def test_info_with_skills(self, tmp_path: Path):
        """Test info with cached skills."""
        # Create cached skill
        skill_path = tmp_path / "skills" / "github" / "owner" / "repo" / "skill" / "abc"
        skill_path.mkdir(parents=True)
        (skill_path / "SKILL.md").write_text("# Skill content here")

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            info = cache.info()

            assert info["skills_count"] == 1
            assert info["size_bytes"] > 0

    def test_info_counts_skills_not_revisions(self, tmp_path: Path):
        """Test that info() counts unique skills, not individual revisions.

        When one skill has multiple cached revisions, info() should report
        it as 1 cached skill (consistent with clear_cache which deletes
        at the skill level).
        """
        # Create one skill cached at two different revisions
        base = tmp_path / "skills" / "github" / "owner" / "repo" / "skill"
        rev1 = base / "abc123"
        rev1.mkdir(parents=True)
        (rev1 / "SKILL.md").write_text("# Skill rev 1")

        rev2 = base / "def456"
        rev2.mkdir(parents=True)
        (rev2 / "SKILL.md").write_text("# Skill rev 2")

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            info = cache.info()
            # Should count 1 skill, not 2 revisions
            assert info["skills_count"] == 1

            # clear() also reports 1 — they should be consistent
            count = cache.clear()
            assert count == 1

    def test_clear_method(self, tmp_path: Path):
        """Test clear method delegates to clear_cache."""
        skill_path = tmp_path / "skills" / "github" / "owner" / "repo" / "skill" / "abc"
        skill_path.mkdir(parents=True)
        (skill_path / "SKILL.md").write_text("# Skill")

        with patch("agr.sdk.cache.get_cache_dir", return_value=tmp_path):
            count = cache.clear()
            assert count == 1


class TestCacheRaceCondition:
    """Tests for race condition handling in cache_skill()."""

    def test_concurrent_cache_writes(self, tmp_path: Path, mock_skill_dir: Path):
        """Test that concurrent cache writes don't corrupt or fail.

        Multiple threads trying to cache the same skill should all succeed,
        with one doing the actual write and others using the cached result.
        """
        cache_base = tmp_path / "cache"
        cache_base.mkdir()

        results = []
        errors = []

        def cache_worker():
            try:
                with patch("agr.sdk.cache.get_cache_dir", return_value=cache_base):
                    result = cache_skill(
                        mock_skill_dir, "owner", "repo", "skill", "abc123"
                    )
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Launch multiple threads simultaneously
        threads = [threading.Thread(target=cache_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All results should be the same path
        assert len(results) == 10
        assert all(r == results[0] for r in results)

        # The cached skill should exist and be valid
        cached = results[0]
        assert cached.exists()
        assert (cached / "SKILL.md").exists()

    def test_double_check_pattern(self, tmp_path: Path, mock_skill_dir: Path):
        """Test that the double-check pattern prevents redundant copies.

        When cache already exists, we should get it immediately without
        re-copying.
        """
        cache_base = tmp_path / "cache"

        # Pre-create the cached skill
        cached = (
            cache_base / "skills" / "github" / "owner" / "repo" / "skill" / "abc123"
        )
        cached.mkdir(parents=True)
        (cached / "SKILL.md").write_text("# Already cached")
        (cached / "marker.txt").write_text("original")

        with patch("agr.sdk.cache.get_cache_dir", return_value=cache_base):
            result = cache_skill(mock_skill_dir, "owner", "repo", "skill", "abc123")

            # Should return existing cache, not overwrite
            assert (result / "SKILL.md").read_text() == "# Already cached"
            assert (result / "marker.txt").read_text() == "original"
