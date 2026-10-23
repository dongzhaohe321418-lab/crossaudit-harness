"""Round 3 of the cross-vendor review of the ruling path (2026-10-23).

* Finding 1: a symlinked ``cycles/rulings.jsonl`` (or ``cycles/``) took the
  appended row outside the repository while ``git add`` committed only the
  link. Symlinks there are refused, the log is opened ``O_NOFOLLOW``, and the
  committed blob must end with the row before the state changes.
* Finding 2: breaking a stale controller lock could delete a fresh owner's
  lock. Stale locks are now refused, never broken; ``doctor --fix`` removes
  one only when its pid is not alive.
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
from crossaudit.controller import StateStore
from crossaudit.controller import state as state_mod
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
    outside = tmp_path / "outside-rulings.jsonl"
    outside.write_bytes(b"")
    (root / LOG).symlink_to(outside)
    head = git("rev-parse", "HEAD", cwd=root)
    assert _refused(cid) == SYMLINK_SENTENCE
    assert outside.read_bytes() == b""
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
    assert _refused(cid) == SYMLINK_SENTENCE
    assert not (real / "rulings.jsonl").exists()
    assert git("rev-parse", "HEAD", cwd=root) == head
    _assert_unruled(root, cid)


def test_a_clean_filter_that_strips_the_row_leaves_the_cycle_escalated(escalated):
    """The commit lands but carries an empty log: the filter removed the row.
    Mutation caught: dropping `_confirm_committed` -- the cycle closes on a
    commit that holds no ruling."""
    root, cid = escalated
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    (gitdir / "info").mkdir(exist_ok=True)
    (gitdir / "info" / "attributes").write_text(f"{LOG} filter=strip\n")
    git("config", "filter.strip.clean", "sed '$d'", cwd=root)
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


# ---------------------------------------------------------------- finding 2
def _write_lock(store: StateStore, pid: int, age: float) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.lock_path.write_text(f"{pid} {time.time() - age:.0f} deadbeefdeadbeef")
    past = time.time() - age
    os.utime(store.lock_path, (past, past))


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_a_stale_observation_never_deletes_a_fresh_owner_s_lock(tmp_path, monkeypatch):
    """The reviewer's interleaving, forced: A observes B's lock as stale; B
    releases; C acquires a fresh lock; A proceeds. Mutation caught: the old
    `unlink(); continue` on a stale observation -- A deletes C's lock and
    both write."""
    a = StateStore(tmp_path / "state.json")
    c = StateStore(tmp_path / "state.json")
    _write_lock(a, os.getpid(), state_mod.LOCK_STALE_S + 60)   # B, "stale"
    real = StateStore._lock_holder
    tokens: dict = {}

    def observe_then_interleave(lock_path):
        seen = real(lock_path)
        if "c" not in tokens:
            lock_path.unlink()                        # B releases
            tokens["c"] = c._acquire(lock_path)       # C acquires, fresh
        return seen                                   # A acts on the old reading
    monkeypatch.setattr(StateStore, "_lock_holder", staticmethod(observe_then_interleave))
    with pytest.raises(IntegrityDenial) as denied:
        a.open_or_advance("t/p", "c" * 40, None)
    assert "is not broken automatically" in denied.value.reason
    assert a.lock_path.read_text() == tokens["c"]     # C's lock is intact


def test_a_stale_lock_with_a_dead_pid_is_refused_then_removed_by_doctor_fix(
        escalated, monkeypatch, capsys):
    """Mutations caught: auto-breaking (the operation would succeed instead of
    refusing); a refusal that does not name `doctor --fix`; `doctor --fix`
    not removing a dead holder's lock."""
    root, cid = escalated
    store = StateStore(root / ".crossaudit" / "state.json")
    pid = _dead_pid()
    _write_lock(store, pid, state_mod.LOCK_STALE_S + 30)
    with pytest.raises(IntegrityDenial) as denied:
        store.escalate(cid, "again")
    assert denied.value.reason.startswith(
        f"the controller lock {store.lock_path} has been held by pid {pid} for ")
    assert denied.value.reason.endswith(
        "s stale limit, and is not broken automatically; if no crossaudit process "
        "is running for this project, `crossaudit doctor --fix` removes it")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input",
                        lambda prompt="": "y" if "controller lock" in prompt else "n")
    capsys.readouterr()
    main.main(["--json", "doctor", "--fix"])
    doc = json.loads(capsys.readouterr().out)
    row = next(c for c in doc["checks"] if c["check"] == "controller lock")
    assert row["ok"] is None and "removed the stale lock" in row["detail"]
    assert not store.lock_path.exists()
    store.escalate(cid, "works again")               # the store is usable


def test_doctor_reports_a_stale_lock_and_fix_refuses_a_live_pid(
        escalated, monkeypatch, capsys):
    """Mutation caught: `remove_stale_lock` (or doctor) removing a lock whose
    pid is alive -- a running process would lose its lock."""
    root, _cid = escalated
    store = StateStore(root / ".crossaudit" / "state.json")
    _write_lock(store, os.getpid(), state_mod.LOCK_STALE_S + 30)
    capsys.readouterr()
    main.main(["--json", "doctor"])                    # read-only
    doc = json.loads(capsys.readouterr().out)
    row = next(c for c in doc["checks"] if c["check"] == "controller lock")
    assert row["ok"] is False and f"pid {os.getpid()} (alive)" in row["detail"]
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    main.main(["--json", "doctor", "--fix"])
    doc = json.loads(capsys.readouterr().out)
    row = next(c for c in doc["checks"] if c["check"] == "controller lock")
    assert row["ok"] is False and "is alive, so --fix leaves it alone" in row["detail"]
    assert store.lock_path.exists()
    assert store.remove_stale_lock() == "alive"
    assert store.lock_path.exists()


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


# ------------------------------------------- the evidence ledger's lock, too
# The same policy applied to `ledger/chain.py`'s lock (audit core): it broke a
# lock older than 30 s by unlinking it, the identical race. No test relied on
# that breaking (none wrote or aged an `evidence.jsonl.lock`).
from crossaudit.ledger import chain as ledger_chain  # noqa: E402
from crossaudit.ledger.chain import EvidenceLedger, LedgerError  # noqa: E402


def _age_lock(lock_path: Path, pid: int, age: float) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(f"{pid} {time.time() - age:.0f} deadbeefdeadbeef")
    past = time.time() - age
    os.utime(lock_path, (past, past))


def _ledger_lock(ledger: EvidenceLedger) -> Path:
    return ledger.path.with_suffix(ledger.path.suffix + ".lock")


def test_a_stale_ledger_lock_is_refused_not_broken(tmp_path):
    """Mutation caught: the old `unlink(); continue` on a stale ledger lock --
    the append would succeed and the lock file (a dead writer's) vanish."""
    ledger = EvidenceLedger(tmp_path / "evidence.jsonl")
    ledger.append("note", run_id="r1", payload={"n": 1})
    before = ledger.path.read_bytes()
    pid = _dead_pid()
    _age_lock(_ledger_lock(ledger), pid, ledger_chain._LOCK_STALE_S + 30)
    with pytest.raises(LedgerError) as denied:
        ledger.append("note", run_id="r1", payload={"n": 2})
    assert denied.value.reason.startswith(
        f"the evidence ledger lock {_ledger_lock(ledger)} has been held by pid {pid} for ")
    assert denied.value.reason.endswith(
        "s stale limit, and is not broken automatically; if no crossaudit process "
        "is running for this project, `crossaudit doctor --fix` removes it")
    assert _ledger_lock(ledger).exists()
    assert ledger.path.read_bytes() == before


def test_a_stale_ledger_observation_never_deletes_a_fresh_writer_s_lock(
        tmp_path, monkeypatch):
    """The interleaving forced on the ledger lock: A observes the lock as
    stale, B releases, C acquires, A proceeds. Mutation caught: unlinking on
    the stale observation -- C's lock would be deleted under it."""
    ledger = EvidenceLedger(tmp_path / "evidence.jsonl")
    lock = _ledger_lock(ledger)
    _age_lock(lock, os.getpid(), ledger_chain._LOCK_STALE_S + 60)   # B
    real = ledger_chain.locks.holder
    held: dict = {}

    def observe_then_interleave(path):
        seen = real(path)
        if "c" not in held:
            path.unlink()                                  # B releases
            held["c"] = ledger_chain._FileLock(path).__enter__()   # C, fresh
        return seen
    monkeypatch.setattr(ledger_chain.locks, "holder", observe_then_interleave)
    with pytest.raises(LedgerError):
        ledger.append("note", run_id="r1", payload={"n": 1})
    assert lock.read_text() == held["c"].token            # C's lock is intact
    held["c"].__exit__(None, None, None)
    assert not lock.exists()                               # released by C


def _doctor_rows(capsys, *argv) -> dict:
    capsys.readouterr()
    main.main(["--json", "doctor", *argv])
    doc = json.loads(capsys.readouterr().out)
    return {c["check"]: c for c in doc["checks"]}


def test_doctor_reports_both_stale_locks(escalated, capsys):
    """Mutation caught: doctor checking only the controller lock -- the
    ledger's stale lock goes unreported."""
    root, _cid = escalated
    store = StateStore(root / ".crossaudit" / "state.json")
    _age_lock(store.lock_path, os.getpid(), state_mod.LOCK_STALE_S + 30)
    ledger_lock = root / ".crossaudit" / "evidence.jsonl.lock"
    _age_lock(ledger_lock, os.getpid(), ledger_chain._LOCK_STALE_S + 30)
    rows = _doctor_rows(capsys)
    assert rows["controller lock"]["ok"] is False
    assert rows["evidence ledger lock"]["ok"] is False
    assert str(ledger_lock) in rows["evidence ledger lock"]["detail"]
    assert "(alive)" in rows["evidence ledger lock"]["detail"]


def test_doctor_fix_removes_a_dead_ledger_lock_and_refuses_a_live_one(
        escalated, monkeypatch, capsys):
    """Mutation caught: the ledger's `remove_stale_lock` ignoring liveness
    (the live writer's lock would be removed), or doctor --fix not removing
    a dead writer's lock."""
    root, _cid = escalated
    ledger_lock = root / ".crossaudit" / "evidence.jsonl.lock"
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input",
                        lambda prompt="": "y" if "lock" in prompt else "n")
    _age_lock(ledger_lock, os.getpid(), ledger_chain._LOCK_STALE_S + 30)
    row = _doctor_rows(capsys, "--fix")["evidence ledger lock"]
    assert row["ok"] is False and "is alive, so --fix leaves it alone" in row["detail"]
    assert ledger_lock.exists()
    ledger = root / ".crossaudit" / "evidence.jsonl"
    assert ledger_chain.remove_stale_lock(ledger) == "alive"   # the shared path itself
    assert ledger_lock.exists()
    _age_lock(ledger_lock, _dead_pid(), ledger_chain._LOCK_STALE_S + 30)
    row = _doctor_rows(capsys, "--fix")["evidence ledger lock"]
    assert row["ok"] is None and "removed the stale lock" in row["detail"]
    assert not ledger_lock.exists()
    EvidenceLedger(root / ".crossaudit" / "evidence.jsonl").append(
        "note", run_id="r1", payload={"usable": True})
