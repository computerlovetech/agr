"""CLI entry point for agrx - temporary skill runner."""

import shutil
import signal
import sys
import uuid
from contextlib import contextmanager, suppress
from pathlib import Path
from collections.abc import Generator
from typing import Annotated

import typer

from agr.config import AgrConfig, find_config, find_repo_root
from agr.console import get_console, print_error
from agr.exceptions import AgrError
from agr.runner import check_tool_cli, run_skill_command
from agr.skill import AGRX_PREFIX
from agr.skill_installer import install_remote_skill
from agr.handle import parse_handle
from agr.tool import (
    DEFAULT_TOOL_NAMES,
    available_tools_string,
    get_tool,
)

app = typer.Typer(
    name="agrx",
    help="Run a skill temporarily without adding to agr.toml.",
    no_args_is_help=True,
    add_completion=False,
)

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


def _cleanup_skill(skill_path: Path) -> None:
    """Clean up a temporary skill."""
    if skill_path.exists():
        with suppress(OSError):
            shutil.rmtree(skill_path)


@contextmanager
def _temporary_skill(skill_path: Path) -> Generator[None, None, None]:
    """Ensure a temporary skill is cleaned up on normal exit or signal.

    Installs SIGINT/SIGTERM handlers that remove the skill directory,
    restores the original handlers on exit, and performs cleanup in the
    ``finally`` block for the non-signal path.
    """
    cleanup_done = False

    def _on_signal(signum: int, frame: object) -> None:
        nonlocal cleanup_done
        if not cleanup_done:
            cleanup_done = True
            _cleanup_skill(skill_path)
        sys.exit(1)

    original_sigint = signal.signal(signal.SIGINT, _on_signal)
    original_sigterm = signal.signal(signal.SIGTERM, _on_signal)

    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)
        if not cleanup_done:
            cleanup_done = True
            _cleanup_skill(skill_path)


@app.command()
def main(
    handle: Annotated[
        str,
        typer.Argument(
            help="Skill handle to run (e.g., vercel-labs/agent-browser/agent-browser).",
        ),
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
            help="Prompt to pass to the skill.",
        ),
    ] = None,
    source: Annotated[
        str | None,
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
        agrx vercel-labs/agent-browser/agent-browser
        agrx maragudk/skills/collaboration -i
        agrx vercel-labs/agent-browser/agent-browser -p "Automate browser testing"
        agrx vercel-labs/agent-browser/agent-browser --tool cursor
        agrx vercel-labs/agent-browser/agent-browser --tool codex
        agrx vercel-labs/agent-browser/agent-browser --tool opencode
    """
    console = get_console()

    # Determine which tool to use
    tool_name = tool or _get_default_tool()

    try:
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

        config_path = find_config()
        config = AgrConfig.load(config_path) if config_path else AgrConfig()

        # Parse handle
        parsed = parse_handle(handle, default_owner=config.default_owner)

        if parsed.is_local:
            print_error("agrx only works with remote handles")
            console.print("[dim]Use 'agr add' for local skills[/dim]")
            raise typer.Exit(1)
        resolver = config.get_source_resolver()
        if source:
            resolver.get(source)

        # Check tool CLI is available
        check_tool_cli(tool_config)

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

        with _temporary_skill(temp_skill_path):
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

            run_skill_command(tool_config, skill_prompt, interactive=interactive)

    except AgrError as e:
        print_error(str(e))
        raise typer.Exit(1)


def _build_temp_skill_name(skill_name: str) -> str:
    """Build a unique temp skill name to avoid collisions."""
    suffix = uuid.uuid4().hex[:AGRX_SUFFIX_LEN]
    return f"{AGRX_PREFIX}{skill_name}-{suffix}"


if __name__ == "__main__":
    app()
