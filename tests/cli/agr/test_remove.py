"""CLI tests for agr remove command."""

from tests.cli.assertions import assert_cli


class TestAgrRemove:
    """Tests for agr remove command."""

    def test_remove_installed_skill_succeeds(self, agr, cli_project, cli_skill):
        """agr remove removes installed skill."""
        # First add the skill
        agr("add", "./skills/test-skill")

        # Then remove it
        result = agr("remove", "./skills/test-skill")

        assert_cli(result).succeeded().stdout_contains("Removed:")

    def test_remove_cleans_up_directory(self, agr, cli_project, cli_skill):
        """agr remove deletes installed directory."""
        agr("add", "./skills/test-skill")

        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()

        agr("remove", "./skills/test-skill")

        assert not installed.exists()

    def test_remove_updates_config(self, agr, cli_project, cli_skill):
        """agr remove updates agr.toml."""
        agr("add", "./skills/test-skill")
        agr("remove", "./skills/test-skill")

        config = (cli_project / "agr.toml").read_text()
        assert "skills/test-skill" not in config

    def test_remove_not_installed_fails(self, agr, cli_skill):
        """agr remove on non-installed skill fails."""
        result = agr("remove", "./skills/test-skill")

        assert_cli(result).failed()


class TestAgrRemoveRalph:
    """Tests for agr remove with ralph type."""

    def test_remove_ralph_succeeds(self, agr, cli_ralph):
        """agr remove removes installed ralph."""
        agr("add", "./ralphs/test-ralph")
        result = agr("remove", "./ralphs/test-ralph")
        assert_cli(result).succeeded().stdout_contains("Removed:")

    def test_remove_ralph_cleans_directory(self, agr, cli_project, cli_ralph):
        """agr remove deletes installed ralph directory."""
        agr("add", "./ralphs/test-ralph")
        installed = cli_project / ".agents" / "ralphs" / "test-ralph"
        assert installed.exists()

        agr("remove", "./ralphs/test-ralph")
        assert not installed.exists()

    def test_remove_ralph_updates_config(self, agr, cli_project, cli_ralph):
        """agr remove updates agr.toml."""
        agr("add", "./ralphs/test-ralph")
        agr("remove", "./ralphs/test-ralph")

        config = (cli_project / "agr.toml").read_text()
        assert "ralphs/test-ralph" not in config
