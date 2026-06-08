"""Tests for the env-var-backed feature-flag module."""

import pytest

from agr.features import feature_enabled


class TestFeatureEnabled:
    """Resolution of the ralph feature flag from its env var."""

    def test_unset_is_off(self, monkeypatch):
        monkeypatch.delenv("AGR_ENABLE_RALPH", raising=False)
        assert feature_enabled("ralph") is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", "on", " true "])
    def test_truthy_values_enable(self, monkeypatch, value):
        monkeypatch.setenv("AGR_ENABLE_RALPH", value)
        assert feature_enabled("ralph") is True

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
    def test_non_truthy_values_disable(self, monkeypatch, value):
        monkeypatch.setenv("AGR_ENABLE_RALPH", value)
        assert feature_enabled("ralph") is False

    def test_unknown_feature_raises(self):
        with pytest.raises(KeyError):
            feature_enabled("does-not-exist")
