---
name: agr-cli
description: >
  Install, share, sync, and create AI agent skills across coding tools (Claude
  Code, Cursor, Codex, OpenCode, Copilot, Pi) using the agr CLI. Use
  whenever the user mentions agr, agr.toml, agr.lock, agrx, or asks to: add a
  skill ("install the pdf skill", "agr add ..."), sync agent resources across
  tools, share skills with their team, scaffold a new SKILL.md, run a skill
  ephemerally (agrx), set up a repo to manage AI agent dependencies, or
  configure tools/sources/instruction-syncing. Also use whenever an agr.toml
  or agr.lock is present in the project and the user is doing
  resource-management work.
---

# agr CLI

agr is the package manager for AI agent skills. It installs, shares, and syncs
SKILL.md folders across Claude Code, Cursor, Codex, OpenCode, GitHub Copilot,
and Pi. This skill helps you operate the `agr` CLI on the user's
behalf — set up new repos, install and sync skills, manage `agr.toml` /
`agr.lock`, and scaffold in-repo skills under `skills/`.

## When to use

Use this skill when the user wants to:

- Install or remove a remote skill (`agr add anthropics/skills/pdf`).
- Sync `agr.toml` after pulling teammates' changes (`agr sync`).
- Upgrade an installed skill past its pinned commit (`agr upgrade`).
- Run a skill once without persisting it (`agrx ...`) or invoke an installed one (`agr run`).
- Scaffold a new skill (`agr init my-skill`) — especially as in-repo skills under `skills/`.
- Set up a repo from scratch to use agr (multi-tool config, instruction syncing, sources).
- Add a local in-repo skill to the project's dependency list.
- Inspect, edit, or troubleshoot `agr.toml` / `agr.lock` / `agr config`.
- Or whenever `agr.toml` is present and the user is doing resource-management work.

Do NOT use this skill for:

- Authoring the *body* of a SKILL.md. This skill scaffolds and registers; for
  writing effective skill instructions, defer to the user or to a dedicated
  authoring skill such as `anthropics/skills/skill-creator`.
- Iterating on an existing skill based on session feedback or a retrospective.
  That's a separate workflow — listen, propose, edit, commit, re-install. If
  the user has a dedicated debrief / improvement skill installed (e.g.
  `skill-debrief`), use it; otherwise just do the workflow directly.

## Prerequisites

Before running anything, verify agr is installed:

```bash
agr --version
```

If missing, the standard install is `uv tool install agr`. **Do not install agr
without checking with the user first** — they may prefer pipx, brew, or a
pinned version in CI.

## Mental model — read first

- A **skill** is a folder containing a `SKILL.md`. agr copies the whole folder
  into each configured AI tool's skills directory (`.claude/skills/`,
  `.cursor/skills/`, `.opencode/skills/`, `.agents/skills/`, etc.).
- A **handle** identifies a remote skill: `user/skill` (assumes a repo named
  `skills`), `user/repo/skill` (any repo), or `./local/path` (on disk).
- `agr.toml` is the **manifest** (hand-edited or written by `agr add`).
  `agr.lock` is the **lockfile** (auto-generated, pins commit SHAs and content
  hashes — never edit by hand).
- **Project-local** vs **global** scope: every command takes `-g` to operate on
  `~/.agr/agr.toml` and global tool dirs.
- `agr sync` only installs *missing* deps. To move past a pinned commit, use
  `agr upgrade`.
- Resource types: **skill** (consumed by AI tools), **ralph** (autonomous
  agent loop), **package** (a folder with its own `agr.toml`, expanded
  transitively). `agr add` auto-detects the type.

For the full conceptual model: [references/handles.md](references/handles.md).

## Workflows

### 1. Set up a new repo for agr

When the user wants to start using agr in a project that has none configured:

1. Run `agr init`. agr auto-detects which AI tools the repo uses
   (`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, `.codex/`, `.opencode/`,
   `.github/copilot-instructions.md`, `.pi/`, `.agents/`) and writes `agr.toml`.
2. Confirm or adjust the detected tools. For multi-tool:
   `agr config set tools claude codex opencode`.
3. If the user maintains a canonical instruction file (e.g. `CLAUDE.md`) and
   wants it mirrored to others (`AGENTS.md`), enable instruction
   syncing: `agr config set sync_instructions true` then
   `agr config set canonical_instructions CLAUDE.md`.
4. Commit `agr.toml`. (`agr.lock` will appear after the first `agr add` or
   `agr sync` — commit it too.)

Full details: [references/setup.md](references/setup.md).

### 2. Install a skill

```bash
agr add anthropics/skills/pdf
```

Notes:

- Multi: `agr add user/skill1 user/skill2` (skills from the same repo are
  batched into one download).
- `--overwrite` / `-o` to replace.
- `-g` for global (available in every project).
- `agr add` auto-creates `agr.toml` if missing — no need to `agr init` first.

For handle formats and private repos: [references/handles.md](references/handles.md)
and [references/installing-skills.md](references/installing-skills.md).

### 3. In-repo skills (the recommended workflow for skills shipping with the codebase)

Place project-specific skills under `skills/` at the repo root (or at the root
of a relevant submodule). This keeps the skill in version control, reviewable
in PRs, and sharable across the team via `agr.toml`.

```bash
agr init my-skill                  # scaffolds my-skill/SKILL.md in CWD
mkdir -p skills && mv my-skill skills/
agr add ./skills/my-skill          # records {path = "./skills/my-skill", type = "skill"} in agr.toml
```

Iterate: edit `skills/my-skill/SKILL.md`, then
`agr add ./skills/my-skill --overwrite` to reinstall into each configured tool.

Teammates pick it up with `agr sync` after pulling. The local `path` dependency
travels with the repo, so contributors don't need network access to use it.

For structuring (scripts/, references/, assets/), iteration patterns, and
testing with `agrx`: [references/in-repo-skills.md](references/in-repo-skills.md).

### 4. Sync after pulling teammates' changes

```bash
agr sync
```

This (1) syncs instruction files, (2) runs directory migrations, (3) installs
any deps missing for any tool, (4) refreshes `agr.lock`.

CI flags:

- `agr sync --frozen` — install exactly what `agr.lock` says; fail if lock is
  missing or doesn't cover all deps. Use in deploy pipelines for byte-identical
  installs.
- `agr sync --locked` — fail if `agr.lock` is stale vs `agr.toml`. Use in PR
  checks to enforce lockfile hygiene.
- `--frozen` and `--locked` are mutually exclusive.

Full lifecycle: [references/syncing.md](references/syncing.md).

### 5. Upgrade past pinned commits

`agr sync` only installs what is missing. To pull the latest upstream code for
a skill that is already installed, use `agr upgrade`:

```bash
agr upgrade                                # everything in scope
agr upgrade pdf                            # short-name match (errors on ambiguity)
agr upgrade anthropics/skills/pdf          # full handle
```

**Gotcha**: upgrading one skill from a multi-skill repo (e.g.
`anthropics/skills/pdf`) does NOT refresh siblings. Run `agr upgrade` with no
args, or name each sibling explicitly, to refresh the whole repo together.

### 6. Run a skill

```bash
agr run pdf                               # invoke installed skill in default tool
agr run pdf -- "summarise report.pdf"     # extra prompt
agr run pdf -i                            # interactive
agr run pdf --tool cursor                 # override tool
agrx anthropics/skills/pdf -p "Extract"   # ephemeral, no install
```

`agr run` requires the skill to be already installed. `agrx` downloads, runs,
and cleans up. Difference and tool-resolution rules:
[references/running-skills.md](references/running-skills.md).

### 7. Configure agr

Keys: `tools`, `default_tool`, `default_owner`, `default_source`,
`sync_instructions`, `canonical_instructions`, `sources`.

```bash
agr config show
agr config set tools claude codex opencode
agr config add tools cursor
agr config remove tools cursor      # ⚠ DELETES that tool's skills directory
```

Private repos / custom Git hosts:

```bash
agr config add sources gitlab --url "https://gitlab.com/{owner}/{repo}.git"
export GITHUB_TOKEN="..."           # auth for private GitHub repos
```

Add `-g` to operate on `~/.agr/agr.toml` instead of the project file.

All keys with defaults: [references/configuration.md](references/configuration.md).

### 8. List and inspect

```bash
agr list           # status of every dep: installed / partial / not synced / invalid
agr list -g        # global skills
cat agr.toml       # the manifest
cat agr.lock       # the lockfile (READ ONLY)
```

`partial (claude, cursor)` means a skill is installed in some tools but not
others — `agr sync` to fan it out to the rest.

## Boundaries

- **Never edit `agr.lock` by hand.** It's regenerated by `agr add`/`agr sync`/
  `agr remove`/`agr upgrade`. If it looks wrong, run `agr sync` (or
  `agr sync --locked` to confirm hygiene).
- **`agr config remove tools <name>` deletes that tool's skills directory.**
  Confirm with the user before running it. The skills can be re-installed by
  re-adding the tool.
- **Don't author the body of a new skill on the user's behalf** unless they
  explicitly asked. This skill scaffolds and registers; SKILL.md content
  authoring is a separate task.
- **Always confirm before `--overwrite`** on a skill the user has been editing
  locally — overwriting will replace their working copy.
- **Don't install agr globally** without checking — the user may have a pinned
  version, alternative install method, or CI constraints.
- **Don't push or `git tag`** as part of these workflows. Commit changes
  locally; let the user push.

## Troubleshooting pointers

- "Skill not found" → check the handle format (2 vs 3 parts), see
  [references/handles.md](references/handles.md).
- "agr.lock out of date" in CI → user added a dep but didn't commit the
  lockfile; run `agr sync` locally and commit.
- `partial` install status → `agr sync` to fan out to all configured tools.
- Auth errors on private repos → check `GITHUB_TOKEN` is exported.
- Type errors after manually editing `agr.toml` → run `agr add` to let agr
  rewrite the entry with the correct `type` field.

Full list: [references/troubleshooting.md](references/troubleshooting.md).

## References

- [setup.md](references/setup.md) — repo bootstrap, multi-tool, instruction syncing
- [handles.md](references/handles.md) — handle formats, resolution, resource types, scopes
- [installing-skills.md](references/installing-skills.md) — `agr add` / `agr remove`, sources, private repos
- [syncing.md](references/syncing.md) — `agr sync` / `agr upgrade`, lockfile, CI patterns
- [in-repo-skills.md](references/in-repo-skills.md) — `skills/` workflow, scaffolding, iterating
- [configuration.md](references/configuration.md) — all `agr config` keys, sources, scopes
- [running-skills.md](references/running-skills.md) — `agr run` vs `agrx`
- [troubleshooting.md](references/troubleshooting.md) — common errors and fixes

For the canonical CLI reference, point the user at
https://computerlovetech.github.io/agr/reference/ or run `agr <command> --help`.

## Related capabilities (separate skills if installed)

- **Greenfield skill authoring** — scaffolding a brand-new SKILL.md from a
  blank slate. Canonical option: `anthropics/skills/skill-creator`.
- **Retrospective-driven skill improvement** — listening to feedback after a
  session and updating an existing skill. If the user has a dedicated
  workflow skill for this, use it; otherwise the workflow is editing the
  source under `skills/<name>/`, committing, and `agr upgrade <name>`.
