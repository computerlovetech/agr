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

- **`agr`** — Main CLI (Typer app in `agr/main.py`). Commands: add, remove, sync, list, init, onboard, config.
- **`agrx`** — Ephemeral skill runner (`agrx/main.py`). Downloads and runs a skill without persisting it.

### Core modules (`agr/`)

| Module | Purpose |
|---|---|
| `handle.py` | Parse handle strings (`user/skill`, `user/repo/skill`, `./path`) into `ParsedHandle` |
| `config.py` | Load/save `agr.toml`, defines `AgrConfig` and `Dependency` |
| `tool.py` | Tool configs (`ToolConfig`) for Claude, Cursor, Codex, OpenCode, Copilot, Antigravity |
| `source.py` | `SourceConfig` and `SourceResolver` for git source resolution |
| `fetcher.py` | Skill install/uninstall orchestration — ties handle, git, skill, metadata together |
| `git.py` | Git clone, sparse checkout, GitHub token injection |
| `skill.py` | Skill discovery and validation (`SKILL.md` scanning) |
| `metadata.py` | Read/write `.agr.json` in installed skill directories |
| `detect.py` | Auto-detect which AI tools are present in a repo |
| `instructions.py` | Sync instruction files (CLAUDE.md, AGENTS.md, GEMINI.md) |
| `console.py` | Rich console output with `--quiet` support |
| `exceptions.py` | Exception hierarchy rooted at `AgrError` |
| `commands/` | One module per CLI command — thin wrappers calling core modules |
| `sdk/` | Programmatic API: `Skill`, `cache`, `list_skills`, `skill_info` |

### Data flow: `agr add user/skill`

1. `parse_handle()` → `ParsedHandle(username, name)`
2. Load `agr.toml` → `AgrConfig` with tools list and sources
3. For each tool: `fetch_and_install()` → clone repo → find SKILL.md → copy to tool's skills dir → write `.agr.json`
4. Add `Dependency` to config, save `agr.toml`

See `agent_docs/` for detailed architecture documentation.

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
- `handle`: Remote GitHub reference (username/repo/skill or username/skill)
- `path`: Local path (alternative to handle)

Future: A `tools` section will configure which tools to sync to:
```toml
tools = ["claude", "cursor"]
```

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