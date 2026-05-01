---
name: improve-skill
description: >
  Iteratively improve an existing AI agent skill (SKILL.md) based on session
  feedback or a retrospective after using it. Use whenever the user says:
  "improve the X skill", "update the X skill", "let's revise X based on what
  we just did", "the X skill should also handle Y", "X skill didn't trigger
  when it should have", "feedback on X skill", "retrospective on X", or
  otherwise wants to capture lessons from a session back into the skill that
  drove it. Handles in-repo skills (under skills/) by editing the source,
  committing, and re-installing via `agr upgrade`. Handles remote/upstream
  skills by offering to fork them in-repo or to file a GitHub issue via `gh`.
  Do NOT use for greenfield skill authoring (a separate concern — see
  `anthropics/skills/skill-creator`) or for installing / syncing / removing
  skills (use the `agr` CLI directly).
---

# Improve Skill

Capture lessons from a session into the skill that drove it. The default
shape is **listen → propose → align → apply → re-install**.

## When to use

Trigger when the user wants to revise an existing SKILL.md based on what
happened in the session. Examples:

- "improve the X skill"
- "let's update X based on what we learned"
- "X skill should also handle …"
- "X didn't trigger when it should have"
- "retrospective on X" / "feedback on X"

Do NOT use this skill for:

- **Greenfield skill authoring.** Use `agr init` to scaffold a SKILL.md and
  defer the body content to the user — or to a dedicated authoring skill
  such as `anthropics/skills/skill-creator`
  (`agr add anthropics/skills/skill-creator`).
- **Installing / syncing / removing skills.** That's plain `agr` CLI work
  (`agr add`, `agr sync`, `agr upgrade`, `agr remove`).

## Step 1: Identify the skill

Ask which skill is being improved if it isn't obvious from context. Then
locate the source:

```bash
agr list                # see installed deps and short names
ls skills/              # in-repo source if present
cat agr.toml            # see whether the dep is local-path or remote
```

Two cases — they have different update paths:

| Case | Source location | Update path |
|---|---|---|
| **In-repo** (`{path = "./skills/<name>", type = "skill"}` in `agr.toml`) | `skills/<name>/` | Edit source → commit → `agr upgrade <name>` |
| **Remote** (`{handle = "user/repo/<name>", …}`) | Upstream GitHub repo | Cannot edit directly — see Step 5 |

If the skill isn't installed at all but the user wants to improve it, ask
whether to add it first (and which case applies).

## Step 2: Receive feedback

**Listen.** The user invoked this skill because they have something to say
— let them say it. Do not interrogate. Do not run a checklist of questions
at them. Take in whatever they offer, in whatever shape they offer it.

Only ask a clarifying question if you genuinely cannot proceed without one
(e.g. the user named a skill that doesn't exist, or two skills share the
name and you need to disambiguate). Even then, ask the minimum.

Be **dynamic**. The user may surface things in any shape — a single
sentence ("the description should also fire on X"), a structured list, or a
ramble that you need to distill. They may also surface things outside the
standard buckets below (rename a section, restructure `references/`, change
output format, drop a deprecated workflow, fix a typo). Apply whatever the
user actually says.

The buckets below are a mental map for *you* when distilling what you
heard, not a checklist to recite at the user:

- **`description` / triggers** — under-fired or over-fired
- **Gotchas / boundaries** — a foot-gun the skill didn't warn about
- **Workflow steps** — missing, wrong, or out of order
- **References** — a topic kept needing more depth → new `references/<topic>.md`
- **Examples / output format** — vague where it should be concrete
- **Pruning** — outdated content that misled

## Step 3: Propose changes

Summarize what you heard, then propose specific edits. Format:

> **Proposed changes to `skills/<name>/SKILL.md`** (and any references):
>
> 1. **Description** — add trigger phrase "…" (because: …)
> 2. **Boundaries** — add: never X (because: discovered this in session)
> 3. **New section "Y"** — describes the workflow that was missing
>
> Want me to apply these, revise, or add more?

For small edits, show the exact diff inline. For larger changes, summarize
first and apply section by section.

**Wait for explicit user approval before editing.** "yes" / "go ahead" /
similar. If the user revises, loop back to Step 2 or 3.

## Step 4: Apply (in-repo case)

Edit the source file(s) under `skills/<name>/`. Then:

```bash
git status                        # confirm only the intended files changed
git add skills/<name>/
git commit -m "skill(<name>): <one-line summary>"
agr upgrade <name>                # re-installs into all configured tools, refreshes agr.lock
git add agr.lock
git commit --amend --no-edit      # or commit separately; match the repo's style
```

**Do not push.** Stop after the commit and let the user push when ready.

### Commit message style

Use a conventional-commits-style scope:

```
skill(<name>): <imperative summary>
```

Examples:

```
skill(agr-cli): clarify upgrade vs sync for local paths
skill(agr-cli): add gotcha for same-repo siblings
skill(code-review): drop outdated linter pre-check
```

If the repo's commit style differs (check `git log --oneline -20`), match it.

### Why `agr upgrade` and not `agr sync`?

`agr sync` only installs **missing** deps — it does NOT re-copy a local-path
skill that's already installed. `agr upgrade <name>` re-copies it and
refreshes `agr.lock`. Use `agr upgrade`.

(Equivalent: `agr add ./skills/<name> --overwrite`. Pick `upgrade` for
consistency — it's the same verb used to refresh remote skills.)

## Step 5: Apply (remote case)

If the skill is a remote dep, the change cannot be applied directly. Ask
the user which path they want:

### Option A — File an issue upstream via `gh`

Best when the change benefits everyone (a real bug or universal improvement
in someone else's published skill).

Resolve the upstream repo from the handle:

- `anthropics/skills/pdf` → `--repo anthropics/skills`
- `user/myrepo/skill` → `--repo user/myrepo`

Confirm the title and body with the user, then:

```bash
gh issue create \
  --repo <owner>/<repo> \
  --title "[<skill-name>] <short summary>" \
  --body "$(cat <<'EOF'
## What I observed

<concrete scenario from the session>

## Suggested change

<proposed wording or workflow>

## Why

<reasoning>
EOF
)"
```

`gh issue create` posts publicly — treat it the same as any other shared-
state action. **Always confirm before running.**

If the user has push access and a local clone, also offer to open a PR
instead of (or alongside) the issue.

### Option B — Fork to in-repo

Best when the change is project-specific or unlikely to be accepted
upstream. Copies the skill into `skills/<name>/` so future retros work the
in-repo way.

Suggested flow:

```bash
# 1. Find the upstream commit (agr.lock has it)
agr list

# 2. Sparse-checkout or full clone, then copy the folder:
mkdir -p skills
cp -r /tmp/upstream-clone/<skill-folder> skills/<name>

# 3. Swap the dep
agr remove anthropics/skills/<name>
agr add ./skills/<name>
```

Tell the user this **forks** the skill — they're now responsible for
keeping it current with upstream. Then continue from Step 3 with the
in-repo flow.

### Both A and B

Offer Option A first when the change is generally useful. Offer Option B
when upstream is unlikely to accept, or when the user wants the change
*now* without waiting on upstream.

## Step 6: Verify

After re-installing (in-repo case):

```bash
agr list                                          # status should be `installed`
diff skills/<name>/SKILL.md .claude/skills/<name>/SKILL.md   # should be empty
```

For remote case (issue filed): confirm the issue URL with the user.

Tell the user what's done and what's pending (commit done, push pending; or
issue filed, awaiting response).

## Boundaries

- **Don't edit a skill without explicit user approval of the proposed
  changes.** Skills are user-owned content — never silently revise.
- **Don't push.** Commit only; the user pushes when ready.
- **Don't open issues or PRs without confirming the title and body** with
  the user first. `gh issue create` is publicly visible — treat it as
  shared-state.
- **Don't edit `agr.lock` by hand** — `agr upgrade` regenerates it.
- **Don't broaden the scope of the edit** beyond what was discussed. If the
  user asked to fix one gotcha, don't also restructure the file.
- **Don't write a skill from scratch** — that's a separate workflow.

## See also

- `anthropics/skills/skill-creator` — canonical greenfield skill authoring
  (install with `agr add anthropics/skills/skill-creator` if needed)
