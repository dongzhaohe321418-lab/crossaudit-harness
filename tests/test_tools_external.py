"""Phases 4-6: HPC/MCP/self-improve tools — gated, never fired, self-install banned.

hpc_submit (L5) and mcp_call (L4) never auto-run: the broker returns
needs_approval and the underlying manager is never invoked. self_install (L6) is
refused at both the broker gate and the handler, so the model can never modify
the running app. A self-improvement candidate lives in an isolated worktree.
"""
from __future__ import annotations

import pytest

from crossaudit import hpc, mcp
from crossaudit.broker import ToolBroker, full_registry
from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.registry import ToolError
from crossaudit.broker.selfimprove import candidate_worktree, self_install
from crossaudit.broker.tools_hpc import hpc_submit
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _tok(tools):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": list(tools), "paths": ["**"],
        "writable": True, "hosts": ["cluster"], "expires_at": "2100-01-01T00:00:00Z"})


def _broker(tmp_path):
    return ToolBroker(full_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))


def test_hpc_submit_never_auto_runs(cfg, tmp_path, monkeypatch):
    fired = []
    monkeypatch.setattr(hpc.MANAGER, "submit",
                        lambda c, p, **k: fired.append(1) or {"job_id": "J1"})
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)      # even fully authorized
    r = _broker(tmp_path).execute(
        {"tool": "hpc_submit", "args": {"manifest": {"cmd": "x"}}},
        _tok(["hpc_submit"]), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval" and fired == []      # nothing submitted


def test_mcp_call_never_auto_runs(cfg, tmp_path, monkeypatch):
    fired = []
    monkeypatch.setattr(mcp.MANAGER, "call_agent",
                        lambda c, req, **k: fired.append(1) or {"status": "ok"})
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    r = _broker(tmp_path).execute(
        {"tool": "mcp_call", "args": {"server_id": "s", "tool": "t"}},
        _tok(["mcp_call"]), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval" and fired == []


def test_self_install_is_always_refused(cfg, tmp_path):
    with pytest.raises(ToolError):
        self_install(cfg, {}, _tok(["self_install"]))       # handler always refuses
    r = _broker(tmp_path).execute({"tool": "self_install", "args": {}},
                                  _tok(["self_install"]), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status in ("needs_approval", "refused")         # never succeeds


def test_hpc_submit_records_only_a_manifest_hash(cfg, monkeypatch):
    monkeypatch.setattr(hpc.MANAGER, "submit", lambda c, p, **k: {"job_id": "J9"})
    out = hpc_submit(cfg, {"manifest": {"cmd": "run"}}, _tok(["hpc_submit"]))
    assert out["job_id"] == "J9" and len(out["manifest_sha256"]) == 64


def test_candidate_worktree_is_isolated_from_the_running_tree(cfg):
    wt = candidate_worktree(cfg)
    assert wt.exists() and wt == cfg.root / cfg.state_dir / "candidate"
    assert wt != cfg.root                                    # separate worktree
