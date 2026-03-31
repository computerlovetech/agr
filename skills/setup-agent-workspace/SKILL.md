---
name: setup-agent-workspace
description: >
  Set up a persistent workspace/ directory for AI agents in any project. The workspace gives
  agents a place to store artifacts, reports, and notes that persist between chat sessions.
  Use this skill when the user mentions "agent workspace", "workspace setup", wants to set up
  a shared working area for agents, or when another skill needs workspace/ and it doesn't exist yet.
  Also use when the user asks where agents should save their output or how to organize agent artifacts.
---

# Setup Agent Workspace

Create a `workspace/` directory at the project root that serves as a persistent, shared working
area for AI agents across tools (Claude Code, Cursor, Codex, Copilot, etc.).

## Why workspace/ exists

When agents work on a project, they often produce artifacts that are valuable beyond a single
session: audit reports, quality scores, analysis notes, execution plans. Without a convention,
these end up scattered or lost between sessions. `workspace/` solves this by giving agents a
known, consistent location.

## The convention

```
workspace/
├── README.md          # Explains the convention (for humans and agents)
├── docs-audit/        # Example: a skill that audits documentation
│   ├── report.md
│   └── screenshots/
├── exec-plans/        # Example: execution plans for complex work
│   └── migration-v2.md
└── notes/             # General scratchpad for cross-agent notes
    └── architecture-decisions.md
```

**Core rules:**
1. `workspace/` lives at the project root, visible (not a dotdir)
2. Skills define their own subdirectories — no central registry needed
3. `workspace/README.md` explains the convention so any agent can discover it
4. Projects choose whether to commit workspace/ or gitignore it

## Setup steps

### 1. Create the workspace directory and README

Create `workspace/README.md` with the content from the template below.

### 2. Add a pointer in the root instruction file

If the project has a `CLAUDE.md`, `AGENTS.md`, or similar root instruction file, add a single
line pointing to the workspace:

```markdown
## Agent Workspace

Persistent agent artifacts live in `workspace/` — see `workspace/README.md` for the convention.
```

### 3. Handle .gitignore

Ask the user whether workspace/ should be:
- **Committed** — useful when reports and artifacts are part of the project record
- **Gitignored** — useful when artifacts are ephemeral or project-specific

If gitignored, add `workspace/` to `.gitignore`. Either way, note the choice in the README.

### 4. Create the notes/ directory

Create `workspace/notes/` as a general-purpose scratchpad. This is where agents can drop
observations, architecture notes, or anything that doesn't belong to a specific skill.

## workspace/README.md template

Use this exact content:

```markdown
# Agent Workspace

This directory is a persistent working area for AI agents. It stores artifacts, reports,
and notes that are useful across chat sessions.

## Convention

- **Skills own subdirectories.** Each skill creates and manages its own directory
  (e.g., `docs-audit/`, `exec-plans/`). No central registry — skills self-organize.
- **`notes/` is shared.** Any agent can use `notes/` for general observations,
  architecture decisions, or cross-skill context.
- **This directory is portable.** The convention works with any AI tool
  (Claude Code, Cursor, Codex, Copilot, etc.) and any project.

## Current contents

<!-- Skills and agents: update this section when you create a new subdirectory -->

- `notes/` — General scratchpad for cross-agent notes
```

## When to use this skill from another skill

If your skill writes to `workspace/` and the directory doesn't exist, you have two options:

1. **Recommended:** Tell the user to run the setup-agent-workspace skill first
2. **Minimal:** Create just your skill's subdirectory and a minimal `workspace/README.md`

Option 1 is better because it sets up the full convention. Option 2 works when you don't
want to interrupt the user's flow.
