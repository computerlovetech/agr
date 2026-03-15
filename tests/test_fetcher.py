"""Tests for agr.fetcher module."""

from pathlib import Path
import shutil
import subprocess

import pytest

from agr.exceptions import (
    AgrError,
    AuthenticationError,
    RepoNotFoundError,
    SkillNotFoundError,
)
from agr.fetcher import (
    _cleanup_empty_parents,
    fetch_and_install_to_tools,
    get_installed_skills,
    install_local_skill,
    install_skill_from_repo,
    is_skill_installed,
    list_remote_repo_skills,
    uninstall_skill,
)
from agr.git import get_github_token, downloaded_repo
from agr.handle import ParsedHandle
from agr.metadata import build_handle_id, read_skill_metadata
from agr.source import SourceConfig
from agr.skill import SKILL_MARKER
from agr.tool import CLAUDE, CURSOR


class TestGitAuthentication:
    """Tests for GitHub token handling."""

    def test_get_github_token_returns_value(self, monkeypatch):
        """Token is returned when GITHUB_TOKEN is set."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert get_github_token() == "ghp_test123"

    def test_get_github_token_returns_none_when_unset(self, monkeypatch):
        """None returned when no token env vars are set."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert get_github_token() is None

    def test_get_github_token_prefers_github_token(self, monkeypatch):
        """GITHUB_TOKEN takes precedence over GH_TOKEN."""
        monkeypatch.setenv("GITHUB_TOKEN", "primary")
        monkeypatch.setenv("GH_TOKEN", "fallback")
        assert get_github_token() == "primary"

    def test_get_github_token_falls_back_to_gh_token(self, monkeypatch):
        """GH_TOKEN used when GITHUB_TOKEN is not set."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "fallback")
        assert get_github_token() == "fallback"


class TestDownloadedRepoE2E:
    """Tests for downloaded_repo context manager."""

    def test_git_missing_raises(self, monkeypatch):
        """Missing git raises AgrError."""
        monkeypatch.setattr(shutil, "which", lambda _: None)
        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with pytest.raises(AgrError, match="git CLI not found"):
            with downloaded_repo(source, "user", "repo"):
                pass

    def test_git_clone_success(self, monkeypatch, tmp_path):
        """Successful clone yields repo dir."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")

        def fake_run(cmd, capture_output, text, check):
            if cmd[:2] == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "ref: refs/heads/main\tHEAD\n", ""
                )
            repo_path = Path(cmd[-1])
            repo_path.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with downloaded_repo(source, "user", "repo") as repo_dir:
            assert repo_dir.exists()

    def test_git_clone_uses_default_branch(self, monkeypatch):
        """Clone uses the detected default branch when available."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")
        calls: list[list[str]] = []

        def fake_run(cmd, capture_output, text, check):
            calls.append(cmd)
            if cmd[:2] == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "ref: refs/heads/master\tHEAD\n", ""
                )
            repo_path = Path(cmd[-1])
            repo_path.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with downloaded_repo(source, "user", "repo") as repo_dir:
            assert repo_dir.exists()

        clone_calls = [call for call in calls if call[:2] == ["git", "clone"]]
        assert clone_calls, "Expected a git clone call"
        assert "--branch" in clone_calls[0]
        assert "master" in clone_calls[0]

    def test_git_clone_falls_back_when_partial_unsupported(self, monkeypatch):
        """Fallback to full clone when partial clone is unsupported."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")
        calls: list[list[str]] = []

        def fake_run(cmd, capture_output, text, check):
            calls.append(cmd)
            if cmd[:2] == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "ref: refs/heads/main\tHEAD\n", ""
                )
            repo_path = Path(cmd[-1])
            if "--filter=blob:none" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 1, "", "unknown option `--filter`"
                )
            repo_path.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with downloaded_repo(source, "user", "repo") as repo_dir:
            assert repo_dir.exists()

        assert len(calls) == 3
        assert calls[0][:2] == ["git", "ls-remote"]
        assert "--filter=blob:none" in calls[1]
        assert "--filter=blob:none" not in calls[2]

    def test_git_clone_not_found(self, monkeypatch):
        """Repository not found errors are classified."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")

        def fake_run(cmd, capture_output, text, check):
            return subprocess.CompletedProcess(
                cmd, 1, "", "fatal: repository not found"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with pytest.raises(RepoNotFoundError):
            with downloaded_repo(source, "user", "repo"):
                pass

    def test_git_clone_auth_failure(self, monkeypatch):
        """Authentication failures are classified."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")

        def fake_run(cmd, capture_output, text, check):
            return subprocess.CompletedProcess(
                cmd, 1, "", "fatal: Authentication failed"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with pytest.raises(AuthenticationError):
            with downloaded_repo(source, "user", "repo"):
                pass


class TestListRemoteRepoSkills:
    """Tests for list_remote_repo_skills function."""

    def test_returns_skills_from_repo(self, monkeypatch):
        """Lists skills found in a cloned repo."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")

        def fake_run(cmd, capture_output, text, check):
            if cmd[:2] == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "ref: refs/heads/main\tHEAD\n", ""
                )
            # git clone
            if cmd[1] == "clone":
                repo_path = Path(cmd[-1])
                repo_path.mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            # git ls-tree (list files)
            if "ls-tree" in cmd:
                files = "skills/alpha/SKILL.md\nskills/beta/SKILL.md\nREADME.md\n"
                return subprocess.CompletedProcess(cmd, 0, files, "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)

        skills = list_remote_repo_skills("owner", "repo")
        assert skills == ["alpha", "beta"]

    def test_returns_empty_for_nonexistent_repo(self, monkeypatch):
        """Returns empty list when repo doesn't exist."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")

        def fake_run(cmd, capture_output, text, check):
            return subprocess.CompletedProcess(
                cmd, 1, "", "fatal: repository not found"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        skills = list_remote_repo_skills("nonexistent", "repo")
        assert skills == []

    def test_returns_empty_for_repo_without_skills(self, monkeypatch):
        """Returns empty list when repo has no skills."""
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")

        def fake_run(cmd, capture_output, text, check):
            if cmd[:2] == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "ref: refs/heads/main\tHEAD\n", ""
                )
            if cmd[1] == "clone":
                repo_path = Path(cmd[-1])
                repo_path.mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if "ls-tree" in cmd:
                files = "README.md\nsrc/main.py\n"
                return subprocess.CompletedProcess(cmd, 0, files, "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)

        skills = list_remote_repo_skills("owner", "repo")
        assert skills == []


class TestInstallLocalSkill:
    """Tests for install_local_skill function."""

    def test_install_valid_skill(self, tmp_path, skill_fixture):
        """Install a valid local skill."""
        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        installed_path = install_local_skill(skill_fixture, dest_dir, CLAUDE)

        assert installed_path.exists()
        assert (installed_path / SKILL_MARKER).exists()
        assert installed_path.name == skill_fixture.name

    def test_install_invalid_skill_raises(self, tmp_path):
        """Installing directory without SKILL.md raises."""
        source_dir = tmp_path / "not-a-skill"
        source_dir.mkdir()
        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        with pytest.raises(SkillNotFoundError, match="not a valid skill"):
            install_local_skill(source_dir, dest_dir, CLAUDE)

    def test_install_existing_raises(self, tmp_path, skill_fixture):
        """Installing to existing location raises without overwrite."""
        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        # Install once
        install_local_skill(skill_fixture, dest_dir, CLAUDE)

        # Install again should raise
        with pytest.raises(FileExistsError):
            install_local_skill(skill_fixture, dest_dir, CLAUDE)

    def test_install_with_overwrite(self, tmp_path, skill_fixture):
        """Overwrite flag allows reinstalling."""
        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        # Install twice with overwrite
        install_local_skill(skill_fixture, dest_dir, CLAUDE)
        installed_path = install_local_skill(
            skill_fixture, dest_dir, CLAUDE, overwrite=True
        )

        assert installed_path.exists()

    def test_install_rejects_separator_in_name(self, tmp_path):
        """Installing skill with reserved separator in name raises."""
        from agr.skill import SKILL_MARKER

        # Create a skill with -- in its name
        bad_skill = tmp_path / "my--bad--skill"
        bad_skill.mkdir()
        (bad_skill / SKILL_MARKER).write_text("# Bad Skill")

        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        with pytest.raises(AgrError, match="contains reserved sequence"):
            install_local_skill(bad_skill, dest_dir, CLAUDE)

    def test_local_collision_raises(self, tmp_path):
        """Second local skill with same name raises."""
        from agr.skill import SKILL_MARKER

        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        # Create two skills with the same directory name in different locations
        skill_a = tmp_path / "a" / "test-skill"
        skill_b = tmp_path / "b" / "test-skill"
        skill_a.mkdir(parents=True)
        skill_b.mkdir(parents=True)
        (skill_a / SKILL_MARKER).write_text("# Skill A")
        (skill_b / SKILL_MARKER).write_text("# Skill B")

        install_local_skill(skill_a, dest_dir, CLAUDE)
        with pytest.raises(AgrError, match="only one local skill"):
            install_local_skill(skill_b, dest_dir, CLAUDE)


class TestUninstallSkill:
    """Tests for uninstall_skill function."""

    def test_uninstall_existing(self, tmp_path, skill_fixture):
        """Uninstall an existing skill."""
        # Set up repo structure
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        # Install skill
        installed_path = install_local_skill(skill_fixture, skills_dir, CLAUDE)

        # Create handle for uninstall
        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )

        # Uninstall
        removed = uninstall_skill(handle, repo_root, CLAUDE)

        assert removed
        assert not installed_path.exists()

    def test_uninstall_nonexistent(self, tmp_path):
        """Uninstalling nonexistent returns False."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(is_local=True, name="nonexistent-skill")
        removed = uninstall_skill(handle, repo_root, CLAUDE)
        assert not removed


class TestMetadataMatching:
    """Tests for metadata-based matching on flat tools."""

    def _create_repo_with_skill(self, base_dir: Path, name: str, label: str) -> Path:
        repo_dir = base_dir / f"repo-{label}-{name}"
        skill_dir = repo_dir / name
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MARKER).write_text("# Test skill")
        return repo_dir

    def test_metadata_written_and_used_for_matching(self, tmp_path):
        """Metadata ensures handles match the correct flat install."""
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        repo_dir = self._create_repo_with_skill(tmp_path, "test-skill", "single")
        handle = ParsedHandle(username="alpha", name="test-skill")

        installed = install_skill_from_repo(
            repo_dir,
            "test-skill",
            handle,
            skills_dir,
            CLAUDE,
            repo_root,
            install_source="github",
        )

        meta = read_skill_metadata(installed)
        assert meta is not None
        assert meta["id"] == build_handle_id(handle, repo_root, "github")
        assert is_skill_installed(handle, repo_root, CLAUDE, "github")

    def test_flat_collision_uses_full_name_and_metadata(self, tmp_path):
        """Second handle with same name installs to full handle name."""
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        repo_a = self._create_repo_with_skill(tmp_path, "test-skill", "a")
        handle_a = ParsedHandle(username="alpha", name="test-skill")
        install_skill_from_repo(
            repo_a,
            "test-skill",
            handle_a,
            skills_dir,
            CLAUDE,
            repo_root,
            install_source="github",
        )

        handle_b = ParsedHandle(username="bravo", name="test-skill")
        assert not is_skill_installed(handle_b, repo_root, CLAUDE)

        repo_b = self._create_repo_with_skill(tmp_path, "test-skill", "b")
        installed_b = install_skill_from_repo(
            repo_b,
            "test-skill",
            handle_b,
            skills_dir,
            CLAUDE,
            repo_root,
            install_source="github",
        )

        assert installed_b.name == handle_b.to_installed_name()
        assert (skills_dir / "test-skill").exists()
        assert (skills_dir / handle_b.to_installed_name()).exists()

        meta_b = read_skill_metadata(installed_b)
        assert meta_b is not None
        assert meta_b["id"] == build_handle_id(handle_b, repo_root, "github")

        assert uninstall_skill(handle_b, repo_root, CLAUDE, "github") is True
        assert not (skills_dir / handle_b.to_installed_name()).exists()
        assert (skills_dir / "test-skill").exists()


class TestGetInstalledSkills:
    """Tests for get_installed_skills function."""

    def test_no_skills_dir(self, tmp_path):
        """Returns empty list when skills dir doesn't exist."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        skills = get_installed_skills(repo_root, CLAUDE)
        assert skills == []

    def test_with_skills(self, tmp_path, skill_fixture):
        """Returns list of installed skill names."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        install_local_skill(skill_fixture, skills_dir, CLAUDE)

        skills = get_installed_skills(repo_root, CLAUDE)
        assert len(skills) == 1
        assert skills[0] == skill_fixture.name


class TestIsSkillInstalled:
    """Tests for is_skill_installed function."""

    def test_installed(self, tmp_path, skill_fixture):
        """Returns True for installed skill."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        install_local_skill(skill_fixture, skills_dir, CLAUDE)

        # Create handle for checking
        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )
        assert is_skill_installed(handle, repo_root, CLAUDE)

    def test_not_installed(self, tmp_path):
        """Returns False for non-installed skill."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(is_local=True, name="nonexistent-skill")
        assert not is_skill_installed(handle, repo_root, CLAUDE)


class TestDownloadedRepo:
    """Tests for downloaded_repo context manager.

    These are E2E tests that require network access.
    """

    @pytest.mark.e2e
    def test_download_existing_repo(self):
        """Download a real repository."""
        from agr.git import downloaded_repo
        from agr.source import SourceConfig
        import subprocess

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with downloaded_repo(source, "kasperjunge", "agent-resources") as repo_dir:
            assert repo_dir.exists()
            result = subprocess.run(
                ["git", "-C", str(repo_dir), "ls-tree", "-r", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0
            files = set(result.stdout.splitlines())
            assert "pyproject.toml" in files or "agr.toml" in files

    @pytest.mark.e2e
    def test_download_nonexistent_raises(self):
        """Downloading nonexistent repo raises."""
        from agr.exceptions import RepoNotFoundError
        from agr.git import downloaded_repo
        from agr.source import SourceConfig

        source = SourceConfig(
            name="github",
            type="git",
            url="https://github.com/{owner}/{repo}.git",
        )
        with pytest.raises(RepoNotFoundError):
            with downloaded_repo(
                source, "nonexistent-user-12345", "nonexistent-repo-67890"
            ):
                pass


class TestCleanupEmptyParents:
    """Tests for _cleanup_empty_parents function."""

    def test_stops_at_boundary(self, tmp_path):
        """Doesn't delete beyond stop_at."""
        stop_at = tmp_path / "skills"
        stop_at.mkdir()
        nested = stop_at / "a" / "b" / "c"
        nested.mkdir(parents=True)

        # Clean up nested empty dirs
        _cleanup_empty_parents(nested, stop_at)

        # All empty dirs within stop_at should be removed
        assert not (stop_at / "a").exists()
        # But stop_at itself should remain
        assert stop_at.exists()

    def test_handles_non_empty_dir(self, tmp_path):
        """Stops at non-empty directories."""
        stop_at = tmp_path / "skills"
        stop_at.mkdir()
        nested = stop_at / "a" / "b"
        nested.mkdir(parents=True)
        # Put a file in "a"
        (stop_at / "a" / "file.txt").write_text("content")

        _cleanup_empty_parents(nested, stop_at)

        # "b" should be removed but "a" should remain (has file)
        assert not (stop_at / "a" / "b").exists()
        assert (stop_at / "a").exists()
        assert (stop_at / "a" / "file.txt").exists()

    def test_handles_symlinks(self, tmp_path):
        """Resolves symlinks before comparison."""
        stop_at = tmp_path / "skills"
        stop_at.mkdir()
        nested = stop_at / "a" / "b"
        nested.mkdir(parents=True)

        # Create a symlink to the skills dir
        symlink = tmp_path / "skills_link"
        symlink.symlink_to(stop_at)

        # Use symlink path
        nested_via_link = symlink / "a" / "b"

        _cleanup_empty_parents(nested_via_link, symlink)

        # Should still clean up properly
        assert not (stop_at / "a").exists()
        assert stop_at.exists()


class TestContentHashOnInstall:
    """Tests that content_hash is written during installation."""

    def _create_repo_with_skill(self, base_dir: Path, name: str) -> Path:
        repo_dir = base_dir / f"repo-{name}"
        skill_dir = repo_dir / name
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MARKER).write_text("# Test skill")
        return repo_dir

    def test_install_local_skill_writes_content_hash(self, tmp_path, skill_fixture):
        """Local skill installation writes a content_hash to .agr.json."""
        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        installed_path = install_local_skill(skill_fixture, dest_dir, CLAUDE)

        meta = read_skill_metadata(installed_path)
        assert meta is not None
        assert "content_hash" in meta
        assert meta["content_hash"].startswith("sha256:")
        assert len(meta["content_hash"]) == 7 + 64  # "sha256:" + 64 hex

    def test_install_local_skill_hash_matches_recomputation(
        self, tmp_path, skill_fixture
    ):
        """Stored content_hash matches a fresh recomputation."""
        from agr.metadata import compute_content_hash

        dest_dir = tmp_path / ".claude" / "skills"
        dest_dir.mkdir(parents=True)

        installed_path = install_local_skill(skill_fixture, dest_dir, CLAUDE)

        meta = read_skill_metadata(installed_path)
        assert meta is not None
        assert meta["content_hash"] == compute_content_hash(installed_path)

    def test_install_inplace_skill_writes_content_hash(self, tmp_path):
        """In-place local skill (source == dest) writes content_hash."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        # Create skill directly at its destination
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / SKILL_MARKER).write_text("# My Skill")

        handle = ParsedHandle(is_local=True, name="my-skill", local_path=skill_dir)
        installed = install_local_skill(
            skill_dir, skills_dir, CLAUDE, repo_root=repo_root, handle=handle
        )

        meta = read_skill_metadata(installed)
        assert meta is not None
        assert "content_hash" in meta
        assert meta["content_hash"].startswith("sha256:")

    def test_install_remote_skill_writes_content_hash(self, tmp_path):
        """Remote skill installation writes a content_hash to .agr.json."""
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        skills_dir = repo_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        repo_dir = self._create_repo_with_skill(tmp_path, "test-skill")
        handle = ParsedHandle(username="alpha", name="test-skill")

        installed = install_skill_from_repo(
            repo_dir,
            "test-skill",
            handle,
            skills_dir,
            CLAUDE,
            repo_root,
            install_source="github",
        )

        meta = read_skill_metadata(installed)
        assert meta is not None
        assert "content_hash" in meta
        assert meta["content_hash"].startswith("sha256:")
        assert len(meta["content_hash"]) == 7 + 64


class TestFetchAndInstallToTools:
    """Tests for fetch_and_install_to_tools function."""

    def test_local_skill_to_multiple_tools(self, tmp_path, skill_fixture):
        """Local skill installs to multiple tools."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )

        results = fetch_and_install_to_tools(
            handle, repo_root, [CLAUDE, CURSOR], overwrite=False
        )

        assert "claude" in results
        assert "cursor" in results
        assert results["claude"].exists()
        assert results["cursor"].exists()
        # Claude uses flat naming (default skill name)
        assert results["claude"].name == skill_fixture.name
        # Cursor uses nested directories
        assert results["cursor"].parent.name == "local"

    def test_rollback_on_partial_failure(self, tmp_path, skill_fixture):
        """If second tool fails, first tool installation is rolled back."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        # Pre-install to cursor so it will fail without overwrite
        cursor_skills = repo_root / ".cursor" / "skills" / "local"
        cursor_skills.mkdir(parents=True)
        (cursor_skills / skill_fixture.name).mkdir()
        (cursor_skills / skill_fixture.name / "SKILL.md").write_text("# existing")

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )

        # This should fail on cursor (file exists) and rollback claude
        with pytest.raises(FileExistsError):
            fetch_and_install_to_tools(
                handle, repo_root, [CLAUDE, CURSOR], overwrite=False
            )

        # Claude installation should be rolled back
        claude_path = repo_root / ".claude" / "skills" / skill_fixture.name
        assert not claude_path.exists()

    def test_empty_tools_list_raises(self, tmp_path, skill_fixture):
        """Empty tools list raises ValueError."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        handle = ParsedHandle(
            is_local=True, name=skill_fixture.name, local_path=skill_fixture
        )

        with pytest.raises(ValueError, match="No tools provided"):
            fetch_and_install_to_tools(handle, repo_root, [], overwrite=False)
