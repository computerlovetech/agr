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

## Iteration 2 — Decision-point gates (2026-06-07)

**Shipped (the Option B remainder — primary gates at every ralph-install
decision point):**

- `agr/commands/add.py`:
  - `_detect_local_type`: `has_ralph = is_valid_ralph_dir(...) and
    feature_enabled("ralph")`. Off → a `RALPH.md` dir (and a both-markers dir)
    resolves to skill and falls through to the existing not-a-skill error; no
    "contains both" raise, no flag mention (AC 3).
  - `_install_dependency`: remote skill→ralph fallback wrapped in
    `if feature_enabled("ralph")`. Off → skill→package only, normal not-found
    (AC 4).
  - `_install_package`: `if dep.is_ralph and not feature_enabled("ralph"):
    continue` before dispatch — ralph leaves dropped silently, non-ralph leaves
    install as today (AC 5).
- `agr/commands/sync.py`:
  - `_classify_dependencies`: ralph dep with flag off → `SyncResult.up_to_date()`
    and `continue` (never enters `pending_ralph`, prints nothing) (AC 6).
  - `_sync_one_dependency` (locked path): ralph dep with flag off returns
    `up_to_date()` before any clone/install work (AC 6).
- Leakage audit (AC 9): no user-facing strings added; off-paths reuse existing
  generic errors and silent up-to-date results. Only "gated"/"flag" words are
  code comments.

**Tests:**
- `tests/unit/test_add.py`: `TestDetectLocalTypeFeatureGate` (ralph dir → skill
  off / ralph on; both-markers no raise off) + off-path remote-fallback-skip and
  package-ralph-leaf-skip tests asserting `fetch_and_install_ralph` not called.
- `tests/unit/test_sync.py` (new): `_classify_dependencies` ralph skipped
  silently + skill still queued when off; ralph queued when on.

**Acceptance criteria covered:** 3, 4, 5, 6, 9, and the remainder of 10/11. With
iteration 1 this closes the full task.

**Verification:** `uv run ruff check .`, `uv run ruff format --check`, `uv run ty
check` pass. `uv run pytest`: 1308 passed, 5 skipped. Same 6 pre-existing
`tests/test_docs.py` failures (missing `docs/creating.md`/`llms.txt`), unrelated.
`agr`/`agrx` both consume `agr.features`, so unification holds.

## Iteration 3 — Contributor doc for the feature-flag registry (2026-06-07)

**Shipped (polish; the task's ACs were already fully covered by iterations 1–2):**

- New `docs/contributing/feature-flags.md`: explains the env-var registry, the
  truthy-value set, how to add a new gated feature (one-line registry entry +
  decision-point gates + defense-in-depth guard), and the "keep a dark feature
  dark" rules (no leakage, gate at the right altitude, silent skips). Uses ralph
  as the worked example with links to the gated files.
- `mkdocs.yml`: added `contributing/**` to `exclude_docs` so the note ships in
  the repo for contributors but is **not** published to agr.run — keeping the
  ralph feature dark for end users (no public mention of `AGR_ENABLE_RALPH`).

**Verification:** `uv run mkdocs build --strict` succeeds; `site/contributing/`
is absent, confirming the doc is excluded from the published site. No code
changed, so the test suite is unaffected (the 6 pre-existing `tests/test_docs.py`
failures remain out of scope).

This makes the "adding a second flag is one line" promise discoverable for
contributors and closes out the task.
