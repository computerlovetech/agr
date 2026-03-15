---
title: Python SDK
---

# Python SDK

Use `agr` as a Python library to load, inspect, and cache skills programmatically.

## Install

```bash
pip install agr   # As a library dependency in your project
```

!!! tip
    If you want the `agr` and `agrx` CLI tools (not just the SDK), install with `uv tool install agr` or `pipx install agr` instead.

## Quick Start

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

## Loading Skills

### From GitHub

`Skill.from_git()` downloads a skill from GitHub and caches it locally. On
subsequent calls, agr checks the remote HEAD commit — if the cached revision
matches, it returns the cached copy without re-downloading.

```python
from agr import Skill

# Short handle (looks in user's "skills" repo)
skill = Skill.from_git("kasperjunge/commit")

# Explicit repo
skill = Skill.from_git("anthropics/skills/code-review")

# Force re-download even if cached (useful after upstream changes)
skill = Skill.from_git("kasperjunge/commit", force_download=True)
```

### From a Local Directory

`Skill.from_local()` loads a skill from a local path. The directory must contain a `SKILL.md` file.

```python
skill = Skill.from_local("./my-skill")
skill = Skill.from_local("/absolute/path/to/skill")
```

## Skill Properties

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

## Discovering Skills

### List Skills in a Repository

```python
from agr import list_skills

# List all skills in a repo
skills = list_skills("anthropics/skills")
for info in skills:
    print(f"{info.handle}: {info.name}")

# List skills in a user's default "skills" repo
skills = list_skills("kasperjunge")
```

### Get Skill Details

```python
from agr import skill_info

info = skill_info("anthropics/skills/code-review")
print(info.name)         # "code-review"
print(info.handle)       # "anthropics/skills/code-review"
print(info.description)  # First paragraph from SKILL.md
print(info.owner)        # "anthropics"
print(info.repo)         # "skills"
```

Both functions use the GitHub API and respect `GITHUB_TOKEN` / `GH_TOKEN` environment variables for authentication.

## Cache Management

Downloaded skills are cached in `~/.cache/agr/skills/`. The `cache` object provides inspection and cleanup.

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

## Error Handling

All SDK errors inherit from `AgrError`:

```python
from agr import Skill
from agr.exceptions import (
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

try:
    skill = Skill.from_local("./missing-skill")
except InvalidLocalPathError:
    print("Path does not exist or is missing SKILL.md")
```

## Types

### `SkillInfo`

Returned by `list_skills()` and `skill_info()`:

```python
@dataclass
class SkillInfo:
    name: str              # Skill name
    handle: str            # Full handle (e.g., "owner/repo/skill")
    description: str | None  # First paragraph from SKILL.md
    repo: str              # Repository name
    owner: str             # GitHub owner/username
```
