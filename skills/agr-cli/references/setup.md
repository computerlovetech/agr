# Setup — bootstrap a repo for agr

How to initialize `agr.toml`, configure tools, and set up instruction syncing.
For the canonical CLI reference, run `agr init --help` or
`agr config --help`.

## Prerequisites

- `agr --version` works (install with `uv tool install agr` if not).
- The repo has at least one supported AI tool's marker — `.claude/`,
  `CLAUDE.md`, `.cursor/`, `.cursorrules`, `.codex/`, `.opencode/`,
  `.github/copilot-instructions.md`, `.gemini/`, etc. agr auto-detects from
  these.

## Initialize

```bash
agr init
```

Creates `agr.toml` and detects tools from repo signals.

Override detection upfront:

```bash
agr init --tools claude,codex,opencode --default-tool claude
```

Flags:

| Flag | Effect |
|---|---|
| `--tools` | Comma-separated list of tools (override auto-detect) |
| `--default-tool` | Tool used by `agrx` and instruction sync (defaults to first in `tools`) |
| `--sync-instructions` / `--no-sync-instructions` | Mirror canonical instruction file to others on `agr sync` |
| `--canonical-instructions` | Source of truth for instructions: `CLAUDE.md`, `AGENTS.md`, or `GEMINI.md` |

Anything you skip can be set later with `agr config`.

## Adjust tools after the fact

```bash
agr config set tools claude codex opencode    # replace
agr config add tools cursor                   # append
agr config remove tools cursor                # ⚠ deletes that tool's skills/
```

Skills install into each configured tool's directory:

| Tool | Skills directory |
|---|---|
| Claude Code | `.claude/skills/<name>/` |
| Cursor | `.cursor/skills/<name>/` |
| Codex | `.agents/skills/<name>/` (older repos: `.codex/`) |
| OpenCode | `.opencode/skills/<name>/` (older: `.opencode/skill/`) |
| GitHub Copilot | `.github/skills/<name>/` |
| Antigravity / Gemini | `.gemini/skills/<name>/` (older: `.agent/`) |

`agr sync` runs migrations automatically when it sees old layouts.

The `tools` list does NOT apply to ralphs — they always install once into
`.agents/ralphs/<name>/`.

## Multi-tool consistency

Once `tools = ["claude", "codex", "opencode"]`, every `agr add` and `agr sync`
fans out to each tool. `agr list` shows `partial` if a skill is missing from
any of the configured tools — run `agr sync` to fix.

## Instruction syncing

If the user keeps a canonical instruction file and wants it mirrored to other
tools' equivalents:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

Mappings:

- `CLAUDE.md` ↔ `.claude/CLAUDE.md`
- `AGENTS.md` ↔ Codex / OpenCode
- `GEMINI.md` ↔ Antigravity

`agr sync` copies the canonical file to the others. Only fires when 2+ tools
are configured. If only one tool is configured, instruction syncing is a no-op.

## Default owner (1-part handles)

`default_owner` lets the user write `agr add setup` to mean
`<default_owner>/skills/setup`. Defaults to `computerlovetech`. Override:

```bash
agr config set default_owner my-org
```

This is mostly useful for organizations that publish their own `skills` repo
and want short handles.

## What to commit

| File / dir | Commit? | Why |
|---|---|---|
| `agr.toml` | YES | The manifest — your team's source of truth |
| `agr.lock` | YES | Pins exact commits and content hashes — required for `--frozen` / `--locked` CI |
| `skills/` (in-repo) | YES | The skill source itself, reviewed in PRs |
| `.claude/skills/`, `.cursor/skills/`, etc. | NO | Generated from agr.toml; usually gitignored |
| `~/.agr/` | N/A | User-specific global config |

If `.claude/skills/` is currently committed, decide with the user whether to
gitignore it now that agr is managing it.

## Worked example: from zero to first skill

```bash
# 1. Install agr (confirm with user first)
uv tool install agr

# 2. Bootstrap config in the repo
agr init --tools claude,cursor --default-tool claude

# 3. Add a remote skill
agr add anthropics/skills/pdf

# 4. Scaffold an in-repo skill
agr init project-conventions
mkdir -p skills && mv project-conventions skills/
agr add ./skills/project-conventions

# 5. Verify
agr list
git status   # show what to commit: agr.toml, agr.lock, skills/project-conventions/
```

## See also

- [handles.md](handles.md) — handle formats and resolution
- [in-repo-skills.md](in-repo-skills.md) — full `skills/` workflow
- [configuration.md](configuration.md) — all config keys
