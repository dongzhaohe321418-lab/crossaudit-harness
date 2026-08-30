"""D10 guards for receipt claims that must be re-derived, not echoed."""
from __future__ import annotations

import hashlib
import json
import importlib

import pytest

from crossaudit.broker import routing
from crossaudit.errors import IntegrityDenial
from crossaudit.ledger.chain import VerifyReport
from crossaudit.receipt.schema import digest
verify_mod = importlib.import_module("crossaudit.receipt.verify")

from .test_receipt_tool_evidence import _mint
from .conftest import git


def _verify(cfg, science, sha, receipt):
    return verify_mod.verify(receipt, science_root=science, audit_root=science,
                             expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def test_constitution_is_checked_against_the_cited_object_not_disk(
        cfg, science, monkeypatch):
    sha, receipt = _mint(cfg, science, with_tools=False)
    const = science / cfg.constitution
    const.write_bytes(b"forged working-tree rules")
    receipt["inputs"]["constitution_sha256"] = hashlib.sha256(
        const.read_bytes()).hexdigest()

    with pytest.raises(IntegrityDenial, match="constitution content differs"):
        _verify(cfg, science, sha, receipt)

    # D10 counterfactual: the old working-tree reader would accept this forged
    # hash. The named source-of-truth guard must therefore go red under that
    # mutation, rather than merely proving that the helper exists.
    monkeypatch.setattr(
        verify_mod, "read_committed_bytes",
        lambda _repo, _commit, _path: const.read_bytes())
    with pytest.raises(AssertionError, match="CONSTITUTION_COMMIT_GUARD"):
        accepted = False
        try:
            _verify(cfg, science, sha, receipt)
        except IntegrityDenial:
            pass
        else:
            accepted = True
        assert not accepted, "CONSTITUTION_COMMIT_GUARD"


def test_report_hash_is_checked_against_the_cited_report_commit(
        cfg, science, monkeypatch):
    sha, receipt = _mint(cfg, science, with_tools=False)
    report = science / receipt["ledger"]["cycle_path"] / "report.md"
    original = report.read_bytes()
    git("add", "--", str(report.relative_to(science)), cwd=science)
    git("commit", "-q", "-m", "commit audit report", cwd=science)
    report_commit = git("rev-parse", "HEAD", cwd=science)
    receipt["ledger"]["report_commit"] = report_commit
    report.write_bytes(original + b"post-commit edit\n")
    receipt["ledger"]["report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()

    with pytest.raises(IntegrityDenial, match="report blob hash mismatch"):
        _verify(cfg, science, sha, receipt)

    # Historical working-tree verification would accept the edited report and
    # its edited hash. Make that mutation explicit and require the named guard
    # to fail its own assertion.
    monkeypatch.setattr(
        verify_mod, "read_committed_bytes",
        lambda _repo, commit, path: (
            (science / path).read_bytes() if commit == report_commit
            else (science / path).read_bytes()))
    with pytest.raises(AssertionError, match="REPORT_COMMIT_GUARD"):
        accepted = False
        try:
            _verify(cfg, science, sha, receipt)
        except IntegrityDenial:
            pass
        else:
            accepted = True
        assert not accepted, "REPORT_COMMIT_GUARD"


def test_cycle_verdict_and_pin_are_rederived_from_controller_state(
        cfg, science, monkeypatch):
    sha, receipt = _mint(cfg, science, with_tools=False)
    cycle_id = receipt["cycle"]["cycle_id"]
    cc = receipt["inputs"]["constitution_commit"]
    receipt["cycle"]["constitution_commit"] = cc
    path = cfg.root / cfg.state_dir / "state.json"
    state = json.loads(path.read_text())
    row = state["cycles"][cycle_id]
    row["constitution_commit"] = cc
    row["verdicts"] = [{
        "round": receipt["cycle"]["round"], "sha": sha,
        "verdict": receipt["audit"]["verdict"], "status": "ESCALATED",
        "receipt": digest(receipt)[:16], "constitution_commit": cc,
    }]
    row["status"] = "ESCALATED"
    row["awaiting_verdict"] = False
    path.write_text(json.dumps(state))

    state["cycles"][cycle_id]["constitution_commit"] = "0" * 40
    path.write_text(json.dumps(state))
    with pytest.raises(IntegrityDenial, match="pinned constitution"):
        _verify(cfg, science, sha, receipt)

    # D10 counterfactual: removing the cycle-record guard lets the forged state
    # through; the explicit assertion below must go red under that mutation.
    monkeypatch.setattr(verify_mod, "_verify_cycle_record", lambda *_args: None)
    with pytest.raises(AssertionError, match="CYCLE_RECORD_GUARD"):
        accepted = False
        try:
            _verify(cfg, science, sha, receipt)
        except IntegrityDenial:
            pass
        else:
            accepted = True
        assert not accepted, "CYCLE_RECORD_GUARD"


def test_broken_evidence_chain_is_not_projected_to_the_auditor(
        cfg, science, monkeypatch):
    _sha, _receipt = _mint(cfg, science, with_tools=True)
    ledger_file = cfg.root / cfg.state_dir / "evidence.jsonl"
    ledger_file.write_text(ledger_file.read_text().replace('"file_read"', '"FORGED"'))
    with pytest.raises(IntegrityDenial, match="evidence ledger cannot be shown"):
        routing.evidence_view(cfg)

    # D10 counterfactual: the historical projector ignored verify() and would
    # return forged rows. A no-op verification mutation must make this guard go
    # red by its own name.
    monkeypatch.setattr(routing.EvidenceLedger, "verify",
                        lambda _self: VerifyReport(ok=True))
    with pytest.raises(AssertionError, match="EVIDENCE_CHAIN_GUARD"):
        accepted = False
        try:
            routing.evidence_view(cfg)
        except IntegrityDenial:
            pass
        else:
            accepted = True
        assert not accepted, "EVIDENCE_CHAIN_GUARD"
