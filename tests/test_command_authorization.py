"""P13 — the command allowlist is a first-class per-project authorization.

The user names the executables the agent may run (in Settings → Agent behavior);
that opt-in flows into the snapshot + settings state and makes run_check live
(catalog coverage is proven in test_live_catalog). Nothing runs without it, and
even then every command is per-call approval-gated and argv-only.
"""
from __future__ import annotations

import sys

from crossaudit.broker.approval import AuthorizationStore
from crossaudit.broker.tools_command import ALLOWED_COMMANDS_KEY
from crossaudit.console.page import PAGE
from crossaudit.console.server import _authorizations, snapshot


def test_authorizations_helper_reports_allowed_commands(cfg):
    assert _authorizations(None)["allowed_commands"] == []
    assert _authorizations(cfg)["allowed_commands"] == []
    AuthorizationStore(cfg).set_list(ALLOWED_COMMANDS_KEY, [sys.executable, "pytest"])
    assert _authorizations(cfg)["allowed_commands"] == [sys.executable, "pytest"]


def test_snapshot_exposes_allowed_commands(cfg):
    assert snapshot(cfg)["authorizations"]["allowed_commands"] == []
    AuthorizationStore(cfg).set_list(ALLOWED_COMMANDS_KEY, ["make"])
    assert snapshot(cfg)["authorizations"]["allowed_commands"] == ["make"]


def test_page_has_the_allowed_commands_control_wired():
    assert 'id="allowed-commands-input"' in PAGE
    assert "allowed_commands" in PAGE
    assert "Commands the agent may run" in PAGE
