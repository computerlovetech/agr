"""Tests for agr.ralph_installer module (direct imports)."""

from unittest.mock import patch

import pytest

from agr.exceptions import RalphNotFoundError
from agr.handle import ParsedHandle
from agr.ralph import RALPH_MARKER
from agr.ralph_installer import (
    fetch_and_install_ralph,
    get_ralphs_dir,
    install_local_ralph,
    is_ralph_installed,
    ralph_not_found_message,
    uninstall_ralph,
)


class TestDirectImportSmoke:
    """Smoke tests verifying direct imports from agr.ralph_installer work."""

    def test_install_and_uninstall(self, tmp_path, ralph_fixture):
        """Install and uninstall a local ralph via direct imports."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        ralphs_dir = get_ralphs_dir(repo_root)
        ralphs_dir.mkdir(parents=True)

        path = install_local_ralph(ralph_fixture, ralphs_dir, repo_root=repo_root)
        assert path.exists()
        assert (path / RALPH_MARKER).exists()

        handle = ParsedHandle(
            is_local=True, name=ralph_fixture.name, local_path=ralph_fixture
        )
        assert is_ralph_installed(handle, repo_root)

        removed = uninstall_ralph(handle, repo_root)
        assert removed is True
        assert not path.exists()

    def test_install_invalid_raises(self, tmp_path):
        """Installing non-ralph raises RalphNotFoundError."""
        source = tmp_path / "not-a-ralph"
        source.mkdir()
        ralphs_dir = tmp_path / ".agents" / "ralphs"
        ralphs_dir.mkdir(parents=True)

        with pytest.raises(RalphNotFoundError):
            install_local_ralph(source, ralphs_dir)

    def test_ralph_not_found_message(self):
        msg = ralph_not_found_message("missing-ralph")
        assert "missing-ralph" in msg
        assert "RALPH.md" in msg


class TestGetRalphsDir:
    """Tests for get_ralphs_dir."""

    def test_returns_expected_path(self, tmp_path):
        result = get_ralphs_dir(tmp_path)
        assert result == tmp_path / ".agents" / "ralphs"


class TestFetchAndInstallRalphRollback:
    """Tests for rollback in fetch_and_install_ralph."""

    def test_rollback_on_content_hash_failure(self, tmp_path, ralph_fixture):
        """If compute_content_hash fails, installed ralph is cleaned up."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(username="user", repo="repo", name="test-ralph")

        with (
            patch("agr.ralph_installer._locate_remote_ralph") as mock_locate,
            patch("agr.ralph_installer.install_ralph_from_repo") as mock_install,
            patch(
                "agr.ralph_installer.compute_content_hash",
                side_effect=RuntimeError("hash failure"),
            ),
        ):
            installed_path = tmp_path / "installed-ralph"
            installed_path.mkdir()
            (installed_path / RALPH_MARKER).write_text("# test")
            mock_install.return_value = installed_path

            # Set up context manager mock
            mock_locate.return_value.__enter__ = lambda self: type(
                "Loc",
                (),
                {
                    "repo_dir": tmp_path,
                    "source_path": ralph_fixture,
                    "source_config": type("SC", (), {"name": "github"})(),
                    "is_legacy": False,
                    "commit": "abc123",
                    "resolved_repo": "skills",
                },
            )()
            mock_locate.return_value.__exit__ = lambda self, *args: False

            with pytest.raises(RuntimeError, match="hash failure"):
                fetch_and_install_ralph(handle, repo_root)

            # The installed path should be cleaned up by rollback
            assert not installed_path.exists()
