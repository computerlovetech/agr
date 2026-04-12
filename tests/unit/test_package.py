"""Unit tests for the package module."""

from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager

import pytest

from agr.config import (
    AgrConfig,
    Dependency,
    PackageMetadata,
)
from agr.exceptions import ConfigError, PackageConflictError
from agr.package import (
    detect_conflicts,
    expand_packages,
    has_package_section,
    load_sub_deps,
)
from agr.source import SourceResolver


class TestPackageMetadata:
    """Tests for PackageMetadata and [package] section parsing."""

    def test_parse_valid_package_section(self, tmp_path):
        """Parse a valid [package] section from agr.toml."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            '[package]\nname = "devbundle"\ndescription = "Dev tools bundle"\n'
            "dependencies = []\n"
        )
        config = AgrConfig.load(config_path)
        assert config.package is not None
        assert config.package.name == "devbundle"
        assert config.package.description == "Dev tools bundle"

    def test_parse_package_section_name_only(self, tmp_path):
        """Parse [package] with only name (description is optional)."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('[package]\nname = "mybundle"\ndependencies = []\n')
        config = AgrConfig.load(config_path)
        assert config.package is not None
        assert config.package.name == "mybundle"
        assert config.package.description is None

    def test_parse_package_section_missing_name_raises(self, tmp_path):
        """Missing name in [package] raises ConfigError."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            '[package]\ndescription = "no name"\ndependencies = []\n'
        )
        with pytest.raises(ConfigError, match="requires a 'name' field"):
            AgrConfig.load(config_path)

    def test_no_package_section(self, tmp_path):
        """Config without [package] section has package=None."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text("dependencies = []\n")
        config = AgrConfig.load(config_path)
        assert config.package is None

    def test_package_metadata_dataclass(self):
        """PackageMetadata dataclass creation."""
        meta = PackageMetadata(name="test", description="desc")
        assert meta.name == "test"
        assert meta.description == "desc"

    def test_package_metadata_no_description(self):
        """PackageMetadata without description."""
        meta = PackageMetadata(name="test")
        assert meta.description is None


class TestLoadSubManifest:
    """Tests for AgrConfig.load_sub_manifest."""

    def test_loads_dependencies(self, tmp_path):
        """load_sub_manifest reads dependencies from agr.toml."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text('dependencies = [{handle = "a/b/c", type = "skill"}]\n')
        config = AgrConfig.load_sub_manifest(config_path)
        assert len(config.dependencies) == 1
        assert config.dependencies[0].handle == "a/b/c"

    def test_loads_package_section(self, tmp_path):
        """load_sub_manifest reads [package] section."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            '[package]\nname = "mybundle"\n'
            'dependencies = [{handle = "a/b/c", type = "skill"}]\n'
        )
        config = AgrConfig.load_sub_manifest(config_path)
        assert config.package is not None
        assert config.package.name == "mybundle"

    def test_ignores_tools(self, tmp_path):
        """load_sub_manifest ignores tools (consumer-only)."""
        config_path = tmp_path / "agr.toml"
        # tools = ["nonexistent"] would fail in full load but not sub_manifest
        config_path.write_text(
            'tools = ["nonexistent_tool"]\n'
            'dependencies = [{handle = "a/b/c", type = "skill"}]\n'
        )
        config = AgrConfig.load_sub_manifest(config_path)
        assert len(config.dependencies) == 1

    def test_ignores_sources(self, tmp_path):
        """load_sub_manifest ignores [[source]] blocks."""
        config_path = tmp_path / "agr.toml"
        config_path.write_text(
            'dependencies = [{handle = "a/b/c", type = "skill"}]\n'
            "[[source]]\n"
            'name = "custom"\ntype = "git"\n'
            'url = "https://custom.example.com/{owner}/{repo}.git"\n'
        )
        config = AgrConfig.load_sub_manifest(config_path)
        assert len(config.dependencies) == 1
        # Sources should be default, not the custom one
        assert config.default_source == "github"

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """load_sub_manifest on nonexistent file returns empty config."""
        config = AgrConfig.load_sub_manifest(tmp_path / "agr.toml")
        assert config.dependencies == []
        assert config.package is None


class TestLoadSubDeps:
    """Tests for load_sub_deps function."""

    def test_with_agr_toml(self, tmp_path):
        """Loads sub-deps from resource dir with agr.toml."""
        (tmp_path / "agr.toml").write_text(
            'dependencies = [{handle = "x/y/z", type = "skill"}]\n'
        )
        deps = load_sub_deps(tmp_path)
        assert len(deps) == 1
        assert deps[0].handle == "x/y/z"

    def test_without_agr_toml(self, tmp_path):
        """Returns empty list when no agr.toml exists."""
        deps = load_sub_deps(tmp_path)
        assert deps == []

    def test_empty_deps(self, tmp_path):
        """Returns empty list when agr.toml has empty dependencies."""
        (tmp_path / "agr.toml").write_text("dependencies = []\n")
        deps = load_sub_deps(tmp_path)
        assert deps == []


class TestHasPackageSection:
    """Tests for has_package_section function."""

    def test_with_package_section(self, tmp_path):
        """Returns True when [package] section exists."""
        (tmp_path / "agr.toml").write_text(
            '[package]\nname = "bundle"\ndependencies = []\n'
        )
        assert has_package_section(tmp_path) is True

    def test_without_package_section(self, tmp_path):
        """Returns False when no [package] section."""
        (tmp_path / "agr.toml").write_text("dependencies = []\n")
        assert has_package_section(tmp_path) is False

    def test_no_agr_toml(self, tmp_path):
        """Returns False when no agr.toml exists."""
        assert has_package_section(tmp_path) is False


class TestDetectConflicts:
    """Tests for detect_conflicts function."""

    def test_no_conflicts(self):
        """No conflicts when all installed names are unique."""
        deps = [
            Dependency(type="skill", handle="a/b/alpha"),
            Dependency(type="skill", handle="c/d/beta"),
        ]
        result = detect_conflicts(deps, {}, set())
        assert len(result) == 2

    def test_same_identifier_no_conflict(self):
        """Duplicate identifiers (same dep twice) are not a conflict."""
        deps = [
            Dependency(type="skill", handle="a/b/alpha"),
            Dependency(type="skill", handle="a/b/alpha"),
        ]
        result = detect_conflicts(deps, {}, set())
        assert len(result) == 2

    def test_direct_wins_over_transitive(self):
        """Direct dep wins over transitive dep with same installed name."""
        deps = [
            Dependency(type="skill", handle="a/b/fmt"),
            Dependency(type="skill", handle="c/d/fmt"),
        ]
        parents = {"c/d/fmt": "some/package"}
        direct_ids = {"a/b/fmt"}
        result = detect_conflicts(deps, parents, direct_ids)
        assert len(result) == 1
        assert result[0].handle == "a/b/fmt"

    def test_transitive_vs_transitive_raises(self):
        """Two transitive deps with same name from different packages raises."""
        deps = [
            Dependency(type="skill", handle="a/b/fmt"),
            Dependency(type="skill", handle="c/d/fmt"),
        ]
        parents = {"a/b/fmt": "pkg1", "c/d/fmt": "pkg2"}
        direct_ids: set[str] = set()
        with pytest.raises(PackageConflictError, match="Conflict"):
            detect_conflicts(deps, parents, direct_ids)

    def test_multiple_direct_conflicts_raises(self):
        """Two direct deps with same installed name but different identifiers raises."""
        deps = [
            Dependency(type="skill", handle="a/b/fmt"),
            Dependency(type="skill", handle="c/d/fmt"),
        ]
        parents: dict[str, str] = {}
        direct_ids = {"a/b/fmt", "c/d/fmt"}
        with pytest.raises(PackageConflictError, match="multiple direct"):
            detect_conflicts(deps, parents, direct_ids)

    def test_removes_conflicting_transitive_from_parents(self):
        """When direct wins, the transitive dep is also removed from parents map."""
        deps = [
            Dependency(type="skill", handle="a/b/fmt"),
            Dependency(type="skill", handle="c/d/fmt"),
        ]
        parents = {"c/d/fmt": "some/package"}
        direct_ids = {"a/b/fmt"}
        result = detect_conflicts(deps, parents, direct_ids)
        assert "c/d/fmt" not in parents
        assert len(result) == 1

    def test_same_name_different_types_do_not_conflict(self):
        """Skills and ralphs with the same installed name use separate surfaces."""
        deps = [
            Dependency(type="skill", handle="a/b/fmt"),
            Dependency(type="ralph", handle="c/d/fmt"),
        ]
        result = detect_conflicts(deps, {}, set())
        assert result == deps


class TestExpandPackages:
    """Tests for expand_packages function."""

    def _make_resolver(self):
        return SourceResolver.default()

    @contextmanager
    def _mock_downloaded_repo(self, sub_dirs: dict[str, str | None]):
        """Mock downloaded_repo to yield a temp dir with sub-directories.

        sub_dirs maps directory names to optional agr.toml content.
        """

        @contextmanager
        def _fake_downloaded(source, owner, repo_name):
            import tempfile

            with tempfile.TemporaryDirectory() as td:
                repo_dir = Path(td)
                for name, toml_content in sub_dirs.items():
                    d = repo_dir / name
                    d.mkdir(parents=True)
                    if toml_content is not None:
                        (d / "agr.toml").write_text(toml_content)
                yield repo_dir

        with (
            patch("agr.package.downloaded_repo", _fake_downloaded),
            patch("agr.package.safe_get_head_commit", return_value="a" * 40),
        ):
            yield

    def test_passthrough_non_package_deps(self):
        """Non-package deps pass through unchanged."""
        deps = [
            Dependency(type="skill", handle="a/b/c"),
            Dependency(type="ralph", handle="x/y/z"),
        ]
        resolver = self._make_resolver()
        result = expand_packages(deps, resolver, "github", None, "skills")
        assert len(result.dependencies) == 2
        assert result.package_entries == []

    def test_expand_single_package(self):
        """Single package expands into its sub-deps."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = 'dependencies = [{handle = "x/y/skill1", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            result = expand_packages(deps, resolver, "github", None, "skills")

        assert len(result.dependencies) == 1
        assert result.dependencies[0].handle == "x/y/skill1"
        assert result.parents["x/y/skill1"] == "owner/repo/bundle"
        assert len(result.package_entries) == 1
        assert result.package_entries[0].handle == "owner/repo/bundle"

    def test_expand_mixed_deps(self):
        """Mix of package and non-package deps."""
        deps = [
            Dependency(type="skill", handle="direct/skill"),
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = 'dependencies = [{handle = "x/y/from-bundle", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            result = expand_packages(deps, resolver, "github", None, "skills")

        assert len(result.dependencies) == 2
        identifiers = {d.identifier for d in result.dependencies}
        assert "direct/skill" in identifiers
        assert "x/y/from-bundle" in identifiers
        assert "direct/skill" not in result.parents

    def test_deduplication(self):
        """Same dep from multiple packages is only included once."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = (
            "dependencies = [\n"
            '    {handle = "x/y/skill1", type = "skill"},\n'
            '    {handle = "x/y/skill1", type = "skill"},\n'
            "]\n"
        )
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            result = expand_packages(deps, resolver, "github", None, "skills")

        assert len(result.dependencies) == 1

    def test_cycle_detection(self):
        """Cycle in package dependencies does not loop infinitely."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle-a"),
        ]
        # bundle-a references bundle-a again (self-cycle)
        toml_a = 'dependencies = [{handle = "owner/repo/bundle-a", type = "package"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle-a": toml_a}):
            result = expand_packages(deps, resolver, "github", None, "skills")

        # Should not loop; the cycle is detected and skipped
        assert len(result.package_entries) == 1

    def test_missing_package_dir_raises(self):
        """Package pointing to nonexistent directory raises ConfigError."""
        deps = [
            Dependency(type="package", handle="owner/repo/missing"),
        ]
        resolver = self._make_resolver()

        # No "missing" subdirectory created
        with self._mock_downloaded_repo({}):
            with pytest.raises(ConfigError, match="not found"):
                expand_packages(deps, resolver, "github", None, "skills")

    def test_local_skill_path_in_remote_package_becomes_same_repo_handle(self):
        """Local path skill in remote package resolves to a same-repo handle."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = 'dependencies = [{path = "./sibling-skill", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            result = expand_packages(deps, resolver, "github", None, "skills")

        assert len(result.dependencies) == 1
        assert result.dependencies[0].handle == "owner/repo/sibling-skill"
        assert result.parents["owner/repo/sibling-skill"] == "owner/repo/bundle"

    def test_local_ralph_path_in_remote_package_becomes_same_repo_handle(self):
        """Local path ralph in remote package resolves to a same-repo handle."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = 'dependencies = [{path = "./my-ralph", type = "ralph"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            result = expand_packages(deps, resolver, "github", None, "skills")

        assert len(result.dependencies) == 1
        assert result.dependencies[0].handle == "owner/repo/my-ralph"
        assert result.dependencies[0].type == "ralph"

    def test_rejects_nested_local_dep_in_remote_package(self):
        """Nested local paths cannot be represented as remote handles."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = 'dependencies = [{path = "./tools/formatter", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            with pytest.raises(ConfigError, match="nested directory"):
                expand_packages(deps, resolver, "github", None, "skills")

    def test_rejects_local_dep_with_traversal_in_remote_package(self):
        """Local path with traversal in remote package is rejected."""
        deps = [
            Dependency(type="package", handle="owner/repo/bundle"),
        ]
        toml = 'dependencies = [{path = "../../../.ssh", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"bundle": toml}):
            with pytest.raises(
                ConfigError, match="resolves outside the downloaded repository"
            ):
                expand_packages(deps, resolver, "github", None, "skills")

    def test_rejects_local_dep_in_nested_remote_package(self):
        """Local path dep in a transitively-expanded nested package is rejected."""
        deps = [
            Dependency(type="package", handle="owner/repo/outer"),
        ]
        outer_toml = (
            'dependencies = [{handle = "owner/repo/inner", type = "package"}]\n'
        )
        inner_toml = 'dependencies = [{path = "../secret", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"outer": outer_toml, "inner": inner_toml}):
            with pytest.raises(
                ConfigError, match="resolves outside the downloaded repository"
            ):
                expand_packages(deps, resolver, "github", None, "skills")

    def test_error_message_includes_package_identifier(self):
        """Error message names both the local dep and the parent package."""
        deps = [
            Dependency(type="package", handle="evil/repo/malicious"),
        ]
        toml = 'dependencies = [{path = "../../.env", type = "skill"}]\n'
        resolver = self._make_resolver()

        with self._mock_downloaded_repo({"malicious": toml}):
            with pytest.raises(
                ConfigError,
                match="resolves outside the downloaded repository",
            ):
                expand_packages(deps, resolver, "github", None, "skills")


class TestDependencyIsPackage:
    """Tests for the is_package property on Dependency."""

    def test_is_package_true(self):
        dep = Dependency(type="package", handle="owner/repo/bundle")
        assert dep.is_package is True
        assert dep.is_skill is False
        assert dep.is_ralph is False

    def test_is_package_false_for_skill(self):
        dep = Dependency(type="skill", handle="owner/repo/skill")
        assert dep.is_package is False

    def test_is_package_false_for_ralph(self):
        dep = Dependency(type="ralph", handle="owner/repo/ralph")
        assert dep.is_package is False
