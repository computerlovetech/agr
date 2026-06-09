"""CLI tests for agr sync command."""

from tests.cli.assertions import assert_cli


class TestAgrSync:
    """Tests for agr sync command."""

    def test_sync_no_config_message(self, agr):
        """agr sync without config shows message."""
        result = agr("sync")

        assert_cli(result).succeeded().stdout_contains("No agr.toml")

    def test_sync_empty_deps_message(self, agr, cli_config):
        """agr sync with empty deps shows message."""
        cli_config("dependencies = []")

        result = agr("sync")

        assert_cli(result).succeeded().stdout_contains("Nothing to sync")

    def test_sync_reports_up_to_date(self, agr, cli_project, cli_skill):
        """agr sync reports already installed skills."""
        agr("add", "./skills/test-skill")

        result = agr("sync")

        assert_cli(result).succeeded().stdout_contains("up to date")

    def test_sync_instructions(self, agr, cli_project, cli_config):
        """agr sync syncs instruction files when configured."""
        (cli_project / "CLAUDE.md").write_text("Claude instructions\n")
        (cli_project / "AGENTS.md").write_text("Agents instructions\n")
        cli_config(
            """
tools = ["claude", "codex"]
sync_instructions = true
dependencies = []
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        assert (cli_project / "AGENTS.md").read_text() == (
            cli_project / "CLAUDE.md"
        ).read_text()

    def test_sync_instructions_creates_agents_for_pi(
        self, agr, cli_project, cli_config
    ):
        """agr sync creates AGENTS.md from CLAUDE.md when pi is configured."""
        (cli_project / "CLAUDE.md").write_text("Claude instructions\n")
        cli_config(
            """
tools = ["claude", "pi"]
sync_instructions = true
canonical_instructions = "CLAUDE.md"
dependencies = []
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        assert (cli_project / "AGENTS.md").exists()
        assert (cli_project / "AGENTS.md").read_text() == "Claude instructions\n"

    def test_sync_instructions_creates_agents_for_cursor(
        self, agr, cli_project, cli_config
    ):
        """agr sync creates AGENTS.md from CLAUDE.md when only CLAUDE.md exists."""
        (cli_project / "CLAUDE.md").write_text("Claude instructions\n")
        cli_config(
            """
tools = ["claude", "cursor"]
sync_instructions = true
canonical_instructions = "CLAUDE.md"
dependencies = []
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()
        assert (cli_project / "AGENTS.md").exists()
        assert (cli_project / "AGENTS.md").read_text() == "Claude instructions\n"


class TestAgrSyncRewritesShorthandHandles:
    """Tests that sync rewrites 2-part handles to their resolved 3-part form."""

    def test_sync_rewrite_preserves_user_comments(
        self, agr, cli_project, git_source_repo
    ):
        """Rewriting a shorthand handle must not destroy user comments.

        ``agr sync`` is expected to be minimally invasive; users who
        hand-edit agr.toml to add pinning notes or custom ordering
        shouldn't lose that content just because sync happened to
        rewrite a dependency's repo.
        """
        base_dir, create_repo = git_source_repo
        create_repo(owner="acme", repo="skills", skill_name="test-skill")

        config_path = cli_project / "agr.toml"
        config_path.write_text(
            f"""# my custom header comment
default_source = "local"
tools = ["claude"]

# deps the team relies on
dependencies = [
    # pinned because we want the latest
    {{handle = "acme/test-skill", type = "skill"}},
]

[[source]]
name = "local"
type = "git"
url = "{base_dir.as_posix()}/{{owner}}/{{repo}}"
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()

        content = config_path.read_text()
        assert "my custom header comment" in content
        assert "deps the team relies on" in content
        assert "pinned because we want the latest" in content
        # The rewrite itself still happened.
        assert "acme/skills/test-skill" in content

    def test_sync_rewrites_shorthand_handle_in_toml(
        self, agr, cli_project, git_source_repo
    ):
        """agr sync promotes owner/name to owner/repo/name in agr.toml.

        Simulates an existing agr.toml written before fully-resolved
        handles were recorded: a shorthand 2-part handle with the actual
        skill living in the default ``skills`` repo. Sync must rewrite
        the handle to ``owner/skills/name`` so later syncs don't rely on
        the default.
        """
        base_dir, create_repo = git_source_repo
        create_repo(owner="acme", repo="skills", skill_name="test-skill")

        config_path = cli_project / "agr.toml"
        config_path.write_text(
            f"""default_source = "local"
tools = ["claude"]
dependencies = [
    {{handle = "acme/test-skill", type = "skill"}},
]

[[source]]
name = "local"
type = "git"
url = "{base_dir.as_posix()}/{{owner}}/{{repo}}"
"""
        )

        result = agr("sync")

        assert_cli(result).succeeded()

        from agr.config import AgrConfig

        config = AgrConfig.load(config_path)
        dep = config.dependencies[0]
        assert dep.handle == "acme/skills/test-skill"


class TestAgrSyncRalph:
    """Tests for agr sync with ralph dependencies."""

    def test_sync_ralph_installs_from_config(
        self, agr, cli_project, cli_ralph, cli_config
    ):
        """agr sync installs ralph from agr.toml config."""
        cli_config('dependencies = [{path = "./ralphs/test-ralph", type = "ralph"}]')

        result = agr("sync")

        assert_cli(result).succeeded().stdout_contains("Installed:")
        installed = cli_project / ".agents" / "ralphs" / "test-ralph"
        assert installed.exists()
        assert (installed / "RALPH.md").exists()

    def test_sync_ralph_reports_up_to_date(self, agr, cli_project, cli_ralph):
        """agr sync reports already installed ralph as up to date."""
        agr("add", "./ralphs/test-ralph")

        result = agr("sync")

        assert_cli(result).succeeded().stdout_contains("up to date")
