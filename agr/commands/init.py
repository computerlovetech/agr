"""agr init command implementation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from agr.config import AgrConfig, Dependency, find_config, find_repo_root
from agr.instructions import canonical_instruction_file, detect_instruction_files
from agr.skill import (
    create_skill_scaffold,
    discover_all_skill_dirs,
    get_skill_frontmatter_name,
    is_valid_skill_dir,
)
from agr.tool import TOOLS

console = Console()


@dataclass(frozen=True)
class DiscoveredSkill:
    """Discovered skill metadata."""

    name: str
    path: Path
    frontmatter_name: str | None
    tool: str | None


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


def _detect_tools(repo_root: Path) -> list[str]:
    detected: list[str] = []
    for name, tool in TOOLS.items():
        skills_dir = tool.get_skills_dir(repo_root)
        if skills_dir.exists():
            detected.append(name)
    return detected


def _discover_skills(repo_root: Path) -> list[DiscoveredSkill]:
    skills: list[DiscoveredSkill] = []
    for skill_dir in discover_all_skill_dirs(repo_root):
        tool_name = None
        for name, tool in TOOLS.items():
            skills_dir = tool.get_skills_dir(repo_root)
            if skills_dir in skill_dir.parents:
                tool_name = name
                break
        skills.append(
            DiscoveredSkill(
                name=skill_dir.name,
                path=skill_dir,
                frontmatter_name=get_skill_frontmatter_name(skill_dir),
                tool=tool_name,
            )
        )
    return skills


def _select_skills(
    discovered: list[DiscoveredSkill], prefer: str | None
) -> tuple[list[DiscoveredSkill], dict[str, list[DiscoveredSkill]]]:
    grouped: dict[str, list[DiscoveredSkill]] = {}
    for skill in discovered:
        grouped.setdefault(skill.name, []).append(skill)

    selected: list[DiscoveredSkill] = []
    for name, skills in grouped.items():
        if len(skills) == 1:
            selected.append(skills[0])
            continue
        if prefer == "newest":
            picked = max(skills, key=lambda s: s.path.stat().st_mtime)
        else:
            picked = min(skills, key=lambda s: len(s.path.parts))
        selected.append(picked)
    selected.sort(key=lambda s: s.name)
    return selected, grouped


def _format_dep_path(repo_root: Path, skill_path: Path) -> str:
    try:
        rel = skill_path.relative_to(repo_root)
    except ValueError:
        return str(skill_path)
    rel_posix = rel.as_posix()
    if not rel_posix.startswith("."):
        rel_posix = f"./{rel_posix}"
    return rel_posix


def _migrate_skill(skill: DiscoveredSkill, skills_root: Path) -> Path:
    dest_dir = skills_root / skill.name
    if dest_dir.exists():
        return dest_dir

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill.path, dest_dir)
    return dest_dir


def _parse_tools_flag(value: str | None) -> list[str] | None:
    if value is None:
        return None
    raw = [v.strip() for v in value.split(",") if v.strip()]
    return raw or None


def _validate_tools(tools: list[str]) -> None:
    for name in tools:
        if name not in TOOLS:
            available = ", ".join(TOOLS.keys())
            raise ValueError(f"Unknown tool '{name}'. Available: {available}")


def _normalize_dep_identifier(repo_root: Path, dep: Dependency) -> str:
    if dep.path:
        path = Path(dep.path)
        skill_path = path if path.is_absolute() else repo_root / path
        return _format_dep_path(repo_root, skill_path)
    return dep.identifier


def run_init(
    skill_name: str | None = None,
    *,
    interactive: bool = False,
    tools: str | None = None,
    default_tool: str | None = None,
    sync_instructions: bool | None = None,
    canonical_instructions: str | None = None,
    migrate: bool = False,
    prefer: str | None = None,
) -> None:
    """Run the init command.

    Args:
        skill_name: If provided, creates a skill scaffold instead of agr.toml
    """
    if skill_name:
        # Create skill scaffold
        try:
            skill_path = init_skill(skill_name)
            console.print(f"[green]Created skill scaffold:[/green] {skill_path}")
            console.print(
                f"  [dim]Edit {skill_path}/SKILL.md to customize your skill[/dim]"
            )
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)
        except FileExistsError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)
        return

    if prefer and prefer not in {"newest", "shallowest"}:
        console.print("[red]Error:[/red] --prefer must be 'shallowest' or 'newest'.")
        raise SystemExit(1)

    repo_root = find_repo_root() or Path.cwd()

    config_path, created = init_config(repo_root)
    config = AgrConfig.load(config_path)
    original_tools = list(config.tools)
    original_default_tool = config.default_tool
    original_sync_instructions = config.sync_instructions
    original_canonical_instructions = config.canonical_instructions
    original_dep_ids = {
        _normalize_dep_identifier(repo_root, dep) for dep in config.dependencies
    }
    changed = False

    if created:
        console.print(f"[green]Created:[/green] {config_path}")
    else:
        console.print(f"[yellow]Already exists:[/yellow] {config_path}")

    discovered = _discover_skills(repo_root)
    tool_skills = [skill for skill in discovered if skill.tool]
    repo_skills = [skill for skill in discovered if not skill.tool]
    candidates = discovered if migrate else repo_skills
    selected, grouped = _select_skills(candidates, prefer)

    # Tools
    tools_display: list[str] | None = None
    tools_override = _parse_tools_flag(tools)
    if tools_override:
        try:
            _validate_tools(tools_override)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise SystemExit(1)
        config.tools = tools_override
        tools_display = tools_override
        if config.tools != original_tools:
            changed = True
    elif created:
        detected_tools = _detect_tools(repo_root)
        if detected_tools:
            config.tools = detected_tools
            tools_display = detected_tools
            if config.tools != original_tools:
                changed = True
    else:
        tools_display = config.tools if config.tools else None

    # Default tool (only prompt if multiple tools)
    if default_tool:
        if default_tool not in TOOLS:
            available = ", ".join(TOOLS.keys())
            console.print(
                f"[red]Error:[/red] Unknown tool '{default_tool}'. Available: {available}"
            )
            raise SystemExit(1)
        config.default_tool = default_tool
        if config.default_tool != original_default_tool:
            changed = True
    elif interactive and len(config.tools) > 1 and config.default_tool is None:
        choice = Prompt.ask(
            "Default tool",
            choices=config.tools,
            default=config.tools[0],
        )
        config.default_tool = choice
        if config.default_tool != original_default_tool:
            changed = True

    if config.default_tool and config.default_tool not in config.tools:
        console.print(
            "[red]Error:[/red] default_tool must be listed in tools. "
            "Use --tools to include it."
        )
        raise SystemExit(1)

    # Instruction sync (only when multiple tools + multiple instruction files)
    instruction_files = detect_instruction_files(repo_root)
    if sync_instructions is not None:
        config.sync_instructions = sync_instructions
        if config.sync_instructions != original_sync_instructions:
            changed = True
    elif (
        interactive
        and len(config.tools) > 1
        and len(instruction_files) > 1
        and config.sync_instructions is None
    ):
        config.sync_instructions = Confirm.ask(
            "Sync instruction files on agr sync?", default=False
        )
        if config.sync_instructions != original_sync_instructions:
            changed = True

    if canonical_instructions:
        if canonical_instructions not in {"AGENTS.md", "CLAUDE.md"}:
            console.print(
                "[red]Error:[/red] canonical instructions must be AGENTS.md or CLAUDE.md"
            )
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

    # Optional migration to skills/
    removed_tool_skills = 0
    if migrate:
        skills_root = repo_root / "skills"
        migrated: list[DiscoveredSkill] = []
        for skill in selected:
            dest_dir = skills_root / skill.name
            if dest_dir.exists() and not is_valid_skill_dir(dest_dir):
                console.print(
                    f"[yellow]Skipping migrate:[/yellow] {dest_dir} exists and is not a valid skill"
                )
                migrated.append(skill)
                continue
            dest_dir = _migrate_skill(skill, skills_root)
            migrated.append(
                DiscoveredSkill(
                    name=skill.name,
                    path=dest_dir,
                    frontmatter_name=skill.frontmatter_name,
                    tool=None,
                )
            )
            if skill.tool and skill.path.exists():
                try:
                    shutil.rmtree(skill.path)
                    removed_tool_skills += 1
                except OSError:
                    console.print(
                        f"[yellow]Warning:[/yellow] Failed to remove {skill.path}"
                    )
        selected = migrated

    # Add dependencies for discovered skills (dedup by identifier)
    existing_ids = set(original_dep_ids)
    for skill in selected:
        dep_path = _format_dep_path(repo_root, skill.path)
        if dep_path in existing_ids:
            continue
        config.add_dependency(Dependency(type="skill", path=dep_path))
        existing_ids.add(dep_path)
        changed = True

    if changed:
        config.save(config_path)

    # Recap
    console.print(
        f"[green]Found:[/green] {len(selected)} skills"
        + ("" if not candidates else f" ({len(candidates)} locations)")
    )

    if tools_display:
        console.print(f"[green]Tools:[/green] {', '.join(tools_display)}")

    if tool_skills and not migrate:
        console.print(
            "[yellow]Note:[/yellow] "
            f"Found {len(tool_skills)} skills in tool folders "
            "(.claude/skills, .agents/skills, .cursor/skills, .opencode/skill, .github/skills; legacy Codex: .codex/skills). "
            "Run `agr init --migrate` to move them into ./skills/."
        )

    if removed_tool_skills:
        console.print(
            f"[green]Migrated:[/green] Removed {removed_tool_skills} skills from tool folders"
        )

    duplicate_names = [name for name, items in grouped.items() if len(items) > 1]
    if duplicate_names:
        console.print(
            "[yellow]Warnings:[/yellow] Duplicate skill names: "
            + ", ".join(sorted(duplicate_names))
        )

    frontmatter_issues = [
        skill.name
        for skill in selected
        if skill.frontmatter_name and skill.frontmatter_name != skill.name
    ]
    if frontmatter_issues:
        console.print(
            "[yellow]Warnings:[/yellow] Frontmatter name mismatch: "
            + ", ".join(sorted(frontmatter_issues))
        )

    console.print("[dim]Next: agr sync[/dim]")
