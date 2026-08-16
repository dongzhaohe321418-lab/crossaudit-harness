"""Receipt ↔ evidence-ledger binding (the Phase-1 tool_evidence block).

This is also the end-to-end proof: a cycle that ran governed tools records
evidence in the ledger; its receipt binds the ledger head; verify() re-derives
both and confirms the binding, and refuses if the ledger is tampered. A cycle
that ran no tools mints a plain v2 receipt (no block) that still verifies — full
backward compatibility, no schema bump.
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
from crossaudit.receipt import build
from crossaudit.receipt.schema import validate
from crossaudit.receipt.verify import verify

from .conftest import GOOD_RESULTS, write_increment


def _mint(cfg, science: Path, *, with_tools: bool):
    sha = write_increment(science, GOOD_RESULTS, "Work done.", "increment")
    if with_tools:
        led = EvidenceLedger(cfg.root / cfg.state_dir / "evidence.jsonl")
        led.append("tool_call", run_id="r", payload={"tool": "file_read"}, ts="t0")
        led.append("decision", run_id="r", payload={"allow": True}, ts="t1")
        led.append("tool_result", run_id="r", payload={"sha256": "abc"}, ts="t2")
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


def test_tool_free_receipt_has_no_block_and_verifies(cfg, science):
    sha, receipt = _mint(cfg, science, with_tools=False)
    assert "tool_evidence" not in receipt        # byte-identical to plain v2
    validate(receipt)
    ev = verify(receipt, science_root=science, audit_root=science,
                expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert ev["verified"]


def test_receipt_binds_ledger_head_and_verifies(cfg, science):
    sha, receipt = _mint(cfg, science, with_tools=True)
    te = receipt.get("tool_evidence")
    assert te and te["entries"] == 3 and len(te["ledger_head"]) == 64
    ev = verify(receipt, science_root=science, audit_root=science,
                expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert ev["verified"]


def test_ledger_tamper_breaks_receipt_verification(cfg, science):
    sha, receipt = _mint(cfg, science, with_tools=True)
    ledger_file = cfg.root / cfg.state_dir / "evidence.jsonl"
    ledger_file.write_text(ledger_file.read_text().replace('"file_read"', '"HACKED"'))
    with pytest.raises(IntegrityDenial):
        verify(receipt, science_root=science, audit_root=science,
               expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def test_malformed_tool_evidence_is_rejected(cfg, science):
    _sha, receipt = _mint(cfg, science, with_tools=True)
    receipt["tool_evidence"]["entries"] = 0        # must be a positive integer
    with pytest.raises(IntegrityDenial):
        validate(receipt)
