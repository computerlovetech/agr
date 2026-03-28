---
title: How to Share AI Agent Skills Across a Team
description: Share AI coding agent skills with your team using agr.toml as a single source of truth — like package.json for AI prompts. Sync CLAUDE.md, AGENTS.md, and GEMINI.md across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity.
keywords:
  - share AI agent skills across team
  - sync AI skills across developers
  - team AI coding tools setup
  - share CLAUDE.md with team
  - sync AGENTS.md across developers
  - share cursor rules across team
  - standardize AI agent prompts team
  - onboard developers AI coding tools
  - agr sync team
  - CI/CD AI agent skills pipeline
  - private AI skills GitHub repo
  - multi-tool AI team setup
  - manage AI prompts in git
  - share custom prompts Claude Code Cursor
  - npm install for AI agent skills
  - sync coding agent instructions across repos
---

# Share AI Agent Skills Across Your Team

!!! tldr
    Commit `agr.toml` to your repo — teammates run `agr sync` to get every
    skill. Multi-tool teams set `tools = ["claude", "cursor", ...]` so one
    `agr add` installs everywhere. Use `GITHUB_TOKEN` for private repos and
    CI/CD.

**Prerequisites:** [agr installed](tutorial.md#step-1-install-agr), a git
repository, and at least one [supported AI tool](tools.md) (Claude Code,
Cursor, Codex, OpenCode, Copilot, or Antigravity)

Set up agr so everyone shares the same AI coding skills, stays in sync
across Claude Code, Cursor, Codex, and other tools — and gets productive on
day one.

**Key terms:** A **skill** is a directory containing a `SKILL.md` file with
instructions for an AI coding agent. A **handle** like `anthropics/skills/pdf`
identifies a skill on GitHub. `agr.toml` tracks your project's skill
dependencies — similar to `package.json` or `Cargo.toml`. See
[Core Concepts](concepts.md) for details.

---

## Set up your project

### 1. Initialize agr

Run this in your repo root:

```bash
agr init
```

This creates `agr.toml` and auto-detects which tools your team uses from
repo signals (`.claude/`, `.cursor/`, `CLAUDE.md`, etc.).

To target specific tools:

```bash
agr init --tools claude,cursor,codex
```

### 2. Add skills

Install the skills your team needs:

```bash
agr add anthropics/skills/frontend-design
agr add anthropics/skills/pdf
agr add ./skills/internal-review   # Local skills work too
```

Each `agr add` updates `agr.toml` with the dependency.

### 3. Commit agr.toml

```bash
git add agr.toml
git commit -m "Add agr skill dependencies"
```

`agr.toml` is your skill lockfile. Commit it so every clone starts with the
same skills.

### What to commit

`agr.toml` is like `package.json` — commit it. The tool skills directories
are like `node_modules` — gitignore them, since `agr sync` recreates them.

| Commit | Gitignore |
|--------|-----------|
| `agr.toml` | `.claude/skills/` |
| `./skills/` (local skills) | `.cursor/skills/` |
| | `.agents/skills/` |
| | `.opencode/skills/` |
| | `.github/skills/` |
| | `.gemini/skills/` |

Add the tool directories to `.gitignore`:

```gitignore
# agr-managed skill directories (recreated by agr sync)
.claude/skills/
.cursor/skills/
.agents/skills/
.opencode/skills/
.github/skills/
.gemini/skills/
```

You only need to gitignore the tools you've configured — but listing all of
them is harmless and avoids surprises if someone adds a tool later.

??? tip "What about local skills in `./skills/`?"
    Local skills referenced by path in `agr.toml` (e.g., `{path = "./skills/my-skill"}`)
    live in your repo and **should be committed**. They're your team's custom
    skills — `agr sync` installs them from the local path, not from GitHub.

### 4. Teammates install

After cloning the repo, a new teammate runs two commands:

```bash
uv tool install agr   # One-time install (or: pipx install agr)
agr sync              # Install all skills from agr.toml
```

Done. Everyone has the same skills in the same tool.

---

## Multi-tool teams

If your team uses different AI coding tools, configure all of them:

```bash
agr config set tools claude cursor codex
```

When anyone runs `agr add` or `agr sync`, skills are installed into every
configured tool's skills directory simultaneously. A skill added by someone
using Claude Code is also available to the teammate using Cursor.

See [Supported Tools](tools.md) for details on each tool.

### Keep instruction files in sync

When using multiple tools, you probably want one source of truth for your
project-level instructions (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`). Enable
instruction syncing:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

Now `agr sync` copies `CLAUDE.md` content to `AGENTS.md` and `GEMINI.md`
as needed by your configured tools. Maintain one file, all tools stay aligned.

See [Configuration — Instruction Syncing](configuration.md#instruction-syncing) for details.

---

## Private skills

Teams often keep internal skills in private GitHub repositories. agr supports
this through environment variables — no configuration changes needed.

### Developer setup

Each developer exports a GitHub token:

```bash
export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
```

Or, if you use the [GitHub CLI](https://cli.github.com/):

```bash
export GH_TOKEN="$(gh auth token)"
```

The token needs **Contents: Read-only** access on the repositories containing
your skills. Fine-grained tokens scoped to specific repos are recommended.

Add the export to your shell profile (`~/.zshrc`, `~/.bashrc`) for permanent
access.

### CI/CD setup

For automated environments, pass the token as a secret:

```yaml
- name: Sync skills
  run: agr sync -q
  env:
    GITHUB_TOKEN: ${{ secrets.SKILL_TOKEN }}
```

Create a fine-grained token with **Contents: Read-only** on your skill
repositories and add it as a repository secret.

See [Configuration — Private Repositories](configuration.md#private-repositories) for full details.

---

## CI/CD integration

Add `agr sync` to your CI pipeline to ensure skills are available in
automated environments.

### GitHub Actions

A complete workflow that syncs skills before your CI jobs run:

```yaml
name: Sync agent skills
on: [push, pull_request]

jobs:
  sync-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v6 # (1)!

      - name: Install agr
        run: uv tool install agr

      - name: Sync skills
        run: agr sync -q # (2)!
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} # (3)!
```

1. Sets up `uv` — see [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) for options
2. `-q` suppresses non-error output, keeping CI logs clean
3. Only needed for private skill repos. For public skills, remove this line.

??? note "Run as a step in an existing workflow"
    If you already have a CI workflow, add just the install and sync steps:

    ```yaml
    - name: Install agr
      run: uv tool install agr

    - name: Sync skills
      run: agr sync -q
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    ```

### Other CI systems

agr is a standard Python CLI. Install it with `pip install agr` or
`pipx install agr` in any CI environment that has Python 3.10+ and Git:

```bash
pip install agr
agr sync -q
```

Set `GITHUB_TOKEN` in your CI environment variables for private repos.

---

## Onboarding existing projects

If your project already has skills installed manually (copied into
`.claude/skills/` or similar), use the interactive onboard command:

```bash
agr onboard
```

This walks you through:

- Selecting which tools your team uses
- Discovering skills already in your tool directories
- Migrating them into `./skills/` as local dependencies
- Creating your `agr.toml`

If you have `.claude/commands/`, `.cursorrules`, or other files that should
become skills:

```bash
agrx kasperjunge/agent-resources/migrate-to-skills
```

---

## Adding and updating skills

### Add a new skill for the team

```bash
agr add anthropics/skills/pdf
git add agr.toml
git commit -m "Add pdf skill"
```

Teammates pick it up on their next `agr sync`.

### Update a skill to the latest version

```bash
agr add anthropics/skills/pdf --overwrite
```

The `--overwrite` flag replaces the installed skill with the latest version
from GitHub. Commit the updated skill files so the team stays in sync.

### Remove a skill

```bash
agr remove anthropics/skills/pdf
git add agr.toml
git commit -m "Remove pdf skill"
```

---

## Recommended workflow

A typical team workflow looks like this:

1. **One person** sets up `agr.toml` with the team's skills and commits it
2. **Everyone** runs `agr sync` after pulling to stay up to date
3. **Anyone** can add or remove skills — changes go through normal code review
4. **CI** runs `agr sync` to ensure skills are available in automated environments

The `agr.toml` file is the single source of truth. Treat it like any other
project dependency file.

---

## Next steps

- [Configuration](configuration.md) — Custom sources, global installs, full
  `agr.toml` reference
- [Creating Skills](creating.md) — Build internal skills for your team
- [Supported Tools](tools.md) — How agr works with each AI coding tool
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
