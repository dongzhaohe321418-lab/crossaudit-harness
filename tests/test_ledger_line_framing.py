"""Evidence-ledger line framing: an entry ends at "\\n" and nowhere else.

The defect: the writer emitted ``json.dumps(..., ensure_ascii=False) + "\\n"``
and the reader split with ``str.splitlines()``, which also splits on U+2028,
U+2029 and U+0085 -- three characters ``ensure_ascii=False`` leaves raw. One of
them in a payload (PDF text carries U+2028 routinely) made ``verify()`` report
"unparseable entry" forever, and because the head was taken from the last line
that parsed, the next two appends both got the same ``seq`` and ``prev``: a
forked chain, after which every receipt's tool evidence was refused.

Every parameterised test sweeps all three characters (AGENTS.md section 3.5):
a fix for one of them says nothing about the other two.

D10 mutations (each run by hand when this was written):
* reader back to ``text.splitlines()`` -- the old-ledger recovery tests go red
  (an old line holding the raw character is split in two and is unparseable);
* writer without the ``translate(_LINE_SEPARATOR_ESCAPES)`` -- the
  old-reader-compatibility test goes red (the raw character is on disk);
* append back to the unverified ``_head_locked()`` -- the corrupted-line and
  broken-chain refusal tests go red (the append succeeds and forks).
"""
from __future__ import annotations

import json

import pytest

from crossaudit.ledger import EvidenceLedger
from crossaudit.ledger.chain import LedgerError
from crossaudit.receipt.schema import digest

SEPARATORS = [" ", " ", "\u0085"]
IDS = ["U+2028", "U+2029", "U+0085"]


def _ledger(tmp_path):
    return EvidenceLedger(tmp_path / "evidence.jsonl")


def _old_writer_line(body: dict) -> bytes:
    """A line exactly as the pre-fix writer produced it: raw separators."""
    return (json.dumps({**body, "digest": digest(body)}, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False)
            + "\n").encode("utf-8")


def _body(seq: int, prev: str, payload: dict) -> dict:
    return {"ledger_schema": 1, "seq": seq, "prev": prev, "kind": "note",
            "run_id": "r", "ts": f"t{seq}", "payload": payload}


@pytest.mark.parametrize("sep", SEPARATORS, ids=IDS)
def test_a_separator_in_a_payload_verifies_and_the_next_append_chains(tmp_path, sep):
    led = _ledger(tmp_path)
    d0 = led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    payload = {"text": f"pdf text{sep}next line", f"key{sep}": sep}
    d1 = led.append("note", run_id="r", payload=payload, ts="t1")
    report = led.verify()
    assert report.ok and report.count == 2 and report.head == d1, report

    # A cold instance (no head cache) re-derives the head and chains onto d1.
    fresh = EvidenceLedger(led.path)
    d2 = fresh.append("note", run_id="r", payload={"i": 2}, ts="t2")
    rows = fresh.entries()
    assert [e["seq"] for e in rows] == [0, 1, 2]              # no repeated seq
    assert [e["prev"] for e in rows] == ["", d0, d1]          # no fork
    assert rows[1]["payload"] == payload                      # the character survives
    report = fresh.verify()
    assert report.ok and report.count == 3 and report.head == d2, report

    # And the warm instance chains onto the cold one's write too.
    d3 = led.append("note", run_id="r", payload={"i": 3}, ts="t3")
    assert [e["prev"] for e in led.entries()][-1] == d2
    assert led.verify().ok and led.verify().head == d3


@pytest.mark.parametrize("sep", SEPARATORS, ids=IDS)
def test_the_writer_escapes_the_separator_so_an_old_reader_can_read_it(tmp_path, sep):
    """New ledgers stay readable by the pre-fix reader (``splitlines``): the
    separator is written as its JSON escape, which decodes to the same
    character, so the digest -- taken over ``canonical(body)``, not the line --
    is the one the old writer would have produced."""
    led = _ledger(tmp_path)
    payload = {"text": f"a{sep}b"}
    stored = led.append("note", run_id="r", payload=payload, ts="t0")
    raw = led.path.read_bytes()
    assert sep.encode("utf-8") not in raw
    escape = "\\u%04x" % ord(sep)
    assert escape.encode("ascii") in raw
    old_reader = raw.decode("utf-8").splitlines()
    assert len(old_reader) == 1 and json.loads(old_reader[0])["payload"] == payload
    assert stored == digest(_body(0, "", payload))


def test_a_payload_without_the_three_separators_is_byte_identical(tmp_path):
    """In-bound input: the line is exactly what the old writer produced,
    non-ASCII included (raw UTF-8, not escaped)."""
    led = _ledger(tmp_path)
    payload = {"text": "中文 · ü · ‧ ‪ tab\tnl\n"}
    led.append("note", run_id="r", payload=payload, ts="t0")
    assert led.path.read_bytes() == _old_writer_line(_body(0, "", payload))


@pytest.mark.parametrize("sep", SEPARATORS, ids=IDS)
def test_an_old_ledger_holding_the_raw_separator_now_verifies(tmp_path, sep):
    """Recovery: a ledger the pre-fix writer left with a raw separator on disk
    verifies under the new reader, and appending onto it chains."""
    path = tmp_path / "evidence.jsonl"
    b0 = _body(0, "", {"i": 0})
    b1 = _body(1, digest(b0), {"text": f"old{sep}line"})
    path.write_bytes(_old_writer_line(b0) + _old_writer_line(b1))
    assert sep.encode("utf-8") in path.read_bytes()

    led = EvidenceLedger(path)
    report = led.verify()
    assert report.ok and report.count == 2 and report.head == digest(b1), report
    d2 = led.append("note", run_id="r", payload={"i": 2}, ts="t2")
    rows = led.entries()
    assert [e["seq"] for e in rows] == [0, 1, 2]
    assert rows[2]["prev"] == digest(b1)
    assert led.verify().ok and led.verify().head == d2


@pytest.mark.parametrize("corrupt", ["{not json", '["a", "list"]', "\x00\x01"],
                         ids=["unparseable", "not-an-object", "binary"])
def test_append_refuses_a_complete_line_that_does_not_parse(tmp_path, corrupt):
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    lines = led.path.read_bytes().split(b"\n")
    led.path.write_bytes(lines[0] + b"\n" + corrupt.encode() + b"\n")
    before = led.path.read_bytes()

    for writer in (led, EvidenceLedger(led.path)):          # warm and cold
        with pytest.raises(LedgerError) as caught:
            writer.append("note", run_id="r", payload={"i": 2}, ts="t2")
        assert "unparseable entry at line 2" in caught.value.reason
        assert "refusing to append" in caught.value.reason
    assert led.path.read_bytes() == before                  # nothing was written
    report = led.verify()
    assert not report.ok and report.error == "unparseable entry at line 2"


def test_append_refuses_a_complete_line_that_does_not_chain(tmp_path):
    led = _ledger(tmp_path)
    for i in range(3):
        led.append("note", run_id="r", payload={"i": i}, ts=f"t{i}")
    lines = led.path.read_bytes().split(b"\n")
    led.path.write_bytes(lines[0] + b"\n" + lines[2] + b"\n")   # drop the middle
    with pytest.raises(LedgerError) as caught:
        EvidenceLedger(led.path).append("note", run_id="r", payload={"i": 3})
    assert "broke the chain" in caught.value.reason
    assert caught.value.detail["at_seq"] == 1


def test_a_crlf_line_is_not_silently_accepted(tmp_path):
    """The writer never emits "\\r"; a CRLF-converted ledger is not one it
    wrote, and the reader does not treat "\\r\\n" as equivalent."""
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    led.path.write_bytes(led.path.read_bytes().replace(b"\n", b"\r\n"))
    report = EvidenceLedger(led.path).verify()
    assert not report.ok and report.error == "unparseable entry at line 1"
    with pytest.raises(LedgerError):
        EvidenceLedger(led.path).append("note", run_id="r", payload={"i": 1})


def test_the_torn_tail_refusal_is_unchanged(tmp_path):
    """The pre-existing refusal still fires first, with its own sentence."""
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    with open(led.path, "ab") as fh:
        fh.write(b'{"seq":1')
    with pytest.raises(LedgerError, match="incomplete final entry"):
        EvidenceLedger(led.path).append("note", run_id="r", payload={"i": 1})
