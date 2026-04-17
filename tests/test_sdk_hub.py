"""Tests for sdk/hub.py handle validation in list_skills."""

import pytest

from agr.exceptions import InvalidHandleError
from agr.sdk.hub import list_skills


def _raises_invalid_handle(repo_handle: str) -> None:
    with pytest.raises(InvalidHandleError):
        list_skills(repo_handle)


# --- Control-character / whitespace rejection (SF-008) ---

def test_list_skills_rejects_newline_in_owner():
    _raises_invalid_handle("owner\nevil/repo")


def test_list_skills_rejects_tab_in_repo():
    _raises_invalid_handle("owner/repo\tevil")


def test_list_skills_rejects_space_in_owner_single_part():
    _raises_invalid_handle("owner evil")


# --- YAML character rejection (SF-010 / SF-011 / SF-012) ---

def test_list_skills_rejects_bracket_in_owner():
    _raises_invalid_handle("[owner]/repo")


def test_list_skills_rejects_hash_in_repo():
    _raises_invalid_handle("owner/#repo")


def test_list_skills_rejects_pipe_in_owner():
    _raises_invalid_handle("|owner/repo")


# --- Path traversal rejection (SF-003) ---

def test_list_skills_rejects_dotdot_owner():
    _raises_invalid_handle("../repo")


def test_list_skills_rejects_dotdot_repo():
    _raises_invalid_handle("owner/..")


# --- Valid handles still work (no regression) ---

def test_list_skills_valid_single_part_raises_network_not_handle(monkeypatch):
    """Valid owner should pass handle validation; network call is mocked to raise."""
    import agr.sdk.hub as hub

    def _fake_fetch(owner, candidates):
        raise RuntimeError("network")

    monkeypatch.setattr(hub, "_fetch_repo_tree", _fake_fetch)
    with pytest.raises(RuntimeError, match="network"):
        list_skills("validowner")


def test_list_skills_valid_two_part_raises_network_not_handle(monkeypatch):
    """Valid owner/repo should pass handle validation; network call is mocked."""
    import agr.sdk.hub as hub

    def _fake_fetch(owner, candidates):
        raise RuntimeError("network")

    monkeypatch.setattr(hub, "_fetch_repo_tree", _fake_fetch)
    with pytest.raises(RuntimeError, match="network"):
        list_skills("owner/repo")
