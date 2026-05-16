# Agent Resources

The package manager for AI agents. Built for teams practicing Agentic Engineering.

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

- **`agr`** — Main CLI (Typer app in `agr/main.py`). Commands: init, add, remove, sync, upgrade, list, run, config.
- **`agrx`** — Ephemeral skill runner (`agrx/main.py`). Downloads and runs a skill without persisting it.

## agr.toml Format

The configuration file uses a flat array of dependencies:

```toml
dependencies = [
    {handle = "username/repo/skill", type = "skill"},
    {handle = "username/skill", type = "skill"},
    {path = "./local/skill", type = "skill"},
    {handle = "username/repo/my-ralph", type = "ralph"},
]
```

Each dependency has:
- `type`: `"skill"` or `"ralph"`. Skills install into each configured tool's skills dir; ralphs install once into `.agents/ralphs/<name>/` (project-scoped, no per-tool fan-out, no global installs).
- `handle`: Remote GitHub reference (username/repo/skill or username/skill)
- `path`: Local path (alternative to handle)

Future: A `tools` section will configure which tools to sync to:
```toml
tools = ["claude", "cursor"]
```

## Conventions

- **Commit messages**: `docs: explain X for users who want to Y`, `feat: add X so users can Y`, `fix: resolve X that caused Y`
- **Dependencies**: Keep runtime deps minimal. Prefer stdlib over new deps.
- **Tests**: Include tests for new functionality. No external services, no API keys in tests.
- **Docs**: Run `mkdocs build --strict` before committing doc changes.

## Boundaries

### Always Do
- agr and agrx should always be unified and synced.
- include in the plan to write tests for what is implemented
- Save all skills in `skills/` directory (not `.claude/skills/` which is gitignored)