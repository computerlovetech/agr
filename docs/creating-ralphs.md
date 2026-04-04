---
title: "How to Create a Ralph — Write, Test, and Publish RALPH.md Files"
description: Step-by-step guide to creating autonomous agent loops — write a RALPH.md with frontmatter and a prompt template, test locally with agr and ralphify, and publish to GitHub.
keywords:
  - create a ralph
  - write RALPH.md
  - RALPH.md format
  - RALPH.md frontmatter
  - ralph prompt template
  - publish ralph to GitHub
  - test ralph locally
  - agr init ralph
  - autonomous agent loop
  - ralphify
  - ralph runtime
  - ralph commands
  - ralph args
  - ralph examples
---

# How to Create a Ralph

!!! tldr
    Create a directory with a `RALPH.md` file — YAML frontmatter configures
    the agent command, shell commands, and args; the markdown body is the
    prompt template. Test with `agr add ./my-ralph` and
    `uvx ralphify run .agents/ralphs/my-ralph`, then push to GitHub.

This guide walks you through creating, testing, and publishing a ralph.
For background on what ralphs are and how they fit into agr, see the
[Ralph Directory](ralphs.md).

!!! note "Looking to create a skill?"
    This page covers **ralphs** — autonomous agent loops executed by a ralph
    runtime. To create context and instructions consumed by AI tools, see
    [Creating Skills](creating.md).

**Prerequisites:** [agr installed](tutorial.md#step-1-install-agr),
[ralphify](https://github.com/kasperjunge/ralphify) for running ralphs locally

---

## RALPH.md Format

A ralph requires a `RALPH.md` file with YAML frontmatter and a markdown
prompt body.

### Frontmatter fields

| Field | Required | What it does |
|---|---|---|
| `agent` | Yes | Shell command that launches the agent (e.g. `claude -p --dangerously-skip-permissions`) |
| `commands` | No | List of `{name, run, timeout?}` entries. Each command's stdout/stderr is captured and available as `{{ commands.<name> }}` in the body. |
| `args` | No | List of argument names the user can pass at runtime. Values are substituted into `{{ args.<name> }}`. |

See the [ralphify frontmatter reference](https://github.com/kasperjunge/ralphify/blob/main/src/ralphify/_frontmatter.py)
for the full list of supported fields.

### Minimal example

```markdown
---
agent: claude -p --dangerously-skip-permissions
commands:
  - name: tests
    run: uv run pytest -x
  - name: lint
    run: uv run ruff check .
args:
  - focus
---

# Bug Hunter

You are an autonomous bug-hunting agent running in a loop. Each iteration
starts with a fresh context — progress lives in the code and in git.

## Test results

{{ commands.tests }}

## Lint

{{ commands.lint }}

## Task

Find and fix a real bug in this codebase.
{{ args.focus }}
```

Adapted from the [bug-hunter example in ralphify](https://github.com/kasperjunge/ralphify/blob/main/examples/bug-hunter/RALPH.md).
See the [examples directory](https://github.com/kasperjunge/ralphify/tree/main/examples)
for more complete ralphs.

---

## Directory Layout

A ralph is a directory with a `RALPH.md` file. Supporting files are optional:

```text
my-ralph/
├── RALPH.md         # Required — frontmatter + prompt body
├── scripts/         # Optional — helper scripts referenced from commands
│   └── precheck.sh
└── references/      # Optional — reference docs
    └── style-guide.md
```

---

## Test Locally

Install your ralph from a local path:

```bash
agr add ./my-ralph
```

Then run it with [ralphify](https://github.com/kasperjunge/ralphify):

```bash
uvx ralphify run .agents/ralphs/my-ralph --max-iterations 1
```

Iterate on the `RALPH.md` content, then reinstall:

```bash
agr add ./my-ralph --overwrite
```

Repeat until the ralph works well. Once you're happy, bump
`--max-iterations` to let the loop run longer and verify it stays on track
across multiple iterations.

---

## Publish to GitHub

### 1. Create the ralph directory

```text
my-ralph/
└── RALPH.md
```

### 2. Push to GitHub

The recommended layout is one directory per ralph inside a repository — the
same shape as a skills repo. A single repository can mix skills and ralphs;
agr picks the right type per directory.

```text
your-username/agent-resources/
├── bug-hunter/
│   └── RALPH.md
└── code-review/
    └── SKILL.md
```

### 3. Share the install command

Others can install with:

```bash
agr add your-username/agent-resources/bug-hunter
```

agr will find the `RALPH.md`, detect the type automatically, and install it
into `.agents/ralphs/bug-hunter/`.

!!! tip "Community Ralphs"
    A curated community directory for ralphs is coming soon. Until then,
    point users to your repo directly, or open an issue at
    [github.com/computerlovetech/agr](https://github.com/computerlovetech/agr/issues)
    to discuss listing options.

---

## Next Steps

- [Ralph Directory](ralphs.md) — Browse ralphs, learn how to install and run them
- [Creating Skills](creating.md) — Write and publish AI tool skills (the other resource type)
- [Core Concepts](concepts.md) — How skills, ralphs, tools, sources, and scopes fit together
- [CLI Reference](reference.md) — Every command and flag
- [ralphify on GitHub](https://github.com/kasperjunge/ralphify) — The reference ralph runtime
