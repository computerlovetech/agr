---
title: "agr — The Package Manager for AI Agents"
description: The package manager for AI agents. Install, share, and sync agent resources across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity — built for teams practicing Agentic Engineering.
keywords:
  - agr
  - package manager for AI agents
  - Agentic Engineering
  - AI agent team collaboration
  - install AI agent resources
  - Claude Code skills
  - Cursor skills
  - Codex skills
  - OpenCode skills
  - GitHub Copilot skills
  - Antigravity skills
  - AI agent resource manager
  - share AI resources across team
  - reusable AI coding instructions
  - npm for AI agents
  - manage Claude Code prompts
  - install Cursor custom instructions
  - AI coding assistant marketplace
  - SKILL.md format
  - agr add install skill
  - agr sync team resources
  - team AI agent setup
  - share custom prompts Claude Code Cursor
  - AI agent management tool
  - Agentic Engineering tools
---

# agr — The Package Manager for AI Agents

**agr** is short for **agent resources** — the package manager your team uses
to manage its coding-agent resources. Built for teams practicing **Agentic
Engineering**. Install, share, and sync resources across
[Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity](tools.md)
with a single command.

When AI agents are first-class members of your development team, you need a way
to keep everyone — humans and agents — on the same page. `agr` gives your team
a single source of truth: commit [`agr.toml`](configuration.md) (the manifest)
and [`agr.lock`](concepts.md#agrlock) (the pinned commits), run `agr sync`,
and every developer has the same resources from day one — reproducibly, down
to the commit SHA.

## The two resource types agr manages

| Resource | Marker file | What it is | Consumed by | Installed to |
|---|---|---|---|---|
| **[Skill](skills.md)** | `SKILL.md` | Context and instructions an AI tool loads when invoked | AI tool (Claude Code, Cursor, Codex, …) | Each configured tool's skills dir (e.g. `.claude/skills/`) |
| **[Ralph](ralphs.md)** | `RALPH.md` | An autonomous agent loop specification — agent command, shell commands whose output fills the prompt, args supplied at runtime | A ralph runtime such as [ralphify](https://github.com/kasperjunge/ralphify) | `.agents/ralphs/<name>/` (once per project) |

The same `agr add`, `agr sync`, `agr remove`, and `agr list` commands work for
both. agr detects the type automatically from the marker file — you don't
pass a `--type` flag.

## Install

```bash
uv tool install agr
```

## Add your first skill

```bash
agr add anthropics/skills/frontend-design
```

That's it. The skill is now installed in your tool's skills folder ([handle format](concepts.md#handles)). Invoke it:

| Tool | Invoke with |
|------|-------------|
| Claude Code | `/frontend-design` |
| Cursor | `/frontend-design` |
| OpenAI Codex | `$frontend-design` |
| OpenCode | `frontend-design` |
| GitHub Copilot | `/frontend-design` |
| Antigravity | *(via IDE)* |

!!! tip "No setup required"
    `agr add` auto-creates `agr.toml` if it doesn't exist and [detects which
    tools](tools.md#detection-signals) you use. You don't need to run `agr init` first.

## Run a skill without installing

```bash
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
```

[`agrx`](agrx.md) downloads the skill, runs it with your tool, and cleans up. Nothing is
saved to your project.

## Built for teams

Your team's resources live in two committed files, similar to `package.json`
and `package-lock.json`:

- **[`agr.toml`](configuration.md)** — the manifest. What resources your team depends on.
- **[`agr.lock`](concepts.md#agrlock)** — auto-generated. Pins the exact git commit SHA and content hash for every resolved dependency so `agr sync` produces byte-identical installs across machines.

```toml
# agr.toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/skill-creator", type = "skill"},
    {handle = "your-username/agent-resources/bug-hunter", type = "ralph"},
]
```

Teammates install everything with one command — see [Teams](teams.md) for CI/CD setup:

```bash
agr sync              # Install everything, refreshing the lockfile
agr sync --frozen     # CI: install exactly what agr.lock specifies
agr sync --locked     # CI: fail if agr.lock is stale vs agr.toml
```

New teammate? `agr sync` and they're productive on day one — same skills,
same ralphs, same pinned commits, across every AI tool your team uses.

## Create your own

```bash
agr init my-skill                # Scaffold a new skill
# Edit my-skill/SKILL.md with your instructions
agr add ./my-skill               # Test locally
# Push to GitHub, then others can:
agr add your-username/my-skill
```

See [Creating Skills](creating.md) for the full guide.

## Commands

| Command | What it does |
|---------|-------------|
| [`agr add <handle>`](reference.md#agr-add) | Install a resource (skill or ralph) |
| [`agr add <handle> -o`](reference.md#agr-add) | Update a resource to the latest version |
| [`agr remove <handle>`](reference.md#agr-remove) | Uninstall a resource |
| [`agr sync`](reference.md#agr-sync) | Install all dependencies from `agr.toml`, refresh `agr.lock` |
| [`agr sync --frozen`](reference.md#agr-sync) | Install exactly what `agr.lock` specifies (CI) |
| [`agr sync --locked`](reference.md#agr-sync) | Fail if `agr.lock` is stale vs `agr.toml` (CI) |
| [`agr list`](reference.md#agr-list) | Show resources and installation status |
| [`agr init`](reference.md#agr-init) | Create `agr.toml` (auto-detects tools) |
| [`agr init <name>`](reference.md#agr-init) | Create a skill scaffold |
| [`agr config <cmd>`](reference.md#agr-config) | Manage tools, sources, and settings |
| [`agrx <handle>`](reference.md#agrx) | Run a skill temporarily |

## Example skills

**Documents & data** — read, create, and transform office files:

```bash
agr add anthropics/skills/pdf              # Extract tables, summarize, create PDFs
agr add anthropics/skills/docx             # Generate and edit Word documents
agr add anthropics/skills/xlsx             # Build and manipulate spreadsheets
agr add anthropics/skills/pptx             # Create and work with slide decks
agr add anthropics/skills/doc-coauthoring  # Structured doc co-authoring workflow
```

**Design & frontend** — build UIs and visual assets:

```bash
agr add anthropics/skills/frontend-design   # Production-grade interfaces
agr add anthropics/skills/canvas-design     # Visual art in PNG and PDF
agr add anthropics/skills/algorithmic-art   # Algorithmic art with p5.js
agr add anthropics/skills/theme-factory     # Style artifacts with themes
agr add anthropics/skills/brand-guidelines  # Anthropic brand colors and typography
```

**Development** — build integrations and test apps:

```bash
agr add anthropics/skills/claude-api             # Build apps with the Claude API
agr add anthropics/skills/mcp-builder            # Create MCP servers
agr add anthropics/skills/web-artifacts-builder  # Multi-component HTML artifacts
agr add anthropics/skills/webapp-testing         # Test web apps with Playwright
```

**Productivity** — create skills and content:

```bash
agr add anthropics/skills/skill-creator     # Create, modify, and improve skills
agr add anthropics/skills/internal-comms    # Write internal communications
agr add anthropics/skills/slack-gif-creator # Create animated GIFs for Slack
```

**Community skills** — built and shared by the community:

```bash
agr add dsjacobsen/agent-resources/golang-pro             # Go — @dsjacobsen
agr add madsnorgaard/drupal-agent-resources/drupal-expert  # Drupal — @madsnorgaard
agr add maragudk/skills/collaboration                      # Workflow — @maragudk
agr add vercel-labs/agent-browser/agent-browser                          # Browser agent — @vercel-labs
```

Browse the full list at the [Skill Directory](skills.md) or on
[GitHub](https://github.com/anthropics/skills).
**Built something?** [Share it here.](https://github.com/computerlovetech/agr/issues)

## Next steps

| I want to... | Go to |
|--------------|-------|
| Get started from scratch | [Tutorial](tutorial.md) — install agr, add skills, sync a team, and create your own |
| Understand how it works | [Core Concepts](concepts.md) — handles, tools, sources, scopes, and the install flow |
| Try a skill without installing | [agrx](agrx.md) — download, run, and clean up in one command |
| Set this up for my team | [Teams](teams.md) — team sync, CI/CD, private repos |
| See what's available | [Skill Directory](skills.md) — official and community skills |
| Install an autonomous loop | [Ralph Directory](ralphs.md) — `RALPH.md` format and how to install ralphs |
| Use a specific AI tool | [Supported Tools](tools.md) — Claude Code, Cursor, Codex, OpenCode, Copilot, Antigravity |
| Build my own skill | [Creating Skills](creating.md) — write, test, and publish skills |
| Use agr in Python code | [Python SDK](sdk.md) — load, discover, and cache skills programmatically |
| Look up a command | [CLI Reference](reference.md) — every command, flag, and option |
| Fix a problem | [Troubleshooting](troubleshooting.md) — common errors and solutions |
| Feed these docs to an LLM | [llms.txt](llms.txt) — summary for AI tools · [llms-full.txt](llms-full.txt) — complete docs in one file |
