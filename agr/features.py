"""Environment-variable-backed feature flags.

A small registry maps feature names to the environment variables that enable
them. A feature is *off* unless its env var is set to a recognised truthy
value. The registry keeps adding a new gated feature to a single line.

Truthy values (case-insensitive, surrounding whitespace ignored):
``1``, ``true``, ``yes``, ``on``. Anything else — including unset — is off.
"""

import os

# Feature name -> environment variable that enables it.
_FEATURE_ENV_VARS: dict[str, str] = {
    "ralph": "AGR_ENABLE_RALPH",
}

# Recognised truthy env-var values (compared lowercase, stripped).
_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def _is_truthy(value: str | None) -> bool:
    """Return True if an env-var value counts as enabling a feature."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


def feature_enabled(name: str) -> bool:
    """Return whether the named feature is enabled via its env var.

    Raises:
        KeyError: if ``name`` is not a registered feature.
    """
    env_var = _FEATURE_ENV_VARS[name]
    return _is_truthy(os.environ.get(env_var))
