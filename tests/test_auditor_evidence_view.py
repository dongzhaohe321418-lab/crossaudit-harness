"""The Auditor's read-only evidence view.

The Auditor reviews an allowlisted projection of the evidence ledger — hashes
and policy decisions only, never raw tool output — so it can judge whether tool
use was appropriate without its context being influenced by untrusted content,
and it gets NO live tools. When no tools ran, the audit prompt is unchanged.
"""
from __future__ import annotations

import json

from crossaudit.auditor import prompt as prompt_mod
from crossaudit.broker.routing import evidence_view
from crossaudit.ledger import EvidenceLedger


def _prompt(tool_evidence=None):
    return prompt_mod.build("C", "commit1", {"checks": []}, {}, "task",
                            tool_evidence=tool_evidence)[0]


def test_prompt_identical_when_no_tool_evidence():
    base = prompt_mod.build("C", "commit1", {"checks": []}, {}, "task")[0]
    assert _prompt(None) == base and _prompt([]) == base
    assert "TOOL-EVIDENCE" not in base


def test_prompt_includes_hashes_and_decisions_when_present():
    ev = [
        {"seq": 0, "kind": "tool_call", "tool": "file_read", "args_sha256": "aaa"},
        {"seq": 1, "kind": "decision", "tool": "file_read", "allow": True,
         "reason": "within grant"},
        {"seq": 2, "kind": "tool_result", "tool": "file_read",
         "result_sha256": "bbb", "status": "succeeded"},
    ]
    p = _prompt(ev)
    assert "GOVERNED TOOL EVIDENCE" in p and "<<<TOOL-EVIDENCE" in p
    for token in ("file_read", "aaa", "bbb", "within grant", "succeeded"):
        assert token in p


def test_evidence_view_allowlists_and_strips_raw_content(cfg):
    led = EvidenceLedger(cfg.root / cfg.state_dir / "evidence.jsonl")
    led.append("tool_call", run_id="r",
               payload={"tool": "file_read", "args_sha256": "aaa",
                        "raw_output": "SECRET"}, ts="t0")
    led.append("tool_result", run_id="r",
               payload={"tool": "file_read", "result_sha256": "bbb",
                        "status": "succeeded", "content": "SECRET2"}, ts="t1")
    view = evidence_view(cfg)
    assert len(view) == 2
    blob = json.dumps(view)
    # Raw output and any non-allowlisted key are dropped.
    assert "SECRET" not in blob and "raw_output" not in blob and "content" not in blob
    assert view[0]["tool"] == "file_read" and view[0]["args_sha256"] == "aaa"
    assert view[1]["result_sha256"] == "bbb" and view[1]["status"] == "succeeded"


def test_evidence_view_empty_when_no_ledger(cfg):
    assert evidence_view(cfg) == []
