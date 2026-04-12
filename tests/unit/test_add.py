"""Unit tests for agr.commands.add."""

from unittest.mock import MagicMock, patch

from agr._install_common import InstallResult
from agr.exceptions import RalphNotFoundError, SkillNotFoundError
from agr.commands.add import (
    AddInstallResult,
    _install_dependency,
    _install_package,
    _update_lockfile_for_adds,
)
from agr.config import AgrConfig, Dependency
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
