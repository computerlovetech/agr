"""Tests for agr.handle module."""

import pytest

from agr.exceptions import InvalidHandleError
from agr.handle import (
    DEFAULT_REPO_NAME,
    LEGACY_DEFAULT_REPO_NAME,
    ParsedHandle,
    iter_repo_candidates,
    parse_handle,
)


class TestParseHandle:
    """Tests for parse_handle function."""

    def test_remote_user_skill(self):
        """Parse user/skill format."""
        h = parse_handle("vercel-labs/agent-browser")
        assert h.username == "vercel-labs"
        assert h.name == "agent-browser"
        assert h.repo is None
        assert h.is_remote
        assert not h.is_local

    def test_remote_user_repo_skill(self):
        """Parse user/repo/skill format."""
        h = parse_handle("maragudk/skills/collaboration")
        assert h.username == "maragudk"
        assert h.repo == "skills"
        assert h.name == "collaboration"
        assert h.is_remote
        assert not h.is_local

    def test_local_dot_slash(self):
        """Parse ./path format as local."""
        h = parse_handle("./my-skill")
        assert h.is_local
        assert not h.is_remote
        assert h.name == "my-skill"
        assert h.local_path is not None

    def test_local_dot_dot_slash(self):
        """Parse ../path format as local."""
        h = parse_handle("../other/skill")
        assert h.is_local
        assert h.name == "skill"

    def test_existing_path_prefers_local(self, tmp_path, monkeypatch):
        """Existing path with one slash is treated as local."""
        skill_dir = tmp_path / "user" / "skill"
        skill_dir.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        h = parse_handle("user/skill")

        assert h.is_local
        assert h.local_path == skill_dir.relative_to(tmp_path)

    def test_empty_raises(self):
        """Empty handle raises error."""
        with pytest.raises(InvalidHandleError):
            parse_handle("")

    def test_whitespace_only_raises(self):
        """Whitespace-only handle raises error."""
        with pytest.raises(InvalidHandleError):
            parse_handle("   ")

    def test_simple_name_raises(self):
        """Simple name without username raises error when no default_owner."""
        with pytest.raises(InvalidHandleError):
            parse_handle("agent-browser")

    def test_simple_name_with_default_owner(self):
        """Simple name resolves with default_owner."""
        h = parse_handle("setup", default_owner="computerlovetech")
        assert h.username == "computerlovetech"
        assert h.name == "setup"
        assert h.repo is None
        assert h.is_remote
        assert not h.is_local

    def test_simple_name_with_custom_default_owner(self):
        """Simple name resolves with custom default_owner."""
        h = parse_handle("commit", default_owner="myorg")
        assert h.username == "myorg"
        assert h.name == "commit"

    def test_simple_name_default_owner_none_raises(self):
        """Simple name with default_owner=None still raises."""
        with pytest.raises(InvalidHandleError):
            parse_handle("setup", default_owner=None)

    def test_simple_name_default_owner_validates_separator(self):
        """Simple name with -- is rejected even with default_owner."""
        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle("my--skill", default_owner="computerlovetech")

    def test_simple_name_default_owner_with_separator_rejected(self):
        """Default owner containing -- is rejected."""
        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle("setup", default_owner="bad--owner")

    def test_simple_name_prefers_local_path(self, tmp_path, monkeypatch):
        """Existing local path takes precedence over default_owner."""
        skill_dir = tmp_path / "setup"
        skill_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        h = parse_handle("setup", default_owner="computerlovetech")
        assert h.is_local
        assert h.name == "setup"

    def test_too_many_segments_raises(self):
        """More than 3 segments raises error."""
        with pytest.raises(InvalidHandleError):
            parse_handle("a/b/c/d")

    def test_trailing_slash_three_part(self):
        """Trailing slash on user/repo/skill/ is stripped."""
        h = parse_handle("owner/repo/skill/")
        assert h.username == "owner"
        assert h.repo == "repo"
        assert h.name == "skill"
        assert h.is_remote

    def test_trailing_slash_two_part(self):
        """Trailing slash on user/skill/ is stripped."""
        h = parse_handle("owner/skill/")
        assert h.username == "owner"
        assert h.name == "skill"
        assert h.repo is None
        assert h.is_remote

    def test_trailing_slash_one_part_with_default_owner(self):
        """Trailing slash on skill/ is stripped."""
        h = parse_handle("skill/", default_owner="myorg")
        assert h.username == "myorg"
        assert h.name == "skill"

    def test_parse_handle_rejects_double_hyphen_in_username(self):
        """Username containing -- raises error."""
        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle("user--name/skill")

    def test_parse_handle_rejects_double_hyphen_in_repo(self):
        """Repo containing -- raises error."""
        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle("user/repo--name/skill")

    def test_parse_handle_rejects_double_hyphen_in_skill(self):
        """Skill name containing -- raises error."""
        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle("user/skill--name")

    def test_parse_handle_allows_single_hyphen(self):
        """Single hyphens are allowed in all components."""
        h = parse_handle("user-name/my-skill")
        assert h.username == "user-name"
        assert h.name == "my-skill"

    def test_parse_handle_allows_single_hyphen_in_repo(self):
        """Single hyphens are allowed in repo name."""
        h = parse_handle("user/my-repo/skill")
        assert h.repo == "my-repo"

    def test_parse_handle_rejects_double_hyphen_in_local_skill(self, tmp_path):
        """Local skill directory containing -- raises error."""
        # Create a directory with -- in the name
        bad_skill = tmp_path / "my--skill"
        bad_skill.mkdir()

        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle(str(bad_skill))


class TestParsedHandle:
    """Tests for ParsedHandle methods."""

    def test_to_toml_handle_simple(self):
        """to_toml_handle for user/skill."""
        h = ParsedHandle(username="vercel-labs", name="agent-browser")
        assert h.to_toml_handle() == "vercel-labs/agent-browser"

    def test_to_toml_handle_with_repo(self):
        """to_toml_handle for user/repo/skill."""
        h = ParsedHandle(username="maragudk", repo="skills", name="collaboration")
        assert h.to_toml_handle() == "maragudk/skills/collaboration"

    def test_to_toml_handle_local(self):
        """to_toml_handle for local path."""
        from pathlib import Path

        # Path("./my-skill") normalizes to "my-skill"
        h = ParsedHandle(is_local=True, name="my-skill", local_path=Path("./my-skill"))
        assert h.to_toml_handle() == "my-skill"

    def test_to_toml_handle_local_with_subdir(self):
        """to_toml_handle for local path with subdirectory."""
        from pathlib import Path

        h = ParsedHandle(
            is_local=True, name="skill", local_path=Path("./path/to/skill")
        )
        assert h.to_toml_handle() == "path/to/skill"

    def test_to_installed_name_simple(self):
        """to_installed_name for user/skill."""
        h = ParsedHandle(username="vercel-labs", name="agent-browser")
        assert h.to_installed_name() == "vercel-labs--agent-browser"

    def test_to_installed_name_with_repo(self):
        """to_installed_name for user/repo/skill."""
        h = ParsedHandle(username="maragudk", repo="skills", name="collaboration")
        assert h.to_installed_name() == "maragudk--skills--collaboration"

    def test_to_installed_name_local(self):
        """to_installed_name for local skill."""
        h = ParsedHandle(is_local=True, name="my-skill")
        assert h.to_installed_name() == "local--my-skill"

    def test_get_github_repo_simple(self):
        """get_github_repo for user/skill defaults repo."""
        h = ParsedHandle(username="vercel-labs", name="agent-browser")
        user, repo = h.get_github_repo()
        assert user == "vercel-labs"
        assert repo == "skills"

    def test_get_github_repo_explicit(self):
        """get_github_repo with explicit repo."""
        h = ParsedHandle(username="maragudk", repo="skills", name="collaboration")
        user, repo = h.get_github_repo()
        assert user == "maragudk"
        assert repo == "skills"

    def test_get_github_repo_local_raises(self):
        """get_github_repo for local handle raises."""
        h = ParsedHandle(is_local=True, name="my-skill")
        with pytest.raises(InvalidHandleError):
            h.get_github_repo()

    def test_get_github_repo_custom_default_repo(self):
        """get_github_repo uses custom default_repo when repo is None."""
        h = ParsedHandle(username="myorg", name="my-skill")
        user, repo = h.get_github_repo(default_repo="my-repo")
        assert user == "myorg"
        assert repo == "my-repo"

    def test_get_github_repo_explicit_repo_ignores_default(self):
        """get_github_repo with explicit repo ignores default_repo."""
        h = ParsedHandle(username="myorg", repo="explicit", name="my-skill")
        user, repo = h.get_github_repo(default_repo="my-repo")
        assert user == "myorg"
        assert repo == "explicit"

    def test_get_github_repo_no_default_repo_falls_back(self):
        """get_github_repo without default_repo falls back to DEFAULT_REPO_NAME."""
        h = ParsedHandle(username="myorg", name="my-skill")
        user, repo = h.get_github_repo()
        assert repo == DEFAULT_REPO_NAME


class TestRepoCandidates:
    """Tests for iter_repo_candidates function."""

    def test_default_candidates(self):
        """Owner-only handles try skills then legacy repo."""
        assert iter_repo_candidates(None) == [
            (DEFAULT_REPO_NAME, False),
            (LEGACY_DEFAULT_REPO_NAME, True),
        ]

    def test_explicit_repo(self):
        """Explicit repo does not include legacy fallback."""
        assert iter_repo_candidates("custom") == [("custom", False)]

    def test_custom_default_repo(self):
        """Custom default_repo replaces standard default, no legacy fallback."""
        assert iter_repo_candidates(None, default_repo="my-repo") == [
            ("my-repo", False),
        ]

    def test_custom_default_repo_skills(self):
        """Setting default_repo to 'skills' keeps legacy fallback."""
        assert iter_repo_candidates(None, default_repo="skills") == [
            (DEFAULT_REPO_NAME, False),
            (LEGACY_DEFAULT_REPO_NAME, True),
        ]

    def test_explicit_repo_ignores_default_repo(self):
        """Explicit repo takes precedence over default_repo."""
        assert iter_repo_candidates("explicit", default_repo="my-repo") == [
            ("explicit", False),
        ]
