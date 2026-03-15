---
title: Troubleshooting
---

# Troubleshooting

Common problems and how to fix them.

## Installation

### "git CLI not found"

```
Error: git CLI not found. Install git to fetch remote skills.
```

agr uses `git` under the hood for all remote operations. Install it:

=== "macOS"

    ```bash
    xcode-select --install
    ```

=== "Ubuntu/Debian"

    ```bash
    sudo apt install git
    ```

=== "Windows"

    Download from [git-scm.com](https://git-scm.com/downloads).

### "Repository not found"

```
Error: Repository 'user/skills' not found in source 'github'.
```

The repository doesn't exist or is private. Check:

1. **Typo in the handle?** Verify the username and repo name on GitHub.
2. **Private repo?** Set a GitHub token (see [Private Repositories](configuration.md#private-repositories)):
   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```
3. **Non-default repo name?** Use the three-part handle format:
   ```bash
   agr add user/my-custom-repo/skill-name
   ```

### "Authentication failed"

```
Error: Authentication failed for source 'github'.
```

Your GitHub token is missing, expired, or lacks permissions.

- **No token set?** Export one:
  ```bash
  export GITHUB_TOKEN="ghp_your_token_here"
  # or
  export GH_TOKEN="$(gh auth token)"
  ```
- **Token expired?** Generate a new one at [github.com/settings/tokens](https://github.com/settings/tokens).
- **Wrong permissions?** The token needs **Contents: Read-only** access on the target repository. Fine-grained tokens are recommended.

### "Skill not found in repository"

```
Error: Skill 'myskill' not found in repository.
No directory named 'myskill' containing SKILL.md was found.
```

The repo exists but doesn't contain a skill with that name. agr searches recursively for a directory matching the skill name that contains a `SKILL.md` file.

**Fix:** Check the repo on GitHub to see what skills are available. If you used a two-part handle, agr may suggest corrections:

```
Skill 'myskill' not found. However, 'user/myskill' exists as a repository with 3 skill(s):
  agr add user/myskill/skill1
  agr add user/myskill/skill2
  agr add user/myskill/skill3
```

### "Skill already exists"

```
Error: Skill already exists at /path/to/skill. Use --overwrite to replace.
```

The skill is already installed. To update it:

```bash
agr add user/skill --overwrite
```

Or remove it first:

```bash
agr remove user/skill
agr add user/skill
```

### "Network error: could not resolve host"

```
Error: Network error: could not resolve host for source 'github'.
```

DNS resolution failed. Check your internet connection, VPN, or proxy settings.

---

## Handle Format

### "Invalid handle: remote handles require username/name format"

```
Error: Invalid handle 'commit': remote handles require username/name format
```

A single word is treated as a local path. For remote skills, include the username:

```bash
# Wrong
agr add commit

# Right
agr add kasperjunge/commit
```

### "Too many path segments"

```
Error: Invalid handle 'a/b/c/d': too many path segments (expected user/name or user/repo/name)
```

Handles support at most three parts: `user/repo/skill`. Check for extra slashes.

### "Contains reserved sequence '--'"

```
Error: Invalid handle 'user/my--skill': skill name 'my--skill' contains reserved sequence '--'
```

Skill names cannot contain `--`. Rename the skill to use single hyphens.

---

## Configuration

### "No agr.toml found"

```
Error: No agr.toml found.
Run 'agr init' first to create one.
```

You're running a command that requires `agr.toml` but the file doesn't exist yet. Create one:

```bash
agr init
```

Or use interactive setup:

```bash
agr onboard
```

### "Not in a git repository"

```
Error: Not in a git repository
```

Project-level commands need to run inside a git repo. Either `cd` into one or initialize git:

```bash
git init
```

### "Unknown tool"

```
Error: Unknown tool 'photoshop' in agr.toml. Available: claude, cursor, codex, opencode, copilot, antigravity
```

Check your `agr.toml` for typos in the `tools` list. The supported tools are:

| Config name | Tool |
|-------------|------|
| `claude` | Claude Code |
| `cursor` | Cursor |
| `codex` | OpenAI Codex |
| `opencode` | OpenCode |
| `copilot` | GitHub Copilot |
| `antigravity` | Antigravity |

### "dependencies must be declared before [[source]] blocks"

```
Error: dependencies must be declared before [[source]] blocks
```

In `agr.toml`, the `dependencies` array must come before any `[[source]]` entries:

```toml
# Correct order
dependencies = [
    {handle = "user/skill", type = "skill"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

### "canonical_instructions must be 'AGENTS.md', 'CLAUDE.md', or 'GEMINI.md'"

Only these three instruction file names are supported for syncing. Other filenames like `README.md` or `INSTRUCTIONS.md` won't work.

---

## Syncing

### "No dependencies in agr.toml. Nothing to sync."

Your `agr.toml` exists but has no `dependencies` entry. Add skills first:

```bash
agr add user/skill
```

This both installs the skill and adds it to `agr.toml`.

### "Instruction sync skipped: CLAUDE.md not found."

You have `sync_instructions = true` but the canonical instruction file doesn't exist yet. Create it:

```bash
touch CLAUDE.md
```

Then run `agr sync` again.

### Instruction sync enabled but nothing happens

You have `sync_instructions = true` but `agr sync` doesn't copy any instruction
files. Two common causes:

1. **Only one tool configured.** Instruction syncing requires **two or more
   tools** — with a single tool, there's nothing to sync to. Add another tool:
   ```bash
   agr config set tools claude cursor
   agr sync
   ```

2. **All tools use the same instruction file.** If all your configured tools
   share the same instruction file (e.g., Cursor, Codex, and OpenCode all use
   `AGENTS.md`), there's nothing to copy. Syncing only helps when tools need
   *different* instruction files (e.g., Claude uses `CLAUDE.md`, Codex uses
   `AGENTS.md`).

### Sync shows "Up to date" but skill seems outdated

agr caches cloned repos. To force a fresh install:

```bash
agr remove user/skill
agr add user/skill
```

---

## Sources

### "Cannot remove default source"

```
Error: Cannot remove default source 'my-server'. Change the default source first.
```

You can't remove a source that is currently set as `default_source`. Change the
default first:

```bash
agr config set default_source github
agr config remove sources my-server
```

### "Local skills cannot specify a source"

```
Error: Local skills cannot specify a source
```

The `--source` flag only applies to remote handles. Local paths (`./my-skill`)
are installed directly from disk — they don't go through any source:

```bash
# Wrong
agr add ./my-skill --source github

# Right
agr add ./my-skill
```

---

## Creating Skills

### "Invalid skill name"

```
Error: Invalid skill name 'my skill': must be alphanumeric with hyphens/underscores
```

Skill names must be lowercase letters, numbers, and hyphens only. No spaces or special characters:

```bash
# Wrong
agr init "my skill"
agr init My_Skill!

# Right
agr init my-skill
```

### "Directory already exists"

```
Error: Directory 'myskill' already exists
```

`agr init` won't overwrite an existing directory. Either remove it or choose a different name.

### Skill not showing up in my tool

After `agr add ./skills/my-skill`, verify:

1. **Check the skill directory exists** in the tool's skills folder (e.g., `.claude/skills/my-skill/SKILL.md`).
2. **Validate SKILL.md frontmatter** — both `name` and `description` are required:
   ```markdown
   ---
   name: my-skill
   description: What this skill does and when to use it.
   ---
   ```
3. **Restart the tool** — some tools require a restart to pick up new skills.
4. **Check `agr list`** to see if the skill is registered.

---

## Global Installs

### "No global agr.toml found"

```
Error: No global agr.toml found
Run 'agr add -g <handle>' first.
```

There's no global config yet. Install a skill globally to create one:

```bash
agr add -g user/skill
```

The global config lives at `~/.agr/agr.toml`.

---

## Still stuck?

- Run the failing command with details and check the output carefully — agr prints hints below most errors.
- Check [GitHub Issues](https://github.com/kasperjunge/agent-resources/issues) for known problems.
- [Open a new issue](https://github.com/kasperjunge/agent-resources/issues/new) with the full error output and your `agr.toml` contents.
