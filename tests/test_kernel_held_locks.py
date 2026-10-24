"""The controller lock and the evidence-ledger lock are kernel-held (review
2026-10-23 round 4).

Round 4 found that every pathname scheme -- judge ownership from the lock
file, then unlink it -- lets another process release and a third create a
fresh lock that is then deleted. Both locks are now ``flock`` on an open file
(``crossaudit.locks``): release is closing it, a dead holder releases with
its process, and no code path unlinks a lock file. These tests replace the
round-2/3 takeover, stale-refusal and ``doctor --fix`` tests, which tested
behaviour that no longer exists. Each test names the mutation it catches.
"""
from __future__ import annotations

import ast
import errno
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from crossaudit import locks, rulings
from crossaudit.cli import main
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.controller import state as state_mod
from crossaudit.errors import ConfigDenial, IntegrityDenial
from crossaudit.gitio import git
from crossaudit.ledger import chain as ledger_chain
from crossaudit.ledger.chain import EvidenceLedger

from .test_resolve_commits_the_ruling import REASON, escalated, install_hook  # noqa: F401

SRC = Path(__file__).resolve().parents[1] / "src"
pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX; see locks.py")


def _holder(code: str) -> subprocess.Popen:
    """A child process that takes a lock, prints `held`, and sleeps."""
    env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.Popen([sys.executable, "-c", code], env=env,
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def _kill(proc: subprocess.Popen) -> None:
    proc.send_signal(signal.SIGKILL)
    proc.wait(10)


# ------------------------------------------------------- a dead holder
def test_a_killed_controller_holder_releases_its_lock_at_once(tmp_path, monkeypatch):
    """Mutation caught: any lock that outlives its holder (the old O_EXCL
    file) -- the next acquisition waits out the timeout and is refused."""
    path = tmp_path / "state.json"
    proc = _holder(
        "import time; from crossaudit.controller import StateStore\n"
        f"s = StateStore({str(path)!r}); h = s._acquire(s.lock_path)\n"
        "print('held', flush=True); time.sleep(60)")
    store = StateStore(path)
    assert store.lock_status()["pid"] == proc.pid
    _kill(proc)
    monkeypatch.setattr(state_mod, "LOCK_TIMEOUT_S", 0.5)
    began = time.monotonic()
    store.open_or_advance("t/p", "a" * 40, None)
    assert time.monotonic() - began < 0.5
    assert store.lock_status() is None
    assert store.lock_path.exists()          # the file persists, inert


def test_a_killed_ledger_writer_releases_its_lock_at_once(tmp_path, monkeypatch):
    """Mutation caught: the same, for the evidence ledger's lock."""
    path = tmp_path / "evidence.jsonl"
    proc = _holder(
        "import time; from pathlib import Path\n"
        "from crossaudit.ledger.chain import _FileLock\n"
        f"_FileLock(Path({str(path) + '.lock'!r})).__enter__()\n"
        "print('held', flush=True); time.sleep(60)")
    assert ledger_chain.lock_status(path)["pid"] == proc.pid
    _kill(proc)
    monkeypatch.setattr(ledger_chain, "_LOCK_TIMEOUT_S", 0.5)
    began = time.monotonic()
    EvidenceLedger(path).append("note", run_id="r1", payload={"n": 1})
    assert time.monotonic() - began < 0.5
    assert ledger_chain.lock_status(path) is None


# ------------------------------------------------------- a live holder
def test_two_processes_cannot_both_hold_the_controller_lock(tmp_path, monkeypatch):
    """Mutation caught: an acquisition that proceeds while another process
    holds the lock (e.g. `_try_lock` ignoring EWOULDBLOCK)."""
    path = tmp_path / "state.json"
    proc = _holder(
        "import time; from crossaudit.controller import StateStore\n"
        f"s = StateStore({str(path)!r}); h = s._acquire(s.lock_path)\n"
        "print('held', flush=True); time.sleep(60)")
    try:
        monkeypatch.setattr(state_mod, "LOCK_TIMEOUT_S", 0.5)
        store = StateStore(path)
        began = time.monotonic()
        with pytest.raises(ConfigDenial) as denied:
            store.open_or_advance("t/p", "b" * 40, None)
        assert time.monotonic() - began >= 0.5
        assert denied.value.reason == (
            f"could not acquire the controller lock; another process (pid "
            f"{proc.pid}) is mid-transaction")
        assert store.lock_status()["pid"] == proc.pid      # the holder's survives
        assert not path.exists()                           # nothing was written
    finally:
        _kill(proc)


def test_a_live_ledger_writer_is_waited_on_then_refused(tmp_path, monkeypatch):
    """A thread holds the ledger lock; another writer waits the timeout and
    is refused naming the pid, and the holder's lock survives. Mutation
    caught: the ledger acquiring past a live holder."""
    path = tmp_path / "evidence.jsonl"
    holder = ledger_chain._FileLock(Path(str(path) + ".lock")).__enter__()
    try:
        monkeypatch.setattr(ledger_chain, "_LOCK_TIMEOUT_S", 0.3)
        with pytest.raises(ConfigDenial) as denied:
            EvidenceLedger(path).append("note", run_id="r1", payload={"n": 1})
        assert denied.value.reason == (
            f"the evidence ledger is locked by another writer (pid {os.getpid()})")
        assert ledger_chain.lock_status(path) is not None
        assert not path.exists()
    finally:
        holder.__exit__(None, None, None)


def test_a_replaced_lock_file_is_never_trusted(tmp_path):
    """Between the acquirer's `open` and its `flock`, the lock file is
    unlinked and recreated, and another holder takes the new one. The
    acquirer's flock on the orphaned inode succeeds; it must notice the inode
    no longer is the lock, release it and retry. Mutation caught: dropping
    the fstat/stat inode check -- the acquirer returns holding the orphan
    while the other holder holds the real lock (two holders)."""
    path = tmp_path / "state.json.lock"
    real_try = locks._try_lock
    rival: dict = {}

    def replace_then_lock(fd):
        if "started" not in rival:
            rival["started"] = True
            path.unlink()
            rival["held"] = locks.acquire(path, 1.0, lambda pid: AssertionError())
        return real_try(fd)

    locks._try_lock = replace_then_lock
    try:
        with pytest.raises(ConfigDenial):
            locks.acquire(path, 0.3, lambda pid: ConfigDenial(f"busy {pid}"))
    finally:
        locks._try_lock = real_try
    assert rival["held"].fd is not None
    # Once the rival releases, the acquirer gets the real (current) inode.
    rival["held"].release()
    held = locks.acquire(path, 1.0, lambda pid: ConfigDenial("busy"))
    try:
        assert os.fstat(held.fd).st_ino == os.stat(path).st_ino
    finally:
        held.release()


def test_a_ruling_in_flight_is_never_written_over(escalated, monkeypatch):
    """While a ruling's hook runs, another store tries to record an
    escalation: it waits, is refused, and writes nothing; the ruling then
    lands whole. Mutation caught: a second holder admitted during the ruling
    -- one of the two writes would be lost."""
    root, cid = escalated
    monkeypatch.setattr(rulings, "COMMIT_TIMEOUT_S", 10.0)
    store = StateStore(root / ".crossaudit" / "state.json")
    other = store.open_or_advance("t/p", "c" * 40, None)["cycle_id"]
    marker = root.parent / "hook-started"
    install_hook(root, f"#!/bin/sh\ntouch '{marker}'\nsleep 1.5\nexit 0\n")
    seen: dict = {}

    def rival():
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        monkeypatch.setattr(state_mod, "LOCK_TIMEOUT_S", 0.3)
        try:
            StateStore(store.path).escalate(other, "concurrent", kind="audit")
            seen["outcome"] = "wrote"
        except ConfigDenial as exc:
            seen["outcome"] = exc.reason

    thread = threading.Thread(target=rival)
    thread.start()
    result = main.resolve_cycle(load(), cid, "close", REASON)
    thread.join(20)
    assert seen["outcome"] == (f"could not acquire the controller lock; another "
                               f"process (pid {os.getpid()}) is mid-transaction")
    state = json.loads(store.path.read_text())
    assert result["cycle"]["status"] == "BLOCKED"
    assert state["cycles"][cid]["status"] == "BLOCKED"
    assert state["cycles"][other]["status"] == "OPEN"


# ------------------------------------------------------- doctor
def test_doctor_reports_who_holds_each_lock_and_nothing_else(escalated, capsys):
    """Mutation caught: `locks.status` not seeing a held lock (doctor silent
    while a writer holds it), or doctor reporting a free lock."""
    root, _cid = escalated
    store = StateStore(root / ".crossaudit" / "state.json")
    capsys.readouterr()
    main.main(["--json", "doctor"])
    checks = {c["check"] for c in json.loads(capsys.readouterr().out)["checks"]}
    assert "controller lock" not in checks and "evidence ledger lock" not in checks
    held = store._acquire(store.lock_path)
    ledger = ledger_chain._FileLock(root / ".crossaudit" / "evidence.jsonl.lock")
    ledger.__enter__()
    try:
        main.main(["--json", "doctor"])
        rows = {c["check"]: c for c in json.loads(capsys.readouterr().out)["checks"]}
    finally:
        ledger.__exit__(None, None, None)
        held.release()
    for name in ("controller lock", "evidence ledger lock"):
        assert rows[name]["ok"] is None
        assert rows[name]["detail"].endswith(f"is held by pid {os.getpid()} (alive)")


# ------------------------------------------------------- the pattern cannot return
def test_no_source_file_unlinks_a_lock_path():
    """Mutation caught: any `*.unlink(` / `os.unlink` / `os.remove` whose call
    mentions a lock, anywhere under src/, and ANY such call at all in the
    modules that implement the two locks (`locks.py`, `ledger/chain.py`,
    `controller/state.py`, where a lock path may hide behind a neutral name
    such as `self.path`) -- the check-then-unlink pattern rounds 3 and 4
    removed. Exceptions: git's `next-index-<pid>.lock` of a git process we
    killed, named by its pid (rulings.py), and in state.py the capability
    probe file and the state write's own temporary file (`state.json.tmp<pid>`),
    neither of which is a lock anyone else takes."""
    lock_modules = {"locks.py", "chain.py", "state.py"}
    offenders = []
    for path in sorted((SRC / "crossaudit").rglob("*.py")):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", "") or getattr(func, "id", "")
            if name not in ("unlink", "remove", "rmtree"):
                continue
            segment = ast.get_source_segment(source, node) or ""
            in_lock_module = (path.name in lock_modules
                              and path.parent.name in ("crossaudit", "ledger", "controller"))
            if "lock" not in segment.lower() and not in_lock_module:
                continue
            if path.name == "rulings.py" and "next-index-" in segment:
                continue
            if path.name == "state.py" and segment.startswith(("probe.unlink(",
                                                                "tmp.unlink(")):
                continue
            offenders.append(f"{path.relative_to(SRC)}:{node.lineno}: {segment}")
    assert offenders == []


# ------------------------------------------------------- git's index.lock (P2)
def test_a_foreign_index_lock_is_never_removed(escalated, monkeypatch):
    """After a timed-out commit is killed, another git writer takes
    `.git/index.lock` before our cleanup runs. It must still be there after
    the refusal, which says so; the killed process's `next-index-<pid>.lock`
    is removed. Mutation caught: unlinking `index.lock` in the cleanup (the
    round-3 behaviour)."""
    root, cid = escalated
    monkeypatch.setattr(rulings, "COMMIT_TIMEOUT_S", 1.0)
    install_hook(root, "#!/bin/sh\nsleep 10\n")
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    real_killpg = os.killpg
    seen: dict = {}

    def kill_then_a_foreign_writer(pid, sig):
        real_killpg(pid, sig)
        time.sleep(0.3)
        seen["next_index_before"] = (gitdir / f"next-index-{pid}.lock").exists()
        seen["pid"] = pid
        (gitdir / "index.lock").unlink(missing_ok=True)      # the old git is gone
        (gitdir / "index.lock").write_bytes(b"foreign writer")  # a new one takes it
    monkeypatch.setattr(rulings.os, "killpg", kill_then_a_foreign_writer)
    with pytest.raises(IntegrityDenial) as denied:
        main.resolve_cycle(load(), cid, "close", REASON)
    monkeypatch.undo()
    assert denied.value.reason.endswith(
        "; .git/index.lock may have been left by the killed git — if no git "
        "process is running, remove it by hand and run "
        "`git reset -q -- cycles/rulings.jsonl`")
    assert (gitdir / "index.lock").read_bytes() == b"foreign writer"
    assert seen["next_index_before"] is True
    assert not (gitdir / f"next-index-{seen['pid']}.lock").exists()
    (gitdir / "index.lock").unlink()


# ------------------------------------------- round 5: replaced after acquisition
def test_a_lock_file_replaced_after_acquisition_never_overwrites_the_new_holder(
        tmp_path, monkeypatch):
    """The reviewer's sequence: the lock file is replaced after the inode
    comparison (here, from `_write_token`), a second writer takes the
    replacement and records a cycle, then the first writer reaches its write.
    It must refuse and the second writer's cycle must survive. Mutation
    caught: dropping `require_current()` before `_write(state)` -- the first
    writer's stale snapshot erases the second's cycle."""
    path = tmp_path / "state.json"
    first = StateStore(path)
    first.open_or_advance("t/p", "1" * 40, None)          # an existing store
    real_write_token = locks._write_token
    seen: dict = {}

    def replace_then_second_writer(fd):
        real_write_token(fd)
        if "child" not in seen:
            seen["child"] = None
            first.lock_path.unlink()
            first.lock_path.write_text("")
            seen["child"] = StateStore(path).open_or_advance(
                "t/p", "2" * 40, None)["cycle_id"]
    monkeypatch.setattr(locks, "_write_token", replace_then_second_writer)
    with pytest.raises(IntegrityDenial) as denied:
        first.open_or_advance("t/p", "3" * 40, None)
    assert denied.value.reason == (
        f"the lock file {first.lock_path} was replaced while this process held "
        f"the lock; this process's change was discarded")
    cycles = json.loads(path.read_text())["cycles"]
    assert seen["child"] in cycles                         # child_cycle_survives
    assert len(cycles) == 2                                # the first's never landed


def test_a_ledger_lock_replaced_after_acquisition_never_forks_the_chain(
        tmp_path, monkeypatch):
    """The same sequence on the evidence ledger: the second writer appends on
    the replacement lock, then the first writer reaches its append. Mutation
    caught: dropping `require_current()` before the ledger's write -- both
    entries claim the same seq and prev, and `verify()` fails."""
    path = tmp_path / "evidence.jsonl"
    ledger = EvidenceLedger(path)
    ledger.append("note", run_id="r", payload={"n": 0})
    lock = Path(str(path) + ".lock")
    real_write_token = locks._write_token
    seen: dict = {}

    def replace_then_second_writer(fd):
        real_write_token(fd)
        if "child" not in seen:
            seen["child"] = None
            lock.unlink()
            lock.write_text("")
            seen["child"] = EvidenceLedger(path).append("note", run_id="r",
                                                       payload={"n": "second"})
    monkeypatch.setattr(locks, "_write_token", replace_then_second_writer)
    with pytest.raises(IntegrityDenial) as denied:
        ledger.append("note", run_id="r", payload={"n": "first"})
    assert "was replaced while this process held the lock" in denied.value.reason
    monkeypatch.undo()
    entries = EvidenceLedger(path).entries()
    assert [e["payload"]["n"] for e in entries] == [0, "second"]
    assert entries[-1]["digest"] == seen["child"]
    assert EvidenceLedger(path).verify().ok


# ------------------------------------------- round 5: no lock service
@pytest.mark.parametrize("code", [errno.ENOLCK, errno.ENOTSUP])
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_filesystem_without_locks_is_a_legible_refusal_not_a_traceback(
        escalated, monkeypatch, capsys, code, lang):
    """`flock` failing with ENOLCK / ENOTSUP (NFS and the like) through
    `main()`. Mutation caught: letting the OSError escape `locks.acquire`
    (main() catches only Denial: a traceback, no exit code)."""
    from crossaudit.errors import EXIT_CONFIG

    root, cid = escalated

    def no_locks(_fd):
        raise OSError(code, os.strerror(code))
    monkeypatch.setattr(locks, "_try_lock", no_locks)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    capsys.readouterr()
    argv = (["--lang", "zh"] if lang == "zh" else []) + [
        "resolve", cid, "--close", "--because", REASON]
    assert main.main(argv) == EXIT_CONFIG
    out, err = capsys.readouterr()
    name = errno.errorcode[code]
    lock = root / ".crossaudit" / "state.json.lock"
    if lang == "en":
        assert err.strip() == (
            f"DENIED (config): this filesystem cannot provide the exclusive "
            f"lock CrossAudit needs at {lock} ({name}: {os.strerror(code)}); use a "
            f"project directory on a local filesystem")
    else:
        assert err.strip().startswith(
            f"DENIED (config): 此文件系统无法在 {lock} 提供 CrossAudit 所需的独占锁"
            f"（{name}：")
    assert "Traceback" not in out + err
