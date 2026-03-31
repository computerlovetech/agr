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
- **This directory is committed to git.** Artifacts are part of the project record.

## Current contents

<!-- Skills and agents: update this section when you create a new subdirectory -->

- `docs-audit/` — Documentation quality audit reports and screenshots
- `notes/` — General scratchpad for cross-agent notes
