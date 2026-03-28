"""Skill validation and SKILL.md handling."""

import re
from pathlib import Path, PurePosixPath
from typing import TypeVar


_P = TypeVar("_P", Path, PurePosixPath)

# Marker file for skills
SKILL_MARKER = "SKILL.md"

# Regex for detecting a frontmatter ``name:`` line (with or without a value).
_FRONTMATTER_NAME_LINE_RE = re.compile(r"^\s*name\s*:")

# Regex for extracting the value from a frontmatter ``name: <value>`` line.
_FRONTMATTER_NAME_VALUE_RE = re.compile(r"^\s*name\s*:\s*(.+)\s*$")

# Regex for validating a skill name per the Agent Skills spec:
# 1-64 lowercase alphanumeric chars and hyphens,
# no leading/trailing/consecutive hyphens.
_VALID_SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Directories to exclude from skill discovery
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "vendor",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _shallowest(paths: list[_P]) -> _P:
    """Return the path with the fewest components (shallowest in the tree).

    When multiple paths share the same minimum depth, returns the first
    such path for deterministic behaviour (sorted input → sorted output).

    Precondition: *paths* must be non-empty.
    """
    return min(paths, key=lambda p: len(p.parts))


def _is_excluded_skill_path(parts: tuple[str, ...]) -> bool:
    """Check if a relative SKILL.md path should be excluded from discovery.

    Centralizes the two exclusion rules shared by both filesystem and
    git-listing discovery:

    1. Root-level SKILL.md (single component, e.g. just ``SKILL.md``)
       is a repo marker, not a skill directory.
    2. Any path component matching ``EXCLUDED_DIRS`` (.git, node_modules,
       __pycache__, etc.) disqualifies the entry.

    Args:
        parts: Components of the path *relative to the repo root*
            (e.g. ``("skills", "my-skill", "SKILL.md")``).

    Returns:
        True if the path should be excluded from skill discovery.
    """
    if len(parts) == 1:
        return True
    return any(part in EXCLUDED_DIRS for part in parts)


def _is_excluded_path(path: Path, repo_dir: Path) -> bool:
    """Check if a path should be excluded from skill discovery.

    Args:
        path: Path to check (absolute, within repo_dir)
        repo_dir: Root of the repository (to detect root-level SKILL.md)

    Returns:
        True if the path should be excluded
    """
    # Only check path components relative to repo_dir, so that
    # parent directories outside the repo (e.g. /home/user/build/project)
    # don't trigger false exclusions.
    rel = path.relative_to(repo_dir)
    return _is_excluded_skill_path(rel.parts)


def is_valid_skill_dir(path: Path) -> bool:
    """Check if a directory is a valid skill (contains SKILL.md).

    Args:
        path: Path to check

    Returns:
        True if the path is a directory containing SKILL.md
    """
    if not path.is_dir():
        return False
    return (path / SKILL_MARKER).exists()


def _find_skill_dirs(repo_dir: Path) -> list[Path]:
    """Find all valid skill directories in a repo.

    Recursively scans for SKILL.md files, excluding root-level markers
    and common non-skill directories (.git, node_modules, etc.).

    Args:
        repo_dir: Path to repository root

    Returns:
        List of skill directory paths (unsorted)
    """
    dirs: list[Path] = []
    for skill_md in repo_dir.rglob(SKILL_MARKER):
        if _is_excluded_path(skill_md, repo_dir):
            continue
        dirs.append(skill_md.parent)
    return dirs


def find_skill_in_repo(repo_dir: Path, skill_name: str) -> Path | None:
    """Find a skill directory in a downloaded repo.

    Searches recursively for any directory containing SKILL.md where the
    directory name matches the skill name. Excludes common non-skill
    directories (.git, node_modules, __pycache__, etc.).

    Results are sorted by path depth (shallowest first) for deterministic
    behavior when multiple matches exist.

    Args:
        repo_dir: Path to extracted repository
        skill_name: Name of the skill to find

    Returns:
        Path to skill directory if found, None otherwise
    """
    matches = [d for d in _find_skill_dirs(repo_dir) if d.name == skill_name]
    if not matches:
        return None

    return _shallowest(matches)


def _find_skill_dirs_in_listing(paths: list[str]) -> list[PurePosixPath]:
    """Return valid skill directories from a git file listing.

    Filters SKILL.md entries, excluding root-level markers and paths
    within excluded directories (.git, node_modules, etc.).

    Args:
        paths: List of file paths from git (posix-style).

    Returns:
        List of skill directory paths (parent of each valid SKILL.md).
    """
    results: list[PurePosixPath] = []
    for rel in paths:
        rel_path = PurePosixPath(rel)
        if rel_path.name != SKILL_MARKER:
            continue
        if _is_excluded_skill_path(rel_path.parts):
            continue
        results.append(rel_path.parent)
    return results


def find_skill_in_repo_listing(
    paths: list[str], skill_name: str
) -> PurePosixPath | None:
    """Find a skill directory from a git file listing.

    Args:
        paths: List of file paths from git (posix-style).
        skill_name: Name of the skill to find.

    Returns:
        Path to skill directory (posix-style, relative), or None if not found.
    """
    matches = [d for d in _find_skill_dirs_in_listing(paths) if d.name == skill_name]
    if not matches:
        return None
    return _shallowest(matches)


def find_skills_in_repo_listing(
    paths: list[str], skill_names: list[str]
) -> dict[str, PurePosixPath]:
    """Find multiple skill directories from a git file listing in a single pass.

    More efficient than calling ``find_skill_in_repo_listing`` in a loop,
    because the file listing is scanned only once.

    Args:
        paths: List of file paths from git (posix-style).
        skill_names: Names of the skills to find.

    Returns:
        Mapping of skill name to directory path for each found skill.
        Missing skills are omitted from the result.
    """
    name_set = set(skill_names)
    matches: dict[str, list[PurePosixPath]] = {}
    for d in _find_skill_dirs_in_listing(paths):
        if d.name in name_set:
            matches.setdefault(d.name, []).append(d)
    return {name: _shallowest(dirs) for name, dirs in matches.items()}


def discover_skills_in_repo_listing(paths: list[str]) -> list[str]:
    """Discover all skill names from a git file listing.

    Returns all unique skill names found. Results are sorted alphabetically.

    Args:
        paths: List of file paths from git (posix-style).

    Returns:
        Sorted list of unique skill names found in the listing.
    """
    return sorted({d.name for d in _find_skill_dirs_in_listing(paths)})


def discover_all_skill_dirs(repo_dir: Path) -> list[Path]:
    """Discover all skill directories in a repository (no dedupe).

    Args:
        repo_dir: Path to repository root

    Returns:
        List of skill directories, sorted by path for determinism
    """
    return sorted(_find_skill_dirs(repo_dir), key=lambda p: p.as_posix())


def parse_frontmatter(content: str) -> tuple[str, str] | None:
    """Parse YAML frontmatter from SKILL.md content.

    Args:
        content: Full file content.

    Returns:
        Tuple of (frontmatter_text, body) if valid ``---`` delimited
        frontmatter exists, None otherwise.
    """
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1], parts[2]


def get_skill_frontmatter_name(skill_dir: Path) -> str | None:
    """Extract the frontmatter name from SKILL.md if present."""
    skill_md = skill_dir / SKILL_MARKER
    if not skill_md.exists():
        return None

    parsed = parse_frontmatter(skill_md.read_text())
    if parsed is None:
        return None

    frontmatter, _ = parsed
    for line in frontmatter.splitlines():
        match = _FRONTMATTER_NAME_VALUE_RE.match(line)
        if match:
            return match.group(1).strip()
    return None


def update_skill_md_name(skill_dir: Path, new_name: str) -> None:
    """Update the name field in SKILL.md.

    Args:
        skill_dir: Path to skill directory containing SKILL.md
        new_name: New name to set in frontmatter
    """
    skill_md = skill_dir / SKILL_MARKER
    if not skill_md.exists():
        return

    content = skill_md.read_text()
    parsed = parse_frontmatter(content)

    if parsed is None:
        # No valid frontmatter — prepend one
        skill_md.write_text(f"---\nname: {new_name}\n---\n\n{content}")
        return

    frontmatter, body = parsed

    # Update or add name in frontmatter
    lines = frontmatter.strip().split("\n")
    new_lines = []
    name_found = False

    for line in lines:
        if _FRONTMATTER_NAME_LINE_RE.match(line):
            new_lines.append(f"name: {new_name}")
            name_found = True
        else:
            new_lines.append(line)

    if not name_found:
        new_lines.insert(0, f"name: {new_name}")

    new_frontmatter = "\n".join(new_lines)
    skill_md.write_text(f"---\n{new_frontmatter}\n---{body}")


def validate_skill_name(name: str) -> bool:
    """Validate a skill name per the Agent Skills specification.

    Valid names: 1-64 lowercase alphanumeric characters and hyphens,
    must not start/end with a hyphen or contain consecutive hyphens.

    Args:
        name: Skill name to validate

    Returns:
        True if valid
    """
    if not name or len(name) > 64:
        return False
    return bool(_VALID_SKILL_NAME_RE.match(name))


def create_skill_scaffold(name: str, base_dir: Path | None = None) -> Path:
    """Create a skill scaffold with SKILL.md.

    Args:
        name: Skill name
        base_dir: Directory to create skill in (defaults to cwd)

    Returns:
        Path to created skill directory

    Raises:
        ValueError: If name is invalid
        FileExistsError: If skill directory already exists
    """
    if not validate_skill_name(name):
        raise ValueError(
            f"Invalid skill name '{name}': "
            "must be 1-64 lowercase alphanumeric characters "
            "and hyphens, cannot start/end with a hyphen"
        )

    base = base_dir or Path.cwd()
    skill_dir = base / name

    if skill_dir.exists():
        raise FileExistsError(f"Directory '{name}' already exists")

    skill_dir.mkdir(parents=True)

    # Create SKILL.md with scaffold content
    # The description field is required by Cursor, Codex, and OpenCode
    # and recommended by Claude Code.
    skill_md = skill_dir / SKILL_MARKER
    skill_md.write_text(f"""---
name: {name}
description: TODO — describe what this skill does and when to use it
---

# {name}

## When to use

Describe when this skill should be used.

## Instructions

Provide detailed instructions here.
""")

    return skill_dir
