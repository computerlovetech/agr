"""agr list command implementation."""

from pathlib import Path

from rich.table import Table

from agr.commands._tool_helpers import load_existing_config, print_missing_config_hint
from agr.config import DEPENDENCY_TYPE_RALPH
from agr.console import get_console
from agr.exceptions import AgrError, InvalidHandleError
from agr.metadata import METADATA_TYPE_LOCAL, METADATA_TYPE_REMOTE
from agr.fetcher import filter_tools_needing_install, is_ralph_installed
from agr.handle import ParsedHandle
from agr.tool import ToolConfig


def _get_installation_status(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    source: str | None = None,
    skills_dirs: dict[str, Path] | None = None,
) -> str:
    """Get installation status across all configured tools.

    Args:
        handle: Parsed handle for the skill
        repo_root: Repository root path
        tools: List of ToolConfig instances
        source: Source name for remote skills (optional)
        skills_dirs: Explicit skills directories per tool (optional)

    Returns:
        Rich-formatted status string
    """
    tools_needing_install = filter_tools_needing_install(
        handle, repo_root, tools, source, skills_dirs
    )

    if not tools_needing_install:
        return "[green]installed[/green]"
    elif len(tools_needing_install) < len(tools):
        installed_names = [t.name for t in tools if t not in tools_needing_install]
        return f"[yellow]partial ({', '.join(installed_names)})[/yellow]"
    else:
        return "[yellow]not synced[/yellow]"


def _get_ralph_installation_status(
    handle: ParsedHandle,
    repo_root: Path | None,
    source: str | None = None,
) -> str:
    """Get installation status for a ralph dependency."""
    if is_ralph_installed(handle, repo_root, source):
        return "[green]installed[/green]"
    return "[yellow]not synced[/yellow]"


def run_list(global_install: bool = False) -> None:
    """Run the list command.

    Lists all dependencies from agr.toml with their sync status.
    """
    console = get_console()
    loaded = load_existing_config(global_install, missing_ok=True)
    if loaded is None:
        print_missing_config_hint(global_install)
        return
    config, config_path = loaded.config, loaded.config_path
    tools, repo_root, skills_dirs = loaded.tools, loaded.repo_root, loaded.skills_dirs

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow]")
        console.print("[dim]Run 'agr add <handle>' to add skills or ralphs.[/dim]")
        return

    # Build table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Status")

    for dep in config.dependencies:
        # Determine display name and status
        if dep.is_local:
            display_name = dep.path or ""
            kind = METADATA_TYPE_LOCAL
        else:
            display_name = dep.handle or ""
            kind = METADATA_TYPE_REMOTE

        # Show dep type alongside local/remote
        dep_type_label = dep.type
        kind_display = f"{kind} ({dep_type_label})"

        # Check installation status
        try:
            handle, source_name = dep.resolve(
                config.default_source, config.default_owner
            )
            if dep.type == DEPENDENCY_TYPE_RALPH:
                status = _get_ralph_installation_status(handle, repo_root, source_name)
            else:
                status = _get_installation_status(
                    handle, repo_root, tools, source_name, skills_dirs
                )
        except (InvalidHandleError, AgrError):
            status = "[red]invalid[/red]"

        table.add_row(display_name, kind_display, status)

    console.print(table)

    # Show config path
    console.print()
    console.print(f"[dim]Config: {config_path}[/dim]")
