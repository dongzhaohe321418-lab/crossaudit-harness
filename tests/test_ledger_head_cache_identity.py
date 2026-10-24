"""The ledger's head cache is keyed on (st_size, st_mtime_ns, st_ino).

The defect (review terra-r1, finding 4): ``_verified_head_locked`` trusted its
cached head whenever the file was the size this instance last left it, and the
docstring said "correctness never depends on the cache". Another process that
rewrote the ledger in place at the same size (one character of the last
entry's digest flipped) was appended onto without re-verification: the new
entry chained onto the cached, genuine digest and extended the forged file.

Now a change in any one of size, ``st_mtime_ns`` or inode forces the
authoritative scan, which refuses a ledger that does not verify. The blind
spot that remains (same size, ``st_mtime_ns`` restored exactly, same inode)
is pinned below as such, together with the ``verify()`` that catches it.

D10 mutation run by hand: the cache key back to ``st_size`` alone (``_stamp_of``
returning ``(st.st_size, 0, 0)``) -> the in-place-rewrite and the
replaced-inode tests go red (the append succeeds onto the forged file); the
fast-path and blind-spot tests stay green, as they should. Second mutation:
the cache hit in ``_verified_head_locked`` disabled (always verify) -> the
fast-path test goes red, and so does the blind-spot test, which pins the
fast path's documented behaviour (a stricter ledger would refuse that append
too; if that is ever chosen, that test changes with the docstring).
"""
from __future__ import annotations

import json
import os

import pytest

from crossaudit.ledger import EvidenceLedger
from crossaudit.ledger import chain
from crossaudit.ledger.chain import LedgerError


def _ledger(tmp_path):
    return EvidenceLedger(tmp_path / "evidence.jsonl")


def _forged_bytes(path) -> bytes:
    """The file with one hex character of the LAST entry's digest flipped:
    same length, different bytes, and a ledger that no longer verifies."""
    data = path.read_bytes()
    last = data.rstrip(b"\n").rsplit(b"\n", 1)[-1]
    start = len(data.rstrip(b"\n")) - len(last)
    digest = json.loads(last)["digest"]
    at = start + last.index(digest.encode())
    old = data[at:at + 1]
    new = b"0" if old != b"0" else b"1"
    forged = data[:at] + new + data[at + 1:]
    assert len(forged) == len(data) and forged != data
    return forged


def _seed(led):
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    assert led.verify().ok


def test_same_size_in_place_rewrite_is_not_appended_onto(tmp_path):
    led = _ledger(tmp_path)
    _seed(led)                                   # cache warm on this instance
    before = os.stat(led.path)
    forged = _forged_bytes(led.path)
    with open(led.path, "r+b") as fh:            # in place: same inode
        fh.write(forged)
    # A distinct mtime set explicitly, so the test does not depend on the
    # filesystem's clock resolution to make the rewrite visible.
    os.utime(led.path, ns=(before.st_atime_ns, before.st_mtime_ns + 7_000_000_000))
    after = os.stat(led.path)
    assert after.st_size == before.st_size and after.st_ino == before.st_ino

    with pytest.raises(LedgerError, match="does not verify"):
        led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    assert led.path.read_bytes() == forged, "the forged file was extended"


def test_same_size_same_mtime_file_replaced_by_rename_is_not_appended_onto(tmp_path):
    led = _ledger(tmp_path)
    _seed(led)
    before = os.stat(led.path)
    forged = _forged_bytes(led.path)
    spare = tmp_path / "forged.jsonl"
    spare.write_bytes(forged)
    os.utime(spare, ns=(before.st_atime_ns, before.st_mtime_ns))
    os.replace(spare, led.path)                  # only the inode differs
    after = os.stat(led.path)
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert after.st_ino != before.st_ino

    with pytest.raises(LedgerError, match="does not verify"):
        led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    assert led.path.read_bytes() == forged


def test_documented_blind_spot_is_caught_by_the_next_verify(tmp_path):
    """Same size, ``st_mtime_ns`` restored exactly, same inode: the fast path
    cannot see it (the docstring says so) and the append goes through; the
    next ``verify()``, which never consults the cache, reports the rewrite."""
    led = _ledger(tmp_path)
    _seed(led)
    before = os.stat(led.path)
    forged = _forged_bytes(led.path)
    with open(led.path, "r+b") as fh:
        fh.write(forged)
    os.utime(led.path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = os.stat(led.path)
    assert chain._stamp_of(after) == chain._stamp_of(before)

    led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    report = led.verify()
    assert report.ok is False
    assert report.at_seq == 1


def test_append_after_append_uses_the_fast_path(tmp_path, monkeypatch):
    _seed(_ledger(tmp_path))
    led = _ledger(tmp_path)                      # cold instance over a real file
    calls = []
    real_verify = EvidenceLedger.verify

    def counting_verify(self):
        calls.append(1)
        return real_verify(self)

    monkeypatch.setattr(EvidenceLedger, "verify", counting_verify)
    led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    assert len(calls) == 1, "a cold instance must verify before its first append"
    led.append("note", run_id="r", payload={"i": 3}, ts="t3")
    led.append("note", run_id="r", payload={"i": 4}, ts="t4")
    assert len(calls) == 1, "an append after this instance's own append re-scanned"
    monkeypatch.setattr(EvidenceLedger, "verify", real_verify)
    report = led.verify()
    assert report.ok and report.count == 5
