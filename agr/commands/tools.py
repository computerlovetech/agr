"""agr tool-configuration command implementations (deprecated).

The ``run_*`` functions here back the deprecated ``agr tools`` sub-commands.
Shared helpers live in ``agr.commands._tool_helpers``.
"""

from agr.config import AgrConfig, find_config, find_repo_root, require_config
from agr.console import error_exit, get_console
from agr.commands._tool_helpers import (
    add_tools_to_config,
    ensure_valid_default_tool,
    exit_if_sync_errors,
    normalize_and_validate_tool_names,
    print_tool_add_result,
    print_tool_remove_result,
    remove_tools_from_config,
    sync_dependencies_to_tools,
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

    available = [name for name in TOOLS if name not in configured]

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
    names = normalize_and_validate_tool_names(tool_names)
    config = _load_required_config()

    result = add_tools_to_config(config, names)
    print_tool_add_result(result)

    sync_errors = sync_dependencies_to_tools(config, result.added)
    config.save()

    exit_if_sync_errors(sync_errors)


def run_tools_set(tool_names: list[str]) -> None:
    """Replace configured tools with the provided list."""
    console = get_console()
    names = normalize_and_validate_tool_names(tool_names)
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

    exit_if_sync_errors(sync_errors)


def run_tools_remove(tool_names: list[str]) -> None:
    """Remove tools from configuration and delete their installed skills."""
    names = normalize_and_validate_tool_names(tool_names)
    config = _load_required_config()
    repo_root = find_repo_root()

    result = remove_tools_from_config(config, names, repo_root)
    config.save()
    print_tool_remove_result(result)


def run_default_tool_set(tool_name: str) -> None:
    """Set default_tool in agr.toml."""
    console = get_console()
    names = normalize_and_validate_tool_names([tool_name])
    name = names[0]
    config = _load_required_config()

    if name not in config.tools:
        error_exit(
            f"Tool '{name}' is not configured. "
            f"Add it first with 'agr config add tools {name}'."
        )

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
