"""Routing a model tool-request through the broker inside the build loop.

The build loop hands a ``server_id == "crossaudit"`` request to the broker with a
per-run read-only grant; anything else stays on the untouched MCP path. These
pin the routing adapter (token scope, request shaping, evidence recording,
deny-by-default) without needing a full generation run.
"""
from __future__ import annotations

from crossaudit.broker.routing import (
    BROKER_SERVER_ID, READONLY_TOOLS, broker_tool_call, evidence_path,
    readonly_token)
from crossaudit.policy import CapabilityToken


def _perm_token():
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "run1", "tools": list(READONLY_TOOLS),
        "paths": ["**"], "expires_at": "2100-01-01T00:00:00Z"})


def test_no_import_cycle():
    # cli.build ← broker.routing → and appservice all import cleanly together.
    import crossaudit.cli.build          # noqa: F401
    import crossaudit.appservice         # noqa: F401
    import crossaudit.broker.routing     # noqa: F401
    assert BROKER_SERVER_ID == "crossaudit"


def test_readonly_token_is_scoped_and_read_only(cfg):
    tok = readonly_token(cfg, run_id="run1", now_epoch=0)
    assert tok.tools == frozenset(READONLY_TOOLS)
    assert not tok.writable and not tok.network_allowed()
    assert tok.allows_tool("file_read") and not tok.allows_tool("write_file")
    assert not tok.expired(now_epoch=0) and tok.expired(now_epoch=9e12)
    scope = tuple(cfg.scope_dirs or ())
    if scope:
        for d in scope:
            assert tok.allows_path(f"{d}/x.txt")
    else:
        assert tok.allows_path("anything/x.txt")


def test_broker_tool_call_routes_runs_and_records(cfg):
    r = broker_tool_call(cfg, {"tool": "file_read", "arguments": {"path": "crossaudit.yml"}},
                         _perm_token(), run_id="run1", now_epoch=0)
    assert r["status"] == "succeeded"
    assert r["server_id"] == BROKER_SERVER_ID and r["tool"] == "file_read"
    assert "science_repo" in r["output"]["content"] and r["result_sha256"]
    # Evidence landed in the project's state dir and the chain verifies.
    from crossaudit.ledger import EvidenceLedger
    assert EvidenceLedger(evidence_path(cfg)).verify().ok


def test_broker_tool_call_accepts_args_alias(cfg):
    r = broker_tool_call(cfg, {"tool": "search", "args": {"query": "science_repo"}},
                         _perm_token(), run_id="run1", now_epoch=0)
    assert r["status"] == "succeeded" and r["output"]["count"] >= 1


def test_broker_tool_call_denies_out_of_scope(cfg):
    tok = CapabilityToken.parse({
        "project_id": "p", "run_id": "run1", "tools": list(READONLY_TOOLS),
        "paths": ["work/**"], "expires_at": "2100-01-01T00:00:00Z"})
    r = broker_tool_call(cfg, {"tool": "file_read", "arguments": {"path": "crossaudit.yml"}},
                         tok, run_id="run1", now_epoch=0)
    assert r["status"] == "refused" and "outside" in r["reason"]
