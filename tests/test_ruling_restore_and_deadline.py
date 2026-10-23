"""A failed ruling restores the log's exact bytes, and the whole commit fits the lock.

Review 2026-10-23 round 2:

* Finding 1: the restore after a failed commit truncated the log to its old
  length, so a rejecting hook that rewrote the log (same-length garbage,
  binary) left it changed while the refusal said "nothing was recorded". The
  exact prior bytes are now kept and put back atomically; a restore that
  cannot be done says so in a different sentence.
* Finding 2: the commit bound applied to each git step, so a slow clean
  filter plus a slow hook held the controller lock past its stale threshold;
  another process could then break the lock, and the old holder wrote its
  stale snapshot over the newer state and unlinked the newer lock. There is
  now one deadline for the transaction, and the lock is ownership-aware.

Time is scaled: the budget and the stale threshold are monkeypatched to a few
seconds, and hooks and filters sleep. Each test names the mutation it catches.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import main
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.controller import state as state_mod
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import git

from .test_resolve_commits_the_ruling import (REASON, assert_nothing_was_ruled,  # noqa: F401
                                              escalated, install_hook)

LOG = "cycles/rulings.jsonl"


def _store(root: Path) -> StateStore:
    return StateStore(root / ".crossaudit" / "state.json")


def _with_a_committed_log(root: Path, cid: str) -> bytes:
    """reopen (committed), then the cycle stops again: the log exists and is
    tracked, and the cycle is ESCALATED for the ruling under test."""
    main.resolve_cycle(load(), cid, "reopen", "try once more")
    _store(root).escalate(cid, "build round budget spent (3)", kind="audit")
    return (root / LOG).read_bytes()


def _assert_restored(root: Path, cid: str, prior: bytes, head: str) -> None:
    assert (root / LOG).read_bytes() == prior
    assert git("status", "--porcelain", "--", LOG, cwd=root) == ""
    assert git("diff", "--cached", "--name-only", cwd=root) == ""
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert [r["action"] for r in rulings.history(load())] == ["reopen"]
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert [h["action"] for h in state["history"]
            if h.get("event") == "human_resolution"] == ["reopen"]


def _refused(cid: str) -> str:
    with pytest.raises(IntegrityDenial) as denied:
        main.resolve_cycle(load(), cid, "close", REASON)
    return denied.value.reason


# ---------------------------------------------------------------- finding 1
def test_a_hook_that_overwrites_the_log_with_same_length_binary_is_undone(escalated):
    """Mutation caught: restoring by truncating to the old length -- the
    0xFF bytes the hook wrote survive, `git status` shows `M`, and
    `history()` raises UnicodeDecodeError."""
    root, cid = escalated
    prior = _with_a_committed_log(root, cid)
    install_hook(root, (
        "#!/bin/sh\n"
        f"n=$(wc -c < {LOG})\n"
        f"head -c \"$n\" /dev/zero | tr '\\000' '\\377' > {LOG}\n"
        "echo 'pre-commit: refused' >&2\nexit 1\n"))
    head = git("rev-parse", "HEAD", cwd=root)
    reason = _refused(cid)
    assert reason.endswith("the cycle stays ESCALATED and nothing was recorded")
    _assert_restored(root, cid, prior, head)


def test_a_hook_that_deletes_the_log_before_rejecting_is_undone(escalated):
    """Mutation caught: a restore that only truncates an existing file (or
    skips a missing one) -- the log stays deleted."""
    root, cid = escalated
    prior = _with_a_committed_log(root, cid)
    install_hook(root, f"#!/bin/sh\nrm -f {LOG}\nexit 1\n")
    head = git("rev-parse", "HEAD", cwd=root)
    _refused(cid)
    _assert_restored(root, cid, prior, head)


def test_a_hook_that_appends_to_the_log_before_rejecting_is_undone(escalated):
    """Mutation caught: no restore at all -- the ruling's line and the
    hook's both stay. (The old truncating restore passes this one; the two
    tests above are the ones it fails.)"""
    root, cid = escalated
    prior = _with_a_committed_log(root, cid)
    install_hook(root, f"#!/bin/sh\nprintf 'tampered\\n' >> {LOG}\nexit 1\n")
    head = git("rev-parse", "HEAD", cwd=root)
    _refused(cid)
    _assert_restored(root, cid, prior, head)


def test_a_restore_that_fails_says_so_and_claims_nothing(escalated, monkeypatch):
    """Mutation caught: swallowing the restore's OSError and raising the
    "nothing was recorded" sentence over a log that was not put back."""
    root, cid = escalated
    _with_a_committed_log(root, cid)
    install_hook(root, "#!/bin/sh\necho 'pre-commit: refused' >&2\nexit 1\n")
    head = git("rev-parse", "HEAD", cwd=root)

    def refuse(_src, _dst):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(rulings.os, "replace", refuse)
    reason = _refused(cid)
    monkeypatch.undo()
    assert reason == (
        f"the ruling on cycle {cid} could not be committed to the ledger "
        f"(pre-commit: refused), and {LOG} could not be restored (No space left "
        f"on device); the cycle stays ESCALATED, but check {LOG} against git "
        f"before ruling again")
    assert "nothing was recorded" not in reason
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert [h["action"] for h in state["history"]
            if h.get("event") == "human_resolution"] == ["reopen"]
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert git("diff", "--cached", "--name-only", cwd=root) == ""
    assert not list((root / "cycles").glob(".rulings.jsonl.restore-*"))


# ---------------------------------------------------------------- finding 2
def test_the_commit_budget_and_its_cleanup_stay_inside_the_lock(escalated):
    """Mutation caught: raising COMMIT_TIMEOUT_S or CLEANUP_TIMEOUT_S (or
    lowering LOCK_STALE_S) until a ruling could outlive the controller lock.
    The 10 s margin covers the state reads and writes around the commit."""
    worst = rulings.COMMIT_TIMEOUT_S + 2 * rulings.CLEANUP_TIMEOUT_S
    assert worst + 10 < state_mod.LOCK_STALE_S


def test_a_slow_filter_plus_a_slow_hook_share_one_deadline(escalated, monkeypatch):
    """`git add` delayed 1.5 s by a clean filter, `git commit` delayed 1.5 s
    by a hook, budget 2 s: each step fits on its own, the two together do
    not. Mutation caught: the bound applied per step (the old behaviour) --
    the ruling lands after 3 s and no denial is raised."""
    root, cid = escalated
    monkeypatch.setattr(rulings, "COMMIT_TIMEOUT_S", 2.0)
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    (gitdir / "info").mkdir(exist_ok=True)
    (gitdir / "info" / "attributes").write_text(f"{LOG} filter=slow\n")
    git("config", "filter.slow.clean", "sleep 1.5; cat", cwd=root)
    install_hook(root, "#!/bin/sh\nsleep 1.5\nexit 0\n")
    head = git("rev-parse", "HEAD", cwd=root)
    began = time.monotonic()
    reason = _refused(cid)
    assert time.monotonic() - began < 2.0 + 1.5
    assert reason == (
        f"the ruling on cycle {cid} could not be committed to the ledger "
        f"(git commit timed out after 2s); the cycle stays ESCALATED and "
        f"nothing was recorded")
    git("config", "--unset", "filter.slow.clean", cwd=root)
    assert_nothing_was_ruled(root, cid, None, head)


def test_a_holder_that_overran_never_writes_over_the_lock_s_new_owner(
        escalated, monkeypatch):
    """The stale threshold scaled to 1 s and the budget to 6 s, so the ruling
    deliberately outlives the lock: while its hook sleeps, a second holder
    breaks the "stale" lock, records a new escalation and takes the lock
    again. The first holder's commit then lands, and it must neither write
    its old snapshot (which would erase the new escalation) nor unlink the
    second holder's lock.

    Mutation caught: `_locked` writing back and unlinking without checking
    its owner token -- the concurrent escalation is lost and the second
    holder's lock vanishes under it."""
    root, cid = escalated
    monkeypatch.setattr(state_mod, "LOCK_STALE_S", 1.0)
    monkeypatch.setattr(rulings, "COMMIT_TIMEOUT_S", 6.0)
    store = _store(root)
    other = store.open_or_advance("t/p", "a" * 40, None)["cycle_id"]
    marker = root.parent / "hook-started"
    install_hook(root, f"#!/bin/sh\ntouch '{marker}'\nsleep 2.5\nexit 0\n")
    first_done = threading.Event()
    seen: dict = {}

    def second_holder():
        rival = _store(root)
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        time.sleep(1.2)                       # the first holder's lock is now "stale"
        rival.escalate(other, "a concurrent escalation", kind="audit")
        held = rival._locked()
        held.__enter__()
        seen["token"] = rival.lock_path.read_text()
        first_done.wait(20)
        seen["lock_while_held"] = (rival.lock_path.read_text()
                                   if rival.lock_path.exists() else None)
        held.__exit__(None, None, None)

    thread = threading.Thread(target=second_holder)
    thread.start()
    try:
        reason = _refused(cid)
    finally:
        first_done.set()
        thread.join(30)
    assert reason.startswith(f"the ruling on cycle {cid} was committed to the ledger (")
    assert reason.endswith("taken over before the cycle's state could change, so "
                           "the cycle stays ESCALATED; rule on it again")
    assert seen["lock_while_held"] == seen["token"]     # not unlinked by the first
    assert not store.lock_path.exists()                 # released by its owner
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][other]["status"] == "ESCALATED"
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert not any(h.get("event") == "human_resolution" and h.get("cycle") == cid
                   for h in state["history"])
    # Honest about what did happen: the commit is in the ledger.
    assert [r["cycle_id"] for r in rulings.history(load())] == [cid]


def test_a_holder_whose_lock_was_taken_says_so_in_its_own_words(tmp_path, monkeypatch):
    """The store-level sentence, without git: a `_locked` body that outlives
    the scaled stale threshold while another store takes the lock. Mutation
    caught: the same as above, at the store, with no ruling in between."""
    monkeypatch.setattr(state_mod, "LOCK_STALE_S", 0.3)
    store = StateStore(tmp_path / "state.json")
    cycle = store.open_or_advance("t/p", "b" * 40, None)
    rival = StateStore(tmp_path / "state.json")
    with pytest.raises(IntegrityDenial) as denied:
        with store._locked() as state:
            state["cycles"][cycle["cycle_id"]]["status"] = "BLOCKED"
            time.sleep(0.5)
            rival.escalate(cycle["cycle_id"], "taken meanwhile")
    assert denied.value.reason == (
        "the controller lock was taken over by another process while this one "
        "held it (longer than the 0.3s stale limit); this process's state change "
        "was discarded")
    assert store.cycle(cycle["cycle_id"])["status"] == "ESCALATED"
