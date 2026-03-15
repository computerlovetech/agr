"""Shared helpers for tool-management commands.

These utilities are used by both the unified config commands (config_cmd.py)
and the deprecated tool commands (tools.py).
"""

import shutil
from pathlib import Path

from agr.config import AgrConfig, find_repo_root
from agr.console import get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.fetcher import fetch_and_install_to_tools, filter_tools_needing_install
from agr.tool import TOOLS, available_tools_string


def normalize_tool_names(tool_names: list[str]) -> list[str]:
    """Normalize user-provided tool names to lowercase, stripped form."""
    return [name.strip().lower() for name in tool_names if name.strip()]


def validate_tool_names(tool_names: list[str]) -> None:
    """Validate tool names against the TOOLS registry, exiting on failure."""
    console = get_console()
    invalid = [name for name in tool_names if name not in TOOLS]
    if invalid:
        print_error(f"Unknown tool(s): {', '.join(invalid)}")
        console.print(f"[dim]Available tools: {available_tools_string()}[/dim]")
        raise SystemExit(1)


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
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)

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
