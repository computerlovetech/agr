---
title: Core Concepts
---

# Core Concepts

This page explains the building blocks of agr. Read it after the
[Tutorial](tutorial.md) to understand *why* things work the way they do, or
skim it before diving into [Configuration](configuration.md).

---

## Skills

A **skill** is a folder containing a `SKILL.md` file. The file has YAML
frontmatter (`name`, `description`) and a markdown body with instructions for
an AI coding agent.

```
my-skill/
├── SKILL.md          # Required — agent instructions
├── scripts/          # Optional — helper scripts
│   └── validate.sh
└── references/       # Optional — reference docs
    └── api-schema.json
```

When you install a skill, agr copies this entire directory into your tool's
skills folder. The AI tool reads `SKILL.md` and follows the instructions when
the skill is invoked.

Skills are tool-agnostic. The same `SKILL.md` works in Claude Code, Cursor,
Codex, OpenCode, Copilot, and Antigravity — agr installs it into the right
place for each tool.

See [Creating Skills](creating.md) for how to write one.

---

## Handles

A **handle** is how you refer to a skill. It tells agr where to find it.

### Remote handles

```
user/skill            →  github.com/user/skills  repo, "skill" directory
user/repo/skill       →  github.com/user/repo    repo, "skill" directory
```

The two-part form (`user/skill`) assumes the skill lives in a repo named
`skills`. If it doesn't, use the three-part form (`user/repo/skill`).

### Local handles

```
./path/to/skill       →  Local directory on disk
```

Local handles point to a skill directory on your filesystem. They're useful
for testing skills before publishing or for project-specific skills that don't
need a remote repo.

### How resolution works

When you run `agr add user/repo/skill`:

1. agr clones `github.com/user/repo` (using sparse checkout for speed)
2. It recursively searches the repo for a directory named `skill` that contains
   `SKILL.md`
3. It copies that directory into your tool's skills folder

The search finds the skill regardless of nesting depth (`skills/skill/`,
`resources/skills/skill/`, `skill/`). When multiple matches exist, the
shallowest path wins.

---

## Tools

A **tool** is an AI coding agent that reads skills. agr supports six:

| Tool | Config name | How skills are invoked |
|------|-------------|----------------------|
| Claude Code | `claude` | `/skill-name` |
| Cursor | `cursor` | `/skill-name` |
| OpenAI Codex | `codex` | `$skill-name` |
| OpenCode | `opencode` | `skill-name` |
| GitHub Copilot | `copilot` | `/skill-name` |
| Antigravity | `antigravity` | (via IDE) |

Each tool has its own skills directory where agr installs skills:

| Tool | Project directory | Global directory |
|------|------------------|-----------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Antigravity | `.agent/skills/` | `~/.gemini/antigravity/skills/` |

When you configure multiple tools, `agr add` and `agr sync` install skills
into all of them simultaneously. Configure your tools with:

```bash
agr config set tools claude cursor codex
```

See [Supported Tools](tools.md) for details on each tool.

---

## Sources

A **source** defines where agr fetches remote skills from. The default source
is GitHub:

```toml
[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

The `{owner}` and `{repo}` placeholders are filled from the handle. For
example, `agr add anthropics/skills/pdf` clones
`https://github.com/anthropics/skills.git`.

You can add custom sources for GitLab, self-hosted Git servers, or any host
that supports Git over HTTPS:

```bash
agr config add sources gitlab --type git --url "https://gitlab.com/{owner}/{repo}.git"
agr add team/skill --source gitlab
```

Set a default source so you don't have to pass `--source` every time:

```bash
agr config set default_source gitlab
```

See [Configuration — Sources](configuration.md#sources) for more.

---

## Scopes: Local vs Global

agr has two scopes:

**Local** (default) — Skills installed in the current project. Tracked in
`./agr.toml`. Installed into project-level directories (e.g., `.claude/skills/`).
These skills are only available when working in this project.

**Global** (`-g` flag) — Skills available everywhere. Tracked in
`~/.agr/agr.toml`. Installed into per-tool global directories (e.g.,
`~/.claude/skills/`). These skills are available in every project.

```bash
agr add anthropics/skills/pdf              # Local: this project only
agr add -g anthropics/skills/skill-creator  # Global: every project
```

Use local for project-specific skills that teammates should share. Use global
for personal utilities you want everywhere.

The two scopes are independent — a skill can be installed both locally and
globally without conflict.

---

## agr.toml

`agr.toml` is the manifest file that tracks your skill dependencies and
configuration. It's similar to `package.json` or `pyproject.toml` — commit it
to version control so your team shares the same skills.

```toml
tools = ["claude", "cursor"]
default_tool = "claude"

dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/pdf", type = "skill"},
    {path = "./skills/internal-review", type = "skill"},
]
```

### How agr finds it

agr looks for `agr.toml` starting from the current directory and searching
upward through parent directories until it finds one or reaches the filesystem
root. This means you can run `agr` commands from any subdirectory in your
project.

For global scope (`-g`), agr uses `~/.agr/agr.toml`.

### Creating it

You don't need to create `agr.toml` manually. It's created automatically by:

- `agr init` — Creates the file and auto-detects your tools
- `agr add` — Creates the file if it doesn't exist
- `agr onboard` — Interactive guided setup

See [Configuration](configuration.md) for all options and
[Reference — agr.toml Format](reference.md#agrtoml-format) for the full schema.

---

## Instruction Syncing

Different tools use different instruction files:

| File | Tools |
|------|-------|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | Cursor, Codex, OpenCode, Copilot |
| `GEMINI.md` | Antigravity |

If you use multiple tools, you can designate one file as **canonical** and have
agr copy its content to the others automatically:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr sync   # Copies CLAUDE.md content to AGENTS.md, GEMINI.md as needed
```

This keeps all your tools aligned without maintaining multiple files manually.

---

## The Two CLIs

agr ships two commands:

**`agr`** — The main CLI for managing skills. Install, remove, sync, list,
configure. Changes persist in `agr.toml` and your tool's skills directories.

**`agrx`** — The ephemeral runner. Downloads a skill, runs it with your tool's
CLI, and cleans up. Nothing is saved. Think of it as `npx` for skills.

```bash
agr add anthropics/skills/pdf         # Permanent: install and track
agrx anthropics/skills/pdf            # Temporary: run once and clean up
```

Use `agr` when you want a skill to stick around. Use `agrx` when you want to
try something quickly or run a one-off task.

See [agrx](agrx.md) for full details.

---

## What Happens When You Install

Here's the full flow when you run `agr add anthropics/skills/pdf`:

1. **Parse the handle** — `anthropics` is the owner, `skills` is the repo,
   `pdf` is the skill name
2. **Load config** — Read `agr.toml` (or create it) to find configured tools
   and sources
3. **Clone the repo** — Sparse-checkout `github.com/anthropics/skills`
4. **Find the skill** — Recursively search for a directory named `pdf`
   containing `SKILL.md`
5. **Install to each tool** — Copy the skill directory to each configured
   tool's skills folder (e.g., `.claude/skills/pdf/`, `.cursor/skills/pdf/`)
6. **Write metadata** — Save `.agr.json` in each installed copy with the
   source handle, revision, and content hash
7. **Update agr.toml** — Add the dependency to the manifest

If any tool's install fails, already-installed copies are rolled back
automatically.

---

## Next Steps

- [Configuration](configuration.md) — Multi-tool setup, custom sources,
  instruction syncing
- [Supported Tools](tools.md) — Detailed info on each tool's behavior
- [Creating Skills](creating.md) — Write and share your own skills
- [Reference](reference.md) — Every command, flag, and config option
