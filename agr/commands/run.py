"""agr run command implementation."""

from pathlib import Path

import typer

from agr.commands._tool_helpers import load_existing_config
from agr.console import get_console, print_error
from agr.exceptions import AgrError
from agr.runner import check_tool_cli, run_skill_command
from agr.skill import find_installed_skill, list_installed_skills
from agr.tool import (
    DEFAULT_TOOL_NAMES,
    ToolConfig,
    get_tool,
)


def _resolve_tool(
    tool: str | None,
    configured_tools: list[str],
    default_tool: str | None,
) -> ToolConfig:
    """Pick the tool to use: explicit flag → default_tool → first configured → fallback."""
    if tool:
        return get_tool(tool)
    if default_tool:
        return get_tool(default_tool)
    if configured_tools:
        return get_tool(configured_tools[0])
    return get_tool(DEFAULT_TOOL_NAMES[0])


def _build_skill_prompt(
    tool_config: ToolConfig,
    skill_dir: Path,
    skills_dir: Path,
    extra_prompt: str | None,
) -> str:
    """Build the prompt string that invokes the skill in the tool's CLI."""
    if tool_config.supports_nested:
        relative = skill_dir.relative_to(skills_dir).as_posix()
        skill_prompt = f"{tool_config.skill_prompt_prefix}{relative}"
    else:
        skill_prompt = f"{tool_config.skill_prompt_prefix}{skill_dir.name}"
    if extra_prompt:
        skill_prompt += f" {extra_prompt}"
    return skill_prompt


def run_run(
    skill_name: str,
    *,
    tool: str | None = None,
    interactive: bool = False,
    prompt: str | None = None,
    extra_args: list[str] | None = None,
    global_install: bool = False,
) -> None:
    """Execute an installed skill via the configured tool's CLI.

    Mirrors ``agrx`` for the persistent-skill case: looks up the skill in
    the project (or global) skills dir for the chosen tool, then shells
    out to the tool CLI with the skill prompt.
    """
    console = get_console()

    try:
        loaded = load_existing_config(global_install)
        config = loaded.config
        repo_root = loaded.repo_root

        tool_config = _resolve_tool(tool, config.tools, config.default_tool)

        if global_install:
            skills_dir = tool_config.get_global_skills_dir()
        else:
            assert repo_root is not None
            skills_dir = tool_config.get_skills_dir(repo_root)

        skill_dir = find_installed_skill(skills_dir, skill_name)
        if skill_dir is None:
            available = list_installed_skills(skills_dir)
            print_error(
                f"Skill '{skill_name}' is not installed for tool '{tool_config.name}'."
            )
            if available:
                console.print(f"[dim]Available skills: {', '.join(available)}[/dim]")
            else:
                console.print(
                    "[dim]No skills installed. Run 'agr sync' or "
                    "'agr add <handle>'.[/dim]"
                )
            raise typer.Exit(1)

        check_tool_cli(tool_config)

        extra_prompt_parts: list[str] = []
        if prompt:
            extra_prompt_parts.append(prompt)
        if extra_args:
            extra_prompt_parts.extend(extra_args)
        extra_prompt = " ".join(extra_prompt_parts) if extra_prompt_parts else None

        skill_prompt = _build_skill_prompt(
            tool_config, skill_dir, skills_dir, extra_prompt
        )

        console.print(
            f"[dim]Running skill '{skill_name}' with {tool_config.name}...[/dim]"
        )
        run_skill_command(tool_config, skill_prompt, interactive=interactive)

    except AgrError as e:
        print_error(str(e))
        raise typer.Exit(1)
