"""Custom exceptions for agr."""


class AgrError(Exception):
    """Base exception for agr errors."""


class RepoNotFoundError(AgrError):
    """Raised when the remote repo doesn't exist."""


class AuthenticationError(AgrError):
    """Raised when authentication fails for a remote repo."""


class SkillNotFoundError(AgrError):
    """Raised when the skill doesn't exist in the repo."""


class ConfigError(AgrError):
    """Raised when agr.toml has issues (not found or invalid)."""


class InvalidHandleError(AgrError):
    """Raised when a handle cannot be parsed."""


class InvalidLocalPathError(AgrError):
    """Raised when a local skill path is invalid."""


class CacheError(AgrError):
    """Raised when cache operations fail."""


class RateLimitError(AgrError):
    """Raised when GitHub API rate limit is exceeded."""


# Exception types commonly caught during install/sync operations.
# FileExistsError (subclass of OSError) must be listed so that
# format_install_error can distinguish it from unexpected OS errors.
INSTALL_ERROR_TYPES = (FileExistsError, AgrError, OSError, ValueError)


def format_install_error(exc: Exception) -> str:
    """Format an install/sync exception for user-facing output.

    Expected errors (AgrError and its subclasses, FileExistsError) are
    shown directly.  Other errors get an 'Unexpected: ' prefix.
    """
    if isinstance(exc, (AgrError, FileExistsError)):
        return str(exc)
    return f"Unexpected: {exc}"
