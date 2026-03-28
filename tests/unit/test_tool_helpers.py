"""Unit tests for agr.commands._tool_helpers module."""

import pytest

from agr.commands import CommandResult
from agr.commands._tool_helpers import (
    ToolAddResult,
    ToolRemoveResult,
    add_tools_to_config,
    delete_tool_skills,
    ensure_valid_default_tool,
    exit_if_sync_errors,
    normalize_and_validate_tool_names,
    normalize_tool_names,
    print_missing_config_hint,
    print_tool_add_result,
    print_tool_remove_result,
    remove_tools_from_config,
    save_and_summarize_results,
    validate_tool_names,
)
from agr.config import AgrConfig


class TestNormalizeToolNames:
    """Tests for normalize_tool_names()."""

    def test_lowercase_and_strip(self):
        assert normalize_tool_names(["  Claude ", "CURSOR"]) == ["claude", "cursor"]

    def test_empty_strings_removed(self):
        assert normalize_tool_names(["claude", "", "  "]) == ["claude"]

    def test_empty_list(self):
        assert normalize_tool_names([]) == []

    def test_already_normalized(self):
        assert normalize_tool_names(["claude", "cursor"]) == ["claude", "cursor"]


class TestValidateToolNames:
    """Tests for validate_tool_names()."""

    def test_valid_names_pass(self):
        validate_tool_names(["claude", "cursor", "codex"])

    def test_single_invalid_name_exits(self):
        with pytest.raises(SystemExit):
            validate_tool_names(["not-a-tool"])

    def test_mixed_valid_invalid_exits(self):
        with pytest.raises(SystemExit):
            validate_tool_names(["claude", "not-a-tool"])

    def test_empty_list_passes(self):
        validate_tool_names([])


class TestNormalizeAndValidateToolNames:
    """Tests for normalize_and_validate_tool_names()."""

    def test_normalizes_and_validates(self):
        result = normalize_and_validate_tool_names(["  Claude ", "CURSOR"])
        assert result == ["claude", "cursor"]

    def test_deduplicates(self):
        result = normalize_and_validate_tool_names(["claude", "Claude", "CLAUDE"])
        assert result == ["claude"]

    def test_empty_exits_by_default(self):
        with pytest.raises(SystemExit):
            normalize_and_validate_tool_names([])

    def test_empty_allowed_when_allow_empty(self):
        result = normalize_and_validate_tool_names([], allow_empty=True)
        assert result == []

    def test_only_whitespace_exits(self):
        with pytest.raises(SystemExit):
            normalize_and_validate_tool_names(["  ", ""])

    def test_invalid_tool_exits(self):
        with pytest.raises(SystemExit):
            normalize_and_validate_tool_names(["fake-tool"])

    def test_preserves_order(self):
        result = normalize_and_validate_tool_names(["cursor", "claude", "codex"])
        assert result == ["cursor", "claude", "codex"]


class TestAddToolsToConfig:
    """Tests for add_tools_to_config()."""

    def test_adds_new_tools(self):
        config = AgrConfig(tools=["claude"])
        result = add_tools_to_config(config, ["cursor", "codex"])

        assert result == ToolAddResult(added=["cursor", "codex"], skipped=[])
        assert config.tools == ["claude", "cursor", "codex"]

    def test_skips_existing_tools(self):
        config = AgrConfig(tools=["claude", "cursor"])
        result = add_tools_to_config(config, ["claude", "codex"])

        assert result == ToolAddResult(added=["codex"], skipped=["claude"])
        assert config.tools == ["claude", "cursor", "codex"]

    def test_all_already_configured(self):
        config = AgrConfig(tools=["claude", "cursor"])
        result = add_tools_to_config(config, ["claude", "cursor"])

        assert result == ToolAddResult(added=[], skipped=["claude", "cursor"])
        assert config.tools == ["claude", "cursor"]

    def test_empty_names_list(self):
        config = AgrConfig(tools=["claude"])
        result = add_tools_to_config(config, [])

        assert result == ToolAddResult(added=[], skipped=[])
        assert config.tools == ["claude"]


class TestRemoveToolsFromConfig:
    """Tests for remove_tools_from_config()."""

    def test_removes_configured_tool(self, tmp_path):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["cursor"], tmp_path)

        assert result.removed == ["cursor"]
        assert result.not_configured == []
        assert config.tools == ["claude"]

    def test_reports_not_configured(self, tmp_path):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["codex"], tmp_path)

        assert result.removed == []
        assert result.not_configured == ["codex"]
        assert config.tools == ["claude", "cursor"]

    def test_mixed_configured_and_not(self, tmp_path):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["cursor", "codex"], tmp_path)

        assert result.removed == ["cursor"]
        assert result.not_configured == ["codex"]

    def test_cannot_remove_all_tools(self, tmp_path):
        config = AgrConfig(tools=["claude"])
        with pytest.raises(SystemExit):
            remove_tools_from_config(config, ["claude"], tmp_path)

    def test_none_repo_root_skips_deletion(self):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["cursor"], None)

        assert result.removed == ["cursor"]
        assert config.tools == ["claude"]


class TestEnsureValidDefaultTool:
    """Tests for ensure_valid_default_tool()."""

    def test_keeps_valid_default(self):
        config = AgrConfig(tools=["claude", "cursor"])
        config.default_tool = "cursor"
        ensure_valid_default_tool(config, "cursor")

        assert config.default_tool == "cursor"

    def test_replaces_removed_default_with_first_tool(self, capsys):
        config = AgrConfig(tools=["claude"])
        config.default_tool = None
        ensure_valid_default_tool(config, "cursor")

        assert config.default_tool == "claude"
        captured = capsys.readouterr()
        assert "Default tool updated" in captured.out

    def test_noop_when_previous_default_was_none(self):
        config = AgrConfig(tools=["claude"])
        config.default_tool = None
        ensure_valid_default_tool(config, None)

        assert config.default_tool is None

    def test_unsets_when_no_tools_remain(self, capsys):
        config = AgrConfig(tools=[])
        config.default_tool = None
        ensure_valid_default_tool(config, "claude")

        assert config.default_tool is None
        captured = capsys.readouterr()
        assert "Default tool unset" in captured.out

    def test_noop_when_default_still_in_tools(self):
        config = AgrConfig(tools=["claude", "cursor"])
        config.default_tool = "claude"
        ensure_valid_default_tool(config, "claude")

        assert config.default_tool == "claude"


class TestToolAddResult:
    """Tests for ToolAddResult dataclass."""

    def test_equality(self):
        a = ToolAddResult(added=["claude"], skipped=["cursor"])
        b = ToolAddResult(added=["claude"], skipped=["cursor"])
        assert a == b

    def test_inequality(self):
        a = ToolAddResult(added=["claude"], skipped=[])
        b = ToolAddResult(added=[], skipped=["claude"])
        assert a != b


class TestToolRemoveResult:
    """Tests for ToolRemoveResult dataclass."""

    def test_equality(self):
        a = ToolRemoveResult(removed=["cursor"], not_configured=["codex"])
        b = ToolRemoveResult(removed=["cursor"], not_configured=["codex"])
        assert a == b

    def test_inequality(self):
        a = ToolRemoveResult(removed=["cursor"], not_configured=[])
        b = ToolRemoveResult(removed=[], not_configured=["cursor"])
        assert a != b


class TestSaveAndSummarizeResults:
    """Tests for save_and_summarize_results()."""

    def _noop_printer(self, result: CommandResult) -> None:
        pass

    def test_saves_config_when_successes(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [CommandResult("user/skill", True, "ok")]

        save_and_summarize_results(
            results, config, config_path,
            action="added", total=1, print_result=self._noop_printer,
        )

        assert config_path.exists()

    def test_does_not_save_config_when_all_failures(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [CommandResult("user/skill", False, "error")]

        with pytest.raises(SystemExit):
            save_and_summarize_results(
                results, config, config_path,
                action="added", total=1, print_result=self._noop_printer,
            )

        assert not config_path.exists()

    def test_exits_on_failure_by_default(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [CommandResult("user/skill", False, "error")]

        with pytest.raises(SystemExit):
            save_and_summarize_results(
                results, config, config_path,
                action="added", total=1, print_result=self._noop_printer,
            )

    def test_no_exit_when_exit_on_failure_false(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [CommandResult("user/skill", False, "error")]

        # Should not raise
        save_and_summarize_results(
            results, config, config_path,
            action="removed", total=1, print_result=self._noop_printer,
            exit_on_failure=False,
        )

    def test_calls_print_result_for_each(self, tmp_path):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [
            CommandResult("a", True, "ok"),
            CommandResult("b", False, "err"),
        ]
        printed: list[str] = []

        def capture(result: CommandResult) -> None:
            printed.append(result.ref)

        with pytest.raises(SystemExit):
            save_and_summarize_results(
                results, config, config_path,
                action="added", total=2, print_result=capture,
            )

        assert printed == ["a", "b"]

    def test_prints_summary_when_multiple_refs(self, tmp_path, capsys):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [
            CommandResult("a", True, "ok"),
            CommandResult("b", True, "ok"),
        ]

        save_and_summarize_results(
            results, config, config_path,
            action="added", total=2, print_result=self._noop_printer,
        )

        captured = capsys.readouterr()
        assert "2/2 skills added" in captured.out

    def test_no_summary_for_single_ref(self, tmp_path, capsys):
        config_path = tmp_path / "agr.toml"
        config = AgrConfig(tools=["claude"])
        results = [CommandResult("a", True, "ok")]

        save_and_summarize_results(
            results, config, config_path,
            action="added", total=1, print_result=self._noop_printer,
        )

        captured = capsys.readouterr()
        assert "Summary" not in captured.out


class TestDeleteToolSkills:
    """Tests for delete_tool_skills()."""

    def test_returns_true_when_repo_root_is_none(self):
        assert delete_tool_skills("claude", None) is True

    def test_returns_true_when_skills_dir_missing(self, tmp_path):
        assert delete_tool_skills("claude", tmp_path) is True

    def test_deletes_skills_directory(self, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "my-skill").mkdir()
        (skills_dir / "my-skill" / "SKILL.md").write_text("# Skill")

        result = delete_tool_skills("claude", tmp_path)

        assert result is True
        assert not skills_dir.exists()

    def test_reports_deleted_skill_count(self, tmp_path, capsys):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "skill-a").mkdir()
        (skills_dir / "skill-b").mkdir()

        delete_tool_skills("claude", tmp_path)

        captured = capsys.readouterr()
        assert "Deleted 2 skills" in captured.out


class TestExitIfSyncErrors:
    """Tests for exit_if_sync_errors()."""

    def test_no_errors_does_nothing(self):
        exit_if_sync_errors(0)

    def test_exits_on_nonzero_errors(self):
        with pytest.raises(SystemExit):
            exit_if_sync_errors(1)

    def test_prints_warning_on_errors(self, capsys):
        with pytest.raises(SystemExit):
            exit_if_sync_errors(3)

        captured = capsys.readouterr()
        assert "3 dependency sync(s) failed" in captured.out


class TestPrintMissingConfigHint:
    """Tests for print_missing_config_hint()."""

    def test_global_hint(self, capsys):
        print_missing_config_hint(global_install=True)

        captured = capsys.readouterr()
        assert "No global agr.toml found" in captured.out
        assert "agr add -g" in captured.out

    def test_local_hint(self, capsys):
        print_missing_config_hint(global_install=False)

        captured = capsys.readouterr()
        assert "No agr.toml found" in captured.out
        assert "agr init" in captured.out


class TestPrintToolAddResult:
    """Tests for print_tool_add_result()."""

    def test_prints_added_tools(self, capsys):
        result = ToolAddResult(added=["claude", "cursor"], skipped=[])
        print_tool_add_result(result)

        captured = capsys.readouterr()
        assert "claude" in captured.out
        assert "cursor" in captured.out

    def test_prints_skipped_tools(self, capsys):
        result = ToolAddResult(added=[], skipped=["claude"])
        print_tool_add_result(result)

        captured = capsys.readouterr()
        assert "Already configured" in captured.out
        assert "claude" in captured.out

    def test_prints_both_added_and_skipped(self, capsys):
        result = ToolAddResult(added=["cursor"], skipped=["claude"])
        print_tool_add_result(result)

        captured = capsys.readouterr()
        assert "cursor" in captured.out
        assert "Already configured" in captured.out


class TestPrintToolRemoveResult:
    """Tests for print_tool_remove_result()."""

    def test_prints_removed_tools(self, capsys):
        result = ToolRemoveResult(removed=["cursor"], not_configured=[])
        print_tool_remove_result(result)

        captured = capsys.readouterr()
        assert "cursor" in captured.out

    def test_prints_not_configured_tools(self, capsys):
        result = ToolRemoveResult(removed=[], not_configured=["codex"])
        print_tool_remove_result(result)

        captured = capsys.readouterr()
        assert "Not configured" in captured.out
        assert "codex" in captured.out
