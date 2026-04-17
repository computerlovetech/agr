"""agr sync command implementation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from agr.commands._tool_helpers import load_existing_config, print_missing_config_hint
from agr.commands.migrations import (
    migrate_flat_installed_names,
    migrate_legacy_directories,
    run_tool_migrations,
)
from agr.config import (
    AgrConfig,
    Dependency,
    find_config,
    require_repo_root,
)
from agr.package import ExpandedDeps, detect_conflicts, expand_packages
from agr.console import error_exit, get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, AgrError, format_install_error
from agr._install_common import InstallResult
from agr.ralph_installer import (
    fetch_and_install_ralph,
    get_ralphs_dir,
    install_ralph_from_repo,
    is_ralph_installed,
)
from agr.skill_installer import (
    fetch_and_install_to_tools,
    filter_tools_needing_install,
    install_skill_from_repo_to_tools,
    prepare_repo_for_skills,
    skill_not_found_message,
)
from agr.git import downloaded_repo, fetch_and_checkout_commit, safe_get_head_commit
from agr.lockfile import (
    LockedEntry,
    Lockfile,
    build_lockfile_path,
    load_lockfile,
    normalize_parent_ids,
    save_lockfile,
)
from agr.handle import ParsedHandle
from agr.metadata import compute_content_hash
from agr.source import SourceResolver
from agr.instructions import (
    canonical_instruction_file,
    sync_instruction_files,
)
from agr.tool import ToolConfig


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
    # Lockfile metadata captured during install (reuses InstallResult)
    install: InstallResult | None = None

    @property
    def commit(self) -> str | None:
        return self.install.commit if self.install else None

    @property
    def content_hash(self) -> str | None:
        return self.install.content_hash if self.install else None

    @property
    def source_name(self) -> str | None:
        return self.install.source_name if self.install else None

    @classmethod
    def installed(
        cls,
        commit: str | None = None,
        content_hash: str | None = None,
        source_name: str | None = None,
    ) -> SyncResult:
        return cls(
            SyncStatus.INSTALLED,
            install=InstallResult(
                commit=commit,
                content_hash=content_hash,
                source_name=source_name,
            ),
        )

    @classmethod
    def from_install_result(cls, result: InstallResult) -> SyncResult:
        return cls(SyncStatus.INSTALLED, install=result)

    @classmethod
    def up_to_date(cls) -> SyncResult:
        return cls(SyncStatus.UP_TO_DATE)

    @classmethod
    def pending(cls) -> SyncResult:
        return cls(SyncStatus.PENDING)

    @classmethod
    def from_error(cls, exc: Exception) -> SyncResult:
        return cls(SyncStatus.ERROR, format_install_error(exc))


@dataclass
class SyncEntry:
    """A dependency queued for sync, with its position in the results list."""

    index: int
    handle: ParsedHandle
    source_name: str | None
    tools_needing_install: list[ToolConfig] | None = None
    overwrite: bool = False


@dataclass
class _ClassifiedDeps:
    """Dependencies classified by install strategy."""

    results: list[SyncResult]
    pending_local: list[SyncEntry]
    pending_remote: list[SyncEntry]
    pending_ralph: list[SyncEntry]


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
                console.print(f"  [dim]{result.error}[/dim]", soft_wrap=True)
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


def _run_pre_install_setup(
    repo_root: Path,
    config: AgrConfig,
    tools: list[ToolConfig],
) -> None:
    """Instruction sync + directory migrations. Shared by `run_sync` and `run_upgrade`."""
    _sync_instructions_if_configured(repo_root, config, tools)
    run_tool_migrations(tools, repo_root)
    for tool in tools:
        skills_dir = tool.get_skills_dir(repo_root)
        migrate_legacy_directories(skills_dir, tool)
        migrate_flat_installed_names(skills_dir, tool, config, repo_root)


def _is_forced(
    dep: Dependency,
    force_all: bool,
    force_identifiers: set[str] | None,
) -> bool:
    return force_all or (
        force_identifiers is not None and dep.identifier in force_identifiers
    )


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
    default_repo: str | None = None,
) -> None:
    """Sync entries one at a time, each downloading its own repo if needed.

    Used for local skills (no download) and default-repo remotes
    (two-part handles like ``user/skill`` where the repo name must be
    discovered by trying candidates).
    """
    for entry in entries:
        try:
            results[entry.index] = _sync_one_dependency(
                entry.handle,
                entry.source_name,
                repo_root,
                tools,
                resolver,
                tools_needing_install=entry.tools_needing_install,
                default_repo=default_repo,
                overwrite=entry.overwrite,
            )
        except INSTALL_ERROR_TYPES as e:
            results[entry.index] = SyncResult.from_error(e)


def _sync_batched_repo_entries(
    entries: list[SyncEntry],
    results: list[SyncResult],
    repo_root: Path | None,
    tools: list[ToolConfig],
    resolver: SourceResolver,
    default_source: str,
    default_repo: str | None = None,
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
        owner, repo_name = handle.get_github_repo(default_repo=default_repo)
        key = (source_name, owner, repo_name)
        grouped.setdefault(key, []).append(entry)

    for (source_name, owner, repo_name), group in grouped.items():
        try:
            source_config = resolver.get(source_name)
            with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                # Capture commit SHA for lockfile before installing.
                commit = safe_get_head_commit(repo_dir)

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
                        commit=commit,
                        overwrite=entry.overwrite,
                    )
        except INSTALL_ERROR_TYPES as e:
            # If the repo-level operation fails (clone, checkout), mark
            # every skill in the group as failed.
            for entry in group:
                results[entry.index] = SyncResult.from_error(e)


def _install_one_from_repo(
    entry: SyncEntry,
    results: list[SyncResult],
    repo_dir: Path,
    skill_sources: dict[str, Path],
    repo_root: Path | None,
    tools: list[ToolConfig],
    source_name: str,
    commit: str | None = None,
    overwrite: bool = False,
) -> None:
    """Install a single skill from an already-downloaded repo."""
    handle = entry.handle
    # _classify_dependencies only queues entries with a non-empty
    # tools_needing_install list, so the invariant is asserted rather than
    # re-checked here.
    assert entry.tools_needing_install, (
        "_classify_dependencies must populate tools_needing_install before "
        "queuing to _install_one_from_repo"
    )
    tools_needing_install = entry.tools_needing_install
    skill_source = skill_sources.get(handle.name)
    if skill_source is None:
        results[entry.index] = SyncResult(
            SyncStatus.ERROR, skill_not_found_message(handle.name)
        )
        return
    try:
        installed_paths = install_skill_from_repo_to_tools(
            repo_dir,
            handle.name,
            handle,
            tools_needing_install,
            repo_root,
            overwrite=overwrite,
            install_source=source_name,
            skill_source=skill_source,
        )
        first_path = next(iter(installed_paths.values()), None)
        content_hash = compute_content_hash(first_path) if first_path else None
        results[entry.index] = SyncResult.installed(
            commit=commit,
            content_hash=content_hash,
            source_name=source_name,
        )
    except INSTALL_ERROR_TYPES as e:
        results[entry.index] = SyncResult.from_error(e)


def _sync_one_dependency(
    handle: ParsedHandle,
    source_name: str | None,
    repo_root: Path | None,
    tools: list[ToolConfig],
    resolver: SourceResolver,
    skills_dirs: dict[str, Path] | None = None,
    tools_needing_install: list[ToolConfig] | None = None,
    default_repo: str | None = None,
    overwrite: bool = False,
) -> SyncResult:
    """Sync a single dependency: check install status and install if needed.

    Returns UP_TO_DATE when all tools already have the skill installed,
    or INSTALLED after a successful install.  Raises on failure so the
    caller can handle errors per-entry.
    """
    if tools_needing_install is None:
        if overwrite:
            tools_needing_install = list(tools)
        else:
            tools_needing_install = filter_tools_needing_install(
                handle, repo_root, tools, source_name, skills_dirs
            )
    if not tools_needing_install:
        return SyncResult.up_to_date()

    _paths, install_result = fetch_and_install_to_tools(
        handle,
        repo_root,
        tools_needing_install,
        overwrite=overwrite,
        resolver=resolver,
        source=source_name,
        skills_dirs=skills_dirs,
        default_repo=default_repo,
    )
    return SyncResult.from_install_result(install_result)


def _sync_ralph_entries(
    entries: list[SyncEntry],
    results: list[SyncResult],
    repo_root: Path | None,
    resolver: SourceResolver,
    default_repo: str | None = None,
) -> None:
    """Sync ralph dependencies to the project-level ralphs directory."""
    for entry in entries:
        try:
            path, install_result = fetch_and_install_ralph(
                entry.handle,
                repo_root,
                overwrite=entry.overwrite,
                resolver=resolver,
                source=entry.source_name,
                default_repo=default_repo,
            )
            results[entry.index] = SyncResult.from_install_result(install_result)
        except INSTALL_ERROR_TYPES as e:
            results[entry.index] = SyncResult.from_error(e)


def _run_global_sync(
    *,
    force_all: bool = False,
    force_identifiers: set[str] | None = None,
) -> None:
    """Sync global dependencies from ~/.agr/agr.toml.

    When ``force_all`` or ``force_identifiers`` is supplied, matching deps
    are re-fetched with ``overwrite=True`` (used by ``run_upgrade``).
    """
    console = get_console()
    loaded = load_existing_config(global_install=True, missing_ok=True)
    if loaded is None:
        print_missing_config_hint(global_install=True)
        return

    config, tools, skills_dirs = loaded.config, loaded.tools, loaded.skills_dirs

    run_tool_migrations(tools, repo_root=None, global_install=True)

    if not config.dependencies:
        console.print(
            "[yellow]No dependencies in global agr.toml.[/yellow] Nothing to sync."
        )
        return

    resolver = config.get_source_resolver()

    results: list[tuple[str, SyncResult]] = []

    for dep in config.dependencies:
        forced = _is_forced(dep, force_all, force_identifiers)
        # Targeted upgrade: skip untargeted deps before resolving or printing
        # anything, so `agr upgrade -g alpha` doesn't leak ralph-skip noise or
        # sibling resolve errors for deps the user didn't ask about.
        if force_identifiers is not None and not forced:
            continue
        try:
            handle, source_name = dep.resolve(
                config.default_source, config.default_owner
            )
            if dep.is_package:
                console.print(
                    f"[yellow]Skipped:[/yellow] {dep.identifier} "
                    "(packages are not supported in global installs)"
                )
                continue
            if dep.is_ralph:
                # Ralphs are project-level only; skip in global mode.
                console.print(
                    f"[yellow]Skipped:[/yellow] {dep.identifier} "
                    "(ralphs are not supported in global installs)"
                )
                continue
            result = _sync_one_dependency(
                handle,
                source_name,
                None,
                tools,
                resolver,
                skills_dirs,
                default_repo=config.default_repo,
                overwrite=forced,
            )
        except INSTALL_ERROR_TYPES as e:
            result = SyncResult.from_error(e)
        results.append((dep.identifier, result))

    _print_results_and_summary(results)


def _classify_dependencies(
    config: AgrConfig,
    repo_root: Path,
    tools: list[ToolConfig],
    *,
    force_all: bool = False,
    force_identifiers: set[str] | None = None,
) -> _ClassifiedDeps:
    """Classify dependencies into local, remote, and ralph install queues.

    Resolves each dependency and checks whether it is already installed.
    Up-to-date or errored entries are recorded directly in the results list;
    entries that need installation are placed into the appropriate pending queue.

    When ``force_all`` is True, every dep is pushed to the pending queue with
    ``overwrite=True`` regardless of its current install state. When
    ``force_identifiers`` is provided, only matching deps are forced.
    """
    results: list[SyncResult] = [SyncResult.pending() for _ in config.dependencies]
    pending_local: list[SyncEntry] = []
    pending_remote: list[SyncEntry] = []
    pending_ralph: list[SyncEntry] = []

    for index, dep in enumerate(config.dependencies):
        try:
            # Packages are content-less bundles — their transitive deps
            # have already been expanded into the deps list, so we mark
            # the package itself as up-to-date and skip installation.
            if dep.is_package:
                results[index] = SyncResult.up_to_date()
                continue

            handle, source_name = dep.resolve(
                config.default_source, config.default_owner
            )

            forced = _is_forced(dep, force_all, force_identifiers)

            # Targeted upgrade: skip non-forced deps entirely so `agr upgrade
            # alpha` never touches siblings (same repo or otherwise), even if
            # they're partially installed. Partial repair is `agr sync`'s job.
            if force_identifiers is not None and not forced:
                results[index] = SyncResult.up_to_date()
                continue

            if dep.is_ralph:
                # Ralphs are tool-agnostic: check project-level ralphs dir.
                if not forced and is_ralph_installed(handle, repo_root, source_name):
                    results[index] = SyncResult.up_to_date()
                    continue
                pending_ralph.append(
                    SyncEntry(
                        index=index,
                        handle=handle,
                        source_name=source_name,
                        overwrite=forced,
                    )
                )
            else:
                # Skills: check per-tool install status.
                if forced:
                    tools_needing_install = list(tools)
                else:
                    tools_needing_install = filter_tools_needing_install(
                        handle, repo_root, tools, source_name
                    )

                if not tools_needing_install:
                    results[index] = SyncResult.up_to_date()
                    continue

                entry = SyncEntry(
                    index=index,
                    handle=handle,
                    source_name=source_name,
                    tools_needing_install=tools_needing_install,
                    overwrite=forced,
                )
                if dep.is_local:
                    pending_local.append(entry)
                else:
                    pending_remote.append(entry)
        except INSTALL_ERROR_TYPES as e:
            results[index] = SyncResult.from_error(e)

    return _ClassifiedDeps(
        results=results,
        pending_local=pending_local,
        pending_remote=pending_remote,
        pending_ralph=pending_ralph,
    )


def run_sync(
    global_install: bool = False,
    frozen: bool = False,
    locked: bool = False,
) -> None:
    """Run the sync command.

    Installs all dependencies from agr.toml that aren't already installed.

    The sync flow has four stages:
    1. **Instruction sync** — copy the canonical instruction file (e.g.
       CLAUDE.md) to other tools' instruction files when enabled.
    2. **Migrations** — rename legacy skill directories to current naming
       conventions (colon → double-hyphen, full names → plain names).
    3. **Dependency install** — install missing skills, optimizing downloads
       by batching same-repo remotes into a single git clone.
    4. **Lockfile** — update agr.lock with resolved commit SHAs.
    5. **Report** — print per-dependency status and a summary line.

    Args:
        global_install: Use global ~/.agr/agr.toml.
        frozen: Install from lockfile exactly, fail if missing.
        locked: Fail if lockfile is out-of-date vs agr.toml.
    """
    console = get_console()

    if frozen and locked:
        error_exit("--frozen and --locked are mutually exclusive.")

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

    # Sync instruction files and run directory migrations before installing,
    # so existing installs are in the expected layout for duplicate detection.
    _run_pre_install_setup(repo_root, config, tools)

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow] Nothing to sync.")
        return

    resolver = config.get_source_resolver()

    # --- Lockfile handling ---
    lockfile_path = build_lockfile_path(config_path)
    existing_lockfile = load_lockfile(lockfile_path)

    if frozen or locked:
        if existing_lockfile is None:
            mode = "--frozen" if frozen else "--locked"
            error_exit(
                f"No agr.lock found. Cannot use {mode} without a lockfile.",
                hint="Run 'agr sync' first to generate a lockfile.",
            )
        if locked and not existing_lockfile.is_current(config.dependencies):
            error_exit(
                "agr.lock is out of date with agr.toml.",
                hint="Run 'agr sync' to update the lockfile.",
            )
        _sync_from_lockfile(existing_lockfile, config, repo_root, tools, resolver)
        return

    _run_install_pipeline(
        config,
        lockfile_path,
        repo_root,
        tools,
        resolver,
        existing_lockfile,
    )


def _run_install_pipeline(
    config: AgrConfig,
    lockfile_path: Path,
    repo_root: Path,
    tools: list[ToolConfig],
    resolver: SourceResolver,
    existing_lockfile: Lockfile | None,
    *,
    force_all: bool = False,
    force_identifiers: set[str] | None = None,
) -> None:
    """Shared by `run_sync` and `run_upgrade`: classify → install → lockfile → report."""
    # --- Phase 0: Expand packages into flat deps ---
    expanded: ExpandedDeps | None = None
    pkg_deps = [d for d in config.dependencies if d.is_package]
    if pkg_deps:
        expanded = expand_packages(
            config.dependencies,
            resolver,
            config.default_source,
            config.default_owner,
            config.default_repo,
        )
        direct_ids = {d.identifier for d in config.dependencies}
        expanded.dependencies = detect_conflicts(
            expanded.dependencies, expanded.parents, direct_ids
        )
        config = replace(config, dependencies=expanded.dependencies)

    # --- Phase 1: Classify dependencies ---
    classified = _classify_dependencies(
        config,
        repo_root,
        tools,
        force_all=force_all,
        force_identifiers=force_identifiers,
    )
    results = classified.results

    # --- Phase 2: Install pending dependencies ---
    # Skills: three categories processed separately for efficiency.
    #
    # 1. Local skills — no git download, just copy from the local path.
    _sync_individual_entries(
        classified.pending_local,
        results,
        repo_root,
        tools,
        resolver,
        default_repo=config.default_repo,
    )

    # 2. Default-repo remotes (two-part handles like "user/skill") — the
    #    repo name is unknown and must be discovered by trying candidates
    #    ("skills", "agent-resources"), so each must download individually.
    pending_remote_default = [
        e for e in classified.pending_remote if e.handle.repo is None
    ]
    pending_remote_specific = [
        e for e in classified.pending_remote if e.handle.repo is not None
    ]

    _sync_individual_entries(
        pending_remote_default,
        results,
        repo_root,
        tools,
        resolver,
        default_repo=config.default_repo,
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
        default_repo=config.default_repo,
    )

    # 4. Ralphs — installed to project-level .agents/ralphs/ directory.
    _sync_ralph_entries(
        classified.pending_ralph,
        results,
        repo_root,
        resolver,
        config.default_repo,
    )

    # --- Phase 3: Update lockfile ---
    package_entries = expanded.package_entries if expanded else []
    parents = expanded.parents if expanded else {}
    parent_sets = expanded.parent_sets if expanded else {}
    new_lockfile = _build_lockfile_from_results(
        config,
        results,
        existing_lockfile,
        package_entries=package_entries,
        parents=parents,
        parent_sets=parent_sets,
    )
    save_lockfile(new_lockfile, lockfile_path)

    # --- Phase 4: Report ---
    labeled_results = []
    for index, dep in enumerate(config.dependencies):
        label = dep.identifier
        parent = parents.get(dep.identifier)
        if parent:
            label = f"{label} (via {parent})"
        labeled_results.append((label, results[index]))
    _print_results_and_summary(labeled_results)


def _sync_dep_from_lockfile(
    dep: Dependency,
    lockfile: Lockfile,
    config: AgrConfig,
    repo_root: Path,
    tools: list[ToolConfig],
    resolver: SourceResolver,
) -> SyncResult:
    """Sync a single dependency using lockfile pins.

    Returns UP_TO_DATE when already installed, INSTALLED after a
    successful install.  Raises on failure so the caller can catch
    per-entry.
    """
    handle, source_name = dep.resolve(config.default_source, config.default_owner)
    is_ralph_dep = dep.is_ralph

    # Check installation status — initialise tools_needing_install
    # unconditionally so it is always bound regardless of code path.
    tools_needing_install: list[ToolConfig] = []

    if is_ralph_dep:
        if is_ralph_installed(handle, repo_root, source_name):
            return SyncResult.up_to_date()
    else:
        tools_needing_install = filter_tools_needing_install(
            handle, repo_root, tools, source_name
        )
        if not tools_needing_install:
            return SyncResult.up_to_date()

    # Local deps: install from disk (no lockfile commit needed)
    if dep.is_local:
        if is_ralph_dep:
            fetch_and_install_ralph(
                handle,
                repo_root,
                overwrite=False,
                resolver=resolver,
                source=source_name,
                default_repo=config.default_repo,
            )
        else:
            fetch_and_install_to_tools(
                handle,
                repo_root,
                tools_needing_install,
                overwrite=False,
                resolver=resolver,
                source=source_name,
                default_repo=config.default_repo,
            )
        return SyncResult.installed()

    # Remote deps: require a pinned commit
    locked_entry = lockfile.find_entry(dep)
    if locked_entry is None or locked_entry.commit is None:
        raise AgrError(
            f"No lockfile entry with commit for '{dep.identifier}'. "
            "Run 'agr sync' to update the lockfile."
        )

    # Clone the repo and checkout the pinned commit
    source_config = resolver.get(source_name or config.default_source)
    owner, repo_name = handle.get_github_repo(default_repo=config.default_repo)
    with downloaded_repo(source_config, owner, repo_name) as repo_dir:
        fetch_and_checkout_commit(repo_dir, locked_entry.commit)
        if is_ralph_dep:
            ralphs_dir = get_ralphs_dir(repo_root)
            install_ralph_from_repo(
                repo_dir,
                handle.name,
                handle,
                ralphs_dir,
                repo_root,
                overwrite=False,
                install_source=source_name,
            )
        else:
            install_skill_from_repo_to_tools(
                repo_dir,
                handle.name,
                handle,
                tools_needing_install,
                repo_root,
                overwrite=False,
                install_source=source_name,
            )
    return SyncResult.installed()


def _dep_from_locked_entry(entry: LockedEntry, kind: str) -> Dependency:
    """Build a dependency object from a lockfile entry."""
    if entry.path is not None:
        return Dependency(type=kind, path=entry.path, source=None)
    if entry.handle is not None:
        return Dependency(type=kind, handle=entry.handle, source=entry.source)
    raise AgrError("Lockfile entry is missing both handle and path")


def _package_closure(lockfile: Lockfile, package_ids: set[str]) -> set[str]:
    """Return package ids including nested packages whose parent is included."""
    all_pkg_ids = set(package_ids)
    changed = True
    while changed:
        changed = False
        for entry in lockfile.packages:
            if entry.parent_ids & all_pkg_ids and entry.identifier not in all_pkg_ids:
                all_pkg_ids.add(entry.identifier)
                changed = True
    return all_pkg_ids


def _locked_transitive_deps_for_packages(
    lockfile: Lockfile,
    package_ids: set[str],
) -> list[tuple[Dependency, str]]:
    """Return locked leaf dependencies whose parent chain belongs to packages."""
    all_pkg_ids = _package_closure(lockfile, package_ids)
    deps: list[tuple[Dependency, str]] = []
    for kind, entries in (("skill", lockfile.skills), ("ralph", lockfile.ralphs)):
        for entry in entries:
            matching_parents = entry.parent_ids & all_pkg_ids
            if matching_parents:
                deps.append(
                    (_dep_from_locked_entry(entry, kind), sorted(matching_parents)[0])
                )
    return deps


def _sync_from_lockfile(
    lockfile: Lockfile,
    config: AgrConfig,
    repo_root: Path,
    tools: list[ToolConfig],
    resolver: SourceResolver,
) -> None:
    """Install dependencies from lockfile pins (--frozen/--locked mode).

    For remote skills/ralphs with a pinned commit, clones the repo and checks
    out the exact commit. For local deps, installs from disk as usual.
    """
    results: list[tuple[str, SyncResult]] = []
    package_ids = {dep.identifier for dep in config.dependencies if dep.is_package}
    direct_ids = {
        (dep.type, dep.identifier) for dep in config.dependencies if not dep.is_package
    }

    for dep in config.dependencies:
        # Packages are content-less bundles — in frozen/locked mode
        # their transitive deps are installed from the lockfile below.
        if dep.is_package:
            results.append((dep.identifier, SyncResult.up_to_date()))
            continue
        try:
            result = _sync_dep_from_lockfile(
                dep, lockfile, config, repo_root, tools, resolver
            )
        except INSTALL_ERROR_TYPES as e:
            result = SyncResult.from_error(e)
        results.append((dep.identifier, result))

    for dep, parent in _locked_transitive_deps_for_packages(lockfile, package_ids):
        dep_key = (dep.type, dep.identifier)
        if dep_key in direct_ids:
            continue
        try:
            result = _sync_dep_from_lockfile(
                dep, lockfile, config, repo_root, tools, resolver
            )
        except INSTALL_ERROR_TYPES as e:
            result = SyncResult.from_error(e)
        results.append((f"{dep.identifier} (via {parent})", result))

    _print_results_and_summary(results)


def _build_lockfile_from_results(
    config: AgrConfig,
    results: list[SyncResult],
    existing_lockfile: Lockfile | None,
    *,
    package_entries: list[LockedEntry] | None = None,
    parents: dict[str, str] | None = None,
    parent_sets: dict[str, set[str]] | None = None,
) -> Lockfile:
    """Build a new lockfile from sync results.

    For freshly installed skills/ralphs, uses commit/hash from SyncResult.
    For up-to-date entries, carries forward existing lockfile entries.
    """
    lockfile = Lockfile()
    parent_map = parents or {}
    parent_set_map = parent_sets or {}

    for index, dep in enumerate(config.dependencies):
        result = results[index]
        dep_kind = dep.type
        name = dep.installed_name
        parent_ids = parent_set_map.get(dep.identifier)
        parent = parent_map.get(dep.identifier)
        current_parent_ids = parent_ids or ({parent} if parent else set())
        lock_parent, lock_parents = normalize_parent_ids(current_parent_ids)

        # Packages are content-less bundles — skip them in skill/ralph lists.
        if dep.is_package:
            continue

        # Local deps: record path only (no commit to pin).
        if dep.is_local:
            if result.status == SyncStatus.ERROR:
                continue
            lockfile.update_entry(
                LockedEntry(
                    path=dep.path,
                    installed_name=name,
                    parent=lock_parent,
                    parents=lock_parents,
                ),
                kind=dep_kind,
            )
            continue

        # Remote: freshly installed — record new metadata. When commit
        # capture failed (result.commit is None), we still drop the old
        # lockfile entry rather than carrying a stale commit forward.
        if result.status == SyncStatus.INSTALLED:
            lockfile.update_entry(
                LockedEntry(
                    handle=dep.handle,
                    source=result.source_name,
                    commit=result.commit,
                    content_hash=result.content_hash,
                    installed_name=name,
                    parent=lock_parent,
                    parents=lock_parents,
                ),
                kind=dep_kind,
            )
            continue

        # Remote, not freshly installed: carry forward existing lockfile entry.
        # Update the parent field to reflect the current dependency graph
        # (e.g. a transitive dep promoted to direct must drop its parent).
        existing = (
            existing_lockfile.find_entry(dep) if existing_lockfile is not None else None
        )
        if existing is not None:
            if existing.parent_ids != current_parent_ids:
                existing = replace(existing, parent=lock_parent, parents=lock_parents)
            lockfile.update_entry(existing, kind=dep_kind)
            continue

        # No existing entry for a failed dep — nothing to record.
        if result.status == SyncStatus.ERROR:
            continue

        # Up-to-date with no prior lockfile entry (e.g. first sync after
        # adding to agr.toml) — record a minimal entry without commit.
        lockfile.update_entry(
            LockedEntry(
                handle=dep.handle,
                source=dep.resolve_source_name(config.default_source),
                installed_name=name,
                parent=lock_parent,
                parents=lock_parents,
            ),
            kind=dep_kind,
        )

    # Append package entries from expansion.
    for entry in package_entries or []:
        lockfile.update_entry(entry, kind="package")

    return lockfile
