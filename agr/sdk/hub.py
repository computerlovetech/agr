"""Hub functions for discovering skills on GitHub."""

import base64
import json
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError

from agr.exceptions import (
    AgrError,
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
    is_local_path_ref,
    iter_repo_candidates,
    parse_handle,
    warn_legacy_repo,
)
from agr.sdk.types import SkillInfo
from agr.skill import (
    SKILL_MARKER,
    discover_skills_in_repo_listing,
    find_skill_in_repo_listing,
    parse_frontmatter,
)


GITHUB_API_BASE = "https://api.github.com"


def _build_display_handle(owner: str, repo: str, skill_name: str) -> str:
    """Build a user-facing handle string, omitting the repo for the default.

    Two-part handles (``owner/skill``) are used when the skill lives in the
    default repo (``skills``); three-part handles (``owner/repo/skill``)
    are used otherwise.
    """
    if repo == DEFAULT_REPO_NAME:
        return f"{owner}/{skill_name}"
    return f"{owner}/{repo}/{skill_name}"


def _github_tree_url(owner: str, repo: str) -> str:
    """Build a GitHub API URL for fetching a repository's full tree."""
    return f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"


def _github_contents_url(owner: str, repo: str, path: str) -> str:
    """Build a GitHub API URL for fetching file contents."""
    return f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"


@dataclass
class _RepoTreeResult:
    """Result of fetching a repo tree across candidate repo names."""

    tree_data: dict[str, Any]
    repo: str
    used_legacy: bool


def _fetch_repo_tree(
    owner: str,
    repo_candidates: list[tuple[str, bool]],
) -> _RepoTreeResult:
    """Try repo candidates in order and return the first successful tree fetch.

    Raises:
        RepoNotFoundError: If no candidate repo exists.
    """
    last_error: Exception | None = None
    for repo_name, is_legacy in repo_candidates:
        try:
            tree_data = _github_api_request(_github_tree_url(owner, repo_name))
            return _RepoTreeResult(
                tree_data=tree_data, repo=repo_name, used_legacy=is_legacy
            )
        except RepoNotFoundError as e:
            last_error = e
            continue
    if last_error:
        raise last_error
    raise RepoNotFoundError(f"Repository not found for owner: {owner}")


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
        raise AgrError(f"Failed to connect to GitHub API: {e}") from e


def _extract_paths_from_tree(tree_data: dict[str, Any]) -> list[str]:
    """Extract file paths from a GitHub API tree response.

    Filters to blob (file) entries only, producing the same format
    used by ``git ls-tree`` so that ``agr.skill`` discovery functions
    can be reused directly.
    """
    return [
        item["path"]
        for item in tree_data.get("tree", [])
        if item.get("type") == "blob" and item.get("path")
    ]


def _find_skill_md_in_tree(tree_data: dict[str, Any], skill_name: str) -> str | None:
    """Find the path to a skill's SKILL.md in a GitHub tree response.

    Uses the same discovery logic as the CLI (``find_skill_in_repo_listing``)
    to ensure consistent filtering of excluded directories.

    Returns the SKILL.md path string if found, None otherwise.
    """
    paths = _extract_paths_from_tree(tree_data)
    skill_dir = find_skill_in_repo_listing(paths, skill_name)
    if skill_dir is None:
        return None
    return f"{skill_dir.as_posix()}/{SKILL_MARKER}"


def _extract_description(skill_md_content: str) -> str | None:
    """Extract description from SKILL.md content.

    Takes the first paragraph after any frontmatter.
    """
    parsed = parse_frontmatter(skill_md_content)
    body = parsed[1] if parsed else skill_md_content

    # Find first non-empty, non-heading line
    description_lines: list[str] = []
    for line in body.split("\n"):
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
        InvalidHandleError: If repo handle format is invalid
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
        raise InvalidHandleError(f"Invalid repo handle: {repo_handle}")

    result = _fetch_repo_tree(owner, list(repo_candidates))
    tree_data = result.tree_data
    repo = result.repo
    used_legacy = result.used_legacy

    # Discover skills using the same logic as the CLI, which filters
    # excluded directories (node_modules, .git, etc.) and root-level
    # SKILL.md files.
    paths = _extract_paths_from_tree(tree_data)
    skill_names = discover_skills_in_repo_listing(paths)

    # Build SkillInfo objects
    skills = []
    if used_legacy:
        warn_legacy_repo()

    for name in skill_names:
        handle = _build_display_handle(owner, repo, name)
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
    if is_local_path_ref(handle):
        raise InvalidHandleError(f"'{handle}' is a local path, not a remote handle")

    parsed = parse_handle(handle, prefer_local=False)
    if parsed.is_local:
        raise InvalidHandleError(f"'{handle}' is a local path, not a remote handle")

    owner, initial_repo = parsed.get_github_repo()
    repo_candidates = iter_repo_candidates(parsed.repo)

    try:
        result = _fetch_repo_tree(owner, list(repo_candidates))
    except RepoNotFoundError:
        raise SkillNotFoundError(
            f"Repository '{owner}/{initial_repo}' not found"
        ) from None
    tree_data = result.tree_data
    repo = result.repo
    used_legacy = result.used_legacy

    # Find SKILL.md for this skill
    skill_md_path = _find_skill_md_in_tree(tree_data, parsed.name)

    if (
        skill_md_path is None
        and parsed.repo is None
        and repo != LEGACY_DEFAULT_REPO_NAME
    ):
        # Try legacy repo if skill not found in default repo
        try:
            legacy_tree = _github_api_request(
                _github_tree_url(owner, LEGACY_DEFAULT_REPO_NAME)
            )
            skill_md_path = _find_skill_md_in_tree(legacy_tree, parsed.name)
            if skill_md_path is not None:
                repo = LEGACY_DEFAULT_REPO_NAME
                used_legacy = True
        except RepoNotFoundError:
            pass

    if not skill_md_path:
        raise SkillNotFoundError(
            f"Skill '{parsed.name}' not found in repository '{owner}/{repo}'"
        )

    # Fetch SKILL.md content
    content_url = _github_contents_url(owner, repo, skill_md_path)
    content_data = _github_api_request(content_url)

    description = None
    if content_data.get("encoding") == "base64":
        content = base64.b64decode(content_data.get("content", "")).decode()
        description = _extract_description(content)

    if used_legacy:
        warn_legacy_repo()

    full_handle = _build_display_handle(owner, repo, parsed.name)

    return SkillInfo(
        name=parsed.name,
        handle=full_handle,
        description=description,
        repo=repo,
        owner=owner,
    )
