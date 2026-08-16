"""The Tool Broker closed loop — proposal → policy → execute → evidence.

This is the Phase-1 proof: a read-only proposal in scope runs and is recorded;
an out-of-scope, unknown, or write proposal is refused *before* execution; every
call leaves an append-only evidence trail; and tampering with that trail is
caught by re-verification. It uses the shared ``cfg`` fixture (a real git repo
with committed files).
"""
from __future__ import annotations

from crossaudit.broker import ToolBroker, ToolSpec, default_registry
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _token(paths, tools=("file_read", "search", "git_status", "doctor"), **kw):
    return CapabilityToken.parse({
        "project_id": "p1", "run_id": "run1", "tools": list(tools),
        "paths": list(paths), "expires_at": "2100-01-01T00:00:00Z", **kw})


def _broker(tmp_path):
    return ToolBroker(default_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))


def _run(broker, request, token, cfg):
    return broker.execute(request, token, cfg=cfg, run_id="run1", now_epoch=0)


def test_readonly_file_read_runs_and_is_recorded(cfg, tmp_path):
    b = _broker(tmp_path)
    r = _run(b, {"tool": "file_read", "args": {"path": "crossaudit.yml"}},
             _token(["**"]), cfg)
    assert r.ok and "science_repo" in r.output["content"]
    assert r.result_sha256 and len(r.evidence) == 3  # tool_call + decision + tool_result
    assert b.ledger.verify().ok and b.ledger.verify().count == 3


def test_out_of_scope_path_is_refused_before_execution(cfg, tmp_path):
    b = _broker(tmp_path)
    r = _run(b, {"tool": "file_read", "args": {"path": "crossaudit.yml"}},
             _token(["work/**"]), cfg)   # grant does not cover the repo root
    assert r.status == "refused" and "outside" in r.reason
    assert len(r.evidence) == 2          # recorded call + decision, no result
    assert b.ledger.verify().ok


def test_unknown_tool_is_refused(cfg, tmp_path):
    b = _broker(tmp_path)
    r = _run(b, {"tool": "delete_everything", "args": {}}, _token(["**"]), cfg)
    assert r.status == "refused" and "unknown tool" in r.reason
    assert len(r.evidence) == 2


def test_write_tool_denied_under_readonly_grant(cfg, tmp_path):
    b = _broker(tmp_path)
    # A hypothetical Level-2 write tool: the broker must plumb writes→policy and
    # refuse it under a read-only grant, before the handler ever runs.
    ran = []
    b.registry.register(ToolSpec(
        name="edit", level=2, writes=True, needs_network=False,
        handler=lambda cfg, a, t: ran.append(1) or {"ok": True},
        path_args=("path",)))
    r = _run(b, {"tool": "edit", "args": {"path": "crossaudit.yml"}},
             _token(["**"], tools=["edit"]), cfg)
    assert r.status == "refused" and "read-only" in r.reason
    assert ran == []                     # handler never executed


def test_search_and_status_and_doctor(cfg, tmp_path):
    b = _broker(tmp_path)
    tok = _token(["**"])
    s = _run(b, {"tool": "search", "args": {"query": "science_repo"}}, tok, cfg)
    assert s.ok and s.output["count"] >= 1
    st = _run(b, {"tool": "git_status", "args": {}}, tok, cfg)
    assert st.ok and "clean" in st.output
    dr = _run(b, {"tool": "doctor", "args": {}}, tok, cfg)
    assert dr.ok and isinstance(dr.output, dict)
    assert b.ledger.verify().ok


def test_evidence_tamper_is_detected(cfg, tmp_path):
    b = _broker(tmp_path)
    _run(b, {"tool": "file_read", "args": {"path": "crossaudit.yml"}},
         _token(["**"]), cfg)
    # Forge a "succeeded" outcome by rewriting the recorded result status.
    text = b.ledger.path.read_text()
    tampered = text.replace('"status":"succeeded"', '"status":"FORGED"')
    assert tampered != text
    b.ledger.path.write_text(tampered)
    assert not b.ledger.verify().ok      # the chain no longer re-derives


def test_expired_grant_refused(cfg, tmp_path):
    b = _broker(tmp_path)
    tok = CapabilityToken.parse({
        "project_id": "p1", "run_id": "run1", "tools": ["file_read"],
        "paths": ["**"], "expires_at": "2000-01-01T00:00:00Z"})
    r = b.execute({"tool": "file_read", "args": {"path": "crossaudit.yml"}},
                  tok, cfg=cfg, run_id="run1", now_epoch=4102444800)
    assert r.status == "refused" and "expired" in r.reason
