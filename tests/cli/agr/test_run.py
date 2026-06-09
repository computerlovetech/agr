"""CLI tests for agr run command."""

import shutil
from pathlib import Path

import pytest

from tests.cli.assertions import assert_cli
from tests.cli.runner import run_cli


def _install_skill(project: Path, tool_dir: str, name: str) -> Path:
    """Create an installed skill in <project>/<tool_dir>/skills/<name>/."""
    skill_dir = project / tool_dir / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n\n# {name}\n\nTest skill for agr run.\n"
    )
    return skill_dir


class TestAgrRunBasic:
    """Basic agr run tests (no external CLI required)."""

    def test_run_help(self):
        """agr run --help shows help."""
        result = run_cli(["agr", "run", "--help"])

        assert_cli(result).succeeded().stdout_contains("installed skill")

    def test_run_no_config_fails(self, agr):
        """agr run without agr.toml fails with helpful message."""
        result = agr("run", "some-skill")

        assert_cli(result).failed().stdout_contains("No agr.toml")

    def test_run_missing_skill_lists_available(self, agr, cli_config, cli_project):
        """agr run with unknown skill shows available skills."""
        cli_config('tools = ["claude"]\ndependencies = []')
        _install_skill(cli_project, ".claude", "real-skill")

        result = agr("run", "ghost-skill")

        assert_cli(result).failed().stdout_contains("not installed")
        assert_cli(result).stdout_contains("real-skill")

    def test_run_missing_skill_no_skills_installed(self, agr, cli_config, cli_project):
        """agr run with no installed skills suggests sync/add."""
        cli_config('tools = ["claude"]\ndependencies = []')

        result = agr("run", "ghost-skill")

        assert_cli(result).failed().stdout_contains("not installed")
        assert_cli(result).stdout_contains("agr sync")

    def test_run_invalid_tool_fails(self, agr, cli_config, cli_project):
        """agr run with invalid --tool fails."""
        cli_config('tools = ["claude"]\ndependencies = []')
        _install_skill(cli_project, ".claude", "real-skill")

        result = agr("run", "real-skill", "--tool", "nope")

        assert_cli(result).failed().stdout_contains("Unknown tool")

    def test_run_outside_git_repo_fails(self, tmp_path):
        """agr run outside a git repo fails."""
        result = run_cli(["agr", "run", "any-skill"], cwd=tmp_path)

        assert_cli(result).failed()

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_run_tool_cli_not_found(self, agr, cli_config, cli_project):
        """agr run reports a clear error when the tool's CLI is missing."""
        cli_config('tools = ["cursor"]\ndependencies = []')
        _install_skill(cli_project, ".cursor", "demo")

        result = agr("run", "demo")

        assert_cli(result).failed().stdout_contains("agent CLI not found")

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_run_uses_default_tool_from_config(self, agr, cli_config, cli_project):
        """agr run picks default_tool over first-in-tools list."""
        cli_config(
            'tools = ["claude", "cursor"]\ndefault_tool = "cursor"\ndependencies = []'
        )
        # Install skill only into cursor's dir to confirm default_tool is used.
        _install_skill(cli_project, ".cursor", "demo")

        result = agr("run", "demo")

        # Should pick cursor (default_tool); with agent CLI absent we expect
        # a clean "CLI not found" error, proving cursor (not claude) was chosen.
        assert_cli(result).failed().stdout_contains("agent CLI not found")

    @pytest.mark.skipif(
        shutil.which("agent") is not None, reason="agent CLI is installed"
    )
    def test_run_tool_flag_overrides_default(self, agr, cli_config, cli_project):
        """agr run --tool overrides config default."""
        cli_config('tools = ["claude", "cursor"]\ndependencies = []')
        _install_skill(cli_project, ".cursor", "demo")

        result = agr("run", "demo", "--tool", "cursor")

        assert_cli(result).failed().stdout_contains("agent CLI not found")
