"""Tests for agrx command construction."""

from agr.tool import CLAUDE, CODEX, COPILOT, CURSOR, OPENCODE
from agrx.main import _build_skill_command, _build_temp_skill_name


def test_build_skill_command_non_interactive_codex_exec():
    """Codex non-interactive uses exec subcommand with positional prompt."""
    cmd = _build_skill_command(CODEX, "$skill prompt", non_interactive=True)
    assert cmd == ["codex", "exec", "$skill prompt"]


def test_build_skill_command_interactive_claude_positional():
    """Claude interactive uses positional prompt."""
    cmd = _build_skill_command(CLAUDE, "/skill prompt", non_interactive=False)
    assert cmd == ["claude", "/skill prompt"]


def test_build_skill_command_interactive_copilot_flag():
    """Copilot interactive uses -i prompt flag."""
    cmd = _build_skill_command(COPILOT, "/skill prompt", non_interactive=False)
    assert cmd == ["copilot", "-i", "/skill prompt"]


def test_build_skill_command_non_interactive_cursor_flag():
    """Cursor non-interactive uses -p prompt flag."""
    cmd = _build_skill_command(CURSOR, "/skill prompt", non_interactive=True)
    assert cmd == ["agent", "-p", "/skill prompt"]


def test_build_temp_skill_name_prefix_and_suffix():
    """Temp skill name includes prefix, name, and unique suffix."""
    temp_name = _build_temp_skill_name("my-skill")
    assert temp_name.startswith("_agrx_my-skill-")


def test_build_temp_skill_name_unique():
    """Temp skill names are unique across calls."""
    first = _build_temp_skill_name("my-skill")
    second = _build_temp_skill_name("my-skill")
    assert first != second


def test_build_skill_command_non_interactive_opencode_run():
    """OpenCode non-interactive uses run subcommand with positional prompt."""
    cmd = _build_skill_command(OPENCODE, "skill prompt", non_interactive=True)
    assert cmd == ["opencode", "run", "skill prompt"]


def test_build_skill_command_interactive_opencode_uses_prompt_flag():
    """OpenCode interactive uses TUI with --prompt flag."""
    cmd = _build_skill_command(OPENCODE, "skill prompt", non_interactive=False)
    assert cmd == ["opencode", "--prompt", "skill prompt"]


def test_build_skill_command_non_interactive_claude_print_flag():
    """Claude non-interactive uses -p flag per CLI docs."""
    cmd = _build_skill_command(CLAUDE, "/skill prompt", non_interactive=True)
    assert cmd == ["claude", "-p", "/skill prompt"]


def test_build_skill_command_interactive_codex_positional():
    """Codex interactive falls back to positional prompt (no interactive flag)."""
    cmd = _build_skill_command(CODEX, "$skill prompt", non_interactive=False)
    assert cmd == ["codex", "$skill prompt"]


def test_build_skill_command_interactive_cursor_positional():
    """Cursor interactive uses positional prompt per CLI docs."""
    cmd = _build_skill_command(CURSOR, "/skill prompt", non_interactive=False)
    assert cmd == ["agent", "/skill prompt"]


def test_build_skill_command_non_interactive_copilot_print_flag():
    """Copilot non-interactive uses -p flag."""
    cmd = _build_skill_command(COPILOT, "/skill prompt", non_interactive=True)
    assert cmd == ["copilot", "-p", "/skill prompt"]
