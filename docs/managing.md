# Manage your skill environment

`agr.toml` is the manifest. `agr.lock` is the lockfile. The per-tool skill
directories (`.claude/skills/`, `.cursor/skills/`, …) are built artifacts —
derived from the manifest and lockfile. They belong in `.gitignore`, like
`.venv/`. `agr sync` rebuilds them.

Commit `agr.toml` and `agr.lock`. Same toml on every machine → same skills
everywhere.

## `agr.toml`

```toml
tools = ["claude", "cursor"]

dependencies = [
  {handle = "anthropics/skills/pdf"},
  {handle = "maragudk/skills/code-review"},
  {path = "./skills/my-internal-skill"},
]
```

### Top-level keys

| Key            | Type       | Description                                       |
|----------------|------------|---------------------------------------------------|
| `tools`        | `string[]` | Which agent tools to sync into. See below.        |
| `dependencies` | `table[]`  | Skills to install. Each entry needs `handle` or `path`. |

### Dependency keys

| Key      | Type   | Description                                                 |
|----------|--------|-------------------------------------------------------------|
| `handle` | string | GitHub reference: `user/repo/skill` or `user/skill`.        |
| `path`   | string | Local path to a skill directory. Alternative to `handle`.   |

## Commands

### `agr add <handle>`

Adds a skill to `agr.toml`, updates `agr.lock`, and syncs.

```bash
agr add anthropics/skills/pdf
```

### `agr remove <handle>`

Removes a skill from `agr.toml`, updates `agr.lock`, and syncs.

```bash
agr remove anthropics/skills/pdf
```

### `agr sync`

Reads `agr.toml` and `agr.lock`, rebuilds the per-tool skill directories.
Idempotent. Run after `git pull` or any manual edit to `agr.toml`.

```bash
agr sync
```

### `agr list`

Shows what's installed and which tool directories each skill lives in.

```bash
agr list
```

## `.gitignore`

Skill directories are built artifacts. Commit the manifest, ignore the build.

```gitignore
.claude/skills/
.cursor/skills/
.codex/skills/
.agents/skills/
```

Add these to your project's `.gitignore` manually.

## Multi-tool

Set `tools` in `agr.toml` to pick which agent tools `agr sync` writes to:

```toml
tools = ["claude", "cursor", "codex"]
```

Supported keys: `claude`, `cursor`, `codex`, `opencode`, `copilot`,
`antigravity`. Each maps to that tool's expected skill directory.

## What now?

- [CLI reference](reference.md) — every command and flag.
- [Get started](index.md) — the 5-minute quickstart.
