"""agr add command implementation."""

from pathlib import Path

from agr.commands import CommandResult
from agr.commands._tool_helpers import load_existing_config, save_and_summarize_results
from agr.commands.migrations import run_tool_migrations
from agr.config import DEPENDENCY_TYPE_RALPH, DEPENDENCY_TYPE_SKILL, Dependency
from agr.console import get_console
from agr.exceptions import (
    INSTALL_ERROR_TYPES,
    AgrError,
    RalphNotFoundError,
    SkillNotFoundError,
    format_install_error,
)
from agr.fetcher import (
    InstallResult,
    fetch_and_install_ralph,
    fetch_and_install_to_tools,
    list_remote_repo_skills,
)
from agr.handle import ParsedHandle, parse_handle
from agr.lockfile import (
    LockedSkill,
    Lockfile,
    build_lockfile_path,
    load_lockfile,
    save_lockfile,
    update_lockfile_entry,
)
from agr.ralph import is_valid_ralph_dir
from agr.skill import is_valid_skill_dir
from agr.source import SourceResolver


def _detect_local_type(source_path: Path) -> str:
    """Detect whether a local path is a skill or ralph.

    Checks for RALPH.md and SKILL.md markers. If both exist,
    raises an error. If neither exists, defaults to skill (existing behaviour).
    """
    has_ralph = is_valid_ralph_dir(source_path)
    has_skill = is_valid_skill_dir(source_path)

    if has_ralph and has_skill:
        raise AgrError(
            f"'{source_path}' contains both SKILL.md and RALPH.md. "
            "A directory can only be one type. Remove one marker file."
        )
    if has_ralph:
        return DEPENDENCY_TYPE_RALPH
    return DEPENDENCY_TYPE_SKILL


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
    # Track install results for lockfile: (handle, ref, install_result, dep_type)
    lockfile_updates: list[tuple[ParsedHandle, str, InstallResult, str]] = []

    for ref in refs:
        try:
            # Parse handle
            handle = parse_handle(ref, default_owner=config.default_owner)

            if source and handle.is_local:
                raise AgrError("Local dependencies cannot specify a source")

            # Validate explicit source if provided
            if source:
                resolver.get(source)

            # Auto-detect type and install
            if handle.is_local:
                source_path = handle.resolve_local_path(repo_root)
                dep_type = _detect_local_type(source_path)

                # Reject a second local dependency with the same name but
                # different path — they would collide in the installed dir.
                for existing in config.dependencies:
                    if (
                        existing.is_local
                        and existing.type == dep_type
                        and existing.identifier != ref
                        and Path(existing.identifier).name == handle.name
                    ):
                        raise AgrError(
                            f"A local {dep_type} named '{handle.name}' is "
                            f"already installed from '{existing.identifier}' — "
                            f"only one local {dep_type} with the same name is "
                            f"allowed. Remove the existing one first with: "
                            f"agr remove {existing.identifier}"
                        )
            else:
                dep_type = DEPENDENCY_TYPE_SKILL  # default, may change below

            if handle.is_local and dep_type == DEPENDENCY_TYPE_SKILL:
                # Local skill — install directly to tools
                installed_paths_dict, install_result = fetch_and_install_to_tools(
                    handle,
                    repo_root,
                    tools,
                    overwrite,
                    resolver=resolver,
                    source=source,
                    skills_dirs=skills_dirs,
                    default_repo=config.default_repo,
                )
                installed_paths = [
                    f"{name}: {path}" for name, path in installed_paths_dict.items()
                ]
            elif handle.is_local:
                # Local ralph — install to project ralphs directory
                installed_path, install_result = fetch_and_install_ralph(
                    handle,
                    repo_root,
                    overwrite,
                    resolver=resolver,
                    source=source,
                    default_repo=config.default_repo,
                )
                installed_paths = [str(installed_path)]
            else:
                # Remote — try as skill first, fall back to ralph
                try:
                    installed_paths_dict, install_result = fetch_and_install_to_tools(
                        handle,
                        repo_root,
                        tools,
                        overwrite,
                        resolver=resolver,
                        source=source,
                        skills_dirs=skills_dirs,
                        default_repo=config.default_repo,
                    )
                    installed_paths = [
                        f"{name}: {path}" for name, path in installed_paths_dict.items()
                    ]
                    dep_type = DEPENDENCY_TYPE_SKILL
                except SkillNotFoundError:
                    try:
                        installed_path, install_result = fetch_and_install_ralph(
                            handle,
                            repo_root,
                            overwrite,
                            resolver=resolver,
                            source=source,
                            default_repo=config.default_repo,
                        )
                        installed_paths = [str(installed_path)]
                        dep_type = DEPENDENCY_TYPE_RALPH
                    except RalphNotFoundError:
                        # Neither skill nor ralph found
                        raise SkillNotFoundError(
                            f"'{handle.name}' not found as a skill or ralph "
                            f"in any configured source."
                        ) from None

            # Add to config
            if handle.is_local:
                path_value = ref
                if global_install and handle.local_path is not None:
                    path_value = str(handle.resolve_local_path())
                config.add_dependency(
                    Dependency(
                        type=dep_type,
                        path=path_value,
                    )
                )
            else:
                config.add_dependency(
                    Dependency(
                        type=dep_type,
                        handle=handle.to_toml_handle(),
                        source=source,
                    ),
                    also_matches=[ref],
                )

            # For local global installs, use the resolved path (same as the
            # dependency identifier) so the lockfile stays consistent with
            # agr.toml.  For everything else the raw ref is correct.
            lockfile_ref = path_value if handle.is_local else ref
            lockfile_updates.append((handle, lockfile_ref, install_result, dep_type))
            results.append(CommandResult(ref, True, ", ".join(installed_paths)))

        except SkillNotFoundError as e:
            message = _maybe_suggest_repo_skills(ref, handle, resolver, source)
            results.append(CommandResult(ref, False, message or str(e)))
        except INSTALL_ERROR_TYPES as e:
            results.append(CommandResult(ref, False, format_install_error(e)))

    def _print_add_result(result: CommandResult) -> None:
        if result.success:
            console.print(f"[green]Added:[/green] {result.ref}")
            console.print(f"  [dim]Installed to {result.message}[/dim]", soft_wrap=True)
        else:
            console.print(f"[red]Failed:[/red] {result.ref}")
            console.print(f"  [dim]{result.message}[/dim]", soft_wrap=True)

    save_and_summarize_results(
        results,
        config,
        config_path,
        action="added",
        total=len(refs),
        print_result=_print_add_result,
    )

    # Update lockfile with install results
    if lockfile_updates:
        lockfile_path = build_lockfile_path(config_path)
        lockfile = load_lockfile(lockfile_path) or Lockfile()
        for handle, ref, install_result, dep_type in lockfile_updates:
            is_ralph = dep_type == DEPENDENCY_TYPE_RALPH
            if handle.is_local:
                update_lockfile_entry(
                    lockfile,
                    LockedSkill(path=ref, installed_name=handle.name),
                    ralph=is_ralph,
                )
            else:
                update_lockfile_entry(
                    lockfile,
                    LockedSkill(
                        handle=handle.to_toml_handle(),
                        source=install_result.source_name,
                        commit=install_result.commit,
                        content_hash=install_result.content_hash,
                        installed_name=handle.name,
                    ),
                    ralph=is_ralph,
                )
        save_lockfile(lockfile, lockfile_path)


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
