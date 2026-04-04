"""Unit tests for the lockfile module."""

import pytest

from agr.config import Dependency
from agr.exceptions import ConfigError
from agr.lockfile import (
    LOCKFILE_VERSION,
    LockedSkill,
    Lockfile,
    build_lockfile_path,
    find_locked_skill,
    is_lockfile_current,
    load_lockfile,
    remove_lockfile_entry,
    save_lockfile,
    update_lockfile_entry,
)


class TestLockedSkill:
    def test_remote_skill_identifier(self):
        skill = LockedSkill(
            handle="user/repo/skill",
            source="github",
            commit="abc123",
            content_hash="sha256:def456",
            installed_name="skill",
        )
        assert skill.identifier == "user/repo/skill"
        assert not skill.is_local

    def test_local_skill_identifier(self):
        skill = LockedSkill(path="./local/skill", installed_name="skill")
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
                LockedSkill(
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
                LockedSkill(path="./local/my-skill", installed_name="my-skill"),
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
                LockedSkill(
                    handle="user/repo/skill",
                    source="github",
                    commit="a" * 40,
                    content_hash="sha256:" + "b" * 64,
                    installed_name="skill",
                ),
                LockedSkill(path="./local/other", installed_name="other"),
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


class TestFindLockedSkill:
    def test_find_by_handle(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/a", installed_name="a"),
                LockedSkill(handle="user/repo/b", installed_name="b"),
            ]
        )
        dep = Dependency(type="skill", handle="user/repo/b")
        result = find_locked_skill(lockfile, dep)
        assert result is not None
        assert result.installed_name == "b"

    def test_find_by_path(self):
        lockfile = Lockfile(
            skills=[LockedSkill(path="./local/skill", installed_name="skill")]
        )
        dep = Dependency(type="skill", path="./local/skill")
        result = find_locked_skill(lockfile, dep)
        assert result is not None
        assert result.installed_name == "skill"

    def test_returns_none_for_unknown(self):
        lockfile = Lockfile(
            skills=[LockedSkill(handle="user/repo/a", installed_name="a")]
        )
        dep = Dependency(type="skill", handle="user/repo/unknown")
        assert find_locked_skill(lockfile, dep) is None

    def test_returns_none_for_empty_lockfile(self):
        lockfile = Lockfile(skills=[])
        dep = Dependency(type="skill", handle="user/repo/skill")
        assert find_locked_skill(lockfile, dep) is None


class TestIsLockfileCurrent:
    def test_matching_deps(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/a", installed_name="a"),
                LockedSkill(path="./local/b", installed_name="b"),
            ]
        )
        deps = [
            Dependency(type="skill", handle="user/repo/a"),
            Dependency(type="skill", path="./local/b"),
        ]
        assert is_lockfile_current(lockfile, deps) is True

    def test_extra_in_lockfile(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/a", installed_name="a"),
                LockedSkill(handle="user/repo/b", installed_name="b"),
            ]
        )
        deps = [Dependency(type="skill", handle="user/repo/a")]
        assert is_lockfile_current(lockfile, deps) is False

    def test_missing_from_lockfile(self):
        lockfile = Lockfile(
            skills=[LockedSkill(handle="user/repo/a", installed_name="a")]
        )
        deps = [
            Dependency(type="skill", handle="user/repo/a"),
            Dependency(type="skill", handle="user/repo/b"),
        ]
        assert is_lockfile_current(lockfile, deps) is False

    def test_both_empty(self):
        assert is_lockfile_current(Lockfile(skills=[]), []) is True


class TestUpdateLockfileEntry:
    def test_adds_new_entry(self):
        lockfile = Lockfile(skills=[])
        entry = LockedSkill(handle="user/repo/a", installed_name="a")
        update_lockfile_entry(lockfile, entry)
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].handle == "user/repo/a"

    def test_replaces_existing_entry(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(
                    handle="user/repo/a",
                    commit="old",
                    installed_name="a",
                )
            ]
        )
        entry = LockedSkill(handle="user/repo/a", commit="new", installed_name="a")
        update_lockfile_entry(lockfile, entry)
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].commit == "new"

    def test_preserves_other_entries(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/a", installed_name="a"),
                LockedSkill(handle="user/repo/b", installed_name="b"),
            ]
        )
        entry = LockedSkill(handle="user/repo/a", commit="new", installed_name="a")
        update_lockfile_entry(lockfile, entry)
        assert len(lockfile.skills) == 2


class TestRemoveLockfileEntry:
    def test_removes_by_handle(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/a", installed_name="a"),
                LockedSkill(handle="user/repo/b", installed_name="b"),
            ]
        )
        remove_lockfile_entry(lockfile, "user/repo/a")
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].handle == "user/repo/b"

    def test_removes_by_path(self):
        lockfile = Lockfile(
            skills=[LockedSkill(path="./local/skill", installed_name="skill")]
        )
        remove_lockfile_entry(lockfile, "./local/skill")
        assert lockfile.skills == []

    def test_noop_for_unknown_identifier(self):
        lockfile = Lockfile(
            skills=[LockedSkill(handle="user/repo/a", installed_name="a")]
        )
        remove_lockfile_entry(lockfile, "user/repo/unknown")
        assert len(lockfile.skills) == 1


class TestRalphLockfileSupport:
    """Tests for ralph entries in the lockfile."""

    def test_round_trip_ralph(self, tmp_path):
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedSkill(
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
                LockedSkill(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[
                LockedSkill(handle="user/repo/ralph", installed_name="ralph"),
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
        entry = LockedSkill(handle="user/repo/ralph", installed_name="ralph")
        update_lockfile_entry(lockfile, entry, ralph=True)
        assert len(lockfile.ralphs) == 1
        assert len(lockfile.skills) == 0
        assert lockfile.ralphs[0].handle == "user/repo/ralph"

    def test_remove_lockfile_entry_ralph(self):
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedSkill(handle="user/repo/a", installed_name="a"),
                LockedSkill(handle="user/repo/b", installed_name="b"),
            ],
        )
        remove_lockfile_entry(lockfile, "user/repo/a", ralph=True)
        assert len(lockfile.ralphs) == 1
        assert lockfile.ralphs[0].handle == "user/repo/b"

    def test_find_locked_ralph(self):
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedSkill(handle="user/repo/ralph", installed_name="ralph"),
            ],
        )
        dep = Dependency(type="ralph", handle="user/repo/ralph")
        result = find_locked_skill(lockfile, dep)
        assert result is not None
        assert result.installed_name == "ralph"

    def test_find_locked_ralph_not_in_skills(self):
        """Ralph dep should not match entries in the skills list."""
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/ralph", installed_name="ralph"),
            ],
            ralphs=[],
        )
        dep = Dependency(type="ralph", handle="user/repo/ralph")
        result = find_locked_skill(lockfile, dep)
        assert result is None

    def test_is_lockfile_current_with_ralphs(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[
                LockedSkill(handle="user/repo/ralph", installed_name="ralph"),
            ],
        )
        deps = [
            Dependency(type="skill", handle="user/repo/skill"),
            Dependency(type="ralph", handle="user/repo/ralph"),
        ]
        assert is_lockfile_current(lockfile, deps) is True

    def test_is_lockfile_current_missing_ralph(self):
        lockfile = Lockfile(
            skills=[
                LockedSkill(handle="user/repo/skill", installed_name="skill"),
            ],
            ralphs=[],
        )
        deps = [
            Dependency(type="skill", handle="user/repo/skill"),
            Dependency(type="ralph", handle="user/repo/ralph"),
        ]
        assert is_lockfile_current(lockfile, deps) is False


class TestRemoveLockfileEntryReturnValue:
    """Tests for remove_lockfile_entry return value."""

    def test_returns_true_on_match(self):
        lockfile = Lockfile(
            skills=[LockedSkill(handle="user/repo/a", installed_name="a")]
        )
        assert remove_lockfile_entry(lockfile, "user/repo/a") is True
        assert len(lockfile.skills) == 0

    def test_returns_false_on_miss(self):
        lockfile = Lockfile(
            skills=[LockedSkill(handle="user/repo/a", installed_name="a")]
        )
        assert remove_lockfile_entry(lockfile, "user/repo/unknown") is False
        assert len(lockfile.skills) == 1

    def test_returns_true_on_ralph_match(self):
        lockfile = Lockfile(
            ralphs=[LockedSkill(handle="user/repo/r", installed_name="r")]
        )
        assert remove_lockfile_entry(lockfile, "user/repo/r", ralph=True) is True
        assert len(lockfile.ralphs) == 0

    def test_returns_false_on_ralph_miss(self):
        lockfile = Lockfile(
            ralphs=[LockedSkill(handle="user/repo/r", installed_name="r")]
        )
        assert remove_lockfile_entry(lockfile, "user/repo/x", ralph=True) is False
        assert len(lockfile.ralphs) == 1
