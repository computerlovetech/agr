"""Shared infrastructure for skill and ralph installation.

Data classes, rollback helpers, and utility functions used by both
skill_installer and ralph_installer.
"""

import logging
import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from agr.exceptions import AgrError, RepoNotFoundError
from agr.git import downloaded_repo, get_head_commit_full
from agr.handle import ParsedHandle, iter_repo_candidates
from agr.metadata import (
    METADATA_KEY_ID,
    read_skill_metadata,
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
    meta = read_skill_metadata(dep_dir)
    if not meta:
        return False
    return meta.get(METADATA_KEY_ID) in handle_ids


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
        ValueError: If both skills_dir and repo_root are None.
    """
    if skills_dir is not None:
        return skills_dir
    if repo_root is None:
        raise ValueError("repo_root is required when skills_dir is not provided")
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
