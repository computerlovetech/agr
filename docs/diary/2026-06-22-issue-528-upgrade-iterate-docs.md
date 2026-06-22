# Diary: Recommend `agr upgrade` for iterating on in-repo skills (#528 / PR #529)

The agr-cli skill steered users to `agr add ./path --overwrite` to re-sync a
locally-edited in-repo skill, when `agr upgrade <name>` is the purpose-built
command. Filed issue #528, fixed the docs in PR #529 (merged), then investigated
whether `--overwrite` is now redundant enough to deprecate.

## Step 1: Fix the iterate guidance

**Author:** main

### Prompt Context

**Verbatim prompt:** "Great, please solve that issue and make a pr that closes it: https://github.com/computerlovetech/agr/issues/528"
**Interpretation:** Implement the doc change proposed in issue #528 and open a PR that auto-closes it on merge.
**Inferred intent:** Make the agr-cli skill recommend the idiomatic, lock-aware re-sync command for in-repo skill iteration.

### What I did
Worked in a worktree (`.worktrees/docs-528-iterate-upgrade` off `origin/main`) per
the workspace rule against editing `main` directly. Edited two files in
`/skills/agr-cli/`: the `SKILL.md` "Iterate" note and `references/in-repo-skills.md`,
both now leading with `agr upgrade my-skill`, keeping `agr add --overwrite` as the
path-based escape hatch and noting `agr sync` won't pick up edits to an
already-installed skill. Ran `uv run mkdocs build --strict` (passed), committed with
`Closes #528`, pushed, opened PR #529.

### Why
`agr upgrade --help` documents "fresh copy for local" + refreshes `agr.lock`, making
it the canonical re-sync for an in-repo skill — shorter and lock-aware versus the
path-based `--overwrite`.

### What worked
`mkdocs build --strict` passed; PR #529 created clean and later merged. Worktree
cleanup afterward (`git worktree remove`, `git branch -d`) was tidy.

### What didn't work
`mkdocs build --strict` emitted a loud red mkdocs-material banner — but it was the
future-2.0 advisory notice, not a build error; the build still succeeded
("Documentation built"). Briefly looked like a failure.

### What I learned
The repo convention (its CLAUDE.md) requires `mkdocs build --strict` before doc
commits, and uses `uv run` for all Python. Commit-message convention is
`docs:/feat:/fix: explain X for users who want to Y`.

### What was tricky
Distinguishing the mkdocs-material advisory banner from an actual `--strict`
failure — the red formatting is alarming but benign.

### What warrants review
PR #529 is merged; nothing outstanding. The change is docs-only.

### Future work
The user raised whether `--overwrite` should be deprecated now — addressed in Step 2.

## Step 2: Assess whether `--overwrite` is now redundant

**Author:** main

### Prompt Context

**Verbatim prompt:** "it is merged now. i the --overwirte actually even nessecary now wher ethe upgrade feature is available? would it make sense to deprecate it?"
**Interpretation:** Determine from the code whether `agr add --overwrite` is still needed given `agr upgrade`, and advise on deprecation.
**Inferred intent:** Avoid redundant surface area if `upgrade` fully subsumes `--overwrite`.

### What I did
Read the implementation rather than guessing. `--overwrite` is a flag on `agr add`
(`agr/main.py`); without it, `agr/_install_common.py:110` raises "already exists …
Use --overwrite to replace." `agr upgrade` (`agr/commands/upgrade.py`) only operates
on deps already in `agr.toml` — `_match_handle_to_dep` raises "'X' is not in
agr.toml" otherwise — and force-reinstalls via the install pipeline.

### Why
The deprecation question hinges on whether the two commands' capabilities fully
overlap. They don't.

### What worked
The code made the division of labor unambiguous: `add` = register/replace,
`upgrade` = re-sync already-registered.

### What didn't work
No dead ends; the relevant code was small and clear.

### What I learned
`upgrade` cannot replace a destination dir when the dep isn't yet in `agr.toml`
(re-adding after removal, repointing a dep's source/path over a stale install, name
collisions). `--overwrite` is the only clobber path for those `add`-time cases.

### What was tricky
The overlap is real but partial — easy to over-conclude "redundant" without noticing
`upgrade`'s hard requirement of prior `agr.toml` membership.

### What warrants review
My recommendation: do NOT deprecate `--overwrite`; it's the clobber flag for the
register+install path. The only genuine redundancy was the docs steering people to
it for plain iteration, already fixed in PR #529. Optional follow-up: a small
docs/help note clarifying add-vs-upgrade roles. User to decide whether to file it.

### Future work
Possibly file a follow-up issue for a docs/help clarification of the
add-vs-upgrade division of labor (pending user's call).
