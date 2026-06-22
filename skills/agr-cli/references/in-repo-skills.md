# In-repo skills — the recommended workflow

Skills that ship with the codebase (project conventions, internal workflows,
domain-specific helpers) belong in version control alongside the code they
describe. The convention this skill encourages: keep them under `skills/` at
the repo root (or at the root of a relevant submodule) and install them as
local-path deps in `agr.toml`.

This page covers scaffolding, structuring, iterating, and shipping in-repo
skills.

## Why `skills/` at the repo root

- **Reviewable in PRs.** Changes to skill content show up in code review.
- **No drift between tools.** One source of truth in `skills/<name>/`; agr
  fans it out to every configured tool's skills dir.
- **Travels with the repo.** New contributors run `agr sync` and immediately
  have the team's skills loaded into their AI tools.
- **Distinct from `.claude/skills/` etc.** Those are gitignored, generated,
  and managed by agr. `skills/` is the source.

For monorepos / repos with submodules, place a `skills/` dir at the root of
each submodule that has its own concerns. Each submodule maintains its own
`agr.toml` referencing its local-path skills.

## Scaffold a new skill

```bash
agr init my-skill
mkdir -p skills && mv my-skill skills/
```

`agr init <name>` creates `<name>/SKILL.md` in the current directory with a
starter template. Move it under `skills/` after.

The starter template:

```markdown
---
name: my-skill
description: TODO — describe what this skill does and when to use it
---

# my-skill

## When to use

Describe when this skill should be used.

## Instructions

Provide detailed instructions here.
```

Edit `skills/my-skill/SKILL.md`:

- **`name`** must match the directory name. 1–64 chars, lowercase, hyphens
  allowed (no leading/trailing/consecutive `-`).
- **`description`** is the only trigger signal — make it pushy and specific.
  List the user phrases / contexts that should fire it.

For body authoring guidance, defer to the user or the official `skill-creator`
skill; this skill scaffolds and registers, but does not write skill content.

## Register in agr.toml

```bash
agr add ./skills/my-skill
```

Writes:

```toml
dependencies = [
    {path = "./skills/my-skill", type = "skill"},
]
```

And installs into `.claude/skills/my-skill/`, `.cursor/skills/my-skill/`, etc.
for every tool in `tools`.

## Iterate

Edit `skills/my-skill/SKILL.md`, then reinstall:

```bash
agr upgrade my-skill
```

`agr upgrade` reinstalls a fresh on-disk copy of the local skill into every
configured tool and refreshes `agr.lock` — the canonical re-sync after editing
an already-registered in-repo skill.

Alternatives:

- `agr add ./skills/my-skill --overwrite` — path-based; reach for it when the
  skill's path changed or you're re-adding it, not for plain edits.
- `agr sync` — only installs what's missing, so it won't pick up edits to an
  already-installed skill. Use `agr upgrade` to force the refresh.

To test ephemerally (no permanent install) on a path:

```bash
agrx ./skills/my-skill -p "test prompt"
```

## Structure for complex skills

Beyond a single SKILL.md:

```
skills/my-skill/
├── SKILL.md             # required — agent instructions, < 500 lines
├── references/          # docs the agent reads on demand
│   └── api-schema.md
├── scripts/             # deterministic shell-outs
│   └── validate.sh
└── assets/              # templates, fixtures
    └── template.json
```

| Folder | Use when |
|---|---|
| `references/` | The agent needs background info that's too long for SKILL.md (style guides, schema dumps, decision matrices). Reference from SKILL.md as `[name](references/name.md)`. |
| `scripts/` | A workflow has more than 2 piped shell commands, or needs deterministic output (lint, codegen, validation). Avoids re-deriving the pipeline every run. |
| `assets/` | Templates, JSON fixtures, sample inputs. Things the skill emits or fills in. |

Keep SKILL.md focused — under 500 lines. The body should be a thin index that
points into `references/` for depth.

## Promote a remote skill to in-repo

If the user wants to fork a remote skill and modify it locally:

```bash
agr remove anthropics/skills/pdf
git clone --depth 1 https://github.com/anthropics/skills /tmp/skills-src
cp -r /tmp/skills-src/pdf skills/pdf
agr add ./skills/pdf
```

(Or download just the folder via `git sparse-checkout` if cloning the whole
repo is overkill.)

Mention to the user that this forks the skill — they're now responsible for
keeping it up to date. Better to upstream improvements via PR if possible.

## Sharing in-repo skills as a public package

Once stable, other repos can install via remote handle:

```bash
# In another project
agr add your-username/this-repo/my-skill
```

The 3-part handle works because the skill lives at `<repo-root>/my-skill/`
when downloaded — wait, no: the skill lives under `skills/my-skill/` here,
which means the remote handle is actually `your-username/this-repo/skills/my-skill`?

Actually `agr add` searches the repo for any directory containing a SKILL.md
matching the requested name, so `your-username/this-repo/my-skill` works as
long as there's a `my-skill/` (under `skills/` or anywhere else) with a
SKILL.md inside. If you publish a dedicated skills repo named `skills`, the
short handle `your-username/my-skill` works.

Two convenience layouts:

- **Dedicated skills repo** (`your-username/skills`): one folder per skill at
  the repo root → users install with 2-part handle `your-username/my-skill`.
- **Skills nested under a project repo** (`your-username/myproj/skills/foo`):
  users install with 3-part handle `your-username/myproj/foo`.

## Checklist when adding a new in-repo skill

- [ ] Scaffolded with `agr init <name>`
- [ ] Moved to `skills/<name>/`
- [ ] `name` in frontmatter matches directory name
- [ ] `description` lists explicit trigger phrases / contexts
- [ ] Registered with `agr add ./skills/<name>`
- [ ] Tested with `agrx ./skills/<name>` or `agr run <name>`
- [ ] `agr.toml`, `agr.lock`, and `skills/<name>/` committed

## See also

- [installing-skills.md](installing-skills.md) — `agr add --overwrite`
- [running-skills.md](running-skills.md) — testing with `agr run` / `agrx`
- [setup.md](setup.md) — repo bootstrap
