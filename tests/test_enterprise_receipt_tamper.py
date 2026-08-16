"""Adversarial: a receipt's tool_evidence is *bound* to the real evidence ledger.

Invariant under attack (receipt_tamper):
  * a receipt that binds the ledger head must refuse to verify() the instant the
    ledger is tampered underneath it (content flip, chain break, truncation);
  * a receipt whose own recorded ledger head / entry count is edited to any value
    that no longer names the genuine bound prefix must refuse to verify();
  * a tool-free cycle mints a plain v2 receipt with NO tool_evidence block, and
    that receipt still verifies — full back-compat, no schema bump.

These tests MIRROR tests/test_receipt_tool_evidence.py's build/verify shapes and
use only the real receipt.build / receipt.verify API and the conftest fixtures.
No component under test is mocked; nothing external is touched.
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
    """Run a real (offline) audit and mint its receipt, exactly as production
    does. When ``with_tools`` we first record three genuine, hash-chained
    evidence entries, so build() binds a real ledger head + count."""
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


def _ledger_file(cfg) -> Path:
    return cfg.root / cfg.state_dir / "evidence.jsonl"


def _verify(cfg, science, sha, receipt):
    return verify(receipt, science_root=science, audit_root=science,
                  expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


# --------------------------------------------------------------------------- #
# (c) back-compat: a tool-free receipt has no block and still verifies.
# --------------------------------------------------------------------------- #
def test_tool_free_receipt_has_no_block_and_still_verifies(cfg, science):
    sha, receipt = _mint(cfg, science, with_tools=False)
    # A cycle that ran no governed tools must be byte-identical to a plain v2:
    assert "tool_evidence" not in receipt
    validate(receipt)                       # structurally valid without the block
    ev = _verify(cfg, science, sha, receipt)
    assert ev["verified"] is True


# --------------------------------------------------------------------------- #
# Control: a genuine tool receipt DOES verify — so the tamper tests below prove
# the *defense* fires, not that verify() rejects everything.
# --------------------------------------------------------------------------- #
def test_genuine_tool_receipt_binds_head_and_verifies(cfg, science):
    sha, receipt = _mint(cfg, science, with_tools=True)
    te = receipt.get("tool_evidence")
    assert te is not None
    assert te["entries"] == 3 and len(te["ledger_head"]) == 64
    # Head bound in the receipt is exactly the last complete ledger digest.
    led = EvidenceLedger(_ledger_file(cfg))
    assert te["ledger_head"] == led.entries()[-1]["digest"]
    ev = _verify(cfg, science, sha, receipt)
    assert ev["verified"] is True


# --------------------------------------------------------------------------- #
# (a) tamper the LEDGER after binding -> receipt verify() must refuse.
# --------------------------------------------------------------------------- #
def test_ledger_content_tamper_breaks_receipt_verification(cfg, science):
    """Flip an entry's payload: the stored digest no longer re-derives, so the
    chain fails re-derivation and the bound receipt is refused."""
    sha, receipt = _mint(cfg, science, with_tools=True)
    lf = _ledger_file(cfg)
    lf.write_text(lf.read_text().replace('"file_read"', '"HACKED_TOOL"'))
    with pytest.raises(IntegrityDenial):
        _verify(cfg, science, sha, receipt)


def test_ledger_chain_break_breaks_receipt_verification(cfg, science):
    """Rewrite a genesis field so its digest is stale: the hash-chain no longer
    re-derives and verify() refuses before it can trust the bound head."""
    sha, receipt = _mint(cfg, science, with_tools=True)
    lf = _ledger_file(cfg)
    # Change the run_id of the first entry only; that entry's stored digest was
    # taken over the original body, so re-derivation now mismatches.
    lines = lf.read_text().splitlines()
    lines[0] = lines[0].replace('"run_id":"r"', '"run_id":"tampered"', 1)
    lf.write_text("\n".join(lines) + "\n")
    with pytest.raises(IntegrityDenial):
        _verify(cfg, science, sha, receipt)


def test_ledger_truncation_orphans_bound_head(cfg, science):
    """Drop the last ledger entry. The remaining chain re-derives cleanly, but
    the receipt bound entries==3, and only 2 rows now exist, so the bound head is
    an orphan -> refuse. (Truncation must never look like a valid prefix.)"""
    sha, receipt = _mint(cfg, science, with_tools=True)
    lf = _ledger_file(cfg)
    kept = [ln for ln in lf.read_text().splitlines() if ln.strip()][:-1]
    lf.write_text("\n".join(kept) + "\n")
    # Sanity: the truncated ledger is itself internally consistent (2 entries),
    # so the ONLY thing that fails is the receipt's head/count binding.
    assert EvidenceLedger(lf).verify().ok is True
    with pytest.raises(IntegrityDenial, match="does not match"):
        _verify(cfg, science, sha, receipt)


# --------------------------------------------------------------------------- #
# (b) tamper the RECEIPT's recorded head / count -> verify() must refuse.
# --------------------------------------------------------------------------- #
def test_receipt_head_forgery_is_refused(cfg, science):
    """Swap the recorded ledger_head for a well-formed but bogus 64-hex digest.
    The re-derived ledger's entry-3 digest will not equal it -> refuse."""
    sha, receipt = _mint(cfg, science, with_tools=True)
    real = receipt["tool_evidence"]["ledger_head"]
    forged = hashlib.sha256(b"attacker-chosen-head").hexdigest()
    assert forged != real and len(forged) == 64
    receipt["tool_evidence"]["ledger_head"] = forged
    with pytest.raises(IntegrityDenial, match="does not match"):
        _verify(cfg, science, sha, receipt)


def test_receipt_count_inflation_is_refused(cfg, science):
    """Claim more entries than the ledger holds. n > len(rows) -> refuse; an
    attacker cannot manufacture evidence rows that were never recorded."""
    sha, receipt = _mint(cfg, science, with_tools=True)
    receipt["tool_evidence"]["entries"] = 99
    with pytest.raises(IntegrityDenial, match="does not match"):
        _verify(cfg, science, sha, receipt)


def test_receipt_count_shrink_without_moving_head_is_refused(cfg, science):
    """Shrink the count but leave the head naming entry 3. head and count are
    JOINTLY bound: entry `count` must be the entry whose digest is `head`, so a
    count that no longer indexes the recorded head is refused. This proves you
    cannot silently drop trailing evidence rows by editing the count alone."""
    sha, receipt = _mint(cfg, science, with_tools=True)
    # keep the real (entry-3) head, but claim only 1 entry was recorded.
    receipt["tool_evidence"]["entries"] = 1
    with pytest.raises(IntegrityDenial, match="does not match"):
        _verify(cfg, science, sha, receipt)


def test_receipt_count_zero_is_refused(cfg, science):
    """A non-positive count is meaningless as a prefix length and must refuse
    (verify() guards n < 1 independently of schema validation)."""
    sha, receipt = _mint(cfg, science, with_tools=True)
    receipt["tool_evidence"]["entries"] = 0
    with pytest.raises(IntegrityDenial, match="does not match"):
        _verify(cfg, science, sha, receipt)
