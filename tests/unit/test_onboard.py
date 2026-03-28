"""Unit tests for agr.commands.onboard helper functions."""

from pathlib import Path

from agr.commands.onboard import (
    DiscoveredSkill,
    _parse_number_selection,
    format_dep_path,
    migrate_skill,
    select_skills,
)


class TestParseNumberSelection:
    """Tests for _parse_number_selection."""

    def test_empty_string(self):
        assert _parse_number_selection("", 5) == []

    def test_whitespace_only(self):
        assert _parse_number_selection("   ", 5) == []

    def test_single_number(self):
        assert _parse_number_selection("2", 5) == [2]

    def test_multiple_numbers(self):
        assert _parse_number_selection("1,3,5", 5) == [1, 3, 5]

    def test_numbers_with_spaces(self):
        assert _parse_number_selection(" 1 , 3 , 5 ", 5) == [1, 3, 5]

    def test_out_of_range_filtered(self):
        assert _parse_number_selection("0,1,6", 5) == [1]

    def test_negative_number_filtered(self):
        assert _parse_number_selection("-1,2", 5) == [2]

    def test_non_numeric_ignored(self):
        assert _parse_number_selection("1,abc,3", 5) == [1, 3]

    def test_duplicates_removed(self):
        assert _parse_number_selection("2,2,3,3", 5) == [2, 3]

    def test_preserves_first_occurrence_order(self):
        assert _parse_number_selection("3,1,2,1", 5) == [3, 1, 2]

    def test_trailing_comma(self):
        assert _parse_number_selection("1,2,", 5) == [1, 2]

    def test_leading_comma(self):
        assert _parse_number_selection(",1,2", 5) == [1, 2]

    def test_all_invalid(self):
        assert _parse_number_selection("abc,def", 5) == []

    def test_boundary_values(self):
        assert _parse_number_selection("1,5", 5) == [1, 5]

    def test_max_val_one(self):
        assert _parse_number_selection("1", 1) == [1]
        assert _parse_number_selection("2", 1) == []


class TestSelectSkills:
    """Tests for select_skills."""

    def _skill(self, name: str, path: str, tool: str | None = None) -> DiscoveredSkill:
        return DiscoveredSkill(name=name, path=Path(path), frontmatter_name=None, tool=tool)

    def test_empty_list(self):
        assert select_skills([]) == []

    def test_single_skill(self):
        skill = self._skill("my-skill", "/repo/skills/my-skill")
        result = select_skills([skill])
        assert len(result) == 1
        assert result[0].name == "my-skill"

    def test_no_duplicates_sorted(self):
        skills = [
            self._skill("zebra", "/repo/skills/zebra"),
            self._skill("alpha", "/repo/skills/alpha"),
        ]
        result = select_skills(skills)
        assert [s.name for s in result] == ["alpha", "zebra"]

    def test_dedup_keeps_shallowest(self):
        deep = self._skill("my-skill", "/repo/.claude/skills/my-skill", tool="claude")
        shallow = self._skill("my-skill", "/repo/skills/my-skill")
        result = select_skills([deep, shallow])
        assert len(result) == 1
        assert result[0].path == Path("/repo/skills/my-skill")

    def test_dedup_keeps_shallowest_reversed_input(self):
        """Order of input shouldn't matter."""
        shallow = self._skill("my-skill", "/repo/skills/my-skill")
        deep = self._skill("my-skill", "/repo/.claude/skills/my-skill", tool="claude")
        result = select_skills([shallow, deep])
        assert len(result) == 1
        assert result[0].path == Path("/repo/skills/my-skill")

    def test_multiple_groups_deduped(self):
        skills = [
            self._skill("a", "/repo/.claude/skills/a", tool="claude"),
            self._skill("a", "/repo/skills/a"),
            self._skill("b", "/repo/.cursor/skills/b", tool="cursor"),
            self._skill("b", "/repo/skills/b"),
        ]
        result = select_skills(skills)
        assert [s.name for s in result] == ["a", "b"]
        assert result[0].path == Path("/repo/skills/a")
        assert result[1].path == Path("/repo/skills/b")


class TestFormatDepPath:
    """Tests for format_dep_path."""

    def test_relative_path_gets_dot_prefix(self):
        result = format_dep_path(Path("/repo"), Path("/repo/skills/my-skill"))
        assert result == "./skills/my-skill"

    def test_dotfile_relative_no_double_prefix(self):
        # Path starting with a dotfile directory already starts with "."
        result = format_dep_path(Path("/repo"), Path("/repo/.claude/skills/my-skill"))
        assert result == ".claude/skills/my-skill"

    def test_path_outside_repo_returns_absolute(self):
        result = format_dep_path(Path("/repo"), Path("/other/skills/my-skill"))
        assert result == "/other/skills/my-skill"

    def test_skill_at_repo_root(self):
        result = format_dep_path(Path("/repo"), Path("/repo/my-skill"))
        assert result == "./my-skill"


class TestMigrateSkill:
    """Tests for migrate_skill."""

    def _skill(self, name: str, path: Path) -> DiscoveredSkill:
        return DiscoveredSkill(name=name, path=path, frontmatter_name=None, tool="claude")

    def test_copies_skill_to_destination(self, tmp_path):
        source = tmp_path / ".claude" / "skills" / "my-skill"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("# My Skill")

        skills_root = tmp_path / "skills"
        skill = self._skill("my-skill", source)
        result = migrate_skill(skill, skills_root)

        assert result == skills_root / "my-skill"
        assert (skills_root / "my-skill" / "SKILL.md").exists()
        assert (skills_root / "my-skill" / "SKILL.md").read_text() == "# My Skill"

    def test_returns_existing_valid_skill_dir(self, tmp_path):
        # Already exists as valid skill
        skills_root = tmp_path / "skills"
        dest = skills_root / "my-skill"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("# Existing")

        source = tmp_path / ".claude" / "skills" / "my-skill"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("# Source")

        skill = self._skill("my-skill", source)
        result = migrate_skill(skill, skills_root)

        assert result == dest
        # Should not overwrite
        assert (dest / "SKILL.md").read_text() == "# Existing"

    def test_returns_none_for_invalid_existing_dir(self, tmp_path):
        # Exists but not a valid skill (no SKILL.md)
        skills_root = tmp_path / "skills"
        dest = skills_root / "my-skill"
        dest.mkdir(parents=True)
        (dest / "README.md").write_text("Not a skill")

        source = tmp_path / ".claude" / "skills" / "my-skill"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("# Source")

        skill = self._skill("my-skill", source)
        result = migrate_skill(skill, skills_root)

        assert result is None

    def test_creates_parent_directories(self, tmp_path):
        source = tmp_path / ".claude" / "skills" / "my-skill"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("# My Skill")

        skills_root = tmp_path / "nested" / "skills"
        skill = self._skill("my-skill", source)
        result = migrate_skill(skill, skills_root)

        assert result is not None
        assert result == skills_root / "my-skill"
        assert result.exists()
