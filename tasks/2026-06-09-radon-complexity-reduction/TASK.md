## Task

Reduce cyclomatic complexity and improve maintainability in the `agr` codebase's hotspot functions, guided by radon metrics, and add a CI gate (xenon) to prevent regressions. The work is decomposition/refactor only — no behavior changes.

## Relevant Codebase

Radon baseline (run via `uvx radon cc agr/ agrx/ -a -s` and `uvx radon mi`):
- **Overall**: 419 blocks, avg CC **A (3.9)**; every file MI grade **A**. Healthy baseline.
- **Worst functions**:
  - `run_remove` — `agr/commands/remove.py:209` — **CC 36 (E)**, the single biggest outlier.
  - `_install_package` — `agr/commands/add.py:225` — **CC 21 (D)**.
  - `detect_conflicts` — `agr/package.py:229` — CC 19 (C); `expand_packages` `agr/package.py:127` — CC 15 (C).
  - `_run_install_pipeline` — `agr/commands/sync.py:748` — CC 17 (C), plus six more C-grade functions in the same file.
  - `_parse_dependencies_from_doc` `agr/config.py:346` (15) and `AgrConfig.save` `agr/config.py:558` (14).
  - `run_config_add` `agr/commands/config_cmd.py:281` (15); `run_list` `agr/commands/list.py:65` (14); `run_add` `agr/commands/add.py:391` (14); `_migrate_skills_directory` `agr/commands/migrations.py:48` (15).
- **Lowest MI files**: `agr/commands/sync.py` 19.3, `agr/commands/config_cmd.py` 29.7, `agr/config.py` 29.9, `agr/commands/add.py` 37.9.
- **Largest file**: `agr/commands/sync.py` — **946 SLOC**, ~2× the next largest.

How it works / patterns to follow:
- Commands live under `agr/commands/`, each exposing a `run_*` orchestrator that delegates to private helpers and returns a `CommandResult` (`agr/commands/__init__.py`). `sync.py` already models good decomposition: `_classify_dependencies` → `_run_install_pipeline` with `_ClassifiedDeps`/`SyncResult` dataclasses. New extractions should mirror this seam-based style.
- `run_remove` already has helpers available to lean on: `_transitive_leaf_entries_for_packages`, `_nested_package_entries_for_packages`, `_find_dep_by_candidates`, `_uninstall_from_filesystem`, `_update_lockfile_after_remove`.
- Per `agr/CLAUDE.md`: agr and agrx stay unified; add/remove should remain symmetric; include tests for what's implemented; tooling is `uv run` (pytest, ruff, ty) and `mkdocs build --strict` for docs.

Integration points: config parsing/serialization round-trips through `agr/config.py` (TOML, comment/order preservation); `package.py` conflict logic runs on every add/sync (high blast radius).

## Goal

The hotspot functions are decomposed into smaller, individually testable units with no D/E-grade functions remaining (target: no function above CC 10, i.e. grade ≤ B), `sync.py` is split into focused modules, and CI fails if new code reintroduces high complexity — all with existing behavior unchanged.

## Acceptance Criteria

1. `run_remove` (`agr/commands/remove.py`) is refactored to CC ≤ 10, splitting resolution → filesystem-uninstall → lockfile-update phases, with a per-branch test matrix (local/remote, package/leaf, transitive cleanup).
2. `_install_package` (`agr/commands/add.py`) is refactored to CC ≤ 10, keeping add/remove handling symmetric; tests cover local-vs-remote and conflict/duplicate branches.
3. `agr/commands/sync.py` is split into focused modules (e.g. classify / pipeline / lockfile) with `run_sync` as a thin entry point; the largest resulting file is materially smaller than 946 SLOC and its MI grade improves from the 19.3 baseline.
4. `detect_conflicts` and `expand_packages` (`agr/package.py`) are each refactored to CC ≤ 10.
5. The config parser/serializer hotspots (`_parse_dependencies_from_doc`, `AgrConfig.save` in `agr/config.py`) are refactored to CC ≤ 10, with golden-file round-trip tests asserting parse→save→parse identity (including comment/order preservation).
6. Remaining C-grade command functions (`run_config_add`, `run_list`, `run_add`, `_migrate_skills_directory`) are reduced to grade ≤ B.
7. A xenon complexity gate runs in CI alongside ruff/ty (e.g. `uvx xenon --max-absolute B --max-modules B --max-average A agr agrx`), tightened to its final thresholds only after criteria 1–6 land.
8. `uv run pytest`, `uv run ruff check .`, and `uv run ty check` all pass; no observable CLI behavior changes for `agr`/`agrx`.

## Scope

### In scope
- Refactoring the named hotspot functions and splitting `sync.py`.
- Adding/expanding unit tests for the refactored code paths and config round-trips.
- Adding the xenon CI gate.

### Out of scope
- Any change to CLI behavior, command surface, or `agr.toml`/`agr.lock` formats.
- Raising comment density / docstring coverage (4% C%L baseline is acceptable for this idiom).
- Refactoring functions already at grade ≤ B that aren't named above.
- New features.

## Risks

- **`run_remove` (CC 36)** has many interacting branches (transitive/nested package cleanup, lockfile sync); easy to drop an edge case — lean on existing helpers and lock behavior with tests before refactoring.
- **`sync.py` split** is the highest-blast-radius structural change; import cycles and the lockfile-build path are the fragile spots. Do it after the smaller wins, on a clear runway.
- **Config round-trip** refactors risk breaking TOML comment/ordering preservation — golden-file identity tests are the safety net.
- **`package.py`** conflict logic runs on every add/sync; regressions are high-impact.
- xenon thresholds must be staged (start lenient, tighten last) or CI will be red mid-effort.
