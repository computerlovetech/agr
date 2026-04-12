"""agr remove command implementation."""

from __future__ import annotations

from pathlib import Path

from agr.commands import CommandResult
from agr.commands._tool_helpers import load_existing_config, save_and_summarize_results
from agr.config import Dependency
from agr.commands.migrations import run_tool_migrations
from agr.console import get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.ralph_installer import uninstall_ralph
from agr.skill_installer import uninstall_skill
from agr.handle import ParsedHandle, parse_handle
from agr.lockfile import (
    Lockfile,
    LockedEntry,
    build_lockfile_path,
    load_lockfile,
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
) -> bool:
    """Remove a dependency from the filesystem.

    For ralphs, removes from the project-level ralphs directory.
    For skills, removes from all configured tools.

    Returns True if anything was removed.
    """
    if is_ralph:
        return uninstall_ralph(handle, repo_root, source_name)
    removed = False
    for tool in tools:
        if uninstall_skill(
            handle,
            repo_root,
            tool,
            source_name,
            skills_dir=lookup_skills_dir(skills_dirs, tool),
        ):
            removed = True
    return removed


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


def _transitive_leaf_entries_for_packages(
    lockfile: Lockfile | None,
    package_ids: set[str],
) -> list[tuple[str, LockedEntry]]:
    """Return lockfile leaf entries whose parent chain belongs to packages."""
    if lockfile is None:
        return []
    all_pkg_ids = _package_closure(lockfile, package_ids)
    entries: list[tuple[str, LockedEntry]] = []
    for kind, locked_entries in (
        ("skill", lockfile.skills),
        ("ralph", lockfile.ralphs),
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
    all_pkg_ids = _package_closure(lockfile, package_ids)
    return [
        ("package", entry)
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
                if dep_kind == "package":
                    removed_package_ids.add(identifier)
                break
    if removed_package_ids:
        for entry in [*lockfile.packages, *lockfile.skills, *lockfile.ralphs]:
            parent_ids = entry.parent_ids - removed_package_ids
            if not parent_ids:
                entry.parent = None
                entry.parents = None
            elif len(parent_ids) == 1:
                entry.parent = next(iter(parent_ids))
                entry.parents = None
            else:
                entry.parent = None
                entry.parents = sorted(parent_ids)
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
    if not ref.startswith(("./", "../", "/", "~")):
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
        try:
            # Parse handle
            handle = parse_handle(ref, default_owner=config.default_owner)

            # Compute the resolved absolute path once for local global installs
            abs_path_str: str | None = None
            if global_install and handle.is_local and handle.local_path is not None:
                abs_path_str = str(handle.resolve_local_path())

            candidates = _identifier_candidates(ref, handle, abs_path_str)

            dep = _find_dep_by_candidates(candidates, ref, config.dependencies)

            # When the dep was found by installed_name fallback (not by
            # any candidate identifier), its actual identifier must be
            # added to candidates so that config and lockfile removal
            # can match it.
            if dep is not None and dep.identifier not in candidates:
                candidates.append(dep.identifier)

            source_name = None
            if dep and dep.is_remote:
                source_name = dep.source or config.default_source

            is_ralph = dep is not None and dep.is_ralph
            dep_kind = dep.type if dep is not None else "skill"
            fs_handle = dep.to_parsed_handle(config.default_owner) if dep else handle

            # Remove from filesystem
            removed_fs = False
            if dep is None or not dep.is_package:
                removed_fs = _uninstall_from_filesystem(
                    fs_handle, is_ralph, tools, repo_root, source_name, skills_dirs
                )

            transitive_entries: list[tuple[str, LockedEntry]] = []
            nested_package_entries: list[tuple[str, LockedEntry]] = []
            if dep is not None and dep.is_package:
                direct_leaf_ids = {
                    (d.type, d.identifier)
                    for d in config.dependencies
                    if not d.is_package and d.identifier != dep.identifier
                }
                candidate_package_ids = (
                    _package_closure(existing_lockfile, {dep.identifier})
                    if existing_lockfile
                    else {dep.identifier}
                )
                nested_package_entries = [
                    (kind, entry)
                    for kind, entry in _nested_package_entries_for_packages(
                        existing_lockfile, {dep.identifier}
                    )
                    if not (entry.parent_ids - candidate_package_ids)
                ]
                removed_package_ids = {dep.identifier} | {
                    entry.identifier for _kind, entry in nested_package_entries
                }
                transitive_entries = [
                    (kind, entry)
                    for kind, entry in _transitive_leaf_entries_for_packages(
                        existing_lockfile, {dep.identifier}
                    )
                    if (kind, entry.identifier) not in direct_leaf_ids
                    and not (entry.parent_ids - removed_package_ids)
                ]
                for kind, entry in transitive_entries:
                    child_handle = _entry_to_handle(entry, kind, config.default_owner)
                    if _uninstall_from_filesystem(
                        child_handle,
                        kind == "ralph",
                        tools,
                        repo_root,
                        entry.source,
                        skills_dirs,
                    ):
                        removed_fs = True

            # Remove from config (try same candidate identifiers)
            removed_config = False
            for identifier in candidates:
                if config.remove_dependency(identifier):
                    removed_config = True
                    break

            if removed_fs or removed_config:
                results.append(CommandResult(ref, True, "Removed"))
                removed_candidates.append(candidates)
                removed_kinds.append(dep_kind)
                for kind, entry in nested_package_entries:
                    removed_candidates.append([entry.identifier])
                    removed_kinds.append(kind)
                for kind, entry in transitive_entries:
                    removed_candidates.append([entry.identifier])
                    removed_kinds.append(kind)
            else:
                results.append(CommandResult(ref, False, "Not found"))

        except INSTALL_ERROR_TYPES as e:
            results.append(CommandResult(ref, False, format_install_error(e)))

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
