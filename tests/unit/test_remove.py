"""Unit tests for agr.commands.remove module."""

from pathlib import Path

from agr.commands.remove import _identifier_candidates, _find_dep_by_candidates
from agr.config import Dependency
from agr.handle import ParsedHandle


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
