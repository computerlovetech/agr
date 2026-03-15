"""agr sync command implementation."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from agr.commands.migrations import (
    migrate_flat_installed_names,
    migrate_legacy_directories,
    run_tool_migrations,
)
from agr.config import AgrConfig, find_config, get_global_config_path, require_repo_root
from agr.console import get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.fetcher import (
    fetch_and_install_to_tools,
    filter_tools_needing_install,
    install_skill_from_repo_to_tools,
    prepare_repo_for_skills,
    skill_not_found_message,
)
from agr.git import downloaded_repo
from agr.handle import ParsedHandle
from agr.source import SourceResolver
from agr.instructions import (
    canonical_instruction_file,
    sync_instruction_files,
)
from agr.tool import ToolConfig, build_global_skills_dirs


class SyncStatus(Enum):
    """Status of a single dependency sync operation."""

    PENDING = "pending"
    UP_TO_DATE = "up-to-date"
    INSTALLED = "installed"
    ERROR = "error"


@dataclass
class SyncResult:
    """Result of syncing a single dependency."""

    status: SyncStatus
    error: str | None = None


@dataclass
class SyncEntry:
    """A dependency queued for sync, with its position in the results list."""

    index: int
    handle: ParsedHandle
    source_name: str | None


def _print_results_and_summary(
    results: list[tuple[str, SyncResult]],
) -> None:
    """Print per-dependency results and the final summary.

    Each entry is an (identifier, SyncResult) pair. Installed and
    up-to-date items are printed inline; errors include the message.
    Raises SystemExit(1) when any dependency failed.
    """
    console = get_console()
    installed = 0
    up_to_date = 0
    errors = 0

    for identifier, result in results:
        if result.status == SyncStatus.INSTALLED:
            console.print(f"[green]Installed:[/green] {identifier}")
            installed += 1
        elif result.status == SyncStatus.UP_TO_DATE:
            console.print(f"[dim]Up to date:[/dim] {identifier}")
            up_to_date += 1
        else:
            print_error(identifier)
            if result.error:
                console.print(f"  [dim]{result.error}[/dim]")
            errors += 1

    console.print()
    parts = []
    if installed:
        parts.append(f"{installed} installed")
    if up_to_date:
        parts.append(f"{up_to_date} up to date")
    if errors:
        parts.append(f"{errors} failed")
    console.print(f"[bold]Summary:[/bold] {', '.join(parts)}")

    if errors:
        raise SystemExit(1)


def _sync_instructions_if_configured(
    repo_root: Path, config: AgrConfig, tools: list[ToolConfig]
) -> None:
    """Copy the canonical instruction file to other tools' instruction files.

    Skipped when sync_instructions is not enabled or fewer than two tools
    are configured.  The canonical file is determined by
    ``config.canonical_instructions`` or the default tool's instruction file.
    """
    console = get_console()
    if not config.sync_instructions:
        return
    if len(tools) < 2:
        return

    if config.canonical_instructions:
        canonical_file = config.canonical_instructions
    else:
        tool_name = config.default_tool or tools[0].name
        canonical_file = canonical_instruction_file(tool_name)

    # Canonical source must exist — otherwise there is nothing to sync from.
    if not (repo_root / canonical_file).exists():
        console.print(
            f"[yellow]Instruction sync skipped:[/yellow] {canonical_file} not found."
        )
        return

    # Build the set of target files from all configured tools (excluding canonical).
    target_files = sorted(
        {
            tool.instruction_file
            for tool in tools
            if tool.instruction_file != canonical_file
        }
    )

    if not target_files:
        return

    updated = sync_instruction_files(repo_root, canonical_file, target_files)
    if updated:
        updated_list = ", ".join(updated)
        console.print(
            f"[green]Synced instructions:[/green] {canonical_file} -> {updated_list}"
        )


def _sync_individual_entries(
    entries: list[SyncEntry],
    results: list[SyncResult],
    repo_root: Path | None,
    tools: list[ToolConfig],
    resolver: SourceResolver,
) -> None:
    """Sync entries one at a time, each downloading its own repo if needed.

    Used for local skills (no download) and default-repo remotes
    (two-part handles like ``user/skill`` where the repo name must be
    discovered by trying candidates).
    """
    for entry in entries:
        try:
            results[entry.index] = _sync_one_dependency(
                entry.handle, entry.source_name, repo_root, tools, resolver
            )
        except INSTALL_ERROR_TYPES as e:
            results[entry.index] = SyncResult(SyncStatus.ERROR, format_install_error(e))


def _sync_batched_repo_entries(
    entries: list[SyncEntry],
    results: list[SyncResult],
    repo_root: Path | None,
    tools: list[ToolConfig],
    resolver: SourceResolver,
    default_source: str,
) -> None:
    """Sync remote entries grouped by repo, downloading each repo only once.

    Groups entries by (source, owner, repo) so that multiple skills from
    the same repository share a single download.
    """
    # Group entries by (source, owner, repo) so all skills from the same
    # repository are installed from a single git clone.
    grouped: dict[tuple[str, str, str], list[SyncEntry]] = {}
    for entry in entries:
        handle = entry.handle
        source_name = entry.source_name or default_source
        owner, repo_name = handle.get_github_repo()
        key = (source_name, owner, repo_name)
        grouped.setdefault(key, []).append(entry)

    for (source_name, owner, repo_name), group in grouped.items():
        try:
            source_config = resolver.get(source_name)
            with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                # Prepare all skills from this repo in one sparse checkout pass.
                skill_names = [entry.handle.name for entry in group]
                skill_sources = prepare_repo_for_skills(repo_dir, skill_names)
                for entry in group:
                    _install_one_from_repo(
                        entry,
                        results,
                        repo_dir,
                        skill_sources,
                        repo_root,
                        tools,
                        source_name,
                    )
        except INSTALL_ERROR_TYPES as e:
            # If the repo-level operation fails (clone, checkout), mark
            # every skill in the group as failed.
            for entry in group:
                results[entry.index] = SyncResult(
                    SyncStatus.ERROR, format_install_error(e)
                )


def _install_one_from_repo(
    entry: SyncEntry,
    results: list[SyncResult],
    repo_dir: Path,
    skill_sources: dict[str, Path],
    repo_root: Path | None,
    tools: list[ToolConfig],
    source_name: str,
) -> None:
    """Install a single skill from an already-downloaded repo."""
    handle = entry.handle
    tools_needing_install = filter_tools_needing_install(
        handle, repo_root, tools, entry.source_name
    )
    if not tools_needing_install:
        results[entry.index] = SyncResult(SyncStatus.UP_TO_DATE)
        return
    skill_source = skill_sources.get(handle.name)
    if skill_source is None:
        results[entry.index] = SyncResult(
            SyncStatus.ERROR,
            skill_not_found_message(handle.name),
        )
        return
    try:
        install_skill_from_repo_to_tools(
            repo_dir,
            handle.name,
            handle,
            tools_needing_install,
            repo_root,
            overwrite=False,
            install_source=source_name,
            skill_source=skill_source,
        )
        results[entry.index] = SyncResult(SyncStatus.INSTALLED)
    except INSTALL_ERROR_TYPES as e:
        results[entry.index] = SyncResult(SyncStatus.ERROR, format_install_error(e))


def _sync_one_dependency(
    handle: ParsedHandle,
    source_name: str | None,
    repo_root: Path | None,
    tools: list[ToolConfig],
    resolver: SourceResolver,
    skills_dirs: dict[str, Path] | None = None,
) -> SyncResult:
    """Sync a single dependency: check install status and install if needed.

    Returns UP_TO_DATE when all tools already have the skill installed,
    or INSTALLED after a successful install.  Raises on failure so the
    caller can handle errors per-entry.
    """
    tools_needing_install = filter_tools_needing_install(
        handle, repo_root, tools, source_name, skills_dirs
    )
    if not tools_needing_install:
        return SyncResult(SyncStatus.UP_TO_DATE)

    fetch_and_install_to_tools(
        handle,
        repo_root,
        tools_needing_install,
        overwrite=False,
        resolver=resolver,
        source=source_name,
        skills_dirs=skills_dirs,
    )
    return SyncResult(SyncStatus.INSTALLED)


def _run_global_sync() -> None:
    """Sync global dependencies from ~/.agr/agr.toml."""
    console = get_console()
    config_path = get_global_config_path()
    if not config_path.exists():
        console.print("[yellow]No global agr.toml found.[/yellow] Nothing to sync.")
        console.print("[dim]Run 'agr add -g <handle>' to create one.[/dim]")
        return

    config = AgrConfig.load(config_path)
    tools = config.get_tools()
    skills_dirs = build_global_skills_dirs(tools)

    run_tool_migrations(tools, repo_root=None, global_install=True)

    if not config.dependencies:
        console.print(
            "[yellow]No dependencies in global agr.toml.[/yellow] Nothing to sync."
        )
        return

    resolver = config.get_source_resolver()

    results: list[tuple[str, SyncResult]] = []

    for dep in config.dependencies:
        try:
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)
            result = _sync_one_dependency(
                handle, source_name, None, tools, resolver, skills_dirs
            )
        except INSTALL_ERROR_TYPES as e:
            result = SyncResult(SyncStatus.ERROR, format_install_error(e))
        results.append((dep.identifier, result))

    _print_results_and_summary(results)


def run_sync(global_install: bool = False) -> None:
    """Run the sync command.

    Installs all dependencies from agr.toml that aren't already installed.

    The sync flow has four stages:
    1. **Instruction sync** — copy the canonical instruction file (e.g.
       CLAUDE.md) to other tools' instruction files when enabled.
    2. **Migrations** — rename legacy skill directories to current naming
       conventions (colon → double-hyphen, full names → plain names).
    3. **Dependency install** — install missing skills, optimizing downloads
       by batching same-repo remotes into a single git clone.
    4. **Report** — print per-dependency status and a summary line.
    """
    console = get_console()
    if global_install:
        _run_global_sync()
        return

    repo_root = require_repo_root()

    config_path = find_config()
    if config_path is None:
        console.print("[yellow]No agr.toml found.[/yellow] Nothing to sync.")
        return

    config = AgrConfig.load(config_path)
    tools = config.get_tools()

    # Stage 1: Sync instruction files across tools (e.g. CLAUDE.md → AGENTS.md).
    _sync_instructions_if_configured(repo_root, config, tools)

    # Stage 2: Run directory migrations before installing new skills so that
    # existing installs are in the expected layout for duplicate detection.
    run_tool_migrations(tools, repo_root)
    for tool in tools:
        skills_dir = tool.get_skills_dir(repo_root)
        migrate_legacy_directories(skills_dir, tool)
        migrate_flat_installed_names(skills_dir, tool, config, repo_root)

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow] Nothing to sync.")
        return

    resolver = config.get_source_resolver()

    # --- Phase 1: Classify dependencies ---
    # Pre-allocate a result slot per dependency so parallel paths can fill
    # them by index without coordination.
    results: list[SyncResult] = [
        SyncResult(SyncStatus.PENDING) for _ in config.dependencies
    ]
    pending_local: list[SyncEntry] = []
    pending_remote: list[SyncEntry] = []

    for index, dep in enumerate(config.dependencies):
        try:
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)

            # Skip dependencies already installed on every configured tool.
            tools_needing_install = filter_tools_needing_install(
                handle, repo_root, tools, source_name
            )

            if not tools_needing_install:
                results[index] = SyncResult(SyncStatus.UP_TO_DATE)
                continue

            entry = SyncEntry(
                index=index,
                handle=handle,
                source_name=source_name,
            )
            if dep.is_local:
                pending_local.append(entry)
            else:
                pending_remote.append(entry)
        except INSTALL_ERROR_TYPES as e:
            results[index] = SyncResult(SyncStatus.ERROR, format_install_error(e))

    # --- Phase 2: Install pending dependencies ---
    # Three categories are processed separately for efficiency:
    #
    # 1. Local skills — no git download, just copy from the local path.
    _sync_individual_entries(pending_local, results, repo_root, tools, resolver)

    # 2. Default-repo remotes (two-part handles like "user/skill") — the
    #    repo name is unknown and must be discovered by trying candidates
    #    ("skills", "agent-resources"), so each must download individually.
    pending_remote_default = [e for e in pending_remote if e.handle.repo is None]
    pending_remote_specific = [e for e in pending_remote if e.handle.repo is not None]

    _sync_individual_entries(
        pending_remote_default, results, repo_root, tools, resolver
    )

    # 3. Specific-repo remotes (three-part handles like "user/repo/skill") —
    #    grouped by (source, owner, repo) so multiple skills from the same
    #    repository share a single git clone.
    _sync_batched_repo_entries(
        pending_remote_specific,
        results,
        repo_root,
        tools,
        resolver,
        config.default_source,
    )

    # --- Phase 3: Report ---
    labeled_results = [
        (dep.identifier, results[index])
        for index, dep in enumerate(config.dependencies)
    ]
    _print_results_and_summary(labeled_results)
