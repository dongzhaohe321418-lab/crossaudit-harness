"""The Application Service seam.

Both the CLI and the console must reach the build loop and a governed Tool
Broker through one module, so tool use is governed identically no matter the
entry point. These check the seam exposes the single loop (not a copy) and
builds a working per-project broker whose evidence lands in the state dir.
"""
from __future__ import annotations

from crossaudit import appservice
from crossaudit.cli import build as cli_build
from crossaudit.broker import ToolBroker


def test_seam_reexports_the_one_build_loop():
    # Same object, not a reimplementation — the console watches this exact loop.
    assert appservice.run_loop is cli_build.run_loop
    assert appservice.resolve_task is cli_build.resolve_task
    assert appservice.preflight is cli_build.preflight
    assert hasattr(appservice, "talk")


def test_evidence_path_is_in_state_dir(cfg):
    p = appservice.evidence_path(cfg)
    assert p.parent == cfg.root / cfg.state_dir
    assert p.name.endswith(".jsonl")


def test_readonly_catalog_lists_the_readonly_tools():
    names = {t["name"] for t in appservice.readonly_tool_catalog()}
    assert names == {"file_read", "search", "git_status", "doctor", "git_diff", "git_log"}
    assert all(t["level"] == 1 and not t["writes"] for t in appservice.readonly_tool_catalog())


def test_broker_for_builds_a_governed_working_broker(cfg):
    from crossaudit.policy import CapabilityToken
    broker = appservice.broker_for(cfg)
    assert isinstance(broker, ToolBroker)
    token = CapabilityToken.parse({
        "project_id": "p", "run_id": "run1", "tools": ["file_read"],
        "paths": ["**"], "expires_at": "2100-01-01T00:00:00Z"})
    r = broker.execute({"tool": "file_read", "args": {"path": "crossaudit.yml"}},
                       token, cfg=cfg, run_id="run1", now_epoch=0)
    assert r.ok and "science_repo" in r.output["content"]
    assert broker.ledger.verify().ok
    assert appservice.evidence_path(cfg).exists()
