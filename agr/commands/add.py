"""agr add command implementation."""

from agr.commands import CommandResult
from agr.commands._tool_helpers import load_existing_config, save_and_summarize_results
from agr.commands.migrations import run_tool_migrations
from agr.config import DEPENDENCY_TYPE_SKILL, Dependency
from agr.console import get_console
from agr.exceptions import (
    INSTALL_ERROR_TYPES,
    AgrError,
    SkillNotFoundError,
    format_install_error,
)
from agr.fetcher import fetch_and_install_to_tools, list_remote_repo_skills
from agr.handle import ParsedHandle, parse_handle
from agr.source import SourceResolver


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
    loaded = load_existing_config(global_install, create_if_missing=True)
    config, config_path = loaded.config, loaded.config_path
    tools, repo_root, skills_dirs = loaded.tools, loaded.repo_root, loaded.skills_dirs

    resolver = config.get_source_resolver()
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
                        type=DEPENDENCY_TYPE_SKILL,
                        path=path_value,
                    )
                )
            else:
                config.add_dependency(
                    Dependency(
                        type=DEPENDENCY_TYPE_SKILL,
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

    def _print_add_result(result: CommandResult) -> None:
        if result.success:
            console.print(f"[green]Added:[/green] {result.ref}")
            console.print(f"  [dim]Installed to {result.message}[/dim]")
        else:
            console.print(f"[red]Failed:[/red] {result.ref}")
            console.print(f"  [dim]{result.message}[/dim]")

    save_and_summarize_results(
        results,
        config,
        config_path,
        action="added",
        total=len(refs),
        print_result=_print_add_result,
    )


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
