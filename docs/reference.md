---
title: "CLI Reference — All agr and agrx Commands, Flags, and Options"
description: Complete CLI reference for agr and agrx — all commands, flags, and handle formats for managing skills across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity.
keywords:
  - agr CLI reference
  - agr commands
  - agr add command
  - agr remove command
  - agr sync command
  - agr config command
  - agrx command
  - agr handle format
  - agr.toml format
  - agr flags and options
  - Claude Code skill commands
  - Cursor skill commands
  - Codex skill commands
  - OpenCode skill commands
  - Copilot skill commands
  - Antigravity skill commands
---

# Reference

!!! tldr
    `agr add` installs resources, `agr sync` installs everything from
    `agr.toml` and refreshes `agr.lock`, `agr config` manages settings.
    `agrx` runs skills ephemerally. Handles: `user/skill`,
    `user/repo/skill`, or `./local`. Add `-g` for global scope. CI uses
    `agr sync --frozen` or `--locked` for reproducible installs.

Complete reference for all `agr` and [`agrx`](agrx.md) commands. For guided
setup, start with the [Tutorial](tutorial.md).

**What is agr?** *agr* stands for **agent resources** — the package manager
your team uses to manage its coding-agent resources. A **resource** can be
a **skill** (a folder with a `SKILL.md` file containing instructions an AI
coding tool loads — see [Creating Skills](creating.md)), a
**[ralph](ralphs.md)** (a folder with a `RALPH.md` file defining an
autonomous agent loop, executed by a ralph runtime such as
[ralphify](https://github.com/kasperjunge/ralphify)), or a **package** (a
folder with an `agr.toml` dependency list that expands into transitive skills
and ralphs). Every `agr` command on this page (`add`, `remove`, `sync`,
`list`) works transparently with these types — the type is detected from the
directory marker files or from the remote layout. A
**[handle](concepts.md#handles)** like `user/skill` or
`user/repo/skill` points to a resource on GitHub. Browse available skills
in the [Skill Directory](skills.md). agr installs skills into
[supported tools](tools.md) including Claude Code, Cursor, Codex, OpenCode,
GitHub Copilot, and Antigravity; ralphs install once per project into
`.agents/ralphs/`. [`agr.toml`](#agrtoml-format) is the manifest (what you
depend on) and [`agr.lock`](#agrlock-format) is the lockfile (the exact
commits). Commit both so your [team](teams.md) shares the same resources,
reproducibly.

## Quick Reference

### Install & Remove

```bash
agr add user/skill                     # Install from GitHub
agr add user/repo/skill                # Install from a specific repo
agr add ./path/to/skill                # Install from local directory
agr add user/skill user/other-skill    # Install multiple at once
agr upgrade                            # Update everything to the latest commit
agr upgrade user/skill                 # Update one resource
agr remove user/skill                  # Uninstall a skill
agr run pdf                            # Run an installed skill in the configured tool
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
agr sync                               # Install all resources, refresh agr.lock
agr sync --frozen                      # CI deploy: install exactly what agr.lock specifies
agr sync --locked                      # CI PR check: fail if agr.lock is stale
agr list                               # Show resources and install status
```

### Try Without Installing

```bash
agrx user/skill                        # Run once, then clean up
agrx user/skill -p "Extract tables"    # Pass a prompt
agrx user/skill -i                     # Interactive: skill + chat
agrx user/skill --tool cursor          # Use a specific tool
```

### Create & Share

See the full [Creating Skills](creating.md) guide for details.

```bash
agr init my-skill                      # Scaffold a new skill
agr add ./my-skill                     # Test locally
agr add ./my-skill -o                  # Reinstall after editing
```

### Configuration

```bash
agr init                               # Create agr.toml (auto-detects tools)
agr config show                        # View current config
agr config set tools claude cursor     # Target multiple tools
agr config set default_tool claude     # Set default for agrx
agr config add tools codex             # Add a tool without replacing
agr config remove tools codex          # Stop syncing to a tool (⚠ deletes its skills)
```

!!! warning "Removing a tool deletes its skills"
    `agr config remove tools <name>` also deletes all skills from that tool's
    skills directory. Skills remain in your other configured tools and can be
    reinstalled with `agr config add tools <name>`.

### Handle Format

```bash
agr add user/skill                 # github.com/user/skills repo, "skill" directory
agr add user/repo/skill            # github.com/user/repo repo, "skill" directory
agr add ./path/to/skill            # Local directory on disk
```

Two-part handles (`user/skill`) assume a repo named `skills`. Use three parts
when the repo has a different name. See [Handle Resolution](concepts.md#handles)
for the full lookup rules.

### Sources & Private Repos

```bash
export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"  # Authenticate for private repos
agr config add sources gitlab \
  --url "https://gitlab.com/{owner}/{repo}.git"              # Custom source
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

These apply to all `agr` commands (not `agrx`):

- `--quiet`, `-q` — Suppress non-error output
- `--version`, `-v` — Show version and exit

## CLI Commands

### agr add

Install skills or [ralphs](ralphs.md) from GitHub or local paths. Skills are
installed into your tool's skills folder (e.g. `.claude/skills/`,
`.agents/skills/`, `.cursor/skills/`, `.opencode/skills/`, `.github/skills/`,
`.gemini/skills/`). Ralphs are installed once per project into
`.agents/ralphs/<name>/`.

agr detects the resource type automatically: for local paths, from the
`SKILL.md` or `RALPH.md` marker inside the directory; for remote handles,
by searching the repo for a matching skill first and falling back to a
ralph if none is found. There is no `--type` flag — the dependency type is
recorded in `agr.toml` after a successful install.

If no `agr.toml` exists, `agr add` creates one automatically and detects which
tools you use from repo signals. You don't need to run `agr init` first.

```bash
agr add <handle>...
```

**Arguments:**

- `handle` — Skill or ralph handle (`user/skill` or `user/repo/skill`) or local path (`./path`)

**Options:**

- `--overwrite`, `-o` — Replace existing skills or ralphs
- `--source`, `-s` `<name>` — Use a specific source from `agr.toml`
- `--global`, `-g` — Install globally using `~/.agr/agr.toml` and tool global directories. Ralph dependencies are skipped under `-g` because ralphs are project-scoped.

**Examples:**

```bash
agr add anthropics/skills/frontend-design
agr add -g anthropics/skills/frontend-design
agr add vercel-labs/agent-browser/agent-browser anthropics/skills/pdf
agr add ./my-skill
agr add ./my-ralph                         # Auto-detected as ralph via RALPH.md
agr add user/agent-resources/bug-hunter    # Remote ralph (falls back to ralph after skill lookup)
agr add anthropics/skills/pdf --overwrite
agr add anthropics/skills/pdf --source github
```

### agr remove

Uninstall skills or ralphs and remove them from `agr.toml`. Skills are
deleted from every tool's skills directory (e.g., `.claude/skills/`,
`.cursor/skills/`). Ralphs are deleted from `.agents/ralphs/<name>/`. In
both cases the dependency entry is removed from the manifest.

```bash
agr remove <handle>...
```

**Arguments:**

- `handle` — Skill handle or local path (same formats as `agr add`)

**Options:**

- `--global`, `-g` — Remove from global skills directory and `~/.agr/agr.toml`

**Examples:**

```bash
agr remove anthropics/skills/frontend-design
agr remove -g anthropics/skills/frontend-design
agr remove vercel-labs/agent-browser/agent-browser
agr remove ./my-skill
```

### agr sync

Install all dependencies (skills and ralphs) from `agr.toml`, refresh
`agr.lock`, sync instruction files, and run any pending directory migrations.

```bash
agr sync
```

```text
Synced instructions: CLAUDE.md -> AGENTS.md
Up to date: anthropics/skills/frontend-design
Up to date: anthropics/skills/pdf
Installed: vercel-labs/agent-browser/agent-browser

Summary: 2 up to date, 1 installed
```

Each `agr sync` run performs up to four stages before reporting results:

1. **Instruction sync** — copies the [canonical instruction file](configuration.md#instruction-syncing) to other tools' instruction files (only when `sync_instructions = true` and 2+ tools are configured)
2. **Migrations** — renames skill directories to match current naming conventions (e.g., Cursor nested → flat, Codex `.codex/` → `.agents/`, OpenCode `.opencode/skill/` → `.opencode/skills/`, Antigravity `.agent/` → `.gemini/`). This happens automatically — no manual steps needed.
3. **Dependency install** — installs any skills and ralphs from `agr.toml` that are not yet present. Skills install into each configured tool's skills folder; ralphs install into `.agents/ralphs/<name>/`. Skills from the same repository are batched into a single download.
4. **Lockfile update** — writes `agr.lock` with the commit SHA and content hash for every resolved dependency, so future `agr sync` runs are reproducible.

**Options:**

- `--global`, `-g` — Sync global dependencies from `~/.agr/agr.toml`. Ralph dependencies are skipped in global mode.
- `--frozen` — Install exactly what `agr.lock` specifies. Fail if `agr.lock` is missing or does not cover every dependency in `agr.toml`. Never re-resolves. Use in CI deploy pipelines for byte-identical installs.
- `--locked` — Fail if `agr.lock` is out of date vs `agr.toml` (e.g. a contributor added a dependency but forgot to commit the refreshed lockfile), then install from the lockfile. Use in CI PR checks to enforce lockfile hygiene.

`--frozen` and `--locked` are mutually exclusive.

**Examples:**

```bash
agr sync                  # Local dev: install missing deps, refresh agr.lock
agr sync --frozen         # CI deploy: install exactly what agr.lock specifies
agr sync --locked         # CI PR check: fail if agr.lock is stale
agr sync -g               # Sync global ~/.agr/agr.toml (ralphs are skipped)
```

### agr upgrade

Re-fetch installed dependencies at the latest upstream commit and refresh
`agr.lock`. `agr sync` only installs what is missing — use `agr upgrade`
when you want to move past the currently pinned commit.

```bash
agr upgrade                              # Upgrade everything
agr upgrade anthropics/skills/pdf        # Upgrade one (full handle)
agr upgrade pdf                          # Upgrade one (short name)
agr upgrade pdf collaboration            # Upgrade several at once
```

Handles may be a full identifier (`user/repo/skill`, `./path/to/skill`) or
the short installed name (`pdf`). Short-name matching errors out when more
than one dependency has the same name; pass the full identifier to
disambiguate.

With no arguments, every dependency in the current scope is re-installed
and the lockfile is refreshed. Runs the same instruction-sync and
directory-migration stages as `agr sync` before installing.

!!! note "Same-repo siblings"
    Upgrading a single skill from a multi-skill repo (`user/repo/skillA`)
    only refreshes `skillA` — sibling skills in the same repo keep their
    existing lockfile commit and on-disk content. Run `agr upgrade` with
    no arguments, or name each sibling, to refresh them all together.

**Options:**

- `--global`, `-g` — Upgrade global dependencies from `~/.agr/agr.toml`.

**Examples:**

```bash
agr upgrade                              # Upgrade every resource in agr.toml
agr upgrade anthropics/skills/pdf        # Upgrade a single remote skill
agr upgrade pdf collaboration            # Upgrade several at once
agr upgrade ./my-skill                   # Re-copy a local skill
agr upgrade -g                           # Upgrade global dependencies
```

### agr run

Invoke an already-installed skill in the project's configured tool. `agr run`
mirrors [`agrx`](#agrx) for the persistent-skill case: it looks up the skill
in the tool's skills directory and shells out to the tool CLI with the skill
prompt — no download, no cleanup.

```bash
agr run <skill-name> [-- <extra prompt>]
```

**Arguments:**

- `skill-name` — Short name of an installed skill (e.g., `pdf`). Also matches
  collision-fallback installs (`user--skill`, `user--repo--skill`) when
  unambiguous.

**Options:**

- `--tool`, `-t` — Tool CLI to use. Overrides `default_tool` from `agr.toml`.
- `--interactive`, `-i` — Invoke the tool in interactive mode with the skill
  prompt prefilled.
- `--prompt`, `-p` `<text>` — Extra prompt text appended after the skill
  reference.
- `--global`, `-g` — Look up the skill in the global skills directory.

Anything after `--` is appended to the prompt as free-form input, after
`--prompt` (if given).

**Examples:**

```bash
agr run pdf                              # Run pdf in the default tool
agr run pdf -- "summarise report.pdf"    # Pass extra prompt text
agr run pdf --tool cursor                # Pick a specific tool
agr run pdf -i                           # Start an interactive session
agr run pdf -g                           # Run a globally-installed skill
```

Tool resolution order: `--tool` flag → `default_tool` in `agr.toml` → first
entry in `tools` → `claude`. If the skill is not installed for the chosen
tool, `agr run` lists the tools' available skills so you can correct the
name or run `agr sync` first.

### agr list

Show all dependencies (skills and ralphs) and their installation status.
The Type column shows whether each entry is local or remote, followed by
the dependency type (`skill` or `ralph`).

```bash
agr list
```

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                                           ┃ Type            ┃ Status               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ anthropics/skills/frontend-design              │ remote (skill)  │ installed            │
│ anthropics/skills/pdf                          │ remote (skill)  │ partial (claude)     │
│ vercel-labs/agent-browser/agent-browser        │ remote (skill)  │ not synced           │
│ your-username/agent-resources/bug-hunter       │ remote (ralph)  │ installed            │
│ ./skills/local-skill                           │ local  (skill)  │ installed            │
└────────────────────────────────────────────────┴─────────────────┴──────────────────────┘
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `installed` | Installed in all configured tools (skill), or present at `.agents/ralphs/<name>/` (ralph) |
| `partial (tool1, tool2)` | Skills only — installed in some tools but not all; lists which tools have it |
| `not synced` | Listed in `agr.toml` but not installed. Run `agr sync` to install. |
| `invalid` | Handle in `agr.toml` cannot be parsed. Check the handle format. |

!!! tip "Partial installs"
    You'll see `partial` status when using [multiple tools](tools.md#target-multiple-tools-at-once)
    and a skill is only installed in some of them. Run `agr sync` to install the
    missing copies, or `agr upgrade <handle>` to refresh from upstream everywhere.

**Options:**

- `--global`, `-g` — List global skills from `~/.agr/agr.toml`

### agr init

Create `agr.toml` or a skill scaffold.

```bash
agr init              # Create agr.toml
agr init <name>       # Create skill scaffold
```

`agr init` creates `agr.toml` and auto-detects which tools you use from repo
signals (`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.).

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

### agr config

Manage `agr.toml` configuration.

```bash
agr config show
```

```text
Config: /Users/you/project/agr.toml

  tools                    = claude, codex, opencode
  default_tool             = claude
  default_source           = github
  sync_instructions        = true
  canonical_instructions   = CLAUDE.md

Sources:
  - github [git] https://github.com/{owner}/{repo}.git (default)
```

```bash
agr config path
```

```text
/Users/you/project/agr.toml
```

```bash
agr config get tools
```

```text
claude codex opencode
```

**All subcommands:**

```bash
agr config show                              # View formatted config
agr config path                              # Print agr.toml path
agr config edit                              # Open in $VISUAL or $EDITOR
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

- `--type` — Source type (when key is `sources`). Defaults to `git`.
- `--url` — Source URL (when key is `sources`)

**Examples:**

```bash
agr config set tools claude codex opencode
agr config set default_tool claude
agr config add tools cursor
agr config remove tools cursor            # ⚠ deletes skills from that tool
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr config add sources my-source --url "https://git.example.com/{owner}/{repo}.git"
agr config unset default_tool
```

### agrx

Run a skill temporarily without adding to `agr.toml`.

```bash
agrx <handle> [options]
```

Downloads the skill, runs it with the selected tool, and cleans up afterwards.
See the [agrx guide](agrx.md) for usage patterns and examples.

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
agrx vercel-labs/agent-browser/agent-browser -i
agrx vercel-labs/agent-browser/agent-browser --source github
```

## agr.toml Format

```toml
default_source = "github" # (1)!
tools = ["claude", "codex", "opencode"] # (2)!
default_tool = "claude" # (3)!
sync_instructions = true # (4)!
canonical_instructions = "CLAUDE.md" # (5)!

dependencies = [ # (6)!
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "vercel-labs/agent-browser/agent-browser", type = "skill"},
    {handle = "team/internal-tool", type = "skill", source = "my-server"}, # (7)!
    {path = "./local-skill", type = "skill"}, # (8)!
    {handle = "your-username/agent-resources/dev-workflow", type = "package"}, # (10)!
    {handle = "your-username/agent-resources/bug-hunter", type = "ralph"}, # (11)!
]

[[source]] # (9)!
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

1. Source used when `--source` is not passed to `agr add` or `agrx`
2. Skills are installed into all listed tools on every `agr add` and `agr sync`. Ralphs ignore this list.
3. Tool used by `agrx` and for instruction sync — defaults to the first in `tools`
4. Copies the canonical instruction file to other tools on `agr sync`
5. The instruction file treated as the source of truth (`CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`)
6. Must appear before any `[[source]]` blocks — each entry needs `type = "skill"`, `type = "ralph"`, or `type = "package"` plus either `handle` or `path`. `type` is set automatically by `agr add`.
7. Pin a dependency to a specific source instead of using `default_source`
8. Local path dependencies point to a directory on disk — no Git fetch needed
9. Each `[[source]]` defines a Git server URL template with `{owner}` and `{repo}` placeholders
10. Package dependencies expand into their transitive skills and ralphs
11. Ralph dependencies install once into `.agents/ralphs/<name>/` per project — see the [Ralph Directory](ralphs.md)

## agr.lock Format

`agr.lock` sits next to `agr.toml` and pins the exact git commit SHA and
content hash of every resolved dependency. It is auto-generated by
`agr add`, `agr remove`, and `agr sync` — **do not edit by hand**. Commit
it so `agr sync --frozen` (and your teammates) get byte-identical installs.

```toml
# This file is auto-generated by agr. Do not edit.

version = 1

[[skill]]
handle = "anthropics/skills/pdf"
source = "github"
commit = "a0d5bfd4d9658073029d33f979ac5a027568caec"
content-hash = "sha256:75e47183c30bc8651e76286680eddac88a3024a7ee5a7f1bc486d4d3fdee34ce"
installed-name = "pdf"

[[skill]]
path = "skills/internal-review"
installed-name = "internal-review"

[[ralph]]
handle = "your-username/agent-resources/bug-hunter"
source = "github"
commit = "9859f7bceb7a46af8482cabb9aa24e0d38a49413"
content-hash = "sha256:fa1ce825fa7e11cd5aac55ee7eac5e9c918e3af113b7988fdbd281a319acc110"
installed-name = "bug-hunter"
```

**Fields:**

| Field | Present on | Meaning |
|---|---|---|
| `version` | top level | Lockfile schema version (currently `1`) |
| `[[skill]]` / `[[ralph]]` | per dep | One entry per resolved dependency, grouped by resource type |
| `handle` | remote deps | The handle the dependency was resolved from |
| `path` | local deps | The local path the dependency was resolved from |
| `source` | remote deps | Source name used to fetch (e.g. `"github"`) |
| `commit` | remote deps | Pinned full 40-char git commit SHA |
| `content-hash` | remote deps | `sha256:` hash of the installed directory's contents |
| `installed-name` | all deps | The directory name the resource is installed under |

See [`agr sync`](#agr-sync) for `--frozen` and `--locked` — the flags that
make CI honor the lockfile strictly.

## Python SDK

For programmatic access to skills, use the [Python SDK](sdk.md) — it provides
`Skill`, `list_skills`, `skill_info`, and caching APIs.

## Troubleshooting

See the [Troubleshooting](troubleshooting.md) page for solutions to common
errors — installation failures, handle format issues, authentication problems,
and more.

## What's New

See the [Changelog](changelog.md) for release notes, new features, and
breaking changes.

## Next Steps

- [Creating Skills](creating.md) — Build and publish your own skills
- [Core Concepts](concepts.md) — Understand handles, sources, and scopes
- [Teams](teams.md) — Share skills across your team with `agr.toml`
