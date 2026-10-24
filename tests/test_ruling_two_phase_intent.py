"""A ruling is two-phase, joined by a local intent (review 2026-10-23 round 9;
D176 rulings 30 and 31).

Round 9 found ruling 27's reconciliation unsafe: it read the committed log
before the controller lock (two resolvers could commit opposite rulings),
read failures were "nothing pending", and any syntactically valid committed
row carrying the cycle's escalation time was applied. Now the intent (with a
random nonce) is written to the local state store under the lock, the row
carries the nonce, and recovery applies only a committed row with the nonce
of this controller's intent. Each test names the mutation it catches.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n, main
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_OK, IntegrityDenial
from crossaudit.gitio import git

from .test_resolve_commits_the_ruling import REASON, escalated  # noqa: F401

LOG = "cycles/rulings.jsonl"


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _store(root: Path) -> StateStore:
    return StateStore(root / ".crossaudit" / "state.json")


def _state(root: Path) -> dict:
    return json.loads((root / ".crossaudit" / "state.json").read_text())


def _rows(root: Path) -> list[dict]:
    path = root / LOG
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().split("\n") if line]
    return [r for r in rows if r.get("kind") != "escalation"]   # escalation rows are not rulings (D176 ruling 43)


def _fail_phase3_write(monkeypatch, *, thread: str | None = None):
    """The state write after the commit (phase 3) fails once with ENOSPC; with
    ``thread``, only in that thread."""
    real = StateStore._write
    calls = {"n": 0}

    def failing(self, state):
        if thread is None or threading.current_thread().name == thread:
            calls["n"] += 1
            if calls["n"] == 2:                    # 1 = intent, 2 = state change
                try:
                    raise OSError(28, "No space left on device")
                except OSError as exc:
                    raise self._unwritable(exc) from exc
        return real(self, state)
    monkeypatch.setattr(StateStore, "_write", failing)


def _commit_count(root: Path, since: str) -> int:
    return int(git("rev-list", "--count", f"{since}..HEAD", cwd=root))


# ---------------------------------------------------------- the race
@pytest.mark.parametrize("order", ["b_first", "concurrent"])
def test_two_resolvers_make_exactly_one_commit(escalated, monkeypatch, order):
    """The reviewer's race: B rules `close` and its state write after the
    commit fails; A rules `reopen`. Exactly one commit in total, and the final
    state reflects it, whichever order the lock gives. Mutation caught:
    recovery without the local intent (A sees no pending ruling and commits a
    second, opposite row)."""
    root, cid = escalated
    head = git("rev-parse", "HEAD", cwd=root)
    _fail_phase3_write(monkeypatch, thread="B")
    cfg = load()
    outcome: dict = {}
    barrier = threading.Barrier(2)

    def resolver(name, action, wait_for=None):
        if wait_for is not None:
            wait_for.join()
        elif order == "concurrent":
            barrier.wait(5)
        try:
            outcome[name] = rulings.rule(cfg, _store(root), cid, action, f"{name} rules")
        except IntegrityDenial as exc:
            outcome[name] = exc.reason

    b = threading.Thread(target=resolver, args=("B", "close"), name="B")
    a = threading.Thread(target=resolver, args=("A", "reopen", b if order == "b_first" else None),
                         name="A")
    b.start()
    a.start()
    a.join(60)
    b.join(60)
    assert _commit_count(root, head) == 1
    rows = _rows(root)
    assert len(rows) == 1
    state = _state(root)
    assert state["cycles"][cid]["status"] == rows[0]["status_after"]
    assert cid not in state.get("pending_rulings", {})


# ---------------------------------------------------------- a failed read
def test_an_unreadable_committed_log_refuses_and_keeps_the_intent(
        escalated, monkeypatch):
    """After a post-commit failure, a one-shot `git cat-file` failure on the
    next ruling. Mutation caught: reading the committed log fail-open (an
    unreadable log as "no rows") -- the intent is cleared and a second ruling
    is committed."""
    root, cid = escalated
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    nonce = _state(root)["pending_rulings"][cid]["nonce"]
    head = git("rev-parse", "HEAD", cwd=root)
    real = rulings._bounded_bytes
    calls = {"n": 0}

    def once_broken(cfg_, args, deadline):
        if args[:2] == ("cat-file", "blob") and calls["n"] == 0:
            calls["n"] += 1
            return 128, b"", "fatal: bad object HEAD:cycles/rulings.jsonl\n"
        return real(cfg_, args, deadline)
    monkeypatch.setattr(rulings, "_bounded_bytes", once_broken)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", "again")
    assert denied.value.reason == (
        "the committed rulings log could not be read (fatal: bad object "
        "HEAD:cycles/rulings.jsonl); no ruling is made until it can be")
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert _state(root)["pending_rulings"][cid]["nonce"] == nonce
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    result = rulings.rule(cfg, _store(root), cid, "close", "and again")
    assert result["reconciled"] is True
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


# ---------------------------------------------------------- a forged row
def test_a_committed_row_this_controller_did_not_make_is_never_applied(
        escalated, monkeypatch, capsys):
    """A hand-written row (1970 timestamp, the cycle's own escalated_at,
    a made-up intent) committed to the audit repository. Mutation caught:
    applying a committed row without this controller's intent nonce (ruling
    27's escalated_at match) -- the cycle would close on the forged row."""
    root, cid = escalated
    cycle = _state(root)["cycles"][cid]
    forged = {"cycle_id": cid, "action": "close", "reason": "forged", "by": "x",
              "t": 0, "at": "1970-01-01T00:00:00Z", "round": cycle["round"],
              "active_sha": cycle["active_sha"], "status_after": "BLOCKED",
              "escalation_reason": "", "escalated_at": cycle.get("escalated_at"),
              "intent": "f" * 32}
    (root / "cycles").mkdir(exist_ok=True)
    with open(root / LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n")
    git("add", "--", LOG, cwd=root)
    git("commit", "-q", "-m", "an unrelated commit", "--", LOG, cwd=root)
    sha = git("rev-parse", "HEAD", cwd=root)
    # status lists it, read-only.
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    row = next(r for r in json.loads(capsys.readouterr().out)["cycles"]
               if r["cycle_id"] == cid)
    # Since D176 ruling 41 an unsigned row is listed as unverified.
    assert row["unverified_rulings"] == [{"action": "close",
                                          "at": "1970-01-01T00:00:00Z",
                                          "commit": sha[:12]}]
    assert main.main(["status"]) == EXIT_OK
    assert f"unverified ruling row ({sha[:12]})" in capsys.readouterr().out
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    # The explicit human ruling proceeds; the ledger then holds both rows.
    result = rulings.rule(load(), _store(root), cid, "reopen", "the genuine ruling")
    assert "reconciled" not in result
    assert _commit_count(root, sha) == 1
    assert [r["reason"] for r in _rows(root)] == ["forged", "the genuine ruling"]
    assert _state(root)["cycles"][cid]["status"] == "OPEN"


# ---------------------------------------------------------- an intent with no commit
def test_an_intent_left_with_no_commit_is_cleared_and_the_ruling_proceeds(
        escalated, monkeypatch, capsys):
    """The process stopped between the intent and the commit (the intent is
    on disk, no row carries its nonce). Mutation caught: treating such an
    intent as an error or as a ruling to apply -- the cycle could never be
    ruled on, or would follow a ruling nobody committed."""
    root, cid = escalated
    store = _store(root)
    with store._locked() as state:
        state.setdefault("pending_rulings", {})[cid] = {
            "action": "reopen", "nonce": "a" * 32, "reason_sha256": "", "by": "",
            "started_at": 0}
    head = git("rev-parse", "HEAD", cwd=root)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    capsys.readouterr()
    assert main.main(["resolve", cid, "--close", "--because", REASON]) == EXIT_OK
    out = capsys.readouterr().out
    assert ("an earlier attempt to rule on this cycle left no commit; its intent was "
            "cleared and this ruling was recorded as a fresh one") in out
    assert _commit_count(root, head) == 1
    state = _state(root)
    assert cid not in state.get("pending_rulings", {})
    assert state["cycles"][cid]["status"] == "BLOCKED"


def test_a_commit_that_fails_clears_its_intent(escalated, monkeypatch):
    """`record()` refuses with a commit that definitely did not land
    (`commit_landed="no"`): nothing is committed, the intent is removed, and
    the next ruling makes exactly one commit. Since D176 ruling 33 only such
    a refusal clears the intent; one without that mark (the commit may have
    landed) keeps it, which this test also checks. Mutations caught: leaving
    the intent behind after a refused commit (the next ruling would report an
    earlier attempt that never happened); clearing it on an uncertain
    outcome. (It also checked the nonce in `ruling_intents`, which D176
    ruling 43 retired.)"""
    root, cid = escalated
    head = git("rev-parse", "HEAD", cwd=root)
    real = rulings.record

    def refuses(*a, **k):
        raise IntegrityDenial("a test refusal", commit_landed="no")
    monkeypatch.setattr(rulings, "record", refuses)
    with pytest.raises(IntegrityDenial):
        rulings.rule(load(), _store(root), cid, "close", REASON)
    assert cid not in _state(root).get("pending_rulings", {})

    def uncertain(*a, **k):
        raise IntegrityDenial("a test refusal, outcome unknown")
    monkeypatch.setattr(rulings, "record", uncertain)
    with pytest.raises(IntegrityDenial):
        rulings.rule(load(), _store(root), cid, "close", REASON)
    assert cid in _state(root).get("pending_rulings", {})
    monkeypatch.setattr(rulings, "record", real)
    assert git("rev-parse", "HEAD", cwd=root) == head
    result = rulings.rule(load(), _store(root), cid, "close", REASON)
    assert result.get("intent_cleared") is True        # the uncertain one had no row
    assert _commit_count(root, head) == 1
    # The row is signed and names the current escalation (D176 ruling 43;
    # `ruling_intents` is no longer kept).
    assert rulings.row_verifies(_rows(root)[-1], rulings._project_pubkey(load()))


# ---------------------------------------------------------- the post-commit failure
@pytest.mark.parametrize("second", ["close", "reopen"])
def test_a_post_commit_failure_keeps_the_intent_and_recovers_from_it(
        escalated, monkeypatch, second):
    """The intent stays on disk with the committed row's nonce; the next
    ruling applies the committed one (same action: reconciled; the other:
    applied, then the request refused). Mutation caught: dropping the intent
    from the recovery (no intent read: the cycle stays ESCALATED and a second
    row is committed)."""
    root, cid = escalated
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    assert f"was committed to the ledger as {sha[:12]}" in denied.value.reason
    intent = _state(root)["pending_rulings"][cid]
    assert _rows(root)[-1]["intent"] == intent["nonce"]
    if second == "close":
        result = rulings.rule(cfg, _store(root), cid, "close", "again")
        assert result["reconciled"] is True and result["ruling"]["commit"] == sha
    else:
        with pytest.raises(IntegrityDenial) as refused:
            rulings.rule(cfg, _store(root), cid, "reopen", "the other way")
        assert refused.value.reason == (f"a committed ruling (close, {sha[:12]}) "
                                        f"already stands for cycle {cid}; the state "
                                        f"now reflects it")
    assert git("rev-parse", "HEAD", cwd=root) == sha
    state = _state(root)
    assert state["cycles"][cid]["status"] == "BLOCKED"
    assert cid not in state.get("pending_rulings", {})


def test_a_legacy_cycle_without_escalated_at_takes_the_same_path(
        escalated, monkeypatch):
    """A cycle escalated before `escalated_at` existed. Mutation caught: any
    remaining timestamp heuristic deciding recovery (ruling 27's
    `updated_at` fallback would not recognise a same-second ruling)."""
    root, cid = escalated
    store = _store(root)
    with store._locked() as state:
        state["cycles"][cid].pop("escalated_at", None)
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    result = rulings.rule(cfg, _store(root), cid, "close", "again")
    assert result["reconciled"] is True
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


def test_record_refuses_a_nonce_that_is_not_the_current_intent(escalated):
    """Mutation caught: `record()` writing a row for any nonce -- a caller
    could mint a row the controller would later treat as its own."""
    root, cid = escalated
    head = git("rev-parse", "HEAD", cwd=root)
    store = _store(root)
    cycle = dict(store.cycle(cid), cycle_id=cid)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.record(load(), cycle, "close", REASON, intent="0" * 32, store=store)
    assert denied.value.reason == (
        f"the ruling on cycle {cid} does not match the intent this controller "
        f"recorded for it; nothing was recorded")
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert _rows(root) == []
