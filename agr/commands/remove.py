"""agr remove command implementation."""

from pathlib import Path

from agr.commands import CommandResult
from agr.commands.migrations import run_tool_migrations
from agr.config import (
    AgrConfig,
    find_config,
    get_global_config_path,
    require_repo_root,
)
from agr.console import get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.fetcher import uninstall_skill
from agr.handle import ParsedHandle, parse_handle
from agr.tool import build_global_skills_dirs


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
    seen: set[str] = set()
    candidates: list[str] = []

    def _add(value: str) -> None:
        if value not in seen:
            seen.add(value)
            candidates.append(value)

    _add(ref)
    if handle.is_local and handle.local_path is not None:
        _add(str(handle.local_path))
    if abs_path_str is not None:
        _add(abs_path_str)
    if not handle.is_local:
        _add(handle.to_toml_handle())
    return candidates


def run_remove(refs: list[str], global_install: bool = False) -> None:
    """Run the remove command.

    Args:
        refs: List of handles or paths to remove
    """
    console = get_console()
    skills_dirs: dict[str, Path] | None = None
    if global_install:
        repo_root = None
        config_path = get_global_config_path()
        if not config_path.exists():
            print_error("No global agr.toml found")
            console.print("[dim]Run 'agr add -g <handle>' first.[/dim]")
            raise SystemExit(1)
    else:
        repo_root = require_repo_root()

        # Find config
        config_path = find_config()
        if config_path is None:
            print_error("No agr.toml found")
            raise SystemExit(1)

    config = AgrConfig.load(config_path)

    # Get configured tools
    tools = config.get_tools()
    if global_install:
        skills_dirs = build_global_skills_dirs(tools)
    run_tool_migrations(tools, repo_root, global_install=global_install)

    # Track results
    results: list[CommandResult] = []

    for ref in refs:
        try:
            # Parse handle
            handle = parse_handle(ref)

            # Compute the resolved absolute path once for local global installs
            abs_path_str: str | None = None
            if global_install and handle.is_local and handle.local_path is not None:
                abs_path_str = str(handle.resolve_local_path())

            candidates = _identifier_candidates(ref, handle, abs_path_str)

            dep = None
            for identifier in candidates:
                dep = config.get_by_identifier(identifier)
                if dep is not None:
                    break

            source_name = None
            if dep and dep.is_remote:
                source_name = dep.source or config.default_source

            # Remove from filesystem for all configured tools
            removed_fs = False
            for tool in tools:
                target_skills_dir = (
                    skills_dirs.get(tool.name) if skills_dirs is not None else None
                )
                if uninstall_skill(
                    handle,
                    repo_root,
                    tool,
                    source_name,
                    skills_dir=target_skills_dir,
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
            else:
                results.append(CommandResult(ref, False, "Not found"))

        except INSTALL_ERROR_TYPES as e:
            results.append(CommandResult(ref, False, format_install_error(e)))

    # Save config if any changes
    successes = [r for r in results if r.success]
    if successes:
        config.save(config_path)

    # Print results
    for result in results:
        if result.success:
            console.print(f"[green]Removed:[/green] {result.ref}")
        elif result.message == "Not found":
            console.print(f"[yellow]Not found:[/yellow] {result.ref}")
        else:
            print_error(result.ref)
            console.print(f"  [dim]{result.message}[/dim]")

    # Summary
    if len(refs) > 1:
        console.print()
        console.print(
            f"[bold]Summary:[/bold] {len(successes)}/{len(refs)} skills removed"
        )
