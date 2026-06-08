"""Unit tests for agr.commands.sync feature-gating of ralph install."""

from pathlib import Path
from unittest.mock import patch

from agr.commands.sync import SyncStatus, _classify_dependencies
from agr.config import AgrConfig, Dependency


class TestClassifyDependenciesRalphGate:
    """Off-path: pinned ralph deps are skipped silently during classification."""

    def _config(self) -> AgrConfig:
        return AgrConfig(
            dependencies=[
                Dependency(type="skill", handle="owner/repo/my-skill"),
                Dependency(type="ralph", handle="owner/repo/my-ralph"),
            ]
        )

    def test_ralph_skipped_silently_when_flag_off(self, monkeypatch):
        monkeypatch.delenv("AGR_ENABLE_RALPH", raising=False)
        config = self._config()

        # The skill still needs installing so we can confirm "installs the rest".
        with (
            patch(
                "agr.commands.sync._resolve_tools_needing_install",
                return_value=["claude"],
            ),
            patch("agr.commands.sync.is_ralph_installed", return_value=False),
        ):
            classified = _classify_dependencies(config, Path("/repo"), [])

        # Ralph dep (index 1) is marked up-to-date and never queued.
        assert classified.results[1].status == SyncStatus.UP_TO_DATE
        assert classified.pending_ralph == []
        # The skill leaf is still queued for install.
        assert len(classified.pending_remote) == 1
        assert classified.pending_remote[0].index == 0

    def test_ralph_queued_when_flag_on(self, monkeypatch):
        monkeypatch.setenv("AGR_ENABLE_RALPH", "1")
        config = self._config()

        with (
            patch(
                "agr.commands.sync._resolve_tools_needing_install",
                return_value=["claude"],
            ),
            patch("agr.commands.sync.is_ralph_installed", return_value=False),
        ):
            classified = _classify_dependencies(config, Path("/repo"), [])

        assert len(classified.pending_ralph) == 1
        assert classified.pending_ralph[0].index == 1
