"""Tests for ralph discovery and validation."""

from pathlib import PurePosixPath

from agr.ralph import (
    RALPH_MARKER,
    discover_ralphs_in_repo_listing,
    find_ralph_in_repo,
    find_ralph_in_repo_listing,
    find_ralphs_in_repo_listing,
    is_valid_ralph_dir,
)


class TestIsValidRalphDir:
    def test_valid_ralph_dir(self, ralph_fixture):
        """Directory containing RALPH.md is valid."""
        assert is_valid_ralph_dir(ralph_fixture) is True

    def test_dir_without_ralph_md(self, tmp_path):
        """Directory without RALPH.md is invalid."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert is_valid_ralph_dir(empty_dir) is False

    def test_nonexistent_dir(self, tmp_path):
        """Non-existent path is invalid."""
        assert is_valid_ralph_dir(tmp_path / "nope") is False

    def test_file_not_dir(self, tmp_path):
        """File path is invalid."""
        f = tmp_path / "file.txt"
        f.write_text("hi")
        assert is_valid_ralph_dir(f) is False


class TestFindRalphInRepo:
    def test_finds_ralph(self, tmp_path):
        """Finds a ralph by directory name."""
        ralph_dir = tmp_path / "ralphs" / "my-ralph"
        ralph_dir.mkdir(parents=True)
        (ralph_dir / RALPH_MARKER).write_text("---\nagent: claude\n---\n")
        result = find_ralph_in_repo(tmp_path, "my-ralph")
        assert result == ralph_dir

    def test_returns_none_when_missing(self, tmp_path):
        """Returns None when ralph not found."""
        result = find_ralph_in_repo(tmp_path, "nope")
        assert result is None

    def test_excludes_root_level(self, tmp_path):
        """Root-level RALPH.md is not a ralph directory."""
        (tmp_path / RALPH_MARKER).write_text("---\nagent: claude\n---\n")
        # Need a subdirectory named same as root to check exclusion
        result = find_ralph_in_repo(tmp_path, tmp_path.name)
        assert result is None

    def test_excludes_git_dirs(self, tmp_path):
        """RALPH.md inside .git is excluded."""
        git_ralph = tmp_path / ".git" / "my-ralph"
        git_ralph.mkdir(parents=True)
        (git_ralph / RALPH_MARKER).write_text("---\nagent: claude\n---\n")
        result = find_ralph_in_repo(tmp_path, "my-ralph")
        assert result is None

    def test_prefers_shallowest(self, tmp_path):
        """When multiple matches, returns the shallowest."""
        shallow = tmp_path / "my-ralph"
        shallow.mkdir()
        (shallow / RALPH_MARKER).write_text("---\nagent: claude\n---\n")

        deep = tmp_path / "nested" / "deep" / "my-ralph"
        deep.mkdir(parents=True)
        (deep / RALPH_MARKER).write_text("---\nagent: claude\n---\n")

        result = find_ralph_in_repo(tmp_path, "my-ralph")
        assert result == shallow


class TestFindRalphInRepoListing:
    def test_finds_ralph(self):
        """Finds ralph in git listing."""
        paths = ["ralphs/my-ralph/RALPH.md", "README.md"]
        result = find_ralph_in_repo_listing(paths, "my-ralph")
        assert result == PurePosixPath("ralphs/my-ralph")

    def test_returns_none_when_missing(self):
        """Returns None when ralph not in listing."""
        paths = ["ralphs/other/RALPH.md"]
        result = find_ralph_in_repo_listing(paths, "my-ralph")
        assert result is None

    def test_excludes_root_level(self):
        """Root-level RALPH.md excluded."""
        paths = ["RALPH.md"]
        result = find_ralph_in_repo_listing(paths, "")
        assert result is None


class TestFindRalphsInRepoListing:
    def test_finds_multiple(self):
        """Finds multiple ralphs in one pass."""
        paths = [
            "ralphs/alpha/RALPH.md",
            "ralphs/beta/RALPH.md",
            "ralphs/gamma/RALPH.md",
        ]
        result = find_ralphs_in_repo_listing(paths, ["alpha", "gamma"])
        assert set(result.keys()) == {"alpha", "gamma"}
        assert result["alpha"] == PurePosixPath("ralphs/alpha")
        assert result["gamma"] == PurePosixPath("ralphs/gamma")

    def test_missing_ralphs_omitted(self):
        """Missing ralphs are not in result."""
        paths = ["ralphs/alpha/RALPH.md"]
        result = find_ralphs_in_repo_listing(paths, ["alpha", "missing"])
        assert set(result.keys()) == {"alpha"}


class TestDiscoverRalphsInRepoListing:
    def test_discovers_all(self):
        """Lists all ralph names sorted."""
        paths = [
            "ralphs/beta/RALPH.md",
            "ralphs/alpha/RALPH.md",
            "README.md",
            "RALPH.md",  # root-level — excluded
        ]
        result = discover_ralphs_in_repo_listing(paths)
        assert result == ["alpha", "beta"]

    def test_empty_listing(self):
        """Empty listing yields empty result."""
        assert discover_ralphs_in_repo_listing([]) == []
