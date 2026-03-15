---
title: Creating Skills
---

# Creating Skills

Skills are folders of instructions that give AI agents new capabilities. This
guide helps you create, test, and share a skill with minimal ceremony.

## Quick Start

```bash
agr init my-skill
```

Creates `my-skill/SKILL.md` in your current directory:

```
my-skill/
└── SKILL.md
```

If you're adding the skill to this repo, place it under `./skills/`:

```
skills/
└── my-skill/
    └── SKILL.md
```

From there you can:

1. Write the instructions in `SKILL.md`
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
| `name` | Max 64 chars. Lowercase letters, numbers, hyphens. Must match directory name. |
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

## Skills with Supporting Files

For complex skills, add supporting files:

```
my-skill/
├── SKILL.md
├── references/       # Additional documentation
│   └── style-guide.md
├── scripts/          # Executable code
│   └── validate.py
└── assets/           # Templates, data files
    └── template.json
```

Reference them in your SKILL.md:

```markdown
See [style guide](references/style-guide.md) for formatting rules.

Run the validation script:
scripts/validate.py
```

Keep your main SKILL.md under 500 lines. Put detailed reference material in the `references/` folder.

## Test Your Skill

Add your local skill and test it:

```bash
agr add ./skills/my-skill
```

(If your skill is elsewhere, point to that path instead.)

Your skill is now available in your configured tool. Test it by starting your
agent and invoking the skill.

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

## Share with Others

Push to GitHub. Others install with:

```bash
agr add your-username/my-skill
```

Or from a specific repo:

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

### Set boundaries

Tell the agent what *not* to do. This prevents the skill from drifting into
unrelated territory.

```markdown
## Boundaries

- Only review files that are part of the current diff — do not review the entire codebase
- Do not refactor or rewrite code; only suggest changes
- If a file is generated (e.g., migrations, lock files), skip it
- Never modify files directly — output your review as text
```

### Use structured output formats

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

## Structuring Complex Skills

### When to add supporting files

Keep your SKILL.md under 500 lines. If the skill needs more detail, extract it
into supporting files:

| What | Where | Why |
|------|-------|-----|
| Reference docs the agent reads at runtime | `references/` | Keeps SKILL.md focused on workflow |
| Scripts the agent should execute | `scripts/` | Executable logic separate from instructions |
| Templates or data files | `assets/` | Reusable artifacts the agent fills in |

### Reference files for domain knowledge

If your skill needs domain-specific knowledge (a style guide, API docs, schema
definitions), put it in `references/` and point to it from SKILL.md:

```markdown
Before generating code, read [the API schema](references/api-schema.json)
and [the style guide](references/style-guide.md).
```

This keeps the main instructions short while giving the agent access to all the
context it needs.

### Scripts for deterministic work

For tasks that have a deterministic correct answer (formatting, linting,
validation), use a script rather than asking the agent to do it:

```markdown
After making changes, run the validation script:

    scripts/validate.sh

If it fails, fix the issues it reports before continuing.
```

This gives you reproducible results and keeps the agent focused on judgment
calls, not mechanical tasks.

---

## Skill Patterns

### Code generation skill

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

### Workflow automation skill

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

### Analysis skill

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

## Testing and Iterating

### Local development loop

The fastest way to iterate on a skill:

```bash
# 1. Create the skill
agr init my-skill

# 2. Edit SKILL.md with your instructions
$EDITOR my-skill/SKILL.md

# 3. Install it locally
agr add ./my-skill

# 4. Test it in your AI tool — invoke the skill and see if it works

# 5. Edit SKILL.md again, then reinstall
agr add ./my-skill --overwrite

# Repeat steps 4-5 until the skill works well
```

### Try before installing

Use `agrx` to test a remote skill without modifying your project:

```bash
agrx ./my-skill -p "Review the changes in src/"
```

### What to test

- **Happy path:** Does the skill do the right thing with a clear, simple request?
- **Edge cases:** What happens with empty input, large files, or ambiguous requests?
- **Boundaries:** Does the skill stay in scope, or does it try to do things you didn't intend?
- **Different tools:** If targeting multiple tools, test in each one — behavior can vary

---

## Common Mistakes

**Skill too broad.** A skill that tries to do everything ("helps with all
coding tasks") will be mediocre at all of them. Make focused skills that do one
thing well.

**Instructions too short.** Agents need context. A three-line SKILL.md will
produce generic output. Give the agent enough detail to produce specific,
useful results.

**No examples.** Without examples, agents guess at what you want. Include at
least one input/output example so the agent understands the expected behavior.

**Hardcoded paths or tools.** Skills should work in any project. Avoid
hardcoding paths like `/Users/me/project/` or assuming specific tools are
installed unless stated in the `compatibility` field.

---

## Learn More

- [Agent Skills Specification](https://agentskills.io/specification) — Full format details
- [Example Skills](https://github.com/anthropics/skills) — Reference implementations
