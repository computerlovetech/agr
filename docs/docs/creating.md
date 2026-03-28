---
title: "How to Create Custom AI Agent Skills — Write, Test, and Share SKILL.md Files"
description: Step-by-step guide to creating reusable AI agent skills — scaffold with agr init, write SKILL.md instructions with YAML frontmatter, test locally, and publish to GitHub for Claude Code, Cursor, Codex, and more.
keywords:
  - create AI agent skill
  - SKILL.md format
  - SKILL.md frontmatter
  - SKILL.md YAML
  - agr init scaffold
  - publish skill to GitHub
  - write AI agent instructions
  - skill testing
  - skill best practices
  - custom AI coding agent prompts
  - write custom rules for Cursor
  - Claude Code custom skills
  - Codex custom agents instructions
  - reusable AI agent prompts
  - how to write SKILL.md
  - share AI coding prompts GitHub
  - agent skill template
  - AI pair programming instructions
---

# How to Create Custom AI Agent Skills

!!! tldr
    Run `agr init my-skill`, edit `my-skill/SKILL.md` with your instructions,
    test with `agr add ./my-skill`, then push to GitHub so others can
    `agr add your-username/my-skill`.

Skills are folders of instructions that give AI agents new capabilities. This
guide helps you create, test, and share a skill with minimal ceremony.

**Prerequisites:** [agr installed](tutorial.md#step-1-install-agr), a project
with at least one [supported AI tool](tools.md)

**Key terms:** A **skill** is a directory containing a `SKILL.md` file with
YAML frontmatter (`name`, `description`) and markdown instructions for an AI
coding agent. A **handle** like `user/skill` or `user/repo/skill` identifies a
skill on GitHub. **agr.toml** is the manifest file that tracks your project's
skill dependencies — similar to `package.json` or `Cargo.toml`. **agr** installs
skills into tools like Claude Code, Cursor, Codex, OpenCode, Copilot, and
Antigravity. See [Core Concepts](concepts.md) for details.

## Scaffold a New Skill with `agr init`

```bash
agr init my-skill
```

```text
Created skill scaffold: my-skill
  Edit my-skill/SKILL.md to customize your skill
```

This creates `my-skill/SKILL.md` with a starter template:

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

If you want to keep the skill in your project, scaffold it then move it under
`./skills/`:

```bash
agr init my-skill
mv my-skill skills/
```

From there you can:

1. Edit the `description` and body in `skills/my-skill/SKILL.md`
2. Add the skill to your tool with `agr add ./skills/my-skill`
3. Add it to `agr.toml` for team sync (see below)

## SKILL.md Format

A skill requires YAML frontmatter with `name` and `description`:

```markdown
---
name: my-skill
description: Brief description of what this skill does and when to use it.
---

# My Skill

Instructions for the agent go here.
```

### Required Fields

| Field | Constraints |
|-------|-------------|
| `name` | 1–64 chars. Lowercase alphanumeric and hyphens only. Cannot start/end with a hyphen or contain consecutive hyphens (`--`). Must match directory name. |
| `description` | Max 1024 chars. Describes what the skill does and when to use it. |

### Optional Fields

| Field | Purpose |
|-------|---------|
| `license` | License name or reference to bundled file |
| `compatibility` | Environment requirements (tools, packages, network) |
| `metadata` | Key-value pairs (author, version, etc.) |

## Example: Complete Skill

```markdown
---
name: code-reviewer
description: Reviews code for bugs, security issues, and best practices. Use when reviewing pull requests or code changes.
license: MIT
metadata:
  author: your-username
  version: "1.0"
---

# Code Reviewer

You are a code review expert. When reviewing code:

1. Check for bugs and logic errors
2. Identify security vulnerabilities
3. Suggest performance improvements
4. Ensure code follows project conventions

Be specific and actionable in your feedback. Reference line numbers when possible.
```

## Add Scripts, References, and Templates Alongside SKILL.md

For complex skills, add supporting files alongside SKILL.md:

```text
my-skill/
├── SKILL.md
├── references/       # Domain knowledge the agent reads at runtime
│   └── style-guide.md
├── scripts/          # Executable code for deterministic tasks
│   └── validate.sh
└── assets/           # Templates, data files
    └── template.json
```

| What | Where | Why |
|------|-------|-----|
| Reference docs the agent reads at runtime | `references/` | Keeps SKILL.md focused on workflow |
| Scripts the agent should execute | `scripts/` | Reproducible results for mechanical tasks |
| Templates or data files | `assets/` | Reusable artifacts the agent fills in |

Reference them in your SKILL.md:

```markdown
Before generating code, read [the style guide](references/style-guide.md).

After making changes, run the validation script:
scripts/validate.sh
```

Keep your main SKILL.md under 500 lines. Put detailed reference material in the `references/` folder.

## Test Your Skill

The fastest way to iterate on a skill:

```bash
agr add ./skills/my-skill
```

```text
Added: ./skills/my-skill
  Installed to claude: .claude/skills/my-skill
```

Test it in your AI tool — invoke the skill and see if it works. Edit
`SKILL.md`, then reinstall:

```bash
agr add ./skills/my-skill --overwrite
```

```text
Added: ./skills/my-skill
  Installed to claude: .claude/skills/my-skill (overwritten)
```

Repeat until the skill works well.

**What to test:**

- **Happy path:** Does the skill do the right thing with a clear, simple request?
- **Edge cases:** What happens with empty input, large files, or ambiguous requests?
- **Boundaries:** Does the skill stay in scope, or does it try to do things you didn't intend?
- **Different tools:** If targeting multiple tools, test in each one — behavior can vary

## Add to agr.toml (Team Sync)

To share a skill with your team, add it to `agr.toml` as a local path
dependency:

```toml
dependencies = [
    {path = "./skills/my-skill", type = "skill"},
]
```

Teammates run:

```bash
agr sync
```

## Publish Your Skill to GitHub

Push your skill to GitHub. The recommended structure is a repo named `skills`
under your GitHub username — this lets people install with the short two-part
handle:

```text
your-username/skills/
├── my-skill/
│   └── SKILL.md
└── another-skill/
    └── SKILL.md
```

```bash
agr add your-username/my-skill
```

If your skills live in a differently named repo, users use the three-part
handle instead:

```bash
agr add your-username/my-repo/my-skill
```

## Writing Effective Instructions

The quality of your skill depends on how well you write the SKILL.md body. The
frontmatter tells tools *when* to use the skill; the body tells the agent *how*.

### Be specific about what to do

Vague instructions produce inconsistent results. Tell the agent exactly what
steps to follow.

**Weak:**

```markdown
# Code Reviewer

Review the code and suggest improvements.
```

**Strong:**

```markdown
# Code Reviewer

When reviewing code changes, follow these steps in order:

1. Read every changed file completely before commenting
2. Check for bugs: null references, off-by-one errors, race conditions
3. Check for security issues: injection, auth bypass, data exposure
4. Flag any function longer than 50 lines or any file longer than 500 lines
5. Verify error handling: are errors caught, logged, and surfaced to the user?

Format each finding as:
- **File and line:** `src/auth.py:42`
- **Severity:** bug / security / style / suggestion
- **What:** one sentence describing the issue
- **Fix:** concrete code or approach to resolve it

If the code looks good, say so. Do not invent issues to fill space.
```

### Write descriptions that trigger correctly

Agents use the `description` field to decide when to activate your skill. A
good description answers: "When should the agent use this?"

```yaml
# Too vague — triggers on everything or nothing
description: Helps with code.

# Clear trigger — agents know exactly when to activate
description: >
  Reviews code changes for bugs, security issues, and style violations.
  Use when reviewing pull requests, staged changes, or code diffs.
```

### Give examples of inputs and outputs

When a skill handles specific inputs (files, prompts, data formats), show what
the agent should expect and produce.

```markdown
## Examples

**Input:** "Summarize the changes in this PR"
**Output:** A bulleted list of what changed, organized by component, with a
one-line summary at the top.

**Input:** "Review src/api/handlers.py"
**Output:** Findings formatted as file:line, severity, description, and fix.
```

### Define what the skill should not do

Tell the agent what *not* to do. This prevents the skill from drifting into
unrelated territory.

```markdown
## Boundaries

- Only review files that are part of the current diff — do not review the entire codebase
- Do not refactor or rewrite code; only suggest changes
- If a file is generated (e.g., migrations, lock files), skip it
- Never modify files directly — output your review as text
```

### Define the output format for consistent results

When the skill produces structured output, define the exact format so results
are consistent and machine-parseable.

```markdown
## Output Format

Return a JSON array of findings:

    [
      {
        "file": "src/auth.py",
        "line": 42,
        "severity": "bug",
        "message": "Unchecked None return from get_user()",
        "suggestion": "Add a None check before accessing .email"
      }
    ]
```

---

## Full Skill Examples by Type

These full examples show how to structure different types of skills. Expand
each to see the complete SKILL.md.

??? example "Code generation — React component generator"
    ```markdown
    ---
    name: react-component
    description: >
      Generates React components following project conventions.
      Use when asked to create a new component, page, or UI element.
    ---

    # React Component Generator

    When creating a new React component:

    1. Read the project's existing components to understand conventions
    2. Use TypeScript with explicit prop types
    3. Use functional components with hooks (no class components)
    4. Place the component in the appropriate directory based on its purpose
    5. Include a basic test file alongside the component

    ## File structure

        ComponentName/
        ├── ComponentName.tsx
        ├── ComponentName.test.tsx
        └── index.ts          # Re-export

    ## Conventions

    - Props interface named `{ComponentName}Props`
    - Default export from the component file
    - Named re-export from index.ts
    - Tests use React Testing Library, not Enzyme
    ```

??? example "Workflow automation — Release preparation"
    ```markdown
    ---
    name: release-prep
    description: >
      Prepares a release by updating changelog, bumping version, and creating
      a release branch. Use when asked to prepare, cut, or create a release.
    ---

    # Release Preparation

    ## Steps

    1. Determine the next version from conventional commits since the last tag
    2. Update CHANGELOG.md with the new version's entries
    3. Bump the version in package.json (or pyproject.toml)
    4. Create a release branch: `release/v{version}`
    5. Commit with message: `chore: prepare release v{version}`
    6. Print a summary of what changed and what to do next

    ## Rules

    - Never push or create tags — only prepare the branch locally
    - If there are uncommitted changes, stop and ask the user to commit first
    - Group changelog entries by type: Added, Changed, Fixed, Removed
    ```

??? example "Analysis — Dependency audit"
    ```markdown
    ---
    name: dependency-audit
    description: >
      Audits project dependencies for security issues, outdated packages, and
      license compliance. Use when asked to check or audit dependencies.
    ---

    # Dependency Audit

    Analyze the project's dependencies and produce a report covering:

    ## Security

    - Run the package manager's audit command (npm audit, pip-audit, cargo audit)
    - List any known vulnerabilities with severity and affected package
    - For each vulnerability, suggest an upgrade path or workaround

    ## Freshness

    - Identify packages more than 2 major versions behind
    - Flag packages that haven't been updated in over 2 years
    - Note any deprecated packages

    ## Output

    Present findings as a markdown table:

    | Package | Issue | Severity | Action |
    |---------|-------|----------|--------|
    | lodash  | CVE-2021-23337 | High | Upgrade to 4.17.21+ |

    End with a summary: total dependencies, issues found, and recommended next steps.
    ```

---

## Common Pitfalls

Avoid these mistakes that make skills produce poor or inconsistent results:

| Pitfall | Why it fails | Fix |
|---------|-------------|-----|
| **Too broad** | A skill that tries to do everything ("helps with all coding tasks") is mediocre at all of them | Make focused skills that do one thing well |
| **Too short** | A three-line SKILL.md gives the agent no context — output will be generic | Include specific steps, constraints, and expected behavior |
| **No examples** | Without input/output examples, agents guess at what you want | Show at least one concrete example of expected input and output |
| **Hardcoded paths** | Skills should work in any project, not just yours | Avoid paths like `/Users/me/project/` or assuming specific tools unless stated in `compatibility` |

---

## Next Steps

- [**Skill Directory**](skills.md) — Browse official and community skills for inspiration
- [**Python SDK**](sdk.md) — Load and inspect skills programmatically
- [**Core Concepts**](concepts.md) — Understand handles, sources, and the sync lifecycle
- [**CLI Reference**](reference.md) — Every command, flag, and option for managing skills
- [Agent Skills Specification](https://agentskills.io/specification) — Full format details
- [Example Skills](https://github.com/anthropics/skills) — Reference implementations
