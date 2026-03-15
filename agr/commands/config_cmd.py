"""Unified agr config command implementations."""

import os
import shlex
import subprocess
from pathlib import Path

from agr.config import (
    AgrConfig,
    VALID_CANONICAL_INSTRUCTIONS,
    find_repo_root,
    get_global_config_path,
    require_config,
)
from agr.commands._tool_helpers import (
    delete_tool_skills,
    ensure_valid_default_tool,
    normalize_tool_names,
    sync_dependencies_to_tools,
    validate_tool_names,
)
from agr.console import get_console, print_error
from agr.source import DEFAULT_SOURCE_NAME, SourceConfig
from agr.tool import DEFAULT_TOOL_NAMES

VALID_KEYS = {
    "tools",
    "default_tool",
    "default_source",
    "sync_instructions",
    "canonical_instructions",
    "sources",
}

SCALAR_KEYS = {
    "default_tool",
    "default_source",
    "sync_instructions",
    "canonical_instructions",
}
LIST_KEYS = {"tools", "sources"}


def _require_config_path(global_scope: bool) -> Path:
    """Locate the config file path, exiting with a user-facing error if missing."""
    if not global_scope:
        return require_config()

    config_path = get_global_config_path()
    if not config_path.exists():
        console = get_console()
        print_error(f"No global config found at {config_path}")
        console.print("[dim]Run 'agr init' or create it manually.[/dim]")
        raise SystemExit(1)
    return config_path


def _load_config(global_scope: bool) -> tuple[AgrConfig, Path]:
    """Load config for local or global scope."""
    config_path = _require_config_path(global_scope)
    return AgrConfig.load(config_path), config_path


def _validate_key(key: str) -> None:
    """Validate key is in VALID_KEYS, exit with error listing valid keys."""
    console = get_console()
    if key not in VALID_KEYS:
        valid = ", ".join(sorted(VALID_KEYS))
        print_error(f"Unknown config key '{key}'")
        console.print(f"[dim]Valid keys: {valid}[/dim]")
        raise SystemExit(1)


def run_config_show(global_scope: bool) -> None:
    """Print formatted view of effective config."""
    console = get_console()
    config, config_path = _load_config(global_scope)

    console.print(f"[bold]Config:[/bold] {config_path}")
    console.print()
    console.print(f"  tools             = {', '.join(config.tools)}")
    console.print(f"  default_tool      = {config.default_tool or '(not set)'}")
    console.print(f"  default_source    = {config.default_source}")

    if config.sync_instructions is not None:
        console.print(f"  sync_instructions = {str(config.sync_instructions).lower()}")
    else:
        console.print("  sync_instructions = (not set)")

    console.print(
        f"  canonical_instructions = {config.canonical_instructions or '(not set)'}"
    )

    console.print()
    console.print("[bold]Sources:[/bold]")
    for src in config.sources:
        default_marker = " (default)" if src.name == config.default_source else ""
        console.print(f"  - {src.name} [{src.type}] {src.url}{default_marker}")


def run_config_path(global_scope: bool) -> None:
    """Print resolved agr.toml path."""
    print(_require_config_path(global_scope))


def run_config_edit(global_scope: bool) -> None:
    """Open agr.toml in $EDITOR."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        print_error("Neither $VISUAL nor $EDITOR is set.")
        raise SystemExit(1)

    path = _require_config_path(global_scope)

    result = subprocess.run([*shlex.split(editor), str(path)])
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_config_get(key: str, global_scope: bool) -> None:
    """Print a config value."""
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key == "tools":
        print(" ".join(config.tools))
    elif key == "sources":
        for src in config.sources:
            print(f"{src.name} {src.type} {src.url}")
    elif key == "default_tool":
        print(config.default_tool or "(not set)")
    elif key == "default_source":
        print(config.default_source)
    elif key == "sync_instructions":
        if config.sync_instructions is not None:
            print(str(config.sync_instructions).lower())
        else:
            print("(not set)")
    elif key == "canonical_instructions":
        print(config.canonical_instructions or "(not set)")
    else:
        raise AssertionError(f"Unhandled key: {key}")


def run_config_set(key: str, values: list[str], global_scope: bool) -> None:
    """Write a scalar value or replace a list."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key == "sources":
        print_error(
            "Cannot set sources directly. Use "
            "'agr config add sources' and "
            "'agr config remove sources'."
        )
        raise SystemExit(1)

    if key == "tools":
        if not values:
            print_error("At least one tool is required.")
            raise SystemExit(1)
        names = list(dict.fromkeys(normalize_tool_names(values)))
        if not names:
            print_error("At least one tool is required.")
            raise SystemExit(1)
        validate_tool_names(names)
        previous_default = config.default_tool
        previous_tools = list(config.tools)
        config.tools = names
        ensure_valid_default_tool(config, previous_default)
        added = [n for n in names if n not in previous_tools]
        if not global_scope:
            sync_errors = sync_dependencies_to_tools(config, added)
            if sync_errors:
                console.print(
                    f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
                )
                raise SystemExit(1)
        config.save()
        console.print(f"[green]Set:[/green] tools = {', '.join(names)}")
        return

    # Scalar keys expect exactly one value
    if len(values) != 1:
        print_error(f"'{key}' expects exactly one value.")
        raise SystemExit(1)

    value = values[0]

    if key == "default_tool":
        normalized = normalize_tool_names([value])
        if not normalized:
            print_error("Tool name is required.")
            raise SystemExit(1)
        name = normalized[0]
        validate_tool_names([name])
        if name not in config.tools:
            print_error(
                f"Tool '{name}' is not in configured tools. "
                f"Add it first with 'agr config add tools {name}'."
            )
            raise SystemExit(1)
        config.default_tool = name
        config.save()
        console.print(f"[green]Set:[/green] default_tool = {name}")

    elif key == "default_source":
        source_names = [s.name for s in config.sources]
        if value not in source_names:
            print_error(f"Source '{value}' not found in sources list.")
            console.print(f"[dim]Available sources: {', '.join(source_names)}[/dim]")
            raise SystemExit(1)
        config.default_source = value
        config.save()
        console.print(f"[green]Set:[/green] default_source = {value}")

    elif key == "sync_instructions":
        if value.lower() not in ("true", "false"):
            print_error("sync_instructions must be 'true' or 'false'.")
            raise SystemExit(1)
        config.sync_instructions = value.lower() == "true"
        config.save()
        console.print(f"[green]Set:[/green] sync_instructions = {value.lower()}")

    elif key == "canonical_instructions":
        if value not in VALID_CANONICAL_INSTRUCTIONS:
            valid = ", ".join(f"'{v}'" for v in sorted(VALID_CANONICAL_INSTRUCTIONS))
            print_error(f"canonical_instructions must be {valid}.")
            raise SystemExit(1)
        config.canonical_instructions = value
        config.save()
        console.print(f"[green]Set:[/green] canonical_instructions = {value}")

    else:
        raise AssertionError(f"Unhandled key: {key}")


def run_config_unset(key: str, global_scope: bool) -> None:
    """Clear a config value to default/None."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key == "sources":
        print_error("Cannot unset sources. Use 'agr config remove sources <name>'.")
        raise SystemExit(1)

    if key == "tools":
        config.tools = list(DEFAULT_TOOL_NAMES)
        config.save()
        console.print(f"[green]Reset:[/green] tools = {', '.join(DEFAULT_TOOL_NAMES)}")
        return

    if key == "default_tool":
        if config.default_tool is None:
            console.print("[dim]default_tool is already unset.[/dim]")
            return
        config.default_tool = None
        config.save()
        console.print("[green]Unset:[/green] default_tool")

    elif key == "default_source":
        config.default_source = DEFAULT_SOURCE_NAME
        config.save()
        console.print(f"[green]Reset:[/green] default_source = {DEFAULT_SOURCE_NAME}")

    elif key == "sync_instructions":
        if config.sync_instructions is None:
            console.print("[dim]sync_instructions is already unset.[/dim]")
            return
        config.sync_instructions = None
        config.save()
        console.print("[green]Unset:[/green] sync_instructions")

    elif key == "canonical_instructions":
        if config.canonical_instructions is None:
            console.print("[dim]canonical_instructions is already unset.[/dim]")
            return
        config.canonical_instructions = None
        config.save()
        console.print("[green]Unset:[/green] canonical_instructions")

    else:
        raise AssertionError(f"Unhandled key: {key}")


def run_config_add(
    key: str,
    values: list[str],
    source_type: str | None,
    source_url: str | None,
    global_scope: bool,
) -> None:
    """Append to a list config value."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key in SCALAR_KEYS:
        print_error(f"'{key}' is a scalar. Use 'agr config set {key} <value>'.")
        raise SystemExit(1)

    # Reject --type/--url on non-sources keys
    if key != "sources" and (source_type is not None or source_url is not None):
        print_error("--type and --url are only valid for 'sources'.")
        raise SystemExit(1)

    if key == "tools":
        if not values:
            print_error("At least one tool name is required.")
            raise SystemExit(1)
        names = list(dict.fromkeys(normalize_tool_names(values)))
        validate_tool_names(names)

        added: list[str] = []
        skipped: list[str] = []
        for name in names:
            if name in config.tools:
                skipped.append(name)
            else:
                config.tools.append(name)
                added.append(name)

        if not global_scope:
            sync_errors = sync_dependencies_to_tools(config, added)
            if sync_errors:
                console.print(
                    f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
                )
                raise SystemExit(1)
        if added:
            config.save()

        for name in added:
            console.print(f"[green]Added:[/green] {name}")
        for name in skipped:
            console.print(f"[dim]Already configured:[/dim] {name}")

    elif key == "sources":
        if not values:
            print_error("Source name is required.")
            raise SystemExit(1)
        if len(values) > 1:
            print_error("Only one source name allowed at a time.")
            raise SystemExit(1)
        name = values[0]

        if source_type is None:
            source_type = "git"
        if source_type != "git":
            print_error(
                f"Unsupported source type '{source_type}'. Only 'git' is supported."
            )
            raise SystemExit(1)
        if source_url is None:
            print_error("--url is required when adding a source.")
            raise SystemExit(1)

        existing_names = {s.name for s in config.sources}
        if name in existing_names:
            print_error(f"Source '{name}' already exists.")
            raise SystemExit(1)

        config.sources.append(SourceConfig(name=name, type=source_type, url=source_url))
        config.save()
        console.print(
            f"[green]Added source:[/green] {name} [{source_type}] {source_url}"
        )


def run_config_remove(key: str, values: list[str], global_scope: bool) -> None:
    """Remove from a list config value."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key in SCALAR_KEYS:
        print_error(f"'{key}' is a scalar. Use 'agr config unset {key}'.")
        raise SystemExit(1)

    if key == "tools":
        if not values:
            print_error("At least one tool name is required.")
            raise SystemExit(1)
        names = list(dict.fromkeys(normalize_tool_names(values)))
        validate_tool_names(names)

        remaining = [t for t in config.tools if t not in names]
        if not remaining:
            print_error("Cannot remove all tools. At least one must remain.")
            raise SystemExit(1)

        previous_default = config.default_tool
        repo_root = None if global_scope else find_repo_root()

        removed: list[str] = []
        not_configured: list[str] = []
        for name in names:
            if name not in config.tools:
                not_configured.append(name)
                continue
            if not global_scope:
                delete_tool_skills(name, repo_root)
            config.tools.remove(name)
            removed.append(name)

        ensure_valid_default_tool(config, previous_default)
        config.save()

        for name in removed:
            console.print(f"[green]Removed:[/green] {name}")
        for name in not_configured:
            console.print(f"[dim]Not configured:[/dim] {name}")

    elif key == "sources":
        if not values:
            print_error("Source name is required.")
            raise SystemExit(1)
        if len(values) > 1:
            print_error("Only one source name allowed at a time.")
            raise SystemExit(1)
        name = values[0]

        if name == config.default_source:
            print_error(
                f"Cannot remove default source '{name}'. Change default_source first."
            )
            raise SystemExit(1)

        original_len = len(config.sources)
        config.sources = [s for s in config.sources if s.name != name]
        if len(config.sources) == original_len:
            print_error(f"Source '{name}' not found.")
            raise SystemExit(1)

        config.save()
        console.print(f"[green]Removed source:[/green] {name}")
