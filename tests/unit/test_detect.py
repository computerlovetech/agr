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
