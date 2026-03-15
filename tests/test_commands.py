"""Tests for agr.commands module (integration tests)."""

import sys

import pytest

from agr.commands.init import init_config, init_skill
from agr.commands.list import run_list
from agr.config import AgrConfig, Dependency
from agr.skill import SKILL_MARKER

# Windows doesn't allow colons in directory names
skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't allow colons in directory names"
)


class TestInitCommand:
    """Tests for init command."""

    def test_init_config_creates_file(self, tmp_path, monkeypatch):
        """init_config creates agr.toml."""
        monkeypatch.chdir(tmp_path)

        config_path, created = init_config()

        assert created
        assert config_path.exists()
        assert config_path.name == "agr.toml"

    def test_init_config_existing(self, tmp_path, monkeypatch):
        """init_config with existing file returns it."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        existing = tmp_path / "agr.toml"
        existing.write_text("dependencies = []")

        config_path, created = init_config()

        assert not created
        assert config_path == existing

    def test_init_skill_creates_scaffold(self, tmp_path, monkeypatch):
        """init_skill creates skill scaffold."""
        monkeypatch.chdir(tmp_path)

        skill_path = init_skill("my-skill")

        assert skill_path.exists()
        assert (skill_path / SKILL_MARKER).exists()

    def test_init_skill_invalid_name(self, tmp_path, monkeypatch):
        """init_skill with invalid name raises."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValueError):
            init_skill("-invalid")

    def test_init_skill_existing_dir(self, tmp_path, monkeypatch):
        """init_skill with existing directory raises."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "existing").mkdir()

        with pytest.raises(FileExistsError):
            init_skill("existing")


class TestListCommand:
    """Tests for list command."""

    def test_list_no_config(self, git_project, capsys):
        """list with no config prints message."""
        run_list()

        captured = capsys.readouterr()
        assert "No agr.toml found" in captured.out

    def test_list_empty_deps(self, git_project, capsys):
        """list with empty deps prints message."""
        config = AgrConfig()
        config.save(git_project / "agr.toml")

        run_list()

        captured = capsys.readouterr()
        assert "No dependencies" in captured.out

    def test_list_with_deps(self, git_project, capsys):
        """list with deps prints table."""
        config = AgrConfig()
        config.add_dependency(Dependency(type="skill", handle="user/skill"))
        config.save(git_project / "agr.toml")

        run_list()

        captured = capsys.readouterr()
        assert "user/skill" in captured.out


class TestAddRemoveCommands:
    """Tests for add and remove commands.

    These require network access for remote skills.
    """

    def test_add_local_skill(self, git_project, skill_fixture):
        """Add a local skill."""
        from agr.commands.add import run_add

        # Move skill fixture into the project
        import shutil

        local_skill = git_project / "my-skill"
        shutil.copytree(skill_fixture, local_skill)

        run_add(["./my-skill"])

        # Check config
        config = AgrConfig.load(git_project / "agr.toml")
        assert len(config.dependencies) == 1
        assert config.dependencies[0].path == "./my-skill"

        # Check installed
        installed_dir = git_project / ".claude" / "skills" / "my-skill"
        assert installed_dir.exists()

    def test_remove_local_skill(self, git_project, skill_fixture):
        """Remove a local skill."""
        from agr.commands.add import run_add
        from agr.commands.remove import run_remove

        # First add the skill
        import shutil

        local_skill = git_project / "my-skill"
        shutil.copytree(skill_fixture, local_skill)
        run_add(["./my-skill"])

        # Now remove it
        run_remove(["./my-skill"])

        # Check config
        config = AgrConfig.load(git_project / "agr.toml")
        assert len(config.dependencies) == 0

        # Check uninstalled
        installed_dir = git_project / ".claude" / "skills" / "my-skill"
        assert not installed_dir.exists()

    @pytest.mark.e2e
    def test_add_remote_skill(self, git_project):
        """Add a remote skill from GitHub."""
        from agr.commands.add import run_add

        run_add(["kasperjunge/migrate-to-skills"])

        # Check config
        config = AgrConfig.load(git_project / "agr.toml")
        assert len(config.dependencies) == 1
        assert config.dependencies[0].handle == "kasperjunge/migrate-to-skills"

        # Check installed
        installed_dir = git_project / ".claude" / "skills" / "migrate-to-skills"
        assert installed_dir.exists()


class TestMaybeSuggestRepoSkills:
    """Tests for _maybe_suggest_repo_skills helper in add command."""

    def test_suggests_skills_for_two_part_handle(self, monkeypatch):
        """Suggests three-part handles when two-part handle matches a repo."""
        from agr.commands.add import _maybe_suggest_repo_skills
        from agr.handle import ParsedHandle
        from agr.source import SourceResolver

        handle = ParsedHandle(username="remorses", name="playwriter")
        resolver = SourceResolver.default()

        monkeypatch.setattr(
            "agr.commands.add.list_remote_repo_skills",
            lambda *args, **kwargs: ["browser-use", "playwright-test"],
        )

        result = _maybe_suggest_repo_skills(
            "remorses/playwriter", handle, resolver, None
        )

        assert result is not None
        assert "remorses/playwriter" in result
        assert "agr add remorses/playwriter/browser-use" in result
        assert "agr add remorses/playwriter/playwright-test" in result
        assert "owner/repo/skill-name" in result

    def test_suggests_sorted_unique_skills(self, monkeypatch):
        """Suggestions should be sorted and unique."""
        from agr.commands.add import _maybe_suggest_repo_skills
        from agr.handle import ParsedHandle
        from agr.source import SourceResolver

        handle = ParsedHandle(username="owner", name="repo")
        resolver = SourceResolver.default()

        monkeypatch.setattr(
            "agr.commands.add.list_remote_repo_skills",
            lambda *args, **kwargs: ["beta", "alpha", "beta", ""],
        )

        result = _maybe_suggest_repo_skills("owner/repo", handle, resolver, None)
        assert result is not None

        lines = [
            line.strip()
            for line in result.splitlines()
            if line.strip().startswith("agr add")
        ]
        assert lines == [
            "agr add owner/repo/alpha",
            "agr add owner/repo/beta",
        ]

    def test_returns_none_for_three_part_handle(self):
        """Returns None for three-part handles (explicit repo)."""
        from agr.commands.add import _maybe_suggest_repo_skills
        from agr.handle import ParsedHandle
        from agr.source import SourceResolver

        handle = ParsedHandle(username="owner", repo="repo", name="skill")
        resolver = SourceResolver.default()

        result = _maybe_suggest_repo_skills("owner/repo/skill", handle, resolver, None)
        assert result is None

    def test_returns_none_for_local_handle(self):
        """Returns None for local handles."""
        from agr.commands.add import _maybe_suggest_repo_skills
        from agr.handle import ParsedHandle
        from agr.source import SourceResolver

        handle = ParsedHandle(is_local=True, name="my-skill")
        resolver = SourceResolver.default()

        result = _maybe_suggest_repo_skills("./my-skill", handle, resolver, None)
        assert result is None

    def test_returns_none_when_repo_has_no_skills(self, monkeypatch):
        """Returns None when the probed repo has no skills."""
        from agr.commands.add import _maybe_suggest_repo_skills
        from agr.handle import ParsedHandle
        from agr.source import SourceResolver

        handle = ParsedHandle(username="owner", name="empty-repo")
        resolver = SourceResolver.default()

        monkeypatch.setattr(
            "agr.commands.add.list_remote_repo_skills",
            lambda *args, **kwargs: [],
        )

        result = _maybe_suggest_repo_skills("owner/empty-repo", handle, resolver, None)
        assert result is None

    def test_returns_none_when_probe_fails(self, monkeypatch):
        """Returns None when probing the repo raises an exception."""
        from agr.commands.add import _maybe_suggest_repo_skills
        from agr.handle import ParsedHandle
        from agr.source import SourceResolver

        handle = ParsedHandle(username="owner", name="broken")
        resolver = SourceResolver.default()

        def raise_error(*args, **kwargs):
            raise OSError("network error")

        monkeypatch.setattr(
            "agr.commands.add.list_remote_repo_skills",
            raise_error,
        )

        result = _maybe_suggest_repo_skills("owner/broken", handle, resolver, None)
        assert result is None


class TestSyncCommand:
    """Tests for sync command."""

    def test_sync_empty(self, git_project, capsys):
        """sync with no config prints message."""
        from agr.commands.sync import run_sync

        run_sync()

        captured = capsys.readouterr()
        assert "No agr.toml found" in captured.out or "Nothing to sync" in captured.out

    def test_sync_up_to_date(self, git_project, skill_fixture, capsys):
        """sync when already installed shows up to date."""
        from agr.commands.add import run_add
        from agr.commands.sync import run_sync

        # Add skill
        import shutil

        local_skill = git_project / "my-skill"
        shutil.copytree(skill_fixture, local_skill)
        run_add(["./my-skill"])

        # Sync again
        run_sync()

        captured = capsys.readouterr()
        assert "up to date" in captured.out.lower()

    def test_sync_owner_only_respects_source(self, git_project, monkeypatch):
        """sync uses dependency source for owner-only handles."""
        from agr.commands.sync import run_sync

        (git_project / "agr.toml").write_text(
            'default_source = "custom"\n'
            "\n"
            "dependencies = [\n"
            '  { handle = "testuser/test-skill", type = "skill", source = "custom" },\n'
            "]\n"
            "\n"
            "[[source]]\n"
            'name = "custom"\n'
            'type = "git"\n'
            'url = "https://example.com/{owner}/{repo}.git"\n'
            "\n"
            'tools = ["claude"]\n'
        )

        captured: dict[str, str | None] = {}

        def fake_fetch_and_install(
            handle, repo_root, tools, overwrite, resolver, source, skills_dirs=None
        ) -> None:
            captured["source"] = source

        monkeypatch.setattr(
            "agr.commands.sync.fetch_and_install_to_tools", fake_fetch_and_install
        )
        monkeypatch.setattr(
            "agr.fetcher.is_skill_installed", lambda *args, **kwargs: False
        )

        run_sync()

        assert captured["source"] == "custom"

    @skip_on_windows
    def test_sync_migrates_colon_directories(self, git_project, capsys):
        """Sync should rename colon-based directories to double-hyphen."""
        from agr.commands.sync import run_sync

        # Setup: create old-format skill directory
        skills_dir = git_project / ".claude" / "skills"
        old_skill = skills_dir / "user:skill"
        old_skill.mkdir(parents=True)
        (old_skill / "SKILL.md").write_text("---\nname: user:skill\n---\n# Test")

        # Create a minimal config so sync doesn't exit early
        (git_project / "agr.toml").write_text("dependencies = []")

        # Run sync
        run_sync()

        # Check migration happened
        assert not old_skill.exists(), "Old colon-based directory should be removed"
        assert (skills_dir / "user--skill").exists(), (
            "New double-hyphen directory should exist"
        )

        # Check output
        captured = capsys.readouterr()
        assert "Migrated" in captured.out

    @skip_on_windows
    def test_sync_migrates_multiple_colon_directories(self, git_project, capsys):
        """Sync should migrate all colon-based directories."""
        from agr.commands.sync import run_sync

        # Setup: create multiple old-format skill directories
        skills_dir = git_project / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        for name in ["user:skill1", "local:my-skill", "org:repo:skill"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n# Test")

        # Create minimal config
        (git_project / "agr.toml").write_text("dependencies = []")

        # Run sync
        run_sync()

        # Check all migrations happened
        assert not (skills_dir / "user:skill1").exists()
        assert (skills_dir / "user--skill1").exists()
        assert not (skills_dir / "local:my-skill").exists()
        assert (skills_dir / "local--my-skill").exists()
        assert not (skills_dir / "org:repo:skill").exists()
        assert (skills_dir / "org--repo--skill").exists()

    def test_sync_migrates_flat_double_dash_to_name(self, git_project, capsys):
        """Sync should migrate flat double-dash names to plain skill name."""
        from agr.commands.sync import run_sync

        # Create a local skill and legacy installed dir
        skill_dir = git_project / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# Test")

        skills_dir = git_project / ".claude" / "skills"
        legacy_dir = skills_dir / "local--my-skill"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "SKILL.md").write_text("---\nname: local--my-skill\n---\n# Old")

        (git_project / "agr.toml").write_text(
            """
dependencies = [
    { path = "./my-skill", type = "skill" },
]
"""
        )

        run_sync()

        assert not legacy_dir.exists()
        assert (skills_dir / "my-skill").exists()

    @skip_on_windows
    def test_sync_skips_migration_if_target_exists(self, git_project, capsys):
        """Sync should skip migration when target directory already exists."""
        from agr.commands.sync import run_sync

        # Setup: create both old and new format directories
        skills_dir = git_project / ".claude" / "skills"
        old_skill = skills_dir / "user:skill"
        new_skill = skills_dir / "user--skill"
        old_skill.mkdir(parents=True)
        new_skill.mkdir(parents=True)
        (old_skill / "SKILL.md").write_text("---\nname: user:skill\n---\n# Old")
        (new_skill / "SKILL.md").write_text("---\nname: user:skill\n---\n# New")

        # Create minimal config
        (git_project / "agr.toml").write_text("dependencies = []")

        # Run sync
        run_sync()

        # Both should still exist (no migration due to conflict)
        assert old_skill.exists(), "Old directory should still exist when target exists"
        assert new_skill.exists(), "New directory should still exist"

        # Check warning in output
        captured = capsys.readouterr()
        assert "Cannot migrate" in captured.out

    @skip_on_windows
    def test_sync_ignores_non_skill_colon_directories(self, git_project, capsys):
        """Sync should not migrate directories without SKILL.md."""
        from agr.commands.sync import run_sync

        # Setup: create a colon-based directory without SKILL.md
        skills_dir = git_project / ".claude" / "skills"
        non_skill = skills_dir / "not:a:skill"
        non_skill.mkdir(parents=True)
        (non_skill / "README.md").write_text("# Not a skill")

        # Create minimal config
        (git_project / "agr.toml").write_text("dependencies = []")

        # Run sync
        run_sync()

        # Directory should not be migrated
        assert non_skill.exists(), "Non-skill directory should not be migrated"
        assert not (skills_dir / "not--a--skill").exists()
