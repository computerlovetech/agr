"""Handle parsing for agr.

Handle formats:
- Remote: "username/skill" or "username/repo/skill"
- Local: "./path/to/skill" or "path/to/skill"

Installed naming (Windows-compatible using -- separator) used on collisions:
- Remote: "username--skill" or "username--repo--skill"
- Local: "local--skillname"

For tools with nested directory support (e.g., Cursor):
- Remote: username/repo/skill/ or username/skill/
- Local: local/skillname/
"""

import warnings
from dataclasses import dataclass
from pathlib import Path
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
# Prefixes that indicate a raw string is a local filesystem path
LOCAL_PATH_PREFIXES = ("./", "../", "/")
DEFAULT_REPO_NAME = "skills"
DEFAULT_OWNER = "computerlovetech"
LEGACY_DEFAULT_REPO_NAME = "agent-resources"
LEGACY_REPO_DEPRECATION_WARNING = (
    "Deprecated: owner-only handles now default to the 'skills' "
    "repo. Falling back to the legacy 'agent-resources' repo. "
    "Use an explicit handle like 'owner/agent-resources/skill' "
    "or move/rename your repo to 'skills'."
)


def warn_legacy_repo() -> None:
    """Issue a deprecation warning for legacy 'agent-resources' repo fallback.

    Centralizes the warning so callers don't repeat the message, category,
    and stacklevel. Uses ``stacklevel=3`` to point at the caller's caller
    (the public API entry point).
    """
    warnings.warn(LEGACY_REPO_DEPRECATION_WARNING, UserWarning, stacklevel=3)


def is_local_path_ref(ref: str) -> bool:
    """Check whether a raw string looks like a local filesystem path.

    Returns True for strings starting with ``./``, ``../``, or ``/``.
    """
    return ref.startswith(LOCAL_PATH_PREFIXES)


def iter_repo_candidates(
    repo: str | None, default_repo: str | None = None
) -> list[tuple[str, bool]]:
    """Return repo candidates for owner-only handles.

    Args:
        repo: Explicit repo name or None for defaults.
        default_repo: Configured default repo name. Falls back to
            ``DEFAULT_REPO_NAME`` ("skills") when *None*.

    Returns:
        List of (repo_name, is_legacy) candidates in priority order.
    """
    if repo:
        return [(repo, False)]
    effective_default = default_repo or DEFAULT_REPO_NAME
    candidates: list[tuple[str, bool]] = [(effective_default, False)]
    # Only try legacy fallback when using the standard default repo
    if effective_default == DEFAULT_REPO_NAME:
        candidates.append((LEGACY_DEFAULT_REPO_NAME, True))
    return candidates


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
            Remote: "vercel-labs/agent-browser" or "maragudk/skills/collaboration"
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
            Remote: "vercel-labs--agent-browser" or "maragudk--skills--collaboration"
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

    def get_github_repo(self, default_repo: str | None = None) -> tuple[str, str]:
        """Get (owner, repo_name) for git download.

        Args:
            default_repo: Configured default repo name. Falls back to
                ``DEFAULT_REPO_NAME`` ("skills") when *None*.

        Returns:
            Tuple of (owner, repo_name).

        Raises:
            InvalidHandleError: If this is a local handle.
        """
        if self.is_local:
            raise InvalidHandleError("Cannot get GitHub repo for local handle")
        if not self.username:
            raise InvalidHandleError("No username in handle")
        return (self.username, self.repo or default_repo or DEFAULT_REPO_NAME)

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

    def resolve_local_path(self, base: Path | None = None) -> Path:
        """Resolve local_path to an absolute path.

        Args:
            base: Base directory for resolving relative paths.
                  Defaults to the current working directory.

        Returns:
            The resolved absolute path.

        Raises:
            InvalidHandleError: If this is not a local handle or has no path.
        """
        if not self.is_local or self.local_path is None:
            raise InvalidHandleError("Cannot resolve path for non-local handle")
        if self.local_path.is_absolute():
            return self.local_path.resolve()
        root = base or Path.cwd()
        return (root / self.local_path).resolve()


def parse_handle(
    ref: str,
    *,
    prefer_local: bool = True,
    default_owner: str | None = None,
) -> ParsedHandle:
    """Parse a handle string into components.

    Args:
        ref: Handle string. Examples:
            - "setup" -> remote with default_owner, user=<default_owner>, name=setup
            - "vercel-labs/agent-browser" -> remote, user=vercel-labs, name=agent-browser
            - "maragudk/skills/collaboration" -> remote,
              user=maragudk, repo=skills, name=collaboration
            - "./my-skill" -> local, name=my-skill
            - "../other/skill" -> local, name=skill
        prefer_local: Prefer local paths when the ref exists on disk.
        default_owner: Default owner for 1-part handles (e.g. "setup" ->
            "<default_owner>/setup"). If None, 1-part handles raise an error.

    Returns:
        ParsedHandle with parsed components.

    Raises:
        InvalidHandleError: If the handle format is invalid.
    """
    if not ref or not ref.strip():
        raise InvalidHandleError("Empty handle")

    ref = ref.strip()

    # Strip trailing slashes for remote handles (e.g. "owner/repo/skill/").
    # Only strip when the ref is not a local path prefix — preserve "./" and "../".
    if not is_local_path_ref(ref):
        ref = ref.rstrip("/")

    if prefer_local:
        path = Path(ref)
        # Local path detection: starts with ./ ../ / or exists on disk
        if is_local_path_ref(ref) or path.exists():
            name = path.name
            if not name or name == "..":
                raise InvalidHandleError(
                    f"Invalid handle '{ref}': empty resource name "
                    "(path must point to a named directory, not '.' or '..')"
                )
            _validate_no_separator(ref, "name", name)
            return ParsedHandle(
                is_local=True,
                name=name,
                local_path=path,
            )

    # Remote handle: split by /
    parts = ref.split("/")

    # Reject empty components (e.g. "user//skill" → ["user", "", "skill"])
    if any(not part for part in parts):
        raise InvalidHandleError(
            f"Invalid handle '{ref}': contains empty path segments"
        )

    if len(parts) == 1:
        # Simple name like "commit" — resolve with default_owner if available
        if default_owner is not None:
            skill_name = parts[0]
            _validate_no_separator(ref, "skill name", skill_name)
            _validate_no_separator(ref, "default owner", default_owner)
            return ParsedHandle(username=default_owner, name=skill_name)
        raise InvalidHandleError(
            f"Invalid handle '{ref}': remote handles require username/name format"
        )

    if len(parts) == 2:
        # user/name format
        username, skill_name = parts[0], parts[1]
        _validate_no_separator(ref, "username", username)
        _validate_no_separator(ref, "skill name", skill_name)
        return ParsedHandle(
            username=username,
            name=skill_name,
        )

    if len(parts) == 3:
        # user/repo/name format
        username, repo, skill_name = parts[0], parts[1], parts[2]
        _validate_no_separator(ref, "username", username)
        _validate_no_separator(ref, "repo", repo)
        _validate_no_separator(ref, "skill name", skill_name)
        return ParsedHandle(
            username=username,
            repo=repo,
            name=skill_name,
        )

    raise InvalidHandleError(
        f"Invalid handle '{ref}': too many path segments "
        "(expected user/name or user/repo/name)"
    )


def parse_remote_handle(
    handle: str, *, default_owner: str | None = None
) -> ParsedHandle:
    """Parse a handle that must be a remote GitHub reference.

    Convenience wrapper around :func:`parse_handle` that rejects local paths
    up-front and enforces ``prefer_local=False``.

    Args:
        handle: Handle string (e.g. ``"anthropics/skills/code-review"``).
        default_owner: Forwarded to :func:`parse_handle`.

    Returns:
        A :class:`ParsedHandle` guaranteed to be remote.

    Raises:
        InvalidHandleError: If the handle resolves to a local path.
    """
    if is_local_path_ref(handle):
        raise InvalidHandleError(f"'{handle}' is a local path, not a remote handle")

    parsed = parse_handle(handle, prefer_local=False, default_owner=default_owner)
    if parsed.is_local:
        raise InvalidHandleError(f"'{handle}' is a local path, not a remote handle")
    return parsed


def _validate_no_separator(ref: str, label: str, value: str) -> None:
    """Validate that a handle component doesn't contain the reserved separator.

    Args:
        ref: Original handle string for error messages.
        label: Human-readable label for the component (e.g. "name", "username").
        value: The component value to validate.

    Raises:
        InvalidHandleError: If the value contains the separator.
    """
    if INSTALLED_NAME_SEPARATOR in value:
        raise InvalidHandleError(
            f"Invalid handle '{ref}': {label} '{value}' "
            f"contains reserved sequence "
            f"'{INSTALLED_NAME_SEPARATOR}'"
        )
