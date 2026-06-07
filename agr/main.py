"""CLI entry point for agr."""

from typing import Annotated
import webbrowser

import typer

from agr import __version__
from agr import auth as agr_auth
from agr.commands.add import run_add
from agr.commands.init import run_init
from agr.commands.list import run_list
from agr.commands.remove import run_remove
from agr.commands.run import run_run
from agr.commands.sync import run_sync
from agr.commands.upgrade import run_upgrade
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
from agr.console import get_console, set_quiet
from agr.github_oauth import GitHubOAuthDeviceFlow
from agr.tool import available_tools_string

GlobalScope = Annotated[
    bool,
    typer.Option("--global", "-g", help="Use global ~/.agr/agr.toml."),
]

app = typer.Typer(
    name="agr",
    help="Agent Resources - The package manager for AI agents.",
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

auth_app = typer.Typer(
    name="auth",
    help="Manage GitHub authentication.",
    no_args_is_help=True,
)
app.add_typer(auth_app, name="auth")

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


def print_auth_status(result: agr_auth.AuthStatus) -> None:
    console = get_console()
    if result.source == "stored":
        method = f" ({result.method})" if result.method else ""
        console.print(f"Authenticated with stored agr GitHub token{method}.")
        return
    console.print(f"Authenticated with {result.source} environment token.")


@auth_app.command("login")
def auth_login(
    oauth: Annotated[
        bool,
        typer.Option("--oauth", help="Authenticate using GitHub OAuth device flow."),
    ] = False,
) -> None:
    """Authenticate with GitHub."""
    console = get_console()
    result = agr_auth.GitHubAuthStatusChecker().get_status()
    if result.authenticated:
        print_auth_status(result)
        console.print("Already logged in.")
        return

    def show_device_prompt(authorization: agr_auth.DeviceAuthorization) -> None:
        console.print("Open this URL to authenticate with GitHub:")
        console.print(authorization.verification_uri)
        console.print(f"Enter code: [bold]{authorization.user_code}[/bold]")
        webbrowser.open(authorization.verification_uri)
        console.print("Waiting for GitHub authorization...")

    if oauth:
        strategy: agr_auth.GitHubLoginStrategy = agr_auth.OAuthGitHubLoginStrategy(
            GitHubOAuthDeviceFlow(),
            show_device_prompt,
        )
    else:
        strategy = agr_auth.UsernamePasswordGitHubLoginStrategy(
            username_prompt=lambda: typer.prompt("GitHub username"),
            password_prompt=lambda: typer.prompt(
                "GitHub password or token",
                hide_input=True,
            ),
        )

    try:
        agr_auth.login(strategy)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    console.print("Authenticated with GitHub.")


@auth_app.command("status")
def auth_status() -> None:
    """Show GitHub authentication status."""
    result = agr_auth.status()
    console = get_console()
    if not result.authenticated:
        console.print(
            "Not authenticated. Run 'agr auth login' or set GITHUB_TOKEN/GH_TOKEN."
        )
        raise typer.Exit(1)
    print_auth_status(result)


@auth_app.command("logout")
def auth_logout() -> None:
    """Remove stored GitHub authentication."""
    removed = agr_auth.logout()
    console = get_console()
    if removed:
        console.print("Removed stored GitHub token.")
        return
    console.print("No stored GitHub token found.")


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
    """Agent Resources - The package manager for AI agents."""
    set_quiet(quiet)


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
    global_install: GlobalScope = False,
) -> None:
    """Add skills from GitHub or local paths.

    Examples:
        agr add vercel-labs/agent-browser/agent-browser
        agr add maragudk/skills/collaboration
        agr add ./my-skill
        agr add vercel-labs/agent-browser/agent-browser anthropics/skills/pdf  # Multiple
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
    global_install: GlobalScope = False,
) -> None:
    """Remove skills from the current scope.

    Examples:
        agr remove vercel-labs/agent-browser/agent-browser
        agr remove ./my-skill
    """
    run_remove(refs, global_install=global_install)


@app.command()
def sync(
    global_install: GlobalScope = False,
    frozen: Annotated[
        bool,
        typer.Option(
            "--frozen",
            help="Install from lockfile exactly, fail if missing.",
        ),
    ] = False,
    locked: Annotated[
        bool,
        typer.Option(
            "--locked",
            help="Fail if lockfile is out-of-date with agr.toml.",
        ),
    ] = False,
) -> None:
    """Install all skills from the current scope config.

    Installs any dependencies that aren't already installed.
    """
    run_sync(global_install=global_install, frozen=frozen, locked=locked)


@app.command()
def upgrade(
    handles: Annotated[
        list[str] | None,
        typer.Argument(
            help="Handles or local paths to upgrade. Omit to upgrade all.",
        ),
    ] = None,
    global_install: GlobalScope = False,
) -> None:
    """Re-install dependencies (latest upstream commit for remotes, fresh copy for local) and refresh agr.lock.

    Examples:
        agr upgrade                              # Upgrade everything
        agr upgrade anthropics/skills/pdf        # Upgrade one (full handle)
        agr upgrade pdf                          # Upgrade one (short name)
        agr upgrade pdf collaboration            # Upgrade several
        agr upgrade -g                           # Upgrade globals
    """
    run_upgrade(handles or [], global_install=global_install)


@app.command(
    name="run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_cmd(
    ctx: typer.Context,
    skill_name: Annotated[
        str,
        typer.Argument(help="Name of an installed skill to run."),
    ],
    tool: Annotated[
        str | None,
        typer.Option(
            "--tool",
            "-t",
            help=f"Tool CLI to use ({available_tools_string()}).",
        ),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Invoke the tool in interactive mode with the skill prompt prefilled.",
        ),
    ] = False,
    prompt: Annotated[
        str | None,
        typer.Option(
            "--prompt",
            "-p",
            help="Additional prompt text to append after the skill reference.",
        ),
    ] = None,
    global_install: GlobalScope = False,
) -> None:
    """Run an installed skill in the project's configured tool.

    Looks up <skill-name> in the configured tool's skills directory and
    invokes the tool's CLI with the skill prompt. Anything after ``--`` is
    appended to the prompt as extra input.

    Examples:
        agr run pdf
        agr run pdf -- "summarise report.pdf"
        agr run pdf --tool cursor
        agr run pdf -i
    """
    run_run(
        skill_name,
        tool=tool,
        interactive=interactive,
        prompt=prompt,
        extra_args=list(ctx.args) if ctx.args else None,
        global_install=global_install,
    )


@app.command(name="list")
def list_cmd(
    global_install: GlobalScope = False,
) -> None:
    """List all skills and their status for the current scope.

    Shows all dependencies from agr.toml and whether they're installed.
    """
    run_list(global_install=global_install)


if __name__ == "__main__":
    app()
