"""Unit tests for agr.detect module."""

from agr.detect import detect_tools
from agr.tool import TOOLS


class TestDetectionSignals:
    """Tests that detection signals are configured on all tools."""

    def test_all_tools_have_detection_signals(self):
        """Every registered tool must define at least one detection signal."""
        for name, tool in TOOLS.items():
            assert tool.detection_signals, f"Tool '{name}' has no detection_signals"


class TestDetectTools:
    """Tests for detect_tools()."""

    def test_no_signals_returns_empty(self, tmp_path):
        """detect_tools returns [] when no signals are present."""
        assert detect_tools(tmp_path) == []

    def test_single_signal_detected(self, tmp_path):
        """detect_tools finds a tool when one signal exists."""
        (tmp_path / ".claude").mkdir()

        result = detect_tools(tmp_path)

        assert result == ["claude"]

    def test_multiple_tools_detected(self, tmp_path):
        """detect_tools finds multiple tools from their signals."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".codex").mkdir()

        result = detect_tools(tmp_path)

        assert "claude" in result
        assert "cursor" in result
        assert "codex" in result

    def test_codex_detected_from_agents_dir(self, tmp_path):
        """detect_tools finds codex from .agents/ directory."""
        (tmp_path / ".agents").mkdir()

        result = detect_tools(tmp_path)

        assert "codex" in result

    def test_codex_detected_from_legacy_codex_dir(self, tmp_path):
        """detect_tools still finds codex from legacy .codex/ directory."""
        (tmp_path / ".codex").mkdir()

        result = detect_tools(tmp_path)

        assert "codex" in result

    def test_file_signal_detected(self, tmp_path):
        """detect_tools detects tools from file signals (not just dirs)."""
        (tmp_path / "CLAUDE.md").write_text("# Instructions")

        result = detect_tools(tmp_path)

        assert "claude" in result

    def test_nested_signal_detected(self, tmp_path):
        """detect_tools detects tools from nested path signals."""
        (tmp_path / ".github" / "copilot").mkdir(parents=True)

        result = detect_tools(tmp_path)

        assert "copilot" in result

    def test_opencode_detected_from_opencode_dir(self, tmp_path):
        """detect_tools finds opencode from .opencode/ directory."""
        (tmp_path / ".opencode").mkdir()

        result = detect_tools(tmp_path)

        assert "opencode" in result

    def test_opencode_detected_from_opencode_json(self, tmp_path):
        """detect_tools finds opencode from opencode.json config file."""
        (tmp_path / "opencode.json").write_text("{}")

        result = detect_tools(tmp_path)

        assert "opencode" in result

    def test_opencode_detected_from_opencode_jsonc(self, tmp_path):
        """detect_tools finds opencode from opencode.jsonc config file."""
        (tmp_path / "opencode.jsonc").write_text("{}")

        result = detect_tools(tmp_path)

        assert "opencode" in result

    def test_antigravity_detected_from_gemini_dir(self, tmp_path):
        """detect_tools finds antigravity from .gemini/ directory."""
        (tmp_path / ".gemini").mkdir()

        result = detect_tools(tmp_path)

        assert "antigravity" in result

    def test_antigravity_detected_from_agents_dir(self, tmp_path):
        """detect_tools finds antigravity from .agents/ directory (shared with Codex)."""
        (tmp_path / ".agents").mkdir()

        result = detect_tools(tmp_path)

        assert "antigravity" in result

    def test_cursor_detected_from_cursorrules_file(self, tmp_path):
        """detect_tools finds cursor from legacy .cursorrules file."""
        (tmp_path / ".cursorrules").write_text("rules here")

        result = detect_tools(tmp_path)

        assert "cursor" in result

    def test_copilot_detected_from_github_skills_dir(self, tmp_path):
        """detect_tools finds copilot from .github/skills/ directory."""
        (tmp_path / ".github" / "skills").mkdir(parents=True)

        result = detect_tools(tmp_path)

        assert "copilot" in result

    def test_copilot_detected_from_copilot_instructions_md(self, tmp_path):
        """detect_tools finds copilot from .github/copilot-instructions.md."""
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "copilot-instructions.md").write_text("# Instructions")

        result = detect_tools(tmp_path)

        assert "copilot" in result

    def test_copilot_detected_from_github_instructions_dir(self, tmp_path):
        """detect_tools finds copilot from .github/instructions/ directory."""
        (tmp_path / ".github" / "instructions").mkdir(parents=True)

        result = detect_tools(tmp_path)

        assert "copilot" in result

    def test_all_tools_detectable(self, tmp_path):
        """Every registered tool can be detected from at least one signal."""
        # Create first detection signal for each tool
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".agents").mkdir()
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".github" / "copilot").mkdir(parents=True)
        (tmp_path / ".gemini").mkdir()

        result = detect_tools(tmp_path)

        for tool_name in TOOLS:
            assert tool_name in result, f"Tool '{tool_name}' not detected"
