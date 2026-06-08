"""Unit tests for agr.commands.add."""

from unittest.mock import MagicMock, patch

from agr._install_common import InstallResult
from agr.exceptions import RalphNotFoundError, SkillNotFoundError
from agr.commands.add import (
    AddInstallResult,
    _detect_local_type,
    _install_dependency,
    _install_package,
    _update_lockfile_for_adds,
)
from agr.config import (
    DEPENDENCY_TYPE_RALPH,
    DEPENDENCY_TYPE_SKILL,
    AgrConfig,
    Dependency,
)
from agr.handle import ParsedHandle
from agr.lockfile import LockedEntry, load_lockfile
from agr.package import ExpandedDeps


class TestInstallPackage:
    """Tests for package add lockfile metadata."""

    def test_install_package_returns_lock_entries_for_package_and_children(self):
        expanded = ExpandedDeps(
            dependencies=[
                Dependency(type="skill", handle="owner/repo/child-skill"),
                Dependency(type="ralph", handle="owner/repo/child-ralph"),
            ],
            parents={
                "owner/repo/child-skill": "owner/repo/bundle",
                "owner/repo/child-ralph": "owner/repo/bundle",
            },
            package_entries=[
                LockedEntry(
                    handle="owner/repo/bundle",
                    source="github",
                    commit="c" * 40,
                    installed_name="bundle",
                )
            ],
        )

        with (
            patch("agr.commands.add.expand_packages", return_value=expanded),
            patch(
                "agr.commands.add.detect_conflicts",
                side_effect=lambda deps, parents, direct_ids: deps,
            ),
            patch(
                "agr.commands.add.fetch_and_install_to_tools",
                return_value=(
                    {"claude": MagicMock()},
                    InstallResult(
                        commit="a" * 40,
                        content_hash="sha256:aaa",
                        source_name="github",
                    ),
                ),
            ),
            patch(
                "agr.commands.add.fetch_and_install_ralph",
                return_value=(
                    MagicMock(),
                    InstallResult(
                        commit="b" * 40,
                        content_hash="sha256:bbb",
                        source_name="github",
                    ),
                ),
            ),
        ):
            result = _install_package(
                ParsedHandle(username="owner", repo="repo", name="bundle"),
                MagicMock(),
                [MagicMock()],
                False,
                MagicMock(),
                None,
                None,
                "skills",
                config=AgrConfig(),
            )

        assert result.dep_type == "package"
        assert result.lock_entries is not None
        entries = {
            (kind, entry.identifier): entry for kind, entry in result.lock_entries
        }
        assert ("package", "owner/repo/bundle") in entries
        assert entries[("skill", "owner/repo/child-skill")].commit == "a" * 40
        assert entries[("skill", "owner/repo/child-skill")].parent == (
            "owner/repo/bundle"
        )
        assert entries[("ralph", "owner/repo/child-ralph")].commit == "b" * 40
        assert entries[("ralph", "owner/repo/child-ralph")].parent == (
            "owner/repo/bundle"
        )

    def test_remote_ralph_fallback_skipped_when_flag_off(self, monkeypatch):
        """Off-path: remote add goes skill->package, never trying ralph."""
        monkeypatch.delenv("AGR_ENABLE_RALPH", raising=False)
        with (
            patch(
                "agr.commands.add.fetch_and_install_to_tools",
                side_effect=SkillNotFoundError("no skill"),
            ),
            patch(
                "agr.commands.add.fetch_and_install_ralph",
            ) as fetch_ralph,
            patch(
                "agr.commands.add._install_package",
                return_value=AddInstallResult([], InstallResult(), "package"),
            ) as install_package,
        ):
            result = _install_dependency(
                ParsedHandle(username="owner", repo="repo", name="bundle"),
                "skill",
                MagicMock(),
                [],
                False,
                MagicMock(),
                None,
                None,
                "skills",
                config=AgrConfig(),
            )

        assert result.dep_type == "package"
        install_package.assert_called_once()
        fetch_ralph.assert_not_called()

    def test_package_ralph_leaf_skipped_when_flag_off(self, monkeypatch):
        """Off-path: ralph leaves are silently dropped, skill leaves install."""
        monkeypatch.delenv("AGR_ENABLE_RALPH", raising=False)
        expanded = ExpandedDeps(
            dependencies=[
                Dependency(type="skill", handle="owner/repo/child-skill"),
                Dependency(type="ralph", handle="owner/repo/child-ralph"),
            ],
            parents={
                "owner/repo/child-skill": "owner/repo/bundle",
                "owner/repo/child-ralph": "owner/repo/bundle",
            },
            package_entries=[],
        )

        with (
            patch("agr.commands.add.expand_packages", return_value=expanded),
            patch(
                "agr.commands.add.detect_conflicts",
                side_effect=lambda deps, parents, direct_ids: deps,
            ),
            patch(
                "agr.commands.add.fetch_and_install_to_tools",
                return_value=(
                    {"claude": MagicMock()},
                    InstallResult(
                        commit="a" * 40,
                        content_hash="sha256:aaa",
                        source_name="github",
                    ),
                ),
            ) as fetch_skill,
            patch("agr.commands.add.fetch_and_install_ralph") as fetch_ralph,
        ):
            _install_package(
                ParsedHandle(username="owner", repo="repo", name="bundle"),
                MagicMock(),
                [MagicMock()],
                False,
                MagicMock(),
                None,
                None,
                "skills",
                config=AgrConfig(),
            )

        fetch_skill.assert_called_once()
        fetch_ralph.assert_not_called()

    def test_remote_dependency_falls_back_to_package(self):
        with (
            patch(
                "agr.commands.add.fetch_and_install_to_tools",
                side_effect=SkillNotFoundError("no skill"),
            ),
            patch(
                "agr.commands.add.fetch_and_install_ralph",
                side_effect=RalphNotFoundError("no ralph"),
            ),
            patch(
                "agr.commands.add._install_package",
                return_value=AddInstallResult([], InstallResult(), "package"),
            ) as install_package,
        ):
            result = _install_dependency(
                ParsedHandle(username="owner", repo="repo", name="bundle"),
                "skill",
                MagicMock(),
                [],
                False,
                MagicMock(),
                None,
                None,
                "skills",
                config=AgrConfig(),
            )

        assert result.dep_type == "package"
        install_package.assert_called_once()

    def test_package_add_prunes_child_that_conflicts_with_existing_direct_dep(self):
        expanded = ExpandedDeps(
            dependencies=[
                Dependency(type="skill", handle="other/repo/fmt"),
            ],
            parents={
                "other/repo/fmt": "owner/repo/bundle",
            },
            parent_sets={
                "other/repo/fmt": {"owner/repo/bundle"},
            },
            package_entries=[
                LockedEntry(
                    handle="owner/repo/bundle",
                    source="github",
                    commit="c" * 40,
                    installed_name="bundle",
                )
            ],
        )

        installed: list[str] = []

        def fake_install(handle, *_args, **_kwargs):
            installed.append(handle.to_toml_handle())
            return (
                {"claude": MagicMock()},
                InstallResult(
                    commit="a" * 40,
                    content_hash="sha256:aaa",
                    source_name="github",
                ),
            )

        with (
            patch("agr.commands.add.expand_packages", return_value=expanded),
            patch(
                "agr.commands.add.fetch_and_install_to_tools", side_effect=fake_install
            ),
        ):
            _install_package(
                ParsedHandle(username="owner", repo="repo", name="bundle"),
                MagicMock(),
                [MagicMock()],
                False,
                MagicMock(),
                None,
                None,
                "skills",
                config=AgrConfig(
                    dependencies=[
                        Dependency(type="skill", handle="owner/repo/fmt"),
                    ]
                ),
            )

        assert installed == []


class TestUpdateLockfileForAdds:
    def test_package_add_writes_supplied_package_and_child_entries(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []\n")
        entries = [
            (
                "package",
                LockedEntry(
                    handle="owner/repo/bundle",
                    source="github",
                    commit="c" * 40,
                    installed_name="bundle",
                ),
            ),
            (
                "skill",
                LockedEntry(
                    handle="owner/repo/child",
                    source="github",
                    commit="a" * 40,
                    installed_name="child",
                    parent="owner/repo/bundle",
                ),
            ),
        ]

        _update_lockfile_for_adds(
            [
                (
                    ParsedHandle(username="owner", repo="repo", name="bundle"),
                    "owner/repo/bundle",
                    InstallResult(commit="wrong"),
                    "package",
                    entries,
                )
            ],
            config_path,
        )

        lockfile = load_lockfile(tmp_path / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.packages) == 1
        assert lockfile.packages[0].commit == "c" * 40
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].parent == "owner/repo/bundle"

    def test_package_handle_not_rewritten_with_subdep_repo(self, tmp_path):
        """Package handles must not be promoted using a sub-dep's repo.

        When a package pulls in transitive skills from a different repo,
        ``install_result.resolved_repo`` holds the sub-dep's repo — NOT the
        package's own. Applying ``with_repo(resolved_repo)`` to the package
        handle would write a reference to a repo that doesn't contain the
        package.
        """
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []\n")

        # No lock_entries supplied — triggers the direct-add branch in
        # _update_lockfile_for_adds where the handle rewrite happens.
        _update_lockfile_for_adds(
            [
                (
                    # User typed "owner/bundle" (shorthand, repo=None).
                    ParsedHandle(username="owner", name="bundle"),
                    "owner/bundle",
                    # InstallResult carries the first sub-dep's resolved_repo,
                    # which is "skills" — the sub-dep lives there but the
                    # package does not.
                    InstallResult(
                        commit="c" * 40,
                        content_hash="sha256:ccc",
                        source_name="github",
                        resolved_repo="skills",
                    ),
                    "package",
                    None,
                )
            ],
            config_path,
        )

        lockfile = load_lockfile(tmp_path / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.packages) == 1
        # Must not be "owner/skills/bundle" (that would be the sub-dep's repo).
        assert lockfile.packages[0].handle == "owner/bundle"

    def test_skill_handle_rewritten_with_resolved_repo(self, tmp_path):
        """Direct skill adds persist the 3-part resolved handle."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []\n")

        _update_lockfile_for_adds(
            [
                (
                    ParsedHandle(username="owner", name="my-skill"),
                    "owner/my-skill",
                    InstallResult(
                        commit="c" * 40,
                        content_hash="sha256:ccc",
                        source_name="github",
                        resolved_repo="skills",
                    ),
                    "skill",
                    None,
                )
            ],
            config_path,
        )

        lockfile = load_lockfile(tmp_path / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].handle == "owner/skills/my-skill"


class TestDetectLocalTypeFeatureGate:
    """Off-path: a local RALPH.md dir is invisible when the flag is off."""

    def test_ralph_dir_detected_as_skill_when_flag_off(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AGR_ENABLE_RALPH", raising=False)
        (tmp_path / "RALPH.md").write_text("# ralph\n")

        assert _detect_local_type(tmp_path) == DEPENDENCY_TYPE_SKILL

    def test_ralph_dir_detected_as_ralph_when_flag_on(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGR_ENABLE_RALPH", "1")
        (tmp_path / "RALPH.md").write_text("# ralph\n")

        assert _detect_local_type(tmp_path) == DEPENDENCY_TYPE_RALPH

    def test_both_markers_does_not_raise_when_flag_off(self, tmp_path, monkeypatch):
        """With ralph gated off, a both-markers dir is just a skill (no error)."""
        monkeypatch.delenv("AGR_ENABLE_RALPH", raising=False)
        (tmp_path / "RALPH.md").write_text("# ralph\n")
        (tmp_path / "SKILL.md").write_text("# skill\n")

        assert _detect_local_type(tmp_path) == DEPENDENCY_TYPE_SKILL
