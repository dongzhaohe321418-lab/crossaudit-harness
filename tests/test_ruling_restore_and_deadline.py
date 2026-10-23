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
  (The takeover tests that lived here were replaced in round 4, when the
  controller lock became kernel-held: a live holder's lock can no longer be
  removed or taken, so "a holder that overran" cannot arise. Their
  successors are in ``test_kernel_held_locks.py``; the budget-versus-stale
  pin went with ``LOCK_STALE_S``.)

Time is scaled: the budget and the stale threshold are monkeypatched to a few
seconds, and hooks and filters sleep. Each test names the mutation it catches.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import main
from crossaudit.config import load
from crossaudit.controller import StateStore
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
    # The killed `git commit` held .git/index.lock; since round 4 it is never
    # deleted (it names no owner), so the refusal says so and the recovery
    # it describes is done here by hand.
    assert reason == (
        f"the ruling on cycle {cid} could not be committed to the ledger "
        f"(git commit timed out after 2s); the cycle stays ESCALATED and "
        f"nothing was recorded; .git/index.lock may have been left by the killed "
        f"git — if no git process is running, remove it by hand and run "
        f"`git reset -q -- {LOG}`")
    assert (gitdir / "index.lock").exists()
    (gitdir / "index.lock").unlink()
    git("config", "--unset", "filter.slow.clean", cwd=root)
    git("reset", "-q", "--", LOG, cwd=root)
    assert_nothing_was_ruled(root, cid, None, head)
