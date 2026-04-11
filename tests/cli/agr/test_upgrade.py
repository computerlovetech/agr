"""CLI tests for agr upgrade command."""

from agr.config import AgrConfig
from agr.lockfile import load_lockfile
from tests.cli.assertions import assert_cli
from tests.cli.runner import run_cli


class TestAgrUpgrade:
    """Tests for agr upgrade command."""

    def test_upgrade_no_config_message(self, agr):
        """agr upgrade without config shows a friendly message."""
        result = agr("upgrade")

        assert_cli(result).succeeded().stdout_contains("No agr.toml")

    def test_upgrade_empty_deps_message(self, agr, cli_config):
        """agr upgrade with empty deps shows a friendly message."""
        cli_config("dependencies = []")

        result = agr("upgrade")

        assert_cli(result).succeeded().stdout_contains("Nothing to upgrade")

    def test_upgrade_all_refreshes_local_skill(self, agr, cli_project, cli_skill):
        """agr upgrade re-copies a local skill when its source changes."""
        agr("add", "./skills/test-skill")

        # Modify the source skill after install.
        (cli_skill / "SKILL.md").write_text("""---
name: test-skill
---

# Test Skill

Updated content after upgrade.
""")

        result = agr("upgrade")

        assert_cli(result).succeeded().stdout_contains("Installed:")
        installed = cli_project / ".claude" / "skills" / "test-skill" / "SKILL.md"
        assert "Updated content after upgrade" in installed.read_text()

    def test_upgrade_specific_handle_refreshes_only_one(self, agr, cli_project):
        """agr upgrade <handle> only refreshes the named dep."""
        # Create two local skills.
        for name, body in (("alpha", "Alpha v1"), ("beta", "Beta v1")):
            skill_dir = cli_project / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
---

# {name}

{body}
""")
            agr("add", f"./skills/{name}")

        # Bump both sources.
        for name, body in (("alpha", "Alpha v2"), ("beta", "Beta v2")):
            (cli_project / "skills" / name / "SKILL.md").write_text(f"""---
name: {name}
---

# {name}

{body}
""")

        result = agr("upgrade", "./skills/alpha")

        assert_cli(result).succeeded()
        alpha = (cli_project / ".claude" / "skills" / "alpha" / "SKILL.md").read_text()
        beta = (cli_project / ".claude" / "skills" / "beta" / "SKILL.md").read_text()
        assert "Alpha v2" in alpha
        assert "Beta v1" in beta  # unchanged

    def test_upgrade_bare_name_matches_installed_name(
        self, agr, cli_project, cli_skill
    ):
        """agr upgrade <short-name> resolves via installed_name."""
        agr("add", "./skills/test-skill")

        (cli_skill / "SKILL.md").write_text("""---
name: test-skill
---

# Test Skill

Refreshed via short name.
""")

        result = agr("upgrade", "test-skill")

        assert_cli(result).succeeded().stdout_contains("Installed:")
        installed = cli_project / ".claude" / "skills" / "test-skill" / "SKILL.md"
        assert "Refreshed via short name" in installed.read_text()

    def test_upgrade_ambiguous_short_name_errors(self, agr, cli_project, cli_config):
        """agr upgrade with an ambiguous short name fails with both full IDs."""
        for parent in ("one", "two"):
            skill_dir = cli_project / parent / "dup"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: dup
---

# dup
""")

        # The duplicate-name check prevents adding two local deps with the
        # same short name, so write agr.toml directly to set up the
        # ambiguous state.
        cli_config(
            "dependencies = [\n"
            '    {path = "./one/dup", type = "skill"},\n'
            '    {path = "./two/dup", type = "skill"},\n'
            "]\n"
        )

        result = agr("upgrade", "dup")

        assert_cli(result).failed().stdout_contains("ambiguous")

    def test_upgrade_unknown_handle_errors(self, agr, cli_project, cli_skill):
        """agr upgrade with an unknown handle fails with a clear message."""
        agr("add", "./skills/test-skill")

        result = agr("upgrade", "not-installed")

        assert_cli(result).failed().stdout_contains("not in agr.toml")

    def test_upgrade_reports_installed_for_forced_deps(
        self, agr, cli_project, cli_skill
    ):
        """agr upgrade always reports forced deps as Installed, never up to date."""
        agr("add", "./skills/test-skill")

        result = agr("upgrade")

        assert_cli(result).succeeded()
        assert "Installed:" in result.stdout
        assert "Up to date:" not in result.stdout

    def test_upgrade_updates_lockfile_entry(self, agr, cli_project, cli_skill):
        """agr upgrade leaves the lockfile entry in place for the dep."""
        agr("add", "./skills/test-skill")

        result = agr("upgrade")

        assert_cli(result).succeeded()
        lockfile = load_lockfile(cli_project / "agr.lock")
        assert lockfile is not None
        assert len(lockfile.skills) == 1
        assert lockfile.skills[0].path == "./skills/test-skill"
        assert lockfile.skills[0].installed_name == "test-skill"

    def test_upgrade_preserves_config(self, agr, cli_project, cli_skill):
        """agr upgrade does not drop the dep from agr.toml."""
        agr("add", "./skills/test-skill")

        agr("upgrade")

        config = AgrConfig.load(cli_project / "agr.toml")
        assert any(d.path == "./skills/test-skill" for d in config.dependencies)

    def test_upgrade_remote_refetches_latest_commit(
        self, agr, cli_project, git_source_repo
    ):
        """agr upgrade pulls the latest commit for remote deps and updates the lockfile."""
        import subprocess

        base_dir, create_repo = git_source_repo
        repo_dir = create_repo(
            owner="acme", repo="tools", skill_name="test-skill", body="Original body"
        )

        (cli_project / "agr.toml").write_text(
            f'''default_source = "local"
dependencies = [
    {{handle = "acme/tools/test-skill", type = "skill"}},
]

[[source]]
name = "local"
type = "git"
url = "{base_dir.as_posix()}/{{owner}}/{{repo}}"
'''
        )

        sync_result = agr("sync")
        assert_cli(sync_result).succeeded()

        first_lock = load_lockfile(cli_project / "agr.lock")
        assert first_lock is not None and len(first_lock.skills) == 1
        first_commit = first_lock.skills[0].commit
        assert first_commit is not None

        # Commit an update in the source repo.
        skill_file = repo_dir / "skills" / "test-skill" / "SKILL.md"
        skill_file.write_text(
            """---
name: test-skill
---

# test-skill

Updated remote body.
"""
        )
        subprocess.run(
            ["git", "add", "."], cwd=repo_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "update"],
            cwd=repo_dir,
            capture_output=True,
            check=True,
        )

        result = agr("upgrade")

        assert_cli(result).succeeded().stdout_contains("Installed:")
        installed = cli_project / ".claude" / "skills" / "test-skill" / "SKILL.md"
        assert "Updated remote body" in installed.read_text()

        second_lock = load_lockfile(cli_project / "agr.lock")
        assert second_lock is not None and len(second_lock.skills) == 1
        assert second_lock.skills[0].commit != first_commit

    def test_upgrade_one_sibling_leaves_other_alone(
        self, agr, cli_project, git_source_repo
    ):
        """Upgrading one skill in a multi-skill repo doesn't touch siblings.

        Protects the "Same-repo siblings" doc note: targeted upgrade must
        not bump a sibling's lockfile commit or re-copy its on-disk files,
        even though both skills live in the same repo and the classifier
        sees them together.
        """
        import subprocess

        base_dir, create_repo = git_source_repo
        repo_dir = create_repo(
            owner="acme", repo="tools", skill_name="alpha", body="Alpha v1"
        )
        # Add a second skill to the same repo and commit together so both
        # are pinned at the same initial commit.
        beta_dir = repo_dir / "skills" / "beta"
        beta_dir.mkdir(parents=True)
        (beta_dir / "SKILL.md").write_text("""---
name: beta
---

# beta

Beta v1
""")
        subprocess.run(
            ["git", "add", "."], cwd=repo_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "add beta"],
            cwd=repo_dir,
            capture_output=True,
            check=True,
        )

        (cli_project / "agr.toml").write_text(
            f'''default_source = "local"
dependencies = [
    {{handle = "acme/tools/alpha", type = "skill"}},
    {{handle = "acme/tools/beta", type = "skill"}},
]

[[source]]
name = "local"
type = "git"
url = "{base_dir.as_posix()}/{{owner}}/{{repo}}"
'''
        )

        assert_cli(agr("sync")).succeeded()

        first_lock = load_lockfile(cli_project / "agr.lock")
        assert first_lock is not None and len(first_lock.skills) == 2
        pinned = {s.installed_name: s.commit for s in first_lock.skills}
        alpha_pinned, beta_pinned = pinned["alpha"], pinned["beta"]
        assert alpha_pinned is not None and beta_pinned is not None

        # Bump both skills upstream in a new commit.
        (repo_dir / "skills" / "alpha" / "SKILL.md").write_text("""---
name: alpha
---

# alpha

Alpha v2
""")
        (repo_dir / "skills" / "beta" / "SKILL.md").write_text("""---
name: beta
---

# beta

Beta v2
""")
        subprocess.run(
            ["git", "add", "."], cwd=repo_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "bump"],
            cwd=repo_dir,
            capture_output=True,
            check=True,
        )

        result = agr("upgrade", "acme/tools/alpha")
        assert_cli(result).succeeded()

        alpha_md = (
            cli_project / ".claude" / "skills" / "alpha" / "SKILL.md"
        ).read_text()
        beta_md = (
            cli_project / ".claude" / "skills" / "beta" / "SKILL.md"
        ).read_text()
        assert "Alpha v2" in alpha_md
        assert "Beta v1" in beta_md  # sibling untouched on disk

        second_lock = load_lockfile(cli_project / "agr.lock")
        assert second_lock is not None and len(second_lock.skills) == 2
        new_pinned = {s.installed_name: s.commit for s in second_lock.skills}
        assert new_pinned["alpha"] != alpha_pinned  # alpha moved
        assert new_pinned["beta"] == beta_pinned  # beta unchanged

    def test_upgrade_empty_deps_with_unknown_handle_errors(self, agr, cli_config):
        """agr upgrade <typo> against empty deps errors — doesn't mask as success."""
        cli_config("dependencies = []")

        result = agr("upgrade", "typo")

        assert_cli(result).failed().stdout_contains("not in agr.toml")

    def test_upgrade_reports_multiple_unknown_handles(
        self, agr, cli_project, cli_skill
    ):
        """agr upgrade lists all unknown handles in a single error, not just the first."""
        agr("add", "./skills/test-skill")

        result = agr("upgrade", "typo1", "typo2")

        assert_cli(result).failed()
        assert "typo1" in result.stdout
        assert "typo2" in result.stdout

    def test_upgrade_normalizes_local_paths(self, agr, cli_project, cli_skill):
        """agr upgrade matches local paths across ./, trailing-slash, and bare forms."""
        agr("add", "./skills/test-skill")

        # No ./ prefix.
        result = agr("upgrade", "skills/test-skill")
        assert_cli(result).succeeded().stdout_contains("Installed:")

        # Trailing slash.
        result = agr("upgrade", "./skills/test-skill/")
        assert_cli(result).succeeded().stdout_contains("Installed:")


class TestAgrUpgradeRalph:
    """Tests for agr upgrade with ralph dependencies."""

    def test_upgrade_ralph_local(self, agr, cli_project, cli_ralph):
        """agr upgrade refreshes a local ralph dependency."""
        agr("add", "./ralphs/test-ralph")

        (cli_ralph / "RALPH.md").write_text("""---
agent: claude -p
commands:
  - name: tests
    run: uv run pytest
---

# Test Ralph

Updated ralph body.
""")

        result = agr("upgrade")

        assert_cli(result).succeeded().stdout_contains("Installed:")
        installed = cli_project / ".agents" / "ralphs" / "test-ralph" / "RALPH.md"
        assert "Updated ralph body" in installed.read_text()

    def test_upgrade_global_missing_config_with_handles_errors(self, tmp_path):
        """agr upgrade -g <handle> with no global agr.toml fails instead of exit 0."""
        home = tmp_path / "home"
        home.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        result = run_cli(
            ["agr", "upgrade", "-g", "user/some-skill"],
            cwd=workspace,
            env={"HOME": str(home)},
        )

        assert_cli(result).failed().stdout_contains("No global agr.toml found")
        assert "user/some-skill" in result.stdout

    def test_upgrade_global_untargeted_deps_stay_silent(self, tmp_path):
        """agr upgrade -g <typo> does not leak 'Skipped:' for untargeted ralphs.

        The force filter must run before the ralph branch so targeted-upgrade
        output stays focused on the deps the user named.
        """
        home = tmp_path / "home"
        home.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        agr_home = home / ".agr"
        agr_home.mkdir()
        (agr_home / "agr.toml").write_text(
            """default_source = "github"
dependencies = [
    {handle = "user/some-ralph", type = "ralph"},
]
"""
        )

        result = run_cli(
            ["agr", "upgrade", "-g", "user/not-installed"],
            cwd=workspace,
            env={"HOME": str(home)},
        )

        assert_cli(result).failed().stdout_contains("not in global agr.toml")
        assert "Skipped:" not in result.stdout

    def test_upgrade_global_with_ralph_errors(self, tmp_path):
        """agr upgrade -g <ralph> errors clearly instead of silently no-opping."""
        home = tmp_path / "home"
        home.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Write a global agr.toml with a ralph entry directly — sync/add
        # would not normally put a ralph in global scope, but _run_global_sync
        # silently skips them, so we guard against the case where a user
        # hand-edited the file.
        agr_home = home / ".agr"
        agr_home.mkdir()
        (agr_home / "agr.toml").write_text(
            """default_source = "github"
dependencies = [
    {handle = "user/some-ralph", type = "ralph"},
]
"""
        )

        result = run_cli(
            ["agr", "upgrade", "-g", "user/some-ralph"],
            cwd=workspace,
            env={"HOME": str(home)},
        )

        assert_cli(result).failed().stdout_contains("Ralphs cannot be upgraded")
