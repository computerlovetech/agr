"""Tests for agr.tool module."""

from pathlib import Path

from agr.tool import (
    ANTIGRAVITY,
    CLAUDE,
    CODEX,
    COPILOT,
    CURSOR,
    OPENCODE,
    TOOLS,
    available_tools_string,
    build_global_skills_dirs,
    get_tool,
    lookup_skills_dir,
)


class TestToolConfig:
    """Tests for ToolConfig dataclass."""

    def test_tool_config_has_cli_command(self):
        """ToolConfig includes cli_command field."""
        assert CLAUDE.cli_command == "claude"
        assert CURSOR.cli_command == "agent"
        assert CODEX.cli_command == "codex"
        assert OPENCODE.cli_command == "opencode"
        assert COPILOT.cli_command == "copilot"
        assert ANTIGRAVITY.cli_command is None

    def test_tool_config_has_cli_flags(self):
        """ToolConfig includes CLI flag fields."""
        # Tools have prompt flag configuration
        assert CLAUDE.cli_prompt_flag == "-p"
        assert CURSOR.cli_prompt_flag == "-p"
        assert CODEX.cli_prompt_flag is None
        assert OPENCODE.cli_prompt_flag is None
        assert COPILOT.cli_prompt_flag == "-p"
        assert ANTIGRAVITY.cli_prompt_flag is None

        # Each tool has its own force flag
        assert CLAUDE.cli_force_flag == "--dangerously-skip-permissions"
        assert CURSOR.cli_force_flag is None
        assert CODEX.cli_force_flag == "--full-auto"
        assert OPENCODE.cli_force_flag is None
        assert COPILOT.cli_force_flag == "--allow-all-tools"
        assert ANTIGRAVITY.cli_force_flag is None

        # All tools have continue flag
        assert CLAUDE.cli_continue_flag == "--continue"
        assert CURSOR.cli_continue_flag == "--continue"
        assert CODEX.cli_continue_flag is None
        assert OPENCODE.cli_continue_flag == "--continue"
        assert COPILOT.cli_continue_flag == "--continue"
        assert ANTIGRAVITY.cli_continue_flag is None

    def test_tool_config_has_cli_commands(self):
        """ToolConfig includes CLI command fields."""
        assert CLAUDE.cli_exec_command is None
        assert CURSOR.cli_exec_command is None
        assert CODEX.cli_exec_command == ["codex", "exec"]
        assert OPENCODE.cli_exec_command == ["opencode", "run"]
        assert COPILOT.cli_exec_command is None
        assert ANTIGRAVITY.cli_exec_command is None

        assert CLAUDE.cli_continue_command is None
        assert CURSOR.cli_continue_command is None
        assert CODEX.cli_continue_command == ["codex", "resume", "--last"]
        assert OPENCODE.cli_continue_command is None
        assert COPILOT.cli_continue_command is None
        assert ANTIGRAVITY.cli_continue_command is None

    def test_tool_config_has_output_handling(self):
        """ToolConfig includes non-interactive output controls."""
        assert CLAUDE.suppress_stderr_non_interactive is False
        assert CURSOR.suppress_stderr_non_interactive is False
        assert CODEX.suppress_stderr_non_interactive is True
        assert OPENCODE.suppress_stderr_non_interactive is False
        assert COPILOT.suppress_stderr_non_interactive is False
        assert ANTIGRAVITY.suppress_stderr_non_interactive is False

    def test_tool_config_has_interactive_prompt_mode(self):
        """ToolConfig includes interactive prompt mode controls."""
        assert CLAUDE.cli_interactive_prompt_positional is True
        assert CURSOR.cli_interactive_prompt_positional is True
        assert CODEX.cli_interactive_prompt_positional is True
        assert OPENCODE.cli_interactive_prompt_positional is False
        assert COPILOT.cli_interactive_prompt_positional is False
        assert ANTIGRAVITY.cli_interactive_prompt_positional is False
        assert CLAUDE.cli_interactive_prompt_flag is None
        assert CURSOR.cli_interactive_prompt_flag is None
        assert CODEX.cli_interactive_prompt_flag is None
        assert OPENCODE.cli_interactive_prompt_flag == "--prompt"
        assert COPILOT.cli_interactive_prompt_flag == "-i"
        assert ANTIGRAVITY.cli_interactive_prompt_flag is None
        assert CLAUDE.skill_prompt_prefix == "/"
        assert CURSOR.skill_prompt_prefix == "/"
        assert CODEX.skill_prompt_prefix == "$"
        assert OPENCODE.skill_prompt_prefix == ""
        assert COPILOT.skill_prompt_prefix == "/"
        assert ANTIGRAVITY.skill_prompt_prefix == ""

    def test_tool_config_has_install_hint(self):
        """ToolConfig includes install_hint field."""
        assert CLAUDE.install_hint is not None
        assert CURSOR.install_hint is not None
        assert CODEX.install_hint is not None
        assert OPENCODE.install_hint is not None
        assert COPILOT.install_hint is not None
        assert ANTIGRAVITY.install_hint is None

    def test_all_tools_have_cli_config(self):
        """All registered tools have CLI configuration."""
        for name, tool_config in TOOLS.items():
            if tool_config.cli_command is None:
                assert tool_config.cli_prompt_flag is None
                assert tool_config.cli_force_flag is None
                assert tool_config.cli_continue_flag is None
                assert tool_config.cli_exec_command is None
                assert tool_config.cli_continue_command is None
                assert tool_config.install_hint is None
            else:
                assert tool_config.cli_command is not None, (
                    f"{name} missing cli_command"
                )
                if tool_config.cli_prompt_flag is not None:
                    assert tool_config.cli_prompt_flag, (
                        f"{name} missing cli_prompt_flag"
                    )
                if tool_config.cli_force_flag is not None:
                    assert tool_config.cli_force_flag, f"{name} missing cli_force_flag"
                if tool_config.cli_continue_flag is not None:
                    assert tool_config.cli_continue_flag, (
                        f"{name} missing cli_continue_flag"
                    )
                if tool_config.cli_exec_command is not None:
                    assert tool_config.cli_exec_command, (
                        f"{name} missing cli_exec_command"
                    )
                if tool_config.cli_continue_command is not None:
                    assert tool_config.cli_continue_command, (
                        f"{name} missing cli_continue_command"
                    )
                assert tool_config.install_hint is not None, (
                    f"{name} missing install_hint"
                )


class TestGetTool:
    """Tests for get_tool function."""

    def test_get_tool_returns_correct_config(self):
        """get_tool returns the correct ToolConfig."""
        assert get_tool("claude") == CLAUDE
        assert get_tool("cursor") == CURSOR
        assert get_tool("codex") == CODEX
        assert get_tool("opencode") == OPENCODE
        assert get_tool("copilot") == COPILOT
        assert get_tool("antigravity") == ANTIGRAVITY

    def test_get_tool_unknown_raises(self):
        """get_tool raises AgrError for unknown tool."""
        import pytest

        from agr.exceptions import AgrError

        with pytest.raises(AgrError, match="Unknown tool"):
            get_tool("unknown-tool")


class TestSkillsDirPaths:
    """Tests for project and global skills directory resolution.

    These lock down the exact paths each tool uses so that any drift from
    the upstream documentation is caught immediately.
    """

    def test_claude_project_skills_dir(self, tmp_path):
        assert CLAUDE.get_skills_dir(tmp_path) == tmp_path / ".claude" / "skills"

    def test_claude_global_skills_dir(self):
        assert CLAUDE.get_global_skills_dir() == Path.home() / ".claude" / "skills"

    def test_cursor_project_skills_dir(self, tmp_path):
        assert CURSOR.get_skills_dir(tmp_path) == tmp_path / ".cursor" / "skills"

    def test_cursor_global_skills_dir(self):
        assert CURSOR.get_global_skills_dir() == Path.home() / ".cursor" / "skills"

    def test_codex_project_skills_dir(self, tmp_path):
        assert CODEX.get_skills_dir(tmp_path) == tmp_path / ".agents" / "skills"

    def test_codex_global_skills_dir(self):
        assert CODEX.get_global_skills_dir() == Path.home() / ".agents" / "skills"

    def test_opencode_project_skills_dir(self, tmp_path):
        assert OPENCODE.get_skills_dir(tmp_path) == tmp_path / ".opencode" / "skills"

    def test_opencode_global_skills_dir(self):
        """OpenCode uses ~/.config/opencode/skills/ for personal skills."""
        assert OPENCODE.get_global_skills_dir() == (
            Path.home() / ".config" / "opencode" / "skills"
        )

    def test_copilot_project_skills_dir(self, tmp_path):
        assert COPILOT.get_skills_dir(tmp_path) == tmp_path / ".github" / "skills"

    def test_copilot_global_skills_dir(self):
        """Copilot uses ~/.copilot/skills/ (asymmetric from .github project path)."""
        assert COPILOT.get_global_skills_dir() == (Path.home() / ".copilot" / "skills")

    def test_antigravity_project_skills_dir(self, tmp_path):
        assert ANTIGRAVITY.get_skills_dir(tmp_path) == (tmp_path / ".gemini" / "skills")

    def test_antigravity_global_skills_dir(self):
        """Antigravity uses ~/.gemini/skills/ for personal skills."""
        assert ANTIGRAVITY.get_global_skills_dir() == (
            Path.home() / ".gemini" / "skills"
        )


class TestDetectionSignals:
    """Tests for tool detection signals.

    Each tool declares filesystem paths whose presence indicates the tool
    is in use. These tests lock down the exact values.
    """

    def test_claude_detection_signals(self):
        assert CLAUDE.detection_signals == (".claude", "CLAUDE.md")

    def test_cursor_detection_signals(self):
        assert CURSOR.detection_signals == (".cursor", ".cursorrules")

    def test_codex_detection_signals(self):
        assert CODEX.detection_signals == (".agents", ".codex")

    def test_opencode_detection_signals(self):
        assert OPENCODE.detection_signals == (
            ".opencode",
            "opencode.json",
            "opencode.jsonc",
        )

    def test_copilot_detection_signals(self):
        assert COPILOT.detection_signals == (
            ".github/copilot",
            ".github/skills",
            ".github/copilot-instructions.md",
            ".github/instructions",
        )

    def test_antigravity_detection_signals(self):
        assert ANTIGRAVITY.detection_signals == (".gemini", ".agents")


class TestInstructionFiles:
    """Tests for tool instruction file names."""

    def test_claude_instruction_file(self):
        assert CLAUDE.instruction_file == "CLAUDE.md"

    def test_cursor_instruction_file(self):
        assert CURSOR.instruction_file == "AGENTS.md"

    def test_codex_instruction_file(self):
        assert CODEX.instruction_file == "AGENTS.md"

    def test_opencode_instruction_file(self):
        assert OPENCODE.instruction_file == "AGENTS.md"

    def test_copilot_instruction_file(self):
        assert COPILOT.instruction_file == "AGENTS.md"

    def test_antigravity_instruction_file(self):
        assert ANTIGRAVITY.instruction_file == "GEMINI.md"


class TestUtilityFunctions:
    """Tests for tool module utility functions."""

    def test_available_tools_string_contains_all_tools(self):
        result = available_tools_string()
        for name in TOOLS:
            assert name in result

    def test_available_tools_string_is_comma_separated(self):
        result = available_tools_string()
        parts = [p.strip() for p in result.split(",")]
        assert set(parts) == set(TOOLS.keys())

    def test_lookup_skills_dir_returns_path_when_present(self):
        mapping = {"claude": Path("/some/path")}
        assert lookup_skills_dir(mapping, CLAUDE) == Path("/some/path")

    def test_lookup_skills_dir_returns_none_when_absent(self):
        mapping = {"cursor": Path("/other/path")}
        assert lookup_skills_dir(mapping, CLAUDE) is None

    def test_lookup_skills_dir_returns_none_when_mapping_is_none(self):
        assert lookup_skills_dir(None, CLAUDE) is None

    def test_build_global_skills_dirs(self):
        result = build_global_skills_dirs([CLAUDE, CODEX, COPILOT])
        assert result == {
            "claude": Path.home() / ".claude" / "skills",
            "codex": Path.home() / ".agents" / "skills",
            "copilot": Path.home() / ".copilot" / "skills",
        }
