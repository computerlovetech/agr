"""Unit tests for agr upgrade internals."""

from agr.commands.upgrade import _transitive_closure
from agr.lockfile import LockedEntry, Lockfile


class TestTransitiveClosure:
    """Tests for _transitive_closure used by `agr upgrade <package>`."""

    def test_direct_children_included(self):
        """Skills whose parent is the upgraded package are included."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/alpha",
                    installed_name="alpha",
                    parent="user/repo/bundle",
                ),
            ],
            packages=[
                LockedEntry(
                    handle="user/repo/bundle",
                    installed_name="bundle",
                ),
            ],
        )

        result = _transitive_closure(lockfile, {"user/repo/bundle"})

        assert "user/repo/alpha" in result

    def test_nested_package_children_included(self):
        """Skills from nested sub-packages must also be included.

        Given: top-bundle -> sub-bundle -> nested-skill
        When:  agr upgrade top-bundle
        Then:  nested-skill should be in the transitive closure

        Regression: _transitive_closure only checked one level of parent
        relationships without walking through intermediate package entries,
        so skills from nested packages were missed.
        """
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/direct-skill",
                    installed_name="direct-skill",
                    parent="user/repo/top-bundle",
                ),
                LockedEntry(
                    handle="user/repo/nested-skill",
                    installed_name="nested-skill",
                    parent="user/repo/sub-bundle",
                ),
            ],
            ralphs=[],
            packages=[
                LockedEntry(
                    handle="user/repo/top-bundle",
                    installed_name="top-bundle",
                ),
                LockedEntry(
                    handle="user/repo/sub-bundle",
                    installed_name="sub-bundle",
                    parent="user/repo/top-bundle",
                ),
            ],
        )

        result = _transitive_closure(lockfile, {"user/repo/top-bundle"})

        assert "user/repo/direct-skill" in result
        assert "user/repo/nested-skill" in result

    def test_nested_ralph_children_included(self):
        """Ralphs from nested sub-packages must also be included."""
        lockfile = Lockfile(
            skills=[],
            ralphs=[
                LockedEntry(
                    handle="user/repo/nested-ralph",
                    installed_name="nested-ralph",
                    parent="user/repo/sub-bundle",
                ),
            ],
            packages=[
                LockedEntry(
                    handle="user/repo/top-bundle",
                    installed_name="top-bundle",
                ),
                LockedEntry(
                    handle="user/repo/sub-bundle",
                    installed_name="sub-bundle",
                    parent="user/repo/top-bundle",
                ),
            ],
        )

        result = _transitive_closure(lockfile, {"user/repo/top-bundle"})

        assert "user/repo/nested-ralph" in result

    def test_unrelated_skills_excluded(self):
        """Skills from unrelated packages are not included."""
        lockfile = Lockfile(
            skills=[
                LockedEntry(
                    handle="user/repo/alpha",
                    installed_name="alpha",
                    parent="user/repo/bundle-a",
                ),
                LockedEntry(
                    handle="user/repo/beta",
                    installed_name="beta",
                    parent="user/repo/bundle-b",
                ),
            ],
            packages=[
                LockedEntry(
                    handle="user/repo/bundle-a",
                    installed_name="bundle-a",
                ),
                LockedEntry(
                    handle="user/repo/bundle-b",
                    installed_name="bundle-b",
                ),
            ],
        )

        result = _transitive_closure(lockfile, {"user/repo/bundle-a"})

        assert "user/repo/alpha" in result
        assert "user/repo/beta" not in result
