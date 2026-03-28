---
title: "agr Python SDK — Load, Discover, and Cache AI Agent Skills Programmatically"
description: Use agr as a Python library to load skills from GitHub or local paths, discover skills in repositories, manage the download cache, and handle errors.
keywords:
  - agr Python SDK
  - agr Python library
  - load skill from GitHub Python
  - Skill.from_git
  - list_skills API
  - skill_info API
  - agr cache management
  - programmatic skill loading
  - AI agent skill discovery
---

# Python SDK

!!! tldr
    `pip install agr` and use `Skill.from_git("owner/repo/skill")` to load
    skills programmatically. Discover skills with `list_skills()`, manage the
    cache with `cache.clear()`, and handle errors via `AgrError` subclasses.

**Prerequisites:** Python 3.10+

Use `agr` as a Python library to load, inspect, and cache [skills](concepts.md#skills) programmatically.

**What is a skill?** A folder containing a `SKILL.md` file with YAML frontmatter
(`name`, `description`) and markdown instructions for an AI coding agent. Skills
work across Claude Code, Cursor, Codex, OpenCode, GitHub Copilot, and
Antigravity. A **handle** like `"anthropics/skills/code-review"` points to a
skill directory inside a GitHub repo.

## Install the agr package

```bash
pip install agr   # As a library dependency in your project
```

!!! tip
    If you want the `agr` and [`agrx`](agrx.md) CLI tools (not just the SDK), install with `uv tool install agr` or `pipx install agr` instead. See the [Tutorial](tutorial.md) for a full walkthrough.

## Load a skill in 3 lines

```python
from agr import Skill

# Load a skill from GitHub
skill = Skill.from_git("anthropics/skills/code-review")
print(skill.prompt)   # Contents of SKILL.md
print(skill.files)    # List of files in the skill directory

# Load a local skill
skill = Skill.from_local("./my-skill")
print(skill.prompt)
```

## Load skills from GitHub or local paths

### From GitHub

`Skill.from_git()` downloads a skill from GitHub and caches it locally using a
[handle](concepts.md#handles) to identify the skill. On subsequent calls, agr
checks the remote HEAD commit — if the cached revision matches, it returns the
cached copy without re-downloading.

```python
from agr import Skill

# Short handle (looks in user's "skills" repo)
skill = Skill.from_git("kasperjunge/commit")

# Explicit repo
skill = Skill.from_git("anthropics/skills/code-review")

# Force re-download even if cached (useful after upstream changes)
skill = Skill.from_git("kasperjunge/commit", force_download=True)

# Private repos — set GITHUB_TOKEN or GH_TOKEN in your environment
# export GITHUB_TOKEN="ghp_..."
skill = Skill.from_git("my-org/private-repo/internal-skill")
```

!!! note "Private repositories"
    `from_git()` uses the same `GITHUB_TOKEN` / `GH_TOKEN` environment
    variables as the CLI. See [Private Repositories](configuration.md#private-repositories)
    for token setup.

### From a Local Directory

`Skill.from_local()` loads a skill from a local path. The directory must contain a `SKILL.md` file (see [Creating Skills](creating.md) for the expected structure).

```python
skill = Skill.from_local("./my-skill")
skill = Skill.from_local("/absolute/path/to/skill")
```

## Skill properties and metadata

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Skill name (directory name) |
| `path` | `Path` | Path to skill directory (cached or local) |
| `handle` | `ParsedHandle \| None` | Parsed handle with owner, repo, and name components |
| `source` | `str \| None` | Source name the skill was fetched from (e.g., `"github"`) |
| `revision` | `str \| None` | Git commit hash (first 12 chars) of the fetched revision |
| `prompt` | `str` | Contents of `SKILL.md` (lazy-loaded on first access) |
| `files` | `list[str]` | Relative file paths in the skill directory (lazy-loaded on first access) |
| `metadata` | `dict` | Combined metadata dict (see below) |
| `content_hash` | `str \| None` | Content hash from `.agr.json`, if present |

The `handle`, `source`, and `revision` attributes are set by `from_git()`. For
locally loaded skills, `source` and `revision` are `None`.

### Provenance: handle, source, revision

When you load a skill from GitHub, agr records where it came from:

```python
skill = Skill.from_git("anthropics/skills/code-review")

# Which repo was it fetched from?
print(skill.source)    # "github"
print(skill.revision)  # "a1b2c3d4e5f6" (short commit hash)

# Access handle components
print(skill.handle.username)  # "anthropics"
print(skill.handle.repo)      # "skills"
print(skill.handle.name)      # "code-review"
```

### The metadata dict

The `metadata` property returns a dict combining all provenance info:

```python
skill = Skill.from_git("anthropics/skills/code-review")
print(skill.metadata)
# {
#     "name": "code-review",
#     "path": "/Users/you/.cache/agr/skills/anthropics/skills/code-review/a1b2c3d4e5f6",
#     "source": "github",
#     "revision": "a1b2c3d4e5f6",
#     "handle": "anthropics/skills/code-review",
#     "is_local": False,
# }
```

### Reading Files

```python
skill = Skill.from_git("anthropics/skills/code-review")

# Read any file in the skill directory
content = skill.read_file("scripts/lint.sh")
```

Path traversal is blocked — paths containing `..` or resolving outside the skill directory raise `ValueError`.

### Recomputing Content Hash

```python
# Compare stored hash with current files on disk
stored = skill.content_hash
current = skill.recompute_content_hash()
if stored != current:
    print("Skill files have changed")
```

## Discover skills in a repository

### List all skills in a repo

```python
from agr import list_skills

# List all skills in a repo
skills = list_skills("anthropics/skills")
for info in skills:
    print(f"{info.handle}: {info.name}")

# List skills in a user's default "skills" repo
skills = list_skills("kasperjunge")
```

!!! note "`list_skills()` does not fetch descriptions"
    `list_skills()` discovers skills from the repository tree without downloading
    each `SKILL.md`. The `description` field on returned `SkillInfo` objects is
    `None`. To get the description for a specific skill, use `skill_info()`.

### Get details for a single skill

`skill_info()` fetches the skill's `SKILL.md` to extract its description (first
body paragraph after frontmatter, up to 200 chars):

```python
from agr import skill_info

info = skill_info("anthropics/skills/code-review")
print(info.name)         # "code-review"
print(info.handle)       # "anthropics/skills/code-review"
print(info.description)  # First body paragraph from SKILL.md
print(info.owner)        # "anthropics"
print(info.repo)         # "skills"
```

Both functions use the GitHub API and respect `GITHUB_TOKEN` / `GH_TOKEN` environment variables for authentication. See [Troubleshooting](troubleshooting.md) if you hit rate limits or auth errors.

## Manage the download cache

Downloaded skills are cached in `~/.cache/agr/skills/` (also used by the [CLI](reference.md)). The `cache` object provides inspection and cleanup.

```python
from agr import cache

# Cache location
print(cache.path)  # ~/.cache/agr

# Cache statistics
info = cache.info()
print(info["skills_count"])  # Number of cached skills
print(info["size_bytes"])    # Total size in bytes

# Clear all cached skills
deleted = cache.clear()

# Clear specific skills (glob pattern)
deleted = cache.clear("anthropics/skills/*")
deleted = cache.clear("kasperjunge/*/*")
```

## Handle errors with AgrError subclasses

All SDK errors inherit from `AgrError`, including network failures. Catch
specific subclasses for targeted handling, or catch `AgrError` as a fallback
for any SDK error (including network issues like DNS failures and timeouts):

```python
from agr import Skill, list_skills, skill_info
from agr.exceptions import (
    AgrError,
    InvalidHandleError,
    InvalidLocalPathError,
    SkillNotFoundError,
    RepoNotFoundError,
    AuthenticationError,
    RateLimitError,
    CacheError,
)

try:
    skill = Skill.from_git("nonexistent/skill")
except SkillNotFoundError:
    print("Skill not found in repository")
except RepoNotFoundError:
    print("Repository does not exist")
except AuthenticationError:
    print("Set GITHUB_TOKEN for private repos")
except RateLimitError:
    print("GitHub API rate limit exceeded")
except AgrError as e:
    print(f"Unexpected error: {e}")  # Network failures, etc.

try:
    skill = Skill.from_local("./missing-skill")
except InvalidLocalPathError:
    print("Path does not exist or is missing SKILL.md")

try:
    skills = list_skills("not a valid handle/a/b")
except InvalidHandleError:
    print("Bad repo handle format")

try:
    info = skill_info("owner/nonexistent-skill")
except SkillNotFoundError:
    print("Skill not found in that repo")
```

!!! tip "Network errors are `AgrError`, not `ConnectionError`"
    Network failures (DNS resolution, timeouts, connection refused) in
    `list_skills()`, `skill_info()`, and `Skill.from_git()` raise `AgrError`
    — not Python's built-in `ConnectionError`. If your code catches `AgrError`
    (or its subclasses), network errors are included automatically.

## Type definitions

### `ParsedHandle`

Returned by `skill.handle`:

```python
@dataclass
class ParsedHandle:
    username: str | None   # GitHub username (None for local skills)
    repo: str | None       # Repository name (None = default "skills" repo)
    name: str              # Skill name (final segment of the handle)
    is_local: bool         # True for local path references
    local_path: Path | None  # Original local path (if is_local)
```

`ParsedHandle` also has an `is_remote` property that returns `True` for GitHub references.

### `SkillInfo`

Returned by `list_skills()` and `skill_info()`:

```python
@dataclass
class SkillInfo:
    name: str              # Skill name
    handle: str            # Full handle (e.g., "owner/repo/skill")
    description: str | None  # First body paragraph from SKILL.md (None from list_skills, populated from skill_info)
    repo: str              # Repository name
    owner: str             # GitHub owner/username
```

---

## Next Steps

- [**Creating Skills**](creating.md) — build your own skills to load with the SDK
- [**Core Concepts**](concepts.md) — understand handles, sources, and the sync lifecycle
- [**CLI Reference**](reference.md) — manage skills from the command line instead of Python
