"""Metadata helpers for installed skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agr.handle import ParsedHandle
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

# Metadata type discriminators written to and read from .agr.json
METADATA_TYPE_LOCAL = "local"
METADATA_TYPE_REMOTE = "remote"


def build_handle_id(
    handle: ParsedHandle, repo_root: Path | None, source: str | None = None
) -> str:
    """Build a stable identifier for a handle."""
    if handle.is_local:
        if handle.local_path is not None:
            resolved = handle.resolve_local_path(repo_root)
            return f"local:{resolved}"
        return "local:"
    if source:
        return f"remote:{source}:{handle.to_toml_handle()}"
    return f"remote:{handle.to_toml_handle()}"


def build_handle_ids(
    handle: ParsedHandle, repo_root: Path | None, source: str | None
) -> list[str]:
    """Build all possible metadata IDs for a handle, including legacy variants.

    Remote skills may have been installed with or without an explicit source
    name in their metadata. To find them regardless of when they were installed,
    we generate both the current ID and the legacy variant:
    - source=None  → also check with DEFAULT_SOURCE_NAME ("github")
    - source="github" → also check without explicit source
    """
    if handle.is_local:
        return [build_handle_id(handle, repo_root)]
    handle_ids = [build_handle_id(handle, repo_root, source)]
    if source is None:
        handle_ids.append(build_handle_id(handle, repo_root, DEFAULT_SOURCE_NAME))
    if source == DEFAULT_SOURCE_NAME:
        handle_ids.append(build_handle_id(handle, repo_root))
    return handle_ids


def read_skill_metadata(skill_dir: Path) -> dict[str, Any] | None:
    """Read metadata from a skill directory."""
    metadata_path = skill_dir / METADATA_FILENAME
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
        Hash string in the format "sha256:<64 hex chars>".
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
    return f"sha256:{hasher.hexdigest()}"


def write_skill_metadata(
    skill_dir: Path,
    handle: ParsedHandle,
    repo_root: Path | None,
    tool_name: str,
    installed_name: str,
    source: str | None = None,
    content_hash: str | None = None,
) -> None:
    """Write metadata for an installed skill."""
    resolved_local = (
        handle.resolve_local_path(repo_root) if handle.local_path is not None else None
    )
    data: dict[str, Any] = {
        METADATA_KEY_ID: build_handle_id(handle, repo_root, source),
        METADATA_KEY_TOOL: tool_name,
        METADATA_KEY_INSTALLED_NAME: installed_name,
    }
    if handle.is_local:
        data[METADATA_KEY_TYPE] = METADATA_TYPE_LOCAL
        data[METADATA_KEY_LOCAL_PATH] = str(resolved_local) if resolved_local else None
    else:
        data[METADATA_KEY_TYPE] = METADATA_TYPE_REMOTE
        data[METADATA_KEY_HANDLE] = handle.to_toml_handle()
        data[METADATA_KEY_SOURCE] = source or DEFAULT_SOURCE_NAME

    if content_hash is not None:
        data[METADATA_KEY_CONTENT_HASH] = content_hash

    metadata_path = skill_dir / METADATA_FILENAME
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")


def stamp_skill_metadata(
    skill_dir: Path,
    handle: ParsedHandle,
    repo_root: Path | None,
    tool_name: str,
    installed_name: str,
    source: str | None = None,
) -> None:
    """Compute content hash and write metadata for a skill in one step.

    This is a convenience wrapper around compute_content_hash +
    write_skill_metadata, used whenever a skill directory needs its
    metadata stamped (initial install, self-install, migration).
    """
    content_hash = compute_content_hash(skill_dir)
    write_skill_metadata(
        skill_dir,
        handle,
        repo_root,
        tool_name,
        installed_name,
        source,
        content_hash,
    )
