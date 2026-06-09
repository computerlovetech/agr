<div align="center">

# agr

**The package manager for AI agents.**

For teams who want to manage agent skills like software packages — the way npm,
PyPI, and uv manage code. Install skills from any Git repo into Claude Code,
Cursor, Codex, and more, then share them across your team like real dependencies.

[![PyPI](https://img.shields.io/pypi/v/agr?color=blue)](https://pypi.org/project/agr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-site-blue)](https://computerlovetech.github.io/agr/)

</div>

<p align="center">
  <img src="docs/images/demo.svg" alt="agr demo — install skills and list them" width="680">
</p>

---

## Why agr

agr is for **teams** who want to manage their agent skills as seriously as they
manage their code — the way npm, PyPI, and uv manage software packages.

Skills make AI agents better at your work. But today they're copied around by
hand, drift between machines, and live in tool-specific folders. agr treats them
like real dependencies: declared in one manifest, locked to a version, installed
with one command, and identical for every teammate, on every machine, in every
tool.

That brings the same wins you already get from a package manager for code:

- **Version & pin.** `agr.lock` records the exact version of every skill, so a
  skill that works today keeps working tomorrow — no silent upstream changes
  breaking your agents. Upgrade on purpose, when you choose, with `agr upgrade`.
- **Distribute effortlessly.** Publishing a skill is just pushing to a Git repo;
  installing one is `agr add owner/repo/skill`. No registry to set up, no files
  to email around.
- **One source of truth for the team.** The skills your agents use are part of
  your repo — reviewed in PRs, versioned in Git, and shared like any other
  dependency. Everyone runs the same skills, so your agents behave consistently
  across the whole team.
- **Onboard in one command.** A new teammate clones the repo, runs `agr sync`,
  and their agents are set up exactly like everyone else's — same skills, same
  standards, day one.

## Install

```bash
uv tool install agr
```

---

## What you can do with it

Five things. That's the whole tool.

### 1. Install a skill from a Git repo

```bash
agr add anthropics/skills/pdf
```

Handles are just a path into GitHub: **`owner/repo/skill`**. `anthropics/skills/pdf`
is the `pdf/` directory inside
[github.com/anthropics/skills](https://github.com/anthropics/skills). Any public
repo works — no registry, no publishing step.

`agr add` auto-creates `agr.toml`, detects which AI tools you use, and installs
the skill into each. Then invoke it in your tool:

| Tool | Invoke with |
|------|-------------|
| Claude Code | `/pdf` |
| Cursor | `/pdf` |
| OpenAI Codex | `$pdf` |
| OpenCode | `pdf` |
| GitHub Copilot | `/pdf` |
| Pi | `/pdf` |

### 2. Use your own local skills

Point at a directory on disk instead of a repo:

```bash
agr add ./skills/my-internal-skill
```

Great for skills you're still writing, or ones that never leave your codebase.
They sync into every tool exactly like remote skills.

### 3. Share one skill environment with your team

`.claude/skills/`, `.cursor/skills/`, … are build artifacts — like `.venv/` or
`node_modules/`. Add them to `.gitignore`. Commit **`agr.toml`** and
**`agr.lock`** instead:

```toml
tools = ["claude", "cursor"]

dependencies = [
    {handle = "anthropics/skills/pdf", type = "skill"},
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {path = "./skills/my-internal-skill", type = "skill"},
]
```

A new teammate clones the repo and runs:

```bash
agr sync   # like `npm install`, but for AI agents
```

Now everyone has the same skills, the same standards, in every tool.

### 4. Keep skills up to date

```bash
agr upgrade            # all skills
agr upgrade pdf        # just one
```

Re-fetches skills at their latest upstream version and updates `agr.lock`.

### 5. Try a skill without installing it

```bash
agrx anthropics/skills/pdf
```

Downloads and runs a skill once, then throws it away — nothing added to
`agr.toml`, nothing left behind.

---

## All commands

| Command | What it does |
|---------|--------------|
| `agr add <handle\|path>` | Install a skill and add it to `agr.toml` |
| `agr remove <handle>` | Uninstall a skill |
| `agr sync` | Install everything in `agr.toml` |
| `agr upgrade [handle...]` | Re-fetch skills at their latest version |
| `agr list` | Show installed skills |
| `agrx <handle>` | Run a skill once, without installing |

Add `-g` to `add`, `remove`, `sync`, or `list` to manage **global** skills,
available across all your projects.

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
