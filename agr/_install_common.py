"""Shared infrastructure for skill and ralph installation.

Data classes, rollback helpers, and utility functions used by both
skill_installer and ralph_installer.
"""

import logging
import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from agr.exceptions import AgrError, RepoNotFoundError
from agr.git import (
    checkout_full,
    checkout_sparse_paths,
    downloaded_repo,
    get_head_commit_full,
    git_list_files,
)
from agr.handle import ParsedHandle, iter_repo_candidates
from agr.metadata import (
    METADATA_KEY_ID,
    build_handle_ids,
    read_resource_metadata,
)
from agr.source import SourceConfig, SourceResolver
from agr.tool import ToolConfig

# Ralph installation directory constants
RALPHS_CONFIG_DIR = ".agents"
RALPHS_SUBDIR = "ralphs"

logger = logging.getLogger(__name__)


@dataclass
class InstallResult:
    """Lockfile-relevant metadata captured during skill installation."""

    commit: str | None = None
    content_hash: str | None = None
    source_name: str | None = None


class _RemoteDepLocation(NamedTuple):
    """Result of locating a remote dependency across sources."""

    repo_dir: Path
    source_path: Path
    source_config: SourceConfig
    is_legacy: bool
    commit: str | None = None


def _dir_matches_handle(dep_dir: Path, handle_ids: list[str]) -> bool:
    """Check whether an installed dependency directory matches a handle via metadata."""
    meta = read_resource_metadata(dep_dir)
    if not meta:
        return False
    return meta.get(METADATA_KEY_ID) in handle_ids


def _find_existing_flat_dir(
    handle: ParsedHandle,
    parent_dir: Path,
    repo_root: Path | None,
    source: str | None,
    is_valid_dir: Callable[[Path], bool],
) -> Path | None:
    """Find an existing installed dependency directory (flat layout).

    Checks two candidate paths in priority order:
    1. Plain name (e.g. ``dep/``) — preferred, requires metadata ID match
    2. Full name (e.g. ``user--repo--dep/``) — accepted without metadata
       (covers both current installs and legacy installs without metadata)

    Args:
        handle: Parsed handle identifying the dependency.
        parent_dir: Directory containing installed dependencies.
        repo_root: Repository root for metadata resolution.
        source: Source name for metadata matching.
        is_valid_dir: Callable to check if a directory is a valid dependency.

    Returns:
        Path to existing directory, or None if not found.
    """
    handle_ids = build_handle_ids(handle, repo_root, source)
    name_path = parent_dir / handle.name
    full_path = parent_dir / handle.to_installed_name()

    if is_valid_dir(name_path) and _dir_matches_handle(name_path, handle_ids):
        return name_path

    if is_valid_dir(full_path):
        return full_path

    return None


def _resolve_flat_destination(
    handle: ParsedHandle,
    parent_dir: Path,
    repo_root: Path | None,
    source: str | None,
    is_valid_dir: Callable[[Path], bool],
) -> Path:
    """Resolve the destination path for installing a dependency (flat layout).

    Resolution order:
    1. If the dependency is already installed (any name form), reuse that path.
    2. If the plain name (e.g. ``dep/``) is free, use it.
    3. If the plain name is taken by a *different* dependency, fall back to the
       fully qualified name (e.g. ``user--repo--dep/``).

    Args:
        handle: Parsed handle identifying the dependency.
        parent_dir: Directory containing installed dependencies.
        repo_root: Repository root for metadata resolution.
        source: Source name for metadata matching.
        is_valid_dir: Callable to check if a directory is a valid dependency.

    Returns:
        Resolved destination path.
    """
    existing = _find_existing_flat_dir(handle, parent_dir, repo_root, source, is_valid_dir)
    if existing:
        return existing

    name_path = parent_dir / handle.name
    if is_valid_dir(name_path):
        return parent_dir / handle.to_installed_name()

    return name_path


def _dep_not_found_message(kind: str, name: str, marker: str, subdir: str) -> str:
    """Build a user-friendly message for a missing dependency in a repository."""
    return (
        f"{kind} '{name}' not found in repository.\n"
        f"No directory named '{name}' containing {marker} was found.\n"
        f"Hint: Create a {kind.lower()} at '{subdir}/{name}/{marker}' or '{name}/{marker}'"
    )


def _resolve_skills_dir(
    skills_dir: Path | None, repo_root: Path | None, tool: ToolConfig
) -> Path:
    """Resolve skills directory from explicit path or repo_root + tool config.

    Args:
        skills_dir: Explicit skills directory, if provided.
        repo_root: Repository root path (project installs) or None (global installs).
        tool: Tool configuration for deriving the skills directory.

    Returns:
        Resolved skills directory path.

    Raises:
        AgrError: If both skills_dir and repo_root are None.
    """
    if skills_dir is not None:
        return skills_dir
    if repo_root is None:
        raise AgrError("repo_root is required when skills_dir is not provided")
    return tool.get_skills_dir(repo_root)


def _rollback_installed(installed: dict[str, Path]) -> None:
    """Remove installed skill dirs to roll back partial installs."""
    for tool_name, rollback_path in installed.items():
        try:
            shutil.rmtree(rollback_path)
        except OSError as e:
            logger.warning(f"Failed to rollback {tool_name} at {rollback_path}: {e}")


@contextmanager
def _rollback_on_failure() -> Generator[dict[str, Path], None, None]:
    """Track installed paths and roll back all on failure.

    Yields a dict that callers populate with {tool_name: path} entries.
    If an exception propagates out, all recorded installs are removed.
    """
    installed: dict[str, Path] = {}
    try:
        yield installed
    except Exception:
        _rollback_installed(installed)
        raise


@contextmanager
def _locate_remote_dep(
    handle: ParsedHandle,
    prepare_fn: Callable[[Path, str], Path | None],
    not_found_error_cls: type[Exception],
    dep_kind: str,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    default_repo: str | None = None,
) -> Generator[_RemoteDepLocation, None, None]:
    """Search for a remote dependency across sources and repo candidates.

    Downloads the repository and prepares the dependency, keeping the temp
    directory alive while the caller processes the result.

    Args:
        handle: Parsed handle identifying the dependency.
        prepare_fn: Callable(repo_dir, name) -> Path | None to locate the
            dependency inside a checked-out repo.
        not_found_error_cls: Exception class to raise when not found.
        dep_kind: Human-readable label for error messages (e.g. "Skill").
        resolver: Source resolver for finding the repo.
        source: Explicit source name.
        default_repo: Default repo name fallback.

    Yields:
        _RemoteDepLocation with repo_dir, source_path, source_config, is_legacy.
    """
    resolver = resolver or SourceResolver.default()
    owner = handle.username or ""

    for repo_name, is_legacy in iter_repo_candidates(handle.repo, default_repo):
        for source_config in resolver.ordered(source):
            try:
                with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                    dep_source = prepare_fn(repo_dir, handle.name)
                    if dep_source is None:
                        continue
                    try:
                        commit = get_head_commit_full(repo_dir)
                    except AgrError:
                        commit = None
                    yield _RemoteDepLocation(
                        repo_dir=repo_dir,
                        source_path=dep_source,
                        source_config=source_config,
                        is_legacy=is_legacy,
                        commit=commit,
                    )
                    return
            except RepoNotFoundError:
                if source is not None:
                    raise
                continue

    raise not_found_error_cls(
        f"{dep_kind} '{handle.name}' not found in sources: "
        f"{', '.join(s.name for s in resolver.ordered(source))}"
    )


def prepare_repo_for_deps(
    repo_dir: Path,
    dep_names: list[str],
    find_in_listing: Callable[[list[str], list[str]], dict[str, PurePosixPath]],
    find_in_repo: Callable[[Path, str], Path | None],
    dep_kind: str,
) -> dict[str, Path]:
    """Prepare a repo so multiple dependency paths are checked out.

    Generic implementation shared by skill and ralph installers.

    Args:
        repo_dir: Path to the downloaded repository.
        dep_names: Names of dependencies to locate.
        find_in_listing: Callable(file_paths, names) -> {name: rel_dir}.
        find_in_repo: Callable(repo_dir, name) -> Path | None (filesystem fallback).
        dep_kind: Human-readable label for error messages (e.g. "skill").

    Returns:
        Mapping of dependency name to resolved path for those found.
    """
    unique_names = list(dict.fromkeys(dep_names))
    if not unique_names:
        return {}

    try:
        paths = git_list_files(repo_dir)
        rel_paths = {
            name: Path(d)
            for name, d in find_in_listing(paths, unique_names).items()
        }

        if rel_paths:
            checkout_sparse_paths(repo_dir, list(rel_paths.values()))
            resolved = {
                name: repo_dir / rel_path for name, rel_path in rel_paths.items()
            }
            for path in resolved.values():
                if not path.exists():
                    raise AgrError(f"Failed to checkout {dep_kind} path.")
            return resolved

        return {}
    except AgrError:
        checkout_full(repo_dir)
        resolved_dict: dict[str, Path] = {}
        for name in unique_names:
            dep_path = find_in_repo(repo_dir, name)
            if dep_path is not None:
                resolved_dict[name] = dep_path
        return resolved_dict


def list_remote_repo_deps(
    owner: str,
    repo_name: str,
    discover_in_listing: Callable[[list[str]], list[str]],
    resolver: SourceResolver | None = None,
    source: str | None = None,
) -> list[str]:
    """List all dependency names of a given kind in a remote repository.

    Generic implementation shared by skill and ralph installers.

    Args:
        owner: Repository owner/username.
        repo_name: Repository name.
        discover_in_listing: Callable(file_paths) -> sorted list of names.
        resolver: Source resolver for finding the repo.
        source: Explicit source name.

    Returns:
        Sorted list of names found, or empty list on any error.
    """
    resolver = resolver or SourceResolver.default()
    for source_config in resolver.ordered(source):
        try:
            with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                paths = git_list_files(repo_dir)
                return discover_in_listing(paths)
        except AgrError:
            continue
    return []


def cleanup_empty_parents(path: Path, stop_at: Path) -> None:
    """Remove empty parent directories up to stop_at.

    Args:
        path: Starting path to clean
        stop_at: Directory to stop at (not removed)
    """
    # Resolve symlinks to ensure proper path comparison
    path = path.resolve()
    stop_at = stop_at.resolve()
    current = path

    while current != stop_at and current.exists():
        # Safety: ensure we're still within stop_at
        if not current.is_relative_to(stop_at):
            break

        if current.is_dir() and not any(current.iterdir()):
            try:
                current.rmdir()
            except OSError:
                break  # Permission error or other issue
            current = current.parent
        else:
            break
