"""CLI tests for agr.lock lockfile functionality."""

from agr.lockfile import load_lockfile
from tests.cli.assertions import assert_cli


class TestLockfileAdd:
    """Tests for lockfile updates during agr add."""

    def test_add_creates_lockfile(self, agr, cli_project, cli_skill):
        """agr add creates agr.lock alongside agr.toml."""
        agr("add", "./skills/test-skill")

        lockfile_path = cli_project / "agr.lock"
        assert lockfile_path.exists()

    def test_add_local_skill_lockfile_entry(self, agr, cli_project, cli_skill):
        """agr add for local skill creates lockfile entry with path, no commit."""
        agr("add", "./skills/test-skill")

        lockfile = load_lockfile(cli_project / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 1
        skill = lockfile.skills[0]
        assert skill.path == "./skills/test-skill"
        assert skill.installed_name == "test-skill"
        assert skill.commit is None
        assert skill.content_hash is None

    def test_add_preserves_existing_lockfile_entries(self, agr, cli_project, cli_skill):
        """Adding a second skill preserves the first in lockfile."""
        agr("add", "./skills/test-skill")

        # Create a second skill
        skill2 = cli_project / "skills" / "second-skill"
        skill2.mkdir(parents=True)
        (skill2 / "SKILL.md").write_text("---\nname: second-skill\n---\n# Second")

        agr("add", "./skills/second-skill")

        lockfile = load_lockfile(cli_project / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 2
        identifiers = {s.identifier for s in lockfile.skills}
        assert "./skills/test-skill" in identifiers
        assert "./skills/second-skill" in identifiers


class TestLockfileRemove:
    """Tests for lockfile updates during agr remove."""

    def test_remove_updates_lockfile(self, agr, cli_project, cli_skill):
        """agr remove removes the entry from agr.lock."""
        agr("add", "./skills/test-skill")
        agr("remove", "./skills/test-skill")

        lockfile = load_lockfile(cli_project / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 0

    def test_remove_preserves_other_entries(self, agr, cli_project, cli_skill):
        """agr remove only removes the specified skill from lockfile."""
        skill2 = cli_project / "skills" / "second-skill"
        skill2.mkdir(parents=True)
        (skill2 / "SKILL.md").write_text("---\nname: second-skill\n---\n# Second")

        agr("add", "./skills/test-skill")
        agr("add", "./skills/second-skill")
        agr("remove", "./skills/test-skill")

        lockfile = load_lockfile(cli_project / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].path == "./skills/second-skill"


class TestLockfileSync:
    """Tests for lockfile during agr sync."""

    def test_sync_creates_lockfile(self, agr, cli_project, cli_skill):
        """agr sync creates agr.lock when it doesn't exist."""
        agr("add", "./skills/test-skill")
        # Remove lockfile to test sync creates it
        (cli_project / "agr.lock").unlink()

        agr("sync")

        assert (cli_project / "agr.lock").exists()
        lockfile = load_lockfile(cli_project / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 1

    def test_sync_frozen_without_lockfile_fails(self, agr, cli_project, cli_config):
        """agr sync --frozen without lockfile fails."""
        cli_config('dependencies = [{path = "./skills/x", type = "skill"}]')

        result = agr("sync", "--frozen")

        assert_cli(result).failed().stdout_contains("No agr.lock")

    def test_sync_locked_without_lockfile_fails(self, agr, cli_project, cli_config):
        """agr sync --locked without lockfile fails."""
        cli_config('dependencies = [{path = "./skills/x", type = "skill"}]')

        result = agr("sync", "--locked")

        assert_cli(result).failed().stdout_contains("No agr.lock")

    def test_sync_locked_with_stale_lockfile_fails(self, agr, cli_project, cli_skill):
        """agr sync --locked fails when lockfile doesn't match agr.toml."""
        agr("add", "./skills/test-skill")

        # Create a second skill and add to config manually (without updating lockfile)
        skill2 = cli_project / "skills" / "second-skill"
        skill2.mkdir(parents=True)
        (skill2 / "SKILL.md").write_text("---\nname: second-skill\n---\n# Second")

        # Manually append a dependency to agr.toml without running agr add
        import tomlkit

        config_text = (cli_project / "agr.toml").read_text()
        doc = tomlkit.parse(config_text)
        dep = tomlkit.inline_table()
        dep["path"] = "./skills/second-skill"
        dep["type"] = "skill"
        doc["dependencies"].append(dep)
        (cli_project / "agr.toml").write_text(tomlkit.dumps(doc))

        result = agr("sync", "--locked")

        assert_cli(result).failed().stdout_contains("out of date")

    def test_sync_frozen_with_valid_lockfile_succeeds(
        self, agr, cli_project, cli_skill
    ):
        """agr sync --frozen with matching lockfile succeeds."""
        agr("add", "./skills/test-skill")

        # Remove the installed skill to force re-install
        import shutil

        shutil.rmtree(cli_project / ".claude" / "skills" / "test-skill")

        result = agr("sync", "--frozen")

        assert_cli(result).succeeded()
        # Skill should be re-installed
        assert (cli_project / ".claude" / "skills" / "test-skill").exists()

    def test_sync_frozen_and_locked_mutually_exclusive(
        self, agr, cli_project, cli_config
    ):
        """agr sync --frozen --locked fails."""
        cli_config("dependencies = []")

        result = agr("sync", "--frozen", "--locked")

        assert_cli(result).failed().stdout_contains("mutually exclusive")
