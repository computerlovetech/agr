"""Unit tests for the git module's pure helper functions."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agr.exceptions import AgrError, AuthenticationError, RepoNotFoundError
from agr.git import fetch_and_checkout_commit, get_github_token, validate_commit_sha
from agr.git import _is_github_source as is_github_source
from agr.git import _partial_clone_unsupported as partial_clone_unsupported
from agr.git import _build_github_auth_env as build_github_auth_env
from agr.git import _raise_clone_error as raise_clone_error
from agr.source import DEFAULT_GITHUB_URL, SourceConfig


class TestGetGithubToken:
    """Tests for get_github_token()."""

    def test_returns_none_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_github_token() is None

    def test_prefers_github_token_over_gh_token(self):
        with patch.dict(
            os.environ, {"GITHUB_TOKEN": "gh-token", "GH_TOKEN": "cli-token"}
        ):
            assert get_github_token() == "gh-token"

    def test_falls_back_to_gh_token(self):
        env = {"GH_TOKEN": "cli-token"}
        with patch.dict(os.environ, env, clear=True):
            assert get_github_token() == "cli-token"

    def test_ignores_empty_github_token(self):
        env = {"GITHUB_TOKEN": "", "GH_TOKEN": "cli-token"}
        with patch.dict(os.environ, env, clear=True):
            assert get_github_token() == "cli-token"

    def test_ignores_whitespace_only_github_token(self):
        env = {"GITHUB_TOKEN": "   ", "GH_TOKEN": "cli-token"}
        with patch.dict(os.environ, env, clear=True):
            assert get_github_token() == "cli-token"

    def test_strips_whitespace_from_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  my-token  "}, clear=True):
            assert get_github_token() == "my-token"

    def test_returns_none_when_both_empty(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=True):
            assert get_github_token() is None


class TestIsGithubSource:
    """Tests for _is_github_source()."""

    def test_github_https_url(self):
        source = SourceConfig(name="default", type="github", url="https://github.com")
        assert is_github_source(source) is True

    def test_github_url_case_insensitive(self):
        source = SourceConfig(name="default", type="github", url="https://GitHub.COM")
        assert is_github_source(source) is True

    def test_non_github_url(self):
        source = SourceConfig(name="gitlab", type="gitlab", url="https://gitlab.com")
        assert is_github_source(source) is False

    def test_github_enterprise_url(self):
        source = SourceConfig(
            name="ghe", type="github", url="https://github.com/enterprise"
        )
        assert is_github_source(source) is True


class TestPartialCloneUnsupported:
    """Tests for _partial_clone_unsupported()."""

    def test_none_stderr(self):
        assert partial_clone_unsupported(None) is False

    def test_empty_stderr(self):
        assert partial_clone_unsupported("") is False

    def test_old_git_client(self):
        assert partial_clone_unsupported("error: unknown option `--filter'") is True

    def test_server_rejects_filter(self):
        assert partial_clone_unsupported("fatal: filtering is not supported") is True

    def test_alternate_server_phrasing(self):
        assert partial_clone_unsupported("error: does not support filtering") is True

    def test_rare_git_build(self):
        assert partial_clone_unsupported("filtering not recognized by server") is True

    def test_unrelated_error(self):
        assert partial_clone_unsupported("fatal: repository not found") is False

    def test_case_insensitive(self):
        assert partial_clone_unsupported("ERROR: Unknown Option `--filter'") is True


class TestRaiseCloneError:
    """Tests for _raise_clone_error().

    This function classifies git clone stderr/stdout into specific exception
    types. The classification order matters and is tested here.
    """

    GITHUB_SOURCE = SourceConfig(
        name="github",
        type="git",
        url=DEFAULT_GITHUB_URL,
    )
    CUSTOM_SOURCE = SourceConfig(
        name="custom",
        type="git",
        url="https://gitlab.example.com/{owner}/{repo}.git",
    )

    # --- Branch 1: Authentication failures ---

    def test_authentication_failed_with_token(self):
        """Explicit auth failure with token set raises AuthenticationError."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(AuthenticationError, match="Authentication failed"),
        ):
            raise_clone_error(
                "fatal: Authentication failed for 'https://github.com'",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_authentication_failed_without_token(self):
        """Auth failure without token mentions 'requires authentication'."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(AuthenticationError, match="requires authentication"),
        ):
            raise_clone_error(
                "fatal: Authentication failed",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_permission_denied_raises_auth_error(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(AuthenticationError, match="Authentication failed"),
        ):
            raise_clone_error(
                "Permission denied (publickey).",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    # --- Branch 2: Repository not found ---

    def test_repository_not_found(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error(
                "ERROR: Repository not found.",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_does_not_exist(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error(
                "fatal: '/owner/repo' does not exist",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_not_found_and_repository_in_message(self):
        """Catches messages where 'not found' and 'repository' appear separately."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(RepoNotFoundError),
        ):
            raise_clone_error(
                "fatal: remote repository not found in source",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    # --- Branch 3: DNS / network failures ---

    def test_could_not_resolve_host(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(AgrError, match="could not resolve host"),
        ):
            raise_clone_error(
                "fatal: unable to access: Could not resolve host: github.com",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    # --- Branch 4: Token-missing heuristic ---

    def test_empty_stderr_no_token_raises_repo_not_found(self):
        """Empty stderr with no token triggers the heuristic branch."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error("", "owner", "repo", self.GITHUB_SOURCE)

    def test_none_stderr_no_token_raises_repo_not_found(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error(None, "owner", "repo", self.GITHUB_SOURCE)

    def test_could_not_read_username_no_token(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error(
                "fatal: could not read Username",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_terminal_prompts_disabled_no_token(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error(
                "fatal: terminal prompts disabled",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_access_denied_no_token(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RepoNotFoundError, match="not found"),
        ):
            raise_clone_error(
                "access denied",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    # --- Branch 5: Catch-all ---

    def test_unrecognized_error_with_token_raises_agr_error(self):
        """Unrecognized error with token falls to catch-all."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(AgrError, match="Failed to clone"),
        ):
            raise_clone_error(
                "fatal: some unknown git error",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_unrecognized_error_non_github_source(self):
        """Unrecognized error on non-GitHub source hits catch-all (branch 4 skipped)."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(AgrError, match="Failed to clone"),
        ):
            raise_clone_error(
                "fatal: some unknown git error",
                "owner",
                "repo",
                self.CUSTOM_SOURCE,
            )

    # --- Edge cases ---

    def test_error_message_includes_source_name(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(AgrError, match="'github'"),
        ):
            raise_clone_error(
                "fatal: unknown error",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )

    def test_repo_not_found_includes_owner_and_repo(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(RepoNotFoundError, match="alice/my-repo"),
        ):
            raise_clone_error(
                "ERROR: Repository not found.",
                "alice",
                "my-repo",
                self.GITHUB_SOURCE,
            )

    def test_stderr_and_stdout_combined(self):
        """Both stderr and stdout are considered for classification."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(RepoNotFoundError),
        ):
            raise_clone_error(
                "",  # stderr empty
                "owner",
                "repo",
                self.GITHUB_SOURCE,
                stdout="ERROR: Repository not found.",
            )

    def test_case_insensitive_matching(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True),
            pytest.raises(AuthenticationError),
        ):
            raise_clone_error(
                "AUTHENTICATION FAILED",
                "owner",
                "repo",
                self.GITHUB_SOURCE,
            )


class TestFetchAndCheckoutCommit:
    """Tests for fetch_and_checkout_commit()."""

    def _create_origin_repo(self, tmp_path: Path) -> tuple[Path, str]:
        """Create a local git repo with one commit and return (path, commit_sha)."""
        origin = tmp_path / "origin"
        origin.mkdir()
        subprocess.run(["git", "init", str(origin)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(origin), "config", "user.email", "test@test.com"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(origin), "config", "user.name", "Test"],
            capture_output=True,
            check=True,
        )
        (origin / "SKILL.md").write_text("---\nname: test\n---\n")
        subprocess.run(
            ["git", "-C", str(origin), "add", "."], capture_output=True, check=True
        )
        subprocess.run(
            ["git", "-C", str(origin), "commit", "-m", "init"],
            capture_output=True,
            check=True,
        )
        result = subprocess.run(
            ["git", "-C", str(origin), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return origin, result.stdout.strip()

    def test_populates_working_tree_when_head_matches_commit(self, tmp_path: Path):
        """Working tree must be populated even when HEAD already matches.

        Regression: partial clones use --no-checkout, so the working tree
        is empty after clone. fetch_and_checkout_commit returned early
        when HEAD == commit without ensuring the working tree was populated.
        """
        origin, commit = self._create_origin_repo(tmp_path)

        # Clone with --no-checkout to simulate partial clone behaviour
        clone_dir = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", "--no-checkout", str(origin), str(clone_dir)],
            capture_output=True,
            check=True,
        )

        # Precondition: working tree is empty
        assert not (clone_dir / "SKILL.md").exists()

        # After fetch_and_checkout_commit, working tree must be populated
        fetch_and_checkout_commit(clone_dir, commit)
        assert (clone_dir / "SKILL.md").exists()

    def test_rejects_non_sha_commit(self, tmp_path: Path):
        """fetch_and_checkout_commit must reject non-SHA refs.

        A tampered lockfile could replace a pinned commit SHA with a
        branch name or tag, defeating --frozen immutability. The function
        must validate the commit format before passing it to git.
        """
        origin, _commit = self._create_origin_repo(tmp_path)
        clone_dir = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", str(origin), str(clone_dir)],
            capture_output=True,
            check=True,
        )

        with pytest.raises(AgrError, match="Invalid commit SHA"):
            fetch_and_checkout_commit(clone_dir, "main")

    def test_rejects_tag_ref(self, tmp_path: Path):
        """Tag names must be rejected as commit refs."""
        origin, _commit = self._create_origin_repo(tmp_path)
        clone_dir = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", str(origin), str(clone_dir)],
            capture_output=True,
            check=True,
        )

        with pytest.raises(AgrError, match="Invalid commit SHA"):
            fetch_and_checkout_commit(clone_dir, "v1.0.0")

    def test_rejects_short_sha(self, tmp_path: Path):
        """Abbreviated SHAs must be rejected (only full 40-char SHAs allowed)."""
        origin, commit = self._create_origin_repo(tmp_path)
        clone_dir = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", str(origin), str(clone_dir)],
            capture_output=True,
            check=True,
        )

        with pytest.raises(AgrError, match="Invalid commit SHA"):
            fetch_and_checkout_commit(clone_dir, commit[:12])


class TestValidateCommitSha:
    """Tests for validate_commit_sha()."""

    def test_accepts_valid_full_sha(self):
        """A valid 40-character lowercase hex SHA must pass."""
        validate_commit_sha("a" * 40)
        validate_commit_sha("0123456789abcdef" * 2 + "01234567")

    def test_rejects_branch_name(self):
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("main")

    def test_rejects_tag_name(self):
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("v1.0.0")

    def test_rejects_short_sha(self):
        """Abbreviated SHAs are ambiguous and must be rejected."""
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("abc123")

    def test_rejects_uppercase_hex(self):
        """Git SHAs are lowercase hex; uppercase must be rejected."""
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("A" * 40)

    def test_rejects_empty_string(self):
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("")

    def test_rejects_sha_with_extra_chars(self):
        """41-char strings or SHAs with trailing content must be rejected."""
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("a" * 40 + "b")

    def test_rejects_refs_heads_prefix(self):
        """Full ref paths like refs/heads/main must be rejected."""
        with pytest.raises(AgrError, match="Invalid commit SHA"):
            validate_commit_sha("refs/heads/main")


class TestBuildGithubAuthEnv:
    """Tests for _build_github_auth_env().

    Verifies that GitHub token authentication is passed via git
    config environment variables instead of being embedded in the URL.
    """

    def test_returns_empty_when_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            assert build_github_auth_env() == {}

    def test_returns_auth_env_when_token_set(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"}, clear=True):
            env = build_github_auth_env()
            assert env["GIT_CONFIG_COUNT"] == "1"
            assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
            assert env["GIT_CONFIG_VALUE_0"] == "AUTHORIZATION: bearer ghp_test123"

    def test_token_value_not_in_config_keys(self):
        """Token must only appear in GIT_CONFIG_VALUE, never in keys."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_secret"}, clear=True):
            env = build_github_auth_env()
            for key in env:
                assert "ghp_secret" not in key

    def test_appends_to_existing_git_config_count(self):
        """Must not overwrite existing GIT_CONFIG_COUNT entries."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "tok",
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "user.name",
                "GIT_CONFIG_VALUE_0": "Test User",
                "GIT_CONFIG_KEY_1": "user.email",
                "GIT_CONFIG_VALUE_1": "test@example.com",
            },
            clear=True,
        ):
            env = build_github_auth_env()
            assert env["GIT_CONFIG_COUNT"] == "3"
            assert "GIT_CONFIG_KEY_2" in env
            assert "GIT_CONFIG_VALUE_2" in env

    def test_uses_gh_token_fallback(self):
        with patch.dict(os.environ, {"GH_TOKEN": "gh_fallback"}, clear=True):
            env = build_github_auth_env()
            assert env["GIT_CONFIG_VALUE_0"] == "AUTHORIZATION: bearer gh_fallback"

    def test_whitespace_only_token_returns_empty(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  "}, clear=True):
            assert build_github_auth_env() == {}

    def test_scoped_to_github_com(self):
        """The config key must be scoped to github.com to avoid leaking to other hosts."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True):
            env = build_github_auth_env()
            key = env["GIT_CONFIG_KEY_0"]
            assert "github.com" in key
            assert key.startswith("http.https://github.com/")

    def test_ignores_malformed_git_config_count(self):
        """A non-integer GIT_CONFIG_COUNT must not raise ValueError; fall back to 0."""
        with patch.dict(
            os.environ,
            {"GITHUB_TOKEN": "tok", "GIT_CONFIG_COUNT": "notanumber"},
            clear=True,
        ):
            env = build_github_auth_env()
            assert env["GIT_CONFIG_COUNT"] == "1"
            assert "GIT_CONFIG_KEY_0" in env
            assert env["GIT_CONFIG_VALUE_0"] == "AUTHORIZATION: bearer tok"
