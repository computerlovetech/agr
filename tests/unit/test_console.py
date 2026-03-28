"""Unit tests for agr.console module."""

import pytest

from agr.console import (
    error_exit,
    get_console,
    print_deprecation,
    print_error,
    set_quiet,
)


class TestSetQuietAndGetConsole:
    """Tests for set_quiet() and get_console() interaction."""

    def setup_method(self):
        """Reset quiet mode before each test."""
        set_quiet(False)

    def teardown_method(self):
        """Reset quiet mode after each test."""
        set_quiet(False)

    def test_default_console_not_quiet(self):
        console = get_console()
        assert console.quiet is False

    def test_set_quiet_true(self):
        set_quiet(True)
        console = get_console()
        assert console.quiet is True

    def test_set_quiet_false_after_true(self):
        set_quiet(True)
        set_quiet(False)
        console = get_console()
        assert console.quiet is False

    def test_get_console_returns_cached_instance(self):
        c1 = get_console()
        c2 = get_console()
        assert c1 is c2

    def test_set_quiet_invalidates_cache(self):
        c1 = get_console()
        set_quiet(True)
        c2 = get_console()
        assert c1 is not c2


class TestPrintError:
    """Tests for print_error()."""

    def setup_method(self):
        set_quiet(False)

    def teardown_method(self):
        set_quiet(False)

    def test_print_error_outputs_message(self, capsys):
        print_error("something went wrong")
        output = capsys.readouterr().out
        assert "something went wrong" in output

    def test_print_error_contains_error_label(self, capsys):
        print_error("test message")
        output = capsys.readouterr().out
        assert "Error" in output


class TestErrorExit:
    """Tests for error_exit()."""

    def setup_method(self):
        set_quiet(False)

    def teardown_method(self):
        set_quiet(False)

    def test_exits_with_code_1(self):
        with pytest.raises(SystemExit) as exc_info:
            error_exit("fatal error")
        assert exc_info.value.code == 1

    def test_prints_message_before_exit(self, capsys):
        with pytest.raises(SystemExit):
            error_exit("fatal error")
        output = capsys.readouterr().out
        assert "fatal error" in output

    def test_prints_hint_when_provided(self, capsys):
        with pytest.raises(SystemExit):
            error_exit("bad input", hint="Try again with --force")
        output = capsys.readouterr().out
        assert "Try again with --force" in output

    def test_no_hint_when_omitted(self, capsys):
        with pytest.raises(SystemExit):
            error_exit("bad input")
        output = capsys.readouterr().out
        assert "bad input" in output


class TestPrintDeprecation:
    """Tests for print_deprecation()."""

    def setup_method(self):
        set_quiet(False)

    def teardown_method(self):
        set_quiet(False)

    def test_prints_old_and_new_commands(self, capsys):
        print_deprecation("agr tools add", "agr config add tools")
        output = capsys.readouterr().out
        assert "agr tools add" in output
        assert "agr config add tools" in output

    def test_prints_warning_label(self, capsys):
        print_deprecation("old-cmd", "new-cmd")
        output = capsys.readouterr().out
        assert "Warning" in output

    def test_prints_deprecated_label(self, capsys):
        print_deprecation("old-cmd", "new-cmd")
        output = capsys.readouterr().out
        assert "deprecated" in output
