---
name: docs-audit
description: >
  Audit a CLI project's documentation quality across the full user journey — from first
  discovery to power user. Evaluates README, user docs, contributor docs, agent docs, and
  skills. Uses playwright-cli to visually inspect rendered docs and assess navigation,
  layout, and discoverability. Produces a graded report (A-F) with actionable recommendations
  saved to workspace/docs-audit/. Use this skill whenever the user wants to evaluate their
  docs, check documentation quality, assess onboarding experience, review their README,
  or asks "how good are my docs?" — even if they only mention one part of the docs.
  Also use when someone asks about documentation strategy or improving developer experience.
---

# Docs Audit

Systematically evaluate a CLI project's documentation across the full user journey and
produce a graded quality report with actionable recommendations.

## Philosophy

Good documentation is not about volume — it's about whether someone can go from "what is
this?" to "I'm productive" with minimal friction. This audit evaluates docs the way a real
user experiences them: progressively, across stages of increasing commitment.

The audit also evaluates agent readability — because in an agent-first world, your docs are
read by AI agents as much as by humans. Docs that work well for agents (structured, progressive
disclosure, clear pointers) also tend to work well for humans.

## Before you start

1. **Ensure workspace/ exists.** If `workspace/` doesn't exist at the project root, tell
   the user to set it up first (the `setup-agent-workspace` skill can help) or create a
   minimal `workspace/docs-audit/` directory.

2. **Identify the docs landscape.** Before auditing, map out what exists:
   - README.md (at repo root)
   - Docs site (look for mkdocs.yml, docusaurus.config.js, docs/ directory, or similar)
   - Contributing guides (CONTRIBUTING.md, docs/contributing/)
   - Agent instruction files (CLAUDE.md, AGENTS.md, .cursorrules, etc.)
   - Skills (skills/ directory, .claude/skills/, etc.)
   - Changelog, migration guides, examples/

3. **Check scope.** By default, audit everything. If the user asked to focus on specific
   areas, only audit those. Mention what you're skipping.

## The user journey framework

Evaluate documentation across six stages. Every user passes through these stages, though
some move faster than others. The question at each stage is: "Does the documentation help
or hinder progress to the next stage?"

### Stage 1: Awareness — "What is this?"

What someone sees when they first encounter the project. Usually the README or a landing page.

**Evaluate:**
- Can you understand what the tool does in under 10 seconds?
- Is there a clear one-liner or tagline?
- Does it say who it's for and what problem it solves?
- Is there a visual or example that shows the tool in action?

**Visual check (playwright-cli):** If there's a docs site or landing page, open it and assess:
- Above-the-fold clarity — does the hero section communicate the value prop?
- Visual hierarchy — can you scan the page and understand the structure?
- Mobile responsiveness (resize to 375px width)

### Stage 2: Evaluation — "Is this for me?"

The user is interested but needs to decide if it's worth trying.

**Evaluate:**
- Are key features listed and easy to find?
- Is there a comparison or positioning against alternatives?
- Are the prerequisites/requirements clear?
- Can you tell what stage the project is in (alpha, stable, etc.)?
- Are there signs of active maintenance (recent commits, releases)?

### Stage 3: First run — "How do I get started?"

The most critical stage. The user has decided to try it — now they need to go from zero
to first success.

**Evaluate:**
- Is there a quickstart section? How many steps from install to first working command?
- Are install instructions complete and copy-pasteable?
- Does the quickstart show a real, useful example (not just `--help`)?
- Are common first-run errors addressed?
- Time-to-value: how many minutes from "I want to try this" to "I did something useful"?

**Visual check (playwright-cli):** If there's a docs site, navigate the getting-started flow:
- Is the quickstart findable from the homepage? How many clicks?
- Is the navigation clear? Can you find your way back?
- Are code blocks readable and copyable?

### Stage 4: Core workflows — "How do I do the main things?"

The user is using the tool regularly and needs to accomplish the primary jobs-to-be-done.

**Evaluate:**
- What are the 3-5 core jobs this tool is built for?
- Is each job well-documented with examples?
- Are the docs organized by task/job (good) or by feature/command (less good)?
- Is there a clear reference for all CLI commands and options?
- Are common patterns and recipes documented?

**Visual check (playwright-cli):** Navigate the docs structure:
- Is information architecture logical? Can you find things by intent?
- Does search work? (if applicable)
- Are there dead ends, 404s, or broken links?

### Stage 5: Power user — "How do I go deeper?"

The user is committed and wants to extend, customize, or contribute.

**Evaluate:**
- Is advanced configuration documented?
- Are extension points / plugin systems documented?
- Is there a contributing guide? Does it actually help you contribute?
- Is the architecture documented enough to understand the codebase?
- Are there examples of real-world advanced usage?

### Stage 6: Agent readability — "Can AI agents work with this?"

In an agent-first world, docs should be optimized for both human and agent consumption.

**Evaluate:**
- Is there a root instruction file (CLAUDE.md, AGENTS.md, etc.)?
- Does it use progressive disclosure (short entry point → deeper references)?
- Or is it a monolithic wall of text that wastes agent context?
- Are there skills that extend agent capabilities?
- Is the instruction file a map (good) or an encyclopedia (bad)?
- Would a new agent joining the project know where to start?

## Grading

Grade each stage A through F:

| Grade | Meaning |
|-------|---------|
| **A** | Excellent — actively helps the user succeed, few or no gaps |
| **B** | Good — covers the basics well, minor gaps or friction |
| **C** | Adequate — information exists but is hard to find or incomplete |
| **D** | Poor — significant gaps, confusing organization, or misleading |
| **F** | Missing or broken — the stage is essentially unsupported |

Also assign an **overall grade** (weighted: First Run and Core Workflows count double,
because that's where most users get stuck or leave).

## Running the audit

### Step 1: Map the docs landscape

Read the project structure and identify all documentation sources. List them.

### Step 2: Read and evaluate each stage

Work through stages 1-6 in order. For each stage:
- Read the relevant docs
- Take notes on what works and what doesn't
- Identify specific gaps and friction points

### Step 3: Visual assessment with playwright-cli

If the project has a docs site:

```bash
playwright-cli open <docs-url>
playwright-cli screenshot --filename=workspace/docs-audit/screenshots/landing-page.png
playwright-cli snapshot
```

Navigate key user flows:
- Homepage → Getting started (count clicks, assess clarity)
- Search for a common task (does it work?)
- Check mobile layout: `playwright-cli resize 375 812` then screenshot
- Check for broken links by navigating through the main sections
- Assess visual hierarchy, code block readability, navigation

Save screenshots to `workspace/docs-audit/screenshots/`.

For README-only projects (no docs site), render the README on GitHub using playwright-cli:
```bash
playwright-cli open https://github.com/<owner>/<repo>
playwright-cli screenshot --filename=workspace/docs-audit/screenshots/github-readme.png
```

### Step 4: Write the report

Save to `workspace/docs-audit/DOCS_QUALITY_SCORE.md` using the report template below.

### Step 5: Present findings

Give the user a summary:
- Overall grade and the biggest wins/gaps
- The top 3 most impactful improvements they could make
- Quick wins (things that take < 30 minutes to fix)

## Report template

```markdown
# Documentation Quality Score

**Project:** [name]
**Audited:** [date]
**Overall Grade:** [grade]

## Grades Summary

| Stage | Grade | One-line summary |
|-------|-------|------------------|
| Awareness | | |
| Evaluation | | |
| First Run | | |
| Core Workflows | | |
| Power User | | |
| Agent Readability | | |

## Stage-by-stage findings

### 1. Awareness — [Grade]

**What works:**
- ...

**Gaps:**
- ...

**Recommendations:**
- ...

[Repeat for each stage]

## Visual assessment

[Screenshots and observations from playwright-cli inspection]

## Top recommendations

### High impact
1. ...
2. ...
3. ...

### Quick wins (< 30 min each)
1. ...
2. ...
3. ...

## Jobs-to-be-done alignment

The primary jobs this tool serves:
1. [job] — documentation coverage: [good/partial/missing]
2. [job] — documentation coverage: [good/partial/missing]
3. [job] — documentation coverage: [good/partial/missing]

## Docs landscape

[List of all documentation sources found and their roles]
```

## Focusing on specific areas

If the user asks to focus on a specific area, only audit those stages. Adjust the report
accordingly, but always note which stages were skipped.

Examples:
- "Check my getting-started experience" → Stage 3 (First Run) only
- "How are my docs for contributors?" → Stage 5 (Power User) only
- "Is my README good?" → Stages 1-2 (Awareness + Evaluation)
- "Are my docs agent-ready?" → Stage 6 (Agent Readability) only

## Tips for a good audit

- **Be specific.** "The docs are unclear" is useless. "The install section on line 23 of
  README.md assumes macOS but doesn't mention Linux or Windows" is actionable.
- **Quote what you see.** When something is confusing, quote the actual text and explain
  why it's confusing.
- **Think like a newcomer.** You've read the whole project — the user's reader hasn't.
  What would confuse someone seeing this for the first time?
- **Credit what works.** Don't just list problems. Call out what's done well so the user
  knows what to protect.
- **Prioritize.** Not all issues are equal. A missing quickstart matters more than a typo
  in the advanced config docs.
