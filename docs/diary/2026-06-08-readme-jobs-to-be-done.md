# Diary: Simplify the README around the top jobs to be done

Reshape `README.md` so a newcomer immediately understands what agr is, who it's
for, and what to do. Center it on the handful of core jobs (install from a repo,
use local skills, share a team environment, upgrade, run once) and make the
team / package-manager-for-skills framing explicit.

## Step 1: Rewrite README around five jobs to be done

**Author:** main

### Prompt Context

**Verbatim prompt:** "Okay so we need to simplify the README file. This is
because we want to center it around the top five jobs to be done and how to get
started with AGR and make it very clear for people how to use it and how it
works with the handles and the whole installing from repos and how it works with
the local skills and stuff like that. Please please give it a shot. It should be
very easy for people to understand it and know that they need AGR and it should
feel simple and it should feel like they actually know what to do. Just really
crisp."

**Interpretation:** Restructure the README so the value proposition and usage
are obvious, organized around ~5 concrete jobs, with handles, repo installs, and
local skills all clearly explained.

**Inferred intent:** Convert the README from a feature list into a "here's what
you can do and how" document that converts a curious reader into a confident
user.

### What I did

Before writing, I confirmed the real capabilities so the doc wouldn't lie:
read `/agr/handle.py` (`parse_handle`, ~line 253) to confirm the handle forms
(`owner/repo/skill`, shorter remote forms, and local `./path`), and read
`/docs/index.md` and `/docs/managing.md` to align messaging and confirm local
skills use a `path = "./…"` entry in `agr.toml`.

Then I rewrote `/README.md` around five jobs under the banner "Five things.
That's the whole tool.":

1. Install a skill from a Git repo — handles explained as "just a path into
   GitHub", plus the per-tool invoke table.
2. Use your own local skills — `agr add ./skills/my-internal-skill` (this job
   was absent from the old README).
3. Share one skill environment with your team — gitignore the tool dirs, commit
   `agr.toml` + `agr.lock`, `agr sync`. The example manifest now shows both a
   remote `handle` and a local `path`.
4. Keep skills up to date — `agr upgrade`.
5. Try a skill without installing — `agrx`, promoted from a table footnote to a
   first-class job.

Kept the header, badges, demo SVG, full command table, community-skills block,
and footer.

### Why

The old README mixed framing ("Built for teams", "Keep skills up to date",
"Example skills") in a way that read as a feature tour rather than a task guide.
Organizing by job answers the reader's real question — "what do I do with this?"
— and surfaces capabilities (local skills, `agrx`) that were buried.

### What worked

Reading `handle.py` and the docs first meant every command and handle example in
the rewrite is accurate rather than guessed — e.g. local skills really are a
`path` entry, and the `owner/repo/skill` → GitHub-directory mapping is exactly
how `parse_handle` documents it.

### What didn't work

Nothing broke — this is a docs-only change, no build or test failures. The first
draft was structurally complete; subsequent edits were additive framing, not
fixes.

### What I learned

agr's local-skill support (`agr add ./path`, `path = "./…"` in `agr.toml`) is a
genuine first-class feature that the previous README never mentioned — easy to
miss because it's only visible in `docs/managing.md` and the handle parser.

### What was tricky

Balancing "crisp" against the user's later asks to *add* the package-manager
rationale and the versioning/distribution benefits — more words, but the request
was explicitly to make the "why" clearer. I kept the additions as a tight bullet
list so the document still scans quickly rather than turning into prose walls.

### What warrants review

Read `/README.md` top to bottom as a new user would and check: (1) the five jobs
are genuinely distinct and ordered by likelihood of use; (2) the handle
explanation lands before any handle is used; (3) the command table matches the
real CLI surface. Cross-check the command table against `/docs/reference.md` if
in doubt.

### Future work

`docs/index.md` and `docs/managing.md` could adopt the same jobs-to-be-done
framing for consistency with the README, but that's out of scope for this change.

## Step 2: Add team + package-manager framing and the "why version/distribute" rationale

**Author:** main

### Prompt Context

**Verbatim prompt:** "Also make sure to make it clear that this is for teams who
want to manage their skills and agent skills in a great way, just like software
packages like npm, PyPI, UV, and stuff like that. I really like the current
thing right now. The current tech is really great." — followed by: "Also explain
why it is nice to version, to distribute to, all of that stuff. Also make sure to
make it clear why it's nice to do this and use this tool as a team."

**Interpretation:** Add an explicit "for teams, like npm/PyPI/uv" positioning to
the header and intro, then expand on the concrete benefits of versioning,
distribution, and team use.

**Inferred intent:** Make sure the reader doesn't just see *how* to use agr but
understands *why* a team would want package-manager discipline for their skills.

### What I did

Edited the header subtitle of `/README.md` to lead with the team +
npm/PyPI/uv analogy. Opened the "Why agr" section with "agr is for **teams**…"
and the same analogy. Then added a four-bullet benefits list: **Version & pin**
(`agr.lock`, intentional upgrades), **Distribute effortlessly** (publish = push
to a repo, install = `agr add`), **One source of truth for the team** (skills in
PRs, versioned in Git, consistent agent behavior), and **Onboard in one command**
(`agr sync` on clone).

### Why

The reorganized README explained *what* and *how* well, but the user wanted the
*why-as-a-team* made explicit — the payoff of treating skills like packages
(reproducibility, no drift, easy onboarding) wasn't spelled out.

### What worked

Framing the benefits as a direct parallel to "wins you already get from a package
manager for code" lets readers transfer their existing npm/uv intuition straight
onto agr, which is exactly the analogy the user asked for.

### What didn't work

Nothing failed — purely additive edits to prose.

### What I learned

The user values the package-manager mental model strongly enough to want it in
two places (header + intro); positioning, not just instructions, is part of what
makes this README "feel simple."

### What was tricky

Adding rationale without bloating the doc. Resolved by keeping each benefit to a
one-line bold lead + one sentence, so the section adds substance while still
scanning fast.

### What warrants review

Check that the header subtitle and the "Why agr" opener don't feel redundant
reading them back-to-back — they intentionally repeat the npm/PyPI/uv analogy,
which should reinforce rather than annoy. Confirm the benefits list claims are
all true (e.g. `agr.lock` really pins versions — yes, per `docs/managing.md`).

### Future work

None beyond the Step 1 follow-up (aligning the docs site pages with the same
framing).
