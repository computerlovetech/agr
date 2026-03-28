"""agr init command implementation."""

from __future__ import annotations

from pathlib import Path

from agr.console import error_exit, get_console
from agr.config import (
    CONFIG_FILENAME,
    AgrConfig,
    find_config,
    find_repo_root,
    validate_canonical_instructions,
)
from agr.commands._tool_helpers import normalize_and_validate_tool_names
from agr.exceptions import ConfigError
from agr.detect import detect_tools
from agr.instructions import canonical_instruction_file
from agr.skill import create_skill_scaffold


def init_config(path: Path | None = None) -> tuple[Path, bool]:
    """Initialize agr.toml if it doesn't exist.

    Args:
        path: Directory to create agr.toml in (defaults to cwd)

    Returns:
        Tuple of (config_path, created). created=False if already existed.
    """
    base = path or Path.cwd()
    config_path = base / CONFIG_FILENAME

    # Check if config already exists anywhere up the tree
    existing = find_config(base)
    if existing:
        return existing, False

    # Create new config
    config = AgrConfig()
    config.save(config_path)

    return config_path, True


def init_skill(name: str, base_dir: Path | None = None) -> Path:
    """Initialize a new skill scaffold.

    Args:
        name: Name of the skill
        base_dir: Directory to create skill in (defaults to cwd)

    Returns:
        Path to created skill directory

    Raises:
        ValueError: If name is invalid
        FileExistsError: If directory already exists
    """
    return create_skill_scaffold(name, base_dir)


def _parse_tools_flag(value: str | None) -> list[str] | None:
    if value is None:
        return None
    raw = [v.strip() for v in value.split(",") if v.strip()]
    return raw or None


def run_init(
    skill_name: str | None = None,
    *,
    tools: str | None = None,
    default_tool: str | None = None,
    sync_instructions: bool | None = None,
    canonical_instructions: str | None = None,
) -> None:
    """Run the init command.

    Args:
        skill_name: If provided, creates a skill scaffold instead of agr.toml
    """
    console = get_console()

    if skill_name:
        # Create skill scaffold
        try:
            skill_path = init_skill(skill_name)
            console.print(f"[green]Created skill scaffold:[/green] {skill_path}")
            console.print(
                f"  [dim]Edit {skill_path}/SKILL.md to customize your skill[/dim]"
            )
        except (ValueError, FileExistsError) as e:
            error_exit(str(e))
        return

    repo_root = find_repo_root() or Path.cwd()

    config_path, created = init_config(repo_root)
    config = AgrConfig.load(config_path)
    original_state = (
        list(config.tools),
        config.default_tool,
        config.sync_instructions,
        config.canonical_instructions,
    )

    if created:
        console.print(f"[green]Created:[/green] {config_path}")
    else:
        console.print(f"[yellow]Already exists:[/yellow] {config_path}")

    # Tools
    tools_display: list[str] | None = None
    tools_override = _parse_tools_flag(tools)
    if tools_override:
        tools_override = normalize_and_validate_tool_names(tools_override)
        config.tools = tools_override
        tools_display = tools_override
    elif created:
        detected_tools = detect_tools(repo_root)
        if detected_tools:
            config.tools = detected_tools
            tools_display = detected_tools
    else:
        tools_display = config.tools if config.tools else None

    # Default tool
    if default_tool:
        names = normalize_and_validate_tool_names([default_tool])
        config.default_tool = names[0]

    if config.default_tool and config.default_tool not in config.tools:
        error_exit("default_tool must be listed in tools. Use --tools to include it.")

    # Instruction sync
    if sync_instructions is not None:
        config.sync_instructions = sync_instructions

    if canonical_instructions:
        try:
            validate_canonical_instructions(canonical_instructions)
        except ConfigError as exc:
            error_exit(str(exc))
        config.canonical_instructions = canonical_instructions
    elif config.sync_instructions and config.canonical_instructions is None:
        if config.default_tool:
            config.canonical_instructions = canonical_instruction_file(
                config.default_tool
            )

    current_state = (
        list(config.tools),
        config.default_tool,
        config.sync_instructions,
        config.canonical_instructions,
    )
    if current_state != original_state:
        config.save(config_path)

    # Summary
    if tools_display:
        console.print(f"[green]Tools:[/green] {', '.join(tools_display)}")

    console.print("[dim]Next: agr add <handle> or agr onboard[/dim]")
