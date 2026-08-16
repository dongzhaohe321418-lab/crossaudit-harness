"""The per-project workspace-writes opt-in surfaces in state + settings + UI.

The user turns writes on for a project via a Settings toggle; the console reads
and writes that authorization, and it flows into the build (build_catalog /
build_broker_and_token) so writes only become possible after the opt-in.
"""
from __future__ import annotations

from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.console.page import PAGE
from crossaudit.console.server import _authorizations, snapshot


def test_authorizations_helper_defaults_off(cfg):
    assert _authorizations(None) == {"workspace_writes": False}
    assert _authorizations(cfg)["workspace_writes"] is False
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    assert _authorizations(cfg)["workspace_writes"] is True


def test_state_snapshot_exposes_authorization(cfg):
    assert snapshot(cfg)["authorizations"]["workspace_writes"] is False
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    assert snapshot(cfg)["authorizations"]["workspace_writes"] is True


def test_page_has_the_toggle_wired_to_the_endpoint():
    assert 'id="workspace-writes-toggle"' in PAGE
    assert "/api/authorization" in PAGE
    assert "Allow the agent to edit files in this project" in PAGE
