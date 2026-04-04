---
title: How to Share AI Agent Resources Across a Team
description: Share AI agent resources with your team using agr.toml as a single source of truth — like package.json for AI agents. Sync skills, prompts, and instructions across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity.
keywords:
  - share AI agent resources across team
  - Agentic Engineering team setup
  - sync AI agents across developers
  - team AI coding tools setup
  - share CLAUDE.md with team
  - sync AGENTS.md across developers
  - share cursor rules across team
  - standardize AI agent prompts team
  - onboard developers AI coding tools
  - agr sync team
  - CI/CD AI agent resources pipeline
  - private AI resources GitHub repo
  - multi-tool AI team setup
  - manage AI prompts in git
  - share custom prompts Claude Code Cursor
  - npm install for AI agents
  - sync coding agent instructions across repos
  - Agentic Engineering
---

# Share AI Agent Resources Across Your Team

!!! tldr
    Commit **both** `agr.toml` (manifest) and `agr.lock` (pinned commits) —
    teammates run `agr sync` to get every resource, reproducibly. Multi-tool
    teams set `tools = ["claude", "cursor", ...]` so one `agr add` installs
    everywhere. CI uses `agr sync --frozen` (install from lockfile exactly)
    or `agr sync --locked` (fail if lockfile is stale). Use `GITHUB_TOKEN`
    for private repos.

**Agentic Engineering** means treating AI agents as first-class members of your
development team. `agr` makes this practical: one manifest, one lockfile, one
sync command, and every developer — and every agent — starts with the same
resources pinned to the same commits.

**Prerequisites:** [agr installed](tutorial.md#step-1-install-agr), a git
repository, and at least one [supported AI tool](tools.md) (Claude Code,
Cursor, Codex, OpenCode, Copilot, or Antigravity)

Set up agr so everyone shares the same agent resources, stays in sync
across Claude Code, Cursor, Codex, and other tools — and gets productive on
day one.

**Key terms:** A **resource** is the unit agr manages — either a **skill**
(a directory with a `SKILL.md` file, consumed by an AI tool) or a **ralph**
(a directory with a `RALPH.md` file, an autonomous loop consumed by a
[ralph runtime](ralphs.md)). A **handle** like `anthropics/skills/pdf`
identifies a resource on GitHub. [`agr.toml`](configuration.md) is your
project's resource manifest; [`agr.lock`](concepts.md#agrlock) pins exact
commit SHAs so installs are reproducible. Together they play the role of
`package.json` + `package-lock.json`. See [Core Concepts](concepts.md) for
details.

---

## Set up your project

### 1. Initialize agr

Run this in your repo root:

```bash
agr init
```

This creates `agr.toml` and auto-detects which tools your team uses from
repo signals (`.claude/`, `.cursor/`, `CLAUDE.md`, etc.).

To target specific tools:

```bash
agr init --tools claude,cursor,codex
```

### 2. Add skills

Install the skills your team needs:

```bash
agr add anthropics/skills/frontend-design
agr add anthropics/skills/pdf
agr add ./skills/internal-review                          # Local skills work too
agr add your-username/agent-resources/bug-hunter          # Ralphs work the same way
```

Each `agr add` updates both `agr.toml` (manifest) and `agr.lock` (pinned
commit SHA + content hash).

### 3. Commit agr.toml and agr.lock

```bash
git add agr.toml agr.lock
git commit -m "Add agr resource dependencies"
```

Commit **both files**. `agr.toml` declares intent; `agr.lock` pins the
exact bytes so every teammate — and CI — gets the same resources. Treat
them like `package.json` + `package-lock.json` or `Cargo.toml` + `Cargo.lock`.

### What to commit

| Commit | Gitignore |
|--------|-----------|
| `agr.toml` (manifest) | `.claude/skills/` |
| `agr.lock` (pinned commits, auto-generated) | `.cursor/skills/` |
| `./skills/` (local skills) | `.agents/skills/` |
| `./ralphs/` (local ralphs, if you keep them in-tree) | `.opencode/skills/` |
| | `.github/skills/` |
| | `.gemini/skills/` |
| | `.agents/ralphs/` |

Add the tool directories to `.gitignore`:

```gitignore
# agr-managed resource directories (recreated by agr sync)
.claude/skills/
.cursor/skills/
.agents/skills/
.opencode/skills/
.github/skills/
.gemini/skills/
.agents/ralphs/
```

You only need to gitignore the tools you've configured — but listing all of
them is harmless and avoids surprises if someone adds a tool later.

??? tip "What about local resources in `./skills/` and `./ralphs/`?"
    Resources referenced by path in `agr.toml` (e.g.,
    `{path = "./skills/my-skill"}` or `{path = "./ralphs/my-loop"}`) live in
    your repo and **should be committed**. They're your team's custom
    resources — `agr sync` installs them from the local path, not from GitHub.

### 4. Teammates install

After cloning the repo, a new teammate runs two commands:

```bash
uv tool install agr   # One-time install
agr sync              # Install every resource at the exact commits in agr.lock
```

Done. Everyone has the same resources, pinned to the same commits, in every
configured tool.

---

## Multi-tool teams

If your team uses different AI coding tools, configure all of them:

```bash
agr config set tools claude cursor codex
```

When anyone runs `agr add` or `agr sync`, skills are installed into every
configured tool's skills directory simultaneously. A skill added by someone
using Claude Code is also available to the teammate using Cursor.

See [Supported Tools](tools.md) for details on each tool.

### Keep instruction files in sync

When using multiple tools, you probably want one source of truth for your
project-level instructions (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`). Enable
instruction syncing:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

Now `agr sync` copies `CLAUDE.md` content to `AGENTS.md` and `GEMINI.md`
as needed by your configured tools. Maintain one file, all tools stay aligned.

See [Configuration — Instruction Syncing](configuration.md#instruction-syncing) for details.

---

## Private skills

Teams often keep internal skills in private GitHub repositories. agr supports
this through environment variables — no configuration changes needed.

### Developer setup

Each developer exports a GitHub token:

```bash
export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
```

Or, if you use the [GitHub CLI](https://cli.github.com/):

```bash
export GH_TOKEN="$(gh auth token)"
```

The token needs **Contents: Read-only** access on the repositories containing
your skills. Fine-grained tokens scoped to specific repos are recommended.

Add the export to your shell profile (`~/.zshrc`, `~/.bashrc`) for permanent
access.

### CI/CD setup

For automated environments, pass the token as a secret:

```yaml
- name: Sync skills
  run: agr sync -q
  env:
    GITHUB_TOKEN: ${{ secrets.SKILL_TOKEN }}
```

Create a fine-grained token with **Contents: Read-only** on your skill
repositories and add it as a repository secret.

See [Configuration — Private Repositories](configuration.md#private-repositories) for full details.

---

## CI/CD integration

Add `agr sync` to your CI pipeline so resources are available in automated
environments. For CI, prefer the lockfile-aware modes — they give you the
same guarantees `npm ci` or `cargo build --locked` do.

| Mode | What it does | When to use |
|---|---|---|
| `agr sync` | Install missing deps, re-resolve, refresh `agr.lock` | Local dev |
| `agr sync --locked` | Fail if `agr.lock` is stale vs `agr.toml`, then install from the lockfile | CI on PRs — catches contributors who forgot to commit the lockfile |
| `agr sync --frozen` | Install exactly what `agr.lock` specifies. Fail if `agr.lock` is missing or a dep is missing from it. Never re-resolve. | CI on deploys — byte-identical installs |

### GitHub Actions

A complete workflow that syncs resources before your CI jobs run:

```yaml
name: Sync agent resources
on: [push, pull_request]

jobs:
  sync-resources:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v6 # (1)!

      - name: Install agr
        run: uv tool install agr

      - name: Sync resources (frozen — install exactly what agr.lock specifies)
        run: agr sync --frozen -q # (2)!
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} # (3)!
```

1. Sets up `uv` — see [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) for options
2. `--frozen` installs exactly what `agr.lock` specifies, byte-for-byte. `-q` suppresses non-error output, keeping CI logs clean. Use `--locked` instead if you also want CI to fail when a contributor forgot to commit an updated lockfile.
3. Only needed for private repos. For public resources, remove this line.

??? note "Run as a step in an existing workflow"
    If you already have a CI workflow, add just the install and sync steps:

    ```yaml
    - name: Install agr
      run: uv tool install agr

    - name: Sync resources
      run: agr sync --frozen -q
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    ```

### Other CI systems

agr is a standard Python CLI. Install it in any CI environment that has Python 3.10+ and Git:

```bash
uv tool install agr
agr sync --frozen -q
```

Set `GITHUB_TOKEN` in your CI environment variables for private repos.

---

## Adding, updating, and removing resources

### Add a new resource for the team

```bash
agr add anthropics/skills/pdf
git add agr.toml agr.lock
git commit -m "Add pdf skill"
```

Teammates pick it up on their next `agr sync`. The same flow works for
ralphs — `agr add` sets `type = "ralph"` automatically when the remote
resource contains a `RALPH.md`.

### Update a resource to the latest version

```bash
agr add anthropics/skills/pdf --overwrite
git add agr.toml agr.lock
git commit -m "Bump pdf skill"
```

`--overwrite` re-resolves the dependency against the current remote HEAD,
replaces the installed copy, and updates `agr.lock` with the new commit SHA.
Commit both files so teammates pick up the new pin.

### Remove a resource

```bash
agr remove anthropics/skills/pdf
git add agr.toml agr.lock
git commit -m "Remove pdf skill"
```

---

## Recommended workflow

A typical team workflow looks like this:

1. **One person** sets up `agr.toml` with the team's resources, runs `agr sync`, and commits both `agr.toml` and `agr.lock`
2. **Everyone** runs `agr sync` after pulling to stay up to date with the pinned commits
3. **Anyone** can add, update, or remove resources — changes go through normal code review, always committing `agr.toml` and `agr.lock` together
4. **CI** runs `agr sync --frozen` (deploy) or `agr sync --locked` (PR checks) so automated environments get the exact same bytes as developers

`agr.toml` is the single source of truth for *what* your team depends on;
`agr.lock` is the single source of truth for *which exact commits* those
dependencies resolve to. Treat them like any other project dependency files.

---

## Next steps

- [Configuration](configuration.md) — Custom sources, global installs, full
  `agr.toml` reference
- [Creating Skills](creating.md) — Build internal skills for your team
- [Supported Tools](tools.md) — How agr works with each AI coding tool
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
