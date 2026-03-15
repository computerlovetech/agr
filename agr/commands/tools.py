"""agr tool-configuration command implementations (deprecated).

The ``run_*`` functions here back the deprecated ``agr tools`` sub-commands.
Shared helpers live in ``agr.commands._tool_helpers``.
"""

from agr.config import AgrConfig, find_config, find_repo_root, require_config
from agr.console import get_console, print_error
from agr.commands._tool_helpers import (
    delete_tool_skills,
    ensure_valid_default_tool,
    normalize_tool_names,
    sync_dependencies_to_tools,
    validate_tool_names,
)

from agr.tool import DEFAULT_TOOL_NAMES, TOOLS


def _load_required_config() -> AgrConfig:
    """Load agr.toml or exit with a user-facing error."""
    return AgrConfig.load(require_config())


def run_tools_list() -> None:
    """List configured tools and available tool names."""
    console = get_console()
    config_path = find_config()

    if config_path:
        config = AgrConfig.load(config_path)
        configured = config.tools
    else:
        configured = list(DEFAULT_TOOL_NAMES)
        console.print("[dim]No agr.toml found, showing defaults[/dim]")
        console.print()

    available = [name for name in TOOLS.keys() if name not in configured]

    console.print("[bold]Configured tools:[/bold]")
    if configured:
        for tool_name in configured:
            console.print(f"  - {tool_name}")
    else:
        console.print("  [dim](none)[/dim]")

    if available:
        console.print()
        console.print(f"[dim]Available tools:[/dim] {', '.join(available)}")


def run_tools_add(tool_names: list[str]) -> None:
    """Add tools and sync existing dependencies to newly added tools."""
    console = get_console()
    names = list(dict.fromkeys(normalize_tool_names(tool_names)))
    validate_tool_names(names)

    config = _load_required_config()

    added: list[str] = []
    skipped: list[str] = []
    for name in names:
        if name in config.tools:
            skipped.append(name)
        else:
            config.tools.append(name)
            added.append(name)

    for name in added:
        console.print(f"[green]Added:[/green] {name}")
    for name in skipped:
        console.print(f"[dim]Already configured:[/dim] {name}")

    sync_errors = sync_dependencies_to_tools(config, added)
    config.save()

    if sync_errors:
        console.print(
            f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
        )
        raise SystemExit(1)


def run_tools_set(tool_names: list[str]) -> None:
    """Replace configured tools with the provided list."""
    console = get_console()
    names = list(dict.fromkeys(normalize_tool_names(tool_names)))
    if not names:
        print_error("Cannot set empty tools list.")
        console.print("[dim]At least one tool must be configured.[/dim]")
        raise SystemExit(1)

    validate_tool_names(names)
    config = _load_required_config()

    previous_tools = list(config.tools)
    previous_default_tool = config.default_tool
    added = [name for name in names if name not in previous_tools]
    removed = [name for name in previous_tools if name not in names]

    config.tools = names
    ensure_valid_default_tool(config, previous_default_tool)

    if added:
        console.print(f"[green]Added:[/green] {', '.join(added)}")
    if removed:
        console.print(f"[yellow]Removed from config:[/yellow] {', '.join(removed)}")
    if not added and not removed and previous_tools == names:
        console.print("[dim]Tools already configured.[/dim]")
    elif not added and not removed:
        console.print("[green]Updated:[/green] Tool order changed")

    sync_errors = sync_dependencies_to_tools(config, added)
    config.save()

    if sync_errors:
        console.print(
            f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
        )
        raise SystemExit(1)


def run_tools_remove(tool_names: list[str]) -> None:
    """Remove tools from configuration and delete their installed skills."""
    console = get_console()
    names = list(dict.fromkeys(normalize_tool_names(tool_names)))
    validate_tool_names(names)

    config = _load_required_config()
    previous_default_tool = config.default_tool

    remaining = [tool for tool in config.tools if tool not in names]
    if not remaining:
        print_error("Cannot remove all tools.")
        console.print("[dim]At least one tool must be configured.[/dim]")
        raise SystemExit(1)

    repo_root = find_repo_root()
    removed: list[str] = []
    not_configured: list[str] = []

    for name in names:
        if name not in config.tools:
            not_configured.append(name)
            continue

        console.print(f"[yellow]Removing:[/yellow] {name}")
        if not delete_tool_skills(name, repo_root):
            continue

        config.tools.remove(name)
        removed.append(name)

    ensure_valid_default_tool(config, previous_default_tool)
    config.save()

    for name in removed:
        console.print(f"[green]Removed:[/green] {name}")
    for name in not_configured:
        console.print(f"[dim]Not configured:[/dim] {name}")


def run_default_tool_set(tool_name: str) -> None:
    """Set default_tool in agr.toml."""
    console = get_console()
    normalized = normalize_tool_names([tool_name])
    if not normalized:
        print_error("Tool name is required.")
        raise SystemExit(1)

    name = normalized[0]
    validate_tool_names([name])
    config = _load_required_config()

    if name not in config.tools:
        print_error(
            f"Tool '{name}' is not configured. "
            f"Add it first with 'agr config tools add {name}'."
        )
        raise SystemExit(1)

    if config.default_tool == name:
        console.print(f"[dim]Default tool already set:[/dim] {name}")
        return

    config.default_tool = name
    config.save()
    console.print(f"[green]Default tool set:[/green] {name}")


def run_default_tool_unset() -> None:
    """Unset default_tool in agr.toml."""
    console = get_console()
    config = _load_required_config()
    if config.default_tool is None:
        console.print("[dim]Default tool is already unset.[/dim]")
        return

    previous = config.default_tool
    config.default_tool = None
    config.save()
    console.print(f"[green]Default tool unset:[/green] {previous}")
