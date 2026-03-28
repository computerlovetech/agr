"""Unit tests for the git module's pure helper functions."""

import os
from unittest.mock import patch

import pytest

from agr.exceptions import AgrError, AuthenticationError, RepoNotFoundError
from agr.git import get_github_token
from agr.git import _is_github_source as is_github_source
from agr.git import _partial_clone_unsupported as partial_clone_unsupported
from agr.git import _apply_github_token as apply_github_token
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


class TestApplyGithubToken:
    """Tests for _apply_github_token()."""

    def test_no_token_returns_original_url(self):
        url = "https://github.com/owner/repo.git"
        with patch.dict(os.environ, {}, clear=True):
            assert apply_github_token(url) == url

    def test_injects_token_into_github_url(self):
        url = "https://github.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            result = apply_github_token(url)
            assert "my-token" in result
            assert result.startswith("https://")
            assert "github.com" in result

    def test_non_https_url_unchanged(self):
        url = "git@github.com:owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            assert apply_github_token(url) == url

    def test_non_github_url_unchanged(self):
        url = "https://gitlab.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            assert apply_github_token(url) == url

    def test_url_with_existing_auth_unchanged(self):
        url = "https://user@github.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            assert apply_github_token(url) == url

    def test_special_chars_in_token_are_encoded(self):
        url = "https://github.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok/en@val"}, clear=True):
            result = apply_github_token(url)
            # '/' and '@' should be percent-encoded
            assert "tok%2Fen%40val" in result


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
