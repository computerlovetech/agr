"""Unit tests for the lockfile module."""

import pytest
from unittest.mock import MagicMock, patch

from agr.commands.sync import (
    SyncResult,
    SyncStatus,
    _build_lockfile_from_results,
    _sync_from_lockfile,
)
from agr.config import AgrConfig, Dependency
from agr.exceptions import ConfigError
from agr.lockfile import (
    LOCKFILE_VERSION,
    LockedEntry,
    Lockfile,
    build_lockfile_path,
    load_lockfile,
    save_lockfile,
)


class TestLockedEntry:
    def test_remote_skill_identifier(self):
        skill = LockedEntry(
            handle="user/repo/skill",
            source="github",
            commit="abc123",
            content_hash="sha256:def456",
            installed_name="skill",
        )
        assert skill.identifier == "user/repo/skill"
        assert not skill.is_local

    def test_local_skill_identifier(self):
        skill = LockedEntry(path="./local/skill", installed_name="skill")
        assert skill.identifier == "./local/skill"
        assert skill.is_local


class TestBuildLockfilePath:
    def test_returns_sibling_of_config(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        assert build_lockfile_path(config_path) == tmp_path / "agr.lock"


class TestSaveAndLoad:
    def test_round_trip_remote_skills(self, tmp_path):
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/skill",
                    source="github",
                    commit="a" * 40,
                    content_hash="sha256:" + "b" * 64,
                    installed_name="skill",
                ),
            ]
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert loaded.version == LOCKFILE_VERSION
        assert len(loaded.skills) == 1
        s = loaded.skills[0]
        assert s.handle == "user/repo/skill"
        assert s.source == "github"
        assert s.commit == "a" * 40
        assert s.content_hash == "sha256:" + "b" * 64
        assert s.installed_name == "skill"

    def test_round_trip_local_skills(self, tmp_path):
        lockfile = Lockfile(
            skills=[
                LockedEntry(path="./local/my-skill", installed_name="my-skill"),
            ]
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.skills) == 1
        s = loaded.skills[0]
        assert s.path == "./local/my-skill"
        assert s.installed_name == "my-skill"
        assert s.handle is None
        assert s.commit is None
        assert s.content_hash is None

    def test_round_trip_mixed_skills(self, tmp_path):
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/skill",
                    source="github",
                    commit="a" * 40,
                    content_hash="sha256:" + "b" * 64,
                    installed_name="skill",
                ),
                LockedEntry(path="./local/other", installed_name="other"),
            ]
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.skills) == 2
        assert loaded.skills[0].handle == "user/repo/skill"
        assert loaded.skills[1].path == "./local/other"

    def test_load_missing_file_returns_none(self, tmp_path):
        assert load_lockfile(tmp_path / "agr.lock") is None

    def test_load_corrupt_toml_raises(self, tmp_path):
        path = tmp_path / "agr.lock"
        path.write_text("[[[[invalid toml")
        with pytest.raises(ConfigError, match="Invalid lockfile"):
            load_lockfile(path)

    def test_load_unsupported_version_raises(self, tmp_path):
        path = tmp_path / "agr.lock"
        path.write_text("version = 999\n")
        with pytest.raises(ConfigError, match="Unsupported lockfile version"):
            load_lockfile(path)

    def test_empty_lockfile_round_trip(self, tmp_path):
        lockfile = Lockfile(skills=[])
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)
        assert loaded is not None
        assert loaded.skills == []

    def test_saved_file_has_header_comment(self, tmp_path):
        path = tmp_path / "agr.lock"
        save_lockfile(Lockfile(skills=[]), path)
        content = path.read_text()
        assert "auto-generated" in content


class TestFindLockedEntry:
    def test_find_by_handle(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(handle="user/repo/b", installed_name="b"),
            ]
        )
        dep = Dependency(type="skill", handle="user/repo/b")
        result = lockfile.find_entry(dep)
        assert result is not None
        assert result.installed_name == "b"

    def test_find_by_path(self):
        lockfile = Lockfile(
            skills=[LockedEntry(path="./local/skill", installed_name="skill")]
        )
        dep = Dependency(type="skill", path="./local/skill")
        result = lockfile.find_entry(dep)
        assert result is not None
        assert result.installed_name == "skill"

    def test_returns_none_for_unknown(self):
        lockfile = Lockfile(
            skills=[LockedEntry(handle="user/repo/a", installed_name="a")]
        )
        dep = Dependency(type="skill", handle="user/repo/unknown")
        assert lockfile.find_entry(dep) is None

    def test_returns_none_for_empty_lockfile(self):
        lockfile = Lockfile(skills=[])
        dep = Dependency(type="skill", handle="user/repo/skill")
        assert lockfile.find_entry(dep) is None


class TestIsLockfileCurrent:
    def test_matching_deps(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(path="./local/b", installed_name="b"),
            ]
        )
        deps = [
            Dependency(type="skill", handle="user/repo/a"),
            Dependency(type="skill", path="./local/b"),
        ]
        assert lockfile.is_current(deps) is True

    def test_extra_in_lockfile(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(handle="user/repo/b", installed_name="b"),
            ]
        )
        deps = [Dependency(type="skill", handle="user/repo/a")]
        assert lockfile.is_current(deps) is False

    def test_missing_from_lockfile(self):
        lockfile = Lockfile(
            skills=[LockedEntry(handle="user/repo/a", installed_name="a")]
        )
        deps = [
            Dependency(type="skill", handle="user/repo/a"),
            Dependency(type="skill", handle="user/repo/b"),
        ]
        assert lockfile.is_current(deps) is False

    def test_both_empty(self):
        assert Lockfile(skills=[]).is_current([]) is True


class TestUpdateLockfileEntry:
    def test_adds_new_entry(self):
        lockfile = Lockfile(skills=[])
        entry = LockedEntry(handle="user/repo/a", installed_name="a")
        lockfile.update_entry(entry)
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].handle == "user/repo/a"

    def test_replaces_existing_entry(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/a",
                    commit="old",
                    installed_name="a",
                )
            ]
        )
        entry = LockedEntry(handle="user/repo/a", commit="new", installed_name="a")
        lockfile.update_entry(entry)
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].commit == "new"

    def test_preserves_other_entries(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(handle="user/repo/b", installed_name="b"),
            ]
        )
        entry = LockedEntry(handle="user/repo/a", commit="new", installed_name="a")
        lockfile.update_entry(entry)
        assert len(lockfile.skills) == 2


class TestRemoveLockfileEntry:
    def test_removes_by_handle(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(handle="user/repo/b", installed_name="b"),
            ]
        )
        lockfile.remove_entry("user/repo/a")
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].handle == "user/repo/b"

    def test_removes_by_path(self):
        lockfile = Lockfile(
            skills=[LockedEntry(path="./local/skill", installed_name="skill")]
        )
        lockfile.remove_entry("./local/skill")
        assert lockfile.skills == []

    def test_noop_for_unknown_identifier(self):
        lockfile = Lockfile(
            skills=[LockedEntry(handle="user/repo/a", installed_name="a")]
        )
        lockfile.remove_entry("user/repo/unknown")
        assert len(lockfile.skills) == 1


class TestRalphLockfileSupport:
    """Tests for ralph entries in the lockfile."""

    def test_round_trip_ralph(self, tmp_path):
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedEntry(
                    handle="user/repo/my-ralph",
                    source="github",
                    commit="c" * 40,
                    content_hash="sha256:" + "d" * 64,
                    installed_name="my-ralph",
                ),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.ralphs) == 1
        assert len(loaded.skills) == 0
        r = loaded.ralphs[0]
        assert r.handle == "user/repo/my-ralph"
        assert r.source == "github"
        assert r.commit == "c" * 40
        assert r.installed_name == "my-ralph"

    def test_round_trip_mixed_skills_and_ralphs(self, tmp_path):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[
                LockedEntry(handle="user/repo/ralph", installed_name="ralph"),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.skills) == 1
        assert len(loaded.ralphs) == 1
        assert loaded.skills[0].handle == "user/repo/skill"
        assert loaded.ralphs[0].handle == "user/repo/ralph"

    def test_update_lockfile_entry_ralph(self):
        lockfile = Lockfile(skills=[], ralphs=[])
        entry = LockedEntry(handle="user/repo/ralph", installed_name="ralph")
        lockfile.update_entry(entry, kind="ralph")
        assert len(lockfile.ralphs) == 1
        assert len(lockfile.skills) == 0
        assert lockfile.ralphs[0].handle == "user/repo/ralph"

    def test_remove_lockfile_entry_ralph(self):
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(handle="user/repo/b", installed_name="b"),
            ],
        )
        lockfile.remove_entry("user/repo/a", kind="ralph")
        assert len(lockfile.ralphs) == 1
        assert lockfile.ralphs[0].handle == "user/repo/b"

    def test_find_locked_ralph(self):
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedEntry(handle="user/repo/ralph", installed_name="ralph"),
            ],
        )
        dep = Dependency(type="ralph", handle="user/repo/ralph")
        result = lockfile.find_entry(dep)
        assert result is not None
        assert result.installed_name == "ralph"

    def test_find_locked_ralph_not_in_skills(self):
        """Ralph dep should not match entries in the skills list."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/ralph", installed_name="ralph"),
            ],
            ralphs=[],
        )
        dep = Dependency(type="ralph", handle="user/repo/ralph")
        result = lockfile.find_entry(dep)
        assert result is None

    def test_is_lockfile_current_with_ralphs(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[
                LockedEntry(handle="user/repo/ralph", installed_name="ralph"),
            ],
        )
        deps = [
            Dependency(type="skill", handle="user/repo/skill"),
            Dependency(type="ralph", handle="user/repo/ralph"),
        ]
        assert lockfile.is_current(deps) is True

    def test_is_lockfile_current_missing_ralph(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[],
        )
        deps = [
            Dependency(type="skill", handle="user/repo/skill"),
            Dependency(type="ralph", handle="user/repo/ralph"),
        ]
        assert lockfile.is_current(deps) is False


class TestRemoveLockfileEntryReturnValue:
    """Tests for Lockfile.remove_entry return value."""

    def test_returns_true_on_match(self):
        lockfile = Lockfile(
            skills=[LockedEntry(handle="user/repo/a", installed_name="a")]
        )
        assert lockfile.remove_entry("user/repo/a") is True
        assert len(lockfile.skills) == 0

    def test_returns_false_on_miss(self):
        lockfile = Lockfile(
            skills=[LockedEntry(handle="user/repo/a", installed_name="a")]
        )
        assert lockfile.remove_entry("user/repo/unknown") is False
        assert len(lockfile.skills) == 1

    def test_returns_true_on_ralph_match(self):
        lockfile = Lockfile(
            ralphs=[LockedEntry(handle="user/repo/r", installed_name="r")]
        )
        assert lockfile.remove_entry("user/repo/r", kind="ralph") is True
        assert len(lockfile.ralphs) == 0

    def test_returns_false_on_ralph_miss(self):
        lockfile = Lockfile(
            ralphs=[LockedEntry(handle="user/repo/r", installed_name="r")]
        )
        assert lockfile.remove_entry("user/repo/x", kind="ralph") is False
        assert len(lockfile.ralphs) == 1


class TestLockfileConfigConsistency:
    """Test that lockfile entries use the same identifiers as config dependencies.

    Regression: agr add --global ./local-skill wrote the raw relative ref to
    the lockfile (e.g. "./skills/my-skill") while the config dependency stored
    the resolved absolute path. This caused Lockfile.is_current() to report
    the lockfile as stale and Lockfile.find_entry() to miss the entry.
    """

    def test_lockfile_path_must_match_dependency_path(self):
        """Lockfile entry path must match the dependency identifier for lookups."""
        # Simulate a global add where the config stores the absolute path
        abs_path = "/home/user/projects/skills/my-skill"
        dep = Dependency(type="skill", path=abs_path)

        # Bug: lockfile entry was written with the raw relative ref
        lockfile_with_raw_ref = Lockfile(
            skills=[LockedEntry(path="./skills/my-skill", installed_name="my-skill")]
        )

        # The lockfile identifier doesn't match the dependency identifier
        assert lockfile_with_raw_ref.find_entry(dep) is None
        assert lockfile_with_raw_ref.is_current([dep]) is False

        # Fix: lockfile entry should use the same path as the dependency
        lockfile_with_resolved_path = Lockfile(
            skills=[LockedEntry(path=abs_path, installed_name="my-skill")]
        )

        assert lockfile_with_resolved_path.find_entry(dep) is not None
        assert lockfile_with_resolved_path.is_current([dep]) is True


class TestPackageLockfileSupport:
    """Tests for package entries in the lockfile."""

    def test_round_trip_package(self, tmp_path):
        lockfile = Lockfile(
            skills=[],
            ralphs=[],
            packages=[
                LockedEntry(
                    handle="user/repo/bundle",
                    source="github",
                    commit="e" * 40,
                    installed_name="bundle",
                ),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.packages) == 1
        assert len(loaded.skills) == 0
        assert len(loaded.ralphs) == 0
        p = loaded.packages[0]
        assert p.handle == "user/repo/bundle"
        assert p.source == "github"
        assert p.commit == "e" * 40
        assert p.installed_name == "bundle"

    def test_round_trip_multiple_parents(self, tmp_path):
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/shared",
                    installed_name="shared",
                    parents=["user/repo/bundle-a", "user/repo/bundle-b"],
                )
            ]
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert loaded.skills[0].parent_ids == {
            "user/repo/bundle-a",
            "user/repo/bundle-b",
        }

    def test_round_trip_mixed_all_types(self, tmp_path):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[
                LockedEntry(handle="user/repo/ralph", installed_name="ralph"),
            ],
            packages=[
                LockedEntry(handle="user/repo/bundle", installed_name="bundle"),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.skills) == 1
        assert len(loaded.ralphs) == 1
        assert len(loaded.packages) == 1

    def test_update_entry_package(self):
        lockfile = Lockfile()
        entry = LockedEntry(handle="user/repo/bundle", installed_name="bundle")
        lockfile.update_entry(entry, kind="package")
        assert len(lockfile.packages) == 1
        assert len(lockfile.skills) == 0
        assert lockfile.packages[0].handle == "user/repo/bundle"

    def test_remove_entry_package(self):
        lockfile = Lockfile(
            packages=[
                LockedEntry(handle="user/repo/a", installed_name="a"),
                LockedEntry(handle="user/repo/b", installed_name="b"),
            ],
        )
        lockfile.remove_entry("user/repo/a", kind="package")
        assert len(lockfile.packages) == 1
        assert lockfile.packages[0].handle == "user/repo/b"

    def test_find_entry_package(self):
        lockfile = Lockfile(
            packages=[
                LockedEntry(handle="user/repo/bundle", installed_name="bundle"),
            ],
        )
        dep = Dependency(type="package", handle="user/repo/bundle")
        result = lockfile.find_entry(dep)
        assert result is not None
        assert result.installed_name == "bundle"

    def test_find_entry_package_not_in_skills(self):
        """Package dep should not match entries in the skills list."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/bundle", installed_name="bundle"),
            ],
            packages=[],
        )
        dep = Dependency(type="package", handle="user/repo/bundle")
        result = lockfile.find_entry(dep)
        assert result is None

    def test_is_current_with_packages(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/skill", installed_name="skill"),
            ],
            packages=[
                LockedEntry(handle="user/repo/bundle", installed_name="bundle"),
            ],
        )
        deps = [
            Dependency(type="skill", handle="user/repo/skill"),
            Dependency(type="package", handle="user/repo/bundle"),
        ]
        assert lockfile.is_current(deps) is True

    def test_is_current_missing_package(self):
        lockfile = Lockfile(
            skills=[
                LockedEntry(handle="user/repo/skill", installed_name="skill"),
            ],
            packages=[],
        )
        deps = [
            Dependency(type="skill", handle="user/repo/skill"),
            Dependency(type="package", handle="user/repo/bundle"),
        ]
        assert lockfile.is_current(deps) is False

    def test_is_current_with_transitive_deps_from_packages(self):
        """Transitive deps (parent set) in lockfile should not cause
        is_current to return False when only direct deps are in config."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/direct-skill", installed_name="direct-skill"
                ),
                LockedEntry(
                    handle="pkg-owner/repo/transitive-skill",
                    installed_name="transitive-skill",
                    parent="user/repo/bundle",
                ),
            ],
            ralphs=[
                LockedEntry(
                    handle="pkg-owner/repo/transitive-ralph",
                    installed_name="transitive-ralph",
                    parent="user/repo/bundle",
                ),
            ],
            packages=[
                LockedEntry(handle="user/repo/bundle", installed_name="bundle"),
            ],
        )
        # Config only has the direct skill and the package — transitive
        # deps are expanded at sync time and not listed in agr.toml.
        deps = [
            Dependency(type="skill", handle="user/repo/direct-skill"),
            Dependency(type="package", handle="user/repo/bundle"),
        ]
        assert lockfile.is_current(deps) is True


class TestPackageClosure:
    """Tests for Lockfile.package_closure."""

    def test_empty_input_returns_empty_set(self):
        lockfile = Lockfile()
        assert lockfile.package_closure(set()) == set()

    def test_no_nested_packages_returns_input(self):
        lockfile = Lockfile(
            packages=[LockedEntry(handle="u/r/a", installed_name="a")],
        )
        assert lockfile.package_closure({"u/r/a"}) == {"u/r/a"}

    def test_expands_nested_packages(self):
        lockfile = Lockfile(
            packages=[
                LockedEntry(handle="u/r/outer", installed_name="outer"),
                LockedEntry(
                    handle="u/r/inner",
                    installed_name="inner",
                    parent="u/r/outer",
                ),
            ],
        )
        assert lockfile.package_closure({"u/r/outer"}) == {
            "u/r/outer",
            "u/r/inner",
        }

    def test_expands_multi_level_nesting(self):
        lockfile = Lockfile(
            packages=[
                LockedEntry(handle="u/r/a", installed_name="a"),
                LockedEntry(handle="u/r/b", installed_name="b", parent="u/r/a"),
                LockedEntry(handle="u/r/c", installed_name="c", parent="u/r/b"),
            ],
        )
        assert lockfile.package_closure({"u/r/a"}) == {
            "u/r/a",
            "u/r/b",
            "u/r/c",
        }


class TestParentFieldSupport:
    """Tests for the parent field on LockedEntry."""

    def test_parent_field_round_trip(self, tmp_path):
        """Parent field serializes and deserializes correctly."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/skill",
                    installed_name="skill",
                    parent="user/repo/bundle",
                ),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        loaded = load_lockfile(path)

        assert loaded is not None
        assert len(loaded.skills) == 1
        assert loaded.skills[0].parent == "user/repo/bundle"

    def test_parent_field_none_not_serialized(self, tmp_path):
        """Parent field with None is not written to lockfile."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/skill",
                    installed_name="skill",
                    parent=None,
                ),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        content = path.read_text()
        assert "parent" not in content

    def test_parent_field_present_in_toml(self, tmp_path):
        """Parent field is present in TOML output."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/skill",
                    installed_name="skill",
                    parent="user/repo/bundle",
                ),
            ],
        )
        path = tmp_path / "agr.lock"
        save_lockfile(lockfile, path)
        content = path.read_text()
        assert 'parent = "user/repo/bundle"' in content


class TestBuildLockfileFromResults:
    """Tests for _build_lockfile_from_results."""

    def test_errored_local_dep_excluded_from_lockfile(self):
        """A local dependency that failed to sync must not appear in the lockfile.

        Regression: the local-dep branch in _build_lockfile_from_results
        unconditionally created a lockfile entry without checking the
        sync result status, unlike the remote-dep branch which correctly
        skips entries with SyncStatus.ERROR.
        """
        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", path="./good-skill"),
                Dependency(type="skill", path="./bad-skill"),
            ]
        )
        results = [
            SyncResult(SyncStatus.INSTALLED),
            SyncResult(SyncStatus.ERROR, error="not a valid skill"),
        ]

        lockfile = _build_lockfile_from_results(config, results, None)

        # Only the successfully installed local dep should be in the lockfile
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].path == "./good-skill"

    def test_parents_dict_sets_parent_field_on_lockfile_entries(self):
        """Transitive deps must have their parent field set in the lockfile.

        Regression: _run_install_pipeline computed the parents dict from
        package expansion but never forwarded it to
        _build_lockfile_from_results, so the parent field on skill/ralph
        lockfile entries was always None.  This broke
        ``agr upgrade <package>`` which relies on the parent field to
        identify transitive deps via _transitive_closure.
        """
        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="owner/repo/alpha"),
                Dependency(type="skill", handle="owner/repo/beta"),
            ]
        )
        results = [
            SyncResult.installed(
                commit="a" * 40,
                content_hash="sha256:aaa",
                source_name="github",
            ),
            SyncResult.installed(
                commit="b" * 40,
                content_hash="sha256:bbb",
                source_name="github",
            ),
        ]
        parents = {
            "owner/repo/alpha": "owner/repo/bundle",
            "owner/repo/beta": "owner/repo/bundle",
        }
        parent_sets = {
            "owner/repo/alpha": {"owner/repo/bundle", "owner/repo/other"},
            "owner/repo/beta": {"owner/repo/bundle"},
        }

        lockfile = _build_lockfile_from_results(
            config, results, None, parents=parents, parent_sets=parent_sets
        )

        assert len(lockfile.skills) == 2
        alpha = next(
            entry
            for entry in lockfile.skills
            if entry.handle is not None and entry.handle.endswith("alpha")
        )
        beta = next(
            entry
            for entry in lockfile.skills
            if entry.handle is not None and entry.handle.endswith("beta")
        )
        assert alpha.parent_ids == {"owner/repo/bundle", "owner/repo/other"}
        assert beta.parent_ids == {"owner/repo/bundle"}

    def test_run_install_pipeline_forwards_parents_to_lockfile(self):
        """_run_install_pipeline must forward expanded.parents to lockfile builder.

        Regression: the parents dict from package expansion was computed
        but only used for display labels, not passed to
        _build_lockfile_from_results, so transitive dependency entries
        never had their parent field set in the lockfile.
        """
        from unittest.mock import patch, MagicMock
        from agr.commands.sync import _run_install_pipeline
        from agr.package import ExpandedDeps

        # A config with one package dep that expands into one skill
        config = AgrConfig(
            dependencies=[
                Dependency(type="package", handle="owner/repo/bundle"),
            ]
        )

        expanded = ExpandedDeps(
            dependencies=[
                Dependency(type="skill", handle="owner/repo/alpha"),
            ],
            parents={"owner/repo/alpha": "owner/repo/bundle"},
            package_entries=[
                LockedEntry(
                    handle="owner/repo/bundle",
                    source="github",
                    commit="c" * 40,
                    installed_name="bundle",
                ),
            ],
        )

        lockfile_path = MagicMock()
        repo_root = MagicMock()
        tools = []
        resolver = MagicMock()

        saved_lockfile = {}

        def capture_save(lf, path):
            saved_lockfile["lockfile"] = lf

        with (
            patch("agr.commands.sync.expand_packages", return_value=expanded),
            patch(
                "agr.commands.sync.detect_conflicts",
                side_effect=lambda deps, parents, direct_ids: deps,
            ),
            patch("agr.commands.sync._classify_dependencies") as mock_classify,
            patch("agr.commands.sync.save_lockfile", side_effect=capture_save),
            patch("agr.commands.sync._print_results_and_summary"),
        ):
            # _classify_dependencies returns all deps as up-to-date
            # (no pending installs) so no actual install work happens.
            from agr.commands.sync import _ClassifiedDeps

            mock_classify.return_value = _ClassifiedDeps(
                results=[
                    SyncResult.installed(
                        commit="a" * 40,
                        content_hash="sha256:aaa",
                        source_name="github",
                    )
                ],
                pending_local=[],
                pending_remote=[],
                pending_ralph=[],
            )

            _run_install_pipeline(
                config, lockfile_path, repo_root, tools, resolver, None
            )

        lockfile = saved_lockfile["lockfile"]
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].parent == "owner/repo/bundle", (
            f"Expected parent='owner/repo/bundle', "
            f"got parent={lockfile.skills[0].parent!r}. "
            "The parents dict from package expansion is not forwarded "
            "to _build_lockfile_from_results."
        )

    def test_carried_forward_entry_updates_stale_parent(self):
        """Carried-forward lockfile entries must reflect the current parent.

        When a dependency transitions from transitive (parent set) to
        direct (parent None), the carried-forward lockfile entry must
        drop the stale parent field.  Otherwise ``is_current()`` excludes
        the entry (it filters out entries with a parent) and falsely
        reports the lockfile as out of date.
        """
        # Existing lockfile has skill S as a transitive dep (parent set).
        existing_lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="owner/repo/skill-s",
                    source="github",
                    commit="a" * 40,
                    content_hash="sha256:aaa",
                    installed_name="skill-s",
                    parent="owner/repo/bundle",
                ),
            ]
        )

        # Config now lists skill S as a direct dep (no parent).
        config = AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="owner/repo/skill-s"),
            ]
        )

        # S is already installed — up to date, not freshly installed.
        results = [SyncResult.up_to_date()]

        # No parents dict — S is direct now, not transitive.
        lockfile = _build_lockfile_from_results(
            config, results, existing_lockfile, parents={}
        )

        assert len(lockfile.skills) == 1
        entry = lockfile.skills[0]
        assert entry.handle == "owner/repo/skill-s"
        # The parent must be None because S is now a direct dep.
        assert entry.parent is None, (
            f"Expected parent=None for direct dep, got parent={entry.parent!r}. "
            "Carried-forward lockfile entries must update the parent field "
            "when a dep transitions from transitive to direct."
        )


class TestInstalledEntries:
    """Tests for Lockfile.installed_entries()."""

    def test_empty_lockfile(self):
        lockfile = Lockfile()
        assert list(lockfile.installed_entries()) == []

    def test_skills_only(self):
        skill = LockedEntry(handle="user/repo/skill", installed_name="skill")
        lockfile = Lockfile(skills=[skill])
        assert list(lockfile.installed_entries()) == [skill]

    def test_ralphs_only(self):
        ralph = LockedEntry(handle="user/repo/ralph", installed_name="ralph")
        lockfile = Lockfile(ralphs=[ralph])
        assert list(lockfile.installed_entries()) == [ralph]

    def test_skills_and_ralphs(self):
        skill = LockedEntry(handle="user/repo/skill", installed_name="skill")
        ralph = LockedEntry(handle="user/repo/ralph", installed_name="ralph")
        lockfile = Lockfile(skills=[skill], ralphs=[ralph])
        assert list(lockfile.installed_entries()) == [skill, ralph]

    def test_excludes_packages(self):
        skill = LockedEntry(handle="user/repo/skill", installed_name="skill")
        ralph = LockedEntry(handle="user/repo/ralph", installed_name="ralph")
        package = LockedEntry(handle="user/repo/bundle", installed_name="bundle")
        lockfile = Lockfile(skills=[skill], ralphs=[ralph], packages=[package])
        result = list(lockfile.installed_entries())
        assert result == [skill, ralph]
        assert package not in result

    def test_preserves_order_skills_then_ralphs(self):
        s1 = LockedEntry(handle="user/repo/s1", installed_name="s1")
        s2 = LockedEntry(handle="user/repo/s2", installed_name="s2")
        r1 = LockedEntry(handle="user/repo/r1", installed_name="r1")
        lockfile = Lockfile(skills=[s1, s2], ralphs=[r1])
        assert list(lockfile.installed_entries()) == [s1, s2, r1]


class TestSyncFromLockfilePackages:
    """Tests for frozen/locked package installs."""

    def test_sync_from_lockfile_installs_transitive_package_children(self):
        config = AgrConfig(
            dependencies=[
                Dependency(type="package", handle="owner/repo/bundle"),
            ]
        )
        lockfile = Lockfile(
            packages=[
                LockedEntry(
                    handle="owner/repo/bundle",
                    source="github",
                    commit="c" * 40,
                    installed_name="bundle",
                )
            ],
            skills=[
                LockedEntry(
                    handle="owner/repo/child-skill",
                    source="github",
                    commit="a" * 40,
                    installed_name="child-skill",
                    parent="owner/repo/bundle",
                )
            ],
            ralphs=[
                LockedEntry(
                    handle="owner/repo/child-ralph",
                    source="github",
                    commit="b" * 40,
                    installed_name="child-ralph",
                    parent="owner/repo/bundle",
                )
            ],
        )
        synced: list[str] = []

        def fake_sync(dep, *_args):
            synced.append(dep.identifier)
            return SyncResult.installed()

        with (
            patch("agr.commands.sync._sync_dep_from_lockfile", side_effect=fake_sync),
            patch("agr.commands.sync._print_results_and_summary"),
        ):
            _sync_from_lockfile(
                lockfile,
                config,
                MagicMock(),
                [],
                MagicMock(),
            )

        assert synced == ["owner/repo/child-skill", "owner/repo/child-ralph"]
