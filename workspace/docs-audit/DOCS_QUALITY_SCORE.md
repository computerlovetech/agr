# Documentation Quality Score

**Project:** agr — A package manager for AI agent skills
**Audited:** 2026-03-31
**Overall Grade:** B+

## Grades Summary

| Stage | Grade | One-line summary |
|-------|-------|------------------|
| Awareness | A | Clear tagline, strong value prop, immediately understandable |
| Evaluation | B+ | Features and positioning are clear; maturity signals could be stronger |
| First Run | A | Excellent tutorial — 8 steps, copy-pasteable, real output examples |
| Core Workflows | A- | All jobs well-documented with examples; some redundancy between pages |
| Power User | B | Architecture docs are thorough; contributing recipes are thin |
| Agent Readability | B- | CLAUDE.md is a good map but uses `...` placeholders that waste agent context |

## Stage-by-stage findings

### 1. Awareness — A

**What works:**
- README opens with a centered tagline: "A package manager for AI agent skills." Immediately clear.
- The "What are skills?" section with a concrete SKILL.md example is brilliant — shows the concept in action before explaining the tool.
- Docs site landing page mirrors this clarity. Hero text "agr — Skills for AI Agents" communicates value in under 5 seconds.
- Tool invocation table (Claude Code, Cursor, Codex, etc.) instantly shows breadth of support.

**Gaps:**
- No hero image, terminal recording, or animated demo. A 15-second asciinema showing `agr add` → skill invocation would be high-impact.
- GitHub README falls below the fold due to file listing — the tagline in the "About" sidebar is the only above-fold signal.

**Recommendations:**
- Add an asciinema or SVG terminal recording to the README showing the core flow.
- Consider a shorter GitHub "About" description that frontloads the key differentiator (cross-tool).

### 2. Evaluation — B+

**What works:**
- Feature list is implicit but effective — the README sections (team sync, agrx, SDK, create & share) naturally enumerate capabilities.
- Example skills section shows real, useful skills with install commands — lets evaluators judge quality.
- Badge row (PyPI, MIT, Docs) provides quick trust signals.
- 420 stars, 36 forks, v0.8.0 — healthy signals of active development.

**Gaps:**
- No explicit "Why agr?" or comparison section. A user evaluating agr vs. manually managing skills has to infer the value.
- Project maturity is unclear — is this alpha, beta, stable? The changelog shows rapid iteration but no stability statement.
- No "Who uses this?" or testimonials section.

**Recommendations:**
- Add a "Why a package manager?" one-paragraph section to the README (the docs site has this in concepts.md but the README doesn't).
- Add a stability/maturity badge or statement (e.g., "Production-ready for Claude Code and Cursor, beta for other tools").

### 3. First Run — A

**What works:**
- Tutorial (`tutorial.md`) is outstanding: 8 clear steps, ~10 minutes, with real command output shown.
- Prerequisites are explicit: Python 3.10+, git, at least one AI tool.
- Handle format cheat sheet in the tutorial prevents the most common confusion point.
- `agr add` auto-creates `agr.toml` and detects tools — zero config needed for the happy path.
- Three install methods (uv, pipx, pip) with uv recommended.

**Gaps:**
- No "verify your installation" step (e.g., `agr --version` with expected output).
- The tutorial doesn't show what happens when you invoke the skill after installing — the user installs `code-review` but never sees it in action.

**Recommendations:**
- Add a verification step after install: `agr --version` → expected output.
- After `agr add`, show a brief example of invoking the skill in Claude Code or Cursor so the user sees the full loop.

### 4. Core Workflows — A-

The primary jobs-to-be-done for agr:

**Job 1: Install a skill** — Excellent coverage. `agr add` is documented in README, tutorial, reference, and concepts. Multiple handle formats explained with examples.

**Job 2: Sync skills across a team** — Well-documented in `teams.md` with GitHub Actions example, what to commit vs. gitignore, and multi-tool teams.

**Job 3: Try a skill without installing** — `agrx.md` is clear and concise. Comparison table (agrx vs agr add) is very helpful.

**Job 4: Create and publish a skill** — `creating.md` is thorough with real examples, frontmatter spec, and common pitfalls.

**Job 5: Use the SDK programmatically** — `sdk.md` covers loading, discovery, and caching with code examples.

**What works:**
- Each job has a dedicated page with examples.
- Cross-referencing between pages is good.
- Reference page provides a complete command table with all flags.
- Troubleshooting page (1000+ lines) covers nearly every error.

**Gaps:**
- Some redundancy: the landing page repeats the example skills list that's on the skills directory page. The reference page repeats agr.toml format from configuration.md.
- Troubleshooting page at 1000+ lines is a wall — hard to navigate without search.
- No "recipes" or "cookbook" page for common multi-step workflows (e.g., "migrate from manual skill management to agr").

**Recommendations:**
- Trim the landing page's "Example skills" section to 3-4 highlights with a link to the full directory.
- Split troubleshooting into sub-pages by category (install, config, sync, etc.) or add a prominent search CTA at the top.

### 5. Power User — B

**What works:**
- Architecture doc (`contributing/architecture.md`) is thorough: project structure, key types, core workflows, migrations, testing patterns. A contributor can understand the codebase without reading all the source.
- Contributing quick reference maps files to modules clearly.
- Configuration reference (`configuration.md`) covers all settings with a fully annotated example.
- Changelog tracks changes by version with links to relevant docs.

**Gaps:**
- Contributing "recipes" (add new tool, add CLI command, add config key) are one-liners — they tell you *what* to do but not *how*. A contributor adding a new tool would still need to read significant source code.
- No CONTRIBUTING.md at repo root — contributors must find `docs/docs/contributing/`.
- No documented extension points or plugin system.
- No examples of real-world advanced usage patterns (e.g., monorepo setup, CI with multiple tool targets).

**Recommendations:**
- Expand the contributing recipes with step-by-step instructions and file diffs.
- Add a root-level CONTRIBUTING.md that points to the full guide (GitHub surfaces this in the "Contributing" sidebar).
- Document advanced patterns: monorepos, CI matrices, custom source servers.

### 6. Agent Readability — B-

**What works:**
- CLAUDE.md exists and functions as a map: points to architecture, commands, conventions, and boundaries.
- Progressive disclosure: short entry point with `docs/docs/contributing/` as the deep reference.
- Skills are stored in `skills/` and the CLAUDE.md references them.
- External docs links for all supported tools are listed.

**Gaps:**
- CLAUDE.md uses `...` as placeholder content in multiple sections (Code Style, Ask First, Never Do, Security). These waste agent context tokens while providing zero information. Either fill them in or remove the headings entirely.
- The `# Docs` section at the bottom is just a raw URL dump with no context about what each link contains or when an agent should consult it.
- No `.cursorrules`, `AGENTS.md`, or `copilot-instructions.md` — agents using other tools have no entry point. (Though agr is primarily developed with Claude Code, cross-tool agent docs would be consistent with agr's own cross-tool philosophy.)
- The boundaries section ("Always Do", "Ask First", "Never Do") is a good pattern but the empty sections undermine it.

**Recommendations:**
- Remove the `...` placeholder sections from CLAUDE.md or fill them with real content. Empty sections are worse than no sections.
- Annotate the docs links: "For skill format spec, see..." rather than a bare URL list.
- Consider adding a `.cursorrules` or `AGENTS.md` for cross-tool agent consistency.

## Visual Assessment

Screenshots saved to `workspace/docs-audit/screenshots/`.

### Docs Site (landing-page.png)
- **Above-the-fold:** Strong. Dark theme, clear h1 "agr — Skills for AI Agents", tagline visible immediately. Navigation tabs (Home, Getting Started, Guides, Building Skills, Contributing, Reference) are clean and scannable.
- **Code blocks:** Dark background with syntax highlighting and copy buttons. Readable.
- **Layout:** MkDocs Material with three-column layout (sidebar, content, TOC). Works well.

### Tutorial Page (tutorial.png)
- **Structure:** Left sidebar shows "Getting Started" with sub-nav. Right sidebar shows step-by-step TOC. TLDR admonition box at top is effective.
- **Navigation:** Previous/Next footer links present. Breadcrumbs visible.

### Mobile (mobile-landing.png)
- **Responsive:** Layout adapts cleanly to 375px. No horizontal overflow. Navigation collapses to hamburger. Code blocks fit within viewport. Tagline is readable.

### GitHub README (github-readme.png)
- **Above-fold:** File listing dominates. README content is below the fold. "About" sidebar shows description and homepage link. 420 stars visible.
- **Badges:** PyPI, License, Docs badges render correctly.

### Overall Visual Quality
- Professional appearance, consistent dark theme
- No broken layouts, 404s, or visual issues detected
- Code blocks are consistently readable with copy functionality
- Mobile experience is solid

## Top Recommendations

### High impact
1. **Remove `...` placeholders from CLAUDE.md** — They waste agent context and signal incompleteness. Either fill in Code Style, Ask First, Never Do, and Security sections with real content, or remove the headings. This is the single highest-impact change for agent readability.
2. **Add a terminal recording to the README** — An asciinema or SVG showing `agr add` → skill invocation would dramatically improve the Awareness stage. First impressions matter, and a 15-second demo communicates more than paragraphs of text.
3. **Show the full loop in the tutorial** — After `agr add code-review`, show what happens when you invoke `/code-review` in Claude Code. The tutorial currently ends at installation without showing the payoff.

### Quick wins (< 30 min each)
1. **Add `agr --version` verification step to the tutorial** — One line of code, prevents "did it install?" confusion.
2. **Add a root CONTRIBUTING.md** that points to `docs/docs/contributing/` — GitHub surfaces this in the repo sidebar. 5 minutes.
3. **Annotate the docs URLs in CLAUDE.md** — Change the bare URL list under `# Docs` to labeled links with one-line descriptions of when to use each.

## Jobs-to-be-done Alignment

The primary jobs this tool serves:

1. **Install a skill from GitHub** — documentation coverage: **good** (README, tutorial, reference, concepts all cover this)
2. **Sync skills across a team** — documentation coverage: **good** (dedicated teams.md with CI/CD example)
3. **Try a skill without committing** — documentation coverage: **good** (agrx.md with comparison table)
4. **Create and publish a skill** — documentation coverage: **good** (creating.md with examples and pitfalls)
5. **Use agr as a Python library** — documentation coverage: **partial** (SDK basics covered, but no real-world integration examples)

## Docs Landscape

| Source | Role | Quality |
|--------|------|---------|
| `README.md` | First contact, overview, quick start | Excellent |
| Docs site (MkDocs Material) | Full documentation, 15 pages | Very good |
| `docs/docs/index.md` | Landing page / overview | Excellent |
| `docs/docs/tutorial.md` | Step-by-step getting started | Excellent |
| `docs/docs/concepts.md` | Core architecture concepts | Very good |
| `docs/docs/tools.md` | Supported tools reference | Very good |
| `docs/docs/skills.md` | Skill directory | Good |
| `docs/docs/teams.md` | Team sync & CI/CD | Very good |
| `docs/docs/configuration.md` | Config reference | Very good |
| `docs/docs/agrx.md` | Ephemeral runner guide | Very good |
| `docs/docs/creating.md` | Skill authoring guide | Very good |
| `docs/docs/sdk.md` | Python SDK reference | Good |
| `docs/docs/contributing/` | Contributor guide + architecture | Good |
| `docs/docs/reference.md` | CLI command reference | Very good |
| `docs/docs/troubleshooting.md` | Error Q&A (1000+ lines) | Good (too long) |
| `docs/docs/changelog.md` | Release notes | Good |
| `CLAUDE.md` | Agent instruction file | Adequate (placeholders) |
| `skills/` | Bundled skills (3 skills) | Present |
