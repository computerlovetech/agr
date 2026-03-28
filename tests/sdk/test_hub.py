"""Tests for hub functions."""

from unittest.mock import MagicMock, patch

import pytest

from agr.exceptions import (
    AgrError,
    AuthenticationError,
    InvalidHandleError,
    RateLimitError,
    RepoNotFoundError,
    SkillNotFoundError,
)
from agr.sdk.hub import (
    DEFAULT_REPO_NAME,
    _extract_description,
    _github_api_request,
    list_skills,
    skill_info,
)


class TestExtractDescription:
    """Tests for _extract_description()."""

    def test_extracts_first_paragraph(self):
        """Test extracting first paragraph after frontmatter."""
        content = """---
name: test
---

# Test Skill

This is the description of the skill.

## More content

More details here.
"""
        desc = _extract_description(content)
        assert desc == "This is the description of the skill."

    def test_extracts_without_frontmatter(self):
        """Test extracting when no frontmatter."""
        content = """# Test Skill

This is the description.

## More content
"""
        desc = _extract_description(content)
        assert desc == "This is the description."

    def test_handles_multi_line_paragraph(self):
        """Test extracting multi-line paragraph."""
        content = """---
name: test
---

# Skill

This is a longer description
that spans multiple lines
in the same paragraph.

## Next section
"""
        desc = _extract_description(content)
        assert desc is not None
        assert "longer description" in desc
        assert "multiple lines" in desc

    def test_returns_none_for_empty(self):
        """Test returns None for empty content."""
        content = """---
name: test
---

# Skill

## Section
"""
        desc = _extract_description(content)
        assert desc is None

    def test_truncates_long_descriptions(self):
        """Test description is truncated to 200 chars."""
        long_text = "x" * 300
        content = f"""# Skill

{long_text}
"""
        desc = _extract_description(content)
        assert desc is not None
        assert len(desc) == 200


class TestGitHubApiRequest:
    """Tests for _github_api_request()."""

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_success_response(self, mock_urlopen: MagicMock):
        """Test successful API request."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"key": "value"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = _github_api_request("https://api.github.com/test")
        assert result == {"key": "value"}

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_auth_failure_401(self, mock_urlopen: MagicMock):
        """Test 401 raises AuthenticationError."""
        from urllib.error import HTTPError

        mock_headers = MagicMock()
        mock_urlopen.side_effect = HTTPError(
            "url", 401, "Unauthorized", mock_headers, None
        )

        with pytest.raises(AuthenticationError):
            _github_api_request("https://api.github.com/test")

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_not_found_404(self, mock_urlopen: MagicMock):
        """Test 404 raises RepoNotFoundError."""
        from urllib.error import HTTPError

        mock_headers = MagicMock()
        mock_urlopen.side_effect = HTTPError(
            "url", 404, "Not Found", mock_headers, None
        )

        with pytest.raises(RepoNotFoundError):
            _github_api_request("https://api.github.com/test")

    @patch("agr.sdk.hub.get_github_token")
    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_includes_auth_header(
        self, mock_urlopen: MagicMock, mock_get_token: MagicMock
    ):
        """Test auth header is included when token available."""
        mock_get_token.return_value = "test-token"
        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        _github_api_request("https://api.github.com/test")

        # Check the request object passed to urlopen
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("Authorization") == "Bearer test-token"


class TestNetworkErrorHandling:
    """Tests for network error handling in _github_api_request()."""

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_url_error_raises_agr_error(self, mock_urlopen: MagicMock):
        """Test that URLError raises AgrError, not built-in ConnectionError."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        with pytest.raises(AgrError, match="Failed to connect to GitHub API"):
            _github_api_request("https://api.github.com/test")

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_url_error_preserves_cause(self, mock_urlopen: MagicMock):
        """Test that URLError is chained as the cause of AgrError."""
        from urllib.error import URLError

        original = URLError("DNS lookup failed")
        mock_urlopen.side_effect = original

        with pytest.raises(AgrError) as exc_info:
            _github_api_request("https://api.github.com/test")

        assert exc_info.value.__cause__ is original


class TestRateLimitHandling:
    """Tests for rate limit handling in _github_api_request()."""

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_http_429_raises_rate_limit_error(self, mock_urlopen: MagicMock):
        """Test that HTTP 429 raises RateLimitError."""
        from urllib.error import HTTPError

        mock_headers = MagicMock()
        mock_urlopen.side_effect = HTTPError(
            "url", 429, "Too Many Requests", mock_headers, None
        )

        with pytest.raises(RateLimitError, match="rate limit exceeded"):
            _github_api_request("https://api.github.com/test")

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_http_403_with_rate_limit_header_raises_rate_limit_error(
        self, mock_urlopen: MagicMock
    ):
        """Test that HTTP 403 with X-RateLimit-Remaining: 0 raises RateLimitError."""
        from urllib.error import HTTPError

        mock_headers = MagicMock()
        mock_headers.get.return_value = "0"
        error = HTTPError("url", 403, "Forbidden", mock_headers, None)
        mock_urlopen.side_effect = error

        with pytest.raises(RateLimitError, match="rate limit exceeded"):
            _github_api_request("https://api.github.com/test")

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_http_403_without_rate_limit_header_raises_auth_error(
        self, mock_urlopen: MagicMock
    ):
        """Test that HTTP 403 without rate limit header raises AuthenticationError."""
        from urllib.error import HTTPError

        # No X-RateLimit-Remaining header or non-zero value
        mock_headers = MagicMock()
        mock_headers.get.return_value = ""  # Empty string, not "0"
        mock_urlopen.side_effect = HTTPError(
            "url", 403, "Forbidden", mock_headers, None
        )

        with pytest.raises(AuthenticationError):
            _github_api_request("https://api.github.com/test")

    @patch("agr.sdk.hub.urllib.request.urlopen")
    def test_http_403_with_nonzero_rate_limit_raises_auth_error(
        self, mock_urlopen: MagicMock
    ):
        """Test that HTTP 403 with remaining rate limit raises AuthenticationError."""
        from urllib.error import HTTPError

        mock_headers = MagicMock()
        mock_headers.get.return_value = "42"
        error = HTTPError("url", 403, "Forbidden", mock_headers, None)
        mock_urlopen.side_effect = error

        with pytest.raises(AuthenticationError):
            _github_api_request("https://api.github.com/test")


class TestListSkills:
    """Tests for list_skills()."""

    @patch("agr.sdk.hub._github_api_request")
    def test_lists_skills_from_repo(self, mock_api: MagicMock):
        """Test listing skills from repository."""
        mock_api.return_value = {
            "tree": [
                {"type": "blob", "path": "skills/commit/SKILL.md"},
                {"type": "blob", "path": "skills/review/SKILL.md"},
                {"type": "blob", "path": "README.md"},
            ]
        }

        skills = list_skills("owner/repo")

        assert len(skills) == 2
        assert skills[0].name == "commit"
        assert skills[0].owner == "owner"
        assert skills[0].repo == "repo"
        assert skills[1].name == "review"

    @patch("agr.sdk.hub._github_api_request")
    def test_handles_default_repo(self, mock_api: MagicMock):
        """Test using default repo name."""
        mock_api.return_value = {
            "tree": [
                {"type": "blob", "path": "commit/SKILL.md"},
            ]
        }

        skills = list_skills("owner")

        assert len(skills) == 1
        assert skills[0].repo == DEFAULT_REPO_NAME
        assert skills[0].handle == "owner/commit"

    @patch("agr.sdk.hub._github_api_request")
    def test_excludes_root_skill_md(self, mock_api: MagicMock):
        """Test that root SKILL.md is excluded."""
        mock_api.return_value = {
            "tree": [
                {"type": "blob", "path": "SKILL.md"},  # Root - should be excluded
                {"type": "blob", "path": "skills/commit/SKILL.md"},
            ]
        }

        skills = list_skills("owner/repo")

        assert len(skills) == 1
        assert skills[0].name == "commit"

    @patch("agr.sdk.hub._github_api_request")
    def test_excludes_skills_in_excluded_dirs(self, mock_api: MagicMock):
        """Test that skills inside excluded directories are filtered out."""
        mock_api.return_value = {
            "tree": [
                {"type": "blob", "path": "skills/commit/SKILL.md"},
                {"type": "blob", "path": "node_modules/some-pkg/SKILL.md"},
                {"type": "blob", "path": ".git/hooks/SKILL.md"},
                {"type": "blob", "path": "__pycache__/cached/SKILL.md"},
                {"type": "blob", "path": "vendor/lib/SKILL.md"},
            ]
        }

        skills = list_skills("owner/repo")

        assert len(skills) == 1
        assert skills[0].name == "commit"

    @patch("agr.sdk.hub._github_api_request")
    def test_find_skill_excludes_excluded_dirs(self, mock_api: MagicMock):
        """Test that skill_info filters skills in excluded directories."""
        mock_api.return_value = {
            "tree": [
                {"type": "blob", "path": "node_modules/my-skill/SKILL.md"},
            ]
        }

        with pytest.raises(SkillNotFoundError):
            skill_info("owner/repo/my-skill")

    def test_invalid_handle_raises(self):
        """Test invalid repo handle raises InvalidHandleError."""
        with pytest.raises(InvalidHandleError, match="Invalid repo handle"):
            list_skills("too/many/parts/here")


class TestSkillInfo:
    """Tests for skill_info()."""

    @patch("agr.sdk.hub._github_api_request")
    def test_gets_skill_info(self, mock_api: MagicMock):
        """Test getting skill info with description."""
        import base64

        skill_md_content = """---
name: commit
---

# Commit Skill

This skill helps with commits.

## Instructions
...
"""
        encoded = base64.b64encode(skill_md_content.encode()).decode()

        def mock_request(url):
            if "trees" in url:
                return {
                    "tree": [
                        {"type": "blob", "path": "skills/commit/SKILL.md"},
                    ]
                }
            else:
                return {"encoding": "base64", "content": encoded}

        mock_api.side_effect = mock_request

        info = skill_info("owner/repo/commit")

        assert info.name == "commit"
        assert info.owner == "owner"
        assert info.repo == "repo"
        assert info.description is not None
        assert "helps with commits" in info.description

    @patch("agr.sdk.hub._github_api_request")
    def test_skill_not_found(self, mock_api: MagicMock):
        """Test skill not found raises SkillNotFoundError."""
        mock_api.return_value = {"tree": []}

        with pytest.raises(SkillNotFoundError):
            skill_info("owner/repo/nonexistent")

    @patch("agr.sdk.hub._github_api_request")
    def test_repo_not_found(self, mock_api: MagicMock):
        """Test repo not found raises SkillNotFoundError."""
        mock_api.side_effect = RepoNotFoundError("Not found")

        with pytest.raises(SkillNotFoundError):
            skill_info("owner/repo/skill")

    def test_local_path_rejected(self):
        """Test local paths are rejected with InvalidHandleError."""
        with pytest.raises(InvalidHandleError, match="local path"):
            skill_info("./local-skill")

        with pytest.raises(InvalidHandleError, match="local path"):
            skill_info("../parent-skill")

        with pytest.raises(InvalidHandleError, match="local path"):
            skill_info("/absolute/path/skill")
