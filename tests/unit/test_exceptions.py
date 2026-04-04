"""Unit tests for the exceptions module."""

from agr.exceptions import (
    INSTALL_ERROR_TYPES,
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


class TestInstallErrorTypes:
    """Tests for INSTALL_ERROR_TYPES tuple coverage."""

    def test_catches_agr_error_subclasses(self):
        """All AgrError subclasses are caught."""
        for cls in (
            AgrError,
            ConfigError,
            InvalidHandleError,
            InvalidLocalPathError,
            SkillNotFoundError,
            RepoNotFoundError,
            AuthenticationError,
            RateLimitError,
            CacheError,
        ):
            assert issubclass(cls, INSTALL_ERROR_TYPES)

    def test_catches_file_exists_error(self):
        assert issubclass(FileExistsError, INSTALL_ERROR_TYPES)

    def test_catches_permission_error(self):
        assert issubclass(PermissionError, INSTALL_ERROR_TYPES)

    def test_catches_file_not_found_error(self):
        assert issubclass(FileNotFoundError, INSTALL_ERROR_TYPES)

    def test_does_not_catch_generic_value_error(self):
        assert not issubclass(ValueError, INSTALL_ERROR_TYPES)

    def test_does_not_catch_generic_os_error(self):
        assert not issubclass(OSError, INSTALL_ERROR_TYPES)
