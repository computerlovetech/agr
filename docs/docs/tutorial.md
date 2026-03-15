---
title: Tutorial
---

# Tutorial: From Zero to Sharing Skills

This tutorial walks you through a complete workflow — installing agr, adding
skills to a project, syncing with a team, and creating your own skill. By the
end you'll understand how all the pieces fit together.

**Time:** ~10 minutes
**Prerequisites:** Python 3.10+, git, a Python package installer ([uv](https://docs.astral.sh/uv/), [pipx](https://pipx.pypa.io/), or pip), and at least one supported AI coding tool (Claude Code, Cursor, Codex, OpenCode, Copilot, or Antigravity)

---

## Step 1: Install agr

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

Verify it works:

```bash
agr --version
```

```
agr 0.7.10
```

This installs two commands:

- **`agr`** — the main CLI for installing, managing, and syncing skills
- **`agrx`** — an ephemeral runner that downloads a skill, runs it once, and cleans up

---

## Step 2: Set up a project

Navigate to a project where you use an AI coding tool:

```bash
cd your-project
```

You can optionally run `agr init` to create `agr.toml` up front:

```bash
agr init
```

This creates an `agr.toml` file and auto-detects which tools you use based on
repo signals (`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.):

```
Created: agr.toml
Tools: claude
Next: agr add <handle> or agr onboard
```

??? tip "Skip this step"
    `agr init` is optional. If you jump straight to `agr add` in the next step,
    agr auto-creates `agr.toml` and detects your tools automatically.

??? tip "Prefer a guided setup?"
    Run `agr onboard` instead. It walks you through tool selection, skill
    discovery, and configuration interactively.

Your `agr.toml` starts mostly empty:

```toml
dependencies = []
```

---

## Step 3: Add your first skill

Install a skill from GitHub:

```bash
agr add anthropics/skills/frontend-design
```

```
Added: anthropics/skills/frontend-design
  Installed to claude: .claude/skills/frontend-design
```

What just happened:

1. agr cloned the `anthropics/skills` repo (via sparse checkout — fast, even for large repos)
2. It found the `frontend-design` directory containing a `SKILL.md` file
3. It copied that skill into your tool's skills folder (e.g., `.claude/skills/frontend-design/`)
4. It added the dependency to `agr.toml`

Check your `agr.toml` — it now tracks the skill:

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
]
```

List what's installed:

```bash
agr list
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┓
┃ Skill                             ┃ Type   ┃ Status    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━┩
│ anthropics/skills/frontend-design │ remote │ installed │
└───────────────────────────────────┴────────┴───────────┘
```

### Use the skill

Open your AI coding tool and invoke the skill. How you invoke it depends on
which tool you use:

| Tool | Invoke with |
|------|-------------|
| Claude Code | Type `/frontend-design` in the chat |
| Cursor | Type `/frontend-design` in the chat |
| OpenAI Codex | Type `$frontend-design` in the chat |
| OpenCode | Type `frontend-design` in the chat |
| GitHub Copilot | Type `/frontend-design` in the chat |

In most tools, skills also load as context automatically — the agent may apply
them without you explicitly invoking them. See [Supported Tools](tools.md) for
details on each tool's behavior.

---

## Step 4: Add more skills

You can install multiple skills at once:

```bash
agr add anthropics/skills/pdf anthropics/skills/skill-creator
```

Or install from a specific user's repo using the three-part handle format:

```bash
agr add madsnorgaard/drupal-agent-resources/drupal-expert
```

### Handle format cheat sheet

| Handle | What it resolves to |
|--------|-------------------|
| `user/skill` | `github.com/user/skills` repo, `skill` directory |
| `user/repo/skill` | `github.com/user/repo` repo, `skill` directory |
| `./path/to/skill` | Local directory on disk |

---

## Step 5: Team sync

Your `agr.toml` is meant to be committed to version control. When a teammate
clones the repo, they run:

```bash
agr sync
```

This installs every skill listed in `agr.toml` that isn't already present. It's
like `npm install` for agent skills:

```
Up to date: anthropics/skills/frontend-design
Up to date: anthropics/skills/pdf
Up to date: anthropics/skills/skill-creator

Summary: 3 up to date
```

For a full walkthrough on multi-tool teams, CI/CD, and private repos, see [Teams](teams.md).

---

## Step 6: Try a skill without installing

Sometimes you want to test a skill before committing to it. That's what `agrx`
is for:

```bash
agrx anthropics/skills/pdf -p "Summarize the key findings in report.pdf"
```

This downloads the skill to a temporary location, runs it with your tool's CLI,
and cleans up afterwards. Nothing is added to `agr.toml`.

Use `-i` to start an interactive session after the skill runs:

```bash
agrx anthropics/skills/skill-creator -i
```

---

## Step 7: Create your own skill

Scaffold a new skill:

```bash
agr init my-skill
```

```
Created skill scaffold: my-skill
  Edit my-skill/SKILL.md to customize your skill
```

This creates `my-skill/SKILL.md` with a starter template:

```markdown
---
name: my-skill
description: What this skill does.
---

# My Skill

Instructions for the agent.
```

Edit the file to describe what you want the agent to do. The frontmatter
(`name`, `description`) is required. The body after the frontmatter is the
actual instruction content that gets loaded by your AI tool.

### Skill structure

A minimal skill is just a `SKILL.md` file in a directory. But skills can include
supporting files too:

```
my-skill/
├── SKILL.md          # Required — skill instructions
├── scripts/          # Optional — helper scripts the skill references
│   └── lint.sh
└── templates/        # Optional — templates or examples
    └── component.tsx
```

### Test it locally

Install your skill from the local path:

```bash
agr add ./my-skill
```

Now open your AI tool and verify the skill works as expected. Iterate on the
`SKILL.md` content until you're happy, then reinstall with `--overwrite`:

```bash
agr add ./my-skill -o
```

---

## Step 8: Share your skill

Push your skill to GitHub. The recommended structure is a repo named `skills`
under your GitHub username:

```
your-username/skills/
├── my-skill/
│   └── SKILL.md
├── another-skill/
│   └── SKILL.md
└── ...
```

Once pushed, anyone can install it:

```bash
agr add your-username/my-skill
```

If your skills live in a differently named repo, users reference it with the
three-part format:

```bash
agr add your-username/my-repo/my-skill
```

---

## Step 9: Remove a skill

```bash
agr remove anthropics/skills/frontend-design
```

```
Removed: anthropics/skills/frontend-design
```

This deletes the skill from your tool's skills folder and removes the entry from
`agr.toml`.

---

## Step 10: Global skills

Some skills are useful across every project — not just one. Install them
globally:

```bash
agr add -g anthropics/skills/skill-creator
```

```
Added: anthropics/skills/skill-creator
  Installed to claude: ~/.claude/skills/skill-creator
```

Global skills are tracked in `~/.agr/agr.toml` and installed into your tool's
global skills directory. Sync them with:

```bash
agr sync -g
```

List global skills:

```bash
agr list -g
```

---

## What's next

- [Core Concepts](concepts.md) — understand handles, tools, sources, and how agr works under the hood
- [Creating Skills](creating.md) — detailed guide on writing effective skills, including frontmatter options and supporting files
- [Configuration](configuration.md) — multi-tool setup, custom sources, private repos, and instruction syncing
- [agrx](agrx.md) — full reference for the ephemeral skill runner
- [Python SDK](sdk.md) — use agr as a library in your own tools
- [CLI Reference](reference.md) — every command, flag, and option
