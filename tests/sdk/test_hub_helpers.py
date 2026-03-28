"""Unit tests for sdk/hub.py pure helper functions.

These functions are currently only tested indirectly through list_skills
and skill_info. Direct tests ensure they handle edge cases correctly.
"""

from agr.sdk.hub import (
    _build_display_handle,
    _extract_paths_from_tree,
    _find_skill_md_in_tree,
)
from agr.handle import DEFAULT_REPO_NAME


class TestBuildDisplayHandle:
    """Tests for _build_display_handle()."""

    def test_default_repo_uses_two_part_handle(self):
        """Skills in the default repo omit the repo name."""
        result = _build_display_handle("owner", DEFAULT_REPO_NAME, "commit")
        assert result == "owner/commit"

    def test_custom_repo_uses_three_part_handle(self):
        """Skills in a non-default repo include the repo name."""
        result = _build_display_handle("owner", "my-repo", "commit")
        assert result == "owner/my-repo/commit"

    def test_legacy_repo_uses_three_part_handle(self):
        """Skills in the legacy 'agent-resources' repo include the repo name."""
        result = _build_display_handle("owner", "agent-resources", "commit")
        assert result == "owner/agent-resources/commit"


class TestExtractPathsFromTree:
    """Tests for _extract_paths_from_tree()."""

    def test_extracts_blob_paths(self):
        tree_data = {
            "tree": [
                {"type": "blob", "path": "README.md"},
                {"type": "blob", "path": "skills/commit/SKILL.md"},
            ]
        }
        result = _extract_paths_from_tree(tree_data)
        assert result == ["README.md", "skills/commit/SKILL.md"]

    def test_excludes_tree_entries(self):
        """Only blob (file) entries are returned, not tree (directory) entries."""
        tree_data = {
            "tree": [
                {"type": "tree", "path": "skills"},
                {"type": "tree", "path": "skills/commit"},
                {"type": "blob", "path": "skills/commit/SKILL.md"},
            ]
        }
        result = _extract_paths_from_tree(tree_data)
        assert result == ["skills/commit/SKILL.md"]

    def test_empty_tree(self):
        assert _extract_paths_from_tree({"tree": []}) == []

    def test_missing_tree_key(self):
        assert _extract_paths_from_tree({}) == []

    def test_skips_entries_without_path(self):
        tree_data = {
            "tree": [
                {"type": "blob", "path": "valid.md"},
                {"type": "blob"},  # missing path
                {"type": "blob", "path": ""},  # empty path
            ]
        }
        result = _extract_paths_from_tree(tree_data)
        assert result == ["valid.md"]

    def test_skips_entries_without_type(self):
        tree_data = {
            "tree": [
                {"path": "no-type.md"},
                {"type": "blob", "path": "has-type.md"},
            ]
        }
        result = _extract_paths_from_tree(tree_data)
        assert result == ["has-type.md"]


class TestFindSkillMdInTree:
    """Tests for _find_skill_md_in_tree()."""

    def test_finds_skill_md(self):
        tree_data = {
            "tree": [
                {"type": "blob", "path": "skills/commit/SKILL.md"},
                {"type": "blob", "path": "skills/commit/helper.py"},
            ]
        }
        result = _find_skill_md_in_tree(tree_data, "commit")
        assert result == "skills/commit/SKILL.md"

    def test_returns_none_when_not_found(self):
        tree_data = {
            "tree": [
                {"type": "blob", "path": "skills/review/SKILL.md"},
            ]
        }
        result = _find_skill_md_in_tree(tree_data, "commit")
        assert result is None

    def test_returns_none_for_empty_tree(self):
        assert _find_skill_md_in_tree({"tree": []}, "commit") is None

    def test_excludes_root_level_skill_md(self):
        """Root-level SKILL.md is not a valid skill directory."""
        tree_data = {
            "tree": [
                {"type": "blob", "path": "SKILL.md"},
            ]
        }
        result = _find_skill_md_in_tree(tree_data, "SKILL.md")
        assert result is None

    def test_excludes_skills_in_node_modules(self):
        tree_data = {
            "tree": [
                {"type": "blob", "path": "node_modules/commit/SKILL.md"},
            ]
        }
        result = _find_skill_md_in_tree(tree_data, "commit")
        assert result is None

    def test_prefers_shallowest_match(self):
        """When multiple matches exist, returns the shallowest path."""
        tree_data = {
            "tree": [
                {"type": "blob", "path": "deep/nested/commit/SKILL.md"},
                {"type": "blob", "path": "commit/SKILL.md"},
            ]
        }
        result = _find_skill_md_in_tree(tree_data, "commit")
        assert result == "commit/SKILL.md"

    def test_skill_in_subdirectory(self):
        """Skills can be nested under any non-excluded directory."""
        tree_data = {
            "tree": [
                {"type": "blob", "path": "tools/commit/SKILL.md"},
            ]
        }
        result = _find_skill_md_in_tree(tree_data, "commit")
        assert result == "tools/commit/SKILL.md"
