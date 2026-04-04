# Architecture Audit

> Date: 2026-04-04 | Codebase: agr v0.8.1 | ~20k lines Python

## Executive Summary

agr is a well-structured, focused package manager for AI agent resources. The codebase demonstrates strong engineering fundamentals: clean separation of concerns, comprehensive test coverage, thoughtful error handling, and good documentation. This audit identifies architectural strengths, areas for improvement, and future directions.

---

## 1. Architecture Assessment

### Strengths

**Clean layered architecture.** The codebase follows a clear dependency hierarchy:

```
CLI (main.py, agrx/main.py)
  → Commands (commands/*.py)
    → Orchestration (fetcher.py)
      → Domain (skill.py, ralph.py, handle.py, config.py, lockfile.py)
        → Infrastructure (git.py, source.py, metadata.py)
```

Each layer has well-defined responsibilities. `fetcher.py` is the natural orchestration point — it coordinates git operations, skill discovery, and installation without leaking details upward.

**Strong domain modeling.** `ParsedHandle`, `Dependency`, `ToolConfig`, `SourceConfig`, and `LockedSkill` are well-designed value objects that encapsulate their invariants. `ParsedHandle` is particularly well-designed — it cleanly separates local vs remote semantics, provides format conversions (`to_toml_handle()`, `to_installed_name()`, `to_skill_path()`), and validates at construction time.

**Tool abstraction.** `ToolConfig` is an excellent extension point. Adding a new AI coding tool requires only a new frozen dataclass instance — no if/else chains, no factory methods. The data-driven design (detection signals, CLI flags, path conventions) means tool-specific behavior is declarative rather than imperative.

**Sync command optimization.** The three-phase sync approach (local → default-repo → batched specific-repo) is well-thought-out. Grouping multiple skills from the same repo into a single git clone is a meaningful performance optimization that shows attention to real-world usage patterns.

**SDK design.** The HuggingFace-style `Skill.from_git()` / `Skill.from_local()` API is clean and intuitive. The cache layer with atomic writes and file locking is production-quality.

### Areas for Improvement

#### 1.1 `fetcher.py` is too large

At 11k+ tokens, `fetcher.py` is the largest module and does too many things: skill installation, ralph installation, skill uninstallation, query operations, repo preparation, sparse checkout coordination, name conflict resolution, and metadata stamping. This makes it the hardest file to reason about.

**Recommendation:** Split into focused modules:
- `installer.py` — install orchestration (skill + ralph)
- `uninstaller.py` — removal logic
- `resolver.py` — name conflict resolution and destination resolution
- Keep `fetcher.py` as a thin facade re-exporting the public API for backward compatibility

#### 1.2 Duplication between skill and ralph

`ralph.py` is almost a line-for-line copy of discovery functions in `skill.py`, just with `RALPH_MARKER` instead of `SKILL_MARKER`. Similarly, `write_skill_metadata` and `write_ralph_metadata` in `metadata.py` differ only in the presence of a `tool` field.

**Recommendation:** Introduce an `Asset` or `Resource` abstraction:
```python
@dataclass(frozen=True)
class ResourceType:
    marker: str          # "SKILL.md" or "RALPH.md"
    name: str            # "skill" or "ralph"
    has_tool_field: bool  # skills are per-tool, ralphs are tool-agnostic
```
Then parameterize discovery and metadata functions on `ResourceType` rather than duplicating.

#### 1.3 Console/output coupling in command logic

Commands like `sync.py` and `add.py` mix business logic with Rich console output. Functions like `_print_results_and_summary` raise `SystemExit(1)` — a UI concern mixed into result handling.

**Recommendation:** Have commands return structured results. Let the CLI layer (or a thin presenter) handle formatting and exit codes. This makes the logic testable without capturing console output and enables the SDK to reuse sync/add logic without console side effects.

#### 1.4 Global mutable state in `console.py`

The `_quiet` flag and `_console` singleton use module-level globals. This makes concurrent usage (e.g., running tests in parallel) unsafe and makes it harder to test.

**Recommendation:** Pass a `Console` instance through the call chain, or use a context variable (`contextvars.ContextVar`).

#### 1.5 `INSTALL_ERROR_TYPES` is a catch-all tuple

```python
INSTALL_ERROR_TYPES = (FileExistsError, AgrError, OSError, ValueError)
```

Catching `OSError` and `ValueError` broadly risks swallowing unexpected errors. This is a known pragmatic trade-off, but it weakens the error hierarchy's value.

**Recommendation:** Replace bare `ValueError` catches with specific `AgrError` subclasses. Narrow `OSError` catches to specific subclasses like `PermissionError` and `FileNotFoundError` where possible.

---

## 2. Code Quality Observations

### Well Done

- **Consistent error hierarchy.** `AgrError` → specialized subclasses. `format_install_error()` provides clean user-facing messages.
- **Validation at boundaries.** `parse_handle()` validates eagerly; `_validate_config_identifier()` prevents injection of separators; `_sanitize_path_component()` in the cache prevents path traversal.
- **Security awareness.** `Skill.read_file()` checks for path traversal. Cache paths are sanitized. Git tokens are injected via credential helpers, not command-line args.
- **Migration support.** The migration system (colon → double-hyphen, full names → plain names, tool directory renames) shows commitment to not breaking existing users.
- **Lockfile design.** The `agr.lock` implementation with `--frozen` and `--locked` modes mirrors modern package manager conventions (npm, uv) and enables reproducible installs.

### Minor Issues

- **`httpx` is a declared dependency but `urllib.request` is used in `sdk/hub.py`.** The SDK uses stdlib `urllib` while the rest of the project declares `httpx`. Pick one — `httpx` is already a dependency, so use it consistently.
- **`pytest-asyncio` is a dev dependency but no async code exists.** Remove it to keep the dev dependency list honest.
- **Type annotations are inconsistent.** Some functions use `| None` (modern), some contexts lack annotations entirely. The `ty check` tool should catch these, but a full pass would improve editor support.

---

## 3. Testing Assessment

The test suite is well-organized across three tiers:

| Tier | Location | Count | Strategy |
|------|----------|-------|----------|
| Unit | `tests/unit/` | ~10 files | Isolated function-level tests |
| Integration | `tests/test_*.py` | ~10 files | Module-level with mocked git |
| CLI E2E | `tests/cli/` | ~20 files | Full CLI invocations via Typer test client |
| SDK | `tests/sdk/` | ~4 files | SDK public API with mocked network |

**Strengths:** The CLI E2E tests are thorough, covering each tool, flag combinations, and error cases. The `conftest.py` fixtures (`git_project`, `skill_fixture`) provide good test infrastructure.

**Gap: No integration tests against real git repos.** All git operations are mocked. Consider a small set of `@pytest.mark.network` tests that clone a known test repo to catch regressions in git sparse checkout, credential handling, etc.

**Gap: No property-based testing.** Handle parsing and skill discovery are good candidates for hypothesis-based tests to find edge cases in path handling.

---

## 4. Suggested Enhancements

### 4.1 Parallel Downloads

Currently `agr sync` processes dependencies sequentially. For repos with 10+ skills across different sources, this is a bottleneck.

**Approach:** Use `concurrent.futures.ThreadPoolExecutor` for git clones (I/O-bound). The results list is already pre-allocated by index, so parallel fill is straightforward. The batching in `_sync_batched_repo_entries` already groups by repo — parallelize across groups.

### 4.2 `agr update` Command

There's no way to update installed skills to newer commits. Users must `agr remove` + `agr add` or delete the skills directory and re-sync.

**Approach:** Compare lockfile commit SHAs against remote HEAD. Show a diff of what would change. Support `agr update <handle>` for selective updates and `agr update --all`.

### 4.3 Dependency Version Constraints

The lockfile pins exact commits, but there's no way to express "use commit X or later" or "pin to tag v1.2". As the ecosystem grows, version constraints will become important.

**Approach:** Add optional `version` or `ref` field to dependencies:
```toml
dependencies = [
    {handle = "anthropics/skills/code-review", type = "skill", ref = "v1.0"},
    {handle = "anthropics/skills/pdf", type = "skill", ref = "main"},
]
```

### 4.4 Skill Integrity Verification

`content_hash` is computed and stored but never verified. A `agr verify` command or a `--verify` flag on sync would close this loop.

### 4.5 Private Source Support

The source system is designed for extensibility (`SourceConfig` with URL templates) but only `git` type is supported. Future types could include:
- **`git+ssh`** — for private repos accessed via SSH keys
- **`local`** — a local directory as a source (mono-repo development)
- **`registry`** — a centralized skill registry with search/versioning

### 4.6 Skill Composition / Dependencies

Skills are currently standalone. As skills become more complex, they may want to depend on other skills (e.g., a "full-stack" skill that composes "frontend" + "backend" + "testing" skills).

**Approach:** A `requires` field in SKILL.md frontmatter:
```yaml
---
name: full-stack
requires:
  - anthropics/skills/frontend
  - anthropics/skills/testing
---
```

### 4.7 SDK Async Support

The SDK uses synchronous HTTP (`urllib.request`) and synchronous git subprocess calls. For integration into async applications (web servers, agent orchestrators), async variants would be valuable.

**Approach:** Since `httpx` is already a dependency and supports async, provide `Skill.async_from_git()` and async hub functions.

### 4.8 Workspace / Monorepo Support

Currently `agr.toml` is found by walking up to the git root. In monorepo setups, teams may want per-directory configs or workspace-level configs that compose.

**Approach:** Support a `[workspace]` section in the root `agr.toml` that references child configs, similar to npm/pnpm workspaces.

---

## 5. Future Architecture Directions

### 5.1 Plugin System for Tools

The current tool registration is compile-time (frozen dataclass instances in `tool.py`). As the AI tool ecosystem grows rapidly, a plugin system would let third parties add tool support without forking agr.

**Approach:** Entry points (`[project.entry-points."agr.tools"]`) that register `ToolConfig` instances. Discover at startup via `importlib.metadata`.

### 5.2 Event Hooks

`agr sync` and `agr add` could emit events (pre-install, post-install, pre-sync, post-sync) that user-defined scripts can hook into. Use cases: running linters after sync, notifying a team channel, custom post-install transforms.

**Approach:** A `[hooks]` section in `agr.toml`:
```toml
[hooks]
post-sync = "scripts/post-sync.sh"
post-add = "scripts/validate-skill.sh"
```

### 5.3 Content Addressing

The current `content_hash` is a good foundation for content-addressable storage. Combined with a registry, this enables deduplication across teams and faster installs (download by hash, not by repo clone).

### 5.4 Team Features

The "Built for teams" positioning suggests future features like:
- **Shared skill sets** — team-level `agr.toml` profiles
- **Approval workflows** — require review before adding skills to a team config
- **Usage analytics** — which skills are used most, by whom
- **Skill quality signals** — download counts, ratings, compatibility matrix

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Git subprocess reliance | Medium | Git must be installed; no fallback. Consider pygit2 or dulwich for critical paths, or better error messages when git is missing. |
| GitHub API rate limits | Medium | `RateLimitError` exists but no retry/backoff. The SDK hub functions hit the API without caching tree responses. Add response caching and exponential backoff. |
| Lockfile version migration | Low | `LOCKFILE_VERSION = 1` with a hard error on mismatch. When v2 is needed, add a migration path rather than requiring manual re-sync. |
| Cache unbounded growth | Low | No TTL or size limit on `~/.cache/agr/`. Add `agr cache prune --older-than 30d` or automatic LRU eviction. |
| Windows compatibility | Low | File locking has Windows support (`msvcrt`), path separators use `--`, but the test suite likely doesn't run on Windows CI. |

---

## 7. Summary of Recommendations

**High Priority (Quality)**
1. Split `fetcher.py` into focused modules
2. Unify skill/ralph abstractions to reduce duplication
3. Replace `urllib.request` with `httpx` in SDK (already a dependency)
4. Narrow `INSTALL_ERROR_TYPES` catch scope

**Medium Priority (Features)**
5. Add `agr update` command
6. Add parallel downloads to `agr sync`
7. Add `agr verify` for content hash verification
8. Support `ref` field for version pinning

**Lower Priority (Future)**
9. Plugin system for tool registration
10. Skill composition via `requires`
11. Workspace/monorepo support
12. Async SDK variants
