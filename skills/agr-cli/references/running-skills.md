# Running skills — `agr run` vs `agrx`

Two commands for invoking skills. They look similar; the difference matters.

## `agr run` — invoke an already-installed skill

```bash
agr run <skill-name> [-- <extra prompt>]
```

Looks up the skill in the configured tool's skills directory and shells out
to that tool's CLI with the skill prompt prefilled. No download, no cleanup,
no network — the skill must already be installed (via `agr add` or
`agr sync`).

### Examples

```bash
agr run pdf                              # default tool
agr run pdf -- "summarise report.pdf"    # extra prompt after --
agr run pdf -p "summarise report.pdf"    # same, via -p
agr run pdf --tool cursor                # override tool
agr run pdf -i                           # interactive session
agr run pdf -g                           # global skill
```

### Flags

| Flag | Effect |
|---|---|
| `--tool`, `-t <tool>` | Override `default_tool` |
| `--interactive`, `-i` | Open the tool in interactive mode with the skill prompt prefilled |
| `--prompt`, `-p <text>` | Append this prompt after the skill reference |
| `--global`, `-g` | Look up in `~/.<tool>/skills/` instead of `./.<tool>/skills/` |

Anything after `--` is appended to the prompt as free-form input, after `-p`
if both are passed.

### Tool resolution order

1. `--tool` flag
2. `default_tool` in `agr.toml`
3. First entry in `tools`
4. `claude`

If the skill isn't installed in the chosen tool, `agr run` lists the tools'
available skills so you can correct the name or `agr sync` first.

### Short-name matching

`agr run pdf` works when one installed skill has the short name `pdf`. With
collisions, agr falls back to the qualified name like `user--repo--skill`;
match that or the full handle.

## `agrx` — ephemeral skill runner

```bash
agrx <handle> [options]
```

Downloads the skill, runs it via the selected tool's CLI, then cleans up.
Nothing is added to `agr.toml`, nothing persists in the project.

### Examples

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/skill-creator -i              # interactive
agrx anthropics/skills/pdf --tool cursor
agrx vercel-labs/agent-browser/agent-browser --source github
agrx ./skills/my-skill -p "test"                     # local path works too
agrx -g anthropics/skills/pdf                        # install to global tool dir
```

### Flags

| Flag | Effect |
|---|---|
| `--tool`, `-t <tool>` | Tool CLI to use; defaults to `default_tool` from config |
| `--interactive`, `-i` | Run skill, then continue in interactive mode |
| `--prompt`, `-p <text>` | Pass a prompt to the skill |
| `--source`, `-s <name>` | Use a specific source from `agr.toml` |
| `--global`, `-g` | Install to global tool skills directory rather than the repo-local one |

## When to use which

| Need | Command |
|---|---|
| Skill is installed; just invoke it | `agr run` |
| Try a skill once without persisting | `agrx <remote-handle>` |
| Test an in-repo skill while iterating | `agrx ./skills/<name>` |
| Skill not installed but you want it permanent | `agr add` first, then `agr run` |
| Quick demo / one-shot for a teammate | `agrx <remote-handle> -p "..."` |

## Tool prerequisites

Both commands shell out to the tool's CLI:

| Tool | CLI command |
|---|---|
| Claude Code | `claude` |
| Cursor | (via Cursor IDE / agent integration — check user's setup) |
| Codex | `codex` |
| OpenCode | `opencode` |
| Copilot | `gh copilot` |
| Antigravity | (IDE-driven) |

If the tool's CLI isn't installed, both commands will fail with a "command
not found" error. Surface that clearly to the user — agr can't help install
the AI tool itself.

## See also

- [installing-skills.md](installing-skills.md) — installing for `agr run`
- [in-repo-skills.md](in-repo-skills.md) — testing during iteration with `agrx`
