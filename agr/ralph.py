"""Ralph validation and RALPH.md handling.

Thin wrappers around the generic resource-discovery functions in
:mod:`agr.skill`, parameterised with ``RALPH_MARKER``.
"""

from pathlib import Path, PurePosixPath

from agr.skill import (
    _is_excluded_skill_path,
    discover_resources_in_repo_listing,
    find_resource_in_repo,
    find_resource_in_repo_listing,
    find_resources_in_repo_listing,
    is_valid_resource_dir,
)


# Marker file for ralphs
RALPH_MARKER = "RALPH.md"

# Reuse skill exclusion logic — same rules apply to ralphs.
_is_excluded_marker_path = _is_excluded_skill_path


def is_valid_ralph_dir(path: Path) -> bool:
    """Check if a directory is a valid ralph (contains RALPH.md)."""
    return is_valid_resource_dir(path, RALPH_MARKER)


def find_ralph_in_repo(repo_dir: Path, ralph_name: str) -> Path | None:
    """Find a ralph directory in a downloaded repo."""
    return find_resource_in_repo(repo_dir, ralph_name, RALPH_MARKER)


def find_ralph_in_repo_listing(
    paths: list[str], ralph_name: str
) -> PurePosixPath | None:
    """Find a ralph directory from a git file listing."""
    return find_resource_in_repo_listing(paths, ralph_name, RALPH_MARKER)


def find_ralphs_in_repo_listing(
    paths: list[str], ralph_names: list[str]
) -> dict[str, PurePosixPath]:
    """Find multiple ralph directories from a git file listing in a single pass."""
    return find_resources_in_repo_listing(paths, ralph_names, RALPH_MARKER)


def discover_ralphs_in_repo_listing(paths: list[str]) -> list[str]:
    """Discover all ralph names from a git file listing."""
    return discover_resources_in_repo_listing(paths, RALPH_MARKER)
