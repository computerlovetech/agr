---
title: "agr Changelog — New Features, Fixes, and Breaking Changes by Release"
description: User-facing changes in each agr release — new features, bug fixes, and breaking changes for the AI agent skill manager.
keywords:
  - agr changelog
  - agr release notes
  - agr new features
  - agr breaking changes
  - agr version history
  - agr updates
  - what's new in agr
---

# What's New

User-facing changes in each release. For the full changelog with implementation
details, see [CHANGELOG.md on GitHub](https://github.com/kasperjunge/agent-resources/blob/main/CHANGELOG.md).

---

## Unreleased

### Antigravity now uses `.gemini/` directory

[Antigravity](tools.md#antigravity) skills now install to `.gemini/skills/` instead of the previous `.agent/skills/`. This matches the Gemini CLI's move from `.agent/` to `.gemini/` as its primary configuration directory.

**Auto-migration:** When you run [`agr sync`](reference.md#agr-sync), [`agr add`](reference.md#agr-add), or [`agr remove`](reference.md#agr-remove), agr automatically moves existing skills from `.agent/skills/` to `.gemini/skills/`. No manual steps needed. See [Automatic Directory Migrations](tools.md#automatic-directory-migrations) for the full list.

### Cursor now uses flat naming

[Cursor](tools.md#cursor) skills are now installed with flat directory names (e.g., `.cursor/skills/skill-name/`) instead of the previous nested structure (`.cursor/skills/owner/repo/skill-name/`). This aligns Cursor with all other [supported tools](tools.md).

**Auto-migration:** When you run [`agr sync`](reference.md#agr-sync), [`agr add`](reference.md#agr-add), or [`agr remove`](reference.md#agr-remove), agr automatically flattens existing nested Cursor skills to the new layout. If a plain name conflicts with an existing directory, the fully-qualified name (`owner--repo--skill`) is used instead. No manual steps needed.

### `agrx` now uses `--full-auto` for Codex

When running skills with [`agrx --tool codex`](agrx.md) in interactive mode, agr now passes `--full-auto` to the [Codex CLI](tools.md#openai-codex). This reduces permission prompts during execution, matching the behavior of other tools (Claude Code's `--dangerously-skip-permissions`, Copilot's `--allow-all-tools`).

### Stricter skill name validation

Skill names now follow the [Agent Skills specification](https://agentskills.io/specification) exactly. Valid names must be:

- 1–64 characters
- Lowercase alphanumeric and hyphens only
- Cannot start or end with a hyphen
- Cannot contain consecutive hyphens (`--`)

Previously accepted names with uppercase letters, underscores, or trailing hyphens are now rejected. If you have existing skills with these patterns, rename them before upgrading.

### `description` field required in SKILL.md

The `description` frontmatter field is now required when scaffolding a skill with [`agr init <name>`](reference.md#agr-init). The generated template includes a placeholder you should fill in:

```yaml
description: TODO — describe what this skill does and when to use it
```

See [SKILL.md Format](creating.md#skillmd-format) for all frontmatter fields.

### Improved Copilot detection

[`agr init`](reference.md#agr-init) and [`agr onboard`](reference.md#agr-onboard) now detect [GitHub Copilot](tools.md#github-copilot) from `.github/copilot-instructions.md` and `.github/instructions/`, in addition to `.github/copilot/` and `.github/skills/`. This catches projects that use Copilot's repo-wide or path-specific instruction files without a dedicated skills directory.

### Improved OpenCode detection

[`agr init`](reference.md#agr-init) and [`agr onboard`](reference.md#agr-onboard) now detect [OpenCode](tools.md#opencode) from `opencode.json` and `opencode.jsonc` config files, in addition to the `.opencode/` directory. This catches projects that use OpenCode's config file without having created the `.opencode/` directory yet.

### Bug fixes

- **[Python SDK](sdk.md):** Network failures in `list_skills()` and `skill_info()` now raise `AgrError` instead of Python's built-in `ConnectionError`. If your code catches `AgrError` (or its subclasses), network errors are now included automatically. If you were catching `ConnectionError` separately, you can remove that handler. See [Error Handling](sdk.md#handle-errors-with-agrerror-subclasses).
- **[Python SDK](sdk.md):** `list_skills()` now raises `InvalidHandleError` instead of `ValueError` for invalid repo handles, matching the behavior of `skill_info()` and `Skill.from_git()`. If your code catches `ValueError` from `list_skills()`, update it to catch `InvalidHandleError` (from `agr.exceptions`). See [Error Handling](sdk.md#handle-errors-with-agrerror-subclasses).
- [Antigravity](tools.md#antigravity) detection signal corrected from `.agent` to `.agents`. Previously, `agr init` and `agr onboard` would not auto-detect Antigravity in repos that had an `.agents/` directory (used by Codex) — only `.gemini/` was matched.
- [`agrx --tool cursor`](agrx.md) no longer passes an invalid `--force` flag to the Cursor CLI. The Cursor CLI (`agent`) does not support this flag, so `agrx` now runs without a permission-bypass flag for Cursor.
- [`agrx --tool opencode`](agrx.md) now correctly uses two different modes: non-interactive runs use `opencode run "prompt"` (one-shot execution), while interactive runs (`-i`) use `opencode --prompt "prompt"` to inject the prompt into the TUI. Previously, `agrx` passed an invalid `--prompt` flag on the base command for non-interactive mode and routed both modes through `opencode run`.

---

## 0.7.10 — 2026-03-10

### Updated tool directories

[Codex](tools.md#openai-codex) and [OpenCode](tools.md#opencode) updated their skills directory conventions upstream. agr now
follows them:

| Tool | Old directory | New directory |
|------|-------------|---------------|
| OpenAI Codex | `.codex/skills/` | `.agents/skills/` |
| OpenCode | `.opencode/skill/` | `.opencode/skills/` |

**Auto-migration:** When you run `agr sync`, `agr add`, or `agr remove`, agr
automatically moves existing skills from the old directories to the new ones. No
manual steps needed.

### Bug fixes

- [`agr config unset tools`](reference.md#agr-config) no longer crashes when `default_tool` is set to a
  tool outside the default list. The default is now cleared automatically.
- The SDK's [`cache.info()`](sdk.md#manage-the-download-cache) now counts unique skills instead of counting each
  cached revision separately.
- Cache operations no longer reject valid skill names that happen to contain
  path-like characters (e.g., names with dots).

---

## 0.7.9 — 2026-03-05

### Content hashes for installed skills

Installed skills now include a `sha256:` content hash in their `.agr.json`
metadata. This lets you detect whether skill files have been modified on disk
since installation.

The [Python SDK](sdk.md) exposes this via [`skill.content_hash` and `skill.recompute_content_hash()`](sdk.md#recomputing-content-hash):

```python
from agr import Skill

skill = Skill.from_git("anthropics/skills/code-review")
if skill.content_hash != skill.recompute_content_hash():
    print("Skill files have changed since install")
```

---

## 0.7.8 — 2026-03-02

### Interactive onboarding

New command: [`agr onboard`](reference.md#agr-onboard). Walks you through setting up agr in an existing
project — tool selection, skill discovery, migration, and configuration — all
interactively.

```bash
agr onboard
```

If you used `agr init --interactive` before, that flag has been removed. Use
`agr onboard` instead.

### Quiet mode

Suppress all non-error output with `--quiet` / `-q`. Useful in [CI/CD pipelines](teams.md#cicd-integration):

```bash
agr sync -q          # Silent sync (errors still print)
agr add user/skill -q
```

### Simplified `agr init`

[`agr init`](reference.md#agr-init) now only creates `agr.toml` and auto-detects your [tools](tools.md). Interactive
setup, skill discovery, and migration moved to [`agr onboard`](reference.md#agr-onboard).

---

## 0.7.7 — 2026-03-02

### Bug fixes

- [`agr config`](reference.md#agr-config) commands with `--global` no longer require a git repository
- `agr config edit` works with editors that need flags (e.g., `EDITOR="code --wait"`)
- `agr config path --global` shows an error when no [global config](configuration.md#global-installs) exists instead of printing a nonexistent path

---

## 0.7.6 — 2026-03-02

### Helpful handle suggestions

When a two-part [handle](concepts.md#handles) like `agr add owner/repo` fails (because it's actually a
repo, not a skill in the default `skills` repo), agr now probes the repo and
suggests the correct three-part handles:

```text
Skill 'my-repo' not found. However, 'owner/my-repo' exists as a repository with 3 skill(s):
  agr add owner/my-repo/skill-a
  agr add owner/my-repo/skill-b
  agr add owner/my-repo/skill-c
```

---

## 0.7.5 — 2026-02-07

### `agr config` command

New unified [config management](configuration.md#managing-config):

```bash
agr config show                # View config
agr config set tools claude codex opencode
agr config set default_tool claude
agr config add sources gitlab --url "https://gitlab.com/{owner}/{repo}.git"
agr config unset default_tool
```

Replaces the older `agr tools` commands (which still work but show deprecation
warnings). See the [CLI Reference](reference.md#agr-config) for all subcommands.

### Global installs

Install skills [globally](configuration.md#global-installs) (available in all projects) with the `-g` flag:

```bash
agr add -g anthropics/skills/skill-creator
agr sync -g
agr list -g
agr remove -g anthropics/skills/skill-creator
```

Global config lives at `~/.agr/agr.toml`.

---

## 0.7.4 — 2026-02-06

### Antigravity support

agr now supports [Antigravity](tools.md#antigravity) as a tool target:

```bash
agr config add tools antigravity
```

Skills install to `.gemini/skills/` (project) and `~/.gemini/skills/` (global).

---

## 0.7.3 — 2026-02-04

### Default repo name change

Two-part [handles](concepts.md#handles) (`user/skill`) now look in the `skills` repo by default instead
of `agent-resources`. During a deprecation period, agr falls back to
`agent-resources` with a warning if the skill isn't found in `skills`.

---

## 0.7.2 — 2026-02-02

### Python SDK

Use agr as a [Python library](sdk.md):

```python
from agr import Skill, list_skills, skill_info, cache

skill = Skill.from_git("anthropics/skills/code-review")
print(skill.prompt)
print(skill.files)
```

See the [Python SDK documentation](sdk.md) for the full API.

### OpenCode support

agr now supports [OpenCode](tools.md#opencode) as a tool target with
`.opencode/skills/` install path.

---

## 0.7.1 — 2026-01-29

### Flat skill naming

Flat tools (Claude, Codex, OpenCode, Copilot, Antigravity) now install skills
using plain names (`skill-name/`) instead of the full handle
(`user--repo--skill/`). Existing installs are auto-migrated during [`agr sync`](reference.md#agr-sync). See [How skills are named on disk](concepts.md#how-skills-are-named-on-disk) for details.

### Instruction file syncing

Keep `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` in sync across tools with [instruction syncing](configuration.md#instruction-syncing):

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr sync   # Copies CLAUDE.md content to AGENTS.md, GEMINI.md as needed
```

---

## 0.7.0 — 2026-01-27

### Multi-tool support

Skills can now be installed to multiple [AI tools](tools.md) simultaneously. Configure your
tools in [`agr.toml`](configuration.md):

```toml
tools = ["claude", "cursor", "codex"]
```

`agr add` and `agr sync` install to all configured tools at once. If an install
fails partway through, already-installed copies are rolled back automatically.

### Cursor support

agr now supports [Cursor](tools.md#cursor) with skills installed to
`.cursor/skills/`.

### GitHub Copilot support

agr now supports [GitHub Copilot](tools.md#github-copilot) with
flat directory structure (`.github/skills/` for project, `~/.copilot/skills/`
for global).

### Private repository support

Set `GITHUB_TOKEN` or `GH_TOKEN` to access private skill repositories:

```bash
export GITHUB_TOKEN="ghp_aBcDeFgHiJkL01234567890mNoPqRsTuVwXy"
agr add private-org/skills/internal-tool
```

See [Private Repositories](configuration.md#private-repositories) for details.

---

## Next Steps

- [**Tutorial**](tutorial.md) — Get started with agr from scratch
- [**CLI Reference**](reference.md) — Full command reference for all features mentioned above
- [**Troubleshooting**](troubleshooting.md) — Fix common errors after upgrading
