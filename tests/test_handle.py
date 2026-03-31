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
        """Simple name without username raises error."""
        with pytest.raises(InvalidHandleError):
            parse_handle("agent-browser")

    def test_too_many_segments_raises(self):
        """More than 3 segments raises error."""
        with pytest.raises(InvalidHandleError):
            parse_handle("a/b/c/d")

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
