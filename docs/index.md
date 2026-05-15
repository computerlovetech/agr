# agr — a package manager for AI agent skills

`agr.toml` is your manifest. The per-tool skill directories
(`.claude/skills/`, `.cursor/skills/`, …) are built artifacts — like `.venv/`.
`agr sync` rebuilds them.

An open alternative to vendor plugin marketplaces. Install any skill from any
GitHub repo, into any supported agent tool.

```bash
uv tool install agr
agr init
agr add anthropics/skills/pdf
agr sync
```

Open Claude Code in the same directory — the `pdf` skill is now available.

## Why agr

- **Declarative.** `agr.toml` is the source of truth, like `pyproject.toml`.
  Commit it. Run `agr sync` after `git pull`.
- **Multi-tool.** One manifest. Syncs to Claude Code, Cursor, Codex, OpenCode,
  Copilot, Antigravity.
- **Open.** Install any skill from any GitHub repo. No marketplace, no
  gatekeeper, no vendor lock-in.

## 5-minute quickstart

### 1. Install agr

```bash
uv tool install agr
```

### 2. Initialize a project

```bash
cd my-project
agr init
```

Writes a starter `agr.toml` and adds the per-tool skill directories to
`.gitignore`.

### 3. Add a skill

```bash
agr add anthropics/skills/pdf
```

Your `agr.toml` now looks like:

```toml
tools = ["claude"]

dependencies = [
  {handle = "anthropics/skills/pdf"},
]
```

`agr add` already ran `sync` for you, so `.claude/skills/pdf/` exists. Open
Claude Code in this directory and ask it to read a PDF.

### 4. Sync on a fresh clone

When a teammate clones the repo, they run:

```bash
agr sync
```

That's it. `agr.toml` + `agr.lock` → identical skill environment, every
machine.

## What now?

- [Manage your skill environment](managing.md) — `agr.toml` in depth,
  multi-tool, the four commands you'll use.
- [CLI reference](reference.md) — every command and flag.

> **Ralphs?** agr also supports `ralphs` — an experimental project-scoped
> agent primitive. Not covered here.
