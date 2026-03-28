"""Shared console factory supporting --quiet flag."""

from typing import NoReturn

from rich.console import Console

_quiet = False
_console: Console | None = None


def set_quiet(value: bool) -> None:
    """Set global quiet mode."""
    global _quiet, _console
    _quiet = value
    _console = None  # Invalidate cached instance


def get_console() -> Console:
    """Get a cached Console instance respecting the global quiet setting."""
    global _console
    if _console is None:
        _console = Console(quiet=_quiet)
    return _console


def print_error(message: str) -> None:
    """Print a styled error message to the console."""
    get_console().print(f"[red]Error:[/red] {message}")


def error_exit(message: str, *, hint: str | None = None) -> NoReturn:
    """Print a styled error message and exit with code 1.

    Replaces the common ``print_error(msg); raise SystemExit(1)`` pattern.
    An optional *hint* is displayed on the next line in dim style.
    """
    print_error(message)
    if hint:
        get_console().print(f"[dim]{hint}[/dim]")
    raise SystemExit(1)


def print_deprecation(old_cmd: str, new_cmd: str) -> None:
    """Print a styled deprecation warning to the console."""
    get_console().print(
        f"[yellow]Warning:[/yellow] '{old_cmd}' is deprecated. Use '{new_cmd}'.",
        soft_wrap=True,
    )
