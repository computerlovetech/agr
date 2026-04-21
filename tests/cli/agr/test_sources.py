"""CLI tests for sources and resolution."""

from pathlib import Path

from tests.cli.assertions import assert_cli


def _write_sources_config(
    path: Path,
    *,
    default_source: str,
    sources: list[tuple[str, str]],
) -> None:
    entries = "\n".join(
        [
            f"""[[source]]\nname = "{name}"\ntype = "git"\nurl = "{url}\"\n"""
            for name, url in sources
        ]
    )
    config = f"""default_source = "{default_source}"
dependencies = []

{entries}
"""
    path.write_text(config)


class TestSourceResolution:
    """Tests for source resolution via CLI."""

    def test_add_with_explicit_source(self, agr, cli_project, git_source_repo):
        """agr add --source installs from the specified source."""
        base_dir, create_repo = git_source_repo
        create_repo()

        config_path = cli_project / "agr.toml"
        _write_sources_config(
            config_path,
            default_source="github",
            sources=[
                ("local", f"{base_dir.as_posix()}/{{owner}}/{{repo}}"),
                ("github", "https://github.com/{owner}/{repo}.git"),
            ],
        )

        result = agr("add", "acme/tools/test-skill", "--source", "local")

        assert_cli(result).succeeded()
        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()

        from agr.config import AgrConfig

        config = AgrConfig.load(config_path)
        dep = config.dependencies[0]
        assert dep.source == "local"

    def test_add_uses_default_source(self, agr, cli_project, git_source_repo):
        """agr add without --source uses default_source."""
        base_dir, create_repo = git_source_repo
        create_repo()

        config_path = cli_project / "agr.toml"
        _write_sources_config(
            config_path,
            default_source="local",
            sources=[
                ("local", f"{base_dir.as_posix()}/{{owner}}/{{repo}}"),
            ],
        )

        result = agr("add", "acme/tools/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".claude" / "skills" / "test-skill"
        assert installed.exists()

        from agr.config import AgrConfig

        config = AgrConfig.load(config_path)
        dep = config.dependencies[0]
        assert dep.source is None

    def test_add_shorthand_records_resolved_repo_in_toml(
        self, agr, cli_project, git_source_repo
    ):
        """agr add owner/name writes the fully-resolved owner/repo/name to agr.toml.

        Shorthand handles used to round-trip as owner/name, which silently
        re-resolves against whatever default_repo is configured at sync time.
        Persisting the resolved repo pins the reference and protects against
        defaults drifting (e.g. DEFAULT_REPO_NAME changing, legacy fallback
        being removed).
        """
        base_dir, create_repo = git_source_repo
        create_repo(owner="acme", repo="skills", skill_name="test-skill")

        config_path = cli_project / "agr.toml"
        _write_sources_config(
            config_path,
            default_source="local",
            sources=[
                ("local", f"{base_dir.as_posix()}/{{owner}}/{{repo}}"),
            ],
        )

        result = agr("add", "acme/test-skill")

        assert_cli(result).succeeded()

        from agr.config import AgrConfig

        config = AgrConfig.load(config_path)
        dep = config.dependencies[0]
        assert dep.handle == "acme/skills/test-skill"

    def test_add_legacy_fallback_records_resolved_repo_in_toml(
        self, agr, cli_project, git_source_repo
    ):
        """agr add owner/name records the legacy repo when fallback fires.

        This is the critical regression test: when the default repo
        ('skills') doesn't exist but 'agent-resources' does, the shorthand
        `acme/test-skill` used to be stored as-is and would silently break
        once the legacy fallback is removed. The resolved repo must be
        captured into agr.toml so sync stays stable.
        """
        base_dir, create_repo = git_source_repo
        # Only the legacy repo exists — skills repo does not.
        create_repo(owner="acme", repo="agent-resources", skill_name="test-skill")

        config_path = cli_project / "agr.toml"
        _write_sources_config(
            config_path,
            default_source="local",
            sources=[
                ("local", f"{base_dir.as_posix()}/{{owner}}/{{repo}}"),
            ],
        )

        result = agr("add", "acme/test-skill")

        assert_cli(result).succeeded()

        from agr.config import AgrConfig

        config = AgrConfig.load(config_path)
        dep = config.dependencies[0]
        assert dep.handle == "acme/agent-resources/test-skill"

    def test_add_explicit_repo_handle_unchanged(
        self, agr, cli_project, git_source_repo
    ):
        """agr add owner/repo/name stores the same 3-part handle verbatim."""
        base_dir, create_repo = git_source_repo
        create_repo(owner="acme", repo="tools", skill_name="test-skill")

        config_path = cli_project / "agr.toml"
        _write_sources_config(
            config_path,
            default_source="local",
            sources=[
                ("local", f"{base_dir.as_posix()}/{{owner}}/{{repo}}"),
            ],
        )

        result = agr("add", "acme/tools/test-skill")

        assert_cli(result).succeeded()

        from agr.config import AgrConfig

        config = AgrConfig.load(config_path)
        dep = config.dependencies[0]
        assert dep.handle == "acme/tools/test-skill"

    def test_first_source_wins(self, agr, cli_project, git_source_repo):
        """When multiple sources match, default source is used."""
        base_dir, create_repo = git_source_repo
        create_repo(owner="acme", repo="tools", body="Source One")

        second_base = base_dir.parent / "sources-2"
        second_base.mkdir(parents=True, exist_ok=True)
        create_repo(
            owner="acme",
            repo="tools",
            skill_name="test-skill",
            body="Source Two",
            base=second_base,
        )

        config_path = cli_project / "agr.toml"
        _write_sources_config(
            config_path,
            default_source="local1",
            sources=[
                ("local1", f"{base_dir.as_posix()}/{{owner}}/{{repo}}"),
                ("local2", f"{second_base.as_posix()}/{{owner}}/{{repo}}"),
            ],
        )

        result = agr("add", "acme/tools/test-skill")

        assert_cli(result).succeeded()
        installed = cli_project / ".claude" / "skills" / "test-skill" / "SKILL.md"
        assert "Source One" in installed.read_text()
