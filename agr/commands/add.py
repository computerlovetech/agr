"""agr add command implementation."""

from dataclasses import dataclass
from pathlib import Path

from agr.commands import CommandResult
from agr.commands._tool_helpers import load_existing_config, save_and_summarize_results
from agr.commands.migrations import run_tool_migrations
from agr.config import (
    DEPENDENCY_TYPE_PACKAGE,
    DEPENDENCY_TYPE_RALPH,
    DEPENDENCY_TYPE_SKILL,
    AgrConfig,
    Dependency,
)
from agr.console import get_console
from agr.exceptions import (
    INSTALL_ERROR_TYPES,
    AgrError,
    RalphNotFoundError,
    SkillNotFoundError,
    format_install_error,
)
from agr._install_common import InstallResult
from agr.package import detect_conflicts, expand_packages, has_package_section
from agr.ralph_installer import fetch_and_install_ralph
from agr.skill_installer import fetch_and_install_to_tools, list_remote_repo_skills
from agr.handle import ParsedHandle, parse_handle
from agr.lockfile import (
    LockedEntry,
    Lockfile,
    build_lockfile_path,
    load_lockfile,
    normalize_parent_ids,
    save_lockfile,
)
from agr.ralph import is_valid_ralph_dir
from agr.skill import is_valid_skill_dir
from agr.source import SourceResolver
from agr.tool import ToolConfig


@dataclass
class AddInstallResult:
    """Result of installing one requested dependency."""

    installed_paths: list[str]
    install_result: InstallResult
    dep_type: str
    lock_entries: list[tuple[str, LockedEntry]] | None = None


def _print_add_result(result: CommandResult) -> None:
    """Print a styled result line for a single add operation."""
    console = get_console()
    if result.success:
        console.print(f"[green]Added:[/green] {result.ref}")
        console.print(f"  [dim]Installed to {result.message}[/dim]", soft_wrap=True)
    else:
        console.print(f"[red]Failed:[/red] {result.ref}")
        console.print(f"  [dim]{result.message}[/dim]", soft_wrap=True)


def _detect_local_type(source_path: Path) -> str:
    """Detect whether a local path is a skill, ralph, or package.

    Checks for RALPH.md and SKILL.md markers first (they take priority).
    If neither marker exists, checks for a [package] section in agr.toml.
    If nothing matches, defaults to skill (existing behaviour).
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
    if has_skill:
        return DEPENDENCY_TYPE_SKILL
    if has_package_section(source_path):
        return DEPENDENCY_TYPE_PACKAGE
    return DEPENDENCY_TYPE_SKILL


def _check_local_name_unique(
    handle: ParsedHandle,
    dep_type: str,
    ref: str,
    existing_deps: list[Dependency],
) -> None:
    """Reject a second local dependency with the same name but different path.

    Two local deps with the same name would collide in the installed directory.
    """
    for existing in existing_deps:
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


def _install_dependency(
    handle: ParsedHandle,
    dep_type: str,
    repo_root: Path | None,
    tools: list[ToolConfig],
    overwrite: bool,
    resolver: SourceResolver,
    source: str | None,
    skills_dirs: dict[str, Path] | None,
    default_repo: str | None,
    *,
    config: AgrConfig | None = None,
) -> AddInstallResult:
    """Install a dependency and return paths, metadata, and resolved type.

    For local deps, installs directly as the detected type. For remote deps,
    tries as skill first then falls back to ralph. For packages, expands
    transitive deps and installs each leaf.

    Returns:
        Tuple of (formatted install paths, install metadata, dependency type).
    """
    if dep_type == DEPENDENCY_TYPE_PACKAGE:
        return _install_package(
            handle,
            repo_root,
            tools,
            overwrite,
            resolver,
            source,
            skills_dirs,
            default_repo,
            config=config,
        )

    if handle.is_local and dep_type == DEPENDENCY_TYPE_SKILL:
        installed_paths_dict, install_result = fetch_and_install_to_tools(
            handle,
            repo_root,
            tools,
            overwrite,
            resolver=resolver,
            source=source,
            skills_dirs=skills_dirs,
            default_repo=default_repo,
        )
        installed_paths = [
            f"{name}: {path}" for name, path in installed_paths_dict.items()
        ]
        return AddInstallResult(installed_paths, install_result, dep_type)

    if handle.is_local:
        installed_path, install_result = fetch_and_install_ralph(
            handle,
            repo_root,
            overwrite,
            resolver=resolver,
            source=source,
            default_repo=default_repo,
        )
        return AddInstallResult([str(installed_path)], install_result, dep_type)

    # Remote — try as skill first, fall back to ralph.
    try:
        installed_paths_dict, install_result = fetch_and_install_to_tools(
            handle,
            repo_root,
            tools,
            overwrite,
            resolver=resolver,
            source=source,
            skills_dirs=skills_dirs,
            default_repo=default_repo,
        )
        installed_paths = [
            f"{name}: {path}" for name, path in installed_paths_dict.items()
        ]
        return AddInstallResult(installed_paths, install_result, DEPENDENCY_TYPE_SKILL)
    except SkillNotFoundError:
        pass

    try:
        installed_path, install_result = fetch_and_install_ralph(
            handle,
            repo_root,
            overwrite,
            resolver=resolver,
            source=source,
            default_repo=default_repo,
        )
        return AddInstallResult(
            [str(installed_path)], install_result, DEPENDENCY_TYPE_RALPH
        )
    except RalphNotFoundError:
        pass

    return _install_package(
        handle,
        repo_root,
        tools,
        overwrite,
        resolver,
        source,
        skills_dirs,
        default_repo,
        config=config,
    )


def _install_package(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    overwrite: bool,
    resolver: SourceResolver,
    source: str | None,
    skills_dirs: dict[str, Path] | None,
    default_repo: str | None,
    *,
    config: AgrConfig | None = None,
) -> AddInstallResult:
    """Expand a package and install its transitive leaf deps."""
    if config is None:
        config = AgrConfig()

    pkg_dep = Dependency(
        type=DEPENDENCY_TYPE_PACKAGE,
        handle=handle.to_toml_handle() if handle.is_remote else None,
        path=str(handle.local_path) if handle.is_local else None,
        source=source,
    )
    expanded = expand_packages(
        [pkg_dep],
        resolver,
        config.default_source,
        config.default_owner,
        config.default_repo,
    )
    direct_ids = {dep.identifier for dep in config.dependencies}
    direct_ids.add(pkg_dep.identifier)
    direct_leaf_deps = [dep for dep in config.dependencies if not dep.is_package]
    resolved_deps = detect_conflicts(
        [*direct_leaf_deps, *expanded.dependencies], expanded.parents, direct_ids
    )
    resolved_keys = {(dep.type, dep.identifier) for dep in resolved_deps}
    direct_leaf_keys = {(dep.type, dep.identifier) for dep in direct_leaf_deps}
    expanded.dependencies = [
        dep
        for dep in expanded.dependencies
        if (dep.type, dep.identifier) in resolved_keys
        and (dep.type, dep.identifier) not in direct_leaf_keys
    ]

    installed_paths: list[str] = []
    first_result: InstallResult | None = None
    lock_entries: list[tuple[str, LockedEntry]] = [
        (DEPENDENCY_TYPE_PACKAGE, entry) for entry in expanded.package_entries
    ]
    for dep in expanded.dependencies:
        sub_handle = dep.to_parsed_handle(config.default_owner)
        sub_source = dep.resolve_source_name(config.default_source)
        if dep.is_ralph:
            path, result = fetch_and_install_ralph(
                sub_handle,
                repo_root,
                overwrite,
                resolver=resolver,
                source=sub_source,
                default_repo=default_repo,
            )
            installed_paths.append(str(path))
        else:
            paths_dict, result = fetch_and_install_to_tools(
                sub_handle,
                repo_root,
                tools,
                overwrite,
                resolver=resolver,
                source=sub_source,
                skills_dirs=skills_dirs,
                default_repo=default_repo,
            )
            installed_paths.extend(
                f"{name}: {path}" for name, path in paths_dict.items()
            )
        if first_result is None:
            first_result = result
        parent, parents = normalize_parent_ids(expanded.parent_ids_for(dep.identifier))
        if dep.is_local:
            lock_entries.append(
                (
                    dep.type,
                    LockedEntry(
                        path=dep.path,
                        installed_name=dep.installed_name,
                        parent=parent,
                        parents=parents,
                    ),
                )
            )
        else:
            lock_entries.append(
                (
                    dep.type,
                    LockedEntry(
                        handle=dep.handle,
                        source=result.source_name,
                        commit=result.commit,
                        content_hash=result.content_hash,
                        installed_name=dep.installed_name,
                        parent=parent,
                        parents=parents,
                    ),
                )
            )

    if first_result is None:
        first_result = InstallResult()

    return AddInstallResult(
        installed_paths,
        first_result,
        DEPENDENCY_TYPE_PACKAGE,
        lock_entries=lock_entries,
    )


def _update_lockfile_for_adds(
    lockfile_updates: list[
        tuple[
            ParsedHandle, str, InstallResult, str, list[tuple[str, LockedEntry]] | None
        ]
    ],
    config_path: Path,
) -> None:
    """Write install results to the lockfile."""
    if not lockfile_updates:
        return
    lockfile_path = build_lockfile_path(config_path)
    lockfile = load_lockfile(lockfile_path) or Lockfile()
    for handle, ref, install_result, dep_type, entries in lockfile_updates:
        if entries is not None:
            for kind, entry in entries:
                lockfile.update_entry(entry, kind=kind)
            continue
        if handle.is_local:
            lockfile.update_entry(
                LockedEntry(path=ref, installed_name=handle.name),
                kind=dep_type,
            )
        else:
            lockfile.update_entry(
                LockedEntry(
                    handle=handle.to_toml_handle(),
                    source=install_result.source_name,
                    commit=install_result.commit,
                    content_hash=install_result.content_hash,
                    installed_name=handle.name,
                ),
                kind=dep_type,
            )
    save_lockfile(lockfile, lockfile_path)


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
    loaded = load_existing_config(global_install, create_if_missing=True)
    config, config_path = loaded.config, loaded.config_path
    tools, repo_root, skills_dirs = loaded.tools, loaded.repo_root, loaded.skills_dirs

    resolver = config.get_source_resolver()
    run_tool_migrations(tools, repo_root, global_install=global_install)

    # Track results for summary
    results: list[CommandResult] = []
    # Track install results for lockfile: (handle, ref, install_result, dep_type)
    lockfile_updates: list[
        tuple[
            ParsedHandle, str, InstallResult, str, list[tuple[str, LockedEntry]] | None
        ]
    ] = []

    for ref in refs:
        try:
            handle = parse_handle(ref, default_owner=config.default_owner)

            if source and handle.is_local:
                raise AgrError("Local dependencies cannot specify a source")
            if source:
                resolver.get(source)

            # Detect dependency type
            if handle.is_local:
                source_path = handle.resolve_local_path(repo_root)
                dep_type = _detect_local_type(source_path)
                _check_local_name_unique(handle, dep_type, ref, config.dependencies)
            else:
                dep_type = DEPENDENCY_TYPE_SKILL  # default, may change below

            # Install
            install = _install_dependency(
                handle,
                dep_type,
                repo_root,
                tools,
                overwrite,
                resolver,
                source,
                skills_dirs,
                config.default_repo,
                config=config,
            )
            installed_paths = install.installed_paths
            install_result = install.install_result
            dep_type = install.dep_type

            # Add to config
            if handle.is_local:
                path_value = ref
                if global_install and handle.local_path is not None:
                    path_value = str(handle.resolve_local_path())
                config.add_dependency(Dependency(type=dep_type, path=path_value))
            else:
                config.add_dependency(
                    Dependency(
                        type=dep_type,
                        handle=handle.to_toml_handle(),
                        source=source,
                    ),
                    also_matches=[ref],
                )

            # Track for lockfile update
            lockfile_ref = path_value if handle.is_local else ref
            lockfile_updates.append(
                (handle, lockfile_ref, install_result, dep_type, install.lock_entries)
            )
            results.append(CommandResult(ref, True, ", ".join(installed_paths)))

        except SkillNotFoundError as e:
            message = _maybe_suggest_repo_skills(ref, handle, resolver, source)
            results.append(CommandResult(ref, False, message or str(e)))
        except INSTALL_ERROR_TYPES as e:
            results.append(CommandResult(ref, False, format_install_error(e)))

    # Update lockfile before save_and_summarize_results because the latter
    # raises SystemExit(1) on partial failure, which would skip the lockfile
    # write and leave it inconsistent with the config.
    _update_lockfile_for_adds(lockfile_updates, config_path)

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
