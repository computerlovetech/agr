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

    def test_dot_path_rejects_empty_name(self):
        """parse_handle('.') must reject because Path('.').name is empty."""
        with pytest.raises(InvalidHandleError, match="empty resource name"):
            parse_handle(".")

    def test_dot_slash_path_rejects_empty_name(self):
        """parse_handle('./') must reject because Path('./').name is empty."""
        with pytest.raises(InvalidHandleError, match="empty resource name"):
            parse_handle("./")

    def test_dotdot_path_rejects_traversal_name(self):
        """parse_handle('..') must reject because Path('..').name is '..'."""
        with pytest.raises(InvalidHandleError, match="empty resource name"):
            parse_handle("..")

    def test_dotdot_slash_path_rejects_traversal_name(self):
        """parse_handle('../') must reject because name resolves to '..'."""
        with pytest.raises(InvalidHandleError, match="empty resource name"):
            parse_handle("../")

    def test_parse_handle_rejects_double_hyphen_in_local_skill(self, tmp_path):
        """Local skill directory containing -- raises error."""
        # Create a directory with -- in the name
        bad_skill = tmp_path / "my--skill"
        bad_skill.mkdir()

        with pytest.raises(InvalidHandleError, match="contains reserved sequence"):
            parse_handle(str(bad_skill))

    def test_remote_dotdot_in_skill_name_rejected(self):
        """Remote handle 'user/..' must reject '..' as skill name."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle("user/..")

    def test_remote_dotdot_in_repo_rejected(self):
        """Remote handle 'user/../skill' must reject '..' as repo."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle("user/../skill")

    def test_remote_dotdot_in_username_rejected(self):
        """Remote handle '../skill' must reject '..' as username."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle("../skill", prefer_local=False)

    def test_remote_dot_in_skill_name_rejected(self):
        """Remote handle 'user/.' must reject '.' as skill name."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle("user/.", prefer_local=False)

    def test_remote_dot_in_repo_rejected(self):
        """Remote handle 'user/./skill' must reject '.' as repo."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle("user/./skill")

    def test_remote_dotdot_as_single_name_with_default_owner(self):
        """Single-part handle '..' with default_owner must be rejected."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle("..", prefer_local=False, default_owner="acme")

    def test_remote_dot_as_single_name_with_default_owner(self):
        """Single-part handle '.' with default_owner must be rejected."""
        with pytest.raises(InvalidHandleError, match="path traversal"):
            parse_handle(".", prefer_local=False, default_owner="acme")

    def test_empty_repo_in_three_part_handle_raises(self):
        """Handle with empty middle component (user//skill) must be rejected.

        Without this check, 'user//skill' silently produces repo=""
        which is not None but falsy, causing misclassification in sync
        (treated as specific-repo instead of default-repo, skipping
        legacy fallback).
        """
        with pytest.raises(InvalidHandleError, match="empty"):
            parse_handle("user//skill")

    def test_empty_username_in_two_part_handle_raises(self):
        """Handle with empty username (/skill) must be rejected in remote mode.

        With prefer_local=False, '/skill' bypasses local detection and
        splits into ['', 'skill'], producing an empty username.
        """
        with pytest.raises(InvalidHandleError, match="empty"):
            parse_handle("/skill", prefer_local=False)

    def test_remote_newline_in_skill_name_rejected(self):
        """Skill name containing a newline must be rejected.

        Without this check, a malicious transitive package dependency
        could inject YAML frontmatter via the skill name, which is
        written into the installed SKILL.md by update_skill_md_name.
        """
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo/skill\ndescription: evil")

    def test_remote_newline_in_repo_rejected(self):
        """Repo name containing a newline must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo\nx/skill")

    def test_remote_newline_in_username_rejected(self):
        """Username containing a newline must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user\nx/skill", prefer_local=False)

    def test_remote_tab_in_skill_name_rejected(self):
        """Skill name containing a tab must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo/skill\tname")

    def test_remote_space_in_skill_name_rejected(self):
        """Skill name containing an internal space must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo/skill name")

    def test_remote_carriage_return_in_component_rejected(self):
        """Component with carriage return must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo/skill\rname")

    def test_remote_null_byte_in_component_rejected(self):
        """Component with null byte must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo/skill\x00name")

    def test_remote_del_character_in_component_rejected(self):
        """Component with DEL (0x7F) control char must be rejected."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("user/repo/skill\x7fname")

    def test_remote_hyphen_name_still_allowed(self):
        """Legitimate hyphenated names remain valid."""
        h = parse_handle("user/repo/my-skill-name")
        assert h.name == "my-skill-name"

    def test_remote_default_owner_rejects_control_char_in_name(self):
        """One-part handle with default_owner rejects control chars in skill name."""
        with pytest.raises(InvalidHandleError, match="whitespace or control"):
            parse_handle("skill\nx", prefer_local=False, default_owner="acme")

    def test_yaml_flow_open_brace_in_skill_name_rejected(self):
        """{} in skill name would produce a YAML flow mapping for the name field."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("user/repo/{skill}", prefer_local=False)

    def test_yaml_flow_close_brace_in_skill_name_rejected(self):
        """Closing brace alone also rejected."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("user/repo/skill}", prefer_local=False)

    def test_yaml_flow_open_bracket_in_skill_name_rejected(self):
        """[ in skill name would produce a YAML flow sequence for the name field."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("user/repo/[skill]", prefer_local=False)

    def test_yaml_flow_close_bracket_in_skill_name_rejected(self):
        """Closing bracket alone also rejected."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("user/repo/skill]", prefer_local=False)

    def test_yaml_flow_brace_in_username_rejected(self):
        """{} in username position also blocked."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("{user}/repo/skill", prefer_local=False)

    def test_yaml_flow_bracket_in_repo_rejected(self):
        """[] in repo position also blocked."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("user/[repo]/skill", prefer_local=False)

    def test_yaml_flow_chars_in_default_owner_one_part_rejected(self):
        """One-part handle with {name} rejected via default_owner path."""
        with pytest.raises(InvalidHandleError, match="YAML flow"):
            parse_handle("{skill}", prefer_local=False, default_owner="acme")

    # SF-011: YAML indicator characters
    def test_yaml_comment_hash_in_skill_name_rejected(self):
        """# in skill name would produce 'name: #foo' where YAML treats #foo as a comment."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("user/repo/#skill", prefer_local=False)

    def test_yaml_comment_hash_in_username_rejected(self):
        """# in username position blocked."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("#user/repo/skill", prefer_local=False)

    def test_yaml_comment_hash_in_repo_rejected(self):
        """# in repo position blocked."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("user/#repo/skill", prefer_local=False)

    def test_yaml_alias_star_in_skill_name_rejected(self):
        """* in skill name would cause a YAML alias parse error."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("user/repo/*alias", prefer_local=False)

    def test_yaml_anchor_ampersand_in_skill_name_rejected(self):
        """& in skill name would set an anchor on a null scalar."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("user/repo/&anchor", prefer_local=False)

    def test_yaml_tag_exclamation_in_skill_name_rejected(self):
        """! in skill name would apply a YAML type tag to the value."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("user/repo/!null", prefer_local=False)

    def test_yaml_hash_in_default_owner_one_part_rejected(self):
        """One-part handle with #name rejected via default_owner path."""
        with pytest.raises(InvalidHandleError, match="YAML indicator"):
            parse_handle("#skill", prefer_local=False, default_owner="acme")

    def test_legitimate_names_with_underscores_still_allowed(self):
        """Names with underscores and dots remain valid (common in GitHub repos)."""
        h = parse_handle("user/my_repo/my-skill", prefer_local=False)
        assert h.username == "user"
        assert h.repo == "my_repo"
        assert h.name == "my-skill"

    # SF-012: YAML block-scalar and quoted-scalar characters
    def test_yaml_block_literal_pipe_in_skill_name_rejected(self):
        """| in skill name produces 'name: |skill' — a YAML parse error (invalid block header)."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle("user/repo/|skill", prefer_local=False)

    def test_yaml_block_folded_gt_in_skill_name_rejected(self):
        """> in skill name produces 'name: >skill' — a YAML parse error (invalid block header)."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle("user/repo/>skill", prefer_local=False)

    def test_yaml_single_quote_in_skill_name_rejected(self):
        """' in skill name starts an unterminated single-quoted scalar, swallowing subsequent frontmatter."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle("user/repo/'skill", prefer_local=False)

    def test_yaml_double_quote_in_skill_name_rejected(self):
        """\" in skill name starts an unterminated double-quoted scalar."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle('user/repo/"skill', prefer_local=False)

    def test_yaml_pipe_in_username_rejected(self):
        """| in username position blocked."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle("|user/repo/skill", prefer_local=False)

    def test_yaml_gt_in_repo_rejected(self):
        """> in repo position blocked."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle("user/>repo/skill", prefer_local=False)

    def test_yaml_pipe_in_default_owner_one_part_rejected(self):
        """One-part handle resolved via default_owner: | in name blocked."""
        with pytest.raises(InvalidHandleError, match="YAML block"):
            parse_handle("|skill", prefer_local=False, default_owner="acme")


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

    def test_with_repo_promotes_shorthand(self):
        """with_repo fills in a missing repo on a 2-part handle."""
        h = ParsedHandle(username="computerlovetech", name="docs-audit")
        assert h.repo is None
        promoted = h.with_repo("skills")
        assert promoted.repo == "skills"
        assert promoted.to_toml_handle() == "computerlovetech/skills/docs-audit"
        # Original is unchanged (returns a copy).
        assert h.repo is None

    def test_with_repo_preserves_explicit_repo(self):
        """with_repo never overwrites an explicit repo."""
        h = ParsedHandle(username="maragudk", repo="agent-resources", name="x")
        promoted = h.with_repo("skills")
        assert promoted is h
        assert promoted.repo == "agent-resources"

    def test_with_repo_none_returns_original(self):
        """with_repo(None) returns the handle unchanged."""
        h = ParsedHandle(username="owner", name="name")
        assert h.with_repo(None) is h

    def test_with_repo_local_returns_original(self):
        """with_repo is a no-op on local handles."""
        from pathlib import Path

        h = ParsedHandle(is_local=True, name="x", local_path=Path("./x"))
        assert h.with_repo("skills") is h

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
