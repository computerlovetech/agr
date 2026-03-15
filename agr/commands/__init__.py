"""Command implementations for agr CLI."""

from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of a single command operation (add, remove, etc.)."""

    ref: str
    success: bool
    message: str
