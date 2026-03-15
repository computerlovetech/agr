"""CLI tests for OpenCode tool support."""

from tests.cli.assertions import assert_cli


class TestOpencodeAdd:
    """Tests for agr add with OpenCode tool."""

    def test_add_local_skill_to_opencode_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add local skill installs to .opencode/skills/<name>/."""
        cli_config('tools = ["opencode"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".opencode" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()


class TestOpencodeSync:
    """Tests for agr sync with OpenCode tool."""

    def test_sync_installs_to_opencode_when_configured(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync with tools = ["opencode"] installs to correct path."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        installed = cli_project / ".opencode" / "skills" / "test-skill"
        assert installed.exists()

    def test_sync_creates_opencode_skills_directory(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync creates .opencode/skills/ if it doesn't exist."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        opencode_dir = cli_project / ".opencode"
        assert not opencode_dir.exists()

        result = agr("sync")

        assert_cli(result).succeeded()
        assert opencode_dir.exists()
        assert (opencode_dir / "skills" / "test-skill").exists()

    def test_sync_migrates_opencode_skill_to_skills(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync migrates skills from .opencode/skill/ to .opencode/skills/."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Pre-populate .opencode/skill/ with a skill
        old_skill_dir = cli_project / ".opencode" / "skill" / "test-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test skill.\n---\n# Test\n"
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        # Skill should be in new location
        new_skill_dir = cli_project / ".opencode" / "skills" / "test-skill"
        assert new_skill_dir.exists()
        assert (new_skill_dir / "SKILL.md").exists()
        # Old location should be cleaned up
        assert not old_skill_dir.exists()


class TestOpencodeMigration:
    """Tests for .opencode/skill/ -> .opencode/skills/ migration edge cases."""

    def test_sync_migration_conflict_preserves_old_skill(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """Old is preserved when both old and new dirs exist."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Pre-populate both old and new locations
        old_skill_dir = cli_project / ".opencode" / "skill" / "test-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Old\n")
        new_skill_dir = cli_project / ".opencode" / "skills" / "test-skill"
        new_skill_dir.mkdir(parents=True)
        (new_skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# New\n")

        result = agr("sync")

        assert_cli(result).succeeded()
        # Old skill should still be in old location (not moved)
        assert old_skill_dir.exists()
        assert (
            (old_skill_dir / "SKILL.md")
            .read_text()
            .startswith("---\nname: test-skill\n---\n# Old\n")
        )
        # New location should keep its content
        assert new_skill_dir.exists()
        # Output should warn about conflict
        assert "Cannot migrate" in result.stdout

    def test_sync_migration_cleans_up_empty_skill_subdir(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """After migration, .opencode/skill/ is removed but .opencode/ is kept."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        old_skill_dir = cli_project / ".opencode" / "skill" / "test-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Test\n")

        result = agr("sync")

        assert_cli(result).succeeded()
        # .opencode/skill/ should be cleaned up
        assert not (cli_project / ".opencode" / "skill").exists()
        # .opencode/ should still exist (it has skills/ now)
        assert (cli_project / ".opencode").exists()

    def test_sync_migration_warns_about_non_directory_files(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """Non-directory files in .opencode/skill/ produce a warning."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        old_skills_dir = cli_project / ".opencode" / "skill"
        old_skills_dir.mkdir(parents=True)
        # Create a regular file (not a skill directory)
        (old_skills_dir / "random-file.txt").write_text("not a skill")

        result = agr("sync")

        assert_cli(result).succeeded()
        # Should warn about leftover files
        assert "non-skill file(s) remain" in result.stdout
        # The file should still be there
        assert (old_skills_dir / "random-file.txt").exists()

    def test_add_migrates_opencode_skills_before_install(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add migrates .opencode/skill/ to .opencode/skills/ before installing."""
        cli_config('tools = ["opencode"]\ndependencies = []')
        # Pre-populate .opencode/skill/ with an existing skill
        old_skill_dir = cli_project / ".opencode" / "skill" / "existing-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text(
            "---\nname: existing-skill\n---\n# Existing\n"
        )

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        # Old skill should be migrated
        assert not old_skill_dir.exists()
        assert (
            cli_project / ".opencode" / "skills" / "existing-skill" / "SKILL.md"
        ).exists()
        # New skill should be installed
        assert (cli_project / ".opencode" / "skills" / "test-skill").exists()

    def test_remove_migrates_opencode_skills_before_uninstall(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove migrates .opencode/skill/ to .opencode/skills/ before removing."""
        cli_config(
            """
tools = ["opencode"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Install the skill first
        agr("sync")
        assert (cli_project / ".opencode" / "skills" / "test-skill").exists()

        # Simulate: move skill back to .opencode/skill/ (old)
        old_skills_dir = cli_project / ".opencode" / "skill"
        old_skills_dir.mkdir(parents=True)
        new_skill = cli_project / ".opencode" / "skills" / "test-skill"
        new_skill.rename(old_skills_dir / "test-skill")

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        # Migration moved to .opencode/skills/, then remove cleaned
        assert not (cli_project / ".opencode" / "skills" / "test-skill").exists()
        assert not (old_skills_dir / "test-skill").exists()


class TestMultiToolOpencodeClaude:
    """Tests for multi-tool scenarios with OpenCode and Claude."""

    def test_add_installs_to_both_claude_and_opencode(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add with tools = ["claude", "opencode"] installs to both."""
        cli_config('tools = ["claude", "opencode"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert (cli_project / ".claude" / "skills" / "test-skill").exists()
        assert (cli_project / ".opencode" / "skills" / "test-skill").exists()
