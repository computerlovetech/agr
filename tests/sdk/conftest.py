"""Test fixtures for SDK tests."""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import init_git_repo


@pytest.fixture
def mock_skill_dir(tmp_path: Path) -> Path:
    """Create a valid skill directory for testing."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
---

# Test Skill

A test skill for unit tests.

## Instructions

Do something useful.
""")
    (skill_dir / "helper.py").write_text("# Helper file\nprint('hello')\n")
    return skill_dir


@pytest.fixture
def mock_github_repo(tmp_path: Path) -> Path:
    """Create a local git repo mimicking GitHub structure.

    Structure:
        repo/
        ├── .git/
        ├── skills/
        │   └── my-skill/
        │       └── SKILL.md
        └── README.md
    """
    repo_dir = tmp_path / "mock-repo"
    repo_dir.mkdir()

    init_git_repo(repo_dir)

    # Create skill
    skill_dir = repo_dir / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: my-skill
---

# My Skill

This is a test skill.

## When to use

Use this for testing.
""")

    # Create README
    (repo_dir / "README.md").write_text("# Mock Repo\n\nA test repository.\n")

    # Commit
    subprocess.run(
        ["git", "add", "."],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )

    return repo_dir


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture
def skill_in_cache(cache_dir: Path) -> tuple[Path, dict]:
    """Pre-populate cache with a skill.

    Returns:
        Tuple of (skill_path, metadata)
    """
    # Create cache structure
    skill_cache = (
        cache_dir
        / "skills"
        / "github"
        / "testowner"
        / "testrepo"
        / "testskill"
        / "abc123"
    )
    skill_cache.mkdir(parents=True)

    (skill_cache / "SKILL.md").write_text("""---
name: testskill
---

# Test Skill

Cached test skill.
""")

    metadata = {
        "owner": "testowner",
        "repo": "testrepo",
        "skill": "testskill",
        "revision": "abc123",
    }

    return skill_cache, metadata
