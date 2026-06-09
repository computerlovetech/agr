# CLI reference

Two binaries: `agr` for managing skills in a project, and `agrx` for running a
skill without installing it.

[`agr init`](#agr-init) · [`agr add`](#agr-add) · [`agr remove`](#agr-remove) ·
[`agr sync`](#agr-sync) · [`agr upgrade`](#agr-upgrade) ·
[`agr list`](#agr-list) · [`agr run`](#agr-run) · [`agr config`](#agr-config) ·
[`agrx`](#agrx)

## Global flags

| Flag        | Description                                              |
|-------------|----------------------------------------------------------|
| `--version` | Print version and exit.                                  |
| `--quiet`   | Suppress non-error output.                               |
| `--global`  | Operate on `~/.agr/agr.toml` instead of the project's.   |

Most subcommands accept `-g, --global`.

## `agr init`

Initialize `agr.toml` in the current directory, or scaffold a new skill.

```bash
agr init                    # write agr.toml
agr init my-skill           # scaffold my-skill/SKILL.md
```

| Flag      | Default  | Description                                               |
|-----------|----------|-----------------------------------------------------------|
| `--tools` | `claude` | Comma-separated tool list (e.g. `claude,codex,opencode`). |

## `agr add`

Add one or more skills from GitHub handles or local paths. Updates `agr.toml`,
`agr.lock`, and syncs.

```bash
agr add anthropics/skills/pdf
agr add ./my-skill
agr add anthropics/skills/pdf maragudk/skills/code-review
```

| Flag              | Default | Description                |
|-------------------|---------|----------------------------|
| `-o, --overwrite` | false   | Overwrite existing skills. |

## `agr remove`

Remove one or more skills. Updates `agr.toml`, `agr.lock`, and syncs.

```bash
agr remove anthropics/skills/pdf
agr remove ./my-skill
```

## `agr sync`

Install all skills declared in `agr.toml`. Idempotent; safe to run any time.

```bash
agr sync
```

| Flag       | Default | Description                                                  |
|------------|---------|--------------------------------------------------------------|
| `--frozen` | false   | Install from lockfile exactly; fail if lockfile incomplete.  |
| `--locked` | false   | Fail if lockfile is out of date with `agr.toml`.             |

## `agr upgrade`

Re-install dependencies at the latest upstream commit (or fresh copy for local
paths) and refresh `agr.lock`.

```bash
agr upgrade                              # all
agr upgrade anthropics/skills/pdf        # one (full handle)
agr upgrade pdf collaboration            # several (short names)
```

## `agr list`

List all skills declared for the current scope and whether they're installed.

```bash
agr list
```

## `agr run`

Run an installed skill in the project's configured tool. Anything after `--`
is appended to the prompt.

```bash
agr run pdf
agr run pdf -- "summarise report.pdf"
agr run pdf --tool cursor
```

| Flag                | Default    | Description                                                                          |
|---------------------|------------|--------------------------------------------------------------------------------------|
| `-t, --tool`        | configured | Tool CLI: `claude`, `cursor`, `codex`, `opencode`, `copilot`, `pi`.                  |
| `-i, --interactive` | false      | Invoke the tool in interactive mode with the skill prefilled.                        |
| `-p, --prompt`      |            | Extra prompt text appended after the skill reference.                                |

## `agr config`

Read or edit `agr.toml`.

```bash
agr config show
agr config get tools
agr config set default-tool claude
```

| Subcommand          | Description                      |
|---------------------|----------------------------------|
| `show`              | Print the effective config.      |
| `edit`              | Open `agr.toml` in `$EDITOR`.    |
| `get <key>`         | Read a config value.             |
| `set <key> <value>` | Write a scalar or replace a list.|

## `agrx`

The ephemeral cousin. Run a skill without touching `agr.toml`.

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/pdf -i
```

| Flag                | Description                          |
|---------------------|--------------------------------------|
| `-p, --prompt`      | Prompt to pass to the skill.         |
| `-i, --interactive` | Invoke the tool in interactive mode. |
| `-t, --tool`        | Tool CLI to use.                     |
