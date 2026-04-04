---
title: "Ralph Directory — Browse and Install Autonomous Ralph Loops for Ralph Runtimes"
description: What a ralph is, the RALPH.md format, and how to install autonomous ralph loops with agr. Ralphs package autonomous agent loops that run with ralph runtimes such as ralphify.
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
  - create a ralph
  - write RALPH.md
  - publish ralph to GitHub
  - RALPH.md format
  - RALPH.md frontmatter
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

## The RALPH.md format

The frontmatter is YAML. The body is a markdown prompt template with
placeholders that the runtime substitutes each iteration.

**Frontmatter fields:**

| Field | Required | What it does |
|---|---|---|
| `agent` | Yes | Shell command that launches the agent (e.g. `claude -p --dangerously-skip-permissions`) |
| `commands` | No | List of `{name, run, timeout?}` entries. Each command's stdout/stderr is captured and available as `{{ commands.<name> }}` in the body. |
| `args` | No | List of argument names the user can pass at runtime. Values are substituted into `{{ args.<name> }}`. |

**Minimal example** (adapted from the
[bug-hunter example in ralphify](https://github.com/kasperjunge/ralphify/blob/main/examples/bug-hunter/RALPH.md)):

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

See the [ralphify frontmatter reference](https://github.com/kasperjunge/ralphify/blob/main/src/ralphify/_frontmatter.py)
for the full list of supported fields and the [examples directory](https://github.com/kasperjunge/ralphify/tree/main/examples)
for more complete ralphs.

## Directory layout

A ralph is just a directory with a `RALPH.md` file. Supporting files are
optional:

```text
my-ralph/
├── RALPH.md         # Required — frontmatter + prompt body
├── scripts/         # Optional — helper scripts referenced from commands
│   └── precheck.sh
└── references/      # Optional — reference docs
    └── style-guide.md
```

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

## Publishing a ralph

### 1. Create the ralph directory

```text
my-ralph/
└── RALPH.md
```

Author `RALPH.md` using the [format above](#the-ralphmd-format). Test
locally before publishing:

```bash
agr add ./my-ralph
uvx ralphify run .agents/ralphs/my-ralph --max-iterations 1
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

## Next Steps

- [Core Concepts](concepts.md) — How skills, ralphs, tools, sources, and scopes fit together
- [Configuration](configuration.md) — `agr.toml` settings, including `type = "ralph"`
- [CLI Reference](reference.md) — Every command and flag
- [Skill Directory](skills.md) — Browse skills, the other resource type agr manages
- [ralphify on GitHub](https://github.com/kasperjunge/ralphify) — The reference ralph runtime
