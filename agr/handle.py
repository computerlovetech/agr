"""Handle parsing for agr.

Handle formats:
- Remote: "username/skill" or "username/repo/skill"
- Remote URL: "https://github.com/user/repo/tree/branch/path/to/skill"
- Local: "./path/to/skill" or "path/to/skill"

Installed naming (Windows-compatible using -- separator) used on collisions:
- Remote: "username--skill" or "username--repo--skill"
- Local: "local--skillname"

For tools with nested directory support (e.g., Cursor):
- Remote: username/repo/skill/ or username/skill/
- Local: local/skillname/
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from typing import TYPE_CHECKING

from agr.exceptions import InvalidHandleError

if TYPE_CHECKING:
    from agr.tool import ToolConfig

# Separator used in installed directory names (Windows-compatible)
INSTALLED_NAME_SEPARATOR = "--"
# Prefix for local skills in installed name
LOCAL_PREFIX = "local"
# Legacy separator (colon) for backward compatibility during migration
LEGACY_SEPARATOR = ":"
DEFAULT_REPO_NAME = "skills"
LEGACY_DEFAULT_REPO_NAME = "agent-resources"
LEGACY_REPO_DEPRECATION_WARNING = (
    "Deprecated: owner-only handles now default to the 'skills' "
    "repo. Falling back to the legacy 'agent-resources' repo. "
    "Use an explicit handle like 'owner/agent-resources/skill' "
    "or move/rename your repo to 'skills'."
)


def iter_repo_candidates(repo: str | None) -> list[tuple[str, bool]]:
    """Return repo candidates for owner-only handles.

    Args:
        repo: Explicit repo name or None for defaults.

    Returns:
        List of (repo_name, is_legacy) candidates in priority order.
    """
    if repo:
        return [(repo, False)]
    return [
        (DEFAULT_REPO_NAME, False),
        (LEGACY_DEFAULT_REPO_NAME, True),
    ]


@dataclass
class ParsedHandle:
    """Parsed resource handle."""

    username: str | None = None  # GitHub username, None for local
    repo: str | None = None  # Repository name, None = default (skills)
    name: str = ""  # Skill name (final segment)
    is_local: bool = False  # True for local path references
    local_path: Path | None = None  # Original local path if is_local

    @property
    def is_remote(self) -> bool:
        """True if this is a remote GitHub reference."""
        return not self.is_local and self.username is not None

    def to_toml_handle(self) -> str:
        """Convert to agr.toml format.

        Examples:
            Remote: "kasperjunge/commit" or "maragudk/skills/collaboration"
            Local: "./my-skill"
        """
        if self.is_local and self.local_path:
            return str(self.local_path)

        if not self.username:
            return self.name

        if self.repo:
            return f"{self.username}/{self.repo}/{self.name}"
        return f"{self.username}/{self.name}"

    def to_installed_name(self) -> str:
        """Convert to installed directory name.

        Uses INSTALLED_NAME_SEPARATOR (--) for Windows compatibility.

        Examples:
            Remote: "kasperjunge--commit" or "maragudk--skills--collaboration"
            Local: "local--my-skill"
        """
        sep = INSTALLED_NAME_SEPARATOR
        if self.is_local:
            return f"{LOCAL_PREFIX}{sep}{self.name}"

        if not self.username:
            return self.name

        if self.repo:
            return f"{self.username}{sep}{self.repo}{sep}{self.name}"
        return f"{self.username}{sep}{self.name}"

    def get_github_repo(self) -> tuple[str, str]:
        """Get (owner, repo_name) for git download.

        Returns:
            Tuple of (owner, repo_name). repo_name defaults to "skills".

        Raises:
            InvalidHandleError: If this is a local handle.
        """
        if self.is_local:
            raise InvalidHandleError("Cannot get GitHub repo for local handle")
        if not self.username:
            raise InvalidHandleError("No username in handle")
        return (self.username, self.repo or DEFAULT_REPO_NAME)

    def to_skill_path(self, tool: "ToolConfig") -> Path:
        """Get default skill installation path based on tool capabilities.

        Args:
            tool: Tool configuration determining path structure

        Returns:
            Path relative to the skills directory.
            - Flat tools (Claude): Path("<skill-name>") by default
            - Nested tools (Cursor): Path("local/my-skill") or Path("user/repo/skill")
        """
        if tool.supports_nested:
            if self.is_local:
                return Path("local") / self.name
            if self.repo:
                return Path(self.username or "") / self.repo / self.name
            return Path(self.username or "") / self.name
        return Path(self.name)

    def resolve_local_path(self) -> Path:
        """Resolve local_path to an absolute path.

        Returns:
            The resolved absolute path.

        Raises:
            InvalidHandleError: If this is not a local handle or has no path.
        """
        if not self.is_local or self.local_path is None:
            raise InvalidHandleError("Cannot resolve path for non-local handle")
        return self.local_path.resolve()

    def get_skill_name_for_tool(self, tool: "ToolConfig") -> str:
        """Get the skill name to use in SKILL.md frontmatter.

        Currently returns the skill name for all tools. The ``tool``
        parameter is accepted for future extensibility.
        """
        return self.name


def parse_handle(ref: str, *, prefer_local: bool = True) -> ParsedHandle:
    """Parse a handle string into components.

    Args:
        ref: Handle string. Examples:
            - "kasperjunge/commit" -> remote, user=kasperjunge, name=commit
            - "maragudk/skills/collaboration" -> remote,
              user=maragudk, repo=skills, name=collaboration
            - "./my-skill" -> local, name=my-skill
            - "../other/skill" -> local, name=skill
        prefer_local: Prefer local paths when the ref exists on disk.

    Returns:
        ParsedHandle with parsed components.

    Raises:
        InvalidHandleError: If the handle format is invalid.
    """
    if not ref or not ref.strip():
        raise InvalidHandleError("Empty handle")

    ref = ref.strip()

    # Try to parse as a GitHub URL first
    normalized = _try_parse_github_url(ref)
    if normalized is not None:
        ref = normalized

    if prefer_local:
        # Local path detection: starts with . or /
        if ref.startswith(("./", "../", "/")):
            path = Path(ref)
            _validate_no_separator_in_name(ref, path.name)
            return ParsedHandle(
                is_local=True,
                name=path.name,
                local_path=path,
            )

        # Prefer local if the path exists (even with one slash)
        test_path = Path(ref)
        if test_path.exists():
            _validate_no_separator_in_name(ref, test_path.name)
            return ParsedHandle(
                is_local=True,
                name=test_path.name,
                local_path=test_path,
            )

    # Remote handle: split by /
    parts = ref.split("/")

    if len(parts) == 1:
        # Simple name like "commit" - treat as local since no username
        raise InvalidHandleError(
            f"Invalid handle '{ref}': remote handles require username/name format"
        )

    if len(parts) == 2:
        # user/name format
        username, skill_name = parts[0], parts[1]
        _validate_no_separator_in_components(
            ref, username=username, skill_name=skill_name
        )
        return ParsedHandle(
            username=username,
            name=skill_name,
        )

    if len(parts) == 3:
        # user/repo/name format
        username, repo, skill_name = parts[0], parts[1], parts[2]
        _validate_no_separator_in_components(
            ref, username=username, repo=repo, skill_name=skill_name
        )
        return ParsedHandle(
            username=username,
            repo=repo,
            name=skill_name,
        )

    raise InvalidHandleError(
        f"Invalid handle '{ref}': too many path segments "
        "(expected user/name or user/repo/name)"
    )


def _try_parse_github_url(ref: str) -> str | None:
    """Try to parse a GitHub URL into a handle string.

    Converts URLs like:
        https://github.com/user/repo/tree/branch/path/to/skill
    Into handle strings like:
        user/repo/skill

    Args:
        ref: The input string that might be a GitHub URL.

    Returns:
        Normalized handle string if the input is a GitHub URL, None otherwise.

    Raises:
        InvalidHandleError: If it looks like a GitHub URL but can't be parsed.
    """
    # Fast path: skip urlparse for non-URL inputs
    if "://" not in ref:
        return None

    parsed = urlparse(ref)
    if parsed.hostname != "github.com":
        return None

    # Strip leading/trailing slashes and split
    path_parts = [p for p in parsed.path.split("/") if p]

    if len(path_parts) < 2:
        raise InvalidHandleError(
            f"Invalid GitHub URL '{ref}': expected at least user/repo in the path"
        )

    username = path_parts[0]
    repo = path_parts[1]

    # Bare repo URL: https://github.com/user/repo
    if len(path_parts) == 2:
        return f"{username}/{repo}"

    # URL with /tree/branch/... or /blob/branch/...
    if len(path_parts) >= 4 and path_parts[2] in ("tree", "blob"):
        # path after branch — e.g. ["skills", "sample"] from /tree/main/skills/sample
        skill_path = path_parts[4:]
        if skill_path:
            return f"{username}/{repo}/{skill_path[-1]}"
        # Just https://github.com/user/repo/tree/branch (no subpath)
        return f"{username}/{repo}"

    raise InvalidHandleError(
        f"Invalid GitHub URL '{ref}': could not extract skill path. "
        f"Expected format: https://github.com/user/repo/tree/branch/path/to/skill"
    )


def _validate_no_separator_in_name(ref: str, name: str) -> None:
    """Validate that a name doesn't contain the reserved separator sequence.

    Args:
        ref: Original handle string for error messages.
        name: The name to validate.

    Raises:
        InvalidHandleError: If the name contains the separator.
    """
    if INSTALLED_NAME_SEPARATOR in name:
        raise InvalidHandleError(
            f"Invalid handle '{ref}': name '{name}' "
            f"contains reserved sequence "
            f"'{INSTALLED_NAME_SEPARATOR}'"
        )


def _validate_no_separator_in_components(
    ref: str,
    *,
    username: str | None = None,
    repo: str | None = None,
    skill_name: str | None = None,
) -> None:
    """Validate that no component contains the reserved separator sequence.

    Args:
        ref: Original handle string for error messages.
        username: GitHub username to validate.
        repo: Repository name to validate.
        skill_name: Skill name to validate.

    Raises:
        InvalidHandleError: If any component contains the separator.
    """
    sep = INSTALLED_NAME_SEPARATOR
    for component, name in [
        ("username", username),
        ("repo", repo),
        ("skill name", skill_name),
    ]:
        if name and sep in name:
            raise InvalidHandleError(
                f"Invalid handle '{ref}': "
                f"{component} '{name}' "
                f"contains reserved sequence "
                f"'{sep}'"
            )


def installed_name_to_toml_handle(installed_name: str) -> str:
    """Convert installed directory name back to agr.toml handle.

    Supports both new separator format and legacy colon format
    for backward compatibility.

    Args:
        installed_name: Directory name like "kasperjunge--commit" or "local--my-skill"
                       (also accepts legacy "kasperjunge:commit" or "local:my-skill")

    Returns:
        Handle like "kasperjunge/commit" or the local path
    """
    # Support legacy colon format during migration
    if LEGACY_SEPARATOR in installed_name:
        parts = installed_name.split(LEGACY_SEPARATOR)
        if parts[0] == LOCAL_PREFIX:
            return parts[1] if len(parts) > 1 else installed_name
        return "/".join(parts)

    # New separator format
    if INSTALLED_NAME_SEPARATOR not in installed_name:
        return installed_name

    parts = installed_name.split(INSTALLED_NAME_SEPARATOR)
    if parts[0] == LOCAL_PREFIX:
        # Local skill - return just the name (path is lost)
        return parts[1] if len(parts) > 1 else installed_name

    # Remote: convert separators to slashes
    return "/".join(parts)
