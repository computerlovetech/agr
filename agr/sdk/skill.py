"""Skill class for loading and accessing skills programmatically."""

import hashlib
import subprocess
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from agr.exceptions import (
    InvalidHandleError,
    InvalidLocalPathError,
    RepoNotFoundError,
    SkillNotFoundError,
)
from agr.fetcher import prepare_repo_for_skill
from agr.git import downloaded_repo
from agr.handle import (
    LEGACY_REPO_DEPRECATION_WARNING,
    ParsedHandle,
    iter_repo_candidates,
    parse_handle,
)
from agr.metadata import compute_content_hash, read_skill_metadata
from agr.sdk.cache import cache_skill, get_skill_cache_path, is_cached
from agr.skill import SKILL_MARKER, is_valid_skill_dir
from agr.source import SourceConfig, default_sources


def _get_head_commit(repo_dir: Path) -> str:
    """Get the HEAD commit hash of a repository.

    If git command fails, generates a unique fallback hash based on
    current time and repo path to ensure proper cache busting.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Generate unique fallback to prevent cache collisions
        fallback_data = f"{time.time_ns()}:{repo_dir}"
        return hashlib.sha256(fallback_data.encode()).hexdigest()[:12]
    return result.stdout.strip()[:12]


@dataclass
class Skill:
    """A loaded skill with content access.

    Provides lazy access to skill content including the SKILL.md prompt
    and file listing.

    Example:
        >>> skill = Skill.from_git("kasperjunge/commit")
        >>> print(skill.prompt)  # Contents of SKILL.md
        >>> print(skill.files)   # List of files
    """

    name: str
    path: Path
    handle: ParsedHandle | None = None
    source: str | None = None
    revision: str | None = None
    _prompt: str | None = field(default=None, repr=False)
    _files: list[str] | None = field(default=None, repr=False)

    @classmethod
    def from_git(
        cls,
        handle: str,
        *,
        force_download: bool = False,
    ) -> "Skill":
        """Load a skill from a Git repository.

        Downloads the skill from GitHub and caches it locally for subsequent use.

        Args:
            handle: Skill handle (e.g., "kasperjunge/commit" or "owner/repo/skill")
            force_download: Force re-download even if cached

        Returns:
            Loaded Skill instance

        Raises:
            InvalidHandleError: If handle format is invalid
            SkillNotFoundError: If skill not found in repository

        Example:
            >>> skill = Skill.from_git("kasperjunge/commit")
            >>> skill = Skill.from_git("anthropics/skills/code-review")
        """
        # Reject obvious local paths early
        if handle.startswith(("./", "../", "/")):
            raise InvalidHandleError(
                f"'{handle}' is a local path. Use Skill.from_local() instead."
            )

        # Parse handle
        parsed = parse_handle(handle, prefer_local=False)
        if parsed.is_local:
            raise InvalidHandleError(
                f"'{handle}' is a local path. Use Skill.from_local() instead."
            )

        owner = parsed.username or ""
        repo_candidates = iter_repo_candidates(parsed.repo)

        # Get default source
        sources = default_sources()
        source_config = (
            sources[0]
            if sources
            else SourceConfig(
                name="github", type="git", url="https://github.com/{owner}/{repo}.git"
            )
        )

        # Try each repo candidate (e.g. "skills", then legacy "agent-resources").
        # Track errors separately: SkillNotFoundError means the repo exists but
        # the skill isn't in it; RepoNotFoundError means the repo doesn't exist.
        # We re-raise the most specific error after exhausting all candidates.
        last_error: SkillNotFoundError | None = None
        last_repo_error: RepoNotFoundError | None = None
        for repo_name, is_legacy in repo_candidates:
            try:
                with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                    # Get commit hash for cache key
                    commit = _get_head_commit(repo_dir)

                    # Check cache
                    if not force_download and is_cached(
                        owner, repo_name, parsed.name, commit
                    ):
                        cached_path = get_skill_cache_path(
                            owner, repo_name, parsed.name, commit
                        )
                        if is_legacy:
                            warnings.warn(
                                LEGACY_REPO_DEPRECATION_WARNING,
                                UserWarning,
                                stacklevel=2,
                            )
                        return cls(
                            name=parsed.name,
                            path=cached_path,
                            handle=parsed,
                            source=source_config.name,
                            revision=commit,
                        )

                    # Find and checkout skill
                    skill_path = prepare_repo_for_skill(repo_dir, parsed.name)
                    if skill_path is None:
                        last_error = SkillNotFoundError(
                            f"Skill '{parsed.name}' not found "
                            f"in repository "
                            f"'{owner}/{repo_name}'."
                        )
                        continue

                    # Cache the skill
                    cached_path = cache_skill(
                        skill_path, owner, repo_name, parsed.name, commit
                    )

                    if is_legacy:
                        warnings.warn(
                            LEGACY_REPO_DEPRECATION_WARNING,
                            UserWarning,
                            stacklevel=2,
                        )

                    return cls(
                        name=parsed.name,
                        path=cached_path,
                        handle=parsed,
                        source=source_config.name,
                        revision=commit,
                    )
            except SkillNotFoundError as exc:
                last_error = exc
                continue
            except RepoNotFoundError as exc:
                last_repo_error = exc
                continue

        if last_error:
            raise last_error
        if last_repo_error:
            raise last_repo_error
        raise SkillNotFoundError(
            f"Skill '{parsed.name}' not found in "
            f"repository "
            f"'{owner}/{repo_candidates[0][0]}'."
        )

    @classmethod
    def from_local(cls, path: str | Path) -> "Skill":
        """Load a skill from a local directory.

        Args:
            path: Path to local skill directory containing SKILL.md

        Returns:
            Loaded Skill instance

        Raises:
            InvalidLocalPathError: If path is not a valid skill directory

        Example:
            >>> skill = Skill.from_local("./my-skill")
            >>> skill = Skill.from_local("/path/to/skill")
        """
        skill_path = Path(path).resolve()

        if not skill_path.exists():
            raise InvalidLocalPathError(f"Path does not exist: {skill_path}")

        if not is_valid_skill_dir(skill_path):
            raise InvalidLocalPathError(
                f"'{skill_path}' is not a valid skill (missing {SKILL_MARKER})"
            )

        return cls(
            name=skill_path.name,
            path=skill_path,
            handle=ParsedHandle(
                is_local=True,
                name=skill_path.name,
                local_path=skill_path,
            ),
        )

    @property
    def prompt(self) -> str:
        """Get the skill prompt (contents of SKILL.md).

        Lazily loaded on first access.

        Returns:
            Contents of SKILL.md
        """
        if self._prompt is None:
            skill_md = self.path / SKILL_MARKER
            self._prompt = skill_md.read_text()
        return self._prompt

    @property
    def files(self) -> list[str]:
        """Get list of files in the skill directory.

        Lazily loaded on first access.

        Returns:
            List of file paths relative to skill directory
        """
        if self._files is None:
            self._files = []
            for file_path in self.path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(self.path)
                    self._files.append(str(rel_path))
            self._files.sort()
        return self._files

    @property
    def metadata(self) -> dict:
        """Get skill metadata.

        Returns:
            Dict with skill metadata including name, path, handle info
        """
        return {
            "name": self.name,
            "path": str(self.path),
            "source": self.source,
            "revision": self.revision,
            "handle": self.handle.to_toml_handle() if self.handle else None,
            "is_local": self.handle.is_local if self.handle else True,
        }

    @property
    def content_hash(self) -> str | None:
        """Get the content hash from .agr.json metadata.

        Returns:
            The stored content hash string, or None if not present.
        """
        meta = read_skill_metadata(self.path)
        if meta is None:
            return None
        return meta.get("content_hash")

    def recompute_content_hash(self) -> str:
        """Recompute the content hash from the current files on disk.

        Returns:
            Fresh hash string in the format "sha256:<64 hex chars>".
        """
        return compute_content_hash(self.path)

    def read_file(self, relative_path: str) -> str:
        """Read a file from the skill directory.

        Args:
            relative_path: Path relative to skill directory

        Returns:
            File contents as string

        Raises:
            ValueError: If path attempts to escape skill directory
            FileNotFoundError: If file does not exist
        """
        # Security: prevent path traversal
        if ".." in relative_path:
            raise ValueError("Path cannot contain '..'")

        file_path = self.path / relative_path

        # Security check: ensure resolved path is within skill directory
        # Using is_relative_to() is more robust than startswith() string comparison
        # which can be fooled by paths like "/skill" vs "/skill_other"
        resolved = file_path.resolve()
        skill_dir_resolved = self.path.resolve()
        if not resolved.is_relative_to(skill_dir_resolved):
            raise ValueError("Path escapes skill directory")

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        return resolved.read_text()
