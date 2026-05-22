<div align="center">

# agr

**The package manager for AI agents.**

Share AI agent skills across your team like code packages — from any Git repo,
into Claude Code, Cursor, Codex, and more.

[![PyPI](https://img.shields.io/pypi/v/agr?color=blue)](https://pypi.org/project/agr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-site-blue)](https://computerlovetech.github.io/agr/)

</div>

<p align="center">
  <img src="docs/images/demo.svg" alt="agr demo — install skills and list them" width="680">
</p>

---

## Getting started

Install the CLI:

```bash
uv tool install agr
```

Install your first skill:

```bash
agr add anthropics/skills/pdf
```

Handles follow the pattern `owner/repo/skill` — pointing to a directory inside
a GitHub repo. `anthropics/skills/pdf` means the `pdf/` directory inside
[github.com/anthropics/skills](https://github.com/anthropics/skills).

Then invoke it in your AI tool:

| Tool | Invoke with |
|------|-------------|
| Claude Code | `/pdf` |
| Cursor | `/pdf` |
| OpenAI Codex | `$pdf` |
| OpenCode | `pdf` |
| GitHub Copilot | `/pdf` |
| Antigravity | *(via IDE)* |

No setup required — `agr add` auto-creates `agr.toml` and detects which tools
you use.

---

## Built for teams

agr is opinionated: skill directories (`.claude/skills/`, `.cursor/skills/`, …)
are build artifacts — like `.venv/` or `node_modules/`. Add them to `.gitignore`.
Commit `agr.toml` and `agr.lock` instead. `agr sync` rebuilds the environment
from the manifest on every machine.

```toml
tools = ["claude", "cursor"]

dependencies = [
    {handle = "anthropics/skills/pdf", type = "skill"},
    {handle = "anthropics/skills/frontend-design", type = "skill"},
]
```

```bash
agr sync   # Like npm install, but for AI agents
```

New teammate? `agr sync` and they're productive on day one — same skills,
same standards, every tool.

---

## Keep skills up to date

```bash
agr upgrade            # all skills
agr upgrade pdf        # one skill
```

---

## Example skills

```bash
agr add anthropics/skills/pdf              # Read, extract, create PDFs
agr add anthropics/skills/frontend-design  # Production-grade interfaces
agr add anthropics/skills/claude-api       # Build apps with the Claude API
agr add anthropics/skills/skill-creator    # Create, modify, and improve skills
```

---

## All commands

| Command | Description |
|---------|-------------|
| `agr add <handle>` | Install a skill |
| `agr remove <handle>` | Uninstall a skill |
| `agr sync` | Install all from `agr.toml` |
| `agr upgrade [handle...]` | Re-fetch deps at latest version |
| `agr list` | Show installed skills |
| `agrx <handle>` | Run a skill temporarily without installing |

Add `-g` to `add`, `remove`, `sync`, or `list` for global skills (available in
all projects).

---

## Community skills

```bash
agr add dsjacobsen/agent-resources/golang-pro              # Go — @dsjacobsen
agr add maragudk/skills/collaboration                      # Workflow — @maragudk
agr add madsnorgaard/drupal-agent-resources/drupal-expert  # Drupal — @madsnorgaard
```

**Built something?** [Share it here.](https://github.com/computerlovetech/agr/issues)

---

<div align="center">

[Documentation](https://computerlovetech.github.io/agr/) · [MIT License](LICENSE)

</div>
