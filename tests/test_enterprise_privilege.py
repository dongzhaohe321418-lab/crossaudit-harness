"""Adversarial: enterprise privilege escalation is impossible by construction.

INVARIANT under attack: L3 and ALL L4+ tools NEVER auto-run; L6 ``self_install``
is ALWAYS refused; and *even full authorization* (a writable capability token
that grants the tool + a project that turned ``workspace_writes`` on + a per-run
grant + a per-project tool grant) cannot make any of them fire on their own.

Each test actually PROPOSES the high-impact action through the real broker /
approval gate and asserts (a) the broker returns ``needs_approval`` (never
``succeeded``) and (b) the underlying manager/handler is NEVER invoked — the
``hpc.MANAGER.submit`` / ``mcp.MANAGER.call_agent`` / git-push / gh calls are
monkeypatched to *record* so a regression that let them auto-run would both flip
the status AND leave a recorded call, failing the assertion. No real external
effect (push, MCP, HPC, gh) can fire: the effectful primitives are neutralised.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from crossaudit import gitio, hpc, mcp
from crossaudit.broker import ToolBroker, ToolError, full_registry
from crossaudit.broker import tools_git
from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.humanapproval import (
    DENY, ONCE, PROJECT, RUN, ApprovalInbox, HumanApprovalGate,
    PendingApproval, PER_CALL_ONLY_LEVEL)
from crossaudit.broker.selfimprove import self_install
from crossaudit.broker.tools_command import register_command
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _dec(level, reason="policy flagged this for approval"):
    """A Decision-like object the gate reads .level/.reason from."""
    return SimpleNamespace(level=level, reason=reason, requires_approval=True,
                           allow=True)


def _proposal(tool, level, *, writes=False, paths=(), host="", cost=0.0, nbytes=0):
    return {"tool": tool, "level": level, "writes": writes,
            "paths": list(paths), "host": host,
            "estimated_cost_usd": cost, "estimated_bytes": nbytes}


def _full_token(cfg, tools, *, writable=True):
    """A maximally-permissive grant: writable, network-enabled, non-expiring,
    scoped to the whole tree, naming exactly the tool(s) under attack. This is
    the strongest capability the runtime ever issues — the point is that even it
    cannot auto-run an L3/L4+ action."""
    return CapabilityToken.parse({
        "project_id": str(cfg.root), "run_id": "r", "tools": list(tools),
        "paths": ["**"], "writable": writable, "hosts": ["example.com", "localhost"],
        "expires_at": "2100-01-01T00:00:00Z"})


def _broker(cfg, tmp_path, *, registry=None, approver=None):
    return ToolBroker(registry or full_registry(),
                      EvidenceLedger(tmp_path / "ev.jsonl"), approver=approver)


def _kinds(broker):
    return [e["kind"] for e in broker.ledger.entries()]


def _resolve_when_pending(inbox, run_id, scope, *, spin=2.0):
    """Mimic the HTTP approval thread: resolve as soon as a card is pending.
    Returns (thread, state) where state['fired'] records whether a card was
    ever seen — so a test can assert a card DID (or did NOT) have to appear."""
    state = {"fired": False}

    def worker():
        deadline = time.time() + spin
        while time.time() < deadline:
            if inbox.pending(run_id) is not None:
                inbox.resolve(run_id, scope)
                state["fired"] = True
                return
            time.sleep(0.005)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t, state


def _assert_needs_approval(r):
    assert r.status == "needs_approval", f"expected needs_approval, got {r.status!r}"
    assert r.reason, "a refusal must carry a reason"


# --------------------------------------------------------------------------- #
# (guard) the registry keeps these tools at their high, gated levels           #
# --------------------------------------------------------------------------- #
def test_full_registry_pins_high_levels():
    reg = full_registry()
    assert reg.get("mcp_call").level == 4
    for name in ("hpc_submit", "git_push", "repo_create"):
        assert reg.get(name).level == 5, name
    assert reg.get("self_install").level == 6
    # Everything L4+ requires per-call approval that can never be standing.
    assert PER_CALL_ONLY_LEVEL == 4


# --------------------------------------------------------------------------- #
# (a) L4+ never auto-run under FULL authorization; the manager is never called #
# --------------------------------------------------------------------------- #
def test_hpc_submit_L5_never_auto_runs(cfg, tmp_path, monkeypatch):
    # Full authorization: project writes on + a writable token naming the tool.
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    calls = []
    monkeypatch.setattr(hpc.MANAGER, "submit",
                        lambda *a, **k: calls.append((a, k)) or {"job_id": "REAL"})
    b = _broker(cfg, tmp_path)                       # standing service, no human
    r = b.execute({"tool": "hpc_submit",
                   "args": {"manifest": {"cmd": "run", "nodes": 8}}},
                  _full_token(cfg, ["hpc_submit"]), cfg=cfg, run_id="r", now_epoch=0)
    _assert_needs_approval(r)
    assert calls == []                               # the remote submit NEVER fired
    k = _kinds(b)
    assert "approval" in k and "tool_result" not in k
    appr = next(e for e in b.ledger.entries() if e["kind"] == "approval")
    assert appr["payload"]["granted"] is False
    assert b.ledger.verify().ok


def test_mcp_call_L4_never_auto_runs(cfg, tmp_path, monkeypatch):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    calls = []
    monkeypatch.setattr(mcp.MANAGER, "call_agent",
                        lambda *a, **k: calls.append((a, k)) or {"ok": True})
    b = _broker(cfg, tmp_path)
    r = b.execute({"tool": "mcp_call",
                   "args": {"request": {"server_id": "srv", "tool": "do"}}},
                  _full_token(cfg, ["mcp_call"]), cfg=cfg, run_id="r", now_epoch=0)
    _assert_needs_approval(r)
    assert calls == []                               # the external MCP tool NEVER ran
    assert "tool_result" not in _kinds(b)
    assert b.ledger.verify().ok


def test_git_push_L5_never_auto_runs(cfg, tmp_path, monkeypatch):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    calls = []
    # Neutralise the effectful primitive so a regression can neither push nor
    # touch the network; record every git invocation to prove it stays at zero.
    monkeypatch.setattr(gitio, "git", lambda *a, **k: calls.append((a, k)) or "")
    b = _broker(cfg, tmp_path)
    r = b.execute({"tool": "git_push", "args": {"remote": "origin", "branch": "main"}},
                  _full_token(cfg, ["git_push"]), cfg=cfg, run_id="r", now_epoch=0)
    _assert_needs_approval(r)
    assert calls == []                               # no `git push` was ever issued
    assert "tool_result" not in _kinds(b)


def test_repo_create_L5_never_auto_runs(cfg, tmp_path, monkeypatch):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    calls = []
    monkeypatch.setattr(tools_git.subprocess, "run",
                        lambda *a, **k: calls.append((a, k)) or
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    b = _broker(cfg, tmp_path)
    r = b.execute({"tool": "repo_create", "args": {"name": "totally-new-repo"}},
                  _full_token(cfg, ["repo_create"]), cfg=cfg, run_id="r", now_epoch=0)
    _assert_needs_approval(r)
    assert calls == []                               # `gh repo create` NEVER ran
    assert "tool_result" not in _kinds(b)


# --------------------------------------------------------------------------- #
# (b) L3 run_check needs approval without a human gate                          #
# --------------------------------------------------------------------------- #
def test_run_check_L3_needs_approval_without_a_human_gate(cfg, tmp_path, monkeypatch):
    # Register the L3 command tool onto the full registry and arm it so it WOULD
    # execute if the broker ever auto-ran it: allowlist the command + patch the
    # subprocess primitive to record. Project writes are authorized (covers L2
    # only) — it must NOT bleed into this L3 command.
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    AuthorizationStore(cfg).set_list("allowed_commands", ["echo"])
    import crossaudit.broker.tools_command as tc
    ran = []
    monkeypatch.setattr(tc.subprocess, "run",
                        lambda *a, **k: ran.append((a, k)) or
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    reg = register_command(full_registry())
    b = _broker(cfg, tmp_path, registry=reg)         # no approver => standing service
    r = b.execute({"tool": "run_check", "args": {"command": ["echo", "hi"]}},
                  _full_token(cfg, ["run_check"]), cfg=cfg, run_id="r", now_epoch=0)
    _assert_needs_approval(r)
    assert ran == []                                 # the command NEVER executed
    assert "tool_result" not in _kinds(b)


# --------------------------------------------------------------------------- #
# (c) L6 self_install is refused at the handler AND at the gate                 #
# --------------------------------------------------------------------------- #
def test_self_install_handler_always_refuses_and_modifies_nothing(cfg):
    # Defense-in-depth: even if approval were somehow obtained, the handler is a
    # hard refuse and touches nothing.
    before = (cfg.root / "crossaudit.yml").read_text()
    tok = _full_token(cfg, ["self_install"])
    with pytest.raises(ToolError) as ei:
        self_install(cfg, {"ref": "HEAD", "target": "/"}, tok)
    assert "not permitted" in str(ei.value).lower()
    assert (cfg.root / "crossaudit.yml").read_text() == before   # app unchanged


def test_self_install_refused_at_gate_even_when_every_grant_is_set(cfg):
    # Pre-grant EVERYTHING the gate normally honours for lower levels: project
    # writes, a per-project tool grant, and a per-run grant. For L6 the gate
    # short-circuits before any of them and refuses WITHOUT even opening a card.
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    AuthorizationStore(cfg).add_tool("self_install")
    inbox = ApprovalInbox()
    inbox.grant_run("r", "self_install")
    gate = HumanApprovalGate(inbox=inbox)
    approval = gate(_proposal("self_install", 6, writes=True), _dec(6), cfg, "r")
    assert not approval.granted
    assert "forbidden" in approval.reason.lower() or "app" in approval.reason.lower()
    assert inbox.pending("r") is None                # never prompted


def test_self_install_through_broker_never_executes_even_with_allowing_gate(
        cfg, tmp_path):
    # A gate whose inbox would auto-approve ANY card with "once" — proving that
    # even a human who would say yes cannot reach the self_install handler,
    # because L6 is refused before a card is ever opened.
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    before = (cfg.root / "crossaudit.yml").read_text()
    inbox = ApprovalInbox()
    t, state = _resolve_when_pending(inbox, "r", ONCE, spin=0.4)
    gate = HumanApprovalGate(inbox=inbox)
    b = _broker(cfg, tmp_path, approver=gate)
    r = b.execute({"tool": "self_install", "args": {"ref": "HEAD"}},
                  _full_token(cfg, ["self_install"]), cfg=cfg, run_id="r", now_epoch=0)
    t.join(2.0)
    _assert_needs_approval(r)
    assert state["fired"] is False                   # no card ever appeared to say yes
    assert "tool_result" not in _kinds(b)            # handler never ran
    assert (cfg.root / "crossaudit.yml").read_text() == before   # app unchanged
    # No candidate worktree / install artifact was produced either.
    assert not (cfg.root / cfg.state_dir / "candidate").exists()


# --------------------------------------------------------------------------- #
# (d) with a HumanApprovalGate, L4+ offers only once/deny — no standing grant   #
# --------------------------------------------------------------------------- #
def test_level4plus_cards_offer_only_once_or_deny():
    for level in (4, 5, 6):
        assert PendingApproval("r", "mcp_call", level, True).scopes() == [ONCE, DENY]
        assert PendingApproval("r", "mcp_call", level, True).per_call_only is True
    # Level 3 may still be granted for a run / project (contrast).
    assert PendingApproval("r", "run_check", 3, False).scopes() == [ONCE, RUN, PROJECT, DENY]


def test_level4_forged_run_or_project_scope_is_treated_as_once(cfg):
    # A forged "project" decision arriving for an L4 action must NOT become a
    # standing grant: it is honoured once and nothing persists.
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    t, state = _resolve_when_pending(inbox, "r", PROJECT)
    approval = gate(_proposal("mcp_call", 4, writes=True, host="svc"), _dec(4), cfg, "r")
    t.join(2.0)
    assert state["fired"] is True                    # a per-call card WAS required
    assert approval.granted                          # allowed this once
    assert not AuthorizationStore(cfg).authorized_tool("mcp_call")   # NOT persisted
    assert not inbox.run_granted("r", "mcp_call")                    # NOT a run grant


def test_per_project_tool_grant_cannot_auto_run_an_L4_tool(cfg, tmp_path, monkeypatch):
    # Even if the user (over-broadly) added mcp_call to the per-project approved
    # tools, an L4 call still opens a fresh card every time (never auto-granted).
    # Here the user denies at the card, so the external MCP tool never runs.
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    AuthorizationStore(cfg).add_tool("mcp_call")
    calls = []
    monkeypatch.setattr(mcp.MANAGER, "call_agent",
                        lambda *a, **k: calls.append((a, k)) or {"ok": True})
    inbox = ApprovalInbox()
    gate = HumanApprovalGate(inbox=inbox)
    t, state = _resolve_when_pending(inbox, "r", DENY)
    b = _broker(cfg, tmp_path, approver=gate)
    r = b.execute({"tool": "mcp_call",
                   "args": {"request": {"server_id": "srv", "tool": "do"}}},
                  _full_token(cfg, ["mcp_call"]), cfg=cfg, run_id="r", now_epoch=0)
    t.join(2.0)
    assert state["fired"] is True                    # a card was forced despite the grant
    _assert_needs_approval(r)
    assert calls == []                               # MCP tool NEVER invoked
    assert "tool_result" not in _kinds(b)
