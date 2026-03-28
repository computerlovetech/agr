---
title: "Fix agr Errors — Troubleshooting Installs, Auth, Sync, Handles, and Skills"
description: Fix common agr problems — installation errors, GitHub auth, sync failures, handle formats, skill conflicts, and configuration issues.
keywords:
  - agr troubleshooting
  - agr error messages
  - fix agr not working
  - GitHub authentication failed agr
  - agr sync not working
  - skill not found agr
  - agr.toml errors
  - agr handle format
  - agr repository not found
  - agr permission error private repo
  - agr config error fix
  - agrx tool CLI not found
  - agr skill not found in sources
  - agr skill already exists
  - agr invalid handle format
  - agr git not found
  - agr unknown config key
  - agr cannot set sources directly
  - agr source already exists
  - agr url required adding source
  - agr cannot unset sources
  - agr expects exactly one value
  - agr at least one tool name required
---

# Fix Common agr Errors

!!! tldr
    Most issues come from wrong handle formats (`user/skill` not `skill`),
    missing `GITHUB_TOKEN` for private repos, or stale installs (fix with
    `agr add --overwrite`). Error messages include hints — read them first.

**Key terms:** A **skill** is a directory containing a `SKILL.md` file with
YAML frontmatter (`name`, `description`) and markdown instructions for an AI
coding agent. A **handle** identifies a skill on GitHub: `user/skill` (from
user's `skills` repo), `user/repo/skill` (from a specific repo), or
`./path/to/skill` (local). A **tool** is a supported AI coding agent (Claude
Code, Cursor, Codex, OpenCode, Copilot, or Antigravity). A **source** is a Git
server URL template where agr fetches remote skills from (default: GitHub).

Quick links: [Installation](#installation) · [Handle Format](#handle-format) · [Configuration](#configuration) · [Syncing](#syncing) · [Sources](#sources) · [Creating Skills](#creating-skills) · [Global Installs](#global-installs) · [agrx](#agrx)

## Installation

### How do I fix "git CLI not found"?

```text
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

### How do I fix "Repository not found"?

```text
Error: Repository 'user/skills' not found in source 'github'.
```

The repository doesn't exist or is private. Check:

1. **Typo in the handle?** Verify the username and repo name on GitHub.
2. **Private repo?** Set a GitHub token (see [Private Repositories](configuration.md#private-repositories)):
   ```bash
   export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
   ```
3. **Non-default repo name?** Use the three-part handle format:
   ```bash
   agr add user/my-custom-repo/skill-name
   ```

### How do I fix "Authentication failed"?

```text
Error: Authentication failed for source 'github'.
```

Your GitHub token is missing, expired, or lacks permissions.

- **No token set?** Export one:
  ```bash
  export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
  # or
  export GH_TOKEN="$(gh auth token)"
  ```
- **Token expired?** Generate a new one at [github.com/settings/tokens](https://github.com/settings/tokens).
- **Wrong permissions?** The token needs **Contents: Read-only** access on the target repository. Fine-grained tokens are recommended.

### How do I fix "Skill not found in repository"?

```text
Error: Skill 'myskill' not found in repository.
No directory named 'myskill' containing SKILL.md was found.
Hint: Create a skill at 'skills/myskill/SKILL.md' or 'myskill/SKILL.md'
```

The repo exists but doesn't contain a skill with that name. agr searches recursively for a directory matching the skill name that contains a `SKILL.md` file.

**Fix:** Follow the hint to create the skill, or check the repo on GitHub to see what skills are available. If you used a two-part handle, agr may suggest corrections:

```text
Skill 'myskill' not found. However, 'user/myskill' exists as a repository with 3 skill(s):
  agr add user/myskill/skill1
  agr add user/myskill/skill2
  agr add user/myskill/skill3
```

### How do I fix "Skill not found in sources"?

```text
Error: Skill 'myskill' not found in sources: github
```

agr searched all configured sources and couldn't find a matching skill anywhere. This differs from "Skill not found in repository" — that one means the repo was found but the skill directory wasn't in it. This error means no source had a repo containing the skill.

**Fix:**

1. **Check the handle.** Verify the username and skill name are correct.
2. **Try the three-part format** if the skill lives in a non-default repo:
   ```bash
   agr add user/custom-repo/myskill
   ```
3. **Check your sources.** If using custom sources, verify they're configured:
   ```bash
   agr config get sources
   ```

### How do I fix "Skill already exists"?

```text
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

### How do I fix "Network error: could not resolve host"?

```text
Error: Network error: could not resolve host for source 'github'.
```

DNS resolution failed. Check your internet connection, VPN, or proxy settings.

### How do I fix "Failed to clone repository"?

```text
Error: Failed to clone repository from source 'github'.
```

This is a catch-all error when git clone fails for a reason agr can't classify
(not auth, not network, not "repo not found"). Common causes:

- **Disk full** — free up space and try again
- **File permission issues** — check write access to your temp directory (`$TMPDIR` or `/tmp`)
- **Corrupt local git state** — clear the agr cache: `python -c "from agr import cache; cache.clear()"`
- **Corporate proxy or firewall** — git may be blocked. Try cloning the repo manually: `git clone https://github.com/user/repo.git`

If the manual clone works but `agr add` doesn't, [open an issue](https://github.com/kasperjunge/agent-resources/issues/new) with the full error output.

### How do I fix "agr onboard requires an interactive terminal"?

```text
Error: agr onboard requires an interactive terminal.
Hint: Use 'agr init' for non-interactive setup.
```

`agr onboard` is an interactive wizard that needs a real terminal (TTY). It won't work in CI/CD, scripts, or piped commands. Use `agr init` instead:

```bash
# In CI/CD or scripts
agr init --tools claude,cursor
```

---

## Handle Format

### How do I fix "Invalid handle: remote handles require username/name format"?

```text
Error: Invalid handle 'commit': remote handles require username/name format
```

A single word is treated as a local path. For remote skills, use the [handle format](concepts.md#handles):

```bash
# Wrong
agr add commit

# Right
agr add kasperjunge/commit
```

### How do I fix "Too many path segments"?

```text
Error: Invalid handle 'a/b/c/d': too many path segments (expected user/name or user/repo/name)
```

Handles support at most three parts: `user/repo/skill`. Check for extra slashes.

### How do I fix "Contains reserved sequence '--'"?

```text
Error: Invalid handle 'user/my--skill': skill name 'my--skill' contains reserved sequence '--'
```

Skill names cannot contain consecutive hyphens. Rename the skill to use single hyphens (e.g., `my-skill` instead of `my--skill`).

---

## Configuration

### How do I fix "No agr.toml found"?

```text
No agr.toml found.
Run 'agr init' to create one.
```

You're running a command that requires `agr.toml` but the file doesn't exist yet. Create one:

```bash
agr init
```

Or use interactive setup:

```bash
agr onboard
```

### How do I fix "Not in a git repository"?

```text
Error: Not in a git repository
```

Project-level commands need to run inside a git repo. Either `cd` into one or initialize git:

```bash
git init
```

For `agrx`, use `--global` to run outside a git repo:

```bash
agrx anthropics/skills/pdf --global
```

### How do I fix "Unknown tool"?

```text
Error: Unknown tool 'photoshop' in agr.toml. Available: claude, cursor, codex, opencode, copilot, antigravity
```

Check your `agr.toml` for typos in the `tools` list. See [Supported Tools](tools.md) for details on each:

| Config name | Tool |
|-------------|------|
| `claude` | Claude Code |
| `cursor` | Cursor |
| `codex` | OpenAI Codex |
| `opencode` | OpenCode |
| `copilot` | GitHub Copilot |
| `antigravity` | Antigravity |

### Why does `agr init` detect a tool I don't use?

`agr init` and `agr onboard` auto-detect tools by looking for specific files and
directories in your repo. Some detection signals are shared between tools:

| Signal | Detected tools |
|--------|---------------|
| `.agents/` | OpenAI Codex **and** Antigravity |

For example, if you use Codex and have an `.agents/` directory, agr also detects
Antigravity because both tools use that directory. This is intentional — the
`.agents/` path follows the [Agent Skills spec](https://agentskills.io/specification)
and both tools read skills from it.

To override detection and pick only the tools you want:

```bash
agr init --tools claude,codex
```

Or remove unwanted tools after setup:

```bash
agr config remove tools antigravity
```

See [Supported Tools — Detection Signals](tools.md#detection-signals) for the full list per tool.

### How do I fix "Cannot remove all tools. At least one must remain."?

```text
Error: Cannot remove all tools. At least one must remain.
```

agr requires at least one tool in the `tools` list. You can't remove every tool — there'd be nowhere to install skills.

If you want to switch tools entirely, add the new one before removing the old:

```bash
agr config add tools codex
agr config remove tools claude
```

### How do I fix "Invalid TOML in agr.toml"?

```text
Error: Invalid TOML in agr.toml: ...
```

Your `agr.toml` has a syntax error. Common causes:

- **Missing quotes** around string values
- **Unclosed brackets** in `dependencies` or `[[source]]`
- **Trailing commas** after the last item in a list (TOML doesn't allow them)

Validate with any TOML linter, or paste your file into [toml-lint.com](https://www.toml-lint.com/) to find the exact line.

### How do I fix "default_tool must be listed in tools"?

```text
Error: default_tool must be listed in tools in agr.toml
```

Your `default_tool` value isn't in your `tools` list. Either add it to `tools` or change `default_tool`:

```toml
# Wrong — codex isn't in tools
tools = ["claude", "cursor"]
default_tool = "codex"
```

```toml
# Right
tools = ["claude", "cursor", "codex"]
default_tool = "codex"
```

### How do I fix "default_source not found in [[source]] list"?

```text
Error: default_source 'my-server' not found in [[source]] list
```

Your `agr.toml` file has a `default_source` that refers to a source name that isn't defined in any `[[source]]` block. Either add the source or fix the name:

```bash
agr config add sources my-server --url "https://git.example.com/{owner}/{repo}.git"
# or fix the default
agr config set default_source github
```

??? note "How do I fix \"Source not found in sources list\" from `agr config set`?"
    ```text
    Error: Source 'my-server' not found in sources list.
    Hint: Available sources: github
    ```

    This is similar to the error above, but happens when you run
    `agr config set default_source my-server` and the source doesn't exist yet.
    The hint shows which sources are available. Either add the source first or
    pick an existing one:

    ```bash
    # Add the source first, then set it as default
    agr config add sources my-server --url "https://git.example.com/{owner}/{repo}.git"
    agr config set default_source my-server

    # Or use an existing source
    agr config set default_source github
    ```

??? note "How do I fix \"dependencies must be declared before [[source]] blocks\"?"
    ```text
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

??? note "How do I fix \"Unknown source in dependency\"?"
    ```text
    Error: Unknown source 'gitlab' in dependency 'user/skill'
    ```

    A dependency specifies a `source` that isn't defined in your `[[source]]` list. Either add the source or remove the `source` field from the dependency:

    ```bash
    # Add the missing source
    agr config add sources gitlab --url "https://gitlab.com/{owner}/{repo}.git"

    # Or edit agr.toml and remove source = "gitlab" from the dependency
    ```

??? note "How do I fix \"Dependency cannot have both handle and path\"?"
    ```text
    Error: Dependency cannot have both handle and path
    ```

    Each dependency must use `handle` or `path`, not both:

    ```toml
    # Wrong — both handle and path
    dependencies = [
        {handle = "user/skill", path = "./skills/skill", type = "skill"},
    ]
    ```

    ```toml
    # Right — remote
    dependencies = [
        {handle = "user/skill", type = "skill"},
    ]
    ```

??? note "How do I fix \"Dependency must have either handle or path\"?"
    ```text
    Error: Dependency must have either handle or path
    ```

    A dependency is missing both `handle` and `path`. Every dependency needs one:

    ```toml
    # Right
    dependencies = [
        {handle = "user/skill", type = "skill"},
    ]
    ```

??? note "How do I fix \"canonical_instructions must be 'AGENTS.md', 'CLAUDE.md', or 'GEMINI.md'\"?"
    Only these three instruction file names are supported for syncing. Other filenames like `README.md` or `INSTRUCTIONS.md` won't work.

??? note "How do I fix \"Cannot unset sources\"?"
    ```text
    Error: Cannot unset sources. Use 'agr config remove sources <name>'.
    ```

    Sources can't be cleared with `unset` because agr needs at least one source.
    Remove individual sources instead:

    ```bash
    agr config remove sources my-server
    ```

??? note "How do I fix \"expects exactly one value\"?"
    ```text
    Error: 'default_tool' expects exactly one value.
    ```

    Scalar keys (`default_tool`, `default_source`, `sync_instructions`,
    `canonical_instructions`) accept a single value, not a list:

    ```bash
    # Wrong — multiple values for a scalar key
    agr config set default_tool claude cursor

    # Right
    agr config set default_tool claude
    ```

    List keys (`tools`) accept multiple values with `set`:

    ```bash
    agr config set tools claude cursor codex
    ```

??? note "How do I fix \"At least one tool name is required\"?"
    ```text
    Error: At least one tool name is required.
    ```

    You ran `agr config set tools` or `agr config add tools` without specifying
    any tool names. Provide at least one:

    ```bash
    agr config set tools claude
    agr config add tools cursor
    ```

### How do I fix "sync_instructions must be 'true' or 'false'"?

```text
Error: sync_instructions must be 'true' or 'false'.
```

The `sync_instructions` setting only accepts boolean values:

```bash
# Wrong
agr config set sync_instructions yes

# Right
agr config set sync_instructions true
```

### How do I fix "Neither $VISUAL nor $EDITOR is set"?

```text
Error: Neither $VISUAL nor $EDITOR is set.
```

`agr config edit` opens `agr.toml` in your default editor, but no editor is configured. Set one:

```bash
export EDITOR="vim"       # or nano, code, etc.
agr config edit
```

Add the `export` to your shell profile (`~/.zshrc`, `~/.bashrc`) to make it permanent.

### How do I fix "No global config found"?

```text
Error: No global config found at ~/.agr/agr.toml
Hint: Run 'agr init' or create it manually.
```

You ran a global config command (`agr config -g ...`) but no global config exists yet. Create one by installing a skill globally:

```bash
agr add -g user/skill
```

This creates `~/.agr/agr.toml` automatically.

### How do I fix "Unknown config key"?

```text
Error: Unknown config key 'tool'. Valid keys: canonical_instructions, default_source, default_tool, sources, sync_instructions, tools
```

You used a key name that `agr config` doesn't recognize. Common mistakes:

- `tool` instead of `tools`
- `source` instead of `sources`
- `instructions` instead of `sync_instructions`

??? note "How do I fix \"'default_tool' is a scalar. Use 'agr config set'\"?"
    ```text
    Error: 'default_tool' is a scalar. Use 'agr config set default_tool <value>'.
    ```

    You used `agr config add` or `agr config remove` on a scalar key. Scalar
    keys (`default_tool`, `default_source`, `sync_instructions`,
    `canonical_instructions`) accept a single value — use `set` to change them
    and `unset` to clear them:

    ```bash
    # Wrong — add/remove are for list keys (tools, sources)
    agr config add default_tool claude
    agr config remove default_tool

    # Right — use set/unset for scalar keys
    agr config set default_tool claude
    agr config unset default_tool
    ```

    List keys (`tools`, `sources`) support `add` and `remove`.

??? note "How do I fix \"Cannot set sources directly\"?"
    ```text
    Error: Cannot set sources directly. Use 'agr config add sources' and 'agr config remove sources'.
    ```

    Sources can't be replaced in one shot with `set`. Add and remove them individually:

    ```bash
    agr config add sources my-server --url "https://git.example.com/{owner}/{repo}.git"
    agr config remove sources old-server
    ```

??? note "How do I fix \"--url is required when adding a source\"?"
    ```text
    Error: --url is required when adding a source.
    ```

    When adding a source, you must provide a URL template with `{owner}` and `{repo}` placeholders:

    ```bash
    agr config add sources my-server --url "https://git.example.com/{owner}/{repo}.git"
    ```

??? note "How do I fix \"Source already exists\"?"
    ```text
    Error: Source 'github' already exists.
    ```

    To update it, remove the old one first:

    ```bash
    agr config remove sources github
    agr config add sources github --url "https://github.com/{owner}/{repo}.git"
    ```

??? note "How do I fix \"Tool is not in configured tools\"?"
    ```text
    Error: Tool 'codex' is not in configured tools. Add it first with 'agr config add tools codex'.
    ```

    Add the tool first, then set it as default:

    ```bash
    agr config add tools codex
    agr config set default_tool codex
    ```

??? note "How do I fix \"Unknown tool(s)\" from `agr config`?"
    ```text
    Error: Unknown tool(s): photoshop
    Hint: Available tools: claude, cursor, codex, opencode, copilot, antigravity
    ```

    You passed an unrecognized tool name to `agr config set tools`,
    `agr config add tools`, or `agr config remove tools`. Check for typos —
    valid names are listed in the hint. See [Supported Tools](tools.md) for
    details on each.

??? note "How do I fix \"Unknown default_tool in agr.toml\"?"
    ```text
    Error: Unknown default_tool 'vscode' in agr.toml. Available: claude, cursor, codex, opencode, copilot, antigravity
    ```

    Your `default_tool` is set to a tool name that agr doesn't recognize. This
    is different from `default_tool must be listed in tools` — that error means
    the tool is valid but not in your `tools` list. This one means the name
    itself is wrong:

    ```bash
    agr config set default_tool claude
    ```

??? note "How do I fix \"Source name is required\" or \"Only one source name allowed\"?"
    ```text
    Error: Source name is required.
    ```

    ```text
    Error: Only one source name allowed at a time.
    ```

    When adding or removing sources, provide exactly one source name:

    ```bash
    # Wrong — missing name
    agr config add sources --url "https://..."

    # Wrong — multiple names
    agr config remove sources gitlab my-server

    # Right
    agr config add sources gitlab --url "https://gitlab.com/{owner}/{repo}.git"
    agr config remove sources gitlab
    ```

??? note "How do I fix \"--type and --url are only valid for 'sources'\"?"
    ```text
    Error: --type and --url are only valid for 'sources'.
    ```

    The `--type` and `--url` flags only work with `agr config add sources`.
    You passed them to a different key:

    ```bash
    # Wrong — --url doesn't apply to tools
    agr config add tools claude --url "https://..."

    # Right
    agr config add sources my-server --url "https://git.example.com/{owner}/{repo}.git"
    ```

---

## Syncing

### How do I fix "No dependencies in agr.toml. Nothing to sync."?

Your `agr.toml` exists but has no `dependencies` entry. Add skills first:

```bash
agr add user/skill
```

This both installs the skill and adds it to `agr.toml`.

### How do I fix "Instruction sync skipped: CLAUDE.md not found."?

You have `sync_instructions = true` but the canonical instruction file doesn't exist yet. Create it:

```bash
touch CLAUDE.md
```

Then run `agr sync` again.

### Why does instruction sync not do anything?

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

### Why does sync show "Up to date" but my skill seems outdated?

`agr sync` skips skills that are already installed. To force a fresh install from
the latest version:

```bash
agr add user/skill --overwrite
```

This re-downloads the skill from GitHub and replaces your local copy.

---

## Sources

### How do I fix "Cannot remove default source"?

```text
Error: Cannot remove default source 'my-server'. Change default_source first.
```

You can't remove a source that is currently set as `default_source`. Change the
default first:

```bash
agr config set default_source github
agr config remove sources my-server
```

??? note "How do I fix \"Source not found\" when removing?"
    ```text
    Error: Source 'my-server' not found.
    ```

    The source you're trying to remove doesn't exist. Check the current sources:

    ```bash
    agr config get sources
    ```

??? note "How do I fix \"Source entry missing name\"?"
    ```text
    Error: Source entry missing name
    ```

    Every `[[source]]` block needs a `name` field:

    ```toml
    [[source]]
    name = "my-server"
    type = "git"
    url = "https://git.example.com/{owner}/{repo}.git"
    ```

??? note "How do I fix \"Source missing url\"?"
    ```text
    Error: Source 'my-server' missing url
    ```

    Add the URL template:

    ```toml
    [[source]]
    name = "my-server"
    type = "git"
    url = "https://git.example.com/{owner}/{repo}.git"
    ```

??? note "How do I fix \"Unsupported source type\"?"
    ```text
    Error: Unsupported source type 'svn' for 'my-server'
    ```

    ```text
    Error: Unsupported source type 'svn'. Only 'git' is supported.
    ```

    Only `git` sources are supported. The first error appears when loading
    `agr.toml` with an invalid `type` in a `[[source]]` block. The second
    appears when running `agr config add sources --type svn`. In both cases,
    change the type to `git`.

### How do I fix "GitHub API rate limit exceeded"?

```text
Error: GitHub API rate limit exceeded
```

You've hit GitHub's API rate limit. This mainly affects the Python SDK (`list_skills()`, `skill_info()`) which use the GitHub API — not `agr add` or `agr sync`, which use Git clones.

- **Authenticate to raise your limit.** Unauthenticated requests are limited to 60/hour. With a token, you get 5,000/hour:
  ```bash
  export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
  ```
- **Wait for the limit to reset.** GitHub rate limits reset hourly. Check your remaining quota with:
  ```bash
  curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit | python3 -m json.tool
  ```
- **In CI, cache results.** If your pipeline calls `list_skills()` or `skill_info()` repeatedly, cache the output instead of calling the API on every run.

### How do I fix "GitHub API authentication failed"?

```text
Error: GitHub API authentication failed (HTTP 403)
```

This SDK-specific error means your `GITHUB_TOKEN` was rejected by the GitHub API.
Unlike the git-level "Authentication failed" error (which fires during `agr add`),
this one fires from SDK functions like `list_skills()` and `skill_info()`.

- **Token revoked or expired?** Generate a new one at [github.com/settings/tokens](https://github.com/settings/tokens).
- **Wrong token type?** Fine-grained tokens need **Contents: Read-only** permission on the target repo.
- **HTTP 401 vs 403:** Both surface as this error. 401 means the token is invalid; 403 means it lacks permissions.

### How do I fix "Failed to connect to GitHub API"?

```text
Error: Failed to connect to GitHub API: <urlopen error ...>
```

The SDK couldn't reach `api.github.com`. This affects `list_skills()`, `skill_info()`,
and other SDK functions that call the GitHub REST API.

- **No internet?** Check your connection.
- **Corporate proxy or firewall?** The GitHub API may be blocked. Try: `curl -s https://api.github.com`
- **DNS issues?** Same as the git-level ["Network error: could not resolve host"](#how-do-i-fix-network-error-could-not-resolve-host) — check VPN and DNS settings.

??? note "How do I fix \"Local skills cannot specify a source\"?"
    ```text
    Error: Local skills cannot specify a source
    ```

    The `--source` flag only applies to remote handles. Local paths are installed
    directly from disk:

    ```bash
    # Wrong
    agr add ./my-skill --source github

    # Right
    agr add ./my-skill
    ```

---

## Creating Skills

### How do I fix "Invalid skill name"?

```text
Error: Invalid skill name 'My_Skill': must be 1-64 lowercase alphanumeric characters and hyphens, cannot start/end with a hyphen
```

Skill names must be lowercase alphanumeric with hyphens. No uppercase, underscores, spaces, or special characters. Names cannot start or end with a hyphen, and consecutive hyphens (`--`) are not allowed.

```bash
# Wrong
agr init "my skill"
agr init My_Skill
agr init MySkill
agr init -my-skill

# Right
agr init my-skill
agr init myskill
agr init code-reviewer
```

??? note "How do I fix \"Directory already exists\"?"
    ```text
    Error: Directory 'myskill' already exists
    ```

    `agr init` won't overwrite an existing directory. Either remove it or choose a different name.

??? note "How do I fix \"Local skill name is already installed\"?"
    ```text
    Error: Local skill name 'my-skill' is already installed at /path/to/my-skill.
    ```

    agr enforces unique names. Rename one skill or remove the existing one:

    ```bash
    agr remove my-skill
    agr add ./new-location/my-skill
    ```

### How do I fix "not a valid skill (missing SKILL.md)"?

```text
Error: './my-skill' is not a valid skill (missing SKILL.md)
```

The path doesn't contain a `SKILL.md` file. Create one and add the required frontmatter — see [Creating Skills](creating.md).

### Why is my skill not showing up in my tool?

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

### How do I fix "No global agr.toml found"?

```text
No global agr.toml found.
Run 'agr add -g <handle>' to create one.
```

There's no global config yet. Install a skill globally to create one:

```bash
agr add -g user/skill
```

The global config lives at `~/.agr/agr.toml`.

---

## agrx

### How do I fix "Tool CLI not found"?

```text
Error: codex CLI not found.
```

`agrx` needs the selected tool's CLI installed on your system. See which CLI each tool requires:

| Tool | CLI command | Install |
|------|------------|---------|
| Claude Code | `claude` | [claude.ai/download](https://claude.ai/download) |
| Cursor | `agent` | Install the Cursor IDE |
| OpenAI Codex | `codex` | `npm i -g @openai/codex` |
| OpenCode | `opencode` | [opencode.ai](https://opencode.ai) |
| GitHub Copilot | `copilot` | Install GitHub Copilot CLI |

If you have the tool installed but `agrx` can't find it, check that the CLI is on your `PATH`:

```bash
which claude   # or codex, agent, opencode, copilot
```

### How do I fix "agrx only works with remote handles"?

```text
Error: agrx only works with remote handles
Hint: Use 'agr add' for local skills
```

`agrx` downloads skills from GitHub and cleans up after running — it doesn't
work with local paths. For local skills, install them permanently instead:

```bash
# Wrong
agrx ./skills/my-skill

# Right — install locally
agr add ./skills/my-skill

# Right — run a remote skill
agrx user/my-skill
```

### Why can't I use agrx with Antigravity?

Antigravity does not have a standalone CLI, so `agrx` cannot run skills with it. Use `agr add` to install skills permanently, then invoke them through the Antigravity IDE interface.

### How do I use agrx outside a git repository?

By default, `agrx` requires a git repo (to find `agr.toml` for tool/source config). Use `--global` to skip this:

```bash
agrx anthropics/skills/pdf --global
```

This installs the skill into the tool's global skills directory, runs it, and cleans up.

---

## Still stuck?

- Run the failing command with details and check the output carefully — agr prints hints below most errors.
- Check [GitHub Issues](https://github.com/kasperjunge/agent-resources/issues) for known problems.
- [Open a new issue](https://github.com/kasperjunge/agent-resources/issues/new) with the full error output and your `agr.toml` contents.

## Related Pages

- [**Configuration**](configuration.md) — Fix `agr.toml` settings, sources, and instruction sync issues
- [**Supported Tools**](tools.md) — Check detection signals, skill directories, and CLI requirements per tool
- [**agrx**](agrx.md) — Fix issues with ephemeral skill runs, tool selection, and interactive mode
- [**CLI Reference**](reference.md) — Verify command syntax, flags, and handle formats
- [**Creating Skills**](creating.md) — Fix SKILL.md format, name validation, and testing issues
- [**Python SDK**](sdk.md) — Fix SDK-specific errors (rate limits, API auth, network failures)
- [**Teams**](teams.md) — Fix CI/CD sync failures, private repo auth, and multi-tool team setup
