# Iteration Log — radon-complexity-reduction

## Iteration 1 — Refactor `run_remove` to CC ≤ B (AC #1)

**Shipped.** Decomposed the worst complexity outlier, `run_remove`
(`agr/commands/remove.py`), from **CC 36 (grade E)** to **CC 2 (A)** with no behavior
change.

### What changed
- Extracted the per-`ref` loop body into focused helpers, all grade ≤ B:
  - `_RefRemoval` dataclass — per-ref outcome (result + parallel candidate/kind lists).
  - `_resolve_dep` — parse handle, build identifier candidates, find matching dep.
  - `_remove_leaf_from_filesystem` / `_remove_from_filesystem` — filesystem removal,
    fanning out to package children.
  - `_nested_packages_to_remove` / `_transitive_leaves_to_remove` / `_resolve_package_cleanup`
    — package child resolution (split so each stays ≤ B).
  - `_uninstall_transitive_entries`, `_remove_from_config`, `_build_removal`, `_process_ref`.
- `run_remove` is now a thin loop: collect `_process_ref` results → flatten → summarize →
  `_update_lockfile_after_remove`.
- Reused all pre-existing helpers; no logic changes.

### Tests
- Added `TestResolvePackageCleanup` (transitive leaf, nested package, shared-child
  retention, no-lockfile) and `TestProcessRef` (not-found, leaf removal, package
  transitive scheduling) to `tests/unit/test_remove.py`.
- Existing `run_remove` integration tests retained as the behavior-preservation net.

### Verification
- `uvx radon cc agr/commands/remove.py -s`: no function above grade B (largest now B 9,
  `_update_lockfile_after_remove`, pre-existing).
- `uv run pytest`: 1310 passed, 6 skipped.
- `uv run ruff check` / `ruff format --check` / `uv run ty check`: clean.
- Smoke: `agr --help`, `agr remove --help` OK.

### Next up
AC #4 + #5 (package.py / config.py hotspots) is the natural next slice; sync.py split
(#3) and xenon gate (#7) remain last per staged-risk ordering.
