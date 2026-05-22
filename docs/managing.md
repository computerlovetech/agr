# Manage your skill environment

Skill directories (`.claude/skills/`, `.cursor/skills/`, …) are build artifacts —
like `.venv/` or `node_modules/`. They belong in `.gitignore`. Commit `agr.toml`
and `agr.lock` instead. `agr sync` rebuilds the skill environment from them.

## agr.toml

```toml
tools = ["claude", "cursor"]

dependencies = [
  {handle = "anthropics/skills/pdf"},
  {handle = "maragudk/skills/code-review"},
  {path = "./skills/my-internal-skill"},
]
```

`tools` sets which agent tools to sync into. `dependencies` lists the skills —
each with a remote `handle` or local `path`.

Handles follow `owner/repo/skill-name` — the `skill-name/` directory inside
`github.com/owner/repo`. `anthropics/skills/pdf` is the `pdf/` directory in
[github.com/anthropics/skills](https://github.com/anthropics/skills).

## Commands

### Add and remove

```bash
agr add anthropics/skills/pdf       # adds to agr.toml and syncs
agr remove anthropics/skills/pdf    # removes from agr.toml and syncs
```

### Sync

Rebuilds all skill directories from `agr.toml` and `agr.lock`. Idempotent —
run it after `git pull` or any manual edit to `agr.toml`.

```bash
agr sync
```

### Upgrade

Re-fetches skills at their latest upstream versions and refreshes `agr.lock`.

```bash
agr upgrade            # all skills
agr upgrade pdf        # one skill (short name)
```

### List

```bash
agr list
```

## Multi-tool

`tools` in `agr.toml` controls which agent tools agr syncs into at once:

```toml
tools = ["claude", "cursor", "codex"]
```

Supported: `claude`, `cursor`, `codex`, `opencode`, `copilot`, `antigravity`.
Each maps to that tool's expected skill directory.

---

[CLI reference →](reference.md)
