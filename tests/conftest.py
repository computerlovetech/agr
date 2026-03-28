"""Test configuration and fixtures for agr v2."""

import os
import subprocess
from pathlib import Path

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring network")
    config.addinivalue_line("markers", "network: tests that make real network requests")


@pytest.fixture(autouse=True)
def skip_e2e_in_ci(request):
    """Auto-skip E2E tests in CI based on SKIP_E2E env var."""
    if request.node.get_closest_marker("e2e") and os.environ.get(
        "SKIP_E2E", ""
    ).lower() in ("1", "true", "yes"):
        pytest.skip("E2E tests skipped in CI (SKIP_E2E=1)")


def init_git_repo(path: Path) -> None:
    """Initialize a directory as a git repo with dummy user config."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def git_project(tmp_path: Path, monkeypatch):
    """Set up a temporary git project directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def skill_fixture(tmp_path: Path) -> Path:
    """Create a valid skill directory."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
---

# Test Skill

A test skill for unit tests.
""")
    return skill_dir
