"""Level-2 recoverable write tool + the broker's approval gate.

The mechanism is proven directly: a write is scoped, escape-proof, atomic, and
reversible via a recovery point (restore puts old content back, or deletes a
file the tool created). And crucially the broker does NOT auto-run a write —
it returns ``needs_approval`` until an Approval Service exists, so no file
changes without a human in the loop.
"""
from __future__ import annotations

import pytest

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.recovery import RecoveryStore, resolve_in_root
from crossaudit.broker.registry import ToolError
from crossaudit.broker.tools_write import MAX_WRITE_BYTES, file_write
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _writable(paths=("**",)):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["file_write", "file_read"],
        "paths": list(paths), "writable": True,
        "expires_at": "2100-01-01T00:00:00Z"})


# -- mechanism (handler called directly) --
def test_write_creates_file_and_reports_diff(cfg):
    r = file_write(cfg, {"path": "work/new.md", "content": "hello"}, _writable())
    assert (cfg.root / "work/new.md").read_text() == "hello"
    assert r["existed_before"] is False and r["pre_sha256"] == ""
    assert r["post_sha256"] and r["bytes"] == 5 and r["recoverable"]


def test_recovery_point_restores_prior_content(cfg):
    (cfg.root / "work").mkdir(parents=True, exist_ok=True)
    (cfg.root / "work/a.md").write_text("original")
    rec = RecoveryStore(cfg)
    record = rec.snapshot("work/a.md")
    file_write(cfg, {"path": "work/a.md", "content": "changed"}, _writable())
    assert (cfg.root / "work/a.md").read_text() == "changed"
    rec.restore(record)
    assert (cfg.root / "work/a.md").read_text() == "original"


def test_recovery_of_a_new_file_deletes_it(cfg):
    rec = RecoveryStore(cfg)
    record = rec.snapshot("work/created.md")        # does not exist yet
    file_write(cfg, {"path": "work/created.md", "content": "x"}, _writable())
    assert (cfg.root / "work/created.md").is_file()
    rec.restore(record)
    assert not (cfg.root / "work/created.md").exists()


def test_write_refuses_out_of_scope(cfg):
    with pytest.raises(ToolError):
        file_write(cfg, {"path": "secret.env", "content": "x"},
                   _writable(paths=("work/**",)))


@pytest.mark.parametrize("evil", ["../outside.txt", "/etc/passwd", "~/x"])
def test_write_refuses_escape(cfg, evil):
    with pytest.raises(ToolError):
        file_write(cfg, {"path": evil, "content": "x"}, _writable())


def test_resolve_in_root_rejects_escapes(cfg):
    assert resolve_in_root(cfg.root, "work/a.md") is not None
    for evil in ["/etc/passwd", "../x", "~/x", ""]:
        assert resolve_in_root(cfg.root, evil) is None


def test_write_over_the_byte_limit_refused(cfg):
    with pytest.raises(ToolError):
        file_write(cfg, {"path": "work/big.md", "content": "x" * (MAX_WRITE_BYTES + 1)},
                   _writable())


# -- the broker gate: writes need approval, never auto-run --
def test_broker_gates_write_behind_approval(cfg, tmp_path):
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    r = broker.execute({"tool": "file_write", "args": {"path": "work/x.md", "content": "y"}},
                       _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"
    assert not (cfg.root / "work/x.md").exists()     # nothing written without a human
    # The proposal + decision are still recorded as evidence.
    assert broker.ledger.verify().ok and broker.ledger.verify().count >= 2


def test_broker_denies_write_under_readonly_grant(cfg, tmp_path):
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    readonly = CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["file_write"],
        "paths": ["**"], "expires_at": "2100-01-01T00:00:00Z"})  # writable defaults False
    r = broker.execute({"tool": "file_write", "args": {"path": "work/x.md", "content": "y"}},
                       readonly, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "refused" and "read-only" in r.reason
    assert not (cfg.root / "work/x.md").exists()
