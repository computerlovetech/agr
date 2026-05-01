# Installing and removing skills

Day-to-day operations for `agr add` and `agr remove`. For canonical flag
listings: `agr add --help`.

## agr add

```bash
agr add <handle>...
```

- Installs into every tool listed in `tools`.
- Auto-creates `agr.toml` if missing — no `agr init` first.
- Skills from the same repository are batched into one download.

### Common patterns

```bash
agr add anthropics/skills/pdf                        # remote skill
agr add anthropics/skills/pdf anthropics/skills/docx # multi
agr add ./skills/my-skill                            # local in-repo
agr add anthropics/skills/pdf --overwrite            # replace existing
agr add anthropics/skills/pdf --source gitlab        # use named source
agr add -g anthropics/skills/pdf                     # global (~/.claude/skills/, etc.)
```

### Flags

| Flag | Effect |
|---|---|
| `--overwrite`, `-o` | Replace existing skills/ralphs |
| `--source`, `-s <name>` | Use a non-default source from `agr.toml` |
| `--global`, `-g` | Install globally; ralph deps are skipped under `-g` |

### What `agr add` writes

After a successful install, `agr add` adds a line to `agr.toml`:

```toml
dependencies = [
    {handle = "anthropics/skills/pdf", type = "skill"},
]
```

And writes the resolved commit + content hash into `agr.lock`. Both files
should be committed.

### --overwrite gotcha

`--overwrite` replaces the installed copy. If the user has been editing a
locally-installed in-repo skill (e.g. tweaking `.claude/skills/my-skill/` by
hand instead of editing `skills/my-skill/`), `--overwrite` will discard those
edits. Confirm with the user first if there's any chance of local mods.

For in-repo skills, the workflow is: edit the source under `skills/<name>/`,
then `agr add ./skills/<name> --overwrite` to push it into each tool's skills
dir.

## agr remove

```bash
agr remove <handle>...
```

- Deletes the skill from every tool's skills directory.
- Removes the entry from `agr.toml`.
- Refreshes `agr.lock`.

### Common patterns

```bash
agr remove anthropics/skills/pdf
agr remove ./skills/my-skill
agr remove -g anthropics/skills/pdf      # remove from global
agr remove pdf docx                      # multi (short names work if unambiguous)
```

### Flags

| Flag | Effect |
|---|---|
| `--global`, `-g` | Remove from `~/.agr/agr.toml` and global tool dirs |

`agr remove` is destructive but reversible — the user can `agr add` again.
Still, confirm before running on shared/in-repo skills, since removing also
deletes the entry from `agr.toml` (the user may have intended to just
uninstall locally without touching the manifest, but agr does not support
that — you have to comment the dep out manually if needed).

## Listing and inspecting

```bash
agr list           # everything in agr.toml + status
agr list -g        # everything in ~/.agr/agr.toml
```

Status values:

| Status | Meaning |
|---|---|
| `installed` | Present in all configured tools |
| `partial (claude, cursor)` | Installed in some tools but not all — `agr sync` to fix |
| `not synced` | In `agr.toml` but not on disk — `agr sync` |
| `invalid` | Handle in `agr.toml` cannot be parsed — fix the handle |

## Troubleshooting installs

- **"Repository not found"** — handle wrong or repo private. Check the handle
  format ([handles.md](handles.md)) and whether `GITHUB_TOKEN` is set.
- **"Skill not found in repo"** — directory name in the handle is wrong. Look
  at the GitHub repo to confirm the folder name.
- **Install succeeds but `agr list` shows `partial`** — a tool's directory
  isn't writable, or migrations haven't run. Run `agr sync`.
- **`agr.lock` rejected by `--locked` in CI** — local user added a dep but
  didn't commit the regenerated lock. Run `agr sync` locally and commit.

## See also

- [syncing.md](syncing.md) — `agr sync` and `agr upgrade` lifecycle
- [handles.md](handles.md) — handle formats and resolution
- [in-repo-skills.md](in-repo-skills.md) — local-path workflow
