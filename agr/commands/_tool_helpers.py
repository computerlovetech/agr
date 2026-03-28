"""Shared helpers for tool-management commands.

These utilities are used by both the unified config commands (config_cmd.py)
and the deprecated tool commands (tools.py).
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Literal, overload

from agr.commands import CommandResult
from agr.config import (
    CONFIG_FILENAME,
    AgrConfig,
    find_config,
    find_repo_root,
    get_global_config_path,
    get_or_create_global_config,
    require_repo_root,
)
from agr.console import error_exit, get_console, print_error
from agr.detect import detect_tools
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.fetcher import fetch_and_install_to_tools, filter_tools_needing_install
from agr.tool import TOOLS, ToolConfig, available_tools_string, build_global_skills_dirs


@dataclass
class LoadedConfig:
    """Result of loading an agr config for a command."""

    config: AgrConfig
    config_path: Path
    tools: list[ToolConfig]
    repo_root: Path | None
    skills_dirs: dict[str, Path] | None


def print_missing_config_hint(global_install: bool) -> None:
    """Print the standard 'no agr.toml found' message with a hint to create one."""
    console = get_console()
    if global_install:
        console.print("[yellow]No global agr.toml found.[/yellow]")
        console.print("[dim]Run 'agr add -g <handle>' to create one.[/dim]")
    else:
        console.print("[yellow]No agr.toml found.[/yellow]")
        console.print("[dim]Run 'agr init' to create one.[/dim]")


@overload
def load_existing_config(
    global_install: bool,
    *,
    missing_ok: Literal[True],
    create_if_missing: bool = ...,
) -> LoadedConfig | None: ...


@overload
def load_existing_config(
    global_install: bool,
    *,
    missing_ok: bool = ...,
    create_if_missing: Literal[True],
) -> LoadedConfig: ...


@overload
def load_existing_config(
    global_install: bool,
) -> LoadedConfig: ...


def load_existing_config(
    global_install: bool,
    *,
    missing_ok: bool = False,
    create_if_missing: bool = False,
) -> LoadedConfig | None:
    """Load an existing agr.toml config with tools and skills dirs.

    This is the shared config-loading pattern used by commands that need
    a resolved config, tools list, and skills directories.

    Args:
        global_install: Whether to use the global config.
        missing_ok: If True, return None when the config is missing instead
            of printing an error and raising SystemExit.
        create_if_missing: If True, create a new config when none exists.
            For global installs, creates ``~/.agr/agr.toml`` with defaults.
            For local installs, creates an in-memory config at the repo
            root with auto-detected tools. Mutually exclusive with
            missing_ok (create_if_missing takes precedence).

    Returns:
        A LoadedConfig, or None when missing_ok is True and no config exists.
    """
    skills_dirs: dict[str, Path] | None = None

    if global_install:
        repo_root = None
        if create_if_missing:
            config_path, config = get_or_create_global_config()
        else:
            config_path = get_global_config_path()
            if not config_path.exists():
                if missing_ok:
                    return None
                print_missing_config_hint(global_install=True)
                raise SystemExit(1)
            config = AgrConfig.load(config_path)
    else:
        repo_root = require_repo_root()
        config_path = find_config()
        if config_path is None:
            if create_if_missing:
                config_path = repo_root / CONFIG_FILENAME
                config = AgrConfig()
                detected = detect_tools(repo_root)
                if detected:
                    config.tools = detected
            elif missing_ok:
                return None
            else:
                print_missing_config_hint(global_install=False)
                raise SystemExit(1)
        else:
            config = AgrConfig.load(config_path)

    tools = config.get_tools()
    if global_install:
        skills_dirs = build_global_skills_dirs(tools)

    return LoadedConfig(
        config=config,
        config_path=config_path,
        tools=tools,
        repo_root=repo_root,
        skills_dirs=skills_dirs,
    )


def save_and_summarize_results(
    results: list[CommandResult],
    config: AgrConfig,
    config_path: Path,
    *,
    action: str,
    total: int,
    print_result: Callable[[CommandResult], None],
    exit_on_failure: bool = True,
) -> None:
    """Save config and print a summary after a batch command (add, remove, etc.).

    Handles the shared pattern of: save config if any successes → print
    per-result output → print summary when multiple refs → optionally
    exit with error code on failures.

    Args:
        results: The list of CommandResult objects from the operation.
        config: The AgrConfig to save.
        config_path: Where to write the config.
        action: Verb for the summary line (e.g. "added", "removed").
        total: Total number of refs attempted (for summary denominator).
        print_result: Callback to print each individual result.
        exit_on_failure: If True, raise SystemExit(1) when any result failed.
    """
    console = get_console()
    successes = [r for r in results if r.success]
    if successes:
        config.save(config_path)

    for result in results:
        print_result(result)

    if total > 1:
        console.print()
        console.print(f"[bold]Summary:[/bold] {len(successes)}/{total} skills {action}")

    if exit_on_failure and any(not r.success for r in results):
        raise SystemExit(1)


def normalize_tool_names(tool_names: list[str]) -> list[str]:
    """Normalize user-provided tool names to lowercase, stripped form."""
    return [name.strip().lower() for name in tool_names if name.strip()]


def validate_tool_names(tool_names: list[str]) -> None:
    """Validate tool names against the TOOLS registry, exiting on failure."""
    invalid = [name for name in tool_names if name not in TOOLS]
    if invalid:
        error_exit(
            f"Unknown tool(s): {', '.join(invalid)}",
            hint=f"Available tools: {available_tools_string()}",
        )


def normalize_and_validate_tool_names(
    tool_names: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    """Normalize, deduplicate, and validate tool names in one step.

    Combines the normalize → deduplicate → validate pipeline that is
    repeated across tool-management commands.

    Args:
        tool_names: Raw tool name strings from user input.
        allow_empty: If False (default), exits with an error when no
            valid tool names remain after normalization.

    Returns:
        Deduplicated list of validated, normalized tool names.
    """
    names = list(dict.fromkeys(normalize_tool_names(tool_names)))
    if not allow_empty and not names:
        error_exit("At least one tool name is required.")
    validate_tool_names(names)
    return names


@dataclass
class ToolAddResult:
    """Result of adding tools to config."""

    added: list[str]
    skipped: list[str]


@dataclass
class ToolRemoveResult:
    """Result of removing tools from config."""

    removed: list[str]
    not_configured: list[str]


def add_tools_to_config(config: AgrConfig, names: list[str]) -> ToolAddResult:
    """Add tools to the config's tool list, skipping already-configured ones.

    Does not save the config — the caller is responsible for that.
    """
    added: list[str] = []
    skipped: list[str] = []
    for name in names:
        if name in config.tools:
            skipped.append(name)
        else:
            config.tools.append(name)
            added.append(name)
    return ToolAddResult(added=added, skipped=skipped)


def remove_tools_from_config(
    config: AgrConfig,
    names: list[str],
    repo_root: Path | None,
) -> ToolRemoveResult:
    """Remove tools from the config's tool list, deleting their installed skills.

    Exits with an error if removing all tools. Does not save the config —
    the caller is responsible for that.
    """
    remaining = [t for t in config.tools if t not in names]
    if not remaining:
        error_exit("Cannot remove all tools. At least one must remain.")

    previous_default = config.default_tool
    removed: list[str] = []
    not_configured: list[str] = []

    for name in names:
        if name not in config.tools:
            not_configured.append(name)
            continue
        if not delete_tool_skills(name, repo_root):
            continue
        config.tools.remove(name)
        removed.append(name)

    ensure_valid_default_tool(config, previous_default)
    return ToolRemoveResult(removed=removed, not_configured=not_configured)


def print_tool_add_result(result: ToolAddResult) -> None:
    """Print the result of a tool add operation."""
    console = get_console()
    for name in result.added:
        console.print(f"[green]Added:[/green] {name}")
    for name in result.skipped:
        console.print(f"[dim]Already configured:[/dim] {name}")


def print_tool_remove_result(result: ToolRemoveResult) -> None:
    """Print the result of a tool remove operation."""
    console = get_console()
    for name in result.removed:
        console.print(f"[green]Removed:[/green] {name}")
    for name in result.not_configured:
        console.print(f"[dim]Not configured:[/dim] {name}")


def sync_dependencies_to_tools(config: AgrConfig, tool_names: list[str]) -> int:
    """Install existing dependencies into newly added tools.

    Returns:
        Number of dependencies that failed to sync.
    """
    console = get_console()
    if not tool_names or not config.dependencies:
        return 0

    repo_root = find_repo_root()
    if repo_root is None:
        console.print(
            "[yellow]Warning:[/yellow] Not in a git repository, "
            "cannot sync dependencies."
        )
        return 0

    console.print()
    console.print(
        f"[dim]Syncing {len(config.dependencies)} dependencies to new tools...[/dim]"
    )

    new_tools = [TOOLS[name] for name in tool_names]
    resolver = config.get_source_resolver()
    sync_errors = 0

    for dep in config.dependencies:
        try:
            handle, source_name = dep.resolve(config.default_source)

            tools_needing_install = filter_tools_needing_install(
                handle, repo_root, new_tools, source_name
            )

            if not tools_needing_install:
                continue

            fetch_and_install_to_tools(
                handle,
                repo_root,
                tools_needing_install,
                overwrite=False,
                resolver=resolver,
                source=source_name,
            )

            tool_list = ", ".join(t.name for t in tools_needing_install)
            console.print(f"[green]Installed:[/green] {dep.identifier} ({tool_list})")

        except INSTALL_ERROR_TYPES as e:
            print_error(f"{dep.identifier}: {format_install_error(e)}")
            sync_errors += 1

    return sync_errors


def exit_if_sync_errors(sync_errors: int) -> None:
    """Print a warning and exit if any dependency syncs failed."""
    if sync_errors:
        console = get_console()
        console.print(
            f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
        )
        raise SystemExit(1)


def delete_tool_skills(tool_name: str, repo_root: Path | None) -> bool:
    """Delete all installed skills for a configured tool.

    Returns True if successful (or no skills to delete), False on error.
    """
    console = get_console()
    if repo_root is None:
        return True

    tool_config = TOOLS[tool_name]
    skills_dir = tool_config.get_skills_dir(repo_root)
    if not skills_dir.exists():
        return True

    skill_count = sum(1 for entry in skills_dir.iterdir() if entry.is_dir())
    try:
        shutil.rmtree(skills_dir)
        console.print(
            f"[dim]Deleted {skill_count} skills from "
            f"{skills_dir.relative_to(repo_root)}/[/dim]"
        )
    except OSError as e:
        console.print(f"[red]Error deleting skills:[/red] {e}")
        console.print(f"[dim]Tool '{tool_name}' not removed from config[/dim]")
        return False

    return True


def ensure_valid_default_tool(
    config: AgrConfig, previous_default_tool: str | None
) -> None:
    """Keep default_tool valid after tool list updates.

    If the current default_tool is no longer in the tools list, replaces it
    with the first remaining tool (or None if no tools remain).
    """
    console = get_console()
    if config.default_tool and config.default_tool in config.tools:
        return
    if previous_default_tool is None:
        return

    replacement = config.tools[0] if config.tools else None
    config.default_tool = replacement
    if replacement:
        console.print(
            "[yellow]Default tool updated:[/yellow] "
            f"{previous_default_tool} -> {replacement}"
        )
    else:
        console.print("[yellow]Default tool unset:[/yellow] no tools configured")
