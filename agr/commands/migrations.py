"""Migration utilities for legacy skill directory layouts.

Handles directory renames, tool-specific path changes, and metadata
updates needed when upgrading from older naming conventions.
"""

import shutil
from pathlib import Path

from agr.config import AgrConfig
from agr.console import get_console
from agr.exceptions import AgrError
from agr.handle import (
    INSTALLED_NAME_SEPARATOR,
    LEGACY_SEPARATOR,
    ParsedHandle,
)
from agr.metadata import (
    build_handle_id,
    compute_content_hash,
    read_skill_metadata,
    write_skill_metadata,
)
from agr.skill import SKILL_MARKER, is_valid_skill_dir, update_skill_md_name
from agr.source import DEFAULT_SOURCE_NAME
from agr.tool import ToolConfig


def _migrate_skills_directory(
    old_skills_dir: Path,
    new_skills_dir: Path,
    *,
    cleanup_parent: bool = False,
) -> None:
    """Migrate skills from one directory to another.

    Moves skill subdirectories from old_skills_dir to new_skills_dir,
    skipping any that already exist at the target. Cleans up the old
    directory if empty after migration.

    Args:
        old_skills_dir: The old skills directory to migrate from.
        new_skills_dir: The new skills directory to migrate to.
        cleanup_parent: If True, also remove the parent of old_skills_dir
            when it becomes empty (e.g., removing .codex/ after .codex/skills/).
    """
    console = get_console()

    if not old_skills_dir.exists():
        return

    old_label = old_skills_dir.name
    old_parent_label = old_skills_dir.parent.name
    old_rel = f"{old_parent_label}/{old_label}"
    new_label = new_skills_dir.name
    new_parent_label = new_skills_dir.parent.name
    new_rel = f"{new_parent_label}/{new_label}"

    new_skills_dir.mkdir(parents=True, exist_ok=True)

    for skill_dir in old_skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        target = new_skills_dir / skill_dir.name
        if target.exists():
            console.print(
                f"[yellow]Cannot migrate:[/yellow] {old_rel}/{skill_dir.name}"
            )
            console.print(
                f"  [dim]Target {new_rel}/{skill_dir.name} already exists[/dim]"
            )
            continue

        try:
            shutil.move(str(skill_dir), target)
            console.print(
                f"[blue]Migrated:[/blue] "
                f"{old_rel}/{skill_dir.name} -> "
                f"{new_rel}/{skill_dir.name}"
            )
        except OSError as e:
            console.print(f"[red]Failed to migrate:[/red] {old_rel}/{skill_dir.name}")
            console.print(f"  [dim]{e}[/dim]")

    # Warn about non-directory files left behind
    if old_skills_dir.exists():
        leftover = [f for f in old_skills_dir.iterdir() if not f.is_dir()]
        if leftover:
            console.print(
                f"[yellow]Note:[/yellow] "
                f"{len(leftover)} non-skill file(s) "
                f"remain in {old_rel}/"
            )

    # Clean up empty old directory
    if old_skills_dir.exists() and not any(old_skills_dir.iterdir()):
        old_skills_dir.rmdir()

    # Optionally clean up empty parent directory
    if cleanup_parent:
        parent = old_skills_dir.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


def run_tool_migrations(
    tools: list[ToolConfig],
    repo_root: Path | None,
    global_install: bool = False,
) -> None:
    """Run all tool-specific directory migrations.

    Handles Codex (.codex/ -> .agents/) and OpenCode (.opencode/skill/ ->
    .opencode/skills/) migrations when those tools are configured.

    Args:
        tools: List of tool configurations to migrate.
        repo_root: Repository root for local installs, or None.
        global_install: If True, use home directory paths for global installs.
    """
    base = Path.home() if global_install else repo_root
    if base is None:
        return

    tool_by_name = {tool.name: tool for tool in tools}

    # Codex migration: .codex/skills/ -> .agents/skills/
    if "codex" in tool_by_name:
        _migrate_skills_directory(
            base / ".codex" / "skills",
            base / ".agents" / "skills",
            cleanup_parent=True,
        )

    # OpenCode migration: .opencode/skill/ -> .opencode/skills/
    if "opencode" in tool_by_name:
        tool = tool_by_name["opencode"]
        # Use global_config_dir for global installs (e.g., .config/opencode)
        opencode_dir = (
            tool.global_config_dir
            if global_install and tool.global_config_dir
            else tool.config_dir
        )
        _migrate_skills_directory(
            base / opencode_dir / "skill",
            base / opencode_dir / "skills",
            cleanup_parent=False,
        )


def migrate_legacy_directories(skills_dir: Path, tool: ToolConfig) -> None:
    """Migrate colon-based directory names to the new separator format.

    This ensures backward compatibility with skills installed before
    the Windows-compatible naming scheme was introduced.

    Only applies to flat tools (Claude), not nested tools (Cursor).

    Args:
        skills_dir: The skills directory to scan for legacy directories.
        tool: Tool configuration (migration only for non-nested tools).
    """
    console = get_console()
    # Only migrate for flat tools
    if tool.supports_nested:
        return

    if not skills_dir.exists():
        return

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        if LEGACY_SEPARATOR not in skill_dir.name:
            continue
        # Verify it's a skill (has SKILL.md)
        if not (skill_dir / SKILL_MARKER).exists():
            continue

        # Convert legacy separator to new separator
        new_name = skill_dir.name.replace(LEGACY_SEPARATOR, INSTALLED_NAME_SEPARATOR)
        new_path = skills_dir / new_name

        if new_path.exists():
            console.print(f"[yellow]Cannot migrate:[/yellow] {skill_dir.name}")
            console.print(f"  [dim]Target {new_name} already exists[/dim]")
            continue

        try:
            skill_dir.rename(new_path)
            console.print(f"[blue]Migrated:[/blue] {skill_dir.name} -> {new_name}")
        except OSError as e:
            console.print(f"[red]Failed to migrate:[/red] {skill_dir.name}")
            console.print(f"  [dim]{e}[/dim]")


def _update_dir_metadata(
    skill_dir: Path,
    handle: ParsedHandle,
    repo_root: Path,
    tool_name: str,
    source_name: str | None,
) -> None:
    """Update SKILL.md name and write metadata for a skill directory."""
    update_skill_md_name(skill_dir, skill_dir.name)
    write_skill_metadata(
        skill_dir,
        handle,
        repo_root,
        tool_name,
        skill_dir.name,
        source_name,
        compute_content_hash(skill_dir),
    )


def migrate_flat_installed_names(
    skills_dir: Path,
    tool: ToolConfig,
    config: AgrConfig,
    repo_root: Path,
) -> None:
    """Migrate flat skill names to the plain ``<skill>`` format when safe.

    Older versions always installed skills under their full flat name
    (``user--repo--skill``). This migration renames them to the shorter
    plain name (``skill``) when there is no ambiguity.

    The logic has three cases per skill name:

    1. **Unique name** (one handle owns this name) — safe to use the plain
       directory name. Rename ``user--repo--skill/`` → ``skill/`` if needed,
       and ensure metadata is up to date.
    2. **Ambiguous name** (multiple handles share the same skill name) —
       keep the full flat names to avoid collisions, but stamp metadata
       on each directory so future operations can identify them.
    3. **Unknown installs** (not tracked in agr.toml) — skipped, because
       we can't determine the correct handle identity.

    Only applies to flat tools (e.g. Claude). Nested tools (e.g. Cursor)
    already use ``user/repo/skill/`` paths and don't need this.
    """
    console = get_console()
    if tool.supports_nested:
        return

    if not skills_dir.exists():
        return

    # Index agr.toml dependencies by skill name so we can look up which
    # handles claim each name. A name with >1 handle is ambiguous.
    handles_by_name: dict[str, list[tuple[ParsedHandle, str | None]]] = {}
    for dep in config.dependencies:
        if not (dep.path or dep.handle):
            continue
        try:
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)
        except (AgrError, ValueError):
            continue
        handles_by_name.setdefault(handle.name, []).append((handle, source_name))

    for skill_name, handles in handles_by_name.items():
        name_dir = skills_dir / skill_name
        name_dir_is_skill = is_valid_skill_dir(name_dir)

        # Check if the plain-name dir already belongs to one of the known
        # handles (by comparing .agr.json metadata IDs). This tells us
        # whether the directory is "claimed" and by whom.
        matched_handle: tuple[ParsedHandle, str | None] | None = None
        if name_dir_is_skill:
            meta = read_skill_metadata(name_dir)
            if meta:
                for handle, source_name in handles:
                    handle_id = build_handle_id(handle, repo_root, source_name)
                    # Also check the legacy ID format (without explicit source)
                    # for backward compatibility with pre-source metadata.
                    legacy_id = (
                        build_handle_id(handle, repo_root)
                        if source_name == DEFAULT_SOURCE_NAME
                        else None
                    )
                    if meta.get("id") in {handle_id, legacy_id}:
                        matched_handle = (handle, source_name)
                        break

        # --- Case 1: Unique name (single handle) ---
        # Safe to use the short plain directory name.
        if len(handles) == 1:
            handle, source_name = handles[0]
            handle_id = build_handle_id(handle, repo_root, source_name)
            if name_dir_is_skill:
                # Plain-name dir exists — just ensure metadata is current.
                meta = read_skill_metadata(name_dir)
                if not meta or meta.get("id") != handle_id:
                    _update_dir_metadata(
                        name_dir, handle, repo_root, tool.name, source_name
                    )
                continue

            # Plain-name dir doesn't exist — try renaming from the full
            # flat name (e.g. ``user--repo--skill`` → ``skill``).
            full_dir = skills_dir / handle.to_installed_name()
            if is_valid_skill_dir(full_dir):
                if not name_dir.exists():
                    try:
                        full_dir.rename(name_dir)
                        _update_dir_metadata(
                            name_dir, handle, repo_root, tool.name, source_name
                        )
                        console.print(
                            f"[blue]Migrated:[/blue] {full_dir.name} -> {name_dir.name}"
                        )
                    except OSError as e:
                        console.print(f"[red]Failed to migrate:[/red] {full_dir.name}")
                        console.print(f"  [dim]{e}[/dim]")
                # else: something non-skill occupies the name; skip.
            continue

        # --- Case 2: Ambiguous name (multiple handles) ---
        # Can't safely rename to the short name, but stamp metadata on
        # whichever directories exist so they can be identified later.
        if matched_handle:
            _update_dir_metadata(
                name_dir, matched_handle[0], repo_root, tool.name, matched_handle[1]
            )

        for handle, source_name in handles:
            full_dir = skills_dir / handle.to_installed_name()
            if is_valid_skill_dir(full_dir):
                _update_dir_metadata(
                    full_dir, handle, repo_root, tool.name, source_name
                )
