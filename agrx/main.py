"""CLI entry point for agrx - temporary skill runner."""

import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated, Optional

import typer

from agr.config import AgrConfig, find_config, find_repo_root
from agr.console import get_console, print_error
from agr.exceptions import AgrError
from agr.fetcher import install_remote_skill
from agr.handle import parse_handle
from agr.tool import (
    DEFAULT_TOOL_NAMES,
    TOOLS,
    ToolConfig,
    available_tools_string,
    get_tool,
)

app = typer.Typer(
    name="agrx",
    help="Run a skill temporarily without adding to agr.toml.",
    no_args_is_help=True,
    add_completion=False,
)

AGRX_PREFIX = "_agrx_"  # Prefix for temporary resources
AGRX_SUFFIX_LEN = 8


def _get_default_tool() -> str:
    """Get default tool from agr.toml or fall back to default."""
    config_path = find_config()
    if config_path:
        config = AgrConfig.load(config_path)
        if config.default_tool:
            return config.default_tool
        if config.tools:
            return config.tools[0]
    return DEFAULT_TOOL_NAMES[0]


def _check_tool_cli(tool_config: ToolConfig) -> None:
    """Check if tool's CLI is installed.

    Args:
        tool_config: ToolConfig for the tool to check

    Raises:
        typer.Exit: If CLI is not found
    """
    console = get_console()
    cli_cmd = tool_config.cli_command
    if not cli_cmd:
        print_error(f"{tool_config.name} has no CLI command configured")
        raise typer.Exit(1)
    if shutil.which(cli_cmd) is None:
        print_error(f"{cli_cmd} CLI not found.")
        if tool_config.install_hint:
            console.print(f"[dim]{tool_config.install_hint}[/dim]")
        raise typer.Exit(1)


def _cleanup_skill(skill_path: Path) -> None:
    """Clean up a temporary skill."""
    if skill_path.exists():
        try:
            shutil.rmtree(skill_path)
        except OSError:
            pass  # Best effort cleanup


def _build_skill_command(
    tool_config: ToolConfig,
    skill_prompt: str,
    *,
    non_interactive: bool,
) -> list[str]:
    """Build the command to run a skill with the selected tool."""
    if non_interactive and tool_config.cli_exec_command:
        cmd = list(tool_config.cli_exec_command)
    else:
        assert tool_config.cli_command is not None
        cmd = [tool_config.cli_command]
    if not non_interactive and tool_config.cli_interactive_prompt_flag:
        cmd.extend([tool_config.cli_interactive_prompt_flag, skill_prompt])
    elif not non_interactive and tool_config.cli_interactive_prompt_positional:
        cmd.append(skill_prompt)
    elif tool_config.cli_prompt_flag:
        cmd.extend([tool_config.cli_prompt_flag, skill_prompt])
    else:
        cmd.append(skill_prompt)
    return cmd


@app.command()
def main(
    handle: Annotated[
        str,
        typer.Argument(
            help="Skill handle to run (e.g., kasperjunge/commit).",
        ),
    ],
    tool: Annotated[
        Optional[str],
        typer.Option(
            "--tool",
            "-t",
            help=(
                "Tool CLI to use (claude, cursor, codex, "
                "opencode, copilot, antigravity)."
            ),
        ),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Start interactive session after running the skill.",
        ),
    ] = False,
    prompt: Annotated[
        Optional[str],
        typer.Option(
            "--prompt",
            "-p",
            help="Prompt to pass to the skill.",
        ),
    ] = None,
    source: Annotated[
        Optional[str],
        typer.Option(
            "--source",
            "-s",
            help="Source name to use for this run.",
        ),
    ] = None,
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Install to global skills directory instead of project-local.",
        ),
    ] = False,
) -> None:
    """Run a skill temporarily without adding to agr.toml.

    Downloads and installs the skill to a temporary location, runs it with the
    selected tool's CLI, and cleans up afterwards.

    Examples:
        agrx kasperjunge/commit
        agrx maragudk/skills/collaboration -i
        agrx kasperjunge/commit -p "Review my changes"
        agrx kasperjunge/commit --tool cursor
        agrx kasperjunge/commit --tool codex
        agrx kasperjunge/commit --tool opencode
    """
    console = get_console()

    # Determine which tool to use
    tool_name = tool or _get_default_tool()

    # Validate tool name
    if tool_name not in TOOLS:
        print_error(f"Unknown tool '{tool_name}'")
        console.print(f"[dim]Available tools: {available_tools_string()}[/dim]")
        raise typer.Exit(1)

    tool_config = get_tool(tool_name)

    # Find repo root (or use global dir)
    repo_root: Path | None = None
    if global_install:
        skills_dir = tool_config.get_global_skills_dir()
    else:
        repo_root = find_repo_root()
        if repo_root is None:
            print_error("Not in a git repository")
            console.print(
                f"[dim]Use --global to install to "
                f"{tool_config.get_global_skills_dir()}[/dim]"
            )
            raise typer.Exit(1)
        skills_dir = tool_config.get_skills_dir(repo_root)

    try:
        # Parse handle
        parsed = parse_handle(handle)

        if parsed.is_local:
            print_error("agrx only works with remote handles")
            console.print("[dim]Use 'agr add' for local skills[/dim]")
            raise typer.Exit(1)

        config_path = find_config()
        config = AgrConfig.load(config_path) if config_path else AgrConfig()
        resolver = config.get_source_resolver()
        if source:
            resolver.get(source)

        # Check tool CLI is available
        _check_tool_cli(tool_config)

        console.print(f"[dim]Downloading {handle}...[/dim]")

        # Create prefixed name for temporary skill
        prefixed_name = _build_temp_skill_name(parsed.name)

        # Download and install to a temporary location
        temp_skill_path = install_remote_skill(
            parsed,
            repo_root,
            tool_config,
            skills_dir,
            overwrite=False,
            resolver=resolver,
            source=source,
            install_name=prefixed_name,
        )

        # Set up cleanup handlers
        cleanup_done = False

        def cleanup_handler(signum, frame):
            nonlocal cleanup_done
            if not cleanup_done:
                cleanup_done = True
                _cleanup_skill(temp_skill_path)
            sys.exit(1)

        original_sigint = signal.signal(signal.SIGINT, cleanup_handler)
        original_sigterm = signal.signal(signal.SIGTERM, cleanup_handler)

        try:
            console.print(
                f"[dim]Running skill '{parsed.name}' with {tool_name}...[/dim]"
            )

            # Build the skill prompt from the actual installed location
            if tool_config.supports_nested:
                relative_skill = temp_skill_path.relative_to(skills_dir)
                skill_prompt = (
                    f"{tool_config.skill_prompt_prefix}{relative_skill.as_posix()}"
                )
            else:
                skill_prompt = (
                    f"{tool_config.skill_prompt_prefix}{temp_skill_path.name}"
                )
            if prompt:
                skill_prompt += f" {prompt}"

            # Run the appropriate CLI
            if interactive:
                # Run the skill in interactive mode
                cmd = _build_skill_command(
                    tool_config,
                    skill_prompt,
                    non_interactive=False,
                )
                if tool_config.cli_force_flag:
                    cmd.append(tool_config.cli_force_flag)
                subprocess.run(cmd, check=False)
            else:
                # Just run the skill
                cmd = _build_skill_command(
                    tool_config,
                    skill_prompt,
                    non_interactive=True,
                )
                if tool_config.suppress_stderr_non_interactive:
                    result = subprocess.run(
                        cmd,
                        check=False,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if result.returncode != 0 and result.stderr:
                        sys.stderr.write(result.stderr)
                else:
                    subprocess.run(cmd, check=False)

        finally:
            # Restore signal handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

            # Clean up
            if not cleanup_done:
                cleanup_done = True
                _cleanup_skill(temp_skill_path)

    except AgrError as e:
        print_error(str(e))
        raise typer.Exit(1)


def _build_temp_skill_name(skill_name: str) -> str:
    """Build a unique temp skill name to avoid collisions."""
    suffix = uuid.uuid4().hex[:AGRX_SUFFIX_LEN]
    return f"{AGRX_PREFIX}{skill_name}-{suffix}"


if __name__ == "__main__":
    app()
