"""Evidence ledger — the Phase 1 append-only, hash-chained record.

These pin the integrity contract the Agentic Runtime depends on: appends chain
and stay ordered; any tampered byte is caught on re-read; the same recorded
evidence re-derives byte-identical digests on any host (offline verifiability);
a crash mid-append is reported as an incomplete tail, not silently trusted; and
concurrent writers serialise instead of forking the chain.
"""
from __future__ import annotations

import json
import threading

import pytest

from crossaudit.errors import ConfigDenial
from crossaudit.ledger import EvidenceLedger


def _ledger(tmp_path):
    return EvidenceLedger(tmp_path / "evidence.jsonl")


def test_empty_ledger_verifies_and_has_no_head(tmp_path):
    led = _ledger(tmp_path)
    assert led.head() == ""
    r = led.verify()
    assert r.ok and r.count == 0 and r.head == ""


def test_append_chains_and_advances_head(tmp_path):
    led = _ledger(tmp_path)
    d0 = led.append("tool_call", run_id="r1", payload={"tool": "file_read"}, ts="t0")
    d1 = led.append("decision", run_id="r1", payload={"allow": True}, ts="t1")
    d2 = led.append("tool_result", run_id="r1", payload={"sha256": "abc"}, ts="t2")
    assert d0 != d1 != d2
    assert led.head() == d2
    rows = led.entries()
    assert [e["seq"] for e in rows] == [0, 1, 2]
    assert rows[0]["prev"] == "" and rows[1]["prev"] == d0 and rows[2]["prev"] == d1
    assert led.verify().ok and led.verify().count == 3


def test_genesis_entry_has_empty_prev_and_seq_zero(tmp_path):
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"x": 1}, ts="t")
    e = led.entries()[0]
    assert e["prev"] == "" and e["seq"] == 0


def test_tampered_payload_is_detected(tmp_path):
    led = _ledger(tmp_path)
    led.append("tool_call", run_id="r1", payload={"path": "work/a.md"}, ts="t0")
    led.append("tool_call", run_id="r1", payload={"path": "work/b.md"}, ts="t1")
    # Flip a byte inside the first entry's payload without touching its digest.
    text = led.path.read_text()
    assert "work/a.md" in text
    led.path.write_text(text.replace("work/a.md", "work/HACKED"))
    r = led.verify()
    assert not r.ok and r.at_seq == 0 and "tampered" in r.error


def test_broken_chain_is_detected(tmp_path):
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    # Drop the middle entry: entry 2's prev no longer links entry 0.
    lines = led.path.read_text().splitlines()
    led.path.write_text(lines[0] + "\n" + lines[2] + "\n")
    r = led.verify()
    assert not r.ok
    assert "chain" in r.error or "order" in r.error


def test_replay_parity_same_evidence_same_digests(tmp_path):
    a = EvidenceLedger(tmp_path / "a.jsonl")
    b = EvidenceLedger(tmp_path / "b.jsonl")
    events = [("tool_call", {"tool": "search", "q": "x"}, "t0"),
              ("decision", {"allow": True, "level": 1}, "t1"),
              ("tool_result", {"result_sha256": "deadbeef"}, "t2")]
    ha = [a.append(k, run_id="run-1", payload=p, ts=t) for k, p, t in events]
    hb = [b.append(k, run_id="run-1", payload=p, ts=t) for k, p, t in events]
    # Identical recorded evidence must re-derive identical digests on any host.
    assert ha == hb
    assert a.head() == b.head()


def test_incomplete_trailing_line_is_reported_not_trusted(tmp_path):
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    # Simulate a crash mid-append: a partial final line with no newline.
    with open(led.path, "a") as fh:
        fh.write('{"seq":1,"prev":"deadbeef","kind":"note"')  # truncated, no \n
    r = led.verify()
    assert not r.ok and r.incomplete_tail
    # The one complete entry before the tear still counts as head.
    assert r.count == 1
    # A fresh append still chains off the last *complete* entry, not the tear.
    good_head = led.head()
    assert good_head == led.entries()[0]["digest"]


def test_rejects_non_mapping_payload(tmp_path):
    led = _ledger(tmp_path)
    with pytest.raises(ConfigDenial):
        led.append("note", run_id="r", payload=["not", "a", "dict"], ts="t")


def test_concurrent_appends_never_fork_the_chain(tmp_path):
    led = _ledger(tmp_path)
    writers, per = 6, 20

    def work(w):
        for i in range(per):
            led.append("note", run_id=f"w{w}", payload={"w": w, "i": i}, ts=f"{w}-{i}")

    threads = [threading.Thread(target=work, args=(w,)) for w in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    r = led.verify()
    assert r.ok, r.error
    assert r.count == writers * per
    # Sequences are a contiguous 0..N-1 with no gaps or duplicates.
    seqs = sorted(e["seq"] for e in led.entries())
    assert seqs == list(range(writers * per))
