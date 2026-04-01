# Architecture

## Overview

Agent Resources (`agr`) is a package manager for AI agent skills. It installs skill files (markdown prompts with optional supporting files) from GitHub repositories into the configuration directories of various AI coding tools (Claude Code, Cursor, Codex, etc.).

## Project structure

```
agr/                  # Core library
  main.py             # CLI entry point (Typer app)
  handle.py           # Handle parsing (ParsedHandle)
  config.py           # agr.toml management (AgrConfig, Dependency)
  tool.py             # Tool definitions (ToolConfig: claude, cursor, codex, etc.)
  source.py           # Git source resolution (SourceConfig, SourceResolver)
  fetcher.py          # Install/uninstall orchestration
  git.py              # Git clone, sparse checkout, token injection
  skill.py            # SKILL.md discovery and validation
  metadata.py         # .agr.json read/write in installed skill dirs
  detect.py           # Auto-detect tools present in a repo
  instructions.py     # Sync CLAUDE.md/AGENTS.md/GEMINI.md
  console.py          # Rich console output with --quiet
  exceptions.py       # AgrError hierarchy
  commands/            # CLI command implementations
    add.py             # agr add
    remove.py          # agr remove
    sync.py            # agr sync
    list.py            # agr list
    init.py            # agr init
    config_cmd.py      # agr config {show,path,edit,get,set,unset,add,remove}
    migrations.py      # Legacy skill migration utilities
    _tool_helpers.py   # Shared helpers for tool-related commands
  sdk/                 # Programmatic Python API
    __init__.py        # Public exports: Skill, cache, list_skills, skill_info
    skill.py           # Skill class for loading and running skills
    cache.py           # Disk cache for downloaded skills (file locking, atomic writes)
    hub.py             # Hub operations (search, list from GitHub API)
    types.py           # SkillInfo type definition

agrx/                 # Ephemeral skill runner CLI
  main.py             # agrx CLI: download, run, discard

tests/                # Pytest test suite
docs/                 # MkDocs site source
```

## Key types

### ParsedHandle (`handle.py`)

Represents a parsed skill reference. Two forms:

- **Remote**: `ParsedHandle(username="user", repo="repo", name="skill")` — from `user/repo/skill` or `user/skill` (repo defaults to `"skills"`)
- **Local**: `ParsedHandle(is_local=True, name="my-skill", local_path=Path("./my-skill"))` — from `./my-skill`

Key methods:
- `to_toml_handle()` → string for agr.toml (`"user/skill"` or `"./path"`)
- `to_installed_name()` → flat directory name with `--` separator (`"user--skill"`)
- `to_skill_path(tool)` → installation path relative to skills dir (flat or nested depending on tool)
- `get_github_repo()` → `(owner, repo_name)` tuple for git operations

### ToolConfig (`tool.py`)

Frozen dataclass defining how a tool stores skills. Key fields:

**Path fields** (where skills are installed):

- `name` — tool identifier (e.g., `"claude"`, `"cursor"`)
- `config_dir` — project-level config directory (e.g., `".claude"`)
- `skills_subdir` — subdirectory for skills (always `"skills"`)
- `supports_nested` — `False` for all current tools (flat naming: `skill-name/` directly under skills dir)
- `global_config_dir` — personal/global path when it differs from project path (e.g., Copilot uses `.github/skills/` locally but `~/.copilot/skills/` globally)
- `get_skills_dir(repo_root)` → `repo_root / config_dir / skills_subdir`
- `get_global_skills_dir()` → `Path.home() / (global_config_dir or config_dir) / skills_subdir`

**CLI fields** (used by `agrx` to invoke the tool):

- `cli_command` — executable name (e.g., `"claude"`, `"codex"`)
- `cli_prompt_flag` — flag for passing prompts (`"-p"` or `None` for positional)
- `cli_force_flag` — flag to skip permission prompts (e.g., `"--dangerously-skip-permissions"`)
- `cli_continue_flag` — flag to continue a session (e.g., `"--continue"`)
- `cli_exec_command` — full command for non-interactive runs (e.g., `["codex", "exec"]`)
- `cli_continue_command` — command to resume a session (e.g., `["codex", "resume", "--last"]`)
- `cli_interactive_prompt_positional` — `True` if interactive mode passes prompt as positional arg
- `cli_interactive_prompt_flag` — flag for interactive prompt (e.g., `"--prompt"` for OpenCode)
- `suppress_stderr_non_interactive` — hide streaming output in non-interactive mode (Codex)
- `skill_prompt_prefix` — prefix for invoking a skill (`"/"` for Claude, `"$"` for Codex, `""` for others)

**Detection and instruction fields**:

- `detection_signals` — paths that indicate tool presence (e.g., `(".claude", "CLAUDE.md")`)
- `instruction_file` — canonical instruction file for this tool (`"CLAUDE.md"`, `"AGENTS.md"`, or `"GEMINI.md"`)
- `install_hint` — help text shown when CLI is not found

Six tools defined: `CLAUDE`, `CURSOR`, `CODEX`, `OPENCODE`, `COPILOT`, `ANTIGRAVITY`.

**Detection signals** (used by `agr init` to auto-detect tools):

| Tool | Detection signals |
|------|-------------------|
| Claude | `.claude`, `CLAUDE.md` |
| Cursor | `.cursor`, `.cursorrules` |
| Codex | `.agents`, `.codex` |
| OpenCode | `.opencode` |
| Copilot | `.github/copilot`, `.github/skills` |
| Antigravity | `.agent` |

**CLI command mapping** (used by `agrx` to invoke tools):

| Tool | CLI | Exec command | Prompt flag | Skill prefix |
|------|-----|-------------|-------------|--------------|
| Claude | `claude` | — | `-p` | `/` |
| Cursor | `agent` | — | `-p` | `/` |
| Codex | `codex` | `codex exec` | positional | `$` |
| OpenCode | `opencode` | `opencode run` | positional / `--prompt` | (none) |
| Copilot | `copilot` | — | `-p` | `/` |
| Antigravity | — | — | — | (none) |

### AgrConfig (`config.py`)

Loaded from `agr.toml`. Contains:

- `dependencies: list[Dependency]` — skills to install
- `tools: list[str]` — target tools (default: `["claude"]`)
- `sources: list[SourceConfig]` — git sources (default: GitHub)
- `default_source`, `default_tool`, `sync_instructions`, `canonical_instructions`

Methods: `load(path)`, `save(path)`, `add_dependency()`, `remove_dependency()`, `get_tools()`, `get_source_resolver()`

### Dependency (`config.py`)

A single entry in the dependencies array:

- `handle` — remote reference (e.g., `"user/skill"`)
- `path` — local path (e.g., `"./my-skill"`)
- `type` — always `"skill"` currently
- `source` — optional explicit source name
- `to_parsed_handle()` → converts to `ParsedHandle`

### SourceConfig (`source.py`)

A git source with URL template: `name`, `type` (always `"git"`), `url` (e.g., `"https://github.com/{owner}/{repo}.git"`).

## Core workflows

### Install (`agr add user/skill`)

```
parse_handle("user/skill")
  → ParsedHandle(username="user", name="skill")

AgrConfig.load("agr.toml")
  → config with tools=["claude"], sources=[github]

For each tool in config.tools:
  fetch_and_install(handle, repo_root, tool)
    → _locate_remote_skill(handle, resolver)
      → iter_repo_candidates(handle.repo)  # ["skills", "agent-resources"]
        → For each repo candidate + source:
          → downloaded_repo(source, owner, repo_name)
            → git clone --depth 1 --filter=blob:none
          → prepare_repo_for_skill(repo_dir, skill_name)
            → git ls-tree → find SKILL.md → sparse checkout
    → install_skill_from_repo(repo_dir, skill_name, handle, skills_dir, tool)
      → _resolve_skill_destination()  # where to put it
      → _copy_skill_to_destination()  # shutil.copytree + metadata

config.add_dependency(Dependency(handle="user/skill", type="skill"))
config.save()
```

### Skill discovery algorithm (`skill.py`)

Skills are found by **recursive search**, not by checking hardcoded paths. The algorithm:

1. List all files via `git ls-tree` (fast path) or `rglob("SKILL.md")` (fallback)
2. Find entries where the filename is `SKILL.md`
3. Exclude: root-level `SKILL.md`, paths within `.git`, `node_modules`, `__pycache__`, `.venv`, `vendor`, `build`, `dist`, etc.
4. Match: directory name must equal the requested skill name
5. When multiple matches exist, the **shallowest** path wins (fewest path components)

This means `skills/my-skill/SKILL.md`, `src/tools/my-skill/SKILL.md`, and `my-skill/SKILL.md` would all match — with the shallowest returned.

### Uninstall (`agr remove user/skill`)

```
parse_handle → find existing skill dir via metadata matching → shutil.rmtree → clean empty parents
config.remove_dependency() → config.save()
```

### Sync (`agr sync`)

The sync command is the most complex workflow, with four stages:

```
1. Instruction sync
   If sync_instructions is enabled and ≥2 tools configured:
     Copy canonical instruction file (e.g. CLAUDE.md) → other tools' files

2. Migrations (before installing, so duplicate detection works)
   run_tool_migrations()        # Codex .codex/ → .agents/, OpenCode .opencode/skill/ → skills/
   migrate_legacy_directories() # Colon separator → double-hyphen (user:skill → user--skill)
   migrate_flat_installed_names()  # Full names → plain names when safe (user--repo--skill → skill)

3. Dependency install (three categories for efficiency)
   For each dependency in agr.toml:
     Check is_skill_installed() on all configured tools
     → UP_TO_DATE (skip) or classify as local / remote-default / remote-specific

   a) Local skills           → copy from local path (no download)
   b) Default-repo remotes   → "user/skill" handles where repo is unknown;
                                each downloads individually (tries "skills", "agent-resources")
   c) Specific-repo remotes  → "user/repo/skill" handles grouped by (source, owner, repo);
                                each group shares a single git clone

4. Report
   Print per-dependency status (installed / up-to-date / error) + summary
```

Key optimization: step 3c groups multiple skills from the same repository into a single download via `_sync_batched_repo_entries()`, avoiding redundant git clones.

### Skill destination resolution (`_resolve_skill_destination`)

For flat tools, the install path is determined by this priority:
1. **Already installed** — if the skill is found (by metadata ID) at any path, reuse it
2. **Plain name free** — install as `<skills-dir>/<skill-name>/`
3. **Name collision** — another skill owns the plain name, so fall back to `<skills-dir>/<user>--<repo>--<skill>/`

Finding existing installs (`_find_existing_skill_dir`) checks:
1. Plain name path, matched by `.agr.json` metadata ID
2. Full qualified name path, matched by metadata ID
3. Full qualified name path without metadata (legacy fallback)

### Local install (`agr add ./my-skill`)

Copies the local directory to the tool's skills dir. Validates `SKILL.md` exists. Checks for name conflicts with other local skills.

Special case: if the source path is already the install destination (e.g. `agr add ./skills/my-skill` when `.claude/skills/` points to `skills/`), the copy is skipped and only metadata is stamped.

## Naming conventions

### Flat tools (Claude, Codex, OpenCode, Copilot, Antigravity)

Skills are installed as top-level directories in the skills folder:
- Default: `<skills-dir>/<skill-name>/`
- On name collision: `<skills-dir>/<user>--<repo>--<skill>/`

### Nested tools (Cursor)

Skills preserve the full handle path:
- Remote: `<skills-dir>/<user>/<repo>/<skill>/`
- Local: `<skills-dir>/local/<skill>/`

## Metadata (`.agr.json`)

Each installed skill directory contains `.agr.json` with:

```json
{
  "id": "remote:github:user/skill",
  "tool": "claude",
  "installed_name": "skill",
  "type": "remote",
  "handle": "user/skill",
  "source": "github",
  "content_hash": "sha256:..."
}
```

Used for: matching skills to handles during uninstall/sync, detecting name conflicts, content change detection.

## Migrations (`commands/migrations.py`)

The sync command runs migrations before installing to ensure existing installs are in the expected layout. Three migration types:

### Tool-specific directory migrations (`run_tool_migrations`)

- **Codex**: `.codex/skills/` → `.agents/skills/` (Codex changed its config directory)
- **OpenCode**: `.opencode/skill/` → `.opencode/skills/` (singular to plural)

### Legacy separator migration (`migrate_legacy_directories`)

Renames colon-based directory names (e.g., `user:skill`) to the Windows-compatible double-hyphen format (`user--skill`). Only applies to flat tools.

### Flat name simplification (`migrate_flat_installed_names`)

Older versions always installed under the full flat name (`user--repo--skill`). This migration renames to the shorter plain name (`skill`) when there is no ambiguity. Three cases:

1. **Unique name** — one handle owns this name → safe to rename to plain name
2. **Ambiguous name** — multiple handles share the same skill name → keep full names, stamp metadata
3. **Unknown installs** — not tracked in agr.toml → skipped

## Instruction sync (`instructions.py`)

When `sync_instructions` is enabled and ≥2 tools are configured, `agr sync` copies the canonical instruction file to other tools' instruction files. The mapping is:

- Claude → `CLAUDE.md`
- Codex, Cursor, OpenCode, Copilot → `AGENTS.md`
- Antigravity → `GEMINI.md`

For example, with `canonical_instructions = "CLAUDE.md"` and `tools = ["claude", "codex", "antigravity"]`, sync copies `CLAUDE.md` content to `AGENTS.md` and `GEMINI.md`.

## agrx workflow (`agrx/main.py`)

The ephemeral skill runner downloads a skill, runs it with a tool's CLI, and cleans up:

```
1. Determine tool (--tool flag > config default_tool > first in tools list > "claude")
2. Validate tool CLI is installed (shutil.which)
3. Parse handle and download skill
4. Install to a temp name: _agrx_<skill>-<uuid8> in the tool's skills dir
5. Build CLI command using ToolConfig's CLI fields
   - Non-interactive (default): use cli_exec_command or cli_command + cli_prompt_flag
   - Interactive (-i): use cli_command + cli_interactive_prompt_flag/positional
6. Run the tool's CLI via subprocess
7. Clean up temp skill directory (also on SIGINT/SIGTERM)
```

Key design choice: agrx installs to the real skills directory (not a temp dir) because tools discover skills by scanning their config directory. The `_agrx_` prefix + UUID suffix prevents collisions.

## Error handling

All errors inherit from `AgrError` (`exceptions.py`):

- `RepoNotFoundError` — remote repo doesn't exist
- `AuthenticationError` — git auth failure (private repo, no token)
- `SkillNotFoundError` — skill directory not found in repo
- `ConfigError` — invalid agr.toml
- `InvalidHandleError` — unparseable handle string
- `InvalidLocalPathError` — local skill path is invalid (missing SKILL.md, path doesn't exist)
- `CacheError` — SDK cache failures
- `RateLimitError` — GitHub API rate limit

Multi-tool installs use `_rollback_on_failure()` context manager to clean up partial installs.

### Error formatting

`format_install_error()` in `exceptions.py` provides user-facing error messages. `AgrError` and `FileExistsError` are shown directly; other exceptions get an "Unexpected: " prefix. The `INSTALL_ERROR_TYPES` tuple defines which exception types are caught per-dependency during `agr sync` (so one failing skill doesn't abort the entire sync).

## Testing

Tests live in `tests/`. Key patterns:

- `tmp_path` fixtures for filesystem tests
- `monkeypatch` for mocking git operations and subprocess calls
- Tests are organized by module: `test_fetcher.py`, `test_config.py`, `test_skill.py`, etc.
- Run with `uv run pytest`

### Available fixtures (`tests/conftest.py`)

| Fixture | What it provides |
|---|---|
| `git_project` | A `tmp_path` with `.git/` dir and cwd set to it — simulates a git repo |
| `skill_fixture` | A valid skill directory with `SKILL.md` containing frontmatter |
| `tmp_path` | Built-in pytest fixture — unique temp directory per test |
| `monkeypatch` | Built-in pytest fixture — for mocking env vars, functions, attributes |

### Mocking git operations

Most tests mock `subprocess.run` to avoid real git clones:

```python
def test_clone_uses_branch(self, monkeypatch):
    """Clone passes --branch when default branch is detected."""
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/git")
    captured_cmds = []

    def fake_run(cmd, capture_output, text, check):
        captured_cmds.append(cmd)
        if cmd[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(
                cmd, 0, "ref: refs/heads/main\tHEAD\n", ""
            )
        repo_path = Path(cmd[-1])
        repo_path.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    # ... test logic using downloaded_repo() ...
```

### Testing with skill directories

Create a minimal valid skill on disk, then exercise install/uninstall:

```python
def test_install_local_skill(self, tmp_path):
    """Local skill is copied to the tool's skills directory."""
    # Set up source skill
    source = tmp_path / "my-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: my-skill\n---\n# My Skill\n")

    # Set up destination
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    result = install_local_skill(source, skills_dir, CLAUDE, repo_root=tmp_path)
    assert (result / "SKILL.md").exists()
```

### Testing exceptions

```python
def test_missing_skill_raises(self):
    """SkillNotFoundError raised when skill doesn't exist in repo."""
    with pytest.raises(SkillNotFoundError, match="not found"):
        install_skill_from_repo(repo_dir, "nonexistent", handle, dest, CLAUDE, None)
```

### Test directory layout

```
tests/
├── conftest.py                    # Shared fixtures (git_project, skill_fixture)
├── test_fetcher.py                # agr/fetcher.py tests
├── test_config.py                 # agr/config.py tests
├── test_handle.py                 # agr/handle.py tests
├── test_skill.py                  # agr/skill.py tests
├── test_metadata.py               # agr/metadata.py tests
├── test_tool.py                   # agr/tool.py tests
├── test_copilot.py                # Copilot-specific tests
├── test_cursor.py                 # Cursor-specific tests
├── test_commands.py               # CLI command integration tests
├── test_agrx_command_building.py  # agrx CLI command building
├── test_docs.py                   # Documentation accuracy tests
├── test_gh_issue_phase.py         # Regression tests for GitHub issues
├── cli/                           # CLI end-to-end tests
│   ├── conftest.py                # CLI test fixtures (mock git, subprocess)
│   ├── runner.py                  # Test runner helpers for CLI invocation
│   ├── assertions.py              # Common CLI assertion helpers
│   ├── agr/                       # agr CLI tests
│   │   ├── test_add.py            # agr add end-to-end
│   │   ├── test_remove.py         # agr remove end-to-end
│   │   ├── test_sync.py           # agr sync end-to-end
│   │   ├── test_list.py           # agr list end-to-end
│   │   ├── test_init.py           # agr init end-to-end
│   │   ├── test_config_commands.py # agr config subcommands
│   │   ├── test_sources.py        # Source-related CLI tests
│   │   ├── test_global_flags.py   # --global flag tests
│   │   ├── test_quiet.py          # --quiet flag tests
│   │   ├── test_version.py        # --version flag tests
│   │   ├── test_private_repo.py   # Private repo handling
│   │   ├── test_antigravity.py    # Antigravity tool CLI tests
│   │   ├── test_codex.py          # Codex tool CLI tests
│   │   ├── test_copilot.py        # Copilot tool CLI tests
│   │   ├── test_cursor.py         # Cursor tool CLI tests
│   │   └── test_opencode.py       # OpenCode tool CLI tests
│   └── agrx/                      # agrx CLI tests
│       ├── test_run.py            # agrx run end-to-end
│       └── test_tool_flag.py      # agrx --tool flag tests
├── sdk/                           # SDK tests
│   ├── conftest.py                # SDK test fixtures
│   ├── test_skill.py              # Skill class tests
│   ├── test_cache.py              # Cache management tests
│   └── test_hub.py                # Hub discovery tests
└── unit/                          # Isolated unit tests
    └── test_detect.py             # Tool detection tests
```
