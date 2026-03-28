# Contributing guide for AI agents

## Quick reference

### Run tests
```bash
uv run pytest                    # all tests
uv run pytest tests/test_foo.py  # specific file
uv run pytest -k "test_name"    # specific test
```

### Lint and format
```bash
uv run ruff check .    # lint
uv run ruff format .   # format
uv run ty check        # type check
```

### Test the CLI
```bash
uv run agr --help
uv run agrx --help
```

## Where to find things

| I want to... | Look at... |
|---|---|
| Add a new CLI command | `agr/commands/` — create a module, wire it in `agr/main.py` |
| Change how skills are installed | `agr/fetcher.py` |
| Change handle parsing | `agr/handle.py` |
| Change config file format | `agr/config.py` |
| Add a new AI tool | `agr/tool.py` — add a `ToolConfig` instance and register in `TOOLS` dict |
| Change git behavior | `agr/git.py` |
| Change skill discovery | `agr/skill.py` |
| Change metadata format | `agr/metadata.py` |
| Change agrx behavior | `agrx/main.py` |
| Add SDK functionality | `agr/sdk/` |
| Change instruction syncing | `agr/instructions.py` |
| Change migration logic | `agr/commands/migrations.py` |
| Add a new exception type | `agr/exceptions.py` — add class, register in `INSTALL_ERROR_TYPES` if catchable during sync |
| Change sync command stages | `agr/commands/sync.py` |
| Update MkDocs site | `docs/docs/` |

## Conventions

### Code style
- Python 3.12+, type hints on all public functions
- Docstrings on all public functions and classes (Google style)
- Ruff for linting and formatting
- No bare `except` — catch specific exceptions
- Module-level docstring on every file

### Testing conventions
- Every new feature needs tests
- Use `tmp_path` for filesystem operations
- Use `monkeypatch` for mocking
- Test files mirror source layout: `agr/fetcher.py` → `tests/test_fetcher.py`
- Group related tests in classes (e.g., `class TestGitAuthentication`)
- Each test method gets a descriptive docstring explaining what it verifies

### agr and agrx sync
These two CLIs must stay functionally aligned. Changes to shared behavior (handle parsing, git operations, skill discovery) apply to both. The `agrx` runner reuses the core `agr/` library.

### Skills directory
Save all skills in `skills/` (not `.claude/skills/` which is gitignored).

## Common patterns in the codebase

### Context managers for temp resources
`downloaded_repo()` and `_rollback_on_failure()` use `@contextmanager` to ensure cleanup:

```python
with downloaded_repo(source, owner, repo) as repo_dir:
    # repo_dir is cleaned up automatically
    skill = find_skill_in_repo(repo_dir, name)
```

### Handle → install path resolution
The path where a skill is installed depends on the tool:
- Flat tools: `_resolve_skill_destination()` in `fetcher.py`
- Nested tools: `handle.to_skill_path(tool)` in `handle.py`

### Config discovery
`find_config()` walks up from cwd to git root looking for `agr.toml`. Global config lives at `~/.agr/agr.toml`.

### Source resolution
`SourceResolver.ordered(explicit_source)` returns sources in priority order. Default source comes first, others follow. If an explicit source is given, only that source is tried.

### Multi-tool install with rollback
`fetch_and_install_to_tools()` downloads once, installs to all tools. If any tool fails, all already-installed copies are removed via `_rollback_on_failure()`.

## Testing patterns

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
│   │   ├── test_onboard.py        # agr onboard end-to-end
│   │   ├── test_config_commands.py # agr config subcommands
│   │   ├── test_tools.py          # agr config tools (deprecated)
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

## Error handling patterns

### Exception hierarchy

All errors inherit from `AgrError` (`agr/exceptions.py`). Use specific subclasses:

| Exception | When to raise |
|---|---|
| `RepoNotFoundError` | Git repo doesn't exist at the expected URL |
| `AuthenticationError` | Git auth fails (private repo, bad token) |
| `SkillNotFoundError` | Skill directory not found in a repo |
| `ConfigError` | Invalid `agr.toml` (bad format, missing fields) |
| `InvalidHandleError` | Handle string can't be parsed |
| `InvalidLocalPathError` | Local path doesn't exist or has no `SKILL.md` |
| `CacheError` | SDK cache read/write failures |
| `RateLimitError` | GitHub API rate limit hit |

### Adding a new exception

1. Define the class in `agr/exceptions.py` inheriting from `AgrError`
2. If it should be caught during sync (non-fatal per dependency), add it to `INSTALL_ERROR_TYPES`
3. If it has a user-friendly message format, add a case in `format_install_error()`

### Error surfacing in commands

- CLI commands catch `AgrError` and call `print_error()` for clean output
- `agr sync` uses `INSTALL_ERROR_TYPES` to catch per-dependency errors without aborting the whole sync
- `_rollback_on_failure()` catches **all** exceptions to ensure partial installs are cleaned up

## Recipes

### Adding a new AI tool

1. **Define the tool** in `agr/tool.py`: create a `ToolConfig` instance with paths, CLI fields, and detection signals
2. **Register it** in the `TOOLS` dict at the bottom of `tool.py`
3. **Add tests** in a new `tests/test_<tool>.py` — test install paths, naming, and detection
4. **Update docs**: add the tool to the table in `docs/docs/configuration.md` and the CLI table in `docs/docs/agrx.md`
5. **Update agent docs**: add detection signals to `agent_docs/ARCHITECTURE.md` tool list

### Adding a new CLI command

1. **Create the module** in `agr/commands/<name>.py` — implement the logic, keep the command thin
2. **Wire it in** `agr/main.py` — add the Typer command or subcommand
3. **Add tests** in `tests/test_commands.py` or a dedicated test file
4. **Document it** in `docs/docs/reference.md` with arguments, options, and examples

### Adding a new config key

1. **Add the field** to `AgrConfig` in `agr/config.py`
2. **Handle serialization** in `to_dict()` and `load()` methods
3. **Add CLI access** via `agr config get/set` in `agr/commands/config_cmd.py`
4. **Document it** in `docs/docs/configuration.md` and `docs/docs/reference.md`
