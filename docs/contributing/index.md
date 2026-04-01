# Contributing

This guide is for contributors — both humans and AI agents — working on the `agr` codebase.

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

## Common patterns

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

## Recipes

### Adding a new AI tool

1. **Define the tool** in `agr/tool.py`: create a `ToolConfig` instance with paths, CLI fields, and detection signals
2. **Register it** in the `TOOLS` dict at the bottom of `tool.py`
3. **Add tests** in a new `tests/test_<tool>.py` — test install paths, naming, and detection
4. **Update docs**: add the tool to the table in `docs/docs/configuration.md` and the CLI table in `docs/docs/agrx.md`

### Adding a new CLI command

1. **Create the module** in `agr/commands/<name>.py` — implement the logic, keep the command thin
2. **Wire it in** `agr/main.py` — add the Typer command or subcommand
3. **Add tests** in `tests/test_commands.py` or a dedicated test file
4. **Document it** in `docs/docs/reference.md` with arguments, options, and examples

## Supported tool documentation

agr installs skills into multiple AI coding tools. When working on tool compatibility — adding a new tool, updating install paths, or fixing integration issues — consult the official docs for each supported tool:

**General:**

- [agentskills.io](https://agentskills.io/) — Cross-tool skill specification
- [agents.md](https://agents.md/) — Agent instruction file convention

**Claude Code:**

- [Skills](https://code.claude.com/docs/en/skills)
- [Slash commands](https://code.claude.com/docs/en/slash-commands)
- [Sub-agents](https://code.claude.com/docs/en/sub-agents)
- [Memory](https://code.claude.com/docs/en/memory)

**Cursor:**

- [Skills](https://cursor.com/docs/context/skills)
- [Commands](https://cursor.com/docs/context/commands)
- [Sub-agents](https://cursor.com/docs/context/subagents)
- [Rules](https://cursor.com/docs/context/rules)

**GitHub Copilot:**

- [Agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)

**OpenAI Codex:**

- [Skills](https://developers.openai.com/codex/skills)
- [Custom prompts](https://developers.openai.com/codex/custom-prompts/)

**OpenCode:**

- [Skills](https://opencode.ai/docs/skills)
- [Commands](https://opencode.ai/docs/commands/)
- [Agents](https://opencode.ai/docs/agents/)

## Recipes

### Adding a new config key

1. **Add the field** to `AgrConfig` in `agr/config.py`
2. **Handle serialization** in `to_dict()` and `load()` methods
3. **Add CLI access** via `agr config get/set` in `agr/commands/config_cmd.py`
4. **Document it** in `docs/docs/configuration.md` and `docs/docs/reference.md`
