"""Older tool/compute results are condensed deterministically for the prompt.

A tool-heavy run used to re-serialize every past result into every later prompt.
Now only the recent tail is kept verbatim; older results become a compact marker
(tool, byte length, stable fingerprint, short preview). The marker must be the
same across two otherwise-identical runs, so a random per-call id may not leak
into it — and it must not promise a recall path (raw output is retained nowhere).
"""
from __future__ import annotations

from crossaudit.cli.build import KEEP_RECENT_RESULTS, _fold_results


def _run(seed: str) -> list[dict]:
    # A fresh random-ish call_id per run, as the real MCP path produces.
    return [{"call_id": f"{seed}-{i:04x}", "tool": "web.fetch", "status": "ok",
             "result": f"payload body number {i}"}
            for i in range(KEEP_RECENT_RESULTS + 3)]


def test_a_short_list_is_returned_unchanged():
    res = [{"call_id": "z", "tool": "t", "result": 1}]
    assert _fold_results(res) == res


def test_recent_tail_is_kept_verbatim():
    res = _run("aaa")
    out = _fold_results(res)
    assert out[-KEEP_RECENT_RESULTS:] == res[-KEEP_RECENT_RESULTS:]
    assert out[0].get("elided") is True
    assert sum(1 for x in out if x.get("elided")) == 3


def test_folding_is_deterministic_across_volatile_call_ids():
    folded_a = [x for x in _fold_results(_run("aaa")) if x.get("elided")]
    folded_b = [x for x in _fold_results(_run("bbb")) if x.get("elided")]
    assert folded_a == folded_b                 # identical despite different ids
    assert len(folded_a) == 3


def test_marker_does_not_leak_the_volatile_id():
    marker = next(x for x in _fold_results(_run("secret-seed")) if x.get("elided"))
    assert "secret-seed" not in marker["preview"]
    assert "call_id" not in marker
    assert marker["tool"] == "web.fetch" and marker["bytes"] > 0
    assert "fingerprint" in marker and len(marker["fingerprint"]) == 16


def test_marker_note_does_not_promise_ledger_recovery():
    marker = next(x for x in _fold_results(_run("a")) if x.get("elided"))
    assert "ledger" not in marker["note"].lower()   # raw output is not retained
