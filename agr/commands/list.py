"""agr list command implementation."""

from pathlib import Path

from rich.table import Table

from agr.config import AgrConfig, find_config, get_global_config_path, require_repo_root
from agr.console import get_console
from agr.exceptions import AgrError, InvalidHandleError
from agr.fetcher import is_skill_installed
from agr.handle import ParsedHandle
from agr.tool import ToolConfig, build_global_skills_dirs


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
    installed_tools = [
        tool.name
        for tool in tools
        if is_skill_installed(
            handle,
            repo_root,
            tool,
            source,
            skills_dir=skills_dirs.get(tool.name) if skills_dirs is not None else None,
        )
    ]

    if len(installed_tools) == len(tools):
        return "[green]installed[/green]"
    elif installed_tools:
        return f"[yellow]partial ({', '.join(installed_tools)})[/yellow]"
    else:
        return "[yellow]not synced[/yellow]"


def run_list(global_install: bool = False) -> None:
    """Run the list command.

    Lists all dependencies from agr.toml with their sync status.
    """
    console = get_console()
    skills_dirs: dict[str, Path] | None = None
    if global_install:
        repo_root = None
        config_path = get_global_config_path()
        if not config_path.exists():
            console.print("[yellow]No global agr.toml found.[/yellow]")
            console.print("[dim]Run 'agr add -g <handle>' to create one.[/dim]")
            return
    else:
        repo_root = require_repo_root()

        # Find config
        config_path = find_config()
        if config_path is None:
            console.print("[yellow]No agr.toml found.[/yellow]")
            console.print("[dim]Run 'agr init' to create one.[/dim]")
            return

    config = AgrConfig.load(config_path)
    tools = config.get_tools()
    if global_install:
        skills_dirs = build_global_skills_dirs(tools)

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow]")
        console.print("[dim]Run 'agr add <handle>' to add skills.[/dim]")
        return

    # Build table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Skill", style="cyan")
    table.add_column("Type")
    table.add_column("Status")

    for dep in config.dependencies:
        # Determine display name and status
        if dep.is_local:
            display_name = dep.path or ""
            kind = "local"
        else:
            display_name = dep.handle or ""
            kind = "remote"

        # Check installation status
        try:
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)
            status = _get_installation_status(
                handle, repo_root, tools, source_name, skills_dirs
            )
        except (InvalidHandleError, AgrError):
            status = "[red]invalid[/red]"

        table.add_row(display_name, kind, status)

    console.print(table)

    # Show config path
    console.print()
    console.print(f"[dim]Config: {config_path}[/dim]")
