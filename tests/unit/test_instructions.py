"""Unit tests for agr.instructions module."""

from pathlib import Path

from agr.instructions import (
    canonical_instruction_file,
    detect_instruction_files,
    sync_instruction_files,
)


class TestCanonicalInstructionFile:
    """Tests for canonical_instruction_file()."""

    def test_claude_tool(self) -> None:
        assert canonical_instruction_file("claude") == "CLAUDE.md"

    def test_cursor_tool(self) -> None:
        assert canonical_instruction_file("cursor") == "AGENTS.md"

    def test_codex_tool(self) -> None:
        assert canonical_instruction_file("codex") == "AGENTS.md"

    def test_copilot_tool(self) -> None:
        assert canonical_instruction_file("copilot") == "AGENTS.md"

    def test_opencode_tool(self) -> None:
        assert canonical_instruction_file("opencode") == "AGENTS.md"

    def test_antigravity_tool(self) -> None:
        assert canonical_instruction_file("antigravity") == "GEMINI.md"

    def test_unknown_tool_returns_agents_md(self) -> None:
        assert canonical_instruction_file("nonexistent") == "AGENTS.md"


class TestDetectInstructionFiles:
    """Tests for detect_instruction_files()."""

    def test_no_files_present(self, tmp_path: Path) -> None:
        assert detect_instruction_files(tmp_path) == []

    def test_only_claude_md(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("content")
        assert detect_instruction_files(tmp_path) == ["CLAUDE.md"]

    def test_only_agents_md(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("content")
        assert detect_instruction_files(tmp_path) == ["AGENTS.md"]

    def test_only_gemini_md(self, tmp_path: Path) -> None:
        (tmp_path / "GEMINI.md").write_text("content")
        assert detect_instruction_files(tmp_path) == ["GEMINI.md"]

    def test_all_files_present(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("a")
        (tmp_path / "AGENTS.md").write_text("b")
        (tmp_path / "GEMINI.md").write_text("c")
        assert detect_instruction_files(tmp_path) == [
            "AGENTS.md",
            "CLAUDE.md",
            "GEMINI.md",
        ]

    def test_preserves_order(self, tmp_path: Path) -> None:
        (tmp_path / "GEMINI.md").write_text("g")
        (tmp_path / "CLAUDE.md").write_text("c")
        result = detect_instruction_files(tmp_path)
        assert result == ["CLAUDE.md", "GEMINI.md"]

    def test_ignores_unrelated_files(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("readme")
        (tmp_path / "CLAUDE.md").write_text("claude")
        assert detect_instruction_files(tmp_path) == ["CLAUDE.md"]


class TestSyncInstructionFiles:
    """Tests for sync_instruction_files()."""

    def test_creates_missing_files(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("instructions here")
        updated = sync_instruction_files(tmp_path, "CLAUDE.md", ["AGENTS.md", "GEMINI.md"])
        assert updated == ["AGENTS.md", "GEMINI.md"]
        assert (tmp_path / "AGENTS.md").read_text() == "instructions here"
        assert (tmp_path / "GEMINI.md").read_text() == "instructions here"

    def test_updates_differing_files(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("new content")
        (tmp_path / "AGENTS.md").write_text("old content")
        updated = sync_instruction_files(tmp_path, "CLAUDE.md", ["AGENTS.md"])
        assert updated == ["AGENTS.md"]
        assert (tmp_path / "AGENTS.md").read_text() == "new content"

    def test_skips_already_synced_files(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("same content")
        (tmp_path / "AGENTS.md").write_text("same content")
        updated = sync_instruction_files(tmp_path, "CLAUDE.md", ["AGENTS.md"])
        assert updated == []

    def test_skips_canonical_file_in_targets(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("content")
        updated = sync_instruction_files(
            tmp_path, "CLAUDE.md", ["CLAUDE.md", "AGENTS.md"]
        )
        assert updated == ["AGENTS.md"]

    def test_returns_empty_when_canonical_missing(self, tmp_path: Path) -> None:
        updated = sync_instruction_files(tmp_path, "CLAUDE.md", ["AGENTS.md"])
        assert updated == []
        assert not (tmp_path / "AGENTS.md").exists()

    def test_empty_targets_list(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("content")
        updated = sync_instruction_files(tmp_path, "CLAUDE.md", [])
        assert updated == []

    def test_mixed_create_update_skip(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("canonical")
        (tmp_path / "AGENTS.md").write_text("canonical")  # already synced
        (tmp_path / "GEMINI.md").write_text("outdated")  # needs update
        # "OTHER.md" doesn't exist — needs creation
        updated = sync_instruction_files(
            tmp_path, "CLAUDE.md", ["AGENTS.md", "GEMINI.md", "OTHER.md"]
        )
        assert updated == ["GEMINI.md", "OTHER.md"]
        assert (tmp_path / "GEMINI.md").read_text() == "canonical"
        assert (tmp_path / "OTHER.md").read_text() == "canonical"
