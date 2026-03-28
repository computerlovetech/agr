"""Unit tests for the exceptions module."""

from agr.exceptions import (
    AgrError,
    AuthenticationError,
    CacheError,
    ConfigError,
    InvalidHandleError,
    InvalidLocalPathError,
    RateLimitError,
    RepoNotFoundError,
    SkillNotFoundError,
    format_install_error,
)


class TestFormatInstallError:
    """Tests for format_install_error()."""

    def test_agr_error_shown_directly(self):
        exc = AgrError("something went wrong")
        assert format_install_error(exc) == "something went wrong"

    def test_agr_error_subclasses_shown_directly(self):
        for cls in (
            RepoNotFoundError,
            AuthenticationError,
            SkillNotFoundError,
            ConfigError,
            InvalidHandleError,
            InvalidLocalPathError,
            CacheError,
            RateLimitError,
        ):
            exc = cls(f"{cls.__name__} message")
            assert format_install_error(exc) == f"{cls.__name__} message"

    def test_file_exists_error_shown_directly(self):
        exc = FileExistsError("skill already exists")
        assert format_install_error(exc) == "skill already exists"

    def test_os_error_gets_unexpected_prefix(self):
        exc = OSError("disk full")
        assert format_install_error(exc) == "Unexpected: disk full"

    def test_value_error_gets_unexpected_prefix(self):
        exc = ValueError("bad value")
        assert format_install_error(exc) == "Unexpected: bad value"

    def test_generic_exception_gets_unexpected_prefix(self):
        exc = RuntimeError("boom")
        assert format_install_error(exc) == "Unexpected: boom"
