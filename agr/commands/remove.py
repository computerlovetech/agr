"""agr remove command implementation."""

from agr.commands import CommandResult
from agr.commands._tool_helpers import load_existing_config, save_and_summarize_results
from agr.commands.migrations import run_tool_migrations
from agr.console import get_console, print_error
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.fetcher import uninstall_skill
from agr.handle import ParsedHandle, parse_handle
from agr.tool import lookup_skills_dir


def _identifier_candidates(
    ref: str,
    handle: ParsedHandle,
    abs_path_str: str | None,
) -> list[str]:
    """Build ordered list of identifiers to try for dependency lookup/removal.

    Dependencies can be stored under different identifier forms (raw ref,
    local path string, resolved absolute path, or TOML handle).  This
    helper produces the candidates in priority order so callers can stop
    at the first match.
    """
    candidates = [ref]
    if handle.is_local and handle.local_path is not None:
        candidates.append(str(handle.local_path))
    if abs_path_str is not None:
        candidates.append(abs_path_str)
    if not handle.is_local:
        candidates.append(handle.to_toml_handle())
    return list(dict.fromkeys(candidates))


def run_remove(refs: list[str], global_install: bool = False) -> None:
    """Run the remove command.

    Args:
        refs: List of handles or paths to remove
    """
    console = get_console()
    loaded = load_existing_config(global_install)
    config, config_path = loaded.config, loaded.config_path
    tools, repo_root, skills_dirs = loaded.tools, loaded.repo_root, loaded.skills_dirs
    run_tool_migrations(tools, repo_root, global_install=global_install)

    # Track results
    results: list[CommandResult] = []

    for ref in refs:
        try:
            # Parse handle
            handle = parse_handle(ref)

            # Compute the resolved absolute path once for local global installs
            abs_path_str: str | None = None
            if global_install and handle.is_local and handle.local_path is not None:
                abs_path_str = str(handle.resolve_local_path())

            candidates = _identifier_candidates(ref, handle, abs_path_str)

            dep = None
            for identifier in candidates:
                dep = config.get_by_identifier(identifier)
                if dep is not None:
                    break

            source_name = None
            if dep and dep.is_remote:
                source_name = dep.source or config.default_source

            # Remove from filesystem for all configured tools
            removed_fs = False
            for tool in tools:
                if uninstall_skill(
                    handle,
                    repo_root,
                    tool,
                    source_name,
                    skills_dir=lookup_skills_dir(skills_dirs, tool),
                ):
                    removed_fs = True

            # Remove from config (try same candidate identifiers)
            removed_config = False
            for identifier in candidates:
                if config.remove_dependency(identifier):
                    removed_config = True
                    break

            if removed_fs or removed_config:
                results.append(CommandResult(ref, True, "Removed"))
            else:
                results.append(CommandResult(ref, False, "Not found"))

        except INSTALL_ERROR_TYPES as e:
            results.append(CommandResult(ref, False, format_install_error(e)))

    def _print_remove_result(result: CommandResult) -> None:
        if result.success:
            console.print(f"[green]Removed:[/green] {result.ref}")
        elif result.message == "Not found":
            console.print(f"[yellow]Not found:[/yellow] {result.ref}")
        else:
            print_error(result.ref)
            console.print(f"  [dim]{result.message}[/dim]")

    save_and_summarize_results(
        results,
        config,
        config_path,
        action="removed",
        total=len(refs),
        print_result=_print_remove_result,
        exit_on_failure=False,
    )
