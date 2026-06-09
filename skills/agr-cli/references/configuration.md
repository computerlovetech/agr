# Configuration — `agr config` and `agr.toml`

The full surface for managing project (and global) configuration.

## Subcommands

```bash
agr config show                 # formatted view of current config
agr config path                 # print path to agr.toml
agr config edit                 # open in $VISUAL or $EDITOR
agr config get <key>            # read a value
agr config set <key> <values>   # write scalar or replace list
agr config add <key> <values>   # append to a list
agr config remove <key> <values># remove from a list
agr config unset <key>          # clear to default
```

Add `-g` / `--global` to operate on `~/.agr/agr.toml` instead of `./agr.toml`.

## All keys

| Key | Type | Default | What it does |
|---|---|---|---|
| `tools` | list | `["claude"]` | AI tools to install skills into. Skills fan out to every tool listed; ralphs ignore this. |
| `default_tool` | string | first in `tools` | Tool used by `agrx` and as the canonical for instruction sync |
| `default_owner` | string | `computerlovetech` | GitHub owner for 1-part handles (`agr add setup` → `<owner>/skills/setup`) |
| `default_source` | string | `github` | Source used when `--source` is not specified |
| `sync_instructions` | bool | `false` | Mirror canonical instruction file to other tools on `agr sync` |
| `canonical_instructions` | string | derived from `default_tool` | Source of truth: `CLAUDE.md` or `AGENTS.md` |
| `sources` | list | `[github]` | Git URL templates (see [Sources](#sources)) |

## Common operations

```bash
# Multi-tool
agr config set tools claude codex opencode
agr config add tools cursor
agr config remove tools cursor          # ⚠ deletes that tool's skills/

# Default tool for agrx
agr config set default_tool claude

# Custom owner
agr config set default_owner my-org

# Instruction syncing
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr config unset sync_instructions      # back to default (false)
```

## ⚠ `agr config remove tools <name>` deletes skills

Removing a tool from `tools` also deletes that tool's skills directory
(`.cursor/skills/`, etc.). Skills remain in the *other* configured tools.
Re-adding the tool with `agr config add tools cursor` followed by `agr sync`
re-installs them.

Always confirm with the user before running this command.

## Sources

A source is a Git URL template:

```toml
[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

`{owner}` and `{repo}` come from the handle.

### Add a custom source

```bash
agr config add sources gitlab \
    --url "https://gitlab.com/{owner}/{repo}.git"

agr config add sources self-hosted \
    --url "https://git.internal.example.com/{owner}/{repo}.git"
```

`--type` defaults to `git` and is the only supported type today.

### Use a non-default source

Per-command:

```bash
agr add team/internal-tool --source gitlab
```

Per-dep (in `agr.toml`):

```toml
dependencies = [
    {handle = "team/internal-tool", type = "skill", source = "gitlab"},
]
```

Switch the default:

```bash
agr config set default_source gitlab
```

### Private repos

Set the host's auth token before invoking agr:

```bash
export GITHUB_TOKEN="ghp_..."
agr add my-org/private-skills/secret-skill
```

For GitLab, use `GITLAB_TOKEN`; for self-hosted Git, see your host's docs.

## Instruction syncing

When the user maintains a canonical instructions file (e.g. `CLAUDE.md`) and
wants the same content in the other tools' equivalents (`AGENTS.md`),
enable instruction syncing:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

Then `agr sync` copies the canonical file to the others. Mappings:

| Tool | Instruction file |
|---|---|
| Claude Code | `CLAUDE.md` |
| Codex / OpenCode / Copilot / Pi | `AGENTS.md` |

Only fires when 2+ tools are configured. With one tool, it's a no-op.

## Full agr.toml example

```toml
default_source = "github"
default_owner = "my-org"
tools = ["claude", "codex", "opencode"]
default_tool = "claude"
sync_instructions = true
canonical_instructions = "CLAUDE.md"

dependencies = [
    {handle = "anthropics/skills/pdf", type = "skill"},
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {path = "./skills/project-conventions", type = "skill"},
    {handle = "team/internal-tool", type = "skill", source = "gitlab"},
    {handle = "your-username/agent-resources/bug-hunter", type = "ralph"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"

[[source]]
name = "gitlab"
type = "git"
url = "https://gitlab.com/{owner}/{repo}.git"
```

Dependencies must come BEFORE any `[[source]]` blocks (TOML semantics).

## Project vs global

| Path | Used for |
|---|---|
| `./agr.toml` | Per-project deps, tools, sources. Committed to git. |
| `~/.agr/agr.toml` | User's global skills, available across all projects. |

`-g` / `--global` on every config subcommand operates on the global file:

```bash
agr config -g show
agr config -g set tools claude cursor
```

## See also

- [setup.md](setup.md) — initial repo bootstrap
- [handles.md](handles.md) — handle formats and resolution
- [syncing.md](syncing.md) — what `agr sync` does with this config
