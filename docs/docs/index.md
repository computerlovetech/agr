---
title: Home
---

# AGR — Skills for AI Agents

A package and project manager for AI agent skills. Install, share, and run skills from GitHub with a single command.

!!! note "Migrating from rules, subagents, or slash commands?"
    Support for rules, subagents, and slash commands has been removed. Most AI coding agents are converging on skills as the standard format, so agr now focuses exclusively on skills. To convert your existing files to skills, run:

    ```bash
    agrx kasperjunge/migrate-to-skills
    agrx kasperjunge/migrate-to-skills -p "convert files in ./my-commands"
    ```

## Install

```bash
pip install agr
```

**Beta note:** Multi-source support is only in the beta release right now. Install `agr==0.7.2b1` to use `default_source`, `[[source]]`, or `--source`.

## Choose Your Path

### Install a Skill (persist it)

```bash
agr add anthropics/skills/frontend-design
```

This installs the skill into your tool's skills folder. Use `--source <name>` to
pick a non-default source from `agr.toml`.

### Run a Skill Once (no install)

```bash
agrx anthropics/skills/pdf                  # Run once, then clean up
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/pdf -i               # Interactive: run skill, then continue chatting
```

The `-i` flag runs the skill first, then starts an interactive session so you can
continue the conversation.

### Share with Your Team

Dependencies are tracked in `agr.toml`:

```toml
default_source = "github"

dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/skill-creator", type = "skill"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

Teammates install everything with:

```bash
agr sync
```

### Create a Skill

```bash
agr init my-skill
```

Then edit `my-skill/SKILL.md`. If you want it in this repo, place it under
`./skills/` and run `agr init` to update `agr.toml`.

### Migrate Old Rules or Commands

```bash
agrx kasperjunge/migrate-to-skills
```

## Commands (Quick Reference)

| Command | What it does |
|---------|-------------|
| `agr add <handle>` | Install a skill |
| `agr remove <handle>` | Uninstall a skill |
| `agr sync` | Install all dependencies from `agr.toml` |
| `agr list` | Show skills and installation status |
| `agr init` | Create `agr.toml` (auto-discovery) |
| `agr init <name>` | Create a skill scaffold |
| `agrx <handle>` | Run a skill temporarily |

## Handle Format

```bash
agr add user/skill              # From user's "skills" repo
agr add user/repo/skill         # From a different repo
agr add ./path/to/skill         # Local path
```

If a user's repo is named `skills`, you can skip the repo name:

```bash
agr add kasperjunge/commit                    # From kasperjunge/skills
agr add kasperjunge/skills/commit             # Same thing (explicit)
```

Note: `user/skill` now defaults to `skills`. During a deprecation period, agr
will fall back to `agent-resources` (with a warning) if the skill isn't found in
`skills`.

## How Skill Discovery Works

When you run `agr add user/repo/skill`, agr searches that repo for a skill named
`skill`. It will be found if it exists in:

- `resources/skills/{skill}/SKILL.md`
- `skills/{skill}/SKILL.md`
- `{skill}/SKILL.md`

If two skills have the same name, you'll get an error.

## Project Setup

`agr init` discovers skills in your repo (based on the skills specification) and
adds them to `agr.toml` as local path dependencies. It also detects tools from
existing tool folders.

```bash
agr init       # Auto-discover skills and create agr.toml
agr init -i    # Guided setup
```

By default, skills inside tool folders (e.g. `.claude/skills/`, `.agents/skills/ (legacy: .codex/skills/)`,
`.cursor/skills/`, `.opencode/skill/`, `.github/skills/`, `.agent/skills/`) are ignored to avoid messy configs. To
bring them into your repo, run:

```bash
agr init --migrate
```

## Example Skills

```bash
agr add anthropics/skills/frontend-design    # Build production-grade UIs
agr add anthropics/skills/skill-creator      # Create new skills
agr add anthropics/skills/pdf                # Work with PDF documents
```

Browse more at [github.com/anthropics/skills](https://github.com/anthropics/skills).

## Next Steps

- [Create your own skill](creating.md)
- [CLI reference](reference.md)
