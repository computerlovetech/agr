---
title: Reference
---

# Reference

## Quick Reference

### Install & Remove

```bash
agr add user/skill                     # Install from GitHub
agr add user/repo/skill                # Install from a specific repo
agr add ./path/to/skill                # Install from local directory
agr add user/skill user/other-skill    # Install multiple at once
agr add user/skill --overwrite         # Update to latest version
agr remove user/skill                  # Uninstall a skill
```

### Global Skills

```bash
agr add -g user/skill                  # Install globally (all projects)
agr list -g                            # List global skills
agr sync -g                            # Sync global dependencies
agr remove -g user/skill               # Remove a global skill
```

### Team Sync

```bash
agr sync                               # Install all skills from agr.toml
agr list                               # Show skills and install status
```

### Try Without Installing

```bash
agrx user/skill                        # Run once, then clean up
agrx user/skill -p "Extract tables"    # Pass a prompt
agrx user/skill -i                     # Interactive: skill + chat
agrx user/skill --tool cursor          # Use a specific tool
```

### Create & Share

```bash
agr init my-skill                      # Scaffold a new skill
agr add ./my-skill                     # Test locally
agr add ./my-skill -o                  # Reinstall after editing
```

### Configuration

```bash
agr init                               # Create agr.toml (auto-detects tools)
agr onboard                            # Interactive guided setup
agr config show                        # View current config
agr config set tools claude cursor     # Target multiple tools
agr config set default_tool claude     # Set default for agrx
agr config add tools codex             # Add a tool without replacing
agr config remove tools codex          # Stop syncing to a tool
```

### Sources & Private Repos

```bash
export GITHUB_TOKEN="ghp_..."                    # Authenticate for private repos
agr config add sources gitlab \
  --type git --url "https://gitlab.com/{owner}/{repo}.git"   # Custom source
agr add user/skill --source gitlab               # Use a specific source
agr config set default_source gitlab             # Change default source
```

### Instruction Syncing

```bash
agr config set sync_instructions true             # Enable syncing
agr config set canonical_instructions CLAUDE.md   # Set source of truth
agr sync                                          # Copies to AGENTS.md, GEMINI.md
```

## Global Options

- `--quiet`, `-q` — Suppress non-error output (works with all commands)
- `--version`, `-v` — Show version and exit

## CLI Commands

### agr add

Install skills from GitHub or local paths. Skills are installed into your tool's
skills folder (e.g. `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`,
`.opencode/skills/`, `.github/skills/`, `.agent/skills/`).

If no `agr.toml` exists, `agr add` creates one automatically and detects which
tools you use from repo signals. You don't need to run `agr init` first.

```bash
agr add <handle>...
```

**Arguments:**

- `handle` — Skill handle (`user/skill` or `user/repo/skill`) or local path (`./path`)

**Options:**

- `--overwrite`, `-o` — Replace existing skills
- `--source`, `-s` `<name>` — Use a specific source from `agr.toml`
- `--global`, `-g` — Install globally using `~/.agr/agr.toml` and tool global directories

**Examples:**

```bash
agr add anthropics/skills/frontend-design
agr add -g anthropics/skills/frontend-design
agr add kasperjunge/commit kasperjunge/pr
agr add ./my-skill
agr add anthropics/skills/pdf --overwrite
agr add anthropics/skills/pdf --source github
```

### agr remove

Uninstall skills.

```bash
agr remove <handle>...
```

**Options:**

- `--global`, `-g` — Remove from global skills directory

**Examples:**

```bash
agr remove anthropics/skills/frontend-design
agr remove -g anthropics/skills/frontend-design
agr remove kasperjunge/commit
agr remove ./my-skill
```

### agr sync

Install all dependencies from `agr.toml`.

```bash
agr sync
agr sync -g
```

Installs any skills listed in `agr.toml` that aren't already installed.

### agr list

Show all skills and their installation status.

```bash
agr list
agr list -g
```

Displays skills from `agr.toml` and whether they're installed.

### agr init

Create `agr.toml` or a skill scaffold.

```bash
agr init              # Create agr.toml
agr init <name>       # Create skill scaffold
```

`agr init` creates `agr.toml` and auto-detects which tools you use from repo
signals (`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.). It does not
discover or add skills — use `agr onboard` for interactive setup with skill
discovery and migration.

**Options:**

- `--tools` — Comma-separated tool list (e.g., `claude,codex,opencode`)
- `--default-tool` — Default tool for `agrx` and instruction sync
- `--sync-instructions/--no-sync-instructions` — Sync instruction files on `agr sync`
- `--canonical-instructions` — Canonical instruction file (`AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`)

**Examples:**

```bash
agr init                    # Creates agr.toml in current directory
agr init my-skill           # Creates my-skill/SKILL.md
agr init --tools claude,codex,opencode --default-tool claude
agr init --sync-instructions --canonical-instructions CLAUDE.md
```

### agr onboard

Interactive guided setup. Walks you through tool selection, skill discovery,
migration from tool folders into `./skills/`, and configuration.

```bash
agr onboard
```

**Options:**

- `--no-migrate` — Skip migration offer for skills in tool folders

**Examples:**

```bash
agr onboard                # Start guided setup
agr onboard --no-migrate   # Skip migration prompts
```

### agr config

Manage `agr.toml` configuration.

```bash
agr config show                              # View formatted config
agr config path                              # Print agr.toml path
agr config edit                              # Open in $EDITOR
agr config get <key>                         # Read a config value
agr config set <key> <values>                # Write scalar or replace list
agr config add <key> <values>                # Append to list
agr config remove <key> <values>             # Remove from list
agr config unset <key>                       # Clear to default
```

**Valid keys:** `tools`, `default_tool`, `default_source`, `sync_instructions`, `canonical_instructions`, `sources`

**Options (on all subcommands):**

- `--global`, `-g` — Operate on `~/.agr/agr.toml` instead of local

**Options (on `add` only):**

- `--type` — Source type (when key is `sources`)
- `--url` — Source URL (when key is `sources`)

**Examples:**

```bash
agr config set tools claude codex opencode
agr config set default_tool claude
agr config add tools cursor
agr config remove tools cursor
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr config add sources my-source --type git --url "https://git.example.com/{owner}/{repo}.git"
agr config unset default_tool
```

!!! note "Deprecated aliases"
    `agr config tools list/add/set/remove` and `agr config default-tool set/unset` still work but print deprecation warnings. Use the unified commands above instead.

### agrx

Run a skill temporarily without adding to `agr.toml`.

```bash
agrx <handle> [options]
```

Downloads the skill, runs it with the selected tool, and cleans up afterwards.

**Options:**

- `--tool`, `-t` — Tool CLI to use (claude, cursor, codex, opencode, copilot, antigravity). Overrides `default_tool` from config.
- `--interactive`, `-i` — Run skill, then continue in interactive mode
- `--prompt`, `-p` — Prompt to pass to the skill
- `--global`, `-g` — Install to the global tool skills directory instead of the repo-local one
- `--source`, `-s` `<name>` — Use a specific source from `agr.toml`

**Examples:**

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx kasperjunge/commit -i
agrx kasperjunge/commit --source github
```

## agr.toml Format

```toml
default_source = "github"
tools = ["claude", "codex", "opencode"]
default_tool = "claude"
sync_instructions = true
canonical_instructions = "CLAUDE.md"

dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "kasperjunge/commit", type = "skill"},
    {path = "./local-skill", type = "skill"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

Each dependency has:

- `handle` — Remote handle
- `path` — Local path
- `source` — Optional source name for remote handles
- `type` — Currently always `skill`

Note: `dependencies` must appear before any `[[source]]` blocks in `agr.toml`.

### Top-Level Keys

- `default_source` — Name of the default `[[source]]` for remote installs
- `tools` — List of tools to sync instructions/skills to
- `default_tool` — Default tool used by `agrx`
- `sync_instructions` — Sync instruction files on `agr sync`
- `canonical_instructions` — Canonical instruction file (`AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`)

## Troubleshooting

See the [Troubleshooting](troubleshooting.md) page for solutions to common
errors — installation failures, handle format issues, authentication problems,
and more.
