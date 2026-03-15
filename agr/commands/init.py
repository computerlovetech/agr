"""agr init command implementation."""

from __future__ import annotations

from pathlib import Path

from agr.console import get_console, print_error
from agr.config import (
    VALID_CANONICAL_INSTRUCTIONS,
    AgrConfig,
    find_config,
    find_repo_root,
)
from agr.detect import detect_tools
from agr.instructions import canonical_instruction_file
from agr.skill import create_skill_scaffold
from agr.tool import TOOLS, available_tools_string


def init_config(path: Path | None = None) -> tuple[Path, bool]:
    """Initialize agr.toml if it doesn't exist.

    Args:
        path: Directory to create agr.toml in (defaults to cwd)

    Returns:
        Tuple of (config_path, created). created=False if already existed.
    """
    base = path or Path.cwd()
    config_path = base / "agr.toml"

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


def _validate_tools(tools: list[str]) -> None:
    for name in tools:
        if name not in TOOLS:
            raise ValueError(
                f"Unknown tool '{name}'. Available: {available_tools_string()}"
            )


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
            print_error(str(e))
            raise SystemExit(1)
        return

    repo_root = find_repo_root() or Path.cwd()

    config_path, created = init_config(repo_root)
    config = AgrConfig.load(config_path)
    original_tools = list(config.tools)
    original_default_tool = config.default_tool
    original_sync_instructions = config.sync_instructions
    original_canonical_instructions = config.canonical_instructions
    changed = False

    if created:
        console.print(f"[green]Created:[/green] {config_path}")
    else:
        console.print(f"[yellow]Already exists:[/yellow] {config_path}")

    # Tools
    tools_display: list[str] | None = None
    tools_override = _parse_tools_flag(tools)
    if tools_override:
        try:
            _validate_tools(tools_override)
        except ValueError as exc:
            print_error(str(exc))
            raise SystemExit(1)
        config.tools = tools_override
        tools_display = tools_override
        if config.tools != original_tools:
            changed = True
    elif created:
        detected_tools = detect_tools(repo_root)
        if detected_tools:
            config.tools = detected_tools
            tools_display = detected_tools
            if config.tools != original_tools:
                changed = True
    else:
        tools_display = config.tools if config.tools else None

    # Default tool
    if default_tool:
        if default_tool not in TOOLS:
            print_error(
                f"Unknown tool '{default_tool}'. Available: {available_tools_string()}"
            )
            raise SystemExit(1)
        config.default_tool = default_tool
        if config.default_tool != original_default_tool:
            changed = True

    if config.default_tool and config.default_tool not in config.tools:
        print_error("default_tool must be listed in tools. Use --tools to include it.")
        raise SystemExit(1)

    # Instruction sync
    if sync_instructions is not None:
        config.sync_instructions = sync_instructions
        if config.sync_instructions != original_sync_instructions:
            changed = True

    if canonical_instructions:
        if canonical_instructions not in VALID_CANONICAL_INSTRUCTIONS:
            valid = ", ".join(sorted(VALID_CANONICAL_INSTRUCTIONS))
            print_error(f"canonical_instructions must be one of: {valid}")
            raise SystemExit(1)
        config.canonical_instructions = canonical_instructions
        if config.canonical_instructions != original_canonical_instructions:
            changed = True
    elif config.sync_instructions and config.canonical_instructions is None:
        if config.default_tool:
            config.canonical_instructions = canonical_instruction_file(
                config.default_tool
            )
            if config.canonical_instructions != original_canonical_instructions:
                changed = True

    if changed:
        config.save(config_path)

    # Summary
    if tools_display:
        console.print(f"[green]Tools:[/green] {', '.join(tools_display)}")

    console.print("[dim]Next: agr add <handle> or agr onboard[/dim]")
