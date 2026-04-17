"""Shared skill execution helpers used by ``agrx`` and ``agr run``.

These were previously private helpers in ``agrx/main.py``; they were
extracted to a shared module so ``agr run`` can reuse the same
tool-CLI invocation logic without duplication.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from pathlib import Path

from agr.console import error_exit
from agr.tool import ToolConfig


def build_skill_prompt(
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


def check_tool_cli(tool_config: ToolConfig) -> None:
    """Verify the tool's CLI is available, exiting with a clear error otherwise."""
    cli_cmd = tool_config.cli_command
    if not cli_cmd:
        error_exit(f"{tool_config.name} has no CLI command configured")
    if shutil.which(cli_cmd) is None:
        error_exit(f"{cli_cmd} CLI not found.", hint=tool_config.install_hint)


def build_skill_command(
    tool_config: ToolConfig,
    skill_prompt: str,
    *,
    non_interactive: bool,
) -> list[str]:
    """Build the command to run a skill with the selected tool."""
    has_interactive_prompt = (
        tool_config.cli_interactive_prompt_flag
        or tool_config.cli_interactive_prompt_positional
    )
    exec_cmd = tool_config.cli_exec_command
    if exec_cmd and (non_interactive or not has_interactive_prompt):
        cmd = list(exec_cmd)
    else:
        cli_cmd = tool_config.cli_command
        if cli_cmd is None:
            error_exit(f"{tool_config.name} has no CLI command configured")
        cmd = [cli_cmd]
    if not non_interactive and tool_config.cli_interactive_prompt_flag:
        cmd.extend([tool_config.cli_interactive_prompt_flag, skill_prompt])
    elif not non_interactive and tool_config.cli_interactive_prompt_positional:
        cmd.append(skill_prompt)
    elif tool_config.cli_prompt_flag:
        cmd.extend([tool_config.cli_prompt_flag, skill_prompt])
    else:
        cmd.append(skill_prompt)
    return cmd


def run_skill_command(
    tool_config: ToolConfig,
    skill_prompt: str,
    *,
    interactive: bool,
) -> None:
    """Build and execute the skill command with the selected tool."""
    cmd = build_skill_command(
        tool_config,
        skill_prompt,
        non_interactive=not interactive,
    )
    if interactive and tool_config.cli_force_flag:
        cmd.append(tool_config.cli_force_flag)

    if not interactive and tool_config.suppress_stderr_non_interactive:
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
