"""agr add command implementation."""

from pathlib import Path

from agr.commands import CommandResult
from agr.commands.migrations import run_tool_migrations
from agr.config import (
    AgrConfig,
    Dependency,
    find_config,
    get_or_create_global_config,
    require_repo_root,
)
from agr.console import get_console
from agr.detect import detect_tools
from agr.exceptions import (
    INSTALL_ERROR_TYPES,
    AgrError,
    SkillNotFoundError,
    format_install_error,
)
from agr.fetcher import fetch_and_install_to_tools, list_remote_repo_skills
from agr.handle import ParsedHandle, parse_handle
from agr.source import SourceResolver
from agr.tool import build_global_skills_dirs


def run_add(
    refs: list[str],
    overwrite: bool = False,
    source: str | None = None,
    global_install: bool = False,
) -> None:
    """Run the add command.

    Args:
        refs: List of handles or paths to add
        overwrite: Whether to overwrite existing skills
    """
    console = get_console()
    skills_dirs: dict[str, Path] | None = None
    if global_install:
        repo_root = None
        config_path, config = get_or_create_global_config()
    else:
        repo_root = require_repo_root()

        # Find or create config
        config_path = find_config()
        if config_path is None:
            config_path = repo_root / "agr.toml"
            config = AgrConfig()
            detected = detect_tools(repo_root)
            if detected:
                config.tools = detected
        else:
            config = AgrConfig.load(config_path)

    # Get configured tools
    tools = config.get_tools()
    resolver = config.get_source_resolver()
    if global_install:
        skills_dirs = build_global_skills_dirs(tools)
    run_tool_migrations(tools, repo_root, global_install=global_install)

    # Track results for summary
    results: list[CommandResult] = []

    for ref in refs:
        try:
            # Parse handle
            handle = parse_handle(ref)

            if source and handle.is_local:
                raise AgrError("Local skills cannot specify a source")

            # Validate explicit source if provided
            if source:
                resolver.get(source)

            # Install the skill to all configured tools (downloads once)
            installed_paths_dict = fetch_and_install_to_tools(
                handle,
                repo_root,
                tools,
                overwrite,
                resolver=resolver,
                source=source,
                skills_dirs=skills_dirs,
            )
            installed_paths = [
                f"{name}: {path}" for name, path in installed_paths_dict.items()
            ]

            # Add to config
            if handle.is_local:
                path_value = ref
                if global_install and handle.local_path is not None:
                    path_value = str(handle.resolve_local_path())
                config.add_dependency(
                    Dependency(
                        type="skill",
                        path=path_value,
                    )
                )
            else:
                config.add_dependency(
                    Dependency(
                        type="skill",
                        handle=handle.to_toml_handle(),
                        source=source,
                    )
                )

            results.append(CommandResult(ref, True, ", ".join(installed_paths)))

        except SkillNotFoundError as e:
            message = _maybe_suggest_repo_skills(ref, handle, resolver, source)
            results.append(CommandResult(ref, False, message or str(e)))
        except INSTALL_ERROR_TYPES as e:
            results.append(CommandResult(ref, False, format_install_error(e)))

    # Save config if any successes
    successes = [r for r in results if r.success]
    if successes:
        config.save(config_path)

    # Print results
    for result in results:
        if result.success:
            console.print(f"[green]Added:[/green] {result.ref}")
            console.print(f"  [dim]Installed to {result.message}[/dim]")
        else:
            console.print(f"[red]Failed:[/red] {result.ref}")
            console.print(f"  [dim]{result.message}[/dim]")

    # Summary
    if len(refs) > 1:
        console.print()
        console.print(
            f"[bold]Summary:[/bold] {len(successes)}/{len(refs)} skills added"
        )

    # Exit with error if any failures
    failures = [r for r in results if not r.success]
    if failures:
        raise SystemExit(1)


def _maybe_suggest_repo_skills(
    ref: str,
    handle: ParsedHandle,
    resolver: SourceResolver,
    source: str | None,
) -> str | None:
    """Try to suggest correct handles when a two-part handle fails.

    When a handle like "owner/name" fails (no skill "name" in the default
    "skills" repo), probes "owner/name" as a GitHub repo and lists
    available skills to suggest three-part handles.

    Returns:
        A helpful error message with suggestions, or None to use the default.
    """
    # Only probe for two-part remote handles (no explicit repo)
    if handle.is_local or handle.repo is not None:
        return None

    owner = handle.username
    repo_name = handle.name
    if not owner or not repo_name:
        return None

    try:
        skills = list_remote_repo_skills(owner, repo_name, resolver, source)
    except (AgrError, OSError):
        return None

    if not skills:
        return None

    cleaned_skills = sorted({skill for skill in skills if skill})
    if not cleaned_skills:
        return None

    lines = [
        f"Skill '{repo_name}' not found. "
        f"However, '{owner}/{repo_name}' exists as a repository "
        f"with {len(cleaned_skills)} skill(s):",
        "",
    ]
    for skill in cleaned_skills:
        lines.append(f"  agr add {owner}/{repo_name}/{skill}")
    lines.append("")
    lines.append("Hint: agr handles use the format: owner/repo/skill-name")
    return "\n".join(lines)
