# Syncing, upgrading, and the lockfile

`agr sync` is what teammates run after pulling. `agr upgrade` is what the
release captain runs to pull in upstream changes. Don't confuse them.

## agr sync

```bash
agr sync
```

Runs four stages in order:

1. **Instruction sync** — copies the canonical instruction file
   (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) to the others. Fires only when
   `sync_instructions = true` and 2+ tools are configured.
2. **Migrations** — renames legacy skill directories
   (`.codex/skills/` → `.agents/skills/`, `.opencode/skill/` →
   `.opencode/skills/`, etc.). Automatic; no user action needed.
3. **Dependency install** — installs any deps from `agr.toml` not already on
   disk. Same-repo skills are batched into one download. Already-installed
   deps are left alone (this is the key difference from `agr upgrade`).
4. **Lockfile update** — writes `agr.lock` with the resolved commit SHA and
   content hash for every dep.

### Use cases

| Situation | Command |
|---|---|
| You pulled and a teammate added new deps | `agr sync` |
| You added a tool to `tools = [...]` and want existing deps in the new tool | `agr sync` |
| You need byte-identical installs in CI | `agr sync --frozen` |
| You want CI to fail if `agr.lock` is stale | `agr sync --locked` |
| You want the latest upstream code, even if already installed | `agr upgrade` (NOT `agr sync`) |

### Flags

| Flag | Effect |
|---|---|
| `--frozen` | Install exactly what `agr.lock` says. Fail if lock is missing or doesn't cover every dep. Never re-resolves. **CI deploy.** |
| `--locked` | Fail if `agr.lock` is out of date vs `agr.toml`, then install from the lock. **CI PR check.** |
| `--global`, `-g` | Sync `~/.agr/agr.toml`. Ralph deps are skipped (project-scoped only). |

`--frozen` and `--locked` are mutually exclusive.

## CI patterns

### PR check

Make CI fail if a contributor added a dep without committing the regenerated
lockfile:

```yaml
# .github/workflows/ci.yml (sketch)
- run: agr sync --locked
```

### Deploy

Lock everything to the recorded commits — no surprise upstream updates:

```yaml
- run: agr sync --frozen
```

## agr upgrade

```bash
agr upgrade                              # everything in scope
agr upgrade pdf                          # short-name match
agr upgrade anthropics/skills/pdf        # full handle
agr upgrade pdf collaboration            # several at once
```

`agr upgrade` re-fetches the named (or all) deps at the current upstream HEAD
and refreshes `agr.lock`. Runs the same instruction-sync and migration stages
as `agr sync` first.

### Short-name matching

`agr upgrade pdf` works when exactly one dep has the installed name `pdf`. If
two deps share a name (e.g. `user1/skills/pdf` and `user2/skills/pdf`), agr
errors and asks you to disambiguate with the full handle.

### Same-repo siblings — important gotcha

Upgrading one skill from a multi-skill repo only refreshes that one. Sibling
skills in the same repo keep their existing lockfile commit and on-disk
content.

```bash
# Bad: only refreshes pdf, leaves docx and xlsx pinned
agr upgrade anthropics/skills/pdf

# Good: refreshes all anthropics/skills siblings together
agr upgrade   # everything in scope
# or
agr upgrade anthropics/skills/pdf anthropics/skills/docx anthropics/skills/xlsx
```

If the user only wants to bump siblings together (e.g. all of
`anthropics/skills/*`), they must list each one explicitly.

### Flags

| Flag | Effect |
|---|---|
| `--global`, `-g` | Upgrade global deps from `~/.agr/agr.toml` |

## agr.lock

Auto-generated; never hand-edit. Format:

```toml
version = 1

[[skill]]
handle = "anthropics/skills/pdf"
source = "github"
commit = "a0d5bfd4d9658073029d33f979ac5a027568caec"
content-hash = "sha256:75e47..."
installed-name = "pdf"

[[skill]]
path = "skills/internal-review"
installed-name = "internal-review"
```

Local-path deps record `path` instead of `handle`/`source`/`commit` — there's
nothing to pin remotely.

If `agr.lock` looks broken or out of sync:

1. Try `agr sync` first (re-resolves and rewrites the lock).
2. If still broken, delete the lock and `agr sync` to regenerate.

Never fix it by hand.

## See also

- [installing-skills.md](installing-skills.md) — `agr add` and `agr remove`
- [configuration.md](configuration.md) — `tools`, `sources`, instruction sync
- [troubleshooting.md](troubleshooting.md) — fixing common errors
