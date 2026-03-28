<div align="center">

# agr

**A package manager for AI agent skills.**

Install, share, and sync skills across Claude Code, Cursor, Codex, OpenCode,
Copilot, and Antigravity — with a single command.

[![PyPI](https://img.shields.io/pypi/v/agr?color=blue)](https://pypi.org/project/agr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-site-blue)](https://kasperjunge.github.io/agent-resources/)

</div>

---

## What are skills?

Skills are reusable instructions that teach AI coding agents how to perform
specific tasks. Each skill is a `SKILL.md` file in a directory, published on
GitHub:

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
each time. Without a package manager, you'd copy these files manually into each
tool's config folder, keep them updated by hand, and hope your teammates have
the same versions. **agr automates all of that.**

---

## Getting Started

Install the CLI:

```bash
uv tool install agr       # recommended
# or: pipx install agr
# or: pip install agr
```

Install your first skill:

```bash
agr add anthropics/skills/frontend-design
```

Then invoke it in your AI tool:

| Tool | Invoke with |
|------|-------------|
| Claude Code | `/frontend-design` |
| Cursor | `/frontend-design` |
| OpenAI Codex | `$frontend-design` |
| OpenCode | `frontend-design` |
| GitHub Copilot | `/frontend-design` |
| Antigravity | *(via IDE)* |

No setup required — `agr add` auto-creates `agr.toml` and detects which tools
you use.

---

## Run a skill without installing

**agrx** downloads a skill, runs it with your tool's CLI, and cleans up. Nothing
is saved to your project:

```bash
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/skill-creator -i   # Interactive: skill + chat
```

---

## Team sync

Dependencies are tracked in `agr.toml` — commit it, and teammates install
everything with one command:

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/pdf", type = "skill"},
]
```

```bash
agr sync   # Like npm install, but for agent skills
```

---

## Create and share

```bash
agr init my-skill                # Scaffold a new skill
# Edit my-skill/SKILL.md with your instructions
agr add ./my-skill               # Test locally
# Push to GitHub, then others can:
agr add your-username/my-skill
```

---

## Python SDK

Use `agr` as a library to load, discover, and cache skills programmatically:

```python
from agr import Skill, list_skills, skill_info

skill = Skill.from_git("anthropics/skills/code-review")
print(skill.prompt)   # SKILL.md contents
print(skill.files)    # Files in the skill directory

for info in list_skills("anthropics/skills"):
    details = skill_info(info.handle)
    print(f"{details.handle}: {details.description}")
```

See the [SDK documentation](https://kasperjunge.github.io/agent-resources/sdk/) for
cache management, error handling, and the full API.

---

## Example skills

**Documents & data:**

```bash
agr add anthropics/skills/pdf              # Read, extract, create PDFs
agr add anthropics/skills/docx             # Generate and edit Word documents
agr add anthropics/skills/xlsx             # Build and manipulate spreadsheets
agr add anthropics/skills/pptx             # Create and work with slide decks
agr add anthropics/skills/doc-coauthoring  # Structured doc co-authoring workflow
```

**Design & frontend:**

```bash
agr add anthropics/skills/frontend-design   # Production-grade interfaces
agr add anthropics/skills/canvas-design     # Visual art in PNG and PDF
agr add anthropics/skills/algorithmic-art   # Algorithmic art with p5.js
agr add anthropics/skills/theme-factory     # Style artifacts with themes
agr add anthropics/skills/brand-guidelines  # Anthropic brand colors and typography
```

**Development:**

```bash
agr add anthropics/skills/claude-api             # Build apps with the Claude API
agr add anthropics/skills/mcp-builder            # Create MCP servers
agr add anthropics/skills/web-artifacts-builder  # Multi-component HTML artifacts
agr add anthropics/skills/webapp-testing         # Test web apps with Playwright
```

**Productivity:**

```bash
agr add anthropics/skills/skill-creator     # Create, modify, and improve skills
agr add anthropics/skills/internal-comms    # Write internal communications
agr add anthropics/skills/slack-gif-creator # Create animated GIFs for Slack
```

Browse the full list in the [Skill Directory](https://kasperjunge.github.io/agent-resources/skills/).

---

## All commands

| Command | Description |
|---------|-------------|
| `agr add <handle>` | Install a skill |
| `agr add <handle> -o` | Update to the latest version |
| `agr remove <handle>` | Uninstall a skill |
| `agr sync` | Install all from `agr.toml` |
| `agr list` | Show installed skills |
| `agr init` | Create `agr.toml` (auto-detects tools) |
| `agr init <name>` | Create a new skill |
| `agr onboard` | Interactive guided setup |
| `agr config <cmd>` | Manage configuration |
| `agrx <handle>` | Run a skill temporarily |

Add `-g` to `add`, `remove`, `sync`, or `list` for global skills (available in
all projects).

---

## Community skills

```bash
# Go — @dsjacobsen
agr add dsjacobsen/agent-resources/golang-pro

# Drupal & DevOps — @madsnorgaard
agr add madsnorgaard/drupal-agent-resources/drupal-expert
agr add madsnorgaard/drupal-agent-resources/drupal-security
agr add madsnorgaard/drupal-agent-resources/drupal-migration
agr add madsnorgaard/drupal-agent-resources/ddev-expert
agr add madsnorgaard/drupal-agent-resources/docker-local

# Workflow — @maragudk, @kasperjunge
agr add maragudk/skills/collaboration
agr add kasperjunge/commit-work
agr add kasperjunge/agent-resources/migrate-to-skills
```

Browse all community skills in the [Skill Directory](https://kasperjunge.github.io/agent-resources/skills/).

**Built something?** [Share it here.](https://github.com/kasperjunge/agent-resources/issues)

---

<div align="center">

[Documentation](https://kasperjunge.github.io/agent-resources/) · [Skill Directory](https://kasperjunge.github.io/agent-resources/skills/) · [Tutorial](https://kasperjunge.github.io/agent-resources/tutorial/) · [Python SDK](https://kasperjunge.github.io/agent-resources/sdk/) · [MIT License](LICENSE)

</div>
