"""Tests for agr.skill module."""

import pytest

from agr.skill import (
    SKILL_MARKER,
    create_skill_scaffold,
    discover_skills_in_repo,
    discover_skills_in_repo_listing,
    find_skill_in_repo,
    is_valid_skill_dir,
    update_skill_md_name,
    validate_skill_name,
)


class TestIsValidSkillDir:
    """Tests for is_valid_skill_dir function."""

    def test_valid_skill(self, tmp_path):
        """Directory with SKILL.md is valid."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / SKILL_MARKER).write_text("# Skill")
        assert is_valid_skill_dir(skill_dir)

    def test_missing_marker(self, tmp_path):
        """Directory without SKILL.md is not valid."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        assert not is_valid_skill_dir(skill_dir)

    def test_file_not_dir(self, tmp_path):
        """File is not valid."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        assert not is_valid_skill_dir(file_path)

    def test_nonexistent(self, tmp_path):
        """Nonexistent path is not valid."""
        assert not is_valid_skill_dir(tmp_path / "nonexistent")


class TestValidateSkillName:
    """Tests for validate_skill_name function."""

    def test_valid_simple(self):
        """Simple alphanumeric name is valid."""
        assert validate_skill_name("commit")

    def test_valid_with_hyphen(self):
        """Name with hyphens is valid."""
        assert validate_skill_name("my-skill")

    def test_valid_with_underscore(self):
        """Name with underscores is valid."""
        assert validate_skill_name("my_skill")

    def test_valid_with_numbers(self):
        """Name with numbers is valid."""
        assert validate_skill_name("skill123")

    def test_invalid_empty(self):
        """Empty name is invalid."""
        assert not validate_skill_name("")

    def test_invalid_starts_with_hyphen(self):
        """Name starting with hyphen is invalid."""
        assert not validate_skill_name("-skill")

    def test_invalid_starts_with_number(self):
        """Name starting with number is valid (alphanumeric)."""
        # Actually this should be valid per the regex
        assert validate_skill_name("1skill")

    def test_invalid_special_chars(self):
        """Name with special characters is invalid."""
        assert not validate_skill_name("skill!")
        assert not validate_skill_name("skill@name")


class TestUpdateSkillMdName:
    """Tests for update_skill_md_name function."""

    def test_update_existing_name(self, tmp_path):
        """Update existing name field."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / SKILL_MARKER
        skill_md.write_text("""---
name: old-name
---

# Content
""")
        update_skill_md_name(skill_dir, "new-name")
        content = skill_md.read_text()
        assert "name: new-name" in content
        assert "old-name" not in content

    def test_add_name_to_frontmatter(self, tmp_path):
        """Add name to existing frontmatter."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / SKILL_MARKER
        skill_md.write_text("""---
description: A skill
---

# Content
""")
        update_skill_md_name(skill_dir, "new-name")
        content = skill_md.read_text()
        assert "name: new-name" in content
        assert "description: A skill" in content

    def test_add_frontmatter_if_missing(self, tmp_path):
        """Add frontmatter if missing."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / SKILL_MARKER
        skill_md.write_text("# Content only")

        update_skill_md_name(skill_dir, "new-name")
        content = skill_md.read_text()
        assert content.startswith("---")
        assert "name: new-name" in content
        assert "# Content only" in content

    def test_missing_skill_md_does_nothing(self, tmp_path):
        """Missing SKILL.md doesn't raise."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        # Should not raise
        update_skill_md_name(skill_dir, "new-name")


class TestCreateSkillScaffold:
    """Tests for create_skill_scaffold function."""

    def test_creates_directory(self, tmp_path):
        """Creates skill directory."""
        skill_path = create_skill_scaffold("my-skill", tmp_path)
        assert skill_path.exists()
        assert skill_path.is_dir()
        assert skill_path.name == "my-skill"

    def test_creates_skill_md(self, tmp_path):
        """Creates SKILL.md with scaffold."""
        skill_path = create_skill_scaffold("my-skill", tmp_path)
        skill_md = skill_path / SKILL_MARKER
        assert skill_md.exists()
        content = skill_md.read_text()
        assert "name: my-skill" in content
        assert "# my-skill" in content

    def test_invalid_name_raises(self, tmp_path):
        """Invalid name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid skill name"):
            create_skill_scaffold("-invalid", tmp_path)

    def test_existing_dir_raises(self, tmp_path):
        """Existing directory raises FileExistsError."""
        (tmp_path / "existing").mkdir()
        with pytest.raises(FileExistsError):
            create_skill_scaffold("existing", tmp_path)


class TestFindSkillInRepo:
    """Tests for find_skill_in_repo function."""

    def test_finds_skill_at_root(self, tmp_path):
        """Finds skill directory at repo root."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "my-skill")
        assert result == skill_dir

    def test_finds_skill_in_skills_dir(self, tmp_path):
        """Finds skill in skills/ subdirectory."""
        skills_dir = tmp_path / "skills" / "commit"
        skills_dir.mkdir(parents=True)
        (skills_dir / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "commit")
        assert result == skills_dir

    def test_finds_skill_deeply_nested(self, tmp_path):
        """Finds skill in deeply nested directory."""
        nested = tmp_path / "resources" / "custom" / "skills" / "deep-skill"
        nested.mkdir(parents=True)
        (nested / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "deep-skill")
        assert result == nested

    def test_returns_none_when_not_found(self, tmp_path):
        """Returns None when skill not found."""
        result = find_skill_in_repo(tmp_path, "nonexistent")
        assert result is None

    def test_excludes_git_directory(self, tmp_path):
        """Excludes .git directory from search."""
        git_skill = tmp_path / ".git" / "hooks" / "my-skill"
        git_skill.mkdir(parents=True)
        (git_skill / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "my-skill")
        assert result is None

    def test_excludes_node_modules(self, tmp_path):
        """Excludes node_modules directory from search."""
        node_skill = tmp_path / "node_modules" / "some-package" / "my-skill"
        node_skill.mkdir(parents=True)
        (node_skill / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "my-skill")
        assert result is None

    def test_excludes_pycache(self, tmp_path):
        """Excludes __pycache__ directory from search."""
        cache_skill = tmp_path / "__pycache__" / "my-skill"
        cache_skill.mkdir(parents=True)
        (cache_skill / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "my-skill")
        assert result is None

    def test_excludes_venv(self, tmp_path):
        """Excludes .venv and venv directories from search."""
        for venv_name in [".venv", "venv"]:
            venv_skill = tmp_path / venv_name / "lib" / "my-skill"
            venv_skill.mkdir(parents=True)
            (venv_skill / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "my-skill")
        assert result is None

    def test_excludes_root_level_skill_md(self, tmp_path):
        """Excludes SKILL.md at repo root (not in a subdirectory)."""
        # Create a SKILL.md directly in repo root
        (tmp_path / SKILL_MARKER).write_text("# Root skill")

        # The repo dir name itself might match, but should be excluded
        result = find_skill_in_repo(tmp_path, tmp_path.name)
        assert result is None

    def test_prefers_shallowest_match(self, tmp_path):
        """Returns shallowest match when duplicates exist."""
        # Create skill at two depths
        shallow = tmp_path / "my-skill"
        shallow.mkdir()
        (shallow / SKILL_MARKER).write_text("# Shallow")

        deep = tmp_path / "nested" / "dir" / "my-skill"
        deep.mkdir(parents=True)
        (deep / SKILL_MARKER).write_text("# Deep")

        result = find_skill_in_repo(tmp_path, "my-skill")
        assert result == shallow

    def test_requires_directory_name_match(self, tmp_path):
        """Only matches when directory name equals skill name."""
        skill_dir = tmp_path / "actual-skill"
        skill_dir.mkdir()
        (skill_dir / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(tmp_path, "other-name")
        assert result is None

    def test_excluded_dir_name_in_parent_path_does_not_affect_discovery(self, tmp_path):
        """Excluded dir names in parent path don't cause false exclusions."""
        # Simulate a repo inside a directory whose name matches EXCLUDED_DIRS
        repo_dir = tmp_path / "build" / "project"
        skill_dir = repo_dir / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MARKER).write_text("# Skill")

        result = find_skill_in_repo(repo_dir, "my-skill")
        assert result == skill_dir


class TestDiscoverSkillsInRepoListing:
    """Tests for discover_skills_in_repo_listing function."""

    def test_discovers_single_skill(self):
        """Discovers a single skill from file listing."""
        paths = ["skills/commit/SKILL.md"]
        assert discover_skills_in_repo_listing(paths) == ["commit"]

    def test_discovers_multiple_skills(self):
        """Discovers multiple skills from file listing."""
        paths = [
            "skills/alpha/SKILL.md",
            "skills/gamma/SKILL.md",
            "skills/beta/SKILL.md",
        ]
        result = discover_skills_in_repo_listing(paths)
        assert result == ["alpha", "beta", "gamma"]

    def test_excludes_root_level_skill_md(self):
        """Excludes SKILL.md at repo root."""
        paths = ["SKILL.md", "skills/real-skill/SKILL.md"]
        assert discover_skills_in_repo_listing(paths) == ["real-skill"]

    def test_excludes_git_directory(self):
        """Excludes .git directory."""
        paths = [".git/hooks/my-skill/SKILL.md", "skills/valid/SKILL.md"]
        assert discover_skills_in_repo_listing(paths) == ["valid"]

    def test_excludes_node_modules(self):
        """Excludes node_modules directory."""
        paths = ["node_modules/pkg/my-skill/SKILL.md", "skills/valid/SKILL.md"]
        assert discover_skills_in_repo_listing(paths) == ["valid"]

    def test_returns_empty_for_no_skills(self):
        """Returns empty list when no skills found."""
        paths = ["README.md", "src/main.py"]
        assert discover_skills_in_repo_listing(paths) == []

    def test_returns_empty_for_empty_input(self):
        """Returns empty list for empty input."""
        assert discover_skills_in_repo_listing([]) == []

    def test_deduplicates_same_name(self):
        """Returns unique names when same skill name at multiple paths."""
        paths = [
            "skills/commit/SKILL.md",
            "nested/skills/commit/SKILL.md",
        ]
        assert discover_skills_in_repo_listing(paths) == ["commit"]

    def test_nested_paths(self):
        """Discovers skills in nested directories."""
        paths = ["resources/custom/skills/deep-skill/SKILL.md"]
        assert discover_skills_in_repo_listing(paths) == ["deep-skill"]


class TestDiscoverSkillsInRepo:
    """Tests for discover_skills_in_repo function."""

    def test_discovers_single_skill(self, tmp_path):
        """Discovers a single skill."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / SKILL_MARKER).write_text("# Skill")

        result = discover_skills_in_repo(tmp_path)
        assert len(result) == 1
        assert result[0] == ("my-skill", skill_dir)

    def test_discovers_multiple_skills(self, tmp_path):
        """Discovers multiple skills."""
        for name in ["alpha", "beta", "gamma"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / SKILL_MARKER).write_text(f"# {name}")

        result = discover_skills_in_repo(tmp_path)
        assert len(result) == 3
        names = [name for name, _ in result]
        assert names == ["alpha", "beta", "gamma"]  # Sorted alphabetically

    def test_discovers_nested_skills(self, tmp_path):
        """Discovers skills in nested directories."""
        nested = tmp_path / "resources" / "skills" / "nested-skill"
        nested.mkdir(parents=True)
        (nested / SKILL_MARKER).write_text("# Nested")

        result = discover_skills_in_repo(tmp_path)
        assert len(result) == 1
        assert result[0][0] == "nested-skill"

    def test_returns_empty_when_no_skills(self, tmp_path):
        """Returns empty list when no skills found."""
        result = discover_skills_in_repo(tmp_path)
        assert result == []

    def test_excludes_git_directory(self, tmp_path):
        """Excludes .git directory from discovery."""
        git_skill = tmp_path / ".git" / "my-skill"
        git_skill.mkdir(parents=True)
        (git_skill / SKILL_MARKER).write_text("# Skill")

        result = discover_skills_in_repo(tmp_path)
        assert result == []

    def test_excludes_node_modules(self, tmp_path):
        """Excludes node_modules from discovery."""
        node_skill = tmp_path / "node_modules" / "pkg" / "my-skill"
        node_skill.mkdir(parents=True)
        (node_skill / SKILL_MARKER).write_text("# Skill")

        result = discover_skills_in_repo(tmp_path)
        assert result == []

    def test_deduplicates_by_name(self, tmp_path):
        """Returns only one entry per skill name."""
        # Create same skill name at two locations
        shallow = tmp_path / "my-skill"
        shallow.mkdir()
        (shallow / SKILL_MARKER).write_text("# Shallow")

        deep = tmp_path / "nested" / "my-skill"
        deep.mkdir(parents=True)
        (deep / SKILL_MARKER).write_text("# Deep")

        result = discover_skills_in_repo(tmp_path)
        assert len(result) == 1
        assert result[0][0] == "my-skill"
        # Should prefer shallowest
        assert result[0][1] == shallow

    def test_results_sorted_alphabetically(self, tmp_path):
        """Results are sorted by skill name."""
        for name in ["zebra", "apple", "mango"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / SKILL_MARKER).write_text(f"# {name}")

        result = discover_skills_in_repo(tmp_path)
        names = [name for name, _ in result]
        assert names == ["apple", "mango", "zebra"]

    def test_excludes_root_level_skill_md(self, tmp_path):
        """Excludes SKILL.md directly at repo root."""
        (tmp_path / SKILL_MARKER).write_text("# Root")

        result = discover_skills_in_repo(tmp_path)
        assert result == []

    def test_mixed_valid_and_excluded(self, tmp_path):
        """Discovers valid skills while excluding invalid locations."""
        # Valid skill
        valid = tmp_path / "valid-skill"
        valid.mkdir()
        (valid / SKILL_MARKER).write_text("# Valid")

        # Excluded locations
        for excluded in [".git/hooks/git-skill", "node_modules/pkg/node-skill"]:
            excluded_dir = tmp_path / excluded
            excluded_dir.mkdir(parents=True)
            (excluded_dir / SKILL_MARKER).write_text("# Excluded")

        result = discover_skills_in_repo(tmp_path)
        assert len(result) == 1
        assert result[0][0] == "valid-skill"

    def test_excluded_dir_name_in_parent_path_does_not_affect_discovery(self, tmp_path):
        """Excluded dir names in parent path don't cause false exclusions."""
        repo_dir = tmp_path / "dist" / "project"
        skill_dir = repo_dir / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MARKER).write_text("# Skill")

        result = discover_skills_in_repo(repo_dir)
        assert len(result) == 1
        assert result[0][0] == "my-skill"
