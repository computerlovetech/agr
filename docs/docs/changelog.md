---
title: What's New
---

# What's New

User-facing changes in each release. For the full changelog with implementation
details, see [CHANGELOG.md on GitHub](https://github.com/kasperjunge/agent-resources/blob/main/CHANGELOG.md).

---

## 0.7.10 — 2026-03-10

### Updated tool directories

Codex and OpenCode updated their skills directory conventions upstream. agr now
follows them:

| Tool | Old directory | New directory |
|------|-------------|---------------|
| OpenAI Codex | `.codex/skills/` | `.agents/skills/` |
| OpenCode | `.opencode/skill/` | `.opencode/skills/` |

**Auto-migration:** When you run `agr sync`, `agr add`, or `agr remove`, agr
automatically moves existing skills from the old directories to the new ones. No
manual steps needed.

---

## 0.7.9 — 2026-03-05

### Content hashes for installed skills

Installed skills now include a `sha256:` content hash in their `.agr.json`
metadata. This lets you detect whether skill files have been modified on disk
since installation.

The SDK exposes this via `skill.content_hash` and `skill.recompute_content_hash()`:

```python
from agr import Skill

skill = Skill.from_git("anthropics/skills/code-review")
if skill.content_hash != skill.recompute_content_hash():
    print("Skill files have changed since install")
```

---

## 0.7.8 — 2026-03-02

### Interactive onboarding

New command: `agr onboard`. Walks you through setting up agr in an existing
project — tool selection, skill discovery, migration, and configuration — all
interactively.

```bash
agr onboard
```

If you used `agr init --interactive` before, that flag has been removed. Use
`agr onboard` instead.

### Quiet mode

Suppress all non-error output with `--quiet` / `-q`:

```bash
agr sync -q          # Silent sync (errors still print)
agr add user/skill -q
```

### Simplified `agr init`

`agr init` now only creates `agr.toml` and auto-detects your tools. Interactive
setup, skill discovery, and migration moved to `agr onboard`.

---

## 0.7.7 — 2026-03-02

### Bug fixes

- `agr config` commands with `--global` no longer require a git repository
- `agr config edit` works with editors that need flags (e.g., `EDITOR="code --wait"`)
- `agr config path --global` shows an error when no global config exists instead of printing a nonexistent path

---

## 0.7.6 — 2026-03-02

### Helpful handle suggestions

When a two-part handle like `agr add owner/repo` fails (because it's actually a
repo, not a skill in the default `skills` repo), agr now probes the repo and
suggests the correct three-part handles:

```
Skill 'my-repo' not found. However, 'owner/my-repo' exists as a repository with 3 skill(s):
  agr add owner/my-repo/skill-a
  agr add owner/my-repo/skill-b
  agr add owner/my-repo/skill-c
```

---

## 0.7.5 — 2026-02-07

### `agr config` command

New unified config management:

```bash
agr config show                # View config
agr config set tools claude codex opencode
agr config set default_tool claude
agr config add sources gitlab --type git --url "https://gitlab.com/{owner}/{repo}.git"
agr config unset default_tool
```

Replaces the older `agr tools` commands (which still work but show deprecation
warnings).

### Global installs

Install skills globally (available in all projects) with the `-g` flag:

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

agr now supports [Antigravity](https://docs.google.com/document/d/1KWjbSVr7YLJ8HSvNdJfUt7pNMa3Z0hMH8TE-DhRxO2E) as a tool target:

```bash
agr config add tools antigravity
```

Skills install to `.agent/skills/` (project) and `~/.gemini/antigravity/skills/` (global).

---

## 0.7.3 — 2026-02-04

### Default repo name change

Two-part handles (`user/skill`) now look in the `skills` repo by default instead
of `agent-resources`. During a deprecation period, agr falls back to
`agent-resources` with a warning if the skill isn't found in `skills`.

---

## 0.7.2 — 2026-02-02

### Python SDK

Use agr as a library:

```python
from agr import Skill, list_skills, skill_info, cache

skill = Skill.from_git("anthropics/skills/code-review")
print(skill.prompt)
print(skill.files)
```

See the [Python SDK documentation](sdk.md) for the full API.

### OpenCode support

agr now supports [OpenCode](https://opencode.ai) as a tool target with
`.opencode/skills/` install path.

---

## 0.7.1 — 2026-01-29

### Flat skill naming

Flat tools (Claude, Codex, OpenCode, Copilot, Antigravity) now install skills
using plain names (`skill-name/`) instead of the full handle
(`user--repo--skill/`). Existing installs are auto-migrated during `agr sync`.

### Instruction file syncing

Keep `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` in sync across tools:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr sync   # Copies CLAUDE.md content to AGENTS.md, GEMINI.md as needed
```

---

## 0.7.0 — 2026-01-27

### Multi-tool support

Skills can now be installed to multiple AI tools simultaneously. Configure your
tools in `agr.toml`:

```toml
tools = ["claude", "cursor", "codex"]
```

`agr add` and `agr sync` install to all configured tools at once. If an install
fails partway through, already-installed copies are rolled back automatically.

### Cursor support

agr now supports [Cursor](https://cursor.com) with nested directory structure
(`.cursor/skills/username/skill/`).

### GitHub Copilot support

agr now supports [GitHub Copilot](https://github.com/features/copilot) with
flat directory structure (`.github/skills/` for project, `~/.copilot/skills/`
for global).

### Private repository support

Set `GITHUB_TOKEN` or `GH_TOKEN` to access private skill repositories:

```bash
export GITHUB_TOKEN="ghp_your_token"
agr add private-org/skills/internal-tool
```

See [Private Repositories](configuration.md#private-repositories) for details.
