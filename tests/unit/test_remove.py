"""Unit tests for agr.commands.remove module."""

import json
from pathlib import Path
from unittest.mock import patch

from agr.commands._tool_helpers import LoadedConfig
from agr.commands.remove import (
    _identifier_candidates,
    _find_dep_by_candidates,
    run_remove,
)
from agr.config import AgrConfig, Dependency
from agr.handle import ParsedHandle
from agr.lockfile import LockedEntry, Lockfile, load_lockfile, save_lockfile
from agr.metadata import (
    METADATA_FILENAME,
    METADATA_KEY_ID,
    METADATA_KEY_TYPE,
    METADATA_TYPE_REMOTE,
    build_handle_id,
)
from agr.skill import SKILL_MARKER
from agr.skill_installer import uninstall_skill
from agr.tool import CLAUDE


class TestIdentifierCandidates:
    """Tests for _identifier_candidates()."""

    def test_remote_handle_includes_ref_and_toml_handle(self):
        """Remote handle produces ref and toml handle as candidates."""
        handle = ParsedHandle(username="owner", repo="repo", name="skill")
        result = _identifier_candidates("owner/repo/skill", handle, None)
        # The ./ prefixed form is appended as a fallback for local-path matching
        assert result[:1] == ["owner/repo/skill"]

    def test_remote_two_part_handle(self):
        """Two-part remote handle produces ref and toml handle."""
        handle = ParsedHandle(username="owner", name="skill")
        result = _identifier_candidates("owner/skill", handle, None)
        assert result[:1] == ["owner/skill"]

    def test_remote_ref_differs_from_toml_handle(self):
        """When ref differs from toml handle, both appear in order."""
        handle = ParsedHandle(username="owner", repo="repo", name="skill")
        result = _identifier_candidates("OWNER/repo/skill", handle, None)
        assert result[:2] == ["OWNER/repo/skill", "owner/repo/skill"]

    def test_local_handle_includes_path(self):
        """Local handle includes ref and local_path string."""
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("./skills/my-skill")
        )
        result = _identifier_candidates("./skills/my-skill", handle, None)
        assert result == ["./skills/my-skill", "skills/my-skill"]

    def test_local_handle_with_abs_path(self):
        """Local handle with absolute path includes all three forms."""
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("./skills/my-skill")
        )
        result = _identifier_candidates(
            "./skills/my-skill", handle, "/home/user/project/skills/my-skill"
        )
        assert result == [
            "./skills/my-skill",
            "skills/my-skill",
            "/home/user/project/skills/my-skill",
        ]

    def test_duplicates_are_removed(self):
        """Duplicate values are deduplicated while preserving order."""
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("./skills/my-skill")
        )
        # ref and str(local_path) could overlap; ./ form also included
        result = _identifier_candidates("skills/my-skill", handle, None)
        assert result == ["skills/my-skill", "./skills/my-skill"]

    def test_local_handle_without_local_path(self):
        """Local handle with no local_path only includes ref."""
        handle = ParsedHandle(is_local=True, name="skill")
        result = _identifier_candidates("./skill", handle, None)
        assert result == ["./skill"]

    def test_abs_path_deduped_with_ref(self):
        """Absolute path identical to ref is deduplicated."""
        handle = ParsedHandle(
            is_local=True, name="skill", local_path=Path("/abs/skill")
        )
        result = _identifier_candidates("/abs/skill", handle, "/abs/skill")
        # Absolute paths start with / so no ./ prefix is added
        assert result == ["/abs/skill"]

    def test_one_part_handle_produces_ref_and_expanded_toml_handle(self):
        """1-part ref with resolved handle produces both raw and expanded forms."""
        handle = ParsedHandle(username="computerlovetech", name="setup")
        result = _identifier_candidates("setup", handle, None)
        assert result[:2] == ["setup", "computerlovetech/setup"]

    def test_local_ref_without_dot_slash_includes_prefixed_form(self):
        """Ref without ./ prefix should also try the ./ form to match config entries.

        Regression: `agr add ./my-skill` stores path="./my-skill" in config,
        but `agr remove my-skill` (when the dir exists on disk and parses as
        local) only produces candidate "my-skill", which doesn't match
        "./my-skill".  Meanwhile `agr upgrade my-skill` succeeds because it
        normalises both sides via _normalize_handle.
        """
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("my-skill")
        )
        result = _identifier_candidates("my-skill", handle, None)
        assert "./my-skill" in result

    def test_local_nested_ref_without_dot_slash_includes_prefixed_form(self):
        """Nested local path without ./ should also try the ./ form."""
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("skills/my-skill")
        )
        result = _identifier_candidates("skills/my-skill", handle, None)
        assert "./skills/my-skill" in result

    def test_local_ref_with_dot_slash_does_not_double_prefix(self):
        """Ref already starting with ./ should not get a second ./ prefix."""
        handle = ParsedHandle(
            is_local=True, name="my-skill", local_path=Path("./my-skill")
        )
        result = _identifier_candidates("./my-skill", handle, None)
        # Should not contain "././my-skill"
        assert all(not c.startswith("././") for c in result)


class TestFindDepByCandidates:
    """Tests for _find_dep_by_candidates()."""

    def test_matches_by_identifier(self):
        """Direct identifier match works."""
        dep = Dependency(handle="owner/repo/skill", type="skill")
        deps = [dep]
        candidates = ["owner/repo/skill"]
        result = _find_dep_by_candidates(candidates, "owner/repo/skill", deps)
        assert result is dep

    def test_matches_by_installed_name_for_three_part_handle(self):
        """Bare skill name matches a three-part handle via installed_name.

        Regression: `agr remove skill` failed to find a dependency with
        handle="owner/repo/skill" because _identifier_candidates only
        generates identifier strings, never checking dep.installed_name.
        Meanwhile `agr upgrade skill` succeeded because _match_handle_to_dep
        also checks dep.installed_name.
        """
        dep = Dependency(handle="owner/repo/skill", type="skill")
        deps = [dep]
        candidates = ["skill", "computerlovetech/skill", "./skill"]
        result = _find_dep_by_candidates(candidates, "skill", deps)
        assert result is dep

    def test_no_match_returns_none(self):
        """Returns None when nothing matches."""
        dep = Dependency(handle="owner/repo/skill", type="skill")
        deps = [dep]
        candidates = ["other", "computerlovetech/other"]
        result = _find_dep_by_candidates(candidates, "other", deps)
        assert result is None

    def test_identifier_match_takes_priority_over_installed_name(self):
        """Identifier match is preferred over installed_name match."""
        dep_direct = Dependency(handle="myowner/skill", type="skill")
        dep_three = Dependency(handle="owner/repo/skill", type="skill")
        deps = [dep_direct, dep_three]
        candidates = ["myowner/skill"]
        result = _find_dep_by_candidates(candidates, "myowner/skill", deps)
        assert result is dep_direct


class TestRemoveByBareNameFilesystem:
    """Test that removing by bare name actually removes filesystem files.

    Regression: when `agr remove my-skill` matches a dep with
    handle="alice/repo/my-skill" via the installed_name fallback,
    the handle used for filesystem removal was parsed from the CLI
    ref ("my-skill" → computerlovetech/my-skill) instead of from
    the dep itself. The metadata check then failed because the
    handle IDs didn't match, leaving orphaned files on disk.
    """

    def _install_fake_skill(
        self, skills_dir: Path, name: str, handle: ParsedHandle, source: str
    ) -> Path:
        """Create a fake installed skill directory with metadata."""
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MARKER).write_text(f"---\nname: {name}\n---\n")
        handle_id = build_handle_id(handle, None, source)
        meta = {
            METADATA_KEY_ID: handle_id,
            METADATA_KEY_TYPE: METADATA_TYPE_REMOTE,
        }
        (skill_dir / METADATA_FILENAME).write_text(json.dumps(meta))
        return skill_dir

    def test_uninstall_with_wrong_handle_fails_to_find_skill(self, tmp_path):
        """Prove the bug: a handle parsed from the bare name can't find the skill."""
        skills_dir = tmp_path / ".claude" / "skills"

        # The skill was installed from alice/repo/my-skill
        real_handle = ParsedHandle(username="alice", repo="repo", name="my-skill")
        skill_dir = self._install_fake_skill(
            skills_dir, "my-skill", real_handle, "github"
        )
        assert skill_dir.exists()

        # But the bare-name ref "my-skill" is parsed with default_owner
        wrong_handle = ParsedHandle(username="computerlovetech", name="my-skill")

        # With the wrong handle, the metadata doesn't match so the
        # skill is not found and therefore not removed.
        removed = uninstall_skill(
            wrong_handle, tmp_path, CLAUDE, "github", skills_dir=skills_dir
        )
        assert not removed, (
            "Expected uninstall to fail with wrong handle — "
            "if this passes, the bug may have been fixed elsewhere"
        )
        assert skill_dir.exists(), "Skill files should still be on disk"

    def test_uninstall_with_correct_handle_succeeds(self, tmp_path):
        """Verify that the correct handle does remove the skill."""
        skills_dir = tmp_path / ".claude" / "skills"

        real_handle = ParsedHandle(username="alice", repo="repo", name="my-skill")
        skill_dir = self._install_fake_skill(
            skills_dir, "my-skill", real_handle, "github"
        )
        assert skill_dir.exists()

        # With the correct handle, the metadata matches and the skill is removed.
        removed = uninstall_skill(
            real_handle, tmp_path, CLAUDE, "github", skills_dir=skills_dir
        )
        assert removed
        assert not skill_dir.exists()

    def test_run_remove_bare_name_uses_config_dependency_handle(self, tmp_path):
        """`agr remove name` removes files for the matched dependency handle."""
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(
            dependencies=[Dependency(type="skill", handle="alice/repo/my-skill")]
        )
        skills_dir = tmp_path / ".claude" / "skills"
        real_handle = ParsedHandle(username="alice", repo="repo", name="my-skill")
        skill_dir = self._install_fake_skill(
            skills_dir, "my-skill", real_handle, "github"
        )

        loaded = LoadedConfig(
            config=config,
            config_path=config_path,
            tools=[CLAUDE],
            repo_root=tmp_path,
            skills_dirs={"claude": skills_dir},
        )

        with (
            patch("agr.commands.remove.load_existing_config", return_value=loaded),
            patch("agr.commands.remove.run_tool_migrations"),
        ):
            run_remove(["my-skill"])

        assert not skill_dir.exists()
        assert config.dependencies == []


class TestRemovePackage:
    """Tests for removing package transitive installs."""

    def _install_fake_skill(
        self, skills_dir: Path, name: str, handle: ParsedHandle, source: str
    ) -> Path:
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MARKER).write_text(f"---\nname: {name}\n---\n")
        (skill_dir / METADATA_FILENAME).write_text(
            json.dumps(
                {
                    METADATA_KEY_ID: build_handle_id(handle, None, source),
                    METADATA_KEY_TYPE: METADATA_TYPE_REMOTE,
                }
            )
        )
        return skill_dir

    def test_remove_package_removes_locked_transitive_children(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(
            dependencies=[Dependency(type="package", handle="alice/repo/bundle")]
        )
        skills_dir = tmp_path / ".claude" / "skills"
        child_handle = ParsedHandle(username="alice", repo="repo", name="child")
        child_dir = self._install_fake_skill(
            skills_dir, "child", child_handle, "github"
        )
        save_lockfile(
            Lockfile(
                packages=[
                    LockedEntry(
                        handle="alice/repo/bundle",
                        source="github",
                        commit="b" * 40,
                        installed_name="bundle",
                    )
                ],
                skills=[
                    LockedEntry(
                        handle="alice/repo/child",
                        source="github",
                        commit="c" * 40,
                        installed_name="child",
                        parent="alice/repo/bundle",
                    )
                ],
            ),
            tmp_path / "agr.lock",
        )

        loaded = LoadedConfig(
            config=config,
            config_path=config_path,
            tools=[CLAUDE],
            repo_root=tmp_path,
            skills_dirs={"claude": skills_dir},
        )

        with (
            patch("agr.commands.remove.load_existing_config", return_value=loaded),
            patch("agr.commands.remove.run_tool_migrations"),
        ):
            run_remove(["bundle"])

        assert not child_dir.exists()
        lockfile = load_lockfile(tmp_path / "agr.lock")
        assert lockfile is not None
        assert lockfile.packages == []
        assert lockfile.skills == []

    def test_remove_package_removes_nested_package_lock_entries(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(
            dependencies=[Dependency(type="package", handle="alice/repo/top")]
        )
        save_lockfile(
            Lockfile(
                packages=[
                    LockedEntry(handle="alice/repo/top", installed_name="top"),
                    LockedEntry(
                        handle="alice/repo/nested",
                        installed_name="nested",
                        parent="alice/repo/top",
                    ),
                ],
            ),
            tmp_path / "agr.lock",
        )
        loaded = LoadedConfig(
            config=config,
            config_path=config_path,
            tools=[CLAUDE],
            repo_root=tmp_path,
            skills_dirs={"claude": tmp_path / ".claude" / "skills"},
        )

        with (
            patch("agr.commands.remove.load_existing_config", return_value=loaded),
            patch("agr.commands.remove.run_tool_migrations"),
        ):
            run_remove(["top"])

        lockfile = load_lockfile(tmp_path / "agr.lock")
        assert lockfile is not None
        assert lockfile.packages == []

    def test_remove_package_keeps_shared_child_required_by_other_package(
        self, tmp_path
    ):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(
            dependencies=[
                Dependency(type="package", handle="alice/repo/bundle-a"),
                Dependency(type="package", handle="alice/repo/bundle-b"),
            ]
        )
        save_lockfile(
            Lockfile(
                packages=[
                    LockedEntry(
                        handle="alice/repo/bundle-a", installed_name="bundle-a"
                    ),
                    LockedEntry(
                        handle="alice/repo/bundle-b", installed_name="bundle-b"
                    ),
                ],
                skills=[
                    LockedEntry(
                        handle="alice/repo/shared",
                        installed_name="shared",
                        parents=["alice/repo/bundle-a", "alice/repo/bundle-b"],
                    )
                ],
            ),
            tmp_path / "agr.lock",
        )
        loaded = LoadedConfig(
            config=config,
            config_path=config_path,
            tools=[CLAUDE],
            repo_root=tmp_path,
            skills_dirs={"claude": tmp_path / ".claude" / "skills"},
        )

        with (
            patch("agr.commands.remove.load_existing_config", return_value=loaded),
            patch("agr.commands.remove.run_tool_migrations"),
        ):
            run_remove(["bundle-a"])

        lockfile = load_lockfile(tmp_path / "agr.lock")
        assert lockfile is not None
        assert [entry.handle for entry in lockfile.packages] == ["alice/repo/bundle-b"]
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].parent_ids == {"alice/repo/bundle-b"}
