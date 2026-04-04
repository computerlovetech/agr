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
    _RemoteSkillLocation,
    _dep_not_found_message,
    _skill_dir_matches_handle,
)
from agr.exceptions import (
    AgrError,
    RalphNotFoundError,
    RepoNotFoundError,
)
from agr.git import (
    checkout_full,
    checkout_sparse_paths,
    downloaded_repo,
    get_head_commit_full,
    git_list_files,
)
from agr.handle import (
    INSTALLED_NAME_SEPARATOR,
    ParsedHandle,
    iter_repo_candidates,
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
    stamp_ralph_metadata,
)
from agr.ralph import (
    RALPH_MARKER,
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
    handle_ids = build_handle_ids(handle, repo_root, source)
    name_path = ralphs_dir / handle.name
    full_path = ralphs_dir / handle.to_installed_name()

    if is_valid_ralph_dir(name_path) and _skill_dir_matches_handle(
        name_path, handle_ids
    ):
        return name_path

    if is_valid_ralph_dir(full_path):
        return full_path

    return None


def _resolve_ralph_destination(
    handle: ParsedHandle,
    ralphs_dir: Path,
    repo_root: Path | None,
    source: str | None = None,
) -> Path:
    """Resolve the destination path for installing a ralph."""
    existing = _find_existing_ralph_dir(handle, ralphs_dir, repo_root, source)
    if existing:
        return existing

    name_path = ralphs_dir / handle.name
    if is_valid_ralph_dir(name_path):
        return ralphs_dir / handle.to_installed_name()

    return name_path


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
    unique_names = list(dict.fromkeys(ralph_names))
    if not unique_names:
        return {}

    try:
        paths = git_list_files(repo_dir)
        rel_paths = {
            name: Path(d)
            for name, d in find_ralphs_in_repo_listing(paths, unique_names).items()
        }

        if rel_paths:
            checkout_sparse_paths(repo_dir, list(rel_paths.values()))
            resolved = {
                name: repo_dir / rel_path for name, rel_path in rel_paths.items()
            }
            for path in resolved.values():
                if not path.exists():
                    raise AgrError("Failed to checkout ralph path.")
            return resolved

        return {}
    except AgrError:
        checkout_full(repo_dir)
        resolved_dict: dict[str, Path] = {}
        for name in unique_names:
            ralph_path = find_ralph_in_repo(repo_dir, name)
            if ralph_path is not None:
                resolved_dict[name] = ralph_path
        return resolved_dict


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

    # Self-install case
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
) -> Generator[_RemoteSkillLocation, None, None]:
    """Search for a remote ralph across sources and repo candidates.

    Reuses _RemoteSkillLocation since the fields are identical.
    """
    resolver = resolver or SourceResolver.default()
    owner = handle.username or ""

    for repo_name, is_legacy in iter_repo_candidates(handle.repo, default_repo):
        for source_config in resolver.ordered(source):
            try:
                with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                    ralph_source = prepare_repo_for_ralph(repo_dir, handle.name)
                    if ralph_source is None:
                        continue
                    try:
                        commit = get_head_commit_full(repo_dir)
                    except AgrError:
                        commit = None
                    yield _RemoteSkillLocation(
                        repo_dir=repo_dir,
                        skill_source=ralph_source,
                        source_config=source_config,
                        is_legacy=is_legacy,
                        commit=commit,
                    )
                    return
            except RepoNotFoundError:
                if source is not None:
                    raise
                continue

    raise RalphNotFoundError(
        f"Ralph '{handle.name}' not found in sources: "
        f"{', '.join(s.name for s in resolver.ordered(source))}"
    )


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
        raise ValueError("repo_root is required for ralph installation")

    ralphs_dir = get_ralphs_dir(repo_root)

    if handle.is_local:
        if handle.local_path is None:
            raise ValueError("Local handle missing path")
        source_path = handle.resolve_local_path(repo_root)
        resolved_handle = ParsedHandle(
            is_local=True, name=handle.name, local_path=source_path
        )
        path = install_local_ralph(
            source_path, ralphs_dir, overwrite, repo_root, resolved_handle
        )
        return path, InstallResult()

    with _locate_remote_ralph(handle, resolver, source, default_repo) as loc:
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
            ralph_source=loc.skill_source,
        )
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
