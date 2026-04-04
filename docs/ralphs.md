---
title: "Ralph Directory — Browse and Install Autonomous Ralph Loops for Ralph Runtimes"
description: What a ralph is and how to install and run autonomous agent loops with agr. Ralphs package autonomous agent loops that run with ralph runtimes such as ralphify.
keywords:
  - agr ralph
  - RALPH.md
  - ralph directory
  - ralphify
  - autonomous agent loop
  - ralph runtime
  - agr install ralph
  - AI agent loop
  - .agents/ralphs
---

# Ralph Directory

!!! tldr
    A **ralph** is a directory containing a `RALPH.md` file that defines an
    autonomous agent loop — an agent command, shell commands whose output
    fills the prompt, and args supplied at runtime. agr packages and
    distributes ralphs; a ralph runtime such as
    [ralphify](https://github.com/kasperjunge/ralphify) executes them.
    Install with `agr add user/repo/ralph-name` — it lands in
    `.agents/ralphs/<name>/`.

## What is a ralph?

A **ralph** is a directory with a `RALPH.md` file. The YAML frontmatter
configures an autonomous loop — which agent binary to invoke, which shell
commands to run each iteration, and which arguments the user can pass in. The
markdown body is the prompt template, with placeholders like
`{{ commands.tests }}` and `{{ args.focus }}` that the runtime fills in on
every iteration.

Unlike a [skill](skills.md), which is context an AI tool loads when invoked,
a ralph is an **autonomous loop specification** — it runs on its own. agr
packages ralphs and installs them into your project; a separate ralph runtime
is what actually executes them. The reference runtime is
[ralphify](https://github.com/kasperjunge/ralphify), but any runtime that
understands the `RALPH.md` format will work.

## Ralph vs skill at a glance

| Aspect | Skill | Ralph |
|---|---|---|
| Marker file | `SKILL.md` | `RALPH.md` |
| Scope on disk | Per tool (`.claude/skills/`, `.cursor/skills/`, …) | Per project (`.agents/ralphs/`) |
| Consumed by | AI tool (Claude Code, Cursor, …) | Ralph runtime (e.g. ralphify) |
| Shape | Context and instructions | Autonomous loop specification |
| `agr.toml` `type` | `"skill"` | `"ralph"` |
| `agr -g` (global) | Yes | No — ralphs are project-only |
| [`agrx`](agrx.md) support | Yes | No — install locally, then run with the runtime |

## Installing a ralph

The same `agr` commands that work for skills work for ralphs — no new flags.
agr detects the dependency type automatically:

- **Local path** — agr looks inside the directory and picks `ralph` if it
  finds a `RALPH.md`, or `skill` if it finds a `SKILL.md`.
- **Remote handle** — agr tries to find the dependency as a skill first and
  falls back to a ralph if no skill directory matches. You don't need to
  tell agr which one it is.

```bash
agr add user/repo/my-ralph       # Remote — auto-detected as ralph
agr add ./path/to/my-ralph       # Local  — detected from RALPH.md
agr list                         # Lists both skills and ralphs
agr remove my-ralph              # Works for either type
agr sync                         # Installs all dependencies from agr.toml
```

After install, the ralph lives at `.agents/ralphs/<name>/` in your project —
one copy, no per-tool fan-out. The dependency is tracked in `agr.toml` with
`type = "ralph"`:

```toml
dependencies = [
    {handle = "user/repo/my-ralph", type = "ralph"},
    {path = "./local/another-ralph", type = "ralph"},
]
```

!!! note "No global installs for ralphs"
    Ralphs are project-scoped. `agr add -g` and `agr sync -g` skip ralph
    dependencies because a ralph's commands (like `uv run pytest`) only
    make sense inside a specific project.

## Running a ralph

agr stops at packaging. To actually run a ralph, use a ralph runtime. The
reference runtime is [ralphify](https://github.com/kasperjunge/ralphify):

```bash
uvx ralphify run .agents/ralphs/my-ralph --max-iterations 5 --focus "fix parser"
```

Any other runtime that implements the `RALPH.md` format works too. See the
[ralphify docs](https://github.com/kasperjunge/ralphify) for full usage,
flags, and behavior.

## Creating a ralph

See [Creating Ralphs](creating-ralphs.md) for the full guide — the
`RALPH.md` format, directory layout, testing workflow, and publishing to
GitHub.

## Next Steps

- [Creating Ralphs](creating-ralphs.md) — Write, test, and publish your own ralphs
- [Core Concepts](concepts.md) — How skills, ralphs, tools, sources, and scopes fit together
- [Configuration](configuration.md) — `agr.toml` settings, including `type = "ralph"`
- [CLI Reference](reference.md) — Every command and flag
- [Skill Directory](skills.md) — Browse skills, the other resource type agr manages
- [ralphify on GitHub](https://github.com/kasperjunge/ralphify) — The reference ralph runtime
