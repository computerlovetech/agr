# Log

## Iteration 1 — Feature-flag foundation + installer guard (2026-06-07)

**Shipped (Option A: foundation only):**

- New `agr/features.py`: env-var-backed feature-flag registry.
  - `feature_enabled(name)` resolves a feature from a name→env-var map
    (`ralph → AGR_ENABLE_RALPH`).
  - Truthy parsing: `1`/`true`/`yes`/`on`, case-insensitive, whitespace-stripped;
    unset or anything else is off. Unknown feature name raises `KeyError`.
- Defense-in-depth guard in `fetch_and_install_ralph`
  (`agr/ralph_installer.py`): when `feature_enabled("ralph")` is false it raises
  `RalphNotFoundError(handle.name)` before any install work — no message
  mentions a flag/feature/env var (no leakage).
- Tests:
  - `tests/test_features.py` — set/unset/truthy/non-truthy resolution + unknown
    feature.
  - `tests/test_ralph_installer.py::TestFetchAndInstallRalphFeatureGate` —
    flag-off blocks install with no leakage; flag-on installs as today.
  - `tests/conftest.py` — autouse `enable_ralph_feature` fixture sets
    `AGR_ENABLE_RALPH=1` by default so the suite reflects "flag on = today's
    behaviour"; off-path tests unset it explicitly.

**Acceptance criteria covered:** 1, 2, 7, 8 (local path), and the slice of 10/11
that applies (flag resolution + installer guard tests; `pytest`/`ruff`/`ty`
green). `agr`/`agrx` share `agr/features.py`, so unification holds.

**Verification:** `uv run ruff check`, `uv run ty check` pass. Full suite:
1298 passed, 8 skipped. 6 pre-existing failures in `tests/test_docs.py` (missing
`docs/creating.md`/`llms.txt` from the earlier docs-distill commit) — confirmed
present on a clean tree, unrelated to this change.

**Postponed to later iterations (the decision-point gating — Option B remainder):**

- `_detect_local_type` gate so `agr add ./local-ralph` ends in a generic
  not-a-skill error (AC 3).
- Remote skill→ralph fallback skip in `_install_dependency` (AC 4).
- Package-expansion silent ralph skip (AC 5).
- `agr sync` silent ralph skip (AC 6).
- Leakage audit across those off-path branches (AC 9).

Note: the installer guard currently raises `RalphNotFoundError`, which the remote
add fallback catches and then tries package — that is acceptable backstop
behaviour, but the primary non-leaking semantics for AC 3–6 still need the
decision-point gates above.
