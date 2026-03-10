---
title: Reference
---

# Reference

## Common Workflows

| Goal | Command(s) |
|------|------------|
| Install a skill for your tool | `agr add <handle>` |
| Run a skill once | `agrx <handle>` |
| Team sync | Add to `agr.toml`, then `agr sync` |
| Configure tool targets | `agr config tools ...` |
| Create a new skill | `agr init <name>` |
| Migrate old rules/commands | `agrx kasperjunge/migrate-to-skills` |

## CLI Commands

**Beta note:** Multi-source support is only in the beta release right now. Install `agr==0.7.2b1` to use `default_source`, `[[source]]`, or `--source`.

### agr add

Install skills from GitHub or local paths. Skills are installed into your tool's
skills folder (e.g. `.claude/skills/`, `.agents/skills/ (legacy: .codex/skills/)`, `.cursor/skills/`,
`.opencode/skill/`, `.github/skills/`, `.agent/skills/`).

```bash
agr add <handle>...
```

**Arguments:**

- `handle` — Skill handle (`user/skill` or `user/repo/skill`) or local path (`./path`)

**Options:**

- `--overwrite`, `-o` — Replace existing skills
- `--source <name>` — Use a specific source from `agr.toml`
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

Create `agr.toml` (with auto-discovery) or a skill scaffold.

```bash
agr init              # Create agr.toml
agr init <name>       # Create skill scaffold
```

By default, `agr init` discovers skills in the repo (based on the skills
spec) and adds them to `agr.toml` as local path dependencies. It also
detects tools from existing tool folders when available.

Skills inside tool folders (e.g. `.claude/skills/`, `.agents/skills/ (legacy: .codex/skills/)`,
`.cursor/skills/`, `.opencode/skill/`, `.github/skills/`, `.agent/skills/`) are ignored by default to keep configs
clean. Use `--migrate` to move them into `./skills/`.

**Options:**

- `--interactive`, `-i` — Run a guided setup wizard
- `--tools` — Comma-separated tool list (e.g., `claude,codex,opencode`)
- `--default-tool` — Default tool for `agrx` and instruction sync
- `--sync-instructions/--no-sync-instructions` — Sync instruction files on `agr sync`
- `--canonical-instructions` — Canonical instruction file (`AGENTS.md` or `CLAUDE.md`)
- `--migrate` — Move tool-folder skills into `./skills/`
- `--prefer` — Duplicate resolution (`shallowest` or `newest`)

**Examples:**

```bash
agr init                    # Creates agr.toml in current directory
agr init my-skill           # Creates my-skill/SKILL.md
agr init -i                 # Guided setup
agr init --tools claude,codex,opencode --default-tool claude
agr init --sync-instructions --canonical-instructions CLAUDE.md
agr init --migrate          # Copy skills into ./skills/
```

### agr config

Manage `agr.toml` configuration, including tool selection and `agrx` defaults.

```bash
agr config tools list
agr config tools add codex
agr config tools set claude codex opencode
agr config tools remove codex
agr config tools unset codex
agr config default-tool set codex
agr config default-tool unset
```

`agr tools ...` remains available as a deprecated alias for `agr config tools ...`.

### agrx

Run a skill temporarily without adding to `agr.toml`.

```bash
agrx <handle> [options]
```

Downloads the skill, runs it with the selected tool, and cleans up afterwards.

**Options:**

- `--interactive`, `-i` — Run skill, then continue in interactive mode
- `--prompt`, `-p` — Prompt to pass to the skill
- `--global`, `-g` — Install to the global tool skills directory (e.g. `~/.claude/skills/`, `~/.agents/skills/ (legacy: ~/.codex/skills/)`, `~/.config/opencode/skill/`, `~/.gemini/antigravity/skills/`) instead of the repo-local one
- `--source <name>` — Use a specific source from `agr.toml`

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
- `canonical_instructions` — Canonical instruction file (`AGENTS.md` or `CLAUDE.md`)

## Troubleshooting

### Skill not found

Check that the skill exists in the repository. agr searches:

- `resources/skills/{name}/SKILL.md`
- `skills/{name}/SKILL.md`
- `{name}/SKILL.md`

### Skill already exists

Use `--overwrite`:

```bash
agr add user/skill --overwrite
```

### Repository not found

Check:

- Username and repo name are correct
- Repository is public
- Default branch is `main`

### Git not installed

Remote installs require `git` to be available on your system.

### Not in a git repository

`agrx` requires a git repository (or use `--global`):

```bash
agrx user/skill --global
```

### Network errors

Ensure the repository is public and you have internet access.
