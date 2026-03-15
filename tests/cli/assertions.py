"""Fluent assertion helpers for CLI testing."""

from __future__ import annotations

import re

from tests.cli.runner import CLIResult


class CLIAssertions:
    """Fluent assertions for CLI results."""

    def __init__(self, result: CLIResult):
        self.result = result

    def _format_error(self, message: str) -> str:
        """Format error message with context."""
        return (
            f"{message}\n\n"
            f"Command: {' '.join(self.result.args)}\n"
            f"Exit code: {self.result.returncode}\n"
            f"Stdout:\n{self.result.stdout or '  (empty)'}\n"
            f"Stderr:\n{self.result.stderr or '  (empty)'}"
        )

    def succeeded(self) -> CLIAssertions:
        """Assert command exited with code 0."""
        assert self.result.returncode == 0, self._format_error(
            f"Expected success (exit code 0), got {self.result.returncode}"
        )
        return self

    def failed(self) -> CLIAssertions:
        """Assert command exited with non-zero code."""
        assert self.result.returncode != 0, self._format_error(
            "Expected failure (non-zero exit code), got 0"
        )
        return self

    def exit_code(self, expected: int) -> CLIAssertions:
        """Assert specific exit code."""
        assert self.result.returncode == expected, self._format_error(
            f"Expected exit code {expected}, got {self.result.returncode}"
        )
        return self

    def stdout_contains(self, text: str) -> CLIAssertions:
        """Assert stdout contains text."""
        assert text in self.result.stdout, self._format_error(
            f"Expected stdout to contain: {text!r}"
        )
        return self

    def stdout_not_contains(self, text: str) -> CLIAssertions:
        """Assert stdout does not contain text."""
        assert text not in self.result.stdout, self._format_error(
            f"Expected stdout NOT to contain: {text!r}"
        )
        return self

    def stdout_equals(self, expected: str) -> CLIAssertions:
        """Assert stdout equals text exactly."""
        assert self.result.stdout == expected, self._format_error(
            f"Expected stdout to equal:\n{expected!r}"
            f"\n\nActual:\n{self.result.stdout!r}"
        )
        return self

    def stdout_matches(self, pattern: str) -> CLIAssertions:
        """Assert stdout matches regex pattern."""
        assert re.search(pattern, self.result.stdout), self._format_error(
            f"Expected stdout to match pattern: {pattern}"
        )
        return self

    def stdout_is_empty(self) -> CLIAssertions:
        """Assert stdout is empty."""
        assert self.result.stdout == "", self._format_error(
            "Expected stdout to be empty"
        )
        return self

    def stderr_contains(self, text: str) -> CLIAssertions:
        """Assert stderr contains text."""
        assert text in self.result.stderr, self._format_error(
            f"Expected stderr to contain: {text!r}"
        )
        return self

    def stderr_not_contains(self, text: str) -> CLIAssertions:
        """Assert stderr does not contain text."""
        assert text not in self.result.stderr, self._format_error(
            f"Expected stderr NOT to contain: {text!r}"
        )
        return self

    def stderr_is_empty(self) -> CLIAssertions:
        """Assert stderr is empty."""
        assert self.result.stderr == "", self._format_error(
            "Expected stderr to be empty"
        )
        return self


def assert_cli(result: CLIResult) -> CLIAssertions:
    """Create fluent assertions for a CLI result."""
    return CLIAssertions(result)
