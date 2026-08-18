"""A4 (C.2): the deterministic citation-provenance check.

Opt-in (`source_provenance` in `checks:`), context-aware, and non-overridable: a
report may only declare sources it actually retrieved through the governed
research tools. A declared id with no governed evidence is a BLOCKER the model
audit cannot waive; a report that declares nothing passes.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from crossaudit.dcl import builtin, neutral, provenance  # noqa: F401  (register)
from crossaudit.dcl.framework import BLOCKER, CheckContext, available, run_checks
from crossaudit.dcl.profiles import resolve
from crossaudit.ledger import EvidenceLedger
from crossaudit.receipt import sources

G1, G2, UNGOVERNED = "a" * 64, "b" * 64, "f" * 64
CTX = CheckContext(governed_source_ids=frozenset({G1, G2}))


def _report(ids: list[str]) -> bytes:
    body = "[" + ", ".join(f'"{i}"' for i in ids) + "]"
    return ("# Report\n\nprose\n\n```crossaudit-sources\n" + body + "\n```\n").encode()


def test_declared_sources_that_are_all_governed_pass():
    r = run_checks({"report.md": _report([G1, G2])}, ["source_provenance"], context=CTX)
    assert r.hard_failures == 0


def test_a_declared_source_that_was_not_governed_is_blocked():
    r = run_checks({"report.md": _report([G1, UNGOVERNED])}, ["source_provenance"],
                   context=CTX)
    assert r.hard_failures == 1
    f = r.findings[0]
    assert f.rule == "CA-SOURCE-001" and f.severity == BLOCKER


def test_a_report_that_declares_no_sources_passes():
    r = run_checks({"report.md": b"# Report\n\nno block here\n"},
                   ["source_provenance"], context=CTX)
    assert r.hard_failures == 0


def test_a_malformed_declaration_block_is_blocked():
    bad = b"# R\n\n```crossaudit-sources\nnot valid json\n```\n"
    r = run_checks({"report.md": bad}, ["source_provenance"], context=CTX)
    assert r.hard_failures == 1 and r.findings[0].rule == "CA-SOURCE-001"


def test_a_declaration_that_is_not_an_array_is_blocked():
    bad = b'# R\n\n```crossaudit-sources\n{"id": "x"}\n```\n'
    r = run_checks({"report.md": bad}, ["source_provenance"], context=CTX)
    assert r.hard_failures == 1


def test_declaration_without_any_governed_evidence_is_blocked():
    # No context (empty governed set): a claimed governed source cannot be
    # confirmed, so it fails closed.
    r = run_checks({"report.md": _report([G1])}, ["source_provenance"])
    assert r.hard_failures == 1


def test_the_check_is_opt_in_and_off_by_default():
    assert "source_provenance" not in resolve("general")
    assert "source_provenance" in resolve("research")
    assert "source_provenance" in available()


def test_legacy_checks_still_run_without_context():
    # A context-aware check coexists with plain fn(files) checks in one run.
    r = run_checks({"a.json": b"{ not json", "report.md": _report([G1])},
                   ["parseable", "source_provenance"], context=CTX)
    rules = {f.rule for f in r.findings}
    assert "CA-FILE-001" in rules            # parseable (legacy) fired
    assert r.hard_failures == 1              # only the bad json; sources are governed


def test_governed_source_ids_reads_the_live_ledger():
    d = Path(tempfile.mkdtemp())
    cfg = SimpleNamespace(root=d, state_dir=".crossaudit")
    led = EvidenceLedger(d / ".crossaudit" / "evidence.jsonl")
    led.append("tool_result", run_id="r", payload={
        "tool": "web_fetch", "status": "succeeded", "host": "x.org",
        "source_ids": [G1]}, ts="t0")
    led.append("tool_result", run_id="r", payload={
        "tool": "paper_search", "status": "succeeded", "source": "arxiv",
        "source_ids": [G2]}, ts="t1")
    led.append("tool_result", run_id="r", payload={
        "tool": "web_fetch", "status": "failed", "error": "x"}, ts="t2")
    governed = sources.governed_source_ids(cfg)
    assert governed == frozenset({G1, G2})
    ctx = CheckContext(governed_source_ids=governed)
    # a report citing a governed source passes; citing an un-fetched one blocks
    assert run_checks({"r.md": _report([G1, G2])}, ["source_provenance"],
                      context=ctx).hard_failures == 0
    assert run_checks({"r.md": _report([UNGOVERNED])}, ["source_provenance"],
                      context=ctx).hard_failures == 1
