# Diary: Replace Antigravity tool support with Pi (pi.dev)

Drop the Antigravity integration from agr and add support for Pi
(https://pi.dev), a minimal open-source terminal coding agent. agr models each
supported coding tool as a `ToolConfig` in `/agr/tool.py`; the work threads a
new tool through the registry, migrations, docs, the bundled `agr-cli` skill,
and the test suite.

## Step 1: Research and plan the swap

**Author:** main

### Prompt Context

**Verbatim prompt:** "I want to remove support for Antigravity and add support for Pi (pi.dev). Please research how to add support for Pi"
**Interpretation:** Remove every Antigravity touchpoint and add a fully-wired Pi tool, after researching how Pi discovers skills and runs from the CLI.
**Inferred intent:** A clean tool swap that matches Pi's real on-disk and CLI behavior, with tests and docs kept consistent, not a half-migration.

### What I did
Mapped the Antigravity footprint with grep across `/agr`, `/tests`, `/docs`, and
`/skills`, then read the central registry `/agr/tool.py`, the migration logic in
`/agr/commands/migrations.py`, `/agr/detect.py`, and `/agr/instructions.py`.
Researched Pi via its docs and the `earendil-works/pi` repo: project skills live
in `.pi/skills/` (with `.agents/skills/` as an alias), global skills in
`~/.pi/agent/skills/`, instructions come from `AGENTS.md` (also `CLAUDE.md`), and
the `pi` CLI supports one-shot `-p/--print`, auto-approve `-a/--approve`, and
resume `--continue`. Wrote a plan file and confirmed two genuine decisions with
the user.

### Why
Antigravity is wired through many layers; a registry-only edit would leave
dangling references in migrations, detection, docs, and ~10 test files. The
research pinned down the exact paths and flags so the `ToolConfig` matches
reality instead of guesses.

### What worked
The `ToolConfig` dataclass already exposes every field Pi needs (CLI flags,
`global_config_dir` for asymmetric global paths, `detection_signals`,
`instruction_file`), so Pi is purely declarative — no new machinery.

### What didn't work
First attempt to dispatch an Explore subagent for the codebase sweep was
rejected by the user mid-call; I fell back to running the grep/read sweep
directly, which was fine.

### What I learned
Pi deliberately reads the shared `.agents/skills/` path that Codex also uses, so
Pi is an "alias-compatible" tool rather than a fully isolated one — that shapes
the detection and duplication tradeoffs below.

### What was tricky
The install-path decision. Pi reads both `.pi/skills/` and `.agents/skills/`, so
either works functionally. The user initially leaned toward `.agents` (shared,
no duplication) then chose the Pi-native `.pi/skills/` + `~/.pi/agent/skills/`
layout, accepting that a user running both Codex and Pi gets the skill written
to both trees.

### What warrants review
`/agr/tool.py` — the `PI` `ToolConfig`: confirm `config_dir=".pi"`,
`global_config_dir=".pi/agent"`, flags `-p`/`-a`/`--continue`,
`detection_signals=(".pi", ".agents")`, and `instruction_file="AGENTS.md"` match
Pi's documented behavior.

### Future work
Reconsider whether Pi should detect on `.pi` only (see Step 3's review finding
about `.agents/` auto-adding Pi to Codex-only repos).

## Step 2: Implement the swap across code, docs, and tests

**Author:** main

### Prompt Context

**Verbatim prompt:** (plan approved via ExitPlanMode) — implement the approved plan.
**Interpretation:** Apply the registry change, delete Antigravity migrations, rewrite docs/skill references, and convert the test suite from Antigravity to Pi.
**Inferred intent:** Land a green, internally-consistent change with no Antigravity residue in shipping code or docs.

### What I did
Replaced the `ANTIGRAVITY` config with `PI` in `/agr/tool.py` and the
`_ALL_TOOLS` tuple. Removed the Antigravity import and both Antigravity
migration blocks from `/agr/commands/migrations.py`. Fixed the
`--canonical-instructions` help text in `/agr/main.py`. Updated `/README.md`,
`/docs/managing.md`, `/docs/reference.md`, and every `agr-cli` skill reference
(`SKILL.md`, `setup.md`, `configuration.md`, `running-skills.md`, `syncing.md`)
to list Pi and drop `GEMINI.md`. Added a CHANGELOG entry. On the test side:
deleted `/tests/cli/agr/test_antigravity.py`, added
`/tests/cli/agr/test_pi.py`, and updated `test_tool.py`, `test_detect.py`,
`test_init.py`, `test_run.py`, `test_tool_flag.py`, `test_sync.py`,
`test_instructions.py`, `test_migrations.py`, and `test_config.py`.

### Why
Every layer that enumerated tools or instruction files needed Pi in and
Antigravity out to stay consistent — the registry drives detection, sync,
migrations, CLI help, and the docs tests.

### What worked
After the edits, `uv run pytest` surfaced exactly the expected fallout in one
pass, and `ruff`/`ty` were clean (ruff reformatted a few files).

### What didn't work
One test failed because `GEMINI.md` is no longer a derived valid instruction
file:

```
agr.exceptions.ConfigError: canonical_instructions must be one of: 'AGENTS.md', 'CLAUDE.md'
FAILED tests/test_config.py::TestAgrConfig::test_load_canonical_instructions_gemini
```

I updated that test to use `AGENTS.md` (later refined in Step 3 into a
coercion test). Two run-time tests that asserted "tool has no CLI configured"
no longer had a CLI-less tool to exercise (Antigravity was the only one), so I
removed one and converted the agrx one into a positive `pi` CLI-not-found check.

### What I learned
`INSTRUCTION_FILES` and the canonical-instructions validator are derived
dynamically from the live `TOOLS` registry, so removing a tool silently changes
which instruction filenames are accepted — a non-obvious ripple.

### What was tricky
Distinguishing Antigravity-specific tests from generic ones. The `GEMINI.md`
fixtures in `/tests/unit/test_instructions.py` only use that filename as
arbitrary test data for the generic file-sync helper, so they stay valid and
were left untouched, whereas the `test_config.py` one was a real validity
assertion that had to change.

### What warrants review
`/agr/commands/migrations.py` — confirm dropping the Antigravity `.agent/`→
`.gemini/` and global subdir migrations is safe (skills already in a user's
`.gemini/` just go unmanaged). `/tests/cli/agr/test_pi.py` — confirm the
asserted `.pi/skills/` paths.

### Future work
The `cli_command is None` branches in `/agr/runner.py` are now unreachable since
every tool has a CLI — candidate for deletion or a synthetic unit test.

## Step 3: Code review and follow-up fixes

**Author:** main (review dispatched to two general-purpose sub-agents)

### Prompt Context

**Verbatim prompt:** "/code-review ... dispatch two subagents to carefully review the code changes ... look at both architecture and implementation."
**Interpretation:** Run a competitive two-agent review over the full diff and act on the genuine findings.
**Inferred intent:** Catch consistency gaps and breaking changes the author missed before shipping.

### What I did
Dispatched two competing review sub-agents over the working-tree diff, then
verified each finding against the source. Acted on three substantive ones:
fixed `/README.md:83` (the "Invoke with" column showed `pi` instead of the
skill prefix `/pdf`); swept ~36 stale Antigravity/`GEMINI.md` references out of
the shipping SEO template `/docs/overrides/main.html` (mkdocs `custom_dir`),
including repurposing the false "Why can't I use agrx with Antigravity?" FAQ;
and added a legacy coercion in `/agr/config.py` mapping
`canonical_instructions = "GEMINI.md"` to `AGENTS.md` on load, with a regression
test and a CHANGELOG "Changed" note.

### Why
The reviewers correctly flagged that `main.html` ships with the site and was
entirely missed, that the README column documents invocation syntax (not the CLI
name), and that existing `agr.toml` files pinned to `GEMINI.md` would otherwise
hard-error on every command with no upgrade path.

### What worked
The two-agent setup produced complementary findings: one focused on the missed
`main.html` and the breaking config validation, the other on the README
invocation column. Verifying before acting filtered out the carried-over
non-issues.

### What didn't work
A first repo-wide grep missed two lowercase `antigravity` strings in
`main.html` (lines 564, 1025) because they sat in different phrasing than the
title-case sweep; a follow-up grep caught them. No command errors.

### What I learned
`/docs/overrides/main.html` is a hand-maintained JSON-LD/SEO file under mkdocs
`custom_dir` — easy to forget because it isn't Markdown and isn't surfaced by
the prose-doc tests. It contains 24 JSON-LD blocks that must stay valid JSON
after edits.

### What was tricky
Editing JSON-LD by hand: a botched comma or quote silently breaks a block, so I
validated all 24 blocks parse with a small Python json.loads check after the
sweep rather than trusting the edits.

### What warrants review
`/agr/config.py` — the `GEMINI.md`→`AGENTS.md` coercion on load (silent, with a
comment). `/docs/overrides/main.html` — the Pi tool card, the rewritten FAQ, and
the instruction-file FAQs.

### Future work
Two acknowledged-but-deferred items: delete or unit-test the now-unreachable
`cli_command is None` branches in `/agr/runner.py`; and reconsider dropping
`.agents` from Pi's `detection_signals` so a Codex-only repo doesn't auto-add
`pi`.

## Final verification

`uv run pytest` — 1304 passed, 6 skipped. `uv run ruff check .` and
`uv run ty check` — clean. `uv run mkdocs build --strict` — succeeds. No
Antigravity/Gemini references remain outside intentional CHANGELOG history, the
legacy-coercion code comment, and the regression-test docstring.
