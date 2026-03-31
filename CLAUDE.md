# Agent Resources

A package manager for AI agents.

## Commands

This project uses `uv` for Python environment management. **Always use `uv run` to execute Python commands** to ensure they run in the correct virtual environment.

```bash
# Run tests
uv run pytest

# Run linters/formatters
uv run ruff check .
uv run ruff format .

# Run type checker
uv run ty check

# Test the CLI tools
uv run agr --help
uv run agrx --help
```

## Architecture

Two CLI tools share a common core library:

- **`agr`** — Main CLI (Typer app in `agr/main.py`). Commands: add, remove, sync, list, init, config.
- **`agrx`** — Ephemeral skill runner (`agrx/main.py`). Downloads and runs a skill without persisting it.

For detailed architecture, contributing guides, code patterns, and recipes, see `docs/docs/contributing/`.

## agr.toml Format

The configuration file uses a flat array of dependencies:

```toml
dependencies = [
    {handle = "username/repo/skill", type = "skill"},
    {handle = "username/skill", type = "skill"},
    {path = "./local/skill", type = "skill"},
]
```

Each dependency has:
- `type`: Always "skill" for now
- `handle`: Remote GitHub reference (username/repo/skill, username/skill, or just skill-name which uses `default_owner`)
- `path`: Local path (alternative to handle)

The config also supports `default_owner` (defaults to `"computerlovetech"`) which enables 1-part handles like `agr add setup`.

The `tools` setting configures which tools to sync to:
```toml
tools = ["claude", "cursor"]
```

## Agent Workspace

Persistent agent artifacts live in `workspace/` — see `workspace/README.md` for the convention.

## Code Style
...

## Boundaries

### Always Do
- agr and agrx should always be unified and synced.
- include in the plan to write tests for what is implemented
- Save all skills in `skills/` directory (not `.claude/skills/` which is gitignored)

### Ask First
...

### Never Do
...

## Security
...

# Docs

General
https://agentskills.io/
https://agents.md/

Claude Code:
https://code.claude.com/docs/en/skills
https://code.claude.com/docs/en/slash-commands
https://code.claude.com/docs/en/sub-agents
https://code.claude.com/docs/en/memory

Cursor:
https://cursor.com/docs/context/skills
https://cursor.com/docs/context/commands
https://cursor.com/docs/context/subagents
https://cursor.com/docs/context/rules

GitHub Copilot:
https://docs.github.com/en/copilot/concepts/agents/about-agent-skills

Codex:
https://developers.openai.com/codex/skills
https://developers.openai.com/codex/custom-prompts/

Open Code:
https://opencode.ai/docs/skills
https://opencode.ai/docs/commands/
https://opencode.ai/docs/agents/
