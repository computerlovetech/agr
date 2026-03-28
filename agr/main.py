"""CLI entry point for agr."""

from typing import Annotated

import typer

from agr import __version__
from agr.commands.add import run_add
from agr.commands.init import run_init
from agr.commands.list import run_list
from agr.commands.onboard import run_onboard
from agr.commands.remove import run_remove
from agr.commands.sync import run_sync
from agr.commands.config_cmd import (
    run_config_add,
    run_config_edit,
    run_config_get,
    run_config_path,
    run_config_remove,
    run_config_set,
    run_config_show,
    run_config_unset,
)
from agr.commands.tools import (
    run_default_tool_set,
    run_default_tool_unset,
    run_tools_add,
    run_tools_list,
    run_tools_remove,
    run_tools_set,
)
from agr.console import print_deprecation, set_quiet

GlobalScope = Annotated[
    bool,
    typer.Option("--global", "-g", help="Use global ~/.agr/agr.toml."),
]

app = typer.Typer(
    name="agr",
    help="Agent Resources - Install and manage agent skills.",
    no_args_is_help=True,
    add_completion=False,
)

# Config sub-app
config_app = typer.Typer(
    name="config",
    help="Manage agr.toml configuration.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

# --- New unified config commands ---


@config_app.command("show")
def config_show(
    global_scope: GlobalScope = False,
) -> None:
    """Show formatted view of effective config."""
    run_config_show(global_scope)


@config_app.command("path")
def config_path(
    global_scope: GlobalScope = False,
) -> None:
    """Print resolved agr.toml path."""
    run_config_path(global_scope)


@config_app.command("edit")
def config_edit(
    global_scope: GlobalScope = False,
) -> None:
    """Open agr.toml in $EDITOR."""
    run_config_edit(global_scope)


@config_app.command("get")
def config_get(
    key: Annotated[str, typer.Argument(help="Config key to read.")],
    global_scope: GlobalScope = False,
) -> None:
    """Read any config value."""
    run_config_get(key, global_scope)


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key to write.")],
    values: Annotated[list[str], typer.Argument(help="Value(s) to set.")],
    global_scope: GlobalScope = False,
) -> None:
    """Write a scalar value or replace a list."""
    run_config_set(key, values, global_scope)


@config_app.command("unset")
def config_unset(
    key: Annotated[str, typer.Argument(help="Config key to clear.")],
    global_scope: GlobalScope = False,
) -> None:
    """Clear a config value to default/None."""
    run_config_unset(key, global_scope)


@config_app.command("add")
def config_add(
    key: Annotated[str, typer.Argument(help="Config key to append to.")],
    values: Annotated[list[str], typer.Argument(help="Value(s) to add.")],
    global_scope: GlobalScope = False,
    source_type: Annotated[
        str | None,
        typer.Option("--type", help="Source type (for sources key)."),
    ] = None,
    source_url: Annotated[
        str | None,
        typer.Option("--url", help="Source URL (for sources key)."),
    ] = None,
) -> None:
    """Append to a list config value."""
    run_config_add(key, values, source_type, source_url, global_scope)


@config_app.command("remove")
def config_remove(
    key: Annotated[str, typer.Argument(help="Config key to remove from.")],
    values: Annotated[list[str], typer.Argument(help="Value(s) to remove.")],
    global_scope: GlobalScope = False,
) -> None:
    """Remove from a list config value."""
    run_config_remove(key, values, global_scope)


# --- Deprecated sub-Typers (still functional, print warnings) ---

# Config tools sub-app
config_tools_app = typer.Typer(
    name="tools",
    help="Manage configured tools.",
    no_args_is_help=False,  # Default to list
)
config_app.add_typer(config_tools_app, name="tools")

# Config default-tool sub-app
default_tool_app = typer.Typer(
    name="default-tool",
    help="Manage default tool used by agrx.",
    no_args_is_help=True,
)
config_app.add_typer(default_tool_app, name="default-tool")

# Backwards-compatible tools alias
tools_app = typer.Typer(
    name="tools",
    help="Deprecated alias for 'agr config tools'.",
    no_args_is_help=False,  # Default to list
)
app.add_typer(tools_app, name="tools")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"agr {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress non-error output.",
        ),
    ] = False,
) -> None:
    """Agent Resources - Install and manage agent skills."""
    set_quiet(quiet)


# Tools subcommand group
@tools_app.callback(invoke_without_command=True)
def tools_default(ctx: typer.Context) -> None:
    """Deprecated alias callback for agr tools commands."""
    print_deprecation("agr tools", "agr config tools")
    if ctx.invoked_subcommand is None:
        run_tools_list()


@tools_app.command("list")
def tools_list() -> None:
    """Deprecated alias for agr config tools list."""
    run_tools_list()


@tools_app.command("add")
def tools_add(
    names: Annotated[
        list[str],
        typer.Argument(help="Tool names to add."),
    ],
) -> None:
    """Deprecated alias for agr config tools add."""
    run_tools_add(names)


@tools_app.command("remove")
def tools_remove(
    names: Annotated[
        list[str],
        typer.Argument(help="Tool names to remove."),
    ],
) -> None:
    """Deprecated alias for agr config tools remove."""
    run_tools_remove(names)


# Config tools subcommand group
@config_tools_app.callback(invoke_without_command=True)
def config_tools_default(ctx: typer.Context) -> None:
    """List configured tools (default behavior)."""
    if ctx.invoked_subcommand is None:
        print_deprecation("agr config tools", "agr config get tools")
        run_tools_list()


@config_tools_app.command("list")
def config_tools_list() -> None:
    """List configured tools."""
    print_deprecation("agr config tools list", "agr config get tools")
    run_tools_list()


@config_tools_app.command("add")
def config_tools_add(
    names: Annotated[
        list[str],
        typer.Argument(help="Tool names to add."),
    ],
) -> None:
    """Add tools and sync existing dependencies to them."""
    print_deprecation("agr config tools add", f"agr config add tools {' '.join(names)}")
    run_tools_add(names)


@config_tools_app.command("set")
def config_tools_set(
    names: Annotated[
        list[str],
        typer.Argument(help="Tool names to set (replaces current list)."),
    ],
) -> None:
    """Replace configured tools with the provided list."""
    print_deprecation("agr config tools set", f"agr config set tools {' '.join(names)}")
    run_tools_set(names)


@config_tools_app.command("remove")
def config_tools_remove(
    names: Annotated[
        list[str],
        typer.Argument(help="Tool names to remove."),
    ],
) -> None:
    """Remove tools and delete their installed skills."""
    new_cmd = f"agr config remove tools {' '.join(names)}"
    print_deprecation("agr config tools remove", new_cmd)
    run_tools_remove(names)


@config_tools_app.command("unset")
def config_tools_unset(
    names: Annotated[
        list[str],
        typer.Argument(help="Tool names to unset (alias of remove)."),
    ],
) -> None:
    """Alias of remove."""
    new_cmd = f"agr config remove tools {' '.join(names)}"
    print_deprecation("agr config tools unset", new_cmd)
    run_tools_remove(names)


@default_tool_app.command("set")
def default_tool_set(
    name: Annotated[
        str,
        typer.Argument(help="Tool name to set as default."),
    ],
) -> None:
    """Set the default tool used by agrx."""
    new_cmd = f"agr config set default_tool {name}"
    print_deprecation("agr config default-tool set", new_cmd)
    run_default_tool_set(name)


@default_tool_app.command("unset")
def default_tool_unset() -> None:
    """Unset the default tool (agrx falls back to first configured tool)."""
    print_deprecation("agr config default-tool unset", "agr config unset default_tool")
    run_default_tool_unset()


@app.command()
def init(
    skill_name: Annotated[
        str | None,
        typer.Argument(
            help="Name for a new skill scaffold. If omitted, creates agr.toml.",
        ),
    ] = None,
    tools: Annotated[
        str | None,
        typer.Option(
            "--tools",
            help="Comma-separated tool list (e.g., claude,codex,opencode).",
        ),
    ] = None,
    default_tool: Annotated[
        str | None,
        typer.Option(
            "--default-tool",
            help="Default tool for agrx and instruction sync.",
        ),
    ] = None,
    sync_instructions: Annotated[
        bool | None,
        typer.Option(
            "--sync-instructions/--no-sync-instructions",
            help="Sync instruction files on agr sync.",
        ),
    ] = None,
    canonical_instructions: Annotated[
        str | None,
        typer.Option(
            "--canonical-instructions",
            help="Canonical instruction file (AGENTS.md, CLAUDE.md, or GEMINI.md).",
        ),
    ] = None,
) -> None:
    """Initialize agr.toml or create a skill scaffold.

    Without arguments: Creates agr.toml in current directory.
    With skill name: Creates a skill scaffold directory.

    Examples:
        agr init           # Create agr.toml
        agr init my-skill  # Create my-skill/SKILL.md scaffold
    """
    run_init(
        skill_name,
        tools=tools,
        default_tool=default_tool,
        sync_instructions=sync_instructions,
        canonical_instructions=canonical_instructions,
    )


@app.command()
def onboard(
    no_migrate: Annotated[
        bool,
        typer.Option(
            "--no-migrate",
            help="Skip migration offer for skills in tool folders.",
        ),
    ] = False,
) -> None:
    """Interactive guided setup for agr.

    Walks you through tool selection, skill discovery, and configuration
    in an interactive terminal session.

    Examples:
        agr onboard           # Start guided setup
        agr onboard --no-migrate  # Skip migration prompts
    """
    run_onboard(no_migrate=no_migrate)


@app.command()
def add(
    refs: Annotated[
        list[str],
        typer.Argument(
            help="Skill handles (user/skill) or local paths (./path) to add.",
        ),
    ],
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-o",
            help="Overwrite existing skills.",
        ),
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            "-s",
            help="Source name to use for this install.",
        ),
    ] = None,
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Install globally using ~/.agr/agr.toml "
            "and per-tool global skill directories.",
        ),
    ] = False,
) -> None:
    """Add skills from GitHub or local paths.

    Examples:
        agr add kasperjunge/commit
        agr add maragudk/skills/collaboration
        agr add ./my-skill
        agr add kasperjunge/commit kasperjunge/pr  # Multiple
    """
    run_add(refs, overwrite, source, global_install=global_install)


@app.command()
def remove(
    refs: Annotated[
        list[str],
        typer.Argument(
            help="Skill handles or paths to remove.",
        ),
    ],
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Remove from global installation (~/.agr/agr.toml).",
        ),
    ] = False,
) -> None:
    """Remove skills from the current scope.

    Examples:
        agr remove kasperjunge/commit
        agr remove ./my-skill
    """
    run_remove(refs, global_install=global_install)


@app.command()
def sync(
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Sync global dependencies from ~/.agr/agr.toml.",
        ),
    ] = False,
) -> None:
    """Install all skills from the current scope config.

    Installs any dependencies that aren't already installed.
    """
    run_sync(global_install=global_install)


@app.command(name="list")
def list_cmd(
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="List global dependencies from ~/.agr/agr.toml.",
        ),
    ] = False,
) -> None:
    """List all skills and their status for the current scope.

    Shows all dependencies from agr.toml and whether they're installed.
    """
    run_list(global_install=global_install)


if __name__ == "__main__":
    app()
