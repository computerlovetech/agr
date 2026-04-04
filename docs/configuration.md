---
title: "Configure agr.toml — Multi-Tool Setup, Sources, and Instruction Syncing"
description: Configure agr.toml for multi-tool setup across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity — custom Git sources, instruction syncing, and global installs.
keywords:
  - agr.toml configuration
  - agr config command
  - custom git sources
  - private repository skills
  - global skill install
  - instruction syncing
  - multi-tool AI setup
  - agr config set tools
  - Claude Code agr config
  - Cursor agr setup
  - Codex agr config
  - OpenCode agr setup
  - GitHub Copilot agr config
  - Antigravity agr setup
---

# Configure agr.toml — Tools, Sources, and Syncing

!!! tldr
    `agr.toml` is your skill manifest. Key settings: **tools** (which AI tools
    to sync to), **sources** (where to fetch skills from), **sync_instructions**
    (keep `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` aligned). Use `agr config` to
    manage everything from the CLI. Add `-g` for global config at `~/.agr/agr.toml`.

**Prerequisites:** [agr installed](tutorial.md#step-1-install-agr) and an
`agr.toml` file (created by [`agr init`](reference.md#agr-init) or
[`agr add`](reference.md#agr-add))

agr uses `agr.toml` for project-level configuration and `~/.agr/agr.toml` for
global configuration. For an overview of how config fits into agr's architecture,
see [Core Concepts](concepts.md).

**Key terms used on this page:**

- A **resource** is the unit agr manages. Today there are two resource types: **skills** and **ralphs**. Every `agr.toml` dependency entry has a `type` field set to `"skill"` or `"ralph"`.
- A **skill** is a directory containing a `SKILL.md` file with YAML frontmatter (`name`, `description`) and markdown instructions for an AI coding agent.
- A **ralph** is a directory containing a `RALPH.md` file that defines an autonomous agent loop — executed by a ralph runtime such as [ralphify](https://github.com/kasperjunge/ralphify), not by the AI tools below. See the [Ralph Directory](ralphs.md) for the full format.
- A **handle** identifies a resource: `skill` (from default owner's `skills` repo), `user/skill` (from user's `skills` repo), `user/repo/skill` (from a specific repo), or `./path/to/resource` (local).
- A **source** is a Git server URL template (e.g., GitHub, GitLab, self-hosted) where agr fetches remote resources from.
- A **tool** is one of the supported AI coding agents: Claude Code, Cursor, Codex, OpenCode, GitHub Copilot, or Antigravity. Tools consume skills — ralphs are consumed by a separate ralph runtime.
- **`agr.toml`** is the hand-edited manifest. **`agr.lock`** is the auto-generated lockfile sitting next to it, pinning exact commit SHAs and content hashes for every resolved dependency. See [agr.toml and agr.lock](concepts.md#agrtoml-and-agrlock) in Core Concepts.

## All agr.toml Settings

| Key | Type | Default | What it does |
|-----|------|---------|-------------|
| `tools` | list | `["claude"]` | [AI tools](#multi-tool-setup) to install skills into |
| `default_tool` | string | first in `tools` | Tool used by [`agrx`](agrx.md) and for [instruction sync](#instruction-syncing) |
| `default_owner` | string | `"computerlovetech"` | Default GitHub owner for [1-part handles](concepts.md#remote-handles) (e.g. `agr add setup` → `computerlovetech/skills/setup`) |
| `default_source` | string | `"github"` | [Source](#sources) used when `--source` is not specified |
| `sync_instructions` | bool | `false` | Copy the canonical instruction file to other tools on [`agr sync`](reference.md#agr-sync) |
| `canonical_instructions` | string | auto from `default_tool` | Which [instruction file](#instruction-syncing) is the source of truth (`CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`) |

Dependencies and sources are configured separately — see [Full Example](#full-agrtoml-example) below. Each dependency entry carries a `type` field whose value is `"skill"` or `"ralph"`; agr sets this automatically on `agr add` and you rarely need to edit it by hand.

!!! note "`tools` does not apply to ralphs"
    The `tools` list only affects where **skills** are installed. **Ralphs**
    are installed once per project into `.agents/ralphs/<name>/` regardless
    of the configured tools — they are executed by a ralph runtime, not by
    the tools in the list.

## Multi-Tool Setup

By default, agr targets Claude Code only. To install skills into multiple tools
at once, configure the `tools` list:

```bash
agr init --tools claude,codex,opencode
```

Or update an existing config:

```bash
agr config set tools claude codex opencode cursor
```

When you run `agr add` or `agr sync`, skills are installed into every configured
tool's skills directory:

| Tool | Project skills directory | Global skills directory |
|------|------------------------|------------------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Antigravity | `.gemini/skills/` | `~/.gemini/skills/` |

### Default Tool

The default tool determines which CLI is used by `agrx` and which instruction
file is canonical when syncing:

```bash
agr config set default_tool claude
```

If not set, the first tool in the `tools` list is used.

### Adding and Removing Tools

Add a tool after initial setup — existing skills are installed into it
automatically:

```bash
agr config add tools cursor
```

!!! warning "Removing a tool deletes its skills"
    `agr config remove tools <name>` deletes all skills from that tool's skills
    directory. Skills remain in your other tools and can be reinstalled with
    `agr config add tools <name>`.

### Tool Detection

`agr init` auto-detects which tools you use by looking for
tool-specific files and directories in your repo. Each tool has its own set of
detection signals — see the [Supported Tools](tools.md) page for the full list
per tool. Override detection with `--tools`:

```bash
agr init --tools claude,codex,opencode
```

## Fetch Skills from Custom Git Servers { #sources }

Sources define where agr fetches remote skills from. The default source is
GitHub:

```toml
[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

### Adding a Custom Source

To fetch skills from a self-hosted Git server:

```bash
agr config add sources my-server --url "https://git.example.com/{owner}/{repo}.git"
```

The URL template uses `{owner}` and `{repo}` placeholders, which are filled from
the handle. For example, `agr add user/repo/skill --source my-server` clones
`https://git.example.com/user/repo.git`.

!!! note "`--type` defaults to `git`"
    The `--type` flag defaults to `git` (the only supported type) and can be
    omitted. Other source types may be added in the future.

### Default Source

Set which source is tried first for remote installs:

```bash
agr config set default_source my-server
```

!!! warning "Cannot remove the default source"
    You can't remove a source that is set as `default_source`. Change the
    default first, then remove the source:
    ```bash
    agr config set default_source github
    agr config remove sources my-server
    ```

### Per-Dependency Source

Pin a specific dependency to a source in `agr.toml`:

```toml
dependencies = [
    {handle = "team/internal-skill", type = "skill", source = "my-server"},
    {handle = "anthropics/skills/pdf", type = "skill"},
]
```

## Instruction Syncing

When using multiple tools, you may want to keep instruction files
(`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) in sync. Enable this with:

```bash
agr init --sync-instructions --canonical-instructions CLAUDE.md
```

Or configure it directly:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

When `agr sync` runs, it copies the canonical file's content to the other
instruction files needed by your configured tools. For example, with
`canonical_instructions = "CLAUDE.md"` and `tools = ["claude", "codex"]`, running
`agr sync` copies `CLAUDE.md` content to `AGENTS.md` (used by Codex).

!!! important "Requires 2+ tools"
    Instruction syncing only runs when you have **two or more tools** configured.
    With a single tool there's nothing to sync to, so `agr sync` silently skips
    this step — even if `sync_instructions = true`.

### Auto-detection of canonical file

If you set `sync_instructions = true` but don't set `canonical_instructions`,
agr picks the instruction file of your **default tool** (or the first tool in
your `tools` list). For example, if your default tool is `claude`, the canonical
file is `CLAUDE.md`.

To be explicit, set it yourself:

```bash
agr config set canonical_instructions CLAUDE.md
```

## Private Repositories

agr supports private GitHub repositories. Set a GitHub personal access token in
your environment and agr will use it automatically for all remote operations.

### Setup

Export one of these environment variables:

```bash
export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
```

Or, if you use the [GitHub CLI](https://cli.github.com/):

```bash
export GH_TOKEN="$(gh auth token)"
```

agr checks `GITHUB_TOKEN` first, then falls back to `GH_TOKEN`.

### Token Permissions

The token needs **read access** to the repositories containing your skills:

- **Fine-grained tokens** (recommended): Grant `Contents: Read-only` on the
  specific repositories
- **Classic tokens**: The `repo` scope works but grants broader access

agr injects the token into HTTPS clone URLs transparently — no config changes
needed. It works with `agr add`, `agr sync`, `agrx`, and the Python SDK.

??? note "Persist your token across shell sessions"
    Add the export to your shell profile so it's always available:

    === "bash"

        ```bash
        echo 'export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"' >> ~/.bashrc
        ```

    === "zsh"

        ```bash
        echo 'export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"' >> ~/.zshrc
        ```

    Or load it dynamically from the GitHub CLI:

    ```bash
    export GITHUB_TOKEN="$(gh auth token)"
    ```

??? note "Self-hosted Git servers (non-GitHub)"
    Token injection only applies to GitHub URLs. For self-hosted Git servers,
    configure credentials through your system's Git credential helper:

    ```bash
    git config --global credential.helper store
    ```

## agr.lock — the reproducibility lockfile

Every mutating `agr` command (`add`, `remove`, `sync`) writes an `agr.lock`
file alongside `agr.toml`. The lockfile pins the exact git commit SHA and
content hash for every resolved dependency so that `agr sync` produces
byte-identical installs across machines and over time. agr.lock plays the
same role as `package-lock.json` or `Cargo.lock`.

```toml
# agr.lock — auto-generated. Do not edit.
version = 1

[[skill]]
handle = "anthropics/skills/pdf"
source = "github"
commit = "a0d5bfd4d9658073029d33f979ac5a027568caec"
content-hash = "sha256:75e47183c30bc8651e76286680eddac88a3024a7ee5a7f1bc486d4d3fdee34ce"
installed-name = "pdf"

[[ralph]]
handle = "your-username/agent-resources/bug-hunter"
source = "github"
commit = "9859f7bceb7a46af8482cabb9aa24e0d38a49413"
content-hash = "sha256:fa1ce825fa7e11cd5aac55ee7eac5e9c918e3af113b7988fdbd281a319acc110"
installed-name = "bug-hunter"
```

**Commit `agr.lock` alongside `agr.toml`.** Without it, `agr sync` would
re-resolve against whatever commit is at each repo's HEAD today, and your
teammates would get drift.

### Lockfile-aware sync modes

`agr sync` has two flags that enforce lockfile discipline — use them in CI:

| Flag | Behavior | When to use |
|---|---|---|
| *(no flag)* | Install missing deps, re-resolve, refresh `agr.lock` | Local dev |
| `--locked` | Fail if `agr.lock` is out of date vs `agr.toml`, then install from the lockfile. Never re-resolves. | CI PR checks — catches contributors who forgot to commit an updated lockfile |
| `--frozen` | Install exactly what `agr.lock` specifies. Fail if `agr.lock` is missing or incomplete. Never re-resolves. | CI deploys — guarantees byte-identical installs |

`--frozen` and `--locked` are mutually exclusive. Both work with `-g` for
global scope (`~/.agr/agr.lock`).

!!! warning "Do not edit agr.lock by hand"
    agr overwrites the lockfile on every mutating command. Hand-edits will
    be clobbered. To update a pinned commit, run `agr add <handle>
    --overwrite` or remove-and-re-add the dependency.

## Global Installs

Skills can be installed globally (available in all projects) using the `-g` flag:

```bash
agr add -g anthropics/skills/pdf
agr sync -g
agr list -g
agr remove -g anthropics/skills/pdf
```

Global configuration lives at `~/.agr/agr.toml` and skills are installed into
each tool's global skills directory (see table above).

## Full agr.toml Example

???+ example "Complete annotated agr.toml"

    ```toml
    default_source = "github" # (1)!
    tools = ["claude", "codex", "opencode"] # (2)!
    default_tool = "claude" # (3)!
    sync_instructions = true # (4)!
    canonical_instructions = "CLAUDE.md" # (5)!

    dependencies = [ # (6)!
        {handle = "anthropics/skills/frontend-design", type = "skill"},
        {handle = "vercel-labs/agent-browser/agent-browser", type = "skill"},
        {handle = "team/internal-tool", type = "skill", source = "my-server"}, # (7)!
        {path = "./skills/local-skill", type = "skill"}, # (8)!
        {handle = "your-username/agent-resources/bug-hunter", type = "ralph"}, # (10)!
    ]

    [[source]] # (9)!
    name = "github"
    type = "git"
    url = "https://github.com/{owner}/{repo}.git"

    [[source]]
    name = "my-server"
    type = "git"
    url = "https://git.example.com/{owner}/{repo}.git"
    ```

    1. Source used when `--source` is not passed to `agr add` or `agrx`
    2. Skills are installed into all listed tools on every `agr add` and `agr sync`
    3. Tool used by `agrx` and for instruction sync — defaults to the first in `tools`
    4. Copies the canonical instruction file to other tools on `agr sync`
    5. The instruction file treated as the source of truth (`CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`)
    6. Must appear before any `[[source]]` blocks — each entry needs `type = "skill"` or `type = "ralph"` plus either `handle` or `path`
    7. Pin a dependency to a specific source instead of using `default_source`
    8. Local path dependencies point to a directory on disk — no Git fetch needed
    9. Each `[[source]]` defines a Git server URL template with `{owner}` and `{repo}` placeholders
    10. Ralph dependencies install to `.agents/ralphs/<name>/` once per project, ignoring the `tools` list — see the [Ralph Directory](ralphs.md) for details

## Managing Config

All `agr config` subcommands at a glance:

| Command | What it does |
|---------|-------------|
| `agr config show` | View formatted config with all settings |
| `agr config path` | Print the path to `agr.toml` |
| `agr config edit` | Open `agr.toml` in `$VISUAL` or `$EDITOR` |
| `agr config get <key>` | Read a single config value |
| `agr config set <key> <values>` | Write a scalar or replace a list |
| `agr config add <key> <values>` | Append to a list (`tools`, `sources`) |
| `agr config remove <key> <values>` | Remove from a list (`tools`, `sources`) |
| `agr config unset <key>` | Clear a setting back to its default |

Add `-g` to any command to operate on the global config (`~/.agr/agr.toml`).
See the [CLI Reference](reference.md#agr-config) for full details and examples.

!!! note "`agr config edit` requires an editor"
    If neither `$VISUAL` nor `$EDITOR` is set, you'll get an error. Set one:
    ```bash
    export EDITOR="vim"              # or nano, code --wait, etc.
    ```

## Next Steps

- [**Supported Tools**](tools.md) — Details on each tool's skills directory and behavior
- [**Teams**](teams.md) — Set up multi-tool teams with shared skills and CI/CD
- [**Troubleshooting**](troubleshooting.md) — Fix common config and sync issues
