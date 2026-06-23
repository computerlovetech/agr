"""agr remove command implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agr.commands import CommandResult
from agr.commands._tool_helpers import load_existing_config, save_and_summarize_results
from agr.config import (
    DEPENDENCY_TYPE_PACKAGE,
    DEPENDENCY_TYPE_RALPH,
    DEPENDENCY_TYPE_SKILL,
    AgrConfig,
    Dependency,
)
from agr.commands.migrations import run_tool_migrations
from agr.console import get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.ralph_installer import uninstall_ralph
from agr.skill_installer import uninstall_skill
from agr.handle import LOCAL_PATH_PREFIXES, ParsedHandle, parse_handle
from agr.lockfile import (
    Lockfile,
    LockedEntry,
    build_lockfile_path,
    load_lockfile,
    normalize_parent_ids,
    save_lockfile,
)
from agr.tool import ToolConfig, lookup_skills_dir


def _print_remove_result(result: CommandResult) -> None:
    """Print a styled result line for a single remove operation."""
    console = get_console()
    if result.success:
        console.print(f"[green]Removed:[/green] {result.ref}")
    elif result.message == "Not found":
        console.print(f"[yellow]Not found:[/yellow] {result.ref}")
    else:
        print_error(result.ref)
        console.print(f"  [dim]{result.message}[/dim]", soft_wrap=True)


def _uninstall_from_filesystem(
    handle: ParsedHandle,
    is_ralph: bool,
    tools: list[ToolConfig],
    repo_root: Path | None,
    source_name: str | None,
    skills_dirs: dict[str, Path] | None,
    default_repo: str | None = None,
) -> bool:
    """Remove a dependency from the filesystem.

    For ralphs, removes from the project-level ralphs directory.
    For skills, removes from all configured tools.

    Returns True if anything was removed.
    """
    if is_ralph:
        return uninstall_ralph(
            handle, repo_root, source_name, default_repo=default_repo
        )
    removed = False
    for tool in tools:
        if uninstall_skill(
            handle,
            repo_root,
            tool,
            source_name,
            skills_dir=lookup_skills_dir(skills_dirs, tool),
            default_repo=default_repo,
        ):
            removed = True
    return removed


def _transitive_leaf_entries_for_packages(
    lockfile: Lockfile | None,
    package_ids: set[str],
) -> list[tuple[str, LockedEntry]]:
    """Return lockfile leaf entries whose parent chain belongs to packages."""
    if lockfile is None:
        return []
    all_pkg_ids = lockfile.package_closure(package_ids)
    entries: list[tuple[str, LockedEntry]] = []
    for kind, locked_entries in (
        (DEPENDENCY_TYPE_SKILL, lockfile.skills),
        (DEPENDENCY_TYPE_RALPH, lockfile.ralphs),
    ):
        for entry in locked_entries:
            if entry.parent_ids & all_pkg_ids:
                entries.append((kind, entry))
    return entries


def _nested_package_entries_for_packages(
    lockfile: Lockfile | None,
    package_ids: set[str],
) -> list[tuple[str, LockedEntry]]:
    """Return nested package entries whose parent chain belongs to packages."""
    if lockfile is None:
        return []
    all_pkg_ids = lockfile.package_closure(package_ids)
    return [
        (DEPENDENCY_TYPE_PACKAGE, entry)
        for entry in lockfile.packages
        if entry.identifier not in package_ids and entry.identifier in all_pkg_ids
    ]


def _entry_to_handle(
    entry: LockedEntry, kind: str, default_owner: str | None
) -> ParsedHandle:
    """Convert a lockfile entry into a parsed handle for filesystem removal."""
    dep = (
        Dependency(type=kind, path=entry.path)
        if entry.path is not None
        else Dependency(type=kind, handle=entry.handle, source=entry.source)
    )
    return dep.to_parsed_handle(default_owner)


def _update_lockfile_after_remove(
    config_path: Path,
    removed_candidates: list[list[str]],
    removed_kinds: list[str],
) -> None:
    """Remove entries from the lockfile for successfully removed deps."""
    if not removed_candidates:
        return
    lockfile_path = build_lockfile_path(config_path)
    lockfile = load_lockfile(lockfile_path)
    if lockfile is None:
        return
    removed_package_ids: set[str] = set()
    for candidates, dep_kind in zip(removed_candidates, removed_kinds):
        for identifier in candidates:
            if lockfile.remove_entry(identifier, kind=dep_kind):
                if dep_kind == DEPENDENCY_TYPE_PACKAGE:
                    removed_package_ids.add(identifier)
                break
    if removed_package_ids:
        for entry in [*lockfile.packages, *lockfile.skills, *lockfile.ralphs]:
            parent_ids = entry.parent_ids - removed_package_ids
            entry.parent, entry.parents = normalize_parent_ids(parent_ids)
    save_lockfile(lockfile, lockfile_path)


def _identifier_candidates(
    ref: str,
    handle: ParsedHandle,
    abs_path_str: str | None,
) -> list[str]:
    """Build ordered list of identifiers to try for dependency lookup/removal.

    Dependencies can be stored under different identifier forms (raw ref,
    local path string, resolved absolute path, or TOML handle).  This
    helper produces the candidates in priority order so callers can stop
    at the first match.
    """
    candidates = [ref]
    if handle.is_local and handle.local_path is not None:
        candidates.append(str(handle.local_path))
    if abs_path_str is not None:
        candidates.append(abs_path_str)
    if not handle.is_local:
        candidates.append(handle.to_toml_handle())
    # Local paths may be stored with a "./" prefix in agr.toml (e.g.
    # ``agr add ./my-skill`` writes ``path = "./my-skill"``).  When the
    # user omits the prefix (``agr remove my-skill``), add the "./" form
    # so we can still match the config entry.
    if not ref.startswith(LOCAL_PATH_PREFIXES + ("~",)):
        candidates.append(f"./{ref}")
    return list(dict.fromkeys(candidates))


def _find_dep_by_candidates(
    candidates: list[str],
    ref: str,
    dependencies: list[Dependency],
) -> Dependency | None:
    """Find a dependency by identifier candidates, falling back to installed_name.

    First tries each candidate against ``Dependency.identifier`` (exact
    match).  If no identifier matches, falls back to matching the bare
    *ref* (with trailing slashes stripped) against
    ``Dependency.installed_name`` — the last component of the handle.

    This fallback mirrors the behaviour of ``_match_handle_to_dep`` in
    the upgrade command, so ``agr remove skill`` works the same as
    ``agr upgrade skill`` for three-part handles like
    ``owner/repo/skill``.
    """
    for identifier in candidates:
        for dep in dependencies:
            if dep.identifier == identifier:
                return dep

    # Fallback: match by installed_name (last segment of the handle).
    bare = ref.rstrip("/")
    for dep in dependencies:
        if dep.installed_name == bare:
            return dep

    return None


@dataclass
class _RefRemoval:
    """Outcome of processing a single ref in ``run_remove``.

    ``removed_candidates`` / ``removed_kinds`` are parallel lists describing
    every lockfile entry that should be dropped as a result of this ref
    (the dep itself plus any transitive/nested children), in the same shape
    ``_update_lockfile_after_remove`` consumes.
    """

    result: CommandResult
    removed_candidates: list[list[str]] = field(default_factory=list)
    removed_kinds: list[str] = field(default_factory=list)


def _nested_packages_to_remove(
    dep: Dependency,
    existing_lockfile: Lockfile | None,
) -> list[tuple[str, LockedEntry]]:
    """Nested package entries whose whole parent chain lives inside ``dep``."""
    candidate_package_ids = (
        existing_lockfile.package_closure({dep.identifier})
        if existing_lockfile
        else {dep.identifier}
    )
    return [
        (kind, entry)
        for kind, entry in _nested_package_entries_for_packages(
            existing_lockfile, {dep.identifier}
        )
        if not (entry.parent_ids - candidate_package_ids)
    ]


def _transitive_leaves_to_remove(
    dep: Dependency,
    config: AgrConfig,
    existing_lockfile: Lockfile | None,
    nested_package_entries: list[tuple[str, LockedEntry]],
) -> list[tuple[str, LockedEntry]]:
    """Transitive leaf entries to remove, excluding ones still directly required.

    A leaf is removed only when it is not a direct dependency and its entire
    parent chain lives inside the package being removed (plus the nested
    packages also being removed).
    """
    direct_leaf_ids = {
        (d.type, d.identifier)
        for d in config.dependencies
        if not d.is_package and d.identifier != dep.identifier
    }
    removed_package_ids = {dep.identifier} | {
        entry.identifier for _kind, entry in nested_package_entries
    }
    return [
        (kind, entry)
        for kind, entry in _transitive_leaf_entries_for_packages(
            existing_lockfile, {dep.identifier}
        )
        if (kind, entry.identifier) not in direct_leaf_ids
        and not (entry.parent_ids - removed_package_ids)
    ]


def _resolve_package_cleanup(
    dep: Dependency,
    config: AgrConfig,
    existing_lockfile: Lockfile | None,
) -> tuple[list[tuple[str, LockedEntry]], list[tuple[str, LockedEntry]]]:
    """Resolve the nested-package and transitive-leaf entries to remove for a package.

    Returns ``(nested_package_entries, transitive_entries)``.  A child is
    only scheduled for removal when its entire parent chain lives inside the
    package being removed (so children still required by another package are
    retained).
    """
    nested_package_entries = _nested_packages_to_remove(dep, existing_lockfile)
    transitive_entries = _transitive_leaves_to_remove(
        dep, config, existing_lockfile, nested_package_entries
    )
    return nested_package_entries, transitive_entries


def _uninstall_transitive_entries(
    transitive_entries: list[tuple[str, LockedEntry]],
    config: AgrConfig,
    tools: list[ToolConfig],
    repo_root: Path | None,
    skills_dirs: dict[str, Path] | None,
) -> bool:
    """Filesystem-remove each transitive child entry. Returns True if any removed."""
    removed = False
    for kind, entry in transitive_entries:
        child_handle = _entry_to_handle(entry, kind, config.default_owner)
        if _uninstall_from_filesystem(
            child_handle,
            kind == DEPENDENCY_TYPE_RALPH,
            tools,
            repo_root,
            entry.source,
            skills_dirs,
            default_repo=config.default_repo,
        ):
            removed = True
    return removed


def _resolve_dep(
    ref: str,
    config: AgrConfig,
    global_install: bool,
) -> tuple[ParsedHandle, list[str], Dependency | None]:
    """Resolve a ref to its handle, identifier candidates, and matching dependency."""
    handle = parse_handle(ref, default_owner=config.default_owner)

    # Compute the resolved absolute path once for local global installs.
    abs_path_str: str | None = None
    if global_install and handle.is_local and handle.local_path is not None:
        abs_path_str = str(handle.resolve_local_path())

    candidates = _identifier_candidates(ref, handle, abs_path_str)
    dep = _find_dep_by_candidates(candidates, ref, config.dependencies)

    # When the dep was found by installed_name fallback (not by any candidate
    # identifier), its actual identifier must be added so that config and
    # lockfile removal can match it.
    if dep is not None and dep.identifier not in candidates:
        candidates.append(dep.identifier)

    return handle, candidates, dep


def _remove_leaf_from_filesystem(
    dep: Dependency | None,
    handle: ParsedHandle,
    config: AgrConfig,
    tools: list[ToolConfig],
    repo_root: Path | None,
    skills_dirs: dict[str, Path] | None,
) -> bool:
    """Filesystem-remove a non-package dependency (skill or ralph)."""
    source_name = None
    if dep and dep.is_remote:
        source_name = dep.source or config.default_source
    is_ralph = dep is not None and dep.is_ralph
    fs_handle = dep.to_parsed_handle(config.default_owner) if dep else handle
    return _uninstall_from_filesystem(
        fs_handle,
        is_ralph,
        tools,
        repo_root,
        source_name,
        skills_dirs,
        default_repo=config.default_repo,
    )


def _remove_from_filesystem(
    dep: Dependency | None,
    handle: ParsedHandle,
    config: AgrConfig,
    tools: list[ToolConfig],
    repo_root: Path | None,
    skills_dirs: dict[str, Path] | None,
    existing_lockfile: Lockfile | None,
) -> tuple[bool, list[tuple[str, LockedEntry]], list[tuple[str, LockedEntry]]]:
    """Filesystem-remove a dependency, fanning out to package children when needed.

    Returns ``(removed_anything, nested_package_entries, transitive_entries)``.
    Packages have no filesystem footprint of their own; only their transitive
    children are removed.
    """
    if dep is not None and dep.is_package:
        nested, transitive = _resolve_package_cleanup(dep, config, existing_lockfile)
        removed = _uninstall_transitive_entries(
            transitive, config, tools, repo_root, skills_dirs
        )
        return removed, nested, transitive
    removed = _remove_leaf_from_filesystem(
        dep, handle, config, tools, repo_root, skills_dirs
    )
    return removed, [], []


def _remove_from_config(config: AgrConfig, candidates: list[str]) -> bool:
    """Remove the first matching candidate identifier from the config."""
    for identifier in candidates:
        if config.remove_dependency(identifier):
            return True
    return False


def _build_removal(
    ref: str,
    dep: Dependency | None,
    candidates: list[str],
    nested_package_entries: list[tuple[str, LockedEntry]],
    transitive_entries: list[tuple[str, LockedEntry]],
) -> _RefRemoval:
    """Assemble a successful ``_RefRemoval`` with the lockfile entries to drop."""
    dep_kind = dep.type if dep is not None else DEPENDENCY_TYPE_SKILL
    removal = _RefRemoval(
        CommandResult(ref, True, "Removed"),
        removed_candidates=[candidates],
        removed_kinds=[dep_kind],
    )
    for kind, entry in (*nested_package_entries, *transitive_entries):
        removal.removed_candidates.append([entry.identifier])
        removal.removed_kinds.append(kind)
    return removal


def _process_ref(
    ref: str,
    config: AgrConfig,
    tools: list[ToolConfig],
    repo_root: Path | None,
    skills_dirs: dict[str, Path] | None,
    existing_lockfile: Lockfile | None,
    global_install: bool,
) -> _RefRemoval:
    """Process a single remove ref: resolve, uninstall, and report the outcome.

    Performs filesystem removal and config removal for one ref (plus any
    transitive/nested package children), returning a ``_RefRemoval`` whose
    parallel candidate/kind lists feed ``_update_lockfile_after_remove``.
    Install errors are caught and surfaced as a failed ``CommandResult``.
    """
    try:
        handle, candidates, dep = _resolve_dep(ref, config, global_install)
        removed_fs, nested, transitive = _remove_from_filesystem(
            dep, handle, config, tools, repo_root, skills_dirs, existing_lockfile
        )
        removed_config = _remove_from_config(config, candidates)
        if not (removed_fs or removed_config):
            return _RefRemoval(CommandResult(ref, False, "Not found"))
        return _build_removal(ref, dep, candidates, nested, transitive)
    except INSTALL_ERROR_TYPES as e:
        return _RefRemoval(CommandResult(ref, False, format_install_error(e)))


def run_remove(refs: list[str], global_install: bool = False) -> None:
    """Run the remove command.

    Args:
        refs: List of handles or paths to remove
    """
    loaded = load_existing_config(global_install)
    config, config_path = loaded.config, loaded.config_path
    tools, repo_root, skills_dirs = loaded.tools, loaded.repo_root, loaded.skills_dirs
    run_tool_migrations(tools, repo_root, global_install=global_install)
    existing_lockfile = load_lockfile(build_lockfile_path(config_path))

    # Track results and the identifier candidates used for each successful
    # removal so we can update the lockfile without re-parsing handles.
    results: list[CommandResult] = []
    removed_candidates: list[list[str]] = []
    removed_kinds: list[str] = []

    for ref in refs:
        removal = _process_ref(
            ref,
            config,
            tools,
            repo_root,
            skills_dirs,
            existing_lockfile,
            global_install,
        )
        results.append(removal.result)
        removed_candidates.extend(removal.removed_candidates)
        removed_kinds.extend(removal.removed_kinds)

    save_and_summarize_results(
        results,
        config,
        config_path,
        action="removed",
        total=len(refs),
        print_result=_print_remove_result,
        exit_on_failure=False,
    )

    _update_lockfile_after_remove(config_path, removed_candidates, removed_kinds)
