"""agr upgrade command implementation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agr.commands._tool_helpers import load_existing_config
from agr.commands.sync import (
    _run_global_sync,
    _run_install_pipeline,
    _run_pre_install_setup,
)
from agr.config import AgrConfig, find_config, require_repo_root
from agr.console import error_exit, get_console
from agr.exceptions import AgrError
from agr.lockfile import Lockfile, build_lockfile_path, load_lockfile

if TYPE_CHECKING:
    from agr.config import Dependency


def run_upgrade(handles: list[str], global_install: bool = False) -> None:
    """Re-install dependencies (latest upstream commit for remotes, fresh copy for local) and refresh agr.lock."""
    if global_install:
        _run_global_upgrade(handles)
        return

    console = get_console()
    repo_root = require_repo_root()
    config_path = find_config()
    if config_path is None:
        console.print("[yellow]No agr.toml found.[/yellow] Nothing to upgrade.")
        return

    config = AgrConfig.load(config_path)
    tools = config.get_tools()

    # Resolve handles BEFORE the empty-deps early return so that
    # `agr upgrade typo` on an empty agr.toml errors cleanly instead of
    # masquerading as success.
    force_identifiers: set[str] | None = None
    if handles:
        matched = _match_handles(handles, config.dependencies, scope_label="agr.toml")
        force_identifiers = {dep.identifier for dep in matched}

        # When upgrading a package, also force-upgrade its transitive deps.
        lockfile_path = build_lockfile_path(config_path)
        existing_lf = load_lockfile(lockfile_path)
        pkg_ids = {dep.identifier for dep in matched if dep.is_package}
        if pkg_ids and existing_lf:
            force_identifiers |= _transitive_closure(existing_lf, pkg_ids)

    # Instruction sync + migrations run before the empty-deps check, matching
    # `run_sync`, so an empty-deps upgrade still refreshes instruction files.
    _run_pre_install_setup(repo_root, config, tools)

    if not config.dependencies:
        console.print(
            "[yellow]No dependencies in agr.toml.[/yellow] Nothing to upgrade."
        )
        return

    resolver = config.get_source_resolver()
    lockfile_path = build_lockfile_path(config_path)
    existing_lockfile = load_lockfile(lockfile_path)

    _run_install_pipeline(
        config,
        lockfile_path,
        repo_root,
        tools,
        resolver,
        existing_lockfile,
        force_all=not handles,
        force_identifiers=force_identifiers,
    )


def _run_global_upgrade(handles: list[str]) -> None:
    if not handles:
        _run_global_sync(force_all=True)
        return

    loaded = load_existing_config(global_install=True, missing_ok=True)
    if loaded is None:
        # Handles were supplied but there's no global config to look them up
        # in — exit non-zero instead of masquerading as success.
        error_exit(f"No global agr.toml found. Cannot upgrade: {', '.join(handles)}.")

    matched = _match_handles(
        handles, loaded.config.dependencies, scope_label="global agr.toml"
    )
    ralphs = [dep for dep in matched if dep.is_ralph]
    if ralphs:
        names = ", ".join(d.identifier for d in ralphs)
        error_exit(
            f"Ralphs cannot be upgraded in global mode: {names}. "
            "Ralphs are project-level only."
        )
    force_identifiers = {dep.identifier for dep in matched}
    _run_global_sync(force_identifiers=force_identifiers)


def _match_handles(
    args: list[str], deps: list[Dependency], *, scope_label: str
) -> list[Dependency]:
    """Collect all per-arg errors before exiting so `agr upgrade typo1 typo2` reports both."""
    matched: list[Dependency] = []
    errors: list[str] = []
    for arg in args:
        try:
            matched.append(_match_handle_to_dep(arg, deps, scope_label=scope_label))
        except AgrError as exc:
            errors.append(str(exc))
    if errors:
        error_exit("\n".join(errors))
    return matched


def _match_handle_to_dep(
    arg: str, deps: list[Dependency], *, scope_label: str = "agr.toml"
) -> Dependency:
    target = _normalize_handle(arg)
    matches: list[Dependency] = []
    for dep in deps:
        if _normalize_handle(dep.identifier) == target:
            matches.append(dep)
            continue
        if dep.installed_name == arg.rstrip("/"):
            matches.append(dep)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AgrError(
            f"'{arg}' is ambiguous — multiple deps match: "
            + ", ".join(d.identifier for d in matches)
            + ". Specify the full identifier."
        )
    raise AgrError(f"'{arg}' is not in {scope_label}.")


def _normalize_handle(s: str) -> str:
    if not s:
        return s
    # Path-like inputs get POSIX-normalised (collapses `./`, `//`, etc.) so
    # `./foo`, `foo/`, and `./foo/` all compare equal. Remote handles and
    # bare short names are only stripped of surrounding slashes.
    if s.startswith((".", "~", "/")):
        return Path(s).expanduser().as_posix().strip("/")
    return s.strip("/")


def _transitive_closure(lockfile: Lockfile, package_ids: set[str]) -> set[str]:
    """Collect all lockfile entry identifiers whose parent chain includes *package_ids*.

    This lets ``agr upgrade <package>`` force-upgrade the entire
    transitive dependency tree, not just the package entry itself.
    Nested packages are expanded first so that skills/ralphs from
    sub-packages are included.
    """
    # Expand package_ids to include nested child packages.
    all_pkg_ids = set(package_ids)
    changed = True
    while changed:
        changed = False
        for entry in lockfile.packages:
            if entry.parent_ids & all_pkg_ids and entry.identifier not in all_pkg_ids:
                all_pkg_ids.add(entry.identifier)
                changed = True

    result: set[str] = set()
    for entry in lockfile.installed_entries():
        if entry.parent_ids & all_pkg_ids:
            result.add(entry.identifier)
    return result
