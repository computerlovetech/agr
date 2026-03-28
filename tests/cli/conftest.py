"""Fixtures for CLI tests."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.cli.runner import run_cli
from tests.conftest import init_git_repo


def pytest_configure(config):
    """Register CLI test markers."""
    config.addinivalue_line(
        "markers", "requires_cli(name): skip test if CLI tool is not installed"
    )
    config.addinivalue_line(
        "markers",
        "network: marks tests as requiring network access "
        "(deselect with '-m \"not network\"')",
    )


def pytest_runtest_setup(item):
    """Skip tests that require unavailable CLI tools."""
    for marker in item.iter_markers(name="requires_cli"):
        cli_name = marker.args[0]
        if shutil.which(cli_name) is None:
            pytest.skip(f"Test requires '{cli_name}' CLI which is not installed")


@pytest.fixture
def cli_project(tmp_path: Path) -> Path:
    """Create a temporary git project directory."""
    project = tmp_path / "project"
    project.mkdir()

    init_git_repo(project)

    return project


@pytest.fixture
def cli_skill(cli_project: Path) -> Path:
    """Create a test skill in the project."""
    skill_dir = cli_project / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
---

# Test Skill

A test skill for CLI testing.
""")
    return skill_dir


@pytest.fixture
def cli_config(cli_project: Path):
    """Factory fixture to create agr.toml with custom content."""

    def _create_config(content: str = "dependencies = []"):
        config_path = cli_project / "agr.toml"
        config_path.write_text(content)
        return config_path

    return _create_config


@pytest.fixture
def git_source_repo(tmp_path: Path):
    """Create a local git repo with a skill for testing sources."""
    base_dir = tmp_path / "sources"
    base_dir.mkdir(parents=True, exist_ok=True)

    def _create_repo(
        owner: str = "acme",
        repo: str = "tools",
        skill_name: str = "test-skill",
        body: str = "Source Skill",
        base: Path | None = None,
    ) -> Path:
        root = base or base_dir
        repo_dir = root / owner / repo
        repo_dir.mkdir(parents=True, exist_ok=True)
        init_git_repo(repo_dir)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=repo_dir,
            capture_output=True,
            check=True,
        )

        skill_dir = repo_dir / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"""---
name: {skill_name}
---

# {skill_name}

{body}
"""
        )
        subprocess.run(
            ["git", "add", "."], cwd=repo_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo_dir,
            capture_output=True,
            check=True,
        )
        return repo_dir

    return base_dir, _create_repo


@pytest.fixture
def agr(cli_project: Path):
    """Helper to run agr commands in the project."""

    def _run(*args: str, **kwargs):
        return run_cli(["agr", *args], cwd=cli_project, **kwargs)

    return _run


@pytest.fixture
def agrx(cli_project: Path):
    """Helper to run agrx commands in the project."""

    def _run(*args: str, **kwargs):
        return run_cli(["agrx", *args], cwd=cli_project, **kwargs)

    return _run
