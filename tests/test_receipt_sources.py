"""A4 (C.1): governed-source provenance binding.

A research cycle retrieves literature through the human-approved governed tools
(web_fetch / paper_search); each retrieval records per-source provenance ids in
the append-only evidence ledger. The receipt re-projects that tool_evidence-bound
prefix into an optional `sources` block; verify() re-derives it and refuses a
mismatch. A cycle that ran no governed retrieval mints a receipt with NO block —
byte-identical to a pre-A4 receipt, even one that used other (non-research) tools.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.controller import StateStore
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import materialise, parent, resolve
from crossaudit.ledger import EvidenceLedger
from crossaudit.receipt import build, sources
from crossaudit.receipt.schema import validate
from crossaudit.receipt.verify import verify

from .conftest import GOOD_RESULTS, write_increment

W1 = "a" * 64
P1 = sources.set_digest(["one"])[:0] + "b" * 64   # two distinct paper source ids
P2 = "c" * 64


def _mint(cfg, science: Path, *, kind: str):
    """kind: 'none' (no tools), 'nonresearch' (an L1 tool, no research),
    'research' (governed web_fetch + paper_search retrievals)."""
    sha = write_increment(science, GOOD_RESULTS, "Work done.", "increment")
    led = EvidenceLedger(cfg.root / cfg.state_dir / "evidence.jsonl")
    if kind == "nonresearch":
        led.append("tool_result", run_id="r", payload={
            "tool": "file_read", "status": "succeeded", "sha256": "abc"}, ts="t0")
    elif kind == "research":
        led.append("tool_result", run_id="r", payload={
            "tool": "paper_search", "status": "succeeded", "result_sha256": "y",
            "source": "arxiv", "source_ids": [P1, P2]}, ts="t0")
        led.append("tool_result", run_id="r", payload={
            "tool": "web_fetch", "status": "succeeded", "result_sha256": "z",
            "host": "example.org", "source_ids": [W1]}, ts="t1")
        # a FAILED research call records a row but contributes no source
        led.append("tool_result", run_id="r", payload={
            "tool": "web_fetch", "status": "failed", "error": "boom"}, ts="t2")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = subprocess.run(["git", "log", "-1", "--format=%H", "--", cfg.constitution],
                        cwd=str(cfg.root), capture_output=True, text=True,
                        check=False).stdout.strip()
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files,
                        notes=notes, constitution=const, constitution_commit=cc,
                        offline=True)
    manifest = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    ldir = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "report.md").write_text(outcome.report)
    _sha, tree = resolve(cfg.root, sha)
    receipt = build(
        cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "experiments"},
        cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
        constitution_bytes=(cfg.root / cfg.constitution).read_bytes(),
        constitution_commit=cc, dcl_source_sha256=dcl_source_digest(),
        prompt_sha256=outcome.prompt_sha256, checks=cfg.checks,
        verdict=outcome.verdict, exchange=outcome.exchange, retention="sealed",
        report_bytes=(ldir / "report.md").read_bytes(), report_commit="",
        cycle_path=str(ldir.relative_to(cfg.root)),
        audit_repo=cfg.audit_repo or "local", mode="local",
        integrity=outcome.integrity)
    return sha, receipt


def _verify(cfg, science, sha, receipt):
    return verify(receipt, science_root=science, audit_root=science,
                  expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def test_research_free_receipt_has_no_sources_block(cfg, science):
    sha, receipt = _mint(cfg, science, kind="none")
    assert "sources" not in receipt
    assert _verify(cfg, science, sha, receipt)["verified"]


def test_nonresearch_tool_receipt_still_has_no_sources_block(cfg, science):
    # tool_evidence is present, but no governed research row → no sources block,
    # so an existing tool-using receipt stays byte-identical (the must-fix gate).
    sha, receipt = _mint(cfg, science, kind="nonresearch")
    assert receipt.get("tool_evidence") is not None
    assert "sources" not in receipt
    assert _verify(cfg, science, sha, receipt)["verified"]


def test_research_receipt_binds_governed_sources_and_verifies(cfg, science):
    sha, receipt = _mint(cfg, science, kind="research")
    src = receipt.get("sources")
    assert src is not None
    assert src["count"] == 3                       # P1, P2, W1 (failed row excluded)
    assert src["origins"] == ["arxiv", "example.org"]
    assert src["set_sha256"] == sources.set_digest([P1, P2, W1])
    assert _verify(cfg, science, sha, receipt)["verified"]


def test_forged_source_digest_is_refused(cfg, science):
    sha, receipt = _mint(cfg, science, kind="research")
    receipt["sources"]["set_sha256"] = "0" * 64    # ledger intact, block forged
    with pytest.raises(IntegrityDenial):
        _verify(cfg, science, sha, receipt)


def test_forged_source_count_is_refused(cfg, science):
    sha, receipt = _mint(cfg, science, kind="research")
    receipt["sources"]["count"] = 99
    with pytest.raises(IntegrityDenial):
        _verify(cfg, science, sha, receipt)


def test_ledger_tamper_breaks_research_verification(cfg, science):
    sha, receipt = _mint(cfg, science, kind="research")
    lf = cfg.root / cfg.state_dir / "evidence.jsonl"
    lf.write_text(lf.read_text().replace(W1, "d" * 64))   # rewrite a source id
    with pytest.raises(IntegrityDenial):
        _verify(cfg, science, sha, receipt)


def test_offline_verify_without_ledger_still_passes(cfg, science):
    sha, receipt = _mint(cfg, science, kind="research")
    (cfg.root / cfg.state_dir / "evidence.jsonl").unlink()
    # No local ledger → the source cross-check is skipped (like tool_evidence),
    # and verification still succeeds on the manifest/bindings alone.
    assert _verify(cfg, science, sha, receipt)["verified"]


def test_schema_rejects_malformed_sources_block(cfg, science):
    _sha, receipt = _mint(cfg, science, kind="research")
    receipt["sources"]["count"] = 0                # must be a positive integer
    with pytest.raises(IntegrityDenial):
        validate(receipt)


def test_schema_rejects_sources_without_tool_evidence(cfg, science):
    _sha, receipt = _mint(cfg, science, kind="research")
    receipt.pop("tool_evidence")                   # no bound prefix to re-derive
    with pytest.raises(IntegrityDenial):
        validate(receipt)


def test_absent_sources_block_still_validates(cfg, science):
    _sha, receipt = _mint(cfg, science, kind="none")
    validate(receipt)                              # absence never denies
