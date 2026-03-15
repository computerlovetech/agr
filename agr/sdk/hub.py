"""Hub functions for discovering skills on GitHub."""

import json
import urllib.request
import warnings
from typing import Any
from urllib.error import HTTPError, URLError

from agr.exceptions import (
    AuthenticationError,
    InvalidHandleError,
    RateLimitError,
    RepoNotFoundError,
    SkillNotFoundError,
)
from agr.git import get_github_token
from agr.handle import (
    DEFAULT_REPO_NAME,
    LEGACY_DEFAULT_REPO_NAME,
    LEGACY_REPO_DEPRECATION_WARNING,
    iter_repo_candidates,
    parse_handle,
)
from agr.sdk.types import SkillInfo
from agr.skill import SKILL_MARKER


def _github_api_request(url: str) -> dict[str, Any]:
    """Make an authenticated request to GitHub API.

    Args:
        url: GitHub API URL

    Returns:
        Parsed JSON response

    Raises:
        AuthenticationError: If authentication fails
        RepoNotFoundError: If repository not found
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "agr-sdk",
    }

    token = get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        # Handle rate limiting (HTTP 429)
        if e.code == 429:
            raise RateLimitError("GitHub API rate limit exceeded") from e
        # Handle 403 with rate limit header (secondary rate limit)
        if e.code == 403:
            rate_limit_remaining = e.headers.get("X-RateLimit-Remaining", "")
            if rate_limit_remaining == "0":
                raise RateLimitError("GitHub API rate limit exceeded") from e
            raise AuthenticationError(
                f"GitHub API authentication failed (HTTP {e.code})"
            ) from e
        if e.code == 401:
            raise AuthenticationError(
                f"GitHub API authentication failed (HTTP {e.code})"
            ) from e
        if e.code == 404:
            raise RepoNotFoundError(f"Repository not found: {url}") from e
        raise
    except URLError as e:
        raise ConnectionError(f"Failed to connect to GitHub API: {e}") from e


def _extract_description(skill_md_content: str) -> str | None:
    """Extract description from SKILL.md content.

    Takes the first paragraph after any frontmatter.
    """
    lines = skill_md_content.split("\n")

    # Skip frontmatter
    start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                start = i + 1
                break

    # Find first non-empty, non-heading line
    description_lines = []
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            if description_lines:
                break
            continue
        if stripped.startswith("#"):
            if description_lines:
                break
            continue
        description_lines.append(stripped)

    if not description_lines:
        return None

    return " ".join(description_lines)[:200]


def list_skills(repo_handle: str) -> list[SkillInfo]:
    """List all skills in a GitHub repository.

    Discovers skills by finding SKILL.md files in the repository tree.

    Args:
        repo_handle: Repository handle (e.g., "owner/repo" or "owner" for default repo)

    Returns:
        List of SkillInfo objects for each skill found

    Raises:
        RepoNotFoundError: If repository not found
        AuthenticationError: If authentication fails

    Example:
        >>> skills = list_skills("anthropics/skills")
        >>> for skill in skills:
        ...     print(f"{skill.name}: {skill.description}")
    """
    # Parse handle to get owner/repo
    parts = repo_handle.split("/")
    if len(parts) == 1:
        owner = parts[0]
        repo_candidates = iter_repo_candidates(None)
    elif len(parts) == 2:
        owner, repo = parts
        repo_candidates = [(repo, False)]
    else:
        raise ValueError(f"Invalid repo handle: {repo_handle}")

    tree_data = None
    repo = None
    used_legacy = False
    last_error: Exception | None = None
    for repo_name, is_legacy in repo_candidates:
        # Get repository tree
        tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1"
        try:
            tree_data = _github_api_request(tree_url)
            repo = repo_name
            used_legacy = is_legacy
            break
        except RepoNotFoundError as e:
            last_error = e
            continue

    if tree_data is None or repo is None:
        if last_error:
            raise last_error
        raise RepoNotFoundError(f"Repository not found: {repo_handle}")

    # Find SKILL.md files
    skill_dirs: dict[str, str] = {}  # name -> path
    for item in tree_data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")

        # Must end with SKILL.md and be in a subdirectory (not root)
        if not path.endswith(SKILL_MARKER) or "/" not in path:
            continue

        # Extract skill name from parent directory
        skill_path = path.rsplit(f"/{SKILL_MARKER}", 1)[0]
        skill_name = skill_path.rsplit("/", 1)[-1]
        if skill_name not in skill_dirs:
            skill_dirs[skill_name] = skill_path

    # Build SkillInfo objects
    skills = []
    if used_legacy:
        warnings.warn(
            LEGACY_REPO_DEPRECATION_WARNING,
            UserWarning,
            stacklevel=2,
        )

    for name, path in sorted(skill_dirs.items()):
        # Construct handle
        if repo == DEFAULT_REPO_NAME:
            handle = f"{owner}/{name}"
        else:
            handle = f"{owner}/{repo}/{name}"

        skills.append(
            SkillInfo(
                name=name,
                handle=handle,
                description=None,  # Lazy - fetch on demand
                repo=repo,
                owner=owner,
            )
        )

    return skills


def skill_info(handle: str) -> SkillInfo:
    """Get detailed information about a skill.

    Fetches the SKILL.md content to extract description.

    Args:
        handle: Skill handle (e.g., "owner/skill" or "owner/repo/skill")

    Returns:
        SkillInfo with full details including description

    Raises:
        SkillNotFoundError: If skill not found
        InvalidHandleError: If handle format is invalid

    Example:
        >>> info = skill_info("anthropics/skills/code-review")
        >>> print(info.description)
    """
    # Reject obvious local paths
    if handle.startswith(("./", "../", "/")):
        raise InvalidHandleError(f"'{handle}' is a local path, not a remote handle")

    parsed = parse_handle(handle, prefer_local=False)
    if parsed.is_local:
        raise InvalidHandleError(f"'{handle}' is a local path, not a remote handle")

    owner, initial_repo = parsed.get_github_repo()
    repo_candidates = iter_repo_candidates(parsed.repo)

    tree_data = None
    repo = None
    used_legacy = False
    last_error: Exception | None = None
    for repo_name, is_legacy in repo_candidates:
        tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1"
        try:
            tree_data = _github_api_request(tree_url)
            repo = repo_name
            used_legacy = is_legacy
            break
        except RepoNotFoundError as e:
            last_error = e
            continue

    if tree_data is None or repo is None:
        if last_error:
            raise SkillNotFoundError(
                f"Repository '{owner}/{initial_repo}' not found"
            ) from None
        raise SkillNotFoundError(f"Repository '{owner}/{initial_repo}' not found")

    # Find SKILL.md for this skill
    skill_md_path = None
    for item in tree_data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if (
            path.endswith(f"/{parsed.name}/{SKILL_MARKER}")
            or path == f"{parsed.name}/{SKILL_MARKER}"
        ):
            skill_md_path = path
            break

    if skill_md_path is None and parsed.repo is None:
        # Try legacy repo if skill not found in default repo
        if repo != LEGACY_DEFAULT_REPO_NAME:
            try:
                legacy_tree_url = f"https://api.github.com/repos/{owner}/{LEGACY_DEFAULT_REPO_NAME}/git/trees/HEAD?recursive=1"
                legacy_tree = _github_api_request(legacy_tree_url)
                for item in legacy_tree.get("tree", []):
                    if item.get("type") != "blob":
                        continue
                    path = item.get("path", "")
                    if (
                        path.endswith(f"/{parsed.name}/{SKILL_MARKER}")
                        or path == f"{parsed.name}/{SKILL_MARKER}"
                    ):
                        skill_md_path = path
                        repo = LEGACY_DEFAULT_REPO_NAME
                        used_legacy = True
                        tree_data = legacy_tree
                        break
            except RepoNotFoundError:
                pass

    if not skill_md_path:
        raise SkillNotFoundError(
            f"Skill '{parsed.name}' not found in repository '{owner}/{repo}'"
        )

    # Fetch SKILL.md content
    content_url = (
        f"https://api.github.com/repos/{owner}/{repo}/contents/{skill_md_path}"
    )
    content_data = _github_api_request(content_url)

    description = None
    if content_data.get("encoding") == "base64":
        import base64

        content = base64.b64decode(content_data.get("content", "")).decode()
        description = _extract_description(content)

    if used_legacy:
        warnings.warn(
            LEGACY_REPO_DEPRECATION_WARNING,
            UserWarning,
            stacklevel=2,
        )

    # Construct handle
    if repo == DEFAULT_REPO_NAME:
        full_handle = f"{owner}/{parsed.name}"
    else:
        full_handle = f"{owner}/{repo}/{parsed.name}"

    return SkillInfo(
        name=parsed.name,
        handle=full_handle,
        description=description,
        repo=repo,
        owner=owner,
    )
