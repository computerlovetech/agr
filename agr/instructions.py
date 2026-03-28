"""Instruction file detection and synchronization."""

from pathlib import Path

from agr.tool import TOOLS

INSTRUCTION_FILES = tuple(sorted({tool.instruction_file for tool in TOOLS.values()}))


def canonical_instruction_file(tool_name: str) -> str:
    """Resolve the canonical instruction file for a tool."""
    tool = TOOLS.get(tool_name)
    if tool is not None:
        return tool.instruction_file
    return "AGENTS.md"


def detect_instruction_files(repo_root: Path) -> list[str]:
    """Detect instruction files present in the repo root."""
    return [name for name in INSTRUCTION_FILES if (repo_root / name).exists()]


def sync_instruction_files(
    repo_root: Path, canonical_file: str, files: list[str]
) -> list[str]:
    """Sync instruction files to match the canonical file.

    Creates missing instruction files from the canonical source and
    updates existing ones that differ from the canonical content.

    Args:
        repo_root: Repository root path.
        canonical_file: Filename to copy from.
        files: Instruction filenames to sync (will be created if missing).

    Returns:
        List of filenames that were created or updated.
    """
    canonical_path = repo_root / canonical_file
    if not canonical_path.exists():
        return []

    canonical_content = canonical_path.read_text()
    updated: list[str] = []

    for filename in files:
        if filename == canonical_file:
            continue
        target_path = repo_root / filename
        if not target_path.exists() or target_path.read_text() != canonical_content:
            target_path.write_text(canonical_content)
            updated.append(filename)

    return updated
