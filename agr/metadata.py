"""Metadata helpers for installed skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agr.handle import ParsedHandle, iter_repo_candidates
from agr.source import DEFAULT_SOURCE_NAME

METADATA_FILENAME = ".agr.json"

# Metadata JSON field names used as dictionary keys in .agr.json
METADATA_KEY_ID = "id"
METADATA_KEY_TYPE = "type"
METADATA_KEY_CONTENT_HASH = "content_hash"
METADATA_KEY_TOOL = "tool"
METADATA_KEY_INSTALLED_NAME = "installed_name"
METADATA_KEY_LOCAL_PATH = "local_path"
METADATA_KEY_HANDLE = "handle"
METADATA_KEY_SOURCE = "source"

# Metadata type discriminators written to and read from .agr.json.
# These values also serve as the prefix in metadata IDs produced by
# build_handle_id (e.g. "local:/abs/path", "remote:user/skill").
METADATA_TYPE_LOCAL = "local"
METADATA_TYPE_REMOTE = "remote"

# Hash algorithm used by compute_content_hash for deterministic file hashing.
CONTENT_HASH_ALGORITHM = "sha256"


def build_handle_id(
    handle: ParsedHandle, repo_root: Path | None, source: str | None = None
) -> str:
    """Build a stable identifier for a handle."""
    if handle.is_local:
        if handle.local_path is not None:
            resolved = handle.resolve_local_path(repo_root)
            return f"{METADATA_TYPE_LOCAL}:{resolved}"
        return f"{METADATA_TYPE_LOCAL}:"
    if source:
        return f"{METADATA_TYPE_REMOTE}:{source}:{handle.to_toml_handle()}"
    return f"{METADATA_TYPE_REMOTE}:{handle.to_toml_handle()}"


def build_handle_ids(
    handle: ParsedHandle,
    repo_root: Path | None,
    source: str | None,
    default_repo: str | None = None,
) -> list[str]:
    """Build all possible metadata IDs for a handle, including legacy variants.

    Remote skills may have been installed with or without an explicit source
    name in their metadata. To find them regardless of when they were installed,
    we generate both the current ID and the legacy variant:
    - source=None  → also check with DEFAULT_SOURCE_NAME ("github")
    - source="github" → also check without explicit source

    ``default_repo`` must match the value that ``iter_repo_candidates`` would
    have used at install time (i.e. ``AgrConfig.default_repo``). Otherwise a
    user who configured a custom default repo will see spurious reinstalls
    because the shorthand/resolved-handle back-off set won't include their
    repo name.
    """
    if handle.is_local:
        return [build_handle_id(handle, repo_root)]

    # Keep lookups stable across the shorthand-to-resolved-handle
    # migration. Pre-fix installs stamped metadata with the 2-part form
    # (``owner/name``); post-fix installs stamp the fully-resolved 3-part
    # form (``owner/repo/name``). Emit both shapes when the repo is or
    # would be a default candidate so either metadata form matches.
    default_candidates = {
        repo_name for repo_name, _ in iter_repo_candidates(None, default_repo)
    }
    handle_variants: list[ParsedHandle] = [handle]
    if handle.repo is None:
        for repo_name in default_candidates:
            handle_variants.append(handle.with_repo(repo_name))
    elif handle.repo in default_candidates:
        # Shorthand variant — strip the default repo back off. Matches
        # pre-fix metadata that was stamped before sync rewrote agr.toml.
        handle_variants.append(
            ParsedHandle(
                username=handle.username,
                repo=None,
                name=handle.name,
            )
        )

    seen: set[str] = set()
    handle_ids: list[str] = []
    for variant in handle_variants:
        sources_to_try: list[str | None] = [source]
        if source is None:
            sources_to_try.append(DEFAULT_SOURCE_NAME)
        elif source == DEFAULT_SOURCE_NAME:
            sources_to_try.append(None)
        for src in sources_to_try:
            hid = build_handle_id(variant, repo_root, src)
            if hid not in seen:
                seen.add(hid)
                handle_ids.append(hid)
    return handle_ids


def read_resource_metadata(resource_dir: Path) -> dict[str, Any] | None:
    """Read metadata from an installed resource directory (skill or ralph)."""
    metadata_path = resource_dir / METADATA_FILENAME
    if not metadata_path.exists():
        return None
    try:
        data = json.loads(metadata_path.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def compute_content_hash(skill_dir: Path) -> str:
    """Compute a deterministic SHA-256 content hash for a skill directory.

    Walks all files recursively (excluding .agr.json), sorts by relative
    POSIX path, and feeds each path + contents into a single SHA-256 hasher.

    Returns:
        Hash string in the format "<algorithm>:<64 hex chars>".
    """
    hasher = hashlib.sha256()
    entries: list[tuple[str, Path]] = []
    for file_path in skill_dir.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(skill_dir).as_posix()
        if rel == METADATA_FILENAME:
            continue
        entries.append((rel, file_path))
    entries.sort(key=lambda e: e[0])
    for rel, file_path in entries:
        hasher.update(rel.encode())
        hasher.update(b"\0")
        hasher.update(file_path.read_bytes())
        hasher.update(b"\0")
    return f"{CONTENT_HASH_ALGORITHM}:{hasher.hexdigest()}"


def write_resource_metadata(
    resource_dir: Path,
    handle: ParsedHandle,
    repo_root: Path | None,
    installed_name: str,
    tool_name: str | None = None,
    source: str | None = None,
    content_hash: str | None = None,
) -> None:
    """Write metadata for an installed resource (skill or ralph).

    Args:
        resource_dir: Directory where the resource is installed.
        handle: Parsed dependency handle.
        repo_root: Repository root for resolving local paths.
        installed_name: Name the resource was installed as.
        tool_name: Tool name (set for skills, ``None`` for ralphs).
        source: Optional source name for remote handles.
        content_hash: Optional pre-computed content hash.
    """
    resolved_local = (
        handle.resolve_local_path(repo_root) if handle.local_path is not None else None
    )
    data: dict[str, Any] = {
        METADATA_KEY_ID: build_handle_id(handle, repo_root, source),
        METADATA_KEY_INSTALLED_NAME: installed_name,
    }
    if tool_name is not None:
        data[METADATA_KEY_TOOL] = tool_name

    if handle.is_local:
        data[METADATA_KEY_TYPE] = METADATA_TYPE_LOCAL
        data[METADATA_KEY_LOCAL_PATH] = str(resolved_local) if resolved_local else None
    else:
        data[METADATA_KEY_TYPE] = METADATA_TYPE_REMOTE
        data[METADATA_KEY_HANDLE] = handle.to_toml_handle()
        data[METADATA_KEY_SOURCE] = source or DEFAULT_SOURCE_NAME

    if content_hash is not None:
        data[METADATA_KEY_CONTENT_HASH] = content_hash

    metadata_path = resource_dir / METADATA_FILENAME
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")


def stamp_resource_metadata(
    resource_dir: Path,
    handle: ParsedHandle,
    repo_root: Path | None,
    installed_name: str,
    tool_name: str | None = None,
    source: str | None = None,
) -> None:
    """Compute content hash and write metadata in one step."""
    content_hash = compute_content_hash(resource_dir)
    write_resource_metadata(
        resource_dir,
        handle,
        repo_root,
        installed_name,
        tool_name=tool_name,
        source=source,
        content_hash=content_hash,
    )
