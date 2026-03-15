# Agent Skills Specification Reference

Complete reference for the [agentskills.io specification](https://agentskills.io/specification).

## Directory Structure

Skills are discovered in these locations (in order of precedence):

| Tool | Project Skills | Personal Skills |
|------|---------------|-----------------|
| Claude Code | `.claude/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/SKILL.md` |
| Cursor | `.cursor/skills/<name>/SKILL.md` | `~/.cursor/skills/<name>/SKILL.md` |
| GitHub Copilot | `.github/skills/<name>/SKILL.md` | `~/.copilot/skills/<name>/SKILL.md` |
| Codex | `.agents/skills/<name>/SKILL.md` | `~/.agents/skills/<name>/SKILL.md` |
| Open Code | `.opencode/skills/<name>/SKILL.md` | `~/.config/opencode/skill/<name>/SKILL.md` |

**Cross-compatibility**: Most tools also read `.claude/skills/` for interoperability.

## SKILL.md Frontmatter

### Required Fields

```yaml
---
name: skill-name                    # 1-64 chars, lowercase alphanumeric + hyphens
                                    # Must match parent directory name
                                    # No leading/trailing hyphens, no consecutive hyphens

description: |                      # 1-1024 chars
  What the skill does and when to use it.
  Include keywords that help agents identify relevant tasks.
---
```

### Optional Fields (Agent Skills Spec)

```yaml
---
license: MIT                        # License name or reference to bundled file

compatibility: |                    # Max 500 chars - environment requirements
  Requires Python 3.10+, network access for API calls

metadata:                           # Arbitrary key-value pairs for extensions
  author: your-name
  version: "1.0"
  category: code-review

allowed-tools: Read Grep Glob Bash  # Space-delimited list of pre-approved tools
                                    # Experimental - support varies by implementation
---
```

### Claude Code Specific Fields

```yaml
---
context: fork                       # Run skill in isolated subagent context window
                                    # Replaces legacy subagent behavior

model: sonnet                       # Model selection: sonnet, opus, haiku
                                    # Omit to inherit from parent context

disable-model-invocation: true      # Prevent automatic invocation by Claude
                                    # Skill only triggers via /skill-name command

argument-hint: <file-pattern>       # Hint shown for expected arguments
                                    # Access via $ARGUMENTS, $1, $2, etc.

agent: Explore                      # Agent type: Explore (read-only), Plan, general-purpose

hooks:                              # Lifecycle hooks (Claude Code 2.1+)
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate.sh"
  PostToolUse:
    - matcher: "*"
      hooks:
        - type: command
          command: "./scripts/log.sh"
---
```

### Cursor Specific Fields

Used in `.cursor/rules/` files:

```yaml
---
alwaysApply: true                   # Attach to every chat and cmd+k request
globs: "src/components/**/*.tsx"    # File patterns where rule applies
---
```

## Body Content Best Practices

The body contains Markdown instructions:

- Keep under **5000 tokens** for optimal loading
- Use numbered lists for sequences
- Include decision points ("If X, then Y")
- Provide input/output examples
- Document edge cases and error handling

## Optional Subdirectories

```
.claude/skills/my-skill/
├── SKILL.md                 # Required - skill definition
├── scripts/                 # Executable code
│   ├── validate.sh
│   └── transform.py
├── references/              # Documentation loaded on demand
│   ├── REFERENCE.md
│   ├── api-docs.md
│   └── examples.md
└── assets/                  # Templates, schemas, data files
    ├── template.json
    └── schema.yaml
```

## Platform-Specific Notes

### Claude Code
- Skills merged with slash commands in Claude Code 2.0+
- Hooks supported in Claude Code 2.1+
- `context: fork` for subagent-like isolation
- Memory hierarchy: Managed Policy → Project → User → Local

### Cursor
- Rules use `.mdc` extension in `.cursor/rules/`
- Supports `alwaysApply` and `globs` in rules
- Skills in `.cursor/skills/` follow Agent Skills spec
- Also reads `.claude/skills/` for compatibility

### GitHub Copilot
- Skills in `.github/skills/` (project) or `~/.copilot/skills/` (personal)
- Also reads `.claude/skills/`
- Available with Pro, Pro+, Business, Enterprise plans

### Codex
- Skills in `.agents/skills/`
- Commands in `.codex/commands/`
- Custom prompts for specialized behaviors
- AGENTS.md support for simple rules

### Open Code
- Skills in `.opencode/skills/` or `.claude/skills/`
- Commands in `.opencode/commands/`
- Built-in agents: Build (full), Plan (analysis), Explore (read-only)
- Subagent types: General, Explore

## Legacy Resource Locations

### Subagents
```
.claude/agents/*.md
.cursor/agents/*.md
.codex/agents/*.md
.opencode/agents/*.md
~/.claude/agents/*.md
```

### Slash Commands
```
.claude/commands/*.md
.cursor/commands/*.md
.codex/commands/*.md
.opencode/commands/*.md
```

### Rules
```
.claude/rules/*.md
.cursor/rules/*.mdc (or .md)
.codex/rules/*.md
~/.claude/rules/*.md
```

### Custom Prompts (Codex)
```
.codex/prompts/*.md
codex.json (prompts section)
```

### AGENTS.md Files
```
AGENTS.md
.claude/AGENTS.md
.cursor/AGENTS.md
```
