"""Skill installation, uninstallation, and query operations.

Handles local and remote skill installation, repo preparation,
destination resolution, and skill lifecycle management.
"""

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator

from agr._install_common import (
    InstallResult,
    _RemoteDepLocation,
    _locate_remote_dep,
    cleanup_empty_parents,
    _dep_not_found_message,
    _dir_matches_handle,
    list_remote_repo_deps,
    prepare_repo_for_deps,
    _resolve_skills_dir,
    _rollback_on_failure,
)
from agr.exceptions import (
    AgrError,
    InvalidHandleError,
    InvalidLocalPathError,
    SkillNotFoundError,
)
from agr.handle import (
    INSTALLED_NAME_SEPARATOR,
    ParsedHandle,
    warn_legacy_repo,
)
from agr.metadata import (
    METADATA_KEY_ID,
    METADATA_KEY_TYPE,
    METADATA_TYPE_LOCAL,
    build_handle_id,
    build_handle_ids,
    compute_content_hash,
    read_skill_metadata,
    stamp_skill_metadata,
)
from agr.skill import (
    SKILL_MARKER,
    discover_skills_in_repo_listing,
    find_skill_in_repo,
    find_skills_in_repo_listing,
    is_valid_skill_dir,
    update_skill_md_name,
)
from agr.source import SourceResolver
from agr.tool import DEFAULT_TOOL, ToolConfig, lookup_skills_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _find_local_name_conflicts(
    handle: ParsedHandle,
    skills_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    default_dest: Path,
) -> tuple[list[Path], bool]:
    """Find conflicting local installs with the same skill name.

    Returns a tuple of (conflict_paths, has_unknown_metadata).
    """
    handle_id = build_handle_id(handle, repo_root)
    conflicts: list[Path] = []
    has_unknown = False

    # Nested tools store local skills under local/<name>; flat tools may
    # use either the plain name or the full user--repo--skill form.
    if tool.supports_nested:
        candidates = [skills_dir / "local" / handle.name]
    else:
        candidates = [skills_dir / handle.name, skills_dir / handle.to_installed_name()]

    for path in candidates:
        # Skip the path we'd install to (it's not a conflict with itself).
        if tool.supports_nested and path == default_dest:
            continue
        if not is_valid_skill_dir(path):
            continue
        meta = read_skill_metadata(path)
        if meta:
            # Remote skills at this path are not local conflicts.
            if meta.get(METADATA_KEY_TYPE) != METADATA_TYPE_LOCAL:
                continue
            # Same local handle — this is us, not a conflict.
            if meta.get(METADATA_KEY_ID) == handle_id:
                continue
            conflicts.append(path)
            continue
        # No metadata means we can't determine ownership — flag it.
        has_unknown = True
        conflicts.append(path)

    return conflicts, has_unknown


def _find_existing_skill_dir(
    handle: ParsedHandle,
    skills_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    source: str | None = None,
) -> Path | None:
    """Find an existing installed skill directory for this handle.

    For nested tools (Cursor), the path is deterministic from the handle.
    For flat tools, we check two candidate paths in priority order:
    1. Plain name (e.g. ``skill/``) — preferred, requires metadata ID match
    2. Full name (e.g. ``user--repo--skill/``) — accepted without metadata
       (covers both current installs and legacy installs without metadata)
    """
    if tool.supports_nested:
        skill_path = skills_dir / handle.to_skill_path(tool)
        return skill_path if is_valid_skill_dir(skill_path) else None

    # Build all possible metadata IDs for this handle, including legacy
    # formats (with/without explicit source name).
    handle_ids = build_handle_ids(handle, repo_root, source)
    name_path = skills_dir / handle.name
    full_path = skills_dir / handle.to_installed_name()

    # Prefer the plain-name path if metadata confirms it's ours.
    if is_valid_skill_dir(name_path) and _dir_matches_handle(name_path, handle_ids):
        return name_path

    # Fall back to the full (qualified) name path without requiring a
    # metadata match.  Older versions always installed under the full
    # name (user--repo--skill), potentially without metadata, so
    # matching by directory name alone keeps those installs reachable.
    if is_valid_skill_dir(full_path):
        return full_path

    return None


def _resolve_skill_destination(
    handle: ParsedHandle,
    skills_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    source: str | None = None,
) -> Path:
    """Resolve the destination path for installing a skill.

    For flat tools, the resolution order is:
    1. If the skill is already installed (any name form), reuse that path.
    2. If the plain name (e.g. ``skill/``) is free, use it.
    3. If the plain name is taken by a *different* skill, fall back to the
       fully qualified name (e.g. ``user--repo--skill/``).
    """
    if tool.supports_nested:
        return skills_dir / handle.to_skill_path(tool)

    existing = _find_existing_skill_dir(handle, skills_dir, tool, repo_root, source)
    if existing:
        return existing

    # Plain name is occupied by a different skill — use full name to avoid collision.
    name_path = skills_dir / handle.name
    if is_valid_skill_dir(name_path):
        return skills_dir / handle.to_installed_name()

    return name_path


# ---------------------------------------------------------------------------
# Repo preparation & discovery
# ---------------------------------------------------------------------------


def prepare_repo_for_skill(repo_dir: Path, skill_name: str) -> Path | None:
    """Prepare a repo so that only the skill path is checked out."""
    result = prepare_repo_for_skills(repo_dir, [skill_name])
    return result.get(skill_name)


def prepare_repo_for_skills(repo_dir: Path, skill_names: list[str]) -> dict[str, Path]:
    """Prepare a repo so multiple skill paths are checked out.

    Returns a mapping of skill name to resolved path for those found.
    Missing skills are omitted from the mapping.
    """
    return prepare_repo_for_deps(
        repo_dir, skill_names, find_skills_in_repo_listing, find_skill_in_repo, "skill"
    )


def list_remote_repo_skills(
    owner: str,
    repo_name: str,
    resolver: SourceResolver | None = None,
    source: str | None = None,
) -> list[str]:
    """List all skill names in a remote repository.

    Clones the repo and scans for SKILL.md files. Used to provide
    helpful suggestions when a two-part handle fails.

    Args:
        owner: Repository owner/username
        repo_name: Repository name
        resolver: Source resolver for finding the repo
        source: Explicit source name

    Returns:
        Sorted list of skill names found, or empty list on any error.
    """
    return list_remote_repo_deps(
        owner, repo_name, discover_skills_in_repo_listing, resolver, source
    )


# ---------------------------------------------------------------------------
# Copy & error messages
# ---------------------------------------------------------------------------


def _copy_skill_to_destination(
    source: Path,
    dest: Path,
    handle: ParsedHandle,
    tool: ToolConfig,
    overwrite: bool,
    repo_root: Path | None,
    install_source: str | None = None,
) -> Path:
    """Copy skill source to destination with overwrite handling.

    Args:
        source: Source skill directory
        dest: Destination path
        handle: Parsed handle for naming
        tool: Tool configuration
        overwrite: Whether to overwrite existing
        repo_root: Repository root for metadata resolution (optional)
        install_source: Source name to record in metadata (optional)

    Returns:
        Path to installed skill

    Raises:
        FileExistsError: If skill exists and not overwriting
    """
    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Skill already exists at {dest}. Use --overwrite to replace."
        )

    if dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    update_skill_md_name(dest, dest.name)
    stamp_skill_metadata(dest, handle, repo_root, tool.name, dest.name, install_source)

    return dest


def skill_not_found_message(name: str) -> str:
    """Build a user-friendly message for a missing skill in a repository."""
    return _dep_not_found_message("Skill", name, SKILL_MARKER, "skills")


# ---------------------------------------------------------------------------
# Install orchestration
# ---------------------------------------------------------------------------


def install_skill_from_repo(
    repo_dir: Path,
    skill_name: str,
    handle: ParsedHandle,
    dest_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    overwrite: bool = False,
    install_source: str | None = None,
    skill_source: Path | None = None,
) -> Path:
    """Install a skill from a downloaded repository.

    Args:
        repo_dir: Path to extracted repository
        skill_name: Name of the skill to install
        handle: Parsed handle for naming
        dest_dir: Destination skills directory
        tool: Tool configuration for path structure
        repo_root: Repository root for metadata resolution (optional)
        overwrite: Whether to overwrite existing
        install_source: Source name to record in metadata (optional)
        skill_source: Pre-resolved skill path within repo (optional,
            skips repo scanning when provided)

    Returns:
        Path to installed skill

    Raises:
        SkillNotFoundError: If skill not found in repo
        FileExistsError: If skill exists and not overwriting
    """
    # Find the skill in the repo
    if skill_source is None:
        skill_source = find_skill_in_repo(repo_dir, skill_name)
    if skill_source is None:
        raise SkillNotFoundError(skill_not_found_message(skill_name))

    skill_dest = _resolve_skill_destination(
        handle, dest_dir, tool, repo_root, install_source
    )

    return _copy_skill_to_destination(
        skill_source, skill_dest, handle, tool, overwrite, repo_root, install_source
    )


def install_skill_from_repo_to_tools(
    repo_dir: Path,
    skill_name: str,
    handle: ParsedHandle,
    tools: list[ToolConfig],
    repo_root: Path | None,
    overwrite: bool = False,
    install_source: str | None = None,
    skill_source: Path | None = None,
) -> dict[str, Path]:
    """Install a skill from a downloaded repo to multiple tools.

    On partial failure, already installed tools are rolled back.
    """
    if not tools:
        raise AgrError("No tools provided for installation")

    with _rollback_on_failure() as installed:
        for tool in tools:
            skills_dir = _resolve_skills_dir(None, repo_root, tool)
            path = install_skill_from_repo(
                repo_dir,
                skill_name,
                handle,
                skills_dir,
                tool,
                repo_root,
                overwrite,
                install_source=install_source,
                skill_source=skill_source,
            )
            installed[tool.name] = path

    return installed


def install_local_skill(
    source_path: Path,
    dest_dir: Path,
    tool: ToolConfig,
    overwrite: bool = False,
    repo_root: Path | None = None,
    handle: ParsedHandle | None = None,
) -> Path:
    """Install a local skill.

    Args:
        source_path: Path to local skill directory
        dest_dir: Destination skills directory
        tool: Tool configuration for path structure
        overwrite: Whether to overwrite existing
        repo_root: Repository root for metadata resolution (optional)
        handle: Optional pre-parsed handle for metadata and naming

    Returns:
        Path to installed skill

    Raises:
        SkillNotFoundError: If source is not a valid skill
        FileExistsError: If skill exists and not overwriting
        AgrError: If skill name contains reserved separator
    """
    # Validate source
    if not is_valid_skill_dir(source_path):
        raise SkillNotFoundError(
            f"'{source_path}' is not a valid skill (missing {SKILL_MARKER})"
        )

    # Validate skill name doesn't contain reserved separator (for flat tools)
    if not tool.supports_nested and INSTALLED_NAME_SEPARATOR in source_path.name:
        raise AgrError(
            f"Skill name '{source_path.name}' contains "
            f"reserved sequence "
            f"'{INSTALLED_NAME_SEPARATOR}'"
        )

    # Determine installed path using ParsedHandle for consistency
    handle = handle or ParsedHandle(
        is_local=True, name=source_path.name, local_path=source_path
    )
    if repo_root is None:
        repo_root = Path.cwd()

    # Self-install case: the source path is already the install destination
    # (e.g. `agr add ./skills/my-skill` when skills/ is the tool's skills dir).
    # Skip copying; just stamp metadata if missing.
    default_dest = dest_dir / handle.to_skill_path(tool)
    if source_path.resolve() == default_dest.resolve() and is_valid_skill_dir(
        default_dest
    ):
        if read_skill_metadata(default_dest) is None:
            stamp_skill_metadata(
                default_dest, handle, repo_root, tool.name, default_dest.name
            )
        return default_dest

    conflicts, has_unknown = _find_local_name_conflicts(
        handle, dest_dir, tool, repo_root, default_dest
    )
    if conflicts:
        locations = ", ".join(str(path) for path in conflicts)
        hint = ""
        if has_unknown:
            hint = (
                " If this is a remote skill, run "
                "`agr sync` or reinstall it to "
                "add metadata."
            )
        raise AgrError(
            f"Local skill name '{handle.name}' is already installed at {locations}. "
            "agr allows only one local skill with a given name. "
            "Rename the skill or remove the existing one."
            f"{hint}"
        )

    skill_dest = _resolve_skill_destination(handle, dest_dir, tool, repo_root)

    return _copy_skill_to_destination(
        source_path, skill_dest, handle, tool, overwrite, repo_root
    )


@contextmanager
def _locate_remote_skill(
    handle: ParsedHandle,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    default_repo: str | None = None,
) -> Generator[_RemoteDepLocation, None, None]:
    """Search for a remote skill across sources and repo candidates."""
    with _locate_remote_dep(
        handle,
        prepare_repo_for_skill,
        SkillNotFoundError,
        "Skill",
        resolver,
        source,
        default_repo,
    ) as loc:
        yield loc


def install_remote_skill(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig,
    skills_dir: Path,
    *,
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    install_name: str | None = None,
) -> Path:
    """Install a remote skill to a specific tool directory."""
    if handle.is_local:
        raise InvalidHandleError("install_remote_skill requires a remote handle")

    with _locate_remote_skill(handle, resolver, source) as loc:
        install_handle = (
            ParsedHandle(
                username=handle.username,
                repo=handle.repo,
                name=install_name,
            )
            if install_name
            else handle
        )
        if loc.is_legacy:
            warn_legacy_repo()
        return install_skill_from_repo(
            loc.repo_dir,
            handle.name,
            install_handle,
            skills_dir,
            tool,
            repo_root,
            overwrite,
            install_source=loc.source_config.name,
            skill_source=loc.source_path,
        )


def fetch_and_install(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig = DEFAULT_TOOL,
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    skills_dir: Path | None = None,
) -> Path:
    """Fetch and install a skill.

    Args:
        handle: Parsed handle (remote or local)
        repo_root: Repository root path (project installs) or None (global installs)
        tool: Tool configuration for path structure
        overwrite: Whether to overwrite existing

    Returns:
        Path to installed skill

    Raises:
        Various exceptions on failure
    """
    skills_dir = _resolve_skills_dir(skills_dir, repo_root, tool)

    if handle.is_local:
        # Local skill installation
        if handle.local_path is None:
            raise InvalidLocalPathError("Local handle missing path")

        source_path = handle.resolve_local_path(repo_root)
        resolved_handle = ParsedHandle(
            is_local=True,
            name=handle.name,
            local_path=source_path,
        )

        return install_local_skill(
            source_path, skills_dir, tool, overwrite, repo_root, resolved_handle
        )

    # Remote skill installation
    return install_remote_skill(
        handle,
        repo_root,
        tool,
        skills_dir,
        overwrite=overwrite,
        resolver=resolver,
        source=source,
    )


def fetch_and_install_to_tools(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    skills_dirs: dict[str, Path] | None = None,
    default_repo: str | None = None,
) -> tuple[dict[str, Path], InstallResult]:
    """Fetch skill once and install to multiple tools.

    This optimizes the common case of installing to multiple tools by
    downloading the repository only once.

    Args:
        handle: Parsed handle (remote or local)
        repo_root: Repository root path (project installs) or None (global installs)
        tools: List of tool configurations to install to
        overwrite: Whether to overwrite existing installations

    Returns:
        Tuple of (dict mapping tool name to installed path, InstallResult
        with lockfile-relevant metadata).

    Raises:
        Various exceptions on failure. On partial failure, already installed
        tools are rolled back (removed).
    """
    if not tools:
        raise AgrError("No tools provided for installation")

    if handle.is_local:
        # Local: no download needed, just iterate with rollback
        with _rollback_on_failure() as installed:
            for tool in tools:
                installed[tool.name] = fetch_and_install(
                    handle,
                    repo_root,
                    tool,
                    overwrite,
                    resolver,
                    source,
                    skills_dir=lookup_skills_dir(skills_dirs, tool),
                )
        return installed, InstallResult()

    # Remote: download once via _locate_remote_skill, then install the same
    # checked-out skill to every tool. The context manager keeps the temp
    # repo directory alive until all tools are done.
    install_result = InstallResult()
    with (
        _rollback_on_failure() as installed,
        _locate_remote_skill(handle, resolver, source, default_repo) as loc,
    ):
        for tool in tools:
            skills_dir = _resolve_skills_dir(
                lookup_skills_dir(skills_dirs, tool), repo_root, tool
            )
            path = install_skill_from_repo(
                loc.repo_dir,
                handle.name,
                handle,
                skills_dir,
                tool,
                repo_root,
                overwrite,
                install_source=loc.source_config.name,
                skill_source=loc.source_path,
            )
            installed[tool.name] = path
        # Warn after successful install so the user sees it once,
        # not on partial failure.
        if loc.is_legacy:
            warn_legacy_repo()

        # Compute content hash from the first installed path for the lockfile.
        first_path = next(iter(installed.values()), None)
        content_hash = compute_content_hash(first_path) if first_path else None

        install_result = InstallResult(
            commit=loc.commit,
            content_hash=content_hash,
            source_name=loc.source_config.name,
        )
    return installed, install_result


# ---------------------------------------------------------------------------
# Uninstall & query
# ---------------------------------------------------------------------------


def uninstall_skill(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig = DEFAULT_TOOL,
    source: str | None = None,
    skills_dir: Path | None = None,
) -> bool:
    """Uninstall a skill.

    Args:
        handle: Parsed handle identifying the skill
        repo_root: Repository root path (project installs) or None (global installs)
        tool: Tool configuration for path structure
        source: Source name for metadata matching (optional)
        skills_dir: Explicit skills directory override (optional)

    Returns:
        True if removed, False if not found
    """
    resolved_dir = _resolve_skills_dir(skills_dir, repo_root, tool)
    skill_path = _find_existing_skill_dir(handle, resolved_dir, tool, repo_root, source)

    if not skill_path:
        return False

    shutil.rmtree(skill_path)

    # Clean up empty parent directories for nested structures
    if tool.supports_nested:
        cleanup_empty_parents(skill_path.parent, resolved_dir)

    return True


def is_skill_installed(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig = DEFAULT_TOOL,
    source: str | None = None,
    skills_dir: Path | None = None,
) -> bool:
    """Check if a skill is installed.

    Args:
        handle: Parsed handle identifying the skill
        repo_root: Repository root path (project installs) or None (global installs)
        tool: Tool configuration for path structure
        source: Source name for metadata matching (optional)
        skills_dir: Explicit skills directory override (optional)

    Returns:
        True if installed
    """
    resolved_dir = _resolve_skills_dir(skills_dir, repo_root, tool)
    # _find_existing_skill_dir already validates via is_valid_skill_dir
    # on every code path, so a non-None result is always valid.
    return (
        _find_existing_skill_dir(handle, resolved_dir, tool, repo_root, source)
        is not None
    )


def filter_tools_needing_install(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    source_name: str | None,
    skills_dirs: dict[str, Path] | None = None,
) -> list[ToolConfig]:
    """Return tools where the given skill is not yet installed.

    Args:
        handle: Parsed handle identifying the skill
        repo_root: Repository root path (project installs) or None (global installs)
        tools: List of tool configurations to check
        source_name: Source name for remote skills
        skills_dirs: Optional mapping of tool name to explicit skills directory

    Returns:
        Subset of tools where the skill still needs to be installed
    """
    return [
        tool
        for tool in tools
        if not is_skill_installed(
            handle,
            repo_root,
            tool,
            source_name,
            skills_dir=lookup_skills_dir(skills_dirs, tool),
        )
    ]
