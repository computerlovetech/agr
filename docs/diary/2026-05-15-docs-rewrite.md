# Diary: drastically simplify agr docs

A total remake of the agr docs. The old docs were bloated (5,944 lines across
16 pages) and didn't make it obvious what functionality matters. The goal of
this task was to find the right scope, design a smaller IA, and rewrite from
scratch.

## Step 1: brainstorm the scope and rewrite the three pages

**Author:** main

### Prompt Context

**Verbatim prompt:** `❯ I'm looking to drastically simplify docs for agr. Like a total remake. They are way too bloated. However, I also feel like it is hard to know what functionality to prioritize.`

**Interpretation:** Two problems entangled: the docs themselves are too long
and too sprawling, *and* the user wasn't sure what to keep. They wanted a
brainstorm that resolved the prioritization question first, then a rewrite.

**Inferred intent:** Land on a sharp positioning for agr that doubles as a
filter for what belongs in the docs. Use that filter to cut hard and rebuild
small.

### What I did

Ran the `/brainstorm` skill. Through a series of single-question turns, the
shape came out:

- Both "too many pages" and "each page too verbose" were the pain.
- Landing page should pitch *and* quickstart.
- Primary audience: the CLI user installing skills — not skill authors, not
  ralph users.
- Ralphs are confusing for newcomers; hide them and mark experimental.
- Target: **3 pages, hard cap**. Add more only when real need shows up.

The user's key reframe: **agr is to AI agent tooling what `uv`/`pip` is to
Python.** `agr.toml` is the manifest, the per-tool skill dirs (`.claude/skills/`,
`.cursor/skills/`, …) are the `.venv` — built artifacts that belong in
`.gitignore`. `agr sync` rebuilds them. Multi-tool, open, an alternative to
vendor plugin marketplaces.

That sharpened the scope: docs cover installing and managing skills, **not**
authoring skills, **not** using skills inside an agent.

The three pages:

1. `/docs/index.md` — Get started: pitch + 5-minute quickstart (`uv tool install agr` → `init` → `add` → `sync`).
2. `/docs/managing.md` — Manage your skill environment: `agr.toml`, lockfile, sync, gitignore stance, multi-tool, four core commands.
3. `/docs/reference.md` — CLI reference: every command and flag.

Before drafting page 3 I ran `uv run agr --help` and per-subcommand help to
get the real CLI surface (`init`, `add`, `remove`, `sync`, `upgrade`, `run`,
`list`, `config` with 8 subcommands, plus `agrx`). The original design had
assumed a smaller CLI; surfacing the real one to the user produced a "page 3
is fine, write it" decision.

After the rewrites I deleted the 13 obsolete doc pages and the
`/docs/contributing/` directory:

```bash
cd /Users/kasperjunge/Code/agr/docs && rm -rf agrx.md changelog.md \
  concepts.md configuration.md contributing creating-ralphs.md creating.md \
  llms-full.txt llms.txt ralphs.md sdk.md skills.md teams.md tools.md \
  troubleshooting.md tutorial.md
```

Updated `/mkdocs.yml` nav to just the three new pages, and fixed stale links
in `/docs/404.md` that still pointed to `tutorial.md` and `troubleshooting.md`.

Ran `uv run mkdocs serve` to preview. Initial attempt failed with
`OSError: [Errno 48] Address already in use` because a background mkdocs from
earlier in the session was still bound to port 8000. Killed it and restarted
cleanly.

### Why

The brainstorm's job was to find a scope that *forces* prioritization —
"three pages, hard cap" is a much stronger constraint than "make it shorter."
The `.venv`/`pyproject.toml` analogy reframed agr as a package manager rather
than a marketplace or skill toolkit, which told us what to cut: authoring,
discovery catalogs, agrx tutorials, ralphs, SDK, teams, troubleshooting. Each
of those is real but none of them is the load-bearing story.

### What worked

- One-question-at-a-time brainstorming reached a sharp design in ~6 turns.
- The `.venv` analogy is the single most useful framing device in the new
  docs — it lets readers map agr onto something they already know.
- Reading the actual CLI before drafting page 3 prevented invention of
  fictional flags. Worth doing before any reference doc.
- Hard caps (page count, line targets per page) made cuts feel inevitable
  rather than arbitrary.

### What didn't work

- The first mkdocs serve attempt failed:

  ```
  OSError: [Errno 48] Address already in use
  ```

  Caused by a stale background mkdocs server from an earlier exploratory
  call. Fix: `pkill -f "mkdocs serve"` then restart.

- The brainstorm design assumed a smaller CLI than reality. The real `agr`
  has `upgrade`, `run`, and an 8-subcommand `config` that the original design
  hadn't budgeted for. Surfacing the gap to the user before drafting was the
  right move — bluffing flag tables would have produced lies.

### What I learned

- agr's `init` has an instruction-syncing feature
  (`--sync-instructions`/`--canonical-instructions` writing
  `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`) that the old docs barely surfaced.
  Now mentioned in `/docs/reference.md`.
- The `--global` (`-g`) flag is consistent across most subcommands, so the
  reference factors it out into a "Global flags" section at the top instead
  of repeating it in every table.
- mkdocs serve binds eagerly and doesn't release the port between dev
  sessions; long-lived sessions need to kill prior servers explicitly.

### What was tricky

- Deciding what *not* to include on page 1. The pitch wants to mention
  multi-tool support, the open-marketplace angle, and the `.venv` analogy —
  but cramming all three into the hero made it noisy. Resolution: two
  sentences in the hero (analogy + open alternative line), three crisp
  bullets under "Why agr."
- Diary placement. `docs/diary/` is the skill's convention, but `docs/` is
  the mkdocs source dir, so anything dropped there gets built and served.
  Resolved by adding `exclude_docs: diary/**` to `/mkdocs.yml`.

### What warrants review

- **Tone & accuracy on `/docs/index.md`** — does the "open alternative to
  vendor plugin marketplaces" framing read fairly or as a swipe at Anthropic?
- **`/docs/managing.md`'s `.gitignore` block** — currently lists
  `.claude/skills/`, `.cursor/skills/`, `.codex/skills/`, `.agents/skills/`.
  Confirm this matches what `agr init` actually writes.
- **`/docs/reference.md` flag tables** — built from the live `--help` output
  on 2026-05-15. If the CLI evolves before docs are next reviewed, these
  will drift.
- **Stale assets** — `/docs/assets/`, `/docs/images/`, `/docs/overrides/`,
  `/docs/includes/`, `/website/`, `/_site/`, `/site/` were not touched.
  Worth a pass to see if any are now orphaned by the doc deletions.

### Future work

- Decide the fate of `/docs/llms-full.txt` and `/docs/llms.txt` if you want
  to keep an LLM discovery file. They were deleted in this pass; regenerate
  if needed.
- A "What's new" or release notes surface eventually — for now the
  `/CHANGELOG.md` at the repo root carries that load.
- If `agr run` and `agr config` get heavier use, page 2 may want a short
  "running and configuring" subsection so they're discoverable from the
  primary flow rather than only via the reference.
- Add a Vercel / GitHub Pages preview before the next merge so the new IA
  can be reviewed in browser without local mkdocs.
