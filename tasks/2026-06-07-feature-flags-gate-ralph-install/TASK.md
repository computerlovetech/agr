## Task

Introduce a general, reusable feature-flag mechanism for `agr`, resolved from
environment variables, and make "installing ralph loops" the first feature
behind it. By default the flag is off and ralph installation is invisible: any
attempt to install a ralph behaves as if ralphs aren't a concept — a generic
not-found, with no hint that a flag exists. The system is built as a small
registry so adding a second flag later is a one-line change.

## Relevant Codebase

The slice this touches is the dependency-install machinery. There is **no
existing feature-flag or env-var gating system** today — config comes entirely
from `agr.toml` via `AgrConfig` (`agr/config.py`), and the only env-var reads in
the codebase are incidental (`$EDITOR` in `agr/commands/config_cmd.py`, git
helpers in `agr/git.py`). This is net-new.

**Ralph is a first-class dependency type but installs through several paths:**

- **Type constant & predicate**: `DEPENDENCY_TYPE_RALPH = "ralph"`
  (`agr/config.py:44`); `Dependency.is_ralph` (`agr/config.py:244`).
- **Single install choke point**: `fetch_and_install_ralph`
  (`agr/ralph_installer.py`) — called from **add.py** (`add.py:166`, `:196`,
  `:276`) and **sync.py** (`sync.py:478`, `:919`).
- **Local type detection**: `_detect_local_type` (`agr/commands/add.py:64`)
  returns `DEPENDENCY_TYPE_RALPH` when a local dir contains `RALPH.md`
  (`is_valid_ralph_dir`, `agr/ralph.py:22`).
- **Remote skill→ralph fallback**: `_install_dependency`
  (`agr/commands/add.py:176-208`) tries skill first, then falls back to ralph,
  then package.
- **Package expansion**: `_install_package` installs ralph-typed transitive
  deps in its loop (`agr/commands/add.py:275`).
- **Sync**: installs ralph deps already pinned in `agr.toml`/lockfile
  (`agr/commands/sync.py:538`, `:607`, `:894-919`); existence check via
  `is_ralph_installed` (`agr/ralph_installer.py:347`).

**How it works (control flow):** `agr add <ref>` → `run_add`
(`add.py:387`) → per-ref `parse_handle` → type detection (local via
`_detect_local_type`, remote defaults to skill) → `_install_dependency` →
ralph branch calls `fetch_and_install_ralph`. `agr sync` reads deps from
`agr.toml`/lockfile and dispatches each by `dep.is_ralph` to the same installer.

**Patterns to follow:**
- New runtime config is read in small dedicated modules with focused functions
  (mirror the style of `agr/config.py` helpers).
- Errors raised via `agr/exceptions.py` types; user-facing messaging through
  `agr/console.py` (`error_exit`, `get_console`).
- Keep runtime deps minimal; prefer stdlib (per `CLAUDE.md`).
- `agr` and `agrx` must stay unified/synced; tests required for new behavior;
  no external services or API keys in tests.

**Integration points:** the gate consumes the new feature-flag module and is
applied at the ralph type-detection and install decision points listed above.
Removal (`agr remove`), upgrade (`agr upgrade`), listing (`agr list`), and
*running* ralphs are unaffected.

## Goal

A user who has not set the ralph feature env var experiences `agr` as if ralph
installation does not exist: `agr add`, `agr sync`, and package expansion never
install a ralph, and nothing in the output reveals that a hidden feature or flag
is involved. A user who sets the env var gets today's full ralph-install
behavior back, unchanged. Adding a second gated feature later requires only
registering its name and env var.

## Acceptance Criteria

1. A reusable feature-flag module exists (e.g. `agr/features.py`) exposing a way
   to check whether a named feature is enabled (e.g. `feature_enabled("ralph")`),
   resolved from an environment variable via a name→env-var registry.
2. Env-var truthiness is parsed consistently (documented set of truthy values,
   e.g. `1`/`true`/`yes`, case-insensitive); unset or non-truthy means off.
3. With the flag **off** (default), `agr add ./local-ralph` (a dir containing
   `RALPH.md`) does NOT install a ralph — `_detect_local_type` does not return
   the ralph type, and the command ends in a generic not-found/not-a-skill
   error with no mention of any flag.
4. With the flag **off**, `agr add owner/repo/x` (remote) skips the skill→ralph
   fallback entirely (skill→package only) and produces a normal not-found error
   with no mention of any flag.
5. With the flag **off**, `agr add <package>` whose expansion contains ralph
   deps installs the non-ralph leaves and skips the ralph leaves silently.
6. With the flag **off**, `agr sync` with ralph deps pinned in
   `agr.toml`/lockfile skips them silently and installs the rest.
7. Defense-in-depth: `fetch_and_install_ralph` cannot install a ralph when the
   flag is off, regardless of caller.
8. With the flag **on**, every path above installs ralphs exactly as it does
   today (no behavior change).
9. No user-facing error or output text, in any off-path, reveals the existence
   of the flag or feature.
10. Tests cover: flag resolution (set/unset/truthy/non-truthy values); each
    install path blocked when off and working when on; package-skip and
    sync-skip behavior; and absence of flag-related leakage in error text.
11. `agr` and `agrx` remain unified; `uv run pytest`, `uv run ruff check .`,
    and `uv run ty check` pass.

## Scope

### In scope
- A general env-var-backed feature-flag system with a registry.
- Gating all ralph **install** paths: local add, remote add fallback, package
  expansion, and sync — plus a guard at `fetch_and_install_ralph`.
- Silent/not-found off-behavior with no flag leakage.
- Tests for the above.

### Out of scope
- `agr.toml`-based flag configuration (env var only for now).
- Gating non-install ralph operations: `agr remove`, `agr upgrade`,
  `agr list` rendering, and *running* ralphs.
- Gating any feature other than ralph install (system is reusable, but ralph is
  the only consumer in this task).

## Risks

- **Multiple choke points, not one.** Correct "silent not-found" semantics need
  the gate at the *type-detection / fallback* decision points (so errors read
  naturally), not only as a raise inside `fetch_and_install_ralph`. A single
  hard raise there would produce wrong error semantics (e.g. the remote add
  fallback catches `RalphNotFoundError` then tries package). The installer
  guard is defense-in-depth, not the primary gate.
- **Leakage of flag existence.** Off-path error/help text must be audited so no
  message hints at the flag — easy to miss in fallback or skip branches.
- **Two small details to settle during implementation** (left open by design):
  (a) for sync/package, silent skip (the chosen assumption) vs. a one-line
  warning; (b) the exact env var name (e.g. `AGR_ENABLE_RALPH`) and the precise
  truthy-value set.
- **agr/agrx sync.** Ensure the flag check is reachable/consistent across both
  CLIs per the repo's unification rule.
