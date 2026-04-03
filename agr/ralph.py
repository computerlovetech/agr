"""Ralph validation and RALPH.md handling."""

from pathlib import Path, PurePosixPath

from agr.skill import EXCLUDED_DIRS, _shallowest


# Marker file for ralphs
RALPH_MARKER = "RALPH.md"


def _is_excluded_ralph_path(parts: tuple[str, ...]) -> bool:
    """Check if a relative RALPH.md path should be excluded from discovery.

    Same rules as skill discovery:
    1. Root-level RALPH.md is a repo marker, not a ralph directory.
    2. Any path component matching EXCLUDED_DIRS disqualifies the entry.
    """
    if len(parts) == 1:
        return True
    return any(part in EXCLUDED_DIRS for part in parts)


def _is_excluded_path(path: Path, repo_dir: Path) -> bool:
    """Check if a path should be excluded from ralph discovery."""
    rel = path.relative_to(repo_dir)
    return _is_excluded_ralph_path(rel.parts)


def is_valid_ralph_dir(path: Path) -> bool:
    """Check if a directory is a valid ralph (contains RALPH.md)."""
    if not path.is_dir():
        return False
    return (path / RALPH_MARKER).exists()


def _find_ralph_dirs(repo_dir: Path) -> list[Path]:
    """Find all valid ralph directories in a repo."""
    dirs: list[Path] = []
    for ralph_md in repo_dir.rglob(RALPH_MARKER):
        if _is_excluded_path(ralph_md, repo_dir):
            continue
        dirs.append(ralph_md.parent)
    return dirs


def find_ralph_in_repo(repo_dir: Path, ralph_name: str) -> Path | None:
    """Find a ralph directory in a downloaded repo.

    Searches recursively for any directory containing RALPH.md where the
    directory name matches the ralph name.
    """
    matches = [d for d in _find_ralph_dirs(repo_dir) if d.name == ralph_name]
    if not matches:
        return None
    return _shallowest(matches)


def _find_ralph_dirs_in_listing(paths: list[str]) -> list[PurePosixPath]:
    """Return valid ralph directories from a git file listing."""
    results: list[PurePosixPath] = []
    for rel in paths:
        rel_path = PurePosixPath(rel)
        if rel_path.name != RALPH_MARKER:
            continue
        if _is_excluded_ralph_path(rel_path.parts):
            continue
        results.append(rel_path.parent)
    return results


def find_ralph_in_repo_listing(
    paths: list[str], ralph_name: str
) -> PurePosixPath | None:
    """Find a ralph directory from a git file listing."""
    matches = [d for d in _find_ralph_dirs_in_listing(paths) if d.name == ralph_name]
    if not matches:
        return None
    return _shallowest(matches)


def find_ralphs_in_repo_listing(
    paths: list[str], ralph_names: list[str]
) -> dict[str, PurePosixPath]:
    """Find multiple ralph directories from a git file listing in a single pass."""
    name_set = set(ralph_names)
    matches: dict[str, list[PurePosixPath]] = {}
    for d in _find_ralph_dirs_in_listing(paths):
        if d.name in name_set:
            matches.setdefault(d.name, []).append(d)
    return {name: _shallowest(dirs) for name, dirs in matches.items()}


def discover_ralphs_in_repo_listing(paths: list[str]) -> list[str]:
    """Discover all ralph names from a git file listing.

    Returns all unique ralph names found, sorted alphabetically.
    """
    return sorted({d.name for d in _find_ralph_dirs_in_listing(paths)})
