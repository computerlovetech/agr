"""CLI tests for OpenAI Codex tool support."""

from tests.cli.assertions import assert_cli


class TestCodexAdd:
    """Tests for agr add with Codex tool."""

    def test_add_local_skill_to_codex_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add local skill installs to .agents/skills/<name>/."""
        cli_config('tools = ["codex"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".agents" / "skills" / "test-skill"
        assert installed.exists()
        assert (installed / "SKILL.md").exists()


class TestCodexSync:
    """Tests for agr sync with Codex tool."""

    def test_sync_installs_to_codex_when_configured(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync with tools = ["codex"] installs to correct path."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        installed = cli_project / ".agents" / "skills" / "test-skill"
        assert installed.exists()

    def test_sync_creates_codex_skills_directory(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync creates .agents/skills/ if it doesn't exist."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        agents_dir = cli_project / ".agents"
        assert not agents_dir.exists()

        result = agr("sync")

        assert_cli(result).succeeded()
        assert agents_dir.exists()
        assert (agents_dir / "skills" / "test-skill").exists()

    def test_sync_migrates_codex_skills_to_agents(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr sync migrates skills from .codex/skills/ to .agents/skills/."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Pre-populate .codex/skills/ with a skill
        old_skill_dir = cli_project / ".codex" / "skills" / "test-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test skill.\n---\n# Test\n"
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        # Skill should be in new location
        new_skill_dir = cli_project / ".agents" / "skills" / "test-skill"
        assert new_skill_dir.exists()
        assert (new_skill_dir / "SKILL.md").exists()
        # Old location should be cleaned up
        assert not old_skill_dir.exists()


class TestCodexRemove:
    """Tests for agr remove with Codex tool."""

    def test_remove_cleans_up_codex_flat_structure(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove removes skill from .agents/skills/."""
        cli_config('tools = ["codex"]\ndependencies = []')
        agr("add", "./skills/test-skill")

        installed = cli_project / ".agents" / "skills" / "test-skill"
        assert installed.exists()

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert not installed.exists()


class TestCodexMigration:
    """Tests for .codex/ -> .agents/ migration edge cases."""

    def test_sync_migration_conflict_preserves_old_skill(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """Old is preserved when both .codex and .agents dirs exist."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Pre-populate both old and new locations
        old_skill_dir = cli_project / ".codex" / "skills" / "test-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Old\n")
        new_skill_dir = cli_project / ".agents" / "skills" / "test-skill"
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

    def test_sync_migration_cleans_up_empty_codex_parent(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """After migration, both .codex/skills/ and .codex/ are removed when empty."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        old_skill_dir = cli_project / ".codex" / "skills" / "test-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Test\n")

        result = agr("sync")

        assert_cli(result).succeeded()
        # Both .codex/skills/ and .codex/ should be cleaned up
        assert not (cli_project / ".codex" / "skills").exists()
        assert not (cli_project / ".codex").exists()

    def test_sync_migration_warns_about_non_directory_files(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """Non-directory files in .codex/skills/ produce a warning."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        old_skills_dir = cli_project / ".codex" / "skills"
        old_skills_dir.mkdir(parents=True)
        # Create a regular file (not a skill directory)
        (old_skills_dir / "random-file.txt").write_text("not a skill")

        result = agr("sync")

        assert_cli(result).succeeded()
        # Should warn about leftover files
        assert "non-skill file(s) remain" in result.stdout
        # The file should still be there
        assert (old_skills_dir / "random-file.txt").exists()

    def test_add_migrates_codex_skills_before_install(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add migrates .codex/skills/ to .agents/skills/ before installing."""
        cli_config('tools = ["codex"]\ndependencies = []')
        # Pre-populate .codex/skills/ with an existing skill
        old_skill_dir = cli_project / ".codex" / "skills" / "existing-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text(
            "---\nname: existing-skill\n---\n# Existing\n"
        )

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        # Old skill should be migrated
        assert not old_skill_dir.exists()
        assert (
            cli_project / ".agents" / "skills" / "existing-skill" / "SKILL.md"
        ).exists()
        # New skill should be installed
        assert (cli_project / ".agents" / "skills" / "test-skill").exists()

    def test_remove_migrates_codex_skills_before_uninstall(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr remove migrates .codex/skills/ to .agents/skills/ before removing."""
        cli_config(
            """
tools = ["codex"]
dependencies = [
    { path = "./skills/test-skill", type = "skill" },
]
"""
        )
        # Install the skill first
        agr("sync")
        assert (cli_project / ".agents" / "skills" / "test-skill").exists()

        # Simulate: move skill back to .codex/ (old codex install)
        old_skills_dir = cli_project / ".codex" / "skills"
        old_skills_dir.mkdir(parents=True)
        new_skill = cli_project / ".agents" / "skills" / "test-skill"
        new_skill.rename(old_skills_dir / "test-skill")

        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded()
        # Migration moved to .agents/, then remove cleaned up
        assert not (cli_project / ".agents" / "skills" / "test-skill").exists()
        assert not (old_skills_dir / "test-skill").exists()


class TestMultiToolCodexClaude:
    """Tests for multi-tool scenarios with Codex and Claude."""

    def test_add_installs_to_both_claude_and_codex(
        self, agr, cli_project, cli_skill, cli_config
    ):
        """agr add with tools = ["claude", "codex"] installs to both."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []')

        result = agr("add", "./skills/test-skill")

        assert_cli(result).succeeded()
        assert (cli_project / ".claude" / "skills" / "test-skill").exists()
        assert (cli_project / ".agents" / "skills" / "test-skill").exists()
