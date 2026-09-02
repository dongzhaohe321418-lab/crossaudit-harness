"""P14 — the governed-actions (evidence) panel makes the audit trail visible.

The panel projects the SAME allowlisted evidence_view the auditor sees (hashes,
decisions, approvals, statuses — never raw output), folded into one row per
governed action. It is read-only and never surfaces content.
"""
from __future__ import annotations

from crossaudit.broker.routing import broker_for, governed_actions, readonly_token
from crossaudit.console.page import PAGE
from crossaudit.console.server import snapshot


def _run(cfg, tool, args=None):
    broker = broker_for(cfg)                       # read-only registry + project ledger
    tok = readonly_token(cfg, run_id="r", now_epoch=0)
    return broker.execute({"tool": tool, "args": args or {}}, tok,
                          cfg=cfg, run_id="r", now_epoch=0)


def test_no_actions_by_default(cfg):
    assert governed_actions(cfg) == []
    assert snapshot(cfg)["governed_actions"] == []


def test_actions_are_grouped_most_recent_first(cfg):
    _run(cfg, "git_status")                        # allowed read → succeeds
    _run(cfg, "definitely_not_a_tool")             # unknown → refused
    acts = governed_actions(cfg)
    assert len(acts) == 2
    assert acts[0]["tool"] == "definitely_not_a_tool" and acts[0]["outcome"] == "refused"
    ok = next(a for a in acts if a["tool"] == "git_status")
    assert ok["outcome"] == "succeeded" and ok["decision"] == "allow"
    assert ok["level"] == 1 and ok["result_sha256"]     # a hash, never raw output


def test_snapshot_exposes_the_panel_data(cfg):
    _run(cfg, "doctor")
    snap = snapshot(cfg)
    assert snap["governed_actions"] and snap["governed_actions"][0]["tool"] == "doctor"


def test_governed_actions_never_carry_raw_output(cfg):
    # file_read returns file bytes; only the result hash may appear, never content.
    (cfg.root / "work").mkdir(parents=True, exist_ok=True)
    (cfg.root / "work/secret.txt").write_text("TOP-SECRET-VALUE-12345")
    _run(cfg, "file_read", {"path": "work/secret.txt"})
    acts = governed_actions(cfg)
    blob = repr(acts)
    assert "TOP-SECRET-VALUE" not in blob
    read = next(a for a in acts if a["tool"] == "file_read")
    assert read["result_sha256"]


def test_page_markup_contains_the_governed_panel():
    """MARKUP ONLY. This asserts strings are present in ``page.py``; it does not
    render anything and cannot fail if the page never reaches a person. Renamed
    under D106: serving an empty document leaves it green, so a name claiming
    "renders"/"announces" was a property nobody tested.
    """
    assert 'data-view="evidence"' in PAGE
    assert "evidenceView" in PAGE and "governed_actions" in PAGE
    assert "Governed actions" in PAGE and "This is the audit trail" in PAGE
