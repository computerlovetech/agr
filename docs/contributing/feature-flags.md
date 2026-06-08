# Feature flags

`agr` has a small, env-var-backed feature-flag system for shipping work that
should stay dark by default — code that lands on `main` and is fully tested, but
behaves as if it doesn't exist until an operator opts in.

This page is for contributors. It is **not** part of the published docs site
(it's excluded from the build), so a gated feature stays invisible to users
until you decide to document it.

## How it works

The whole mechanism lives in [`agr/features.py`](https://github.com/computerlovetech/agr/blob/main/agr/features.py):

- A registry maps a **feature name** to the **environment variable** that
  enables it.
- A feature is **off** unless its env var is set to a recognised truthy value:
  `1`, `true`, `yes`, or `on` — case-insensitive, surrounding whitespace
  ignored. Anything else, including unset, is off.
- `feature_enabled(name)` returns the on/off state. An unregistered name raises
  `KeyError` (a programming error, surfaced loudly rather than silently off).

```python
from agr.features import feature_enabled

if feature_enabled("ralph"):
    ...  # gated behaviour
```

Both `agr` and `agrx` import the same module, so a flag resolves identically
across the two CLIs.

## Adding a new gated feature

1. **Register it** — one line in `_FEATURE_ENV_VARS`:

   ```python
   _FEATURE_ENV_VARS: dict[str, str] = {
       "ralph": "AGR_ENABLE_RALPH",
       "my_feature": "AGR_ENABLE_MY_FEATURE",
   }
   ```

2. **Gate the behaviour at every decision point**, not just at one choke point.
   Wrap each branch that turns the feature on in `feature_enabled("my_feature")`.

3. **Add a defense-in-depth guard** at the lowest-level entry point (the
   function that actually does the work), so the feature can't activate even if
   a caller forgets a gate.

## Keeping a dark feature dark

The hard part isn't the flag — it's making the *off* path indistinguishable
from a world where the feature was never built:

- **No leakage.** Off-path errors and help text must never mention the flag, the
  env var, or the feature's name. Reuse the generic errors that already exist
  for "not found" / "unsupported" cases.
- **Gate at the right altitude.** A single hard `raise` deep in the call stack
  can produce the wrong surface behaviour (e.g. a caught exception that triggers
  a fallback). Gate at the *decision* point so the resulting error reads
  naturally, and keep the deep guard only as a backstop.
- **Silent skips.** Where a feature would expand into work (package expansion,
  sync over pinned deps), drop the gated items silently rather than warning —
  a warning reveals that something was skipped.

The ralph-install feature is the worked example: it's gated at local type
detection, the remote install fallback, package expansion, and sync, with a
backstop guard in the installer. See
[`agr/commands/add.py`](https://github.com/computerlovetech/agr/blob/main/agr/commands/add.py),
[`agr/commands/sync.py`](https://github.com/computerlovetech/agr/blob/main/agr/commands/sync.py),
and [`agr/ralph_installer.py`](https://github.com/computerlovetech/agr/blob/main/agr/ralph_installer.py).

## Testing

In tests, set or unset the env var to exercise both states. The suite enables
ralph by default via an autouse fixture in `tests/conftest.py`
(`AGR_ENABLE_RALPH=1`), so existing tests reflect "flag on = today's
behaviour"; off-path tests unset it explicitly. Cover, at minimum: flag
resolution (set/unset/truthy/non-truthy), each gated path blocked when off and
working when on, and the absence of any flag-related text in off-path output.
