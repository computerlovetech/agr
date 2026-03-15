"""agr onboard command — interactive guided setup."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.prompt import Confirm, Prompt

from agr.config import AgrConfig, Dependency, find_config, find_repo_root
from agr.console import get_console, print_error
from agr.detect import detect_tools
from agr.instructions import canonical_instruction_file, detect_instruction_files
from agr.metadata import read_skill_metadata
from agr.skill import (
    discover_all_skill_dirs,
    get_skill_frontmatter_name,
    is_valid_skill_dir,
)
from agr.tool import DEFAULT_TOOL_NAMES, TOOLS


@dataclass(frozen=True)
class DiscoveredSkill:
    """Discovered skill metadata."""

    name: str
    path: Path
    frontmatter_name: str | None
    tool: str | None


def discover_skills(repo_root: Path) -> list[DiscoveredSkill]:
    """Discover all skills in the repository."""
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


def select_skills(
    discovered: list[DiscoveredSkill],
) -> list[DiscoveredSkill]:
    """Deduplicate skills, keeping the shallowest path for each name."""
    grouped: dict[str, list[DiscoveredSkill]] = {}
    for skill in discovered:
        grouped.setdefault(skill.name, []).append(skill)

    selected: list[DiscoveredSkill] = []
    for name, skills in grouped.items():
        if len(skills) == 1:
            selected.append(skills[0])
        else:
            picked = min(skills, key=lambda s: len(s.path.parts))
            selected.append(picked)
    selected.sort(key=lambda s: s.name)
    return selected


def format_dep_path(repo_root: Path, skill_path: Path) -> str:
    """Format a skill path as a relative dependency path."""
    try:
        rel = skill_path.relative_to(repo_root)
    except ValueError:
        return str(skill_path)
    rel_posix = rel.as_posix()
    if not rel_posix.startswith("."):
        rel_posix = f"./{rel_posix}"
    return rel_posix


def migrate_skill(skill: DiscoveredSkill, skills_root: Path) -> Path | None:
    """Copy a skill to the skills/ directory.

    Returns:
        The destination path if migration succeeded (or dest already valid),
        None if dest exists but is not a valid skill directory.
    """
    dest_dir = skills_root / skill.name
    if dest_dir.exists():
        if is_valid_skill_dir(dest_dir):
            return dest_dir
        return None

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill.path, dest_dir)
    return dest_dir


def _parse_number_selection(input_str: str, max_val: int) -> list[int]:
    """Parse comma-separated number selection like '1,3' into indices."""
    if not input_str.strip():
        return []
    result = []
    for part in input_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            num = int(part)
            if 1 <= num <= max_val:
                result.append(num)
        except ValueError:
            continue
    return list(dict.fromkeys(result))


def run_onboard(*, no_migrate: bool = False) -> None:
    """Run the interactive onboard command."""
    console = get_console()

    # TTY check (bypass with _AGR_FORCE_TTY=1 for testing)
    if not sys.stdin.isatty() and not os.environ.get("_AGR_FORCE_TTY"):
        print_error("agr onboard requires an interactive terminal.")
        console.print("[dim]Use 'agr init' for non-interactive setup.[/dim]")
        raise SystemExit(1)

    # Find repo root
    repo_root = find_repo_root() or Path.cwd()

    # Load existing config or start fresh
    config_path = find_config(repo_root)
    if config_path:
        config = AgrConfig.load(config_path)
        console.print(f"[dim]Found existing config:[/dim] {config_path}")
    else:
        config = AgrConfig()
        config_path = repo_root / "agr.toml"

    # ── Step 1: Tools ──
    console.print()
    console.print("[bold]Step 1: Tools[/bold]")
    console.print("[dim]Which AI coding tools do you use?[/dim]")
    console.print()

    detected = detect_tools(repo_root)
    all_tool_names = list(TOOLS.keys())

    # Determine defaults: existing config tools, or detected, or none
    if config.tools and config.tools != list(DEFAULT_TOOL_NAMES):
        default_indices = [
            i + 1 for i, name in enumerate(all_tool_names) if name in config.tools
        ]
    elif detected:
        default_indices = [
            i + 1 for i, name in enumerate(all_tool_names) if name in detected
        ]
    else:
        default_indices = []

    for i, name in enumerate(all_tool_names, 1):
        markers = []
        if name in detected:
            markers.append("detected")
        if config.tools and name in config.tools:
            markers.append("configured")
        suffix = f" ({', '.join(markers)})" if markers else ""
        console.print(f"  {i}. {name}{suffix}")

    default_str = ",".join(str(i) for i in default_indices) if default_indices else ""
    selection = Prompt.ask(
        f"\nSelect tools [default: {default_str}]" if default_str else "\nSelect tools",
        default=default_str,
    )

    if selection.strip():
        selected_indices = _parse_number_selection(selection, len(all_tool_names))
        selected_tools = [all_tool_names[i - 1] for i in selected_indices]
    elif default_indices:
        selected_tools = [all_tool_names[i - 1] for i in default_indices]
    else:
        selected_tools = ["claude"]

    if not selected_tools:
        selected_tools = ["claude"]

    config.tools = selected_tools
    console.print(f"[green]Tools:[/green] {', '.join(selected_tools)}")

    # ── Step 2: Skills ──
    console.print()
    console.print("[bold]Step 2: Skills[/bold]")
    console.print("[dim]Discovering skills in repository...[/dim]")

    all_discovered = discover_skills(repo_root)
    if not all_discovered:
        console.print("[dim]No skills found in repository.[/dim]")
        selected_skills: list[DiscoveredSkill] = []
    else:
        deduplicated = select_skills(all_discovered)
        console.print(f"[dim]Found {len(deduplicated)} skill(s):[/dim]")
        console.print()

        for i, skill in enumerate(deduplicated, 1):
            rel_path = format_dep_path(repo_root, skill.path)
            tool_note = f" [in {skill.tool}]" if skill.tool else ""
            console.print(f"  {i}. {skill.name} ({rel_path}){tool_note}")

        default_skill_str = ",".join(str(i) for i in range(1, len(deduplicated) + 1))
        skill_selection = Prompt.ask(
            f"\nSelect skills to register [default: {default_skill_str}]",
            default=default_skill_str,
        )

        if skill_selection.strip():
            skill_indices = _parse_number_selection(skill_selection, len(deduplicated))
            selected_skills = [deduplicated[i - 1] for i in skill_indices]
        else:
            selected_skills = list(deduplicated)

        if selected_skills:
            console.print(f"[green]Selected:[/green] {len(selected_skills)} skill(s)")

        # Migration offer for tool-folder skills (skip remote-installed ones)
        def _is_migratable(skill: DiscoveredSkill) -> bool:
            if not skill.tool:
                return False
            meta = read_skill_metadata(skill.path)
            return meta is None or meta.get("type") != "remote"

        tool_folder_skills = [s for s in selected_skills if _is_migratable(s)]
        if tool_folder_skills and not no_migrate:
            console.print()
            console.print(
                f"[yellow]Note:[/yellow] "
                f"{len(tool_folder_skills)} skill(s) "
                "are in tool folders "
                "(e.g. .claude/skills/)."
            )
            should_migrate = Confirm.ask(
                "Move them to ./skills/ (recommended)?", default=True
            )

            if should_migrate:
                skills_root = repo_root / "skills"
                migrated_skills: list[DiscoveredSkill] = []
                migrate_count = 0
                for skill in selected_skills:
                    if _is_migratable(skill):
                        old_path = skill.path
                        dest_existed = (skills_root / skill.name).exists()
                        dest_dir = migrate_skill(skill, skills_root)
                        if dest_dir is None:
                            console.print(
                                f"  [yellow]Skipping:[/yellow] "
                                f"{skills_root / skill.name} "
                                "exists and is not a "
                                "valid skill"
                            )
                            migrated_skills.append(skill)
                            continue
                        migrated_skills.append(
                            DiscoveredSkill(
                                name=skill.name,
                                path=dest_dir,
                                frontmatter_name=skill.frontmatter_name,
                                tool=None,
                            )
                        )
                        migrate_count += 1
                        # Remove old skill from tool folder only if we actually copied
                        if not dest_existed and old_path.exists():
                            try:
                                shutil.rmtree(old_path)
                            except OSError:
                                console.print(
                                    "  [yellow]Warning:[/yellow] "
                                    f"Failed to remove {old_path}"
                                )
                    else:
                        migrated_skills.append(skill)
                selected_skills = migrated_skills
                console.print(
                    f"[green]Migrated:[/green] {migrate_count} skill(s) to ./skills/"
                )

    # ── Step 3: Defaults ──
    if len(selected_tools) > 1:
        console.print()
        console.print("[bold]Step 3: Defaults[/bold]")

        # Default tool
        default_tool_choice = Prompt.ask(
            "Default tool",
            choices=selected_tools,
            default=selected_tools[0],
        )
        config.default_tool = default_tool_choice

        # Instruction sync
        instruction_files = detect_instruction_files(repo_root)
        if len(instruction_files) > 1:
            config.sync_instructions = Confirm.ask(
                "Sync instruction files on agr sync?", default=False
            )
            if config.sync_instructions:
                config.canonical_instructions = canonical_instruction_file(
                    config.default_tool
                )

    # ── Step 4: Summary + Confirm ──
    console.print()
    console.print("[bold]Summary[/bold]")
    console.print(f"  Config:  {config_path}")
    console.print(f"  Tools:   {', '.join(config.tools)}")
    if config.default_tool:
        console.print(f"  Default: {config.default_tool}")
    if selected_skills:
        console.print(f"  Skills:  {len(selected_skills)}")
        for skill in selected_skills:
            rel = format_dep_path(repo_root, skill.path)
            console.print(f"    - {skill.name} ({rel})")
    if config.sync_instructions:
        console.print(f"  Sync:    {config.canonical_instructions} → others")

    console.print()
    if not Confirm.ask("Proceed?", default=True):
        console.print("[dim]Aborted. No changes made.[/dim]")
        return

    # ── Write config ──
    # Add skill dependencies
    existing_ids = {dep.identifier for dep in config.dependencies}
    for skill in selected_skills:
        dep_path = format_dep_path(repo_root, skill.path)
        if dep_path in existing_ids:
            continue
        config.add_dependency(Dependency(type="skill", path=dep_path))
        existing_ids.add(dep_path)

    config.save(config_path)
    console.print(f"[green]Saved:[/green] {config_path}")
    console.print("[dim]Next: agr sync[/dim]")
