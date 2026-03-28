---
title: "agrx — Run AI Agent Skills Instantly Without Installing"
description: Run AI agent skills instantly with agrx — test before installing, no agr.toml changes, automatic cleanup. Like npx for AI skills in Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity.
keywords:
  - agrx
  - run skills without installing
  - test AI agent skill before installing
  - try AI skills without installing
  - npx for AI skills
  - one-off skill execution
  - ephemeral skill runner
  - agrx command
  - temporary skill testing
  - agrx interactive mode
  - agrx vs agr add
  - download and run AI skills
  - agrx Claude Code
  - agrx Cursor
  - agrx Codex
---

# agrx — Run Skills Without Installing

!!! tldr
    `agrx` downloads a skill, runs it with your AI tool's CLI, and cleans up
    afterwards. Nothing is added to `agr.toml`. Use it to try skills before
    committing to an install.

**Prerequisites:** [agr installed](tutorial.md#step-1-install-agr) and the
[tool CLI](tools.md) for your chosen AI tool (e.g., `claude`, `codex`,
`agent`)

`agrx` is like [npx](https://docs.npmjs.com/cli/commands/npx) for AI agent
skills. It downloads a [skill](concepts.md#skills) from GitHub, runs it with
your AI coding tool's CLI, and cleans up afterwards. Nothing is added to
[`agr.toml`](configuration.md) — no permanent install, no project changes.

**Key terms:** A **skill** is a directory containing a `SKILL.md` file with
instructions for an AI coding agent. A **handle** like `anthropics/skills/pdf`
identifies a skill on GitHub (`user/repo/skill`). The short form `user/skill`
assumes a repo named `skills`. A **tool** is one of the supported AI coding
agents: Claude Code, Cursor, Codex, OpenCode, GitHub Copilot, or Antigravity.

## Quick Start

```bash
agrx anthropics/skills/pdf                          # Run once, then clean up
```

```text
Downloading anthropics/skills/pdf...
Running skill 'pdf' with claude...
```

```bash
agrx anthropics/skills/pdf -p "Extract tables"      # Pass a prompt
agrx kasperjunge/commit -i                          # Interactive: skill + chat
```

## How It Works

1. **Determine tool** — Uses `--tool` flag, or `default_tool` from `agr.toml`, or the first tool in `tools`, or `claude` (see [Supported Tools](tools.md))
2. **Download skill** — Clones the repo and extracts the skill (same as `agr add`, using [handles](concepts.md#handles))
3. **Install temporarily** — Places the skill in your tool's skills directory with a unique `_agrx_` prefix so it doesn't conflict with permanent installs
4. **Run the tool's CLI** — Invokes the tool (e.g., `claude -p "/skill-name"`)
5. **Clean up** — Removes the temporary skill directory, even on Ctrl+C

??? note "Permission-bypass flags in interactive mode"
    When you use `-i` (interactive mode), `agrx` passes a tool-specific flag
    to reduce permission prompts during the session:

    | Tool | Flag (with `-i` only) |
    |------|------|
    | Claude Code | `--dangerously-skip-permissions` |
    | OpenAI Codex | `--full-auto` |
    | GitHub Copilot | `--allow-all-tools` |

    Cursor, OpenCode, and Antigravity don't have a permission-bypass flag.

    Without `-i`, the tool runs in non-interactive mode (prompt-and-exit) and
    no permission-bypass flag is passed — you'll see normal permission prompts
    if the skill takes actions that require approval.

## Options

| Flag | Short | Description |
|------|-------|-------------|
| `--tool` | `-t` | Tool CLI to use (claude, cursor, codex, opencode, copilot, antigravity) |
| `--interactive` | `-i` | Run skill, then continue in interactive mode |
| `--prompt` | `-p` | Prompt to pass to the skill |
| `--global` | `-g` | Install to global skills directory instead of project-local |
| `--source` | `-s` | Use a specific source from `agr.toml` |

## Examples

### Run with a specific tool

```bash
agrx anthropics/skills/pdf --tool codex
```

```text
Downloading anthropics/skills/pdf...
Running skill 'pdf' with codex...
```

```bash
agrx anthropics/skills/pdf --tool cursor
agrx anthropics/skills/pdf --tool opencode
```

### Interactive mode

The `-i` flag runs the skill first, then starts an interactive session so you
can continue the conversation:

```bash
agrx kasperjunge/commit -i
```

```text
Downloading kasperjunge/commit...
Running skill 'commit' with claude...
```

### Pass a prompt

```bash
agrx anthropics/skills/pdf -p "Extract all tables from report.pdf as CSV"
```

```text
Downloading anthropics/skills/pdf...
Running skill 'pdf' with claude...
```

### Use a custom source

See [Configuration — Sources](configuration.md#sources) for how to set up custom sources.

```bash
agrx team/internal-skill --source my-server
```

```text
Downloading team/internal-skill...
Running skill 'internal-skill' with claude...
```

### Run outside a git repo

`agrx` requires a git repository by default. Use `--global` to run anywhere:

```bash
agrx anthropics/skills/pdf --global
```

```text
Downloading anthropics/skills/pdf...
Running skill 'pdf' with claude...
```

## Differences from `agr add`

| | `agr add` | `agrx` |
|---|-----------|--------|
| Persists skill | Yes (permanent install) | No (cleaned up after run) |
| Updates `agr.toml` | Yes (adds dependency) | No |
| Runs the skill | No | Yes (invokes tool CLI) |
| Local paths | Supported | Not supported (remote only) |
| Multi-tool | Installs to all configured tools | Uses one tool |

## Common Errors

Running `agrx` on a local path fails — only remote handles are supported:

```bash
agrx ./my-skill
```

```text
Error: agrx only works with remote handles
Use 'agr add' for local skills
```

Running outside a git repo without `--global`:

```bash
agrx anthropics/skills/pdf
```

```text
Error: Not in a git repository
Use --global to install to ~/.claude/skills/
```

## Tool CLI Requirements

`agrx` needs the tool's CLI to be installed. If it's missing, you'll see an
error with installation instructions:

| Tool | CLI | Install |
|------|-----|---------|
| Claude Code | `claude` | [claude.ai/download](https://claude.ai/download) |
| Cursor | `agent` | Install Cursor IDE |
| OpenAI Codex | `codex` | `npm i -g @openai/codex` |
| OpenCode | `opencode` | [opencode.ai/docs/cli](https://opencode.ai/docs/cli/) |
| GitHub Copilot | `copilot` | Install GitHub Copilot CLI |
| Antigravity | — | No CLI available; use `agr add` to install skills instead |

## Next Steps

- [**Tutorial**](tutorial.md) — Full walkthrough including using `agrx` to try skills
- [**Skill Directory**](skills.md) — Browse available skills to run with `agrx`
- [**CLI Reference**](reference.md) — Complete `agrx` command reference with all flags
- [**Troubleshooting**](troubleshooting.md) — Fix common errors with skill downloads and tool CLIs
