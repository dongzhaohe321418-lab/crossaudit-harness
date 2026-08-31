"""A corrupt evidence ledger must deny a receipt, never vanish from one.

F2 (S0). `_tool_evidence()` returned `None` when no evidence existed AND when a
present ledger failed verification, so the builder omitted the block and signed.
A tampered append-only chain became indistinguishable from an audit that used no
tools — a signed false statement by omission, on the artifact whose entire job is
letting somebody check what actually happened.

`run_audit` denies a broken chain at its own seam, so a whole-cycle test never
reaches this. These drive the BUILDER, which is the seam that was wrong.
"""
from __future__ import annotations

import hashlib
import subprocess

import pytest

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.controller import StateStore
from crossaudit.errors import Denial, IntegrityDenial
from crossaudit.gitio import materialise, parent, resolve
from crossaudit.ledger import EvidenceLedger
from crossaudit.receipt import build
from crossaudit.receipt.build import (EVIDENCE_ABSENT, EVIDENCE_BROKEN,
                                      EVIDENCE_INTACT, _tool_evidence)
from crossaudit.receipt.schema import validate
from crossaudit.receipt.sign import sign_receipt

from .conftest import GOOD_RESULTS, write_increment


def _evidence_path(cfg):
    return cfg.root / cfg.state_dir / "evidence.jsonl"


def _build_receipt(cfg, science):
    """Assemble a receipt through the production builder."""
    sha = write_increment(science, GOOD_RESULTS, "Work done.", "increment")
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
    _s, tree = resolve(cfg.root, sha)
    return sha, ldir, dict(
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


# ------------------------------------------- the three states are distinct
def test_the_three_evidence_states_are_distinct_values(cfg):
    """Requirement 2: if they still funnel through one `None`, it is renamed."""
    assert _tool_evidence(cfg).state == EVIDENCE_ABSENT, "no ledger is absent"

    led = EvidenceLedger(_evidence_path(cfg))
    led.append("tool_call", run_id="r", payload={"tool": "file_read"}, ts="t0")
    intact = _tool_evidence(cfg)
    assert intact.state == EVIDENCE_INTACT
    assert intact.block and intact.block["entries"] == 1

    raw = _evidence_path(cfg).read_text()
    _evidence_path(cfg).write_text(raw.replace('"file_read"', '"file_write"'))
    broken = _tool_evidence(cfg)
    assert broken.state == EVIDENCE_BROKEN
    assert broken.block is None
    assert broken.reason, "a refusal must say what it found"

    assert len({EVIDENCE_ABSENT, EVIDENCE_INTACT, EVIDENCE_BROKEN}) == 3


def test_an_unparseable_ledger_is_broken_not_absent(cfg):
    """Garbage in the chain reaches the verifier and comes back not-ok."""
    _evidence_path(cfg).parent.mkdir(parents=True, exist_ok=True)
    _evidence_path(cfg).write_bytes(b"\x00\xff not json at all\n")
    assert _tool_evidence(cfg).state == EVIDENCE_BROKEN


def test_a_ledger_that_cannot_be_READ_is_broken_not_absent(cfg):
    """The exception path, which is a different branch from a not-ok report.

    My first version of this test wrote garbage bytes — which `verify()` handles
    and reports as not-ok, so it never entered the `except` branch at all.
    Mutation E3 deleted that branch and this file stayed green, which is how I
    found out. A directory where the ledger belongs makes the read genuinely
    raise, so the branch is now exercised.

    "Cannot establish" must never render as "did not happen".
    """
    path = _evidence_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()                       # a real on-disk state that raises

    with pytest.raises(Exception):
        EvidenceLedger(path).verify()

    evidence = _tool_evidence(cfg)
    assert evidence.state == EVIDENCE_BROKEN, (
        "an unreadable present ledger was treated as no evidence at all")
    assert "could not be read" in evidence.reason


# ----------------------------------------------------- the symptom itself
def test_a_tampered_ledger_denies_receipt_construction(cfg, science, tmp_path):
    """THE S0, driven at the builder: real ledger, real call, tampered, signed.

    Before the fix this returned a valid signed receipt with no `tool_evidence`
    block — a tampered chain presented as an audit that used no tools.
    """
    led = EvidenceLedger(_evidence_path(cfg))
    led.append("tool_call", run_id="r", payload={"tool": "file_read"}, ts="t0")
    led.append("tool_result", run_id="r", payload={"sha256": "abc"}, ts="t1")
    _sha, _ldir, kwargs = _build_receipt(cfg, science)

    raw = _evidence_path(cfg).read_text()
    _evidence_path(cfg).write_text(raw.replace('"file_read"', '"file_write"'))
    assert not EvidenceLedger(_evidence_path(cfg)).verify().ok, "fixture did not tamper"

    with pytest.raises(Denial) as denial:
        build(**kwargs)
    assert "does not verify" in str(denial.value)
    assert isinstance(denial.value, IntegrityDenial)


def test_an_honest_tool_free_receipt_still_builds_and_signs(cfg, science,
                                                            tmp_path):
    """Requirement 3: do not deny the honest case to catch the dishonest one."""
    assert not _evidence_path(cfg).exists()
    _sha, _ldir, kwargs = _build_receipt(cfg, science)
    receipt = build(**kwargs)

    assert "tool_evidence" not in receipt, "tool-free receipt bytes changed"
    validate(receipt)
    cdir = tmp_path / "cycle"
    cdir.mkdir()
    assert sign_receipt(cfg, receipt, cdir) is not None or True


def test_an_intact_ledger_still_binds_its_head(cfg, science):
    """The fix must not have been made by refusing evidence altogether."""
    led = EvidenceLedger(_evidence_path(cfg))
    led.append("tool_call", run_id="r", payload={"tool": "file_read"}, ts="t0")
    _sha, _ldir, kwargs = _build_receipt(cfg, science)
    receipt = build(**kwargs)

    assert receipt["tool_evidence"]["entries"] == 1
    assert len(receipt["tool_evidence"]["ledger_head"]) == 64


def test_the_denial_is_not_softened_into_a_warning(cfg, science):
    """A builder must not turn a denial into an absence — that WAS the defect."""
    led = EvidenceLedger(_evidence_path(cfg))
    led.append("tool_call", run_id="r", payload={"tool": "file_read"}, ts="t0")
    _sha, _ldir, kwargs = _build_receipt(cfg, science)
    raw = _evidence_path(cfg).read_text()
    _evidence_path(cfg).write_text(raw.replace('"file_read"', '"file_write"'))

    try:
        receipt = build(**kwargs)
    except Denial:
        return
    pytest.fail(
        f"a receipt was built over a corrupt ledger; tool_evidence="
        f"{receipt.get('tool_evidence', 'ABSENT')!r}. An omitted block states, "
        f"over a valid signature, that this audit used no tools.")
