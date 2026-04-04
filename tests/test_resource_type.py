"""Tests for the ResourceType abstraction and generic resource discovery."""

import json
from pathlib import PurePosixPath

from agr.handle import ParsedHandle
from agr.metadata import (
    METADATA_FILENAME,
    METADATA_KEY_INSTALLED_NAME,
    METADATA_KEY_TOOL,
    METADATA_KEY_TYPE,
    METADATA_TYPE_REMOTE,
    write_resource_metadata,
    stamp_resource_metadata,
)
from agr.resource_type import RALPH_RESOURCE, SKILL_RESOURCE, ResourceType
from agr.skill import (
    SKILL_MARKER,
    _find_resource_dirs_in_listing,
    discover_resources_in_repo_listing,
    find_resource_in_repo,
    find_resource_in_repo_listing,
    find_resources_in_repo_listing,
    is_valid_resource_dir,
)


# ---------------------------------------------------------------------------
# ResourceType dataclass
# ---------------------------------------------------------------------------


class TestResourceType:
    def test_skill_resource(self):
        assert SKILL_RESOURCE.marker == "SKILL.md"
        assert SKILL_RESOURCE.name == "skill"
        assert SKILL_RESOURCE.has_tool_field is True

    def test_ralph_resource(self):
        assert RALPH_RESOURCE.marker == "RALPH.md"
        assert RALPH_RESOURCE.name == "ralph"
        assert RALPH_RESOURCE.has_tool_field is False

    def test_frozen(self):
        """ResourceType instances are immutable."""
        import pytest

        with pytest.raises(AttributeError):
            SKILL_RESOURCE.marker = "OTHER.md"  # type: ignore[misc]  # ty: ignore[invalid-assignment]

    def test_custom_resource_type(self):
        custom = ResourceType(marker="CUSTOM.md", name="custom", has_tool_field=False)
        assert custom.marker == "CUSTOM.md"


# ---------------------------------------------------------------------------
# Generic discovery functions with different markers
# ---------------------------------------------------------------------------

FAKE_MARKER = "FAKE.md"


class TestIsValidResourceDir:
    def test_valid_dir(self, tmp_path):
        d = tmp_path / "my-resource"
        d.mkdir()
        (d / FAKE_MARKER).write_text("# Fake")
        assert is_valid_resource_dir(d, FAKE_MARKER) is True

    def test_missing_marker(self, tmp_path):
        d = tmp_path / "my-resource"
        d.mkdir()
        assert is_valid_resource_dir(d, FAKE_MARKER) is False

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        assert is_valid_resource_dir(f, FAKE_MARKER) is False


class TestFindResourceInRepo:
    def test_finds_by_name(self, tmp_path):
        d = tmp_path / "resources" / "my-res"
        d.mkdir(parents=True)
        (d / FAKE_MARKER).write_text("# Fake")
        result = find_resource_in_repo(tmp_path, "my-res", FAKE_MARKER)
        assert result == d

    def test_returns_none_when_missing(self, tmp_path):
        result = find_resource_in_repo(tmp_path, "nonexistent", FAKE_MARKER)
        assert result is None

    def test_excludes_root_level(self, tmp_path):
        (tmp_path / FAKE_MARKER).write_text("# Root marker")
        result = find_resource_in_repo(tmp_path, tmp_path.name, FAKE_MARKER)
        assert result is None

    def test_excludes_node_modules(self, tmp_path):
        d = tmp_path / "node_modules" / "my-res"
        d.mkdir(parents=True)
        (d / FAKE_MARKER).write_text("# Fake")
        result = find_resource_in_repo(tmp_path, "my-res", FAKE_MARKER)
        assert result is None


class TestFindResourceDirsInListing:
    def test_finds_dirs(self):
        paths = ["foo/bar/FAKE.md", "baz/FAKE.md", "README.md"]
        result = _find_resource_dirs_in_listing(paths, FAKE_MARKER)
        assert PurePosixPath("foo/bar") in result
        assert PurePosixPath("baz") in result
        assert len(result) == 2

    def test_excludes_root(self):
        paths = ["FAKE.md"]
        result = _find_resource_dirs_in_listing(paths, FAKE_MARKER)
        assert result == []

    def test_excludes_excluded_dirs(self):
        paths = [".git/hooks/FAKE.md", "vendor/lib/FAKE.md", "ok/FAKE.md"]
        result = _find_resource_dirs_in_listing(paths, FAKE_MARKER)
        assert len(result) == 1
        assert result[0] == PurePosixPath("ok")


class TestFindResourceInRepoListing:
    def test_finds_by_name(self):
        paths = ["skills/commit/FAKE.md", "skills/review/FAKE.md"]
        result = find_resource_in_repo_listing(paths, "commit", FAKE_MARKER)
        assert result == PurePosixPath("skills/commit")

    def test_returns_none_when_missing(self):
        paths = ["skills/commit/FAKE.md"]
        result = find_resource_in_repo_listing(paths, "review", FAKE_MARKER)
        assert result is None


class TestFindResourcesInRepoListing:
    def test_finds_multiple(self):
        paths = ["a/FAKE.md", "b/FAKE.md", "c/FAKE.md"]
        result = find_resources_in_repo_listing(paths, ["a", "c"], FAKE_MARKER)
        assert set(result.keys()) == {"a", "c"}

    def test_omits_missing(self):
        paths = ["a/FAKE.md"]
        result = find_resources_in_repo_listing(paths, ["a", "b"], FAKE_MARKER)
        assert "a" in result
        assert "b" not in result


class TestDiscoverResourcesInRepoListing:
    def test_discovers_all(self):
        paths = ["x/FAKE.md", "y/FAKE.md", "z/FAKE.md"]
        result = discover_resources_in_repo_listing(paths, FAKE_MARKER)
        assert result == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# Unified metadata functions
# ---------------------------------------------------------------------------


class TestWriteResourceMetadata:
    def test_skill_metadata_includes_tool(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        handle = ParsedHandle(name="my-skill", username="owner", repo="repo")
        write_resource_metadata(
            d,
            handle,
            tmp_path,
            "my-skill",
            tool_name="claude",
            source="github",
        )
        data = json.loads((d / METADATA_FILENAME).read_text())
        assert data[METADATA_KEY_TOOL] == "claude"
        assert data[METADATA_KEY_INSTALLED_NAME] == "my-skill"
        assert data[METADATA_KEY_TYPE] == METADATA_TYPE_REMOTE

    def test_ralph_metadata_no_tool(self, tmp_path):
        d = tmp_path / "my-ralph"
        d.mkdir()
        handle = ParsedHandle(name="my-ralph", username="owner", repo="repo")
        write_resource_metadata(
            d,
            handle,
            tmp_path,
            "my-ralph",
            source="github",
        )
        data = json.loads((d / METADATA_FILENAME).read_text())
        assert METADATA_KEY_TOOL not in data
        assert data[METADATA_KEY_INSTALLED_NAME] == "my-ralph"


class TestStampResourceMetadata:
    def test_stamps_with_hash(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / SKILL_MARKER).write_text("# Skill")
        handle = ParsedHandle(name="my-skill", username="owner", repo="repo")
        stamp_resource_metadata(
            d,
            handle,
            tmp_path,
            "my-skill",
            tool_name="claude",
            source="github",
        )
        data = json.loads((d / METADATA_FILENAME).read_text())
        assert "content_hash" in data
        assert data["content_hash"].startswith("sha256:")
        assert data[METADATA_KEY_TOOL] == "claude"
