"""Metadata helpers for installed skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agr.handle import ParsedHandle
from agr.source import DEFAULT_SOURCE_NAME

METADATA_FILENAME = ".agr.json"


def _resolve_local_path(handle: ParsedHandle, repo_root: Path | None) -> Path | None:
    """Resolve a local handle path to an absolute path."""
    if handle.local_path is None:
        return None

    base = repo_root or Path.cwd()
    if handle.local_path.is_absolute():
        return handle.local_path.resolve()
    return (base / handle.local_path).resolve()


def build_handle_id(
    handle: ParsedHandle, repo_root: Path | None, source: str | None = None
) -> str:
    """Build a stable identifier for a handle."""
    if handle.is_local:
        resolved = _resolve_local_path(handle, repo_root)
        return f"local:{resolved}" if resolved else "local:"
    if source:
        return f"remote:{source}:{handle.to_toml_handle()}"
    return f"remote:{handle.to_toml_handle()}"


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
    resolved_local = _resolve_local_path(handle, repo_root)
    data: dict[str, Any] = {
        "id": build_handle_id(handle, repo_root, source),
        "tool": tool_name,
        "installed_name": installed_name,
    }
    if handle.is_local:
        data["type"] = "local"
        data["local_path"] = str(resolved_local) if resolved_local else None
    else:
        data["type"] = "remote"
        data["handle"] = handle.to_toml_handle()
        data["source"] = source or DEFAULT_SOURCE_NAME

    if content_hash is not None:
        data["content_hash"] = content_hash

    metadata_path = skill_dir / METADATA_FILENAME
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
