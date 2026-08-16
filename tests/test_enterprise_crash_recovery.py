"""Crash-recovery invariant: a crash mid-write is recoverable, never silently trusted.

The Agentic Runtime durability story has two halves, both exercised here against
the *real* code paths (no mocks):

* The Evidence Ledger uses the trailing newline as its durability signal. A
  crash mid-append leaves an unterminated final line; even when that torn line
  happens to be *valid JSON minus the newline*, the ledger must refuse to trust
  it — ``verify()`` reports an ``incomplete_tail`` at the torn ``seq`` and
  ``head()`` reports the last *complete* entry, never the tear. A fresh
  ``EvidenceLedger`` is constructed on the torn file so the P10 size-guarded
  head cache is cold and cannot smuggle the tear in from a warm process.

* The Level-2 write primitives are reversible and atomic: ``RecoveryStore``
  snapshots pre-write state so a write can be rolled back (prior content
  restored, or a newly-created file deleted), and ``atomic_write`` renames a
  temp file into place so a normal write never leaves a ``.tmp`` partial behind.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from crossaudit.broker.recovery import RecoveryStore, atomic_write
from crossaudit.ledger import EvidenceLedger
from crossaudit.ledger.chain import LedgerError


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _ledger(tmp_path: Path) -> EvidenceLedger:
    return EvidenceLedger(tmp_path / "evidence.jsonl")


def _strip_one_trailing_newline(path: Path) -> None:
    """Simulate a crash mid-append that dropped only the terminating newline.

    This is the adversarial case: the last line is *still complete, valid JSON* —
    only the ``\\n`` is missing — so a naive reader that parses line-by-line would
    happily trust a byte sequence that was never durably committed.
    """
    raw = path.read_bytes()
    assert raw.endswith(b"\n"), "precondition: a healthy ledger ends in a newline"
    path.write_bytes(raw[:-1])
    assert not path.read_bytes().endswith(b"\n")


# --------------------------------------------------------------------------- #
# (a) torn tail: reported as incomplete, never silently trusted
# --------------------------------------------------------------------------- #
def test_torn_tail_verify_reports_incomplete_tail_at_right_seq(tmp_path):
    led = _ledger(tmp_path)
    d0 = led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    d1 = led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    d2 = led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    assert led.head() == d2  # healthy: head is the last (seq 2) entry

    _strip_one_trailing_newline(led.path)

    # Fresh instance => COLD P10 cache: verify must re-derive from disk and
    # cannot inherit a warm cache that pointed at the (now torn) seq 2.
    fresh = EvidenceLedger(led.path)
    r = fresh.verify()
    assert r.ok is False
    assert r.incomplete_tail is True
    assert r.at_seq == 2                 # the torn entry's seq, exactly
    assert r.count == 2                  # the two entries before the tear stay intact
    assert r.head == d1                  # head reported is the last COMPLETE entry
    assert r.head != d2                  # never the torn tail
    assert "incomplete" in r.error


def test_torn_tail_head_is_last_complete_not_the_tear(tmp_path):
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    d1 = led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    d2 = led.append("note", run_id="r", payload={"i": 2}, ts="t2")

    _strip_one_trailing_newline(led.path)

    # A fresh instance (cold P10 cache) must re-derive the head from disk and
    # honour the newline durability signal: the last COMPLETE entry is seq 1,
    # never the torn seq 2 whose bytes are (deceptively) still valid JSON.
    fresh = EvidenceLedger(led.path)
    assert fresh.head() == d1
    assert fresh.head() != d2


def test_append_after_crash_tear_is_refused_fail_closed(tmp_path):
    """The realistic recovery path: crash, restart, try to append again.

    A crash tore the newline off the last entry. ``head()``/``verify()`` already
    refuse to trust the tear; appending is ALSO fail-closed — extending a damaged
    chain would glue new bytes onto the partial line (``O_APPEND`` does not
    repair the missing newline), so the ledger refuses until the tear is
    recovered. The two durably-committed entries remain readable, and the torn
    tail was never trusted or extended.
    """
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    d1 = led.append("note", run_id="r", payload={"i": 1}, ts="t1")

    # Add a seq 2 whose newline is then torn off (the deceptive "valid JSON
    # minus the newline" case), simulating a crash after its content bytes but
    # before its terminating newline was durable.
    led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    _strip_one_trailing_newline(led.path)

    fresh = EvidenceLedger(led.path)
    assert fresh.head() == d1                       # head ignores the tear
    with pytest.raises(LedgerError):                # append is fail-closed
        fresh.append("note", run_id="r", payload={"i": 3}, ts="t3")
    # Nothing was glued on; the durable entries survive and the tear stays flagged.
    assert [e["seq"] for e in fresh.entries()] == [0, 1]
    r = fresh.verify()
    assert r.ok is False and r.incomplete_tail is True and r.at_seq == 2


def test_torn_first_entry_leaves_nothing_trusted(tmp_path):
    """A crash during the very first append (before its newline) trusts nothing."""
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    _strip_one_trailing_newline(led.path)

    fresh = EvidenceLedger(led.path)
    r = fresh.verify()
    assert r.ok is False and r.incomplete_tail is True
    assert r.at_seq == 0 and r.count == 0
    assert fresh.head() == ""            # no complete entry => no trusted head


def test_torn_tail_not_included_in_entries(tmp_path):
    """entries() must agree with head()/verify() and omit a torn crash-tail, so
    a tear can never leak into the Auditor's evidence view (fixed in P11)."""
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    led.append("note", run_id="r", payload={"i": 2}, ts="t2")

    _strip_one_trailing_newline(led.path)

    fresh = EvidenceLedger(led.path)
    seqs = [e["seq"] for e in fresh.entries()]
    # entries() omits the torn tail (seq 2), matching head()/verify().
    assert seqs == [0, 1]


# --------------------------------------------------------------------------- #
# (b) an empty / zero-byte ledger is a clean, verifiable state
# --------------------------------------------------------------------------- #
def test_empty_nonexistent_ledger_verifies_ok_count_zero(tmp_path):
    led = _ledger(tmp_path)
    assert not led.path.exists()
    r = led.verify()
    assert r.ok is True and r.count == 0 and r.head == ""
    assert led.head() == ""


def test_zero_byte_ledger_verifies_ok_and_is_usable(tmp_path):
    led = _ledger(tmp_path)
    # A crash after file creation but before any bytes were written: 0-byte file.
    led.path.parent.mkdir(parents=True, exist_ok=True)
    led.path.write_bytes(b"")
    assert led.path.exists() and led.path.stat().st_size == 0

    fresh = EvidenceLedger(led.path)
    r = fresh.verify()
    assert r.ok is True and r.count == 0 and r.head == ""
    assert fresh.head() == ""
    # ...and it recovers into a usable ledger: a genesis append still chains.
    d0 = fresh.append("note", run_id="r", payload={"i": 0}, ts="t0")
    assert fresh.head() == d0
    r2 = fresh.verify()
    assert r2.ok is True and r2.count == 1
    assert fresh.entries()[0]["seq"] == 0 and fresh.entries()[0]["prev"] == ""


# --------------------------------------------------------------------------- #
# (c) RecoveryStore: snapshot -> write -> restore round-trips
# --------------------------------------------------------------------------- #
def test_recovery_restores_prior_content_after_crash_write(cfg):
    (cfg.root / "work").mkdir(parents=True, exist_ok=True)
    target = cfg.root / "work" / "a.md"
    target.write_text("original")

    rec = RecoveryStore(cfg)
    record = rec.snapshot("work/a.md")
    assert record["existed"] is True and record["pre_sha256"]

    # Simulate a governed write that must be rolled back (e.g. a crash/abort
    # left the file holding half-written, wrong content).
    atomic_write(target, b"corrupted-half-write")
    assert target.read_bytes() == b"corrupted-half-write"

    rec.restore(record)
    assert target.read_text() == "original"   # pre-write state restored exactly


def test_recovery_deletes_file_the_write_created(cfg):
    rec = RecoveryStore(cfg)
    record = rec.snapshot("work/created.md")           # does not exist yet
    assert record["existed"] is False and record["pre_sha256"] == ""

    atomic_write(cfg.root / "work" / "created.md", b"new content")
    assert (cfg.root / "work" / "created.md").is_file()

    rec.restore(record)                                # undo => delete the new file
    assert not (cfg.root / "work" / "created.md").exists()


# --------------------------------------------------------------------------- #
# (d) atomic_write never leaves a .tmp partial after a normal write
# --------------------------------------------------------------------------- #
def test_atomic_write_leaves_no_tmp_partial(cfg):
    target = cfg.root / "work" / "d.md"
    atomic_write(target, b"hello world")

    assert target.read_bytes() == b"hello world"
    tmp = target.with_name(target.name + f".tmp{os.getpid()}")
    assert not tmp.exists()
    # Nothing matching the temp pattern lingers in the directory.
    assert list(target.parent.glob("*.tmp*")) == []


def test_atomic_write_overwrite_is_clean_and_complete(cfg):
    target = cfg.root / "work" / "over.md"
    atomic_write(target, b"first-version")
    atomic_write(target, b"second-version-longer")

    # The overwrite fully replaces the old content (no mix, no partial) and,
    # being a rename-into-place, leaves no temp file behind.
    assert target.read_bytes() == b"second-version-longer"
    assert list(target.parent.glob("*.tmp*")) == []
