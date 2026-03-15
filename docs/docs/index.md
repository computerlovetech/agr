---
title: Home
hide:
  - navigation
  - toc
---

# AGR — Skills for AI Agents

A package manager for AI agent skills. Install, share, and run skills across
Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity — with a single
command.

## What are skills?

Skills are reusable instructions that teach AI coding agents how to perform
specific tasks — reviewing code, generating components, preparing releases, or
anything else you'd normally explain in a prompt. Each skill is a `SKILL.md`
file in a directory, published on GitHub.

Here's what one looks like:

```markdown
---
name: code-reviewer
description: Reviews code for bugs, security issues, and best practices.
---

# Code Reviewer

When reviewing code changes, follow these steps:

1. Read every changed file completely before commenting
2. Check for bugs: null references, off-by-one errors, race conditions
3. Check for security issues: injection, auth bypass, data exposure
4. Verify error handling: are errors caught, logged, and surfaced?

Format each finding as:
- **File and line:** `src/auth.py:42`
- **Severity:** bug / security / style
- **Fix:** concrete code or approach to resolve it
```

Install it, and your AI agent gains a new capability — no prompt engineering
each time.

### Why a package manager?

Without agr, managing skills means:

- **Manual copying** — download files from GitHub, figure out which folder each
  tool expects, copy them in
- **No updates** — when a skill improves, you repeat the process by hand
- **Team drift** — teammates have different skills, different versions, no
  single source of truth
- **Multi-tool pain** — using Claude Code *and* Cursor? Copy everything twice,
  into different directories

With agr:

```bash
agr add anthropics/skills/pdf          # Install from GitHub — one command
agr add anthropics/skills/pdf -o       # Update to the latest version
agr sync                               # Teammates get everything from agr.toml
agr config set tools claude cursor     # Multi-tool — skills install everywhere
```

## Install

=== "uv (recommended)"

    ```bash
    uv tool install agr
    ```

=== "pipx"

    ```bash
    pipx install agr
    ```

=== "pip"

    ```bash
    pip install agr
    ```

## Add your first skill

```bash
agr add anthropics/skills/frontend-design
```

That's it. The skill is now installed in your tool's skills folder. Invoke it:

| Tool | Invoke with |
|------|-------------|
| Claude Code | `/frontend-design` |
| Cursor | `/frontend-design` |
| OpenAI Codex | `$frontend-design` |
| OpenCode | `frontend-design` |
| GitHub Copilot | `/frontend-design` |

!!! tip "No setup required"
    `agr add` auto-creates `agr.toml` if it doesn't exist and detects which
    tools you use. You don't need to run `agr init` first.

## Run a skill without installing

```bash
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
```

`agrx` downloads the skill, runs it with your tool, and cleans up. Nothing is
saved to your project.

## Sync skills across a team

Dependencies are tracked in `agr.toml`:

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/skill-creator", type = "skill"},
]
```

Teammates install everything with:

```bash
agr sync
```

## Commands

| Command | What it does |
|---------|-------------|
| `agr add <handle>` | Install a skill |
| `agr add <handle> -o` | Update a skill to the latest version |
| `agr remove <handle>` | Uninstall a skill |
| `agr sync` | Install all dependencies from `agr.toml` |
| `agr list` | Show skills and installation status |
| `agr init` | Create `agr.toml` (auto-detects tools) |
| `agr init <name>` | Create a skill scaffold |
| `agr onboard` | Interactive guided setup |
| `agr config <cmd>` | Manage tools, sources, and settings |
| `agrx <handle>` | Run a skill temporarily |

## Example skills

**Documents & data** — read, create, and transform office files:

```bash
agr add anthropics/skills/pdf       # Extract tables, summarize, create PDFs
agr add anthropics/skills/docx      # Generate and edit Word documents
agr add anthropics/skills/xlsx      # Build and manipulate spreadsheets
```

**Design & frontend** — build UIs and visual assets:

```bash
agr add anthropics/skills/frontend-design   # Production-grade interfaces
agr add anthropics/skills/canvas-design     # Visual art in PNG and PDF
```

**Development** — build integrations and test apps:

```bash
agr add anthropics/skills/claude-api        # Build apps with the Claude API
agr add anthropics/skills/mcp-builder       # Create MCP servers
agr add anthropics/skills/webapp-testing    # Test web apps with Playwright
```

Browse the full list at the [Skill Directory](skills.md) or on
[GitHub](https://github.com/anthropics/skills).

## Next steps

| I want to... | Go to |
|--------------|-------|
| Get started from scratch | [Tutorial](tutorial.md) — install agr, add skills, sync a team, and create your own |
| Understand how it works | [Core Concepts](concepts.md) — handles, tools, sources, scopes, and the install flow |
| Set this up for my team | [Teams](teams.md) — team sync, CI/CD, private repos |
| See what's available | [Skill Directory](skills.md) — official and community skills |
| Use a specific AI tool | [Supported Tools](tools.md) — Claude Code, Cursor, Codex, OpenCode, Copilot, Antigravity |
| Build my own skill | [Creating Skills](creating.md) — write, test, and publish skills |
| Look up a command | [CLI Reference](reference.md) — every command, flag, and option |
| Fix a problem | [Troubleshooting](troubleshooting.md) — common errors and solutions |
