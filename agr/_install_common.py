"""Shared infrastructure for skill and ralph installation.

Data classes, rollback helpers, and utility functions used by both
skill_installer and ralph_installer.
"""

import logging
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Generator
from typing import NamedTuple

from agr.metadata import (
    METADATA_KEY_ID,
    read_skill_metadata,
)
from agr.source import SourceConfig
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


class _RemoteSkillLocation(NamedTuple):
    """Result of locating a remote skill/ralph across sources."""

    repo_dir: Path
    skill_source: Path
    source_config: SourceConfig
    is_legacy: bool
    commit: str | None = None


def _skill_dir_matches_handle(skill_dir: Path, handle_ids: list[str]) -> bool:
    """Check whether a skill directory matches a handle via metadata."""
    meta = read_skill_metadata(skill_dir)
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


def _cleanup_empty_parents(path: Path, stop_at: Path) -> None:
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
