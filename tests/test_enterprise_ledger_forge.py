"""Adversarial: forge / replay / tamper the evidence ledger's raw JSONL.

INVARIANT under attack: the evidence ledger is append-only + hash-chained, so
verify() re-derives the whole chain from disk and refuses on the FIRST
inconsistency — a flipped byte, a replayed line, a rewritten ``prev``, a
reordering, a deleted middle, or a hand-crafted self-consistent entry spliced in
with the wrong ``prev``. These tests actually mutate the on-disk file and assert
verify() catches it at the right seq. They also confirm the authority is verify()
itself: the P10 size-guarded head cache can never launder a tampered tail past it.

Every mutation here would make verify() return ok=True if the corresponding
defense (content digest / chain link / seq order) were removed, so none of these
tests is vacuous.
"""
from __future__ import annotations

import json

from crossaudit.ledger import EvidenceLedger
from crossaudit.ledger.chain import LEDGER_SCHEMA
from crossaudit.receipt.schema import digest


def _ledger(tmp_path):
    return EvidenceLedger(tmp_path / "evidence.jsonl")


def _lines(led):
    return led.path.read_text().splitlines()


def _write_lines(led, lines):
    led.path.write_text("\n".join(lines) + "\n")


def _forge_line(*, seq, prev, kind="note", run_id="attacker", ts="t", payload):
    """Build a line byte-identical in shape to what EvidenceLedger.append writes,
    but with attacker-chosen seq/prev. Its ``digest`` is a *correct* hash of its
    own body — the entry is internally self-consistent; only its chain position
    is a lie."""
    body = {
        "ledger_schema": LEDGER_SCHEMA,
        "seq": seq,
        "prev": prev,
        "kind": kind,
        "run_id": run_id,
        "ts": ts,
        "payload": payload,
    }
    entry_digest = digest(body)
    return json.dumps({**body, "digest": entry_digest}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


def _seed(led, n):
    """Append n honest entries with fixed ts (deterministic digests)."""
    return [led.append("note", run_id="r", payload={"i": i}, ts=f"t{i}")
            for i in range(n)]


# -- (a) flip a byte in a payload -> content/digest error at the right seq -----
def test_flip_byte_in_middle_payload_is_caught_at_that_seq(tmp_path):
    led = _ledger(tmp_path)
    led.append("tool_call", run_id="r", payload={"path": "work/UNIQUE_A.md"}, ts="t0")
    led.append("tool_call", run_id="r", payload={"path": "work/UNIQUE_B.md"}, ts="t1")
    led.append("tool_call", run_id="r", payload={"path": "work/UNIQUE_C.md"}, ts="t2")
    assert led.verify().ok  # honest chain verifies before we tamper

    # Flip a byte inside entry seq 1's payload; leave its stored digest alone.
    text = led.path.read_text()
    assert text.count("UNIQUE_B") == 1
    led.path.write_text(text.replace("work/UNIQUE_B.md", "work/UNIQUE_X.md"))

    r = led.verify()
    assert r.ok is False
    assert r.at_seq == 1
    assert "tampered" in r.error  # digest(body) != stored digest


# -- (b) duplicate / replay a line -> chain/seq check fails --------------------
def test_replayed_duplicate_line_is_rejected(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 3)
    assert led.verify().ok

    # Replay: append the last complete line again, verbatim.
    lines = _lines(led)
    _write_lines(led, lines + [lines[-1]])

    r = led.verify()
    assert r.ok is False
    # The replayed entry's prev links seq1, but the chain is already at seq2's
    # digest, and its seq (2) is not the next expected (3): a replay cannot pass.
    assert r.at_seq == 3
    assert "chain" in r.error or "order" in r.error


def test_replaying_the_whole_file_is_rejected(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 4)
    lines = _lines(led)
    # Concatenate a second full copy of the chain after the first.
    _write_lines(led, lines + lines)
    r = led.verify()
    assert r.ok is False
    # First replayed line sits where seq 4 should be; its prev/seq both lie.
    assert r.at_seq == 4
    assert "chain" in r.error or "order" in r.error


# -- (c) rewrite an entry's "prev" to forge a different history ----------------
def test_rewriting_prev_breaks_the_content_digest(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 3)
    lines = _lines(led)

    # Rewrite ONLY entry seq 1's prev (to a fake genesis link), leaving its
    # stored digest untouched. prev lives inside the hashed body, so you cannot
    # rewrite history without also invalidating the digest — that is the point.
    obj1 = json.loads(lines[1])
    assert obj1["seq"] == 1
    obj1["prev"] = "0" * 64
    lines[1] = json.dumps(obj1, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    _write_lines(led, lines)

    r = led.verify()
    assert r.ok is False
    assert r.at_seq == 1
    assert "tampered" in r.error


# -- (d) reorder two lines -> chain/order check fails --------------------------
def test_reordering_two_lines_is_caught(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 3)
    lines = _lines(led)

    # Swap the seq-1 and seq-2 lines. On-disk order is now 0, 2, 1.
    lines[1], lines[2] = lines[2], lines[1]
    _write_lines(led, lines)

    r = led.verify()
    assert r.ok is False
    # At position 1 we now meet seq 2, whose prev links seq1's digest, not
    # seq0's — the reorder is caught immediately.
    assert r.at_seq == 1
    assert "chain" in r.error or "order" in r.error


# -- (e) delete a middle line -> chain check fails -----------------------------
def test_deleting_a_middle_line_is_caught(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 5)
    lines = _lines(led)

    del lines[2]  # drop seq 2
    _write_lines(led, lines)

    r = led.verify()
    assert r.ok is False
    # After seq1, the next line is seq3 whose prev links seq2 (now gone).
    assert r.at_seq == 2
    assert "chain" in r.error or "order" in r.error


# -- (f) hand-crafted entry: correct-looking digest, WRONG prev -> rejected ----
def test_self_consistent_entry_with_wrong_prev_is_rejected(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 2)
    true_head = led.head()

    # A forged tail whose digest correctly hashes its OWN body (content check
    # would pass) and whose seq is the next expected (order check would pass),
    # but whose prev does not link the real head.
    forged = _forge_line(seq=2, prev="f" * 64, payload={"x": "forged"})
    with open(led.path, "a") as fh:
        fh.write(forged + "\n")

    r = led.verify()
    assert r.ok is False
    assert r.at_seq == 2
    assert "chain" in r.error  # content & seq are fine; only the link is a lie
    assert true_head != "f" * 64


def test_forge_control_correct_prev_is_accepted(tmp_path):
    """Positive control: the SAME hand-crafting machinery, given the REAL prev,
    produces an entry verify() accepts. This proves the rejection above is due
    specifically to the wrong prev, not a malformed body — i.e. the digest in
    the forge really is 'correct-looking'."""
    led = _ledger(tmp_path)
    _seed(led, 2)
    head = led.head()

    good = _forge_line(seq=2, prev=head, payload={"x": "forged"})
    with open(led.path, "a") as fh:
        fh.write(good + "\n")

    r = led.verify()
    assert r.ok is True
    assert r.count == 3
    # verify()'s re-derived head equals the spliced entry's stored digest.
    assert r.head == json.loads(good)["digest"]


# -- head() / P10 size-guarded cache never accept a tampered tail --------------
def test_truncating_the_tail_invalidates_the_warm_cache(tmp_path):
    led = _ledger(tmp_path)
    digests = _seed(led, 5)              # warms the cache: (seq4, d4, size)
    assert led.head() == digests[4]

    # Attacker removes the last entry. The file size changes, so the size-guard
    # MUST miss the cache and re-derive the true head instead of vouching for
    # the deleted tail's digest.
    _write_lines(led, _lines(led)[:-1])
    assert led.head() == digests[3]
    assert led.head() != digests[4]

    r = led.verify()
    assert r.ok is True and r.count == 4


def test_verify_ignores_warm_cache_and_catches_same_size_tail_tamper(tmp_path):
    led = _ledger(tmp_path)
    led.append("note", run_id="r", payload={"i": 0}, ts="t0")
    led.append("note", run_id="r", payload={"i": 1}, ts="t1")
    led.append("note", run_id="r", payload={"path": "work/TAILZZZZ.md"}, ts="t2")
    # Cache is warm here: _cached_size == current file size, head == seq2 digest.
    warm_head = led.head()

    # In-place edit of the TAIL entry's payload, byte-for-byte same length, so
    # the file size is unchanged and the size-guarded cache still "matches".
    text = led.path.read_text()
    before = len(text)
    tampered = text.replace("work/TAILZZZZ.md", "work/TAILWWWW.md")
    assert len(tampered) == before  # size identical -> cache guard not tripped
    led.path.write_text(tampered)

    # verify() never consults the cache; it re-reads disk and catches the tail.
    r = led.verify()
    assert r.ok is False
    assert r.at_seq == 2
    assert "tampered" in r.error
    # And head() (cache warm, size unchanged) still reports the entry's stored
    # digest — it never fabricates or forwards the attacker's altered body.
    assert led.head() == warm_head


def test_fresh_cold_instance_also_catches_a_tampered_tail(tmp_path):
    led = _ledger(tmp_path)
    _seed(led, 3)
    # Tamper the tail's payload (changes its digest relationship).
    text = led.path.read_text()
    led.path.write_text(text.replace('"i":2', '"i":9'))

    # A brand-new instance (cold cache) is the offline-verifier case: it must
    # re-derive from disk and refuse, never trust the tail.
    fresh = EvidenceLedger(tmp_path / "evidence.jsonl")
    r = fresh.verify()
    assert r.ok is False
    assert r.at_seq == 2
    assert "tampered" in r.error
