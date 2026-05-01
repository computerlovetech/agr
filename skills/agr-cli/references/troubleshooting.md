# Troubleshooting

Common failure modes and their fixes.

## Install errors

### "Repository not found" / "skill not found"

The handle format is wrong, or the repo is private.

- Check 2-part vs 3-part: `user/skill` assumes a repo named `skills`. If the
  repo has a different name, use `user/repo/skill`.
- Open the URL `https://github.com/<owner>/<repo>` in a browser to confirm
  the repo exists.
- For private repos: `export GITHUB_TOKEN=...` before re-running.

See [handles.md](handles.md) for full handle resolution.

### "Skill directory not found in repo"

The repo exists but the named subdirectory doesn't.

```bash
agr add anthropics/skills/typo-here    # → not found
```

Look at the GitHub repo and confirm the folder name. agr searches for any
directory containing a SKILL.md matching the requested name.

### "Auth required" on a private repo

```bash
export GITHUB_TOKEN="ghp_..."          # GitHub
export GITLAB_TOKEN="..."              # GitLab
agr add my-org/private-skills/secret
```

The token needs read access to the repo.

## Sync / lockfile errors

### "agr.lock is out of date" (--locked failure in CI)

A contributor added a dep but didn't commit the regenerated lockfile.

```bash
agr sync         # locally — re-resolves and rewrites agr.lock
git add agr.lock
git commit -m "chore: refresh agr.lock"
```

Then push.

### "agr.lock missing or incomplete" (--frozen failure in CI)

Either `agr.lock` isn't committed, or a dep was added to `agr.toml` without
running `agr sync`. Same fix as above.

### `agr list` shows `partial (claude, cursor)`

The skill is installed in some configured tools but not all (e.g. you added
a tool to `tools = [...]` and didn't sync yet, or one tool's skills dir
wasn't writable).

```bash
agr sync
```

If still partial, check permissions on the missing tool's skills dir.

### `agr list` shows `not synced`

Listed in `agr.toml` but not on disk.

```bash
agr sync
```

### `agr list` shows `invalid`

The handle in `agr.toml` cannot be parsed. Open `agr.toml` and fix the entry
manually, or remove and re-add:

```bash
# manually edit agr.toml to remove the bad entry, then:
agr add <correct-handle>
```

## Manifest errors

### "agr.toml syntax error"

You hand-edited `agr.toml` and broke TOML syntax. Common causes:

- `[[source]]` block placed before `dependencies = [...]` (deps must come
  first).
- Missing `type` on a dep entry.
- Unclosed array.

Easiest fix: open in editor, paste a known-good snippet from
[configuration.md](configuration.md), and re-add deps with `agr add`.

### Type errors after manual edit

If you hand-edited a dep entry and `agr sync` complains about the `type`,
let agr rewrite it:

```bash
# Remove the manually-edited entry, then re-add:
agr add <handle>
```

## Run-time errors

### "claude: command not found" (or codex / opencode / etc.)

The AI tool's CLI isn't installed. agr only manages skills — it doesn't
install the AI tools themselves. Direct the user to the tool's install docs.

### "Skill not installed for tool X"

`agr run pdf --tool cursor` but the skill isn't in `.cursor/skills/`.

- If `cursor` is in `tools`: `agr sync` to fan out.
- If `cursor` is NOT in `tools`: add it first
  (`agr config add tools cursor`), then `agr sync`.

### `agr run pdf` errors with "ambiguous short name"

Two installed skills share the name `pdf`. Use the full handle:

```bash
agr run user--repo--pdf            # collision-fallback installed-name
# or
agrx anthropics/skills/pdf         # ephemeral with full handle
```

## Configuration errors

### Removed a tool by accident; lost its skills

```bash
agr config remove tools cursor    # this DELETED .cursor/skills/
```

Recover:

```bash
agr config add tools cursor
agr sync
```

The skills are re-installed from `agr.toml` (using the pinned commits in
`agr.lock`).

### `default_owner` resolving wrong handle

You set `default_owner = "my-org"` but `agr add setup` is hitting
`computerlovetech`. Check:

```bash
agr config get default_owner
agr config show
```

If global config overrides it, `-g` lets you check / fix the global file.

## When all else fails

1. `agr config show` — confirm config matches expectations.
2. `agr list` — see what agr thinks is installed.
3. `cat agr.toml agr.lock` — look at the manifest and lockfile.
4. Delete `agr.lock` and run `agr sync` to regenerate from scratch.
5. As a nuclear option: `rm -rf .claude/skills/ .cursor/skills/ ...` then
   `agr sync` to reinstall everything. (Confirm with the user first.)

## Reporting bugs upstream

agr issues: https://github.com/computerlovetech/agr/issues

Useful info to include:

- `agr --version`
- `agr config show`
- `agr.toml` and `agr.lock` (redact private handles if needed)
- The exact command and full error output
