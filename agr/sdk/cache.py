"""Cache management for downloaded skills.

Cache structure:
    ~/.cache/agr/skills/
    └── github/
        └── {owner}/
            └── {repo}/
                └── {skill_name}/
                    └── {revision}/
                        ├── SKILL.md
                        └── ...
"""

import fnmatch
import os
import re
import shutil
import tempfile
from typing import Any, Generator, TextIO, cast
from pathlib import Path

from agr.exceptions import CacheError

_LOCKS_USE_MSVCRT = os.name == "nt"
_msvcrt = None
_fcntl = None

if _LOCKS_USE_MSVCRT:
    import msvcrt as _msvcrt
else:
    import fcntl as _fcntl


def _acquire_file_lock(lock_fd: TextIO) -> None:
    """Acquire an exclusive lock for a lock file descriptor."""
    if _LOCKS_USE_MSVCRT:
        if _msvcrt is None:
            raise CacheError("Windows lock backend not available")
        msvcrt = cast(Any, _msvcrt)
        lock_fd.seek(0)
        lock_fd.write("0")
        lock_fd.flush()
        lock_fd.seek(0)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
        return

    if _fcntl is None:
        raise CacheError("POSIX lock backend not available")
    _fcntl.flock(lock_fd.fileno(), _fcntl.LOCK_EX)


def _release_file_lock(lock_fd: TextIO) -> None:
    """Release a previously acquired lock file descriptor."""
    if _LOCKS_USE_MSVCRT:
        if _msvcrt is None:
            return
        msvcrt = cast(Any, _msvcrt)
        lock_fd.seek(0)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
        return

    if _fcntl is None:
        return
    _fcntl.flock(lock_fd.fileno(), _fcntl.LOCK_UN)


def _sanitize_path_component(component: str, name: str) -> str:
    """Validate and sanitize a path component.

    Args:
        component: The path component to sanitize
        name: Name of the component (for error messages)

    Returns:
        The sanitized component

    Raises:
        ValueError: If the component is invalid
    """
    if not component:
        raise ValueError(f"{name} cannot be empty")

    if "\x00" in component:
        raise ValueError(f"{name} cannot contain null bytes")

    if ".." in component:
        raise ValueError(f"{name} cannot contain '..'")

    if "/" in component or "\\" in component:
        raise ValueError(f"{name} cannot contain path separators")

    # Allow only alphanumeric, hyphens, underscores, and dots
    if not re.match(r"^[a-zA-Z0-9._-]+$", component):
        raise ValueError(
            f"{name} contains invalid characters: must be alphanumeric, "
            "hyphens, underscores, or dots"
        )

    return component


def get_cache_dir() -> Path:
    """Get the base cache directory.

    Returns:
        Path to ~/.cache/agr
    """
    return Path.home() / ".cache" / "agr"


def get_skill_cache_path(owner: str, repo: str, skill: str, revision: str) -> Path:
    """Get the cache path for a specific skill revision.

    Args:
        owner: GitHub owner/username
        repo: Repository name
        skill: Skill name
        revision: Git revision (commit hash)

    Returns:
        Path to the cached skill directory

    Raises:
        ValueError: If any component contains invalid characters
    """
    # Sanitize all path components to prevent path traversal attacks
    owner = _sanitize_path_component(owner, "owner")
    repo = _sanitize_path_component(repo, "repo")
    skill = _sanitize_path_component(skill, "skill")
    revision = _sanitize_path_component(revision, "revision")

    return get_cache_dir() / "skills" / "github" / owner / repo / skill / revision


def is_cached(owner: str, repo: str, skill: str, revision: str) -> bool:
    """Check if a skill revision is cached.

    Args:
        owner: GitHub owner/username
        repo: Repository name
        skill: Skill name
        revision: Git revision (commit hash)

    Returns:
        True if the skill is cached
    """
    cache_path = get_skill_cache_path(owner, repo, skill, revision)
    return cache_path.exists() and (cache_path / "SKILL.md").exists()


def cache_skill(
    source_path: Path, owner: str, repo: str, skill: str, revision: str
) -> Path:
    """Cache a skill directory atomically with file locking.

    Uses double-check locking pattern:
    1. Quick check if already cached (no lock needed)
    2. Acquire exclusive lock
    3. Double-check after lock (another process may have cached)
    4. Atomic write with temp dir + rename
    5. Clean up lock file

    Args:
        source_path: Path to skill directory to cache
        owner: GitHub owner/username
        repo: Repository name
        skill: Skill name
        revision: Git revision (commit hash)

    Returns:
        Path to the cached skill directory

    Raises:
        CacheError: If caching fails
    """
    cache_path = get_skill_cache_path(owner, repo, skill, revision)

    try:
        # Fast path: already cached, no lock needed
        if cache_path.exists():
            return cache_path

        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Use file lock to prevent race conditions
        lock_file = cache_path.parent / f".{revision}.lock"
        lock_fd = None

        try:
            lock_fd = open(lock_file, "w")  # noqa: SIM115
            _acquire_file_lock(lock_fd)

            # Double-check after acquiring lock (another process may have cached)
            if cache_path.exists():
                return cache_path

            # Use temp dir in same parent for atomic rename
            with tempfile.TemporaryDirectory(dir=cache_path.parent) as tmp_dir:
                tmp_path = Path(tmp_dir) / "skill"
                shutil.copytree(source_path, tmp_path)

                # Atomic rename
                try:
                    tmp_path.rename(cache_path)
                except OSError:
                    # Fall back to copy if rename fails (cross-device)
                    if cache_path.exists():
                        shutil.rmtree(cache_path)
                    shutil.copytree(tmp_path, cache_path)
        finally:
            if lock_fd is not None:
                _release_file_lock(lock_fd)
                lock_fd.close()
                # Clean up lock file (best effort)
                try:
                    lock_file.unlink()
                except OSError:
                    pass  # Another process may have deleted or be using it

    except OSError as e:
        raise CacheError(f"Failed to cache skill: {e}") from e

    return cache_path


def _iter_skill_cache_dirs(
    skills_cache: Path,
) -> Generator[tuple[Path, str], None, None]:
    """Yield ``(skill_dir, skill_id)`` for every cached skill.

    Walks the cache tree: ``<skills_cache>/<source>/<owner>/<repo>/<skill>``.
    ``skill_id`` is formatted as ``owner/repo/skill``.
    """
    for source_dir in skills_cache.iterdir():
        if not source_dir.is_dir():
            continue
        for owner_dir in source_dir.iterdir():
            if not owner_dir.is_dir():
                continue
            for repo_dir in owner_dir.iterdir():
                if not repo_dir.is_dir():
                    continue
                for skill_dir in repo_dir.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    skill_id = f"{owner_dir.name}/{repo_dir.name}/{skill_dir.name}"
                    yield skill_dir, skill_id


def clear_cache(pattern: str | None = None) -> int:
    """Clear cached skills.

    Args:
        pattern: Optional glob pattern to filter skills (e.g., "owner/repo/*")
                 If None, clears all cached skills.

    Returns:
        Number of skill directories deleted
    """
    skills_cache = get_cache_dir() / "skills"
    if not skills_cache.exists():
        return 0

    count = 0
    for skill_dir, skill_id in _iter_skill_cache_dirs(skills_cache):
        if pattern is not None and not fnmatch.fnmatch(skill_id, pattern):
            continue
        shutil.rmtree(skill_dir)
        count += 1
    return count


class _CacheManager:
    """Cache manager for programmatic access."""

    @property
    def path(self) -> Path:
        """Get the cache directory path."""
        return get_cache_dir()

    def info(self) -> dict:
        """Get cache information.

        Returns:
            Dict with cache statistics:
            - path: Cache directory path
            - skills_count: Number of cached skills
            - size_bytes: Total cache size in bytes
        """
        skills_cache = get_cache_dir() / "skills"
        skills_count = 0
        size_bytes = 0

        if skills_cache.exists():
            for path in skills_cache.rglob("*"):
                if path.is_file():
                    size_bytes += path.stat().st_size
                elif path.is_dir() and (path / "SKILL.md").exists():
                    # Each revision directory containing SKILL.md is one cached skill.
                    # Intermediate directories (source/owner/repo) are not counted.
                    skills_count += 1

        return {
            "path": str(get_cache_dir()),
            "skills_count": skills_count,
            "size_bytes": size_bytes,
        }

    def clear(self, pattern: str | None = None) -> int:
        """Clear cached skills.

        Args:
            pattern: Optional glob pattern to filter skills

        Returns:
            Number of skill directories deleted
        """
        return clear_cache(pattern)


cache = _CacheManager()
