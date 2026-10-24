"""Round 3 of the cross-vendor review of the ruling path (2026-10-23).

* Finding 1: a symlinked ``cycles/rulings.jsonl`` (or ``cycles/``) took the
  appended row outside the repository while ``git add`` committed only the
  link. Symlinks there are refused, the log is opened ``O_NOFOLLOW``, and the
  committed blob must end with the row before the state changes.
* Finding 2: breaking a stale controller lock could delete a fresh owner's
  lock. (Its tests moved to ``test_kernel_held_locks.py`` when round 4
  replaced the lock file with a kernel-held lock; the stale-refusal and
  ``doctor --fix`` tests were deleted with the behaviour they tested.)
* Finding 3: a hook's detached child holding git's output kept the ruling
  waiting after the group kill; output now goes to files and only the
  process's exit is awaited.

Each test names the mutation it catches.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import main
from crossaudit.config import load
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import git

from .test_resolve_commits_the_ruling import REASON, escalated, install_hook  # noqa: F401

LOG = "cycles/rulings.jsonl"


def _state(root: Path) -> dict:
    return json.loads((root / ".crossaudit" / "state.json").read_text())


def _assert_unruled(root: Path, cid: str) -> None:
    state = _state(root)
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert not any(h.get("event") == "human_resolution" for h in state["history"])


def _refused(cid: str) -> str:
    with pytest.raises(IntegrityDenial) as denied:
        main.resolve_cycle(load(), cid, "close", REASON)
    return denied.value.reason


SYMLINK_SENTENCE = (f"{LOG} (or its directory) is a symbolic link; the rulings log "
                    "must be a regular file inside the repository, so the ruling "
                    "was not recorded")


# ---------------------------------------------------------------- finding 1
def test_a_symlinked_log_file_is_refused_and_nothing_leaves_the_repository(
        escalated, tmp_path):
    """Mutation caught: dropping both the lstat walk and O_NOFOLLOW -- the
    row goes to the outside target, the commit holds only the link's target
    pathname, and the cycle closes."""
    root, cid = escalated
    # Since D176 ruling 43 the log already holds the escalation's row, so its
    # bytes move outside and the log becomes a link to them.
    outside = tmp_path / "outside-rulings.jsonl"
    before = (root / LOG).read_bytes()
    outside.write_bytes(before)
    (root / LOG).unlink()
    (root / LOG).symlink_to(outside)
    head = git("rev-parse", "HEAD", cwd=root)
    assert _refused(cid) == SYMLINK_SENTENCE
    assert outside.read_bytes() == before
    assert (root / LOG).is_symlink()
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert git("diff", "--cached", "--name-only", cwd=root) == ""
    _assert_unruled(root, cid)


def test_a_symlinked_ledger_directory_is_refused(escalated, tmp_path):
    """`O_NOFOLLOW` guards only the last component. Mutation caught: dropping
    the lstat walk over `cycles/` -- the row is written into the directory
    outside the repository."""
    root, cid = escalated
    real = tmp_path / "outside-cycles"
    (root / "cycles").rename(real)
    (root / "cycles").symlink_to(real, target_is_directory=True)
    head = git("rev-parse", "HEAD", cwd=root)
    before = (real / "rulings.jsonl").read_bytes()      # the escalation's row
    assert _refused(cid) == SYMLINK_SENTENCE
    assert (real / "rulings.jsonl").read_bytes() == before
    assert git("rev-parse", "HEAD", cwd=root) == head
    _assert_unruled(root, cid)


def test_a_clean_filter_that_strips_the_row_leaves_the_cycle_escalated(escalated):
    """The commit lands but carries something else: the filter replaced the
    row. (Since D176 ruling 43 the log already holds the escalation's row, so
    a filter that only deleted the last line would leave nothing to commit;
    this one rewrites it.) Mutation caught: dropping `_confirm_committed` --
    the cycle closes on a commit that holds no ruling."""
    root, cid = escalated
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    (gitdir / "info").mkdir(exist_ok=True)
    (gitdir / "info" / "attributes").write_text(f"{LOG} filter=strip\n")
    git("config", "filter.strip.clean", "sed '$s/.*/{\"replaced\": true}/'", cwd=root)
    head = git("rev-parse", "HEAD", cwd=root)
    reason = _refused(cid)
    landed = git("rev-parse", "HEAD", cwd=root)
    assert landed != head                         # the commit is not undone
    assert reason == (
        f"the ruling on cycle {cid} was committed as {landed[:12]}, but the "
        f"committed {LOG} could not be confirmed to contain it (a filter or hook "
        f"changed the file); the cycle stays ESCALATED — check the repository's "
        f"filters and hooks before ruling again")
    committed = subprocess.run(["git", "cat-file", "blob", f"HEAD:{LOG}"], cwd=root,
                               capture_output=True, check=True).stdout
    assert (root / LOG).read_bytes() == committed  # no line git does not have
    assert REASON.encode() not in committed
    _assert_unruled(root, cid)


# ---------------------------------------------------------------- finding 3
@pytest.mark.skipif(os.name == "nt", reason="os.setsid is POSIX")
def test_a_detached_hook_child_holding_git_s_output_does_not_hold_the_ruling(
        escalated, monkeypatch, tmp_path):
    """A hook starts a setsid child that keeps git's stdout/stderr and then
    sleeps past the budget. Mutation caught: reading git's output through
    pipes to end-of-file after the kill (the old `communicate()`) -- the
    ruling waits ~10 s for the detached child."""
    root, cid = escalated
    monkeypatch.setattr(rulings, "COMMIT_TIMEOUT_S", 0.5)
    monkeypatch.setattr(rulings, "CLEANUP_TIMEOUT_S", 1.0)
    pidfile = tmp_path / "detached.pid"
    child = (f"{sys.executable} -c 'import os,sys,time; os.setsid(); "
             f"open(sys.argv[1],\"w\").write(str(os.getpid())); time.sleep(10)' "
             f"'{pidfile}' >&2 &")
    install_hook(root, f"#!/bin/sh\n{child}\nsleep 10\n")
    head = git("rev-parse", "HEAD", cwd=root)
    began = time.monotonic()
    try:
        reason = _refused(cid)
        elapsed = time.monotonic() - began
    finally:
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if pidfile.exists() and pidfile.read_text().strip().isdigit():
            try:
                os.kill(int(pidfile.read_text()), 9)
            except OSError:
                pass
    assert elapsed < 0.5 + 1.0 + 1.5, elapsed
    assert "(git commit timed out after 0.5s)" in reason
    assert git("rev-parse", "HEAD", cwd=root) == head
    _assert_unruled(root, cid)
