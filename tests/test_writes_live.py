"""Writes go live only under per-project authorization.

A build's tool catalog and capability token are read-only by default; when the
user turns on this project's ``workspace_writes`` authorization, the build gains
``file_write`` and a writable token — so the model can edit files, recoverably
and audited, but only after the explicit opt-in. Without it, a write proposal is
refused and nothing changes.
"""
from __future__ import annotations

from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.routing import build_broker_and_token, build_catalog

_READONLY = {"file_read", "search", "git_status", "doctor", "git_diff", "git_log"}


def test_unauthorized_project_is_read_only(cfg):
    assert {t["name"] for t in build_catalog(cfg)} == _READONLY
    broker, tok = build_broker_and_token(cfg, run_id="r", now_epoch=0)
    assert not tok.writable and not tok.allows_tool("file_write")
    r = broker.execute({"tool": "file_write", "args": {"path": "work/x.md", "content": "y"}},
                       tok, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "refused"
    assert not (cfg.root / "work/x.md").exists()


def test_authorized_project_can_write_and_it_is_audited(cfg):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    assert "file_write" in {t["name"] for t in build_catalog(cfg)}
    broker, tok = build_broker_and_token(cfg, run_id="r", now_epoch=0)
    assert tok.writable and tok.allows_tool("file_write")
    r = broker.execute({"tool": "file_write", "args": {"path": "work/x.md", "content": "hi"}},
                       tok, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "succeeded"
    assert (cfg.root / "work/x.md").read_text() == "hi"
    # The write's diff is recorded and the chain verifies.
    results = [e for e in broker.ledger.entries() if e["kind"] == "tool_result"]
    assert results and results[-1]["payload"]["post_sha256"]
    assert broker.ledger.verify().ok
