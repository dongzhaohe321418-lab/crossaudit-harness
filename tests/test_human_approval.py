"""P7 — per-call human approval: the real-time gate that makes Level 3+ usable.

A flagged action pauses in place; the user's decision (delivered through the
process-global inbox exactly as the ``/api/approval`` endpoint delivers it)
either lets the *same* worker continue or refuses the action. The invariants
are pinned here: deny-by-default (cancel/timeout deny), permission comes from
the human not the model, Level 4+ is always per-call (no standing grant), and
Level 6 self-install is refused without even prompting.
"""
from __future__ import annotations

import pathlib
import threading
import time
from types import SimpleNamespace

import pytest

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.humanapproval import (
    DENY, ONCE, PROJECT, RUN, ApprovalInbox, HumanApprovalGate, PendingApproval,
    reversibility)
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _dec(level, reason="policy flagged this for approval"):
    """A Decision-like object the gate reads .level/.reason from."""
    return SimpleNamespace(level=level, reason=reason, requires_approval=True,
                           allow=True)


def _proposal(tool, level, *, writes=False, paths=(), host="", cost=0.0, nbytes=0):
    return {"tool": tool, "level": level, "writes": writes,
            "paths": list(paths), "host": host,
            "estimated_cost_usd": cost, "estimated_bytes": nbytes}


def _resolve_when_pending(inbox, run_id, scope, *, timeout=4.0):
    """Mimic the HTTP thread: resolve as soon as the card is pending."""
    def worker():
        deadline = time.time() + timeout
        while time.time() < deadline:
            if inbox.pending(run_id) is not None:
                inbox.resolve(run_id, scope)
                return
            time.sleep(0.005)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


def _writable(paths=("**",)):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["file_write", "git_commit"],
        "paths": list(paths), "writable": True,
        "expires_at": "2100-01-01T00:00:00Z"})


# -- the gate: standing authorization still grants without prompting --
def test_standing_l2_authorization_grants_without_a_card(cfg):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    approval = gate(_proposal("file_write", 2, writes=True), _dec(2), cfg, "r")
    assert approval.granted
    assert inbox.pending("r") is None          # never had to ask


# -- allow once / this run / this project --
def test_allow_once_grants_only_this_call(cfg):
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    _resolve_when_pending(inbox, "r", ONCE)
    approval = gate(_proposal("run_check", 3), _dec(3), cfg, "r")
    assert approval.granted
    assert not inbox.run_granted("r", "run_check")            # not persisted
    assert not AuthorizationStore(cfg).authorized_tool("run_check")


def test_allow_this_run_persists_for_the_run(cfg):
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    _resolve_when_pending(inbox, "r", RUN)
    assert gate(_proposal("run_check", 3), _dec(3), cfg, "r").granted
    assert inbox.run_granted("r", "run_check")
    # A second same-tool proposal in the same run does NOT re-prompt.
    again = gate(_proposal("run_check", 3), _dec(3), cfg, "r")
    assert again.granted and inbox.pending("r") is None
    # A different run still has to ask (grant is run-scoped).
    assert not inbox.run_granted("r2", "run_check")


def test_allow_this_project_persists_across_runs(cfg):
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    _resolve_when_pending(inbox, "r", PROJECT)
    assert gate(_proposal("git_commit", 3), _dec(3), cfg, "r").granted
    assert AuthorizationStore(cfg).authorized_tool("git_commit")
    # A fresh run / fresh gate is auto-granted with no card.
    gate2 = HumanApprovalGate(inbox=ApprovalInbox())
    assert gate2(_proposal("git_commit", 3), _dec(3), cfg, "r2").granted
    assert gate2.inbox.pending("r2") is None


def test_deny_refuses(cfg):
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    _resolve_when_pending(inbox, "r", DENY)
    approval = gate(_proposal("run_check", 3), _dec(3), cfg, "r")
    assert not approval.granted


# -- Level 4+ is always per-call; Level 6 is refused without prompting --
def test_level4_offers_only_once_or_deny_and_never_persists(cfg):
    assert PendingApproval("r", "mcp_call", 4, True).scopes() == [ONCE, DENY]
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    # Even if a (forged) "project" scope arrives for a Level-4 action, it is
    # treated as once — never a standing grant.
    _resolve_when_pending(inbox, "r", PROJECT)
    approval = gate(_proposal("mcp_call", 4, writes=True, host="svc"), _dec(4),
                    cfg, "r")
    assert approval.granted                                   # allowed this once
    assert not AuthorizationStore(cfg).authorized_tool("mcp_call")   # not persisted
    assert not inbox.run_granted("r", "mcp_call")


def test_level6_self_install_is_refused_without_prompting(cfg):
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    approval = gate(_proposal("self_install", 6, writes=True), _dec(6), cfg, "r")
    assert not approval.granted
    assert inbox.pending("r") is None                         # never asked


# -- deny-by-default: cancel and timeout both deny, and heartbeat fires --
def test_cancel_denies_and_wakes_the_worker():
    inbox = ApprovalInbox()
    resolved = inbox.wait("r", is_cancelled=lambda: True, timeout=5.0)
    assert resolved.scope == DENY


def test_timeout_denies_and_heartbeats_while_waiting():
    inbox = ApprovalInbox()
    beats = []
    inbox.open(PendingApproval("r", "run_check", 3, False))
    resolved = inbox.wait("r", heartbeat=lambda: beats.append(1),
                          timeout=0.05, poll=0.02)
    assert resolved.scope == DENY
    assert beats                                              # stayed alive


def test_resolve_unknown_run_returns_false():
    inbox = ApprovalInbox()
    assert inbox.resolve("nope", ONCE) is False
    inbox.open(PendingApproval("r", "run_check", 3, False))
    assert inbox.resolve("r", "not-a-scope") is False        # bad scope rejected


def test_resolve_unblocks_a_waiting_worker():
    inbox = ApprovalInbox()
    out = {}

    def worker():
        inbox.open(PendingApproval("r", "run_check", 3, False))
        out["decision"] = inbox.wait("r", timeout=5.0)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    deadline = time.time() + 4.0
    while inbox.pending("r") is None and time.time() < deadline:
        time.sleep(0.005)
    assert inbox.resolve("r", ONCE)
    t.join(timeout=5.0)
    assert out["decision"].scope == ONCE


# -- through the broker: approve -> execute, deny -> refuse, both ledgered --
def test_broker_with_gate_approves_and_executes_a_write(cfg, tmp_path):
    inbox = ApprovalInbox()
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"),
                        approver=HumanApprovalGate(inbox=inbox))
    _resolve_when_pending(inbox, "r", ONCE)
    r = broker.execute(
        {"tool": "file_write", "args": {"path": "work/x.md", "content": "hi"}},
        _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "succeeded"
    assert (cfg.root / "work/x.md").read_text() == "hi"      # the write happened
    kinds = [e["kind"] for e in broker.ledger.entries()]
    assert "approval" in kinds and "tool_result" in kinds
    approval = next(e for e in broker.ledger.entries() if e["kind"] == "approval")
    assert approval["payload"]["granted"] is True
    assert broker.ledger.verify().ok


def test_broker_with_gate_denies_and_refuses_a_write(cfg, tmp_path):
    inbox = ApprovalInbox()
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"),
                        approver=HumanApprovalGate(inbox=inbox))
    _resolve_when_pending(inbox, "r", DENY)
    r = broker.execute(
        {"tool": "file_write", "args": {"path": "work/x.md", "content": "hi"}},
        _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"
    assert not (cfg.root / "work/x.md").exists()             # nothing written
    kinds = [e["kind"] for e in broker.ledger.entries()]
    assert "approval" in kinds and "tool_result" not in kinds
    approval = next(e for e in broker.ledger.entries() if e["kind"] == "approval")
    assert approval["payload"]["granted"] is False


def test_broker_without_a_gate_stays_deny_by_default(cfg, tmp_path):
    # No approver injected: an L3 command is refused (needs_approval), never run.
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    tok = CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["git_commit"],
        "paths": ["**"], "writable": True, "expires_at": "2100-01-01T00:00:00Z"})
    r = broker.execute({"tool": "git_commit", "args": {"message": "x"}},
                       tok, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"


def test_reversibility_phrasing_scales_with_level():
    assert "reads only" in reversibility(1, False)
    assert "recovery point" in reversibility(2, True)
    assert "network" in reversibility(4, True)
    assert "forbidden" in reversibility(6, True) or "destructive" in reversibility(6, True)


# -- surfaced to the UI + the endpoint is wired --
def test_snapshot_pending_approval_defaults_none(cfg):
    from crossaudit.console.server import snapshot
    assert snapshot(cfg)["pending_approval"] is None


def test_page_markup_declares_the_approval_card_and_the_endpoint_path():
    """MARKUP ONLY. This asserts strings are present in ``page.py``; it does not
    render anything and cannot fail if the page never reaches a person. Renamed
    under D106: serving an empty document leaves it green, so a name claiming
    "renders"/"announces" was a property nobody tested.
    """
    from crossaudit.console.page import PAGE
    assert "approval-card" in PAGE and "Approval needed" in PAGE
    assert "resolveApproval" in PAGE and "/api/approval" in PAGE


def test_server_endpoint_is_wired_to_the_inbox():
    import crossaudit.console.server as server_mod
    src = pathlib.Path(server_mod.__file__).read_text(encoding="utf-8")
    assert '"/api/approval"' in src and "INBOX.resolve" in src
