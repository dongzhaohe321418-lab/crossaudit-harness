"""The Approval Service — the 'project-level authorization, like Claude Code' model.

A Level-2 recoverable write auto-runs ONLY when the user turned on this
project's workspace-writes authorization; otherwise the broker surfaces it for a
per-call decision and writes nothing. Level 4+ is never auto-granted, even with
the authorization on. Every approval decision is itself recorded as evidence.
"""
from __future__ import annotations

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.approval import (
    AuthorizationStore, WORKSPACE_WRITES, approve)
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken, Decision, decide


def _writable():
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["file_write", "file_read"],
        "paths": ["**"], "writable": True, "expires_at": "2100-01-01T00:00:00Z"})


def test_authorization_store_roundtrip(cfg):
    store = AuthorizationStore(cfg)
    assert not store.authorized(WORKSPACE_WRITES)
    store.set(WORKSPACE_WRITES, True)
    assert store.authorized(WORKSPACE_WRITES)
    store.set(WORKSPACE_WRITES, False)
    assert not store.authorized(WORKSPACE_WRITES)


def test_approve_grants_l2_write_only_when_authorized(cfg):
    proposal = {"tool": "file_write", "level": 2, "writes": True, "paths": ["work/a.md"]}
    d = decide(proposal, _writable(), now_epoch=0)
    assert d.allow and d.requires_approval
    assert not approve(proposal, d, cfg).granted           # not authorized yet
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    assert approve(proposal, d, cfg).granted               # now authorized


def test_high_impact_never_auto_granted_even_when_authorized(cfg):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    proposal = {"tool": "push", "level": 5, "writes": True}
    d = Decision(allow=True, reason="", level=5, requires_approval=True)
    assert not approve(proposal, d, cfg).granted


def test_broker_executes_write_when_project_authorized(cfg, tmp_path):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    r = broker.execute({"tool": "file_write", "args": {"path": "work/x.md", "content": "hi"}},
                       _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "succeeded"
    assert (cfg.root / "work/x.md").read_text() == "hi"
    assert r.output["post_sha256"]
    # tool_call + decision + approval(granted) + tool_result, chain intact.
    rep = broker.ledger.verify()
    assert rep.ok and rep.count == 4


def test_broker_needs_approval_when_not_authorized(cfg, tmp_path):
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    r = broker.execute({"tool": "file_write", "args": {"path": "work/x.md", "content": "hi"}},
                       _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"
    assert not (cfg.root / "work/x.md").exists()
    # The refused approval is recorded too.
    assert broker.ledger.verify().ok
