"""Unit tests for agr.commands.migrations module."""

import json
from pathlib import Path

from agr.commands.migrations import (
    _flatten_nested_skills,
    _migrate_skills_directory,
    migrate_flat_installed_names,
    migrate_legacy_directories,
    run_tool_migrations,
)
from agr.config import AgrConfig, Dependency
from agr.handle import INSTALLED_NAME_SEPARATOR, LEGACY_SEPARATOR
from agr.metadata import METADATA_FILENAME
from agr.skill import SKILL_MARKER
from agr.tool import ANTIGRAVITY, CLAUDE, CODEX, CURSOR, OPENCODE


def _make_skill(path, *, metadata=None):
    """Create a minimal skill directory with SKILL.md and optional metadata."""
    path.mkdir(parents=True, exist_ok=True)
    (path / SKILL_MARKER).write_text("---\nname: test\n---\nTest skill\n")
    if metadata:
        (path / METADATA_FILENAME).write_text(json.dumps(metadata, indent=2) + "\n")


class TestMigrateSkillsDirectory:
    """Tests for _migrate_skills_directory."""

    def test_moves_skill_dirs(self, tmp_path):
        """Skills are moved from old dir to new dir."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        _make_skill(old / "my-skill")

        _migrate_skills_directory(old, new)

        assert not (old / "my-skill").exists()
        assert (new / "my-skill" / SKILL_MARKER).exists()

    def test_skips_when_old_dir_missing(self, tmp_path):
        """No-op when old directory does not exist."""
        old = tmp_path / "nonexistent"
        new = tmp_path / "new" / "skills"

        _migrate_skills_directory(old, new)  # Should not raise

        assert not new.exists()

    def test_skips_conflict(self, tmp_path, capsys):
        """Skips migration when target already exists."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        _make_skill(old / "my-skill")
        _make_skill(new / "my-skill")

        _migrate_skills_directory(old, new)

        # Old skill should still be there
        assert (old / "my-skill" / SKILL_MARKER).exists()
        captured = capsys.readouterr()
        assert "Cannot migrate" in captured.out

    def test_cleans_up_empty_old_dir(self, tmp_path):
        """Old directory is removed when empty after migration."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        _make_skill(old / "my-skill")

        _migrate_skills_directory(old, new)

        assert not old.exists()

    def test_cleanup_parent(self, tmp_path):
        """Parent dir is removed when cleanup_parent=True and empty."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        _make_skill(old / "my-skill")

        _migrate_skills_directory(old, new, cleanup_parent=True)

        assert not old.parent.exists()

    def test_no_cleanup_parent_by_default(self, tmp_path):
        """Parent dir is kept when cleanup_parent=False."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        _make_skill(old / "my-skill")

        _migrate_skills_directory(old, new, cleanup_parent=False)

        # Parent still exists (it's empty but cleanup_parent is False)
        assert old.parent.exists()

    def test_warns_about_non_dir_files(self, tmp_path, capsys):
        """Warns about non-directory files left behind."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        old.mkdir(parents=True)
        (old / "stray-file.txt").write_text("leftover")

        _migrate_skills_directory(old, new)

        captured = capsys.readouterr()
        assert "non-skill file" in captured.out

    def test_skips_non_directory_entries(self, tmp_path):
        """Non-directory entries in old dir are not moved."""
        old = tmp_path / "old" / "skills"
        new = tmp_path / "new" / "skills"
        old.mkdir(parents=True)
        (old / "README.md").write_text("notes")

        _migrate_skills_directory(old, new)

        # File should still be in old dir
        assert (old / "README.md").exists()
        # And not in new dir
        assert not (new / "README.md").exists()


class TestMigrateLegacyDirectories:
    """Tests for migrate_legacy_directories (colon → double-hyphen)."""

    def test_renames_colon_to_double_hyphen(self, tmp_path):
        """Legacy colon directories are renamed to double-hyphen."""
        skills_dir = tmp_path / "skills"
        old_name = f"user{LEGACY_SEPARATOR}skill"
        new_name = f"user{INSTALLED_NAME_SEPARATOR}skill"
        _make_skill(skills_dir / old_name)

        migrate_legacy_directories(skills_dir, CLAUDE)

        assert not (skills_dir / old_name).exists()
        assert (skills_dir / new_name / SKILL_MARKER).exists()

    def test_skips_non_skill_dirs(self, tmp_path):
        """Directories without SKILL.md are not migrated."""
        skills_dir = tmp_path / "skills"
        old_name = f"user{LEGACY_SEPARATOR}skill"
        (skills_dir / old_name).mkdir(parents=True)
        # No SKILL.md

        migrate_legacy_directories(skills_dir, CLAUDE)

        assert (skills_dir / old_name).exists()

    def test_skips_when_target_exists(self, tmp_path, capsys):
        """Skips migration when target already exists."""
        skills_dir = tmp_path / "skills"
        old_name = f"user{LEGACY_SEPARATOR}skill"
        new_name = f"user{INSTALLED_NAME_SEPARATOR}skill"
        _make_skill(skills_dir / old_name)
        _make_skill(skills_dir / new_name)

        migrate_legacy_directories(skills_dir, CLAUDE)

        # Both should still exist
        assert (skills_dir / old_name).exists()
        assert (skills_dir / new_name).exists()
        captured = capsys.readouterr()
        assert "Cannot migrate" in captured.out

    def test_skips_nested_tools(self, tmp_path):
        """No migration for tools that support nested directories."""
        skills_dir = tmp_path / "skills"
        old_name = f"user{LEGACY_SEPARATOR}skill"
        _make_skill(skills_dir / old_name)

        # Cursor used to support nested; even if it no longer does, test the guard
        from dataclasses import replace

        nested_tool = replace(CLAUDE, supports_nested=True)
        migrate_legacy_directories(skills_dir, nested_tool)

        # Should not have migrated
        assert (skills_dir / old_name).exists()

    def test_noop_when_dir_missing(self, tmp_path):
        """No-op when skills directory does not exist."""
        skills_dir = tmp_path / "nonexistent"
        migrate_legacy_directories(skills_dir, CLAUDE)  # Should not raise

    def test_ignores_dirs_without_colon(self, tmp_path):
        """Directories without the legacy separator are left alone."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "plain-skill")

        migrate_legacy_directories(skills_dir, CLAUDE)

        assert (skills_dir / "plain-skill").exists()


class TestMigrateFlatInstalledNames:
    """Tests for migrate_flat_installed_names."""

    def test_renames_full_name_to_plain(self, tmp_path):
        """Unique skills are renamed from user--repo--skill to skill."""
        skills_dir = tmp_path / "skills"
        full_name = (
            f"user{INSTALLED_NAME_SEPARATOR}repo{INSTALLED_NAME_SEPARATOR}commit"
        )
        _make_skill(skills_dir / full_name)

        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="user/repo/commit"),
            ]
        )

        migrate_flat_installed_names(skills_dir, CLAUDE, config, tmp_path)

        assert not (skills_dir / full_name).exists()
        assert (skills_dir / "commit" / SKILL_MARKER).exists()

    def test_skips_nested_tools(self, tmp_path):
        """No migration for tools that support nested directories."""
        skills_dir = tmp_path / "skills"
        full_name = f"user{INSTALLED_NAME_SEPARATOR}skill"
        _make_skill(skills_dir / full_name)

        from dataclasses import replace

        nested_tool = replace(CLAUDE, supports_nested=True)
        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="user/skill"),
            ]
        )

        migrate_flat_installed_names(skills_dir, nested_tool, config, tmp_path)

        # Should not have migrated
        assert (skills_dir / full_name).exists()

    def test_noop_when_dir_missing(self, tmp_path):
        """No-op when skills directory does not exist."""
        skills_dir = tmp_path / "nonexistent"
        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="user/skill"),
            ]
        )

        migrate_flat_installed_names(skills_dir, CLAUDE, config, tmp_path)  # No raise

    def test_updates_metadata_when_plain_name_exists(self, tmp_path):
        """When plain-name dir exists, metadata is updated if stale."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "commit")
        # No metadata initially

        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="user/repo/commit"),
            ]
        )

        migrate_flat_installed_names(skills_dir, CLAUDE, config, tmp_path)

        # Metadata should now exist
        meta_path = skills_dir / "commit" / METADATA_FILENAME
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert "user/repo/commit" in meta.get("id", "")

    def test_ambiguous_names_keep_full_paths(self, tmp_path):
        """When multiple handles share a skill name, full names are kept."""
        skills_dir = tmp_path / "skills"
        full1 = f"alice{INSTALLED_NAME_SEPARATOR}repo{INSTALLED_NAME_SEPARATOR}commit"
        full2 = f"bob{INSTALLED_NAME_SEPARATOR}repo{INSTALLED_NAME_SEPARATOR}commit"
        _make_skill(skills_dir / full1)
        _make_skill(skills_dir / full2)

        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="alice/repo/commit"),
                Dependency(type="skill", handle="bob/repo/commit"),
            ]
        )

        migrate_flat_installed_names(skills_dir, CLAUDE, config, tmp_path)

        # Both full-name dirs should still exist (ambiguous)
        assert (skills_dir / full1).exists()
        assert (skills_dir / full2).exists()
        # Metadata should be stamped on both
        assert (skills_dir / full1 / METADATA_FILENAME).exists()
        assert (skills_dir / full2 / METADATA_FILENAME).exists()


class TestFlattenNestedSkills:
    """Tests for _flatten_nested_skills."""

    def test_flattens_nested_skill(self, tmp_path):
        """Nested skill (user/repo/skill/) is flattened to top level."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "user" / "repo" / "my-skill")

        _flatten_nested_skills(skills_dir)

        assert (skills_dir / "my-skill" / SKILL_MARKER).exists()
        assert not (skills_dir / "user").exists()

    def test_uses_qualified_name_on_conflict(self, tmp_path):
        """Falls back to qualified name when plain name is taken."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "my-skill")  # Already at top level
        _make_skill(skills_dir / "user" / "repo" / "my-skill")

        _flatten_nested_skills(skills_dir)

        sep = INSTALLED_NAME_SEPARATOR
        qualified = f"user{sep}repo{sep}my-skill"
        assert (skills_dir / "my-skill" / SKILL_MARKER).exists()
        assert (skills_dir / qualified / SKILL_MARKER).exists()

    def test_noop_for_already_flat(self, tmp_path):
        """Skills already at depth 1 are not moved."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "my-skill")

        _flatten_nested_skills(skills_dir)

        assert (skills_dir / "my-skill" / SKILL_MARKER).exists()

    def test_noop_when_dir_missing(self, tmp_path):
        """No-op when skills directory does not exist."""
        _flatten_nested_skills(tmp_path / "nonexistent")  # Should not raise

    def test_cleans_up_empty_parents(self, tmp_path):
        """Empty intermediate directories are removed after flattening."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "user" / "repo" / "my-skill")

        _flatten_nested_skills(skills_dir)

        assert not (skills_dir / "user").exists()

    def test_skips_when_both_names_taken(self, tmp_path, capsys):
        """Skips when both plain and qualified names are taken."""
        skills_dir = tmp_path / "skills"
        _make_skill(skills_dir / "my-skill")
        sep = INSTALLED_NAME_SEPARATOR
        qualified = f"user{sep}repo{sep}my-skill"
        _make_skill(skills_dir / qualified)
        _make_skill(skills_dir / "user" / "repo" / "my-skill")

        _flatten_nested_skills(skills_dir)

        captured = capsys.readouterr()
        assert "Cannot flatten" in captured.out
        # Nested skill should still be there
        assert (skills_dir / "user" / "repo" / "my-skill").exists()


class TestRunToolMigrations:
    """Tests for run_tool_migrations."""

    def test_codex_migration(self, tmp_path):
        """Codex skills are migrated from .codex/ to .agents/."""
        _make_skill(tmp_path / ".codex" / "skills" / "my-skill")

        run_tool_migrations([CODEX], tmp_path)

        assert (tmp_path / ".agents" / "skills" / "my-skill" / SKILL_MARKER).exists()
        # Old .codex dir should be cleaned up
        assert not (tmp_path / ".codex").exists()

    def test_opencode_migration(self, tmp_path):
        """OpenCode skills are migrated from skill/ to skills/."""
        _make_skill(tmp_path / ".opencode" / "skill" / "my-skill")

        run_tool_migrations([OPENCODE], tmp_path)

        assert (tmp_path / ".opencode" / "skills" / "my-skill" / SKILL_MARKER).exists()
        assert not (tmp_path / ".opencode" / "skill").exists()

    def test_antigravity_migration(self, tmp_path):
        """Antigravity skills are migrated from .agent/ to .gemini/."""
        _make_skill(tmp_path / ".agent" / "skills" / "my-skill")

        run_tool_migrations([ANTIGRAVITY], tmp_path)

        assert (tmp_path / ".gemini" / "skills" / "my-skill" / SKILL_MARKER).exists()
        # Old .agent dir should be cleaned up
        assert not (tmp_path / ".agent").exists()

    def test_antigravity_global_subdir_migration(self, tmp_path):
        """Antigravity legacy .gemini/antigravity/skills/ is migrated to .gemini/skills/."""
        _make_skill(tmp_path / ".gemini" / "antigravity" / "skills" / "my-skill")

        _migrate_skills_directory(
            tmp_path / ".gemini" / "antigravity" / "skills",
            tmp_path / ".gemini" / "skills",
            cleanup_parent=True,
        )

        assert (tmp_path / ".gemini" / "skills" / "my-skill" / SKILL_MARKER).exists()
        # Old .gemini/antigravity dir should be cleaned up
        assert not (tmp_path / ".gemini" / "antigravity").exists()

    def test_noop_when_repo_root_none(self):
        """No-op when repo_root is None and not global."""
        run_tool_migrations([CLAUDE], None)  # Should not raise

    def test_cursor_migration_flattens_nested(self, tmp_path):
        """Cursor nested skills are flattened to top level during migration."""
        _make_skill(tmp_path / ".cursor" / "skills" / "user" / "repo" / "my-skill")

        run_tool_migrations([CURSOR], tmp_path)

        assert (tmp_path / ".cursor" / "skills" / "my-skill" / SKILL_MARKER).exists()
        assert not (tmp_path / ".cursor" / "skills" / "user").exists()

    def test_opencode_global_migration_uses_global_config_dir(
        self, tmp_path, monkeypatch
    ):
        """OpenCode global migration uses ~/.config/opencode/ not ~/.opencode/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _make_skill(tmp_path / ".config" / "opencode" / "skill" / "my-skill")

        run_tool_migrations([OPENCODE], None, global_install=True)

        assert (
            tmp_path / ".config" / "opencode" / "skills" / "my-skill" / SKILL_MARKER
        ).exists()
        assert not (tmp_path / ".config" / "opencode" / "skill").exists()

    def test_antigravity_global_migration(self, tmp_path, monkeypatch):
        """Antigravity global migration moves .gemini/antigravity/skills/ to .gemini/skills/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _make_skill(tmp_path / ".gemini" / "antigravity" / "skills" / "my-skill")

        run_tool_migrations([ANTIGRAVITY], None, global_install=True)

        assert (tmp_path / ".gemini" / "skills" / "my-skill" / SKILL_MARKER).exists()
        assert not (tmp_path / ".gemini" / "antigravity").exists()

    def test_codex_global_migration(self, tmp_path, monkeypatch):
        """Codex global migration moves ~/.codex/skills/ to ~/.agents/skills/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _make_skill(tmp_path / ".codex" / "skills" / "my-skill")

        run_tool_migrations([CODEX], None, global_install=True)

        assert (tmp_path / ".agents" / "skills" / "my-skill" / SKILL_MARKER).exists()
        assert not (tmp_path / ".codex").exists()

    def test_cursor_global_migration_flattens_nested(self, tmp_path, monkeypatch):
        """Cursor global migration flattens nested skills in ~/.cursor/skills/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _make_skill(
            tmp_path / ".cursor" / "skills" / "user" / "repo" / "my-skill"
        )

        run_tool_migrations([CURSOR], None, global_install=True)

        assert (
            tmp_path / ".cursor" / "skills" / "my-skill" / SKILL_MARKER
        ).exists()
        assert not (tmp_path / ".cursor" / "skills" / "user").exists()

    def test_antigravity_global_agent_to_gemini_migration(
        self, tmp_path, monkeypatch
    ):
        """Antigravity global migration moves ~/.agent/skills/ to ~/.gemini/skills/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _make_skill(tmp_path / ".agent" / "skills" / "my-skill")

        run_tool_migrations([ANTIGRAVITY], None, global_install=True)

        assert (
            tmp_path / ".gemini" / "skills" / "my-skill" / SKILL_MARKER
        ).exists()
        assert not (tmp_path / ".agent").exists()

    def test_skips_unconfigured_tools(self, tmp_path):
        """Only migrates tools that are in the tools list."""
        _make_skill(tmp_path / ".codex" / "skills" / "my-skill")

        # Only Claude configured, not Codex
        run_tool_migrations([CLAUDE], tmp_path)

        # Codex skill should not be migrated
        assert (tmp_path / ".codex" / "skills" / "my-skill").exists()
