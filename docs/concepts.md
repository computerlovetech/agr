---
title: "How agr Works — Skills, Handles, Sources, Scopes, and the Sync Lifecycle"
description: How agr manages AI agent resources — SKILL.md format, handle resolution, multi-tool sync across Claude Code, Cursor, Codex, and more. Understand skills, handles, sources, scopes, and agr.toml.
keywords:
  - how agr works
  - agr skills explained
  - skill handles resolution
  - SKILL.md format
  - agr.toml manifest
  - local vs global skills
  - agr sync lifecycle
  - agr instruction syncing
  - AI agent resource scopes
  - agr sources configuration
  - how AI agent resources work
  - manage AI coding agent prompts across tools
  - sync prompts between Claude Code and Cursor
  - package manager for AI agents
  - share AI agent resources across team
  - SKILL.md vs CLAUDE.md vs AGENTS.md
  - install AI resources from GitHub
  - AI agent resource directory structure
  - multi-tool AI resource management
  - keep AI agent instructions in sync
  - Agentic Engineering
---

# Core Concepts

!!! tldr
    agr manages **resources** for AI coding agents. Today there are two
    resource types: **skills** (folders with a `SKILL.md`, consumed by AI
    tools) and **ralphs** (folders with a `RALPH.md`, autonomous loops
    executed by a ralph runtime). Around those sit **handles** (like
    `user/skill`) to reference them, **tools** (Claude Code, Cursor, etc.)
    that consume skills, **sources** (where to fetch from), and **scopes**
    (local per-project vs global). [`agr.toml`](#agrtoml) is the manifest
    and [`agr.lock`](#agrlock) pins exact commit SHAs.

This page explains the building blocks of agr. Read it after the
[Tutorial](tutorial.md) to understand *why* things work the way they do, or
skim it before diving into [Configuration](configuration.md).

---

## Resources

**agr** stands for *agent resources*. A **resource** is a versioned,
shareable directory that gives an AI coding agent new capabilities. agr's
job is to package these resources, distribute them from Git, and sync them
into your project reproducibly.

Today agr supports two resource types:

| Resource | Marker file | Consumed by | Installed to | `agr.toml` `type` |
|---|---|---|---|---|
| **Skill** | `SKILL.md` | AI coding tool (Claude Code, Cursor, Codex, OpenCode, Copilot, Antigravity) | Each configured tool's skills directory (e.g. `.claude/skills/`) | `"skill"` |
| **Ralph** | `RALPH.md` | A ralph runtime such as [ralphify](https://github.com/kasperjunge/ralphify) | `.agents/ralphs/<name>/` (once per project) | `"ralph"` |

Every other concept on this page — handles, sources, scopes, the
manifest, the lockfile, the install flow — applies to **both** resource
types. `agr add`, `agr sync`, `agr remove`, and `agr list` all accept
either kind; agr detects which is which from the marker file (for local
paths) or by searching the remote repo (for remote handles).

!!! note "Why two resource types?"
    Skills and ralphs answer different questions. A **skill** is context an
    AI tool loads to do what *you* asked it to. A **ralph** is an
    autonomous loop that runs on its own under a ralph runtime, re-deriving
    progress from the codebase on every iteration. Both benefit from the
    same packaging, pinning, and team-sync story — so agr treats them as
    two types of the same underlying resource concept.

---

## Skills

A **skill** is a folder containing a `SKILL.md` file. The file has YAML
frontmatter (`name`, `description`) and a markdown body with instructions for
an AI coding agent.

```text
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

See [Creating Skills](creating.md) for how to write one, or browse the
[Skill Directory](skills.md) for published skills you can install.

---

## Ralphs

A **ralph** is a folder containing a `RALPH.md` file. Like a skill, it's a
portable directory you can install with `agr add`. Unlike a skill, it
describes an **autonomous agent loop** — a YAML frontmatter block with an
agent command, shell commands whose output fills the prompt, and args the
runtime fills in on each iteration:

```text
my-ralph/
├── RALPH.md          # Required — frontmatter + prompt body
└── scripts/          # Optional — helpers referenced from commands
    └── precheck.sh
```

Ralphs are not consumed by AI tools the way skills are. Instead, a
**ralph runtime** like [ralphify](https://github.com/kasperjunge/ralphify)
runs the loop: substitute command output and args into the body, invoke the
agent, repeat. agr only packages and distributes ralphs — running them is
the runtime's job.

Because a ralph is not tied to any particular AI tool, agr installs it
**once per project** into `.agents/ralphs/<name>/` rather than fanning out
into each tool's skills folder. For the same reason, global installs (`-g`)
skip ralph dependencies — a ralph's commands (like `uv run pytest`) only
make sense inside a specific project.

See the [Ralph Directory](ralphs.md) for the full `RALPH.md` format,
installation details, and publishing guide.

---

## Handles

A **handle** is how you refer to a skill. It tells agr where to find it.

### Remote handles

```text
skill                 →  default owner's skills repo, "skill" directory
user/skill            →  github.com/user/skills  repo, "skill" directory
user/repo/skill       →  github.com/user/repo    repo, "skill" directory
```

The simplest form is just a skill name (e.g. `agr add setup`). This resolves
using your `default_owner` setting (defaults to `computerlovetech`), so
`setup` becomes `computerlovetech/skills/setup`. You can change the default
owner in `agr.toml`:

```toml
default_owner = "myorg"
```

!!! note "1-part handles are expanded on save"
    When you run `agr add setup`, agr stores the fully-qualified handle
    `computerlovetech/setup` (or `myorg/setup` if you changed `default_owner`)
    in `agr.toml`. The 1-part form is a CLI convenience — it is not
    preserved in the manifest.

The two-part form (`user/skill`) assumes the skill lives in a repo named
`skills`. If it doesn't, use the three-part form (`user/repo/skill`).

### Local handles

```text
./path/to/skill       →  Local directory on disk
```

Local handles point to a skill directory on your filesystem. They're useful
for testing skills before publishing or for project-specific skills that don't
need a remote repo.

### How agr resolves a handle to files on disk

Every remote handle follows the same three-step flow — clone, search, copy:

1. **Clone** — agr sparse-checkouts the repo from GitHub (fast, even for large repos)
2. **Search** — it finds a directory named after the skill that contains `SKILL.md`
3. **Copy** — it installs that directory into each configured tool's skills folder

The handle format determines *which* repo gets cloned:

| Handle | Repo cloned | When to use |
|--------|-------------|-------------|
| `skill` | `github.com/<default_owner>/skills` | Quickest — uses `default_owner` from config |
| `user/skill` | `github.com/user/skills` | Explicit owner — repo is always named `skills` |
| `user/repo/skill` | `github.com/user/repo` | Skills live in a differently named repo |

The one-part form is the quickest way to install from the default registry.
The two-part form is the most common for third-party skills.

agr searches recursively regardless of nesting depth (`skills/skill/`,
`resources/skills/skill/`, `skill/`). When multiple matches exist, the
shallowest path wins.

!!! tip "Wrong handle format?"
    If `agr add user/repo` fails because it's actually a repo (not a skill in
    the `skills` repo), agr probes the repo and suggests the correct three-part
    handles — so you don't have to guess.

---

## Tools

A **tool** is an AI coding agent that reads skills. Tools only consume
skills — [ralphs](#ralphs) are consumed by a separate ralph runtime rather
than by any tool in this list. agr supports six tools:

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
| Antigravity | `.gemini/skills/` | `~/.gemini/skills/` |

When you configure multiple tools, `agr add` and `agr sync` install skills
into all of them simultaneously. Configure your tools with:

```bash
agr config set tools claude cursor codex
```

### How skills are named on disk

Skills are installed using their plain name — `agr add anthropics/skills/pdf`
creates a `pdf/` directory inside each tool's skills folder.

If two different handles share the same skill name (e.g., `alice/skills/lint`
and `bob/tools/lint`), agr falls back to a fully-qualified directory name
(`alice--skills--lint/`, `bob--tools--lint/`) to avoid collisions. You'll
still invoke the skill by its plain name in your tool — agr handles the
mapping.

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
agr config add sources gitlab --url "https://gitlab.com/{owner}/{repo}.git"
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

Use local for project-specific skills that teammates should share (see
[Teams](teams.md) for the full team setup). Use global for personal utilities
you want everywhere.

The two scopes are independent — a skill can be installed both locally and
globally without conflict.

---

## agr.toml and agr.lock

agr tracks your project's resources in two committed files, just like npm
uses `package.json` + `package-lock.json` or Cargo uses `Cargo.toml` +
`Cargo.lock`:

| File | Hand-edited? | What it records |
|---|---|---|
| **`agr.toml`** | Yes | The manifest: which resources your team depends on, plus settings (tools, sources, default owner, …) |
| **`agr.lock`** | No — auto-generated | The resolved state: exact git commit SHA, content hash, and installed name for every resolved dependency |

**Commit both.** `agr.toml` declares intent; `agr.lock` makes installs
reproducible across machines and over time.

### agr.toml

The manifest. Hand-edited (or updated via `agr add` / `agr remove`) and
committed to version control so your team shares the same resources.

```toml
tools = ["claude", "cursor"]
default_tool = "claude"

dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/pdf", type = "skill"},
    {path = "./skills/internal-review", type = "skill"},
    {handle = "your-username/agent-resources/bug-hunter", type = "ralph"},
]
```

Each entry has a `type` field — `"skill"` or `"ralph"`. agr sets this
automatically on `agr add`; you rarely need to touch it by hand.

**How agr finds it.** agr looks for `agr.toml` starting from the current
directory and searching upward through parent directories until it finds one
or reaches the filesystem root. You can run `agr` commands from any
subdirectory. For global scope (`-g`), agr uses `~/.agr/agr.toml`.

**Creating it.** `agr init` creates the file and auto-detects your tools;
`agr add` creates it on the fly if it doesn't exist.

### agr.lock

`agr.lock` is written alongside `agr.toml` by `agr add`, `agr remove`, and
`agr sync`. It pins the exact git commit SHA and content hash for every
resolved dependency, so a teammate running `agr sync` later gets the same
bytes you did — even if upstream `main` has moved on.

```toml
# This file is auto-generated by agr. Do not edit.

version = 1

[[skill]]
handle = "anthropics/skills/pdf"
source = "github"
commit = "a0d5bfd4d9658073029d33f979ac5a027568caec"
content-hash = "sha256:75e47183c30bc8651e76286680eddac88a3024a7ee5a7f1bc486d4d3fdee34ce"
installed-name = "pdf"

[[ralph]]
handle = "your-username/agent-resources/bug-hunter"
source = "github"
commit = "9859f7bceb7a46af8482cabb9aa24e0d38a49413"
content-hash = "sha256:fa1ce825fa7e11cd5aac55ee7eac5e9c918e3af113b7988fdbd281a319acc110"
installed-name = "bug-hunter"
```

**Lockfile-aware sync modes** (for CI and reproducibility):

| Command | Behavior |
|---|---|
| `agr sync` | Install missing dependencies, refresh `agr.lock` with the commits that were actually used. |
| `agr sync --frozen` | Install **exactly** what `agr.lock` specifies. Fail if `agr.lock` is missing. Never re-resolve. |
| `agr sync --locked` | Fail if `agr.lock` is out of date vs `agr.toml` (e.g. a teammate added a dep but forgot to commit the lockfile), then install from the lockfile. |

Use `--frozen` in CI and deploy pipelines where you want guaranteed-identical
installs. Use `--locked` in CI to assert that whoever opened the PR committed
a consistent lockfile.

!!! warning "Don't edit agr.lock by hand"
    agr overwrites `agr.lock` on every mutating command. Hand-edits will be
    clobbered. If you need to update a pinned commit, run `agr add <handle>
    --overwrite` (which re-resolves that dep) or re-run `agr sync`.

See [Configuration](configuration.md) for all manifest options and
[Reference — agr.toml Format](reference.md#agrtoml-format) for the full schema.

---

## Keep Instruction Files Aligned Across Tools

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

## `agr` vs `agrx` — Permanent Install vs One-Off Run

agr ships two commands:

**`agr`** — The main CLI for managing resources (skills and ralphs). Install,
remove, sync, list, configure. Changes persist in `agr.toml`, `agr.lock`, and
your tool's skills directories (or `.agents/ralphs/` for ralphs).

**`agrx`** — The ephemeral runner for skills only. Downloads a skill, runs
it with your tool's CLI, and cleans up. Nothing is saved. Think of it as
`npx` for skills. `agrx` does not support ralphs — install them with
`agr add` and run them with a ralph runtime.

```bash
agr add anthropics/skills/pdf         # Permanent: install and track
agrx anthropics/skills/pdf            # Temporary: run once and clean up
```

Use `agr` when you want a skill to stick around. Use `agrx` when you want to
try something quickly or run a one-off task.

See [agrx](agrx.md) for full details. You can also load skills
programmatically with the [Python SDK](sdk.md).

---

## The Full `agr add` Install Flow

When you run `agr add anthropics/skills/pdf`, agr parses the handle, clones
the repo (sparse checkout), finds the `pdf/SKILL.md` directory, copies it into
each configured tool's skills folder, and updates `agr.toml`.

???+ note "Full install flow (8 steps)"
    1. **Parse the handle** — `anthropics` is the owner, `skills` is the repo,
       `pdf` is the skill name
    2. **Load config** — Read `agr.toml` (or create it) to find configured tools
       and sources
    3. **Clone the repo** — Sparse-checkout `github.com/anthropics/skills`
    4. **Find the resource** — Recursively search for a directory named `pdf`
       containing `SKILL.md` (or `RALPH.md` for a ralph)
    5. **Install to each tool** — Copy the skill directory to each configured
       tool's skills folder (e.g., `.claude/skills/pdf/`, `.cursor/skills/pdf/`)
    6. **Write metadata** — Save `.agr.json` in each installed copy with the
       source handle, install details, and content hash
    7. **Update agr.toml** — Add the dependency to the manifest
    8. **Update agr.lock** — Record the resolved commit SHA and content hash
       so future `agr sync` runs are reproducible

    If any tool's install fails, already-installed copies are rolled back
    automatically.

    **For ralphs**, steps 5–6 install the directory once into
    `.agents/ralphs/<name>/` — there is no per-tool fan-out. agr picks the
    ralph path automatically when the source directory contains a
    `RALPH.md` (local) or when a remote handle does not match a skill.

---

## Next Steps

- [Configuration](configuration.md) — Multi-tool setup, custom sources,
  instruction syncing
- [Supported Tools](tools.md) — Detailed info on each tool's behavior
- [Creating Skills](creating.md) — Write and share your own skills
- [Reference](reference.md) — Every command, flag, and config option
- [Troubleshooting](troubleshooting.md) — Fix common errors and edge cases
