"""Ralph installation, uninstallation, and query operations.

Handles local and remote ralph installation, repo preparation,
destination resolution, and ralph lifecycle management.
"""

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator

from agr._install_common import (
    InstallResult,
    RALPHS_CONFIG_DIR,
    RALPHS_SUBDIR,
    _RemoteDepLocation,
    _dep_not_found_message,
    _find_existing_flat_dir,
    _locate_remote_dep,
    _resolve_flat_destination,
    _rollback_on_failure,
    list_remote_repo_deps,
    prepare_repo_for_deps,
)
from agr.exceptions import (
    AgrError,
    InvalidLocalPathError,
    RalphNotFoundError,
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
    compute_content_hash,
    read_skill_metadata,
    stamp_ralph_metadata,
)
from agr.ralph import (
    RALPH_MARKER,
    discover_ralphs_in_repo_listing,
    find_ralph_in_repo,
    find_ralphs_in_repo_listing,
    is_valid_ralph_dir,
)
from agr.source import SourceResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Directory helper
# ---------------------------------------------------------------------------


def get_ralphs_dir(repo_root: Path) -> Path:
    """Return the project-level ralphs directory."""
    return repo_root / RALPHS_CONFIG_DIR / RALPHS_SUBDIR


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _find_existing_ralph_dir(
    handle: ParsedHandle,
    ralphs_dir: Path,
    repo_root: Path | None,
    source: str | None = None,
) -> Path | None:
    """Find an existing installed ralph directory for this handle."""
    return _find_existing_flat_dir(handle, ralphs_dir, repo_root, source, is_valid_ralph_dir)


def _resolve_ralph_destination(
    handle: ParsedHandle,
    ralphs_dir: Path,
    repo_root: Path | None,
    source: str | None = None,
) -> Path:
    """Resolve the destination path for installing a ralph."""
    return _resolve_flat_destination(handle, ralphs_dir, repo_root, source, is_valid_ralph_dir)


# ---------------------------------------------------------------------------
# Copy & error messages
# ---------------------------------------------------------------------------


def _copy_ralph_to_destination(
    source: Path,
    dest: Path,
    handle: ParsedHandle,
    overwrite: bool,
    repo_root: Path | None,
    install_source: str | None = None,
) -> Path:
    """Copy ralph source to destination with overwrite handling."""
    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Ralph already exists at {dest}. Use --overwrite to replace."
        )

    if dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    stamp_ralph_metadata(dest, handle, repo_root, dest.name, install_source)

    return dest


def ralph_not_found_message(name: str) -> str:
    """Build a user-friendly message for a missing ralph in a repository."""
    return _dep_not_found_message("Ralph", name, RALPH_MARKER, "ralphs")


# ---------------------------------------------------------------------------
# Repo preparation
# ---------------------------------------------------------------------------


def prepare_repo_for_ralph(repo_dir: Path, ralph_name: str) -> Path | None:
    """Prepare a repo so that only the ralph path is checked out."""
    result = prepare_repo_for_ralphs(repo_dir, [ralph_name])
    return result.get(ralph_name)


def prepare_repo_for_ralphs(repo_dir: Path, ralph_names: list[str]) -> dict[str, Path]:
    """Prepare a repo so multiple ralph paths are checked out."""
    return prepare_repo_for_deps(
        repo_dir, ralph_names, find_ralphs_in_repo_listing, find_ralph_in_repo, "ralph"
    )


def list_remote_repo_ralphs(
    owner: str,
    repo_name: str,
    resolver: SourceResolver | None = None,
    source: str | None = None,
) -> list[str]:
    """List all ralph names in a remote repository.

    Clones the repo and scans for RALPH.md files. Used to provide
    helpful suggestions when a handle fails to resolve.

    Returns:
        Sorted list of ralph names found, or empty list on any error.
    """
    return list_remote_repo_deps(
        owner, repo_name, discover_ralphs_in_repo_listing, resolver, source
    )


# ---------------------------------------------------------------------------
# Install orchestration
# ---------------------------------------------------------------------------


def install_ralph_from_repo(
    repo_dir: Path,
    ralph_name: str,
    handle: ParsedHandle,
    ralphs_dir: Path,
    repo_root: Path | None,
    overwrite: bool = False,
    install_source: str | None = None,
    ralph_source: Path | None = None,
) -> Path:
    """Install a ralph from a downloaded repository."""
    if ralph_source is None:
        ralph_source = find_ralph_in_repo(repo_dir, ralph_name)
    if ralph_source is None:
        raise RalphNotFoundError(ralph_not_found_message(ralph_name))

    ralph_dest = _resolve_ralph_destination(
        handle, ralphs_dir, repo_root, install_source
    )

    return _copy_ralph_to_destination(
        ralph_source, ralph_dest, handle, overwrite, repo_root, install_source
    )


def _find_local_ralph_name_conflicts(
    handle: ParsedHandle,
    ralphs_dir: Path,
    repo_root: Path | None,
    default_dest: Path,
) -> tuple[list[Path], bool]:
    """Find conflicting local installs with the same ralph name.

    Returns a tuple of (conflict_paths, has_unknown_metadata).
    """
    handle_id = build_handle_id(handle, repo_root)
    conflicts: list[Path] = []
    has_unknown = False

    candidates = [ralphs_dir / handle.name, ralphs_dir / handle.to_installed_name()]

    for path in candidates:
        if path.resolve() == default_dest.resolve():
            continue
        if not is_valid_ralph_dir(path):
            continue
        meta = read_skill_metadata(path)
        if meta:
            if meta.get(METADATA_KEY_TYPE) != METADATA_TYPE_LOCAL:
                continue
            if meta.get(METADATA_KEY_ID) == handle_id:
                continue
            conflicts.append(path)
            continue
        has_unknown = True
        conflicts.append(path)

    return conflicts, has_unknown


def install_local_ralph(
    source_path: Path,
    ralphs_dir: Path,
    overwrite: bool = False,
    repo_root: Path | None = None,
    handle: ParsedHandle | None = None,
) -> Path:
    """Install a local ralph."""
    if not is_valid_ralph_dir(source_path):
        raise RalphNotFoundError(
            f"'{source_path}' is not a valid ralph (missing {RALPH_MARKER})"
        )

    if INSTALLED_NAME_SEPARATOR in source_path.name:
        raise AgrError(
            f"Ralph name '{source_path.name}' contains "
            f"reserved sequence '{INSTALLED_NAME_SEPARATOR}'"
        )

    handle = handle or ParsedHandle(
        is_local=True, name=source_path.name, local_path=source_path
    )
    if repo_root is None:
        repo_root = Path.cwd()

    # Self-install case: ralphs always install by name (no tool-specific
    # path nesting), so handle.name is the correct destination, unlike
    # skills which use handle.to_skill_path(tool).
    default_dest = ralphs_dir / handle.name
    if source_path.resolve() == default_dest.resolve() and is_valid_ralph_dir(
        default_dest
    ):
        if read_skill_metadata(default_dest) is None:
            stamp_ralph_metadata(default_dest, handle, repo_root, default_dest.name)
        return default_dest

    conflicts, has_unknown = _find_local_ralph_name_conflicts(
        handle, ralphs_dir, repo_root, default_dest
    )
    if conflicts:
        locations = ", ".join(str(path) for path in conflicts)
        hint = ""
        if has_unknown:
            hint = (
                " If this is a remote ralph, run "
                "`agr sync` or reinstall it to "
                "add metadata."
            )
        raise AgrError(
            f"Local ralph name '{handle.name}' is already installed at {locations}. "
            "agr allows only one local ralph with a given name. "
            "Rename the ralph or remove the existing one."
            f"{hint}"
        )

    ralph_dest = _resolve_ralph_destination(handle, ralphs_dir, repo_root)

    return _copy_ralph_to_destination(
        source_path, ralph_dest, handle, overwrite, repo_root
    )


@contextmanager
def _locate_remote_ralph(
    handle: ParsedHandle,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    default_repo: str | None = None,
) -> Generator[_RemoteDepLocation, None, None]:
    """Search for a remote ralph across sources and repo candidates."""
    with _locate_remote_dep(
        handle,
        prepare_repo_for_ralph,
        RalphNotFoundError,
        "Ralph",
        resolver,
        source,
        default_repo,
    ) as loc:
        yield loc


def fetch_and_install_ralph(
    handle: ParsedHandle,
    repo_root: Path | None,
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    default_repo: str | None = None,
) -> tuple[Path, InstallResult]:
    """Fetch and install a ralph to the project-level ralphs directory.

    Returns:
        Tuple of (installed path, InstallResult with lockfile metadata).
    """
    if repo_root is None:
        raise AgrError("repo_root is required for ralph installation")

    ralphs_dir = get_ralphs_dir(repo_root)

    if handle.is_local:
        if handle.local_path is None:
            raise InvalidLocalPathError("Local handle missing path")
        source_path = handle.resolve_local_path(repo_root)
        resolved_handle = ParsedHandle(
            is_local=True, name=handle.name, local_path=source_path
        )
        path = install_local_ralph(
            source_path, ralphs_dir, overwrite, repo_root, resolved_handle
        )
        return path, InstallResult()

    install_result = InstallResult()
    with (
        _rollback_on_failure() as installed,
        _locate_remote_ralph(handle, resolver, source, default_repo) as loc,
    ):
        if loc.is_legacy:
            warn_legacy_repo()
        path = install_ralph_from_repo(
            loc.repo_dir,
            handle.name,
            handle,
            ralphs_dir,
            repo_root,
            overwrite,
            install_source=loc.source_config.name,
            ralph_source=loc.source_path,
        )
        installed["ralph"] = path
        content_hash = compute_content_hash(path)
        install_result = InstallResult(
            commit=loc.commit,
            content_hash=content_hash,
            source_name=loc.source_config.name,
        )
    return path, install_result


# ---------------------------------------------------------------------------
# Uninstall & query
# ---------------------------------------------------------------------------


def uninstall_ralph(
    handle: ParsedHandle,
    repo_root: Path | None,
    source: str | None = None,
) -> bool:
    """Uninstall a ralph from the project-level ralphs directory."""
    if repo_root is None:
        return False
    ralphs_dir = get_ralphs_dir(repo_root)
    ralph_path = _find_existing_ralph_dir(handle, ralphs_dir, repo_root, source)
    if not ralph_path:
        return False
    shutil.rmtree(ralph_path)
    return True


def is_ralph_installed(
    handle: ParsedHandle,
    repo_root: Path | None,
    source: str | None = None,
) -> bool:
    """Check if a ralph is installed."""
    if repo_root is None:
        return False
    ralphs_dir = get_ralphs_dir(repo_root)
    return _find_existing_ralph_dir(handle, ralphs_dir, repo_root, source) is not None
