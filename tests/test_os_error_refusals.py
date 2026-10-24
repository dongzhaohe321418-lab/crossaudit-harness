"""Operating-system errors on the state and ledger write paths, and anywhere
else, reach a person as one legible sentence, never a traceback (review
2026-10-23 round 7).

Two layers: the state write and the ledger append turn their own OSErrors
into translated ConfigDenials; and `main()` catches any OSError that no layer
translated and prints one sentence in the person's language. Each test names
the mutation it catches.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from crossaudit.cli import main
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_CONFIG, ConfigDenial
from crossaudit.gitio import git
from crossaudit.ledger import chain as chain_mod
from crossaudit.ledger.chain import EvidenceLedger

from .test_resolve_commits_the_ruling import REASON, escalated  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="POSIX permissions, not as root")


def _argv(lang, *rest):
    return (["--lang", "zh"] if lang == "zh" else []) + list(rest)


# ---------------------------------------------------------- the state write
def test_the_store_refuses_an_unwritable_existing_directory(tmp_path):
    """The reviewer's reproduction at the store: an existing, writable lock
    file and a state directory at 0500. Mutation caught: `_write` opening the
    temporary file unwrapped -- a raw PermissionError."""
    store = StateStore(tmp_path / "state" / "state.json")
    store.open_or_advance("t/p", "a" * 40, None)
    store.path.parent.chmod(0o500)
    try:
        with pytest.raises(ConfigDenial) as denied:
            store.open_or_advance("t/p", "b" * 40, None)
    finally:
        store.path.parent.chmod(0o700)
    assert denied.value.reason == (
        f"the controller state at {store.path} could not be written (EACCES: "
        f"Permission denied); check the directory and file are writable")
    assert list(store.path.parent.glob("state.json.tmp*")) == []


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_resolve_with_an_unwritable_state_directory_refuses_before_committing(
        escalated, monkeypatch, capsys, lang):
    """Through `main()`. The ruling is refused BEFORE its commit, so the
    ledger never holds a ruling whose state change then failed. Since the
    two-phase ruling (D176 ruling 30) the refusal comes from the intent's
    state write, which precedes the commit (it replaced round 7's
    `_require_writable` probe). Mutation caught: committing before the
    intent is written (HEAD moves). `_write`'s own wrapping is caught by the
    store-level test above."""
    root, cid = escalated
    state_dir = root / ".crossaudit"
    head = git("rev-parse", "HEAD", cwd=root)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    state_dir.chmod(0o500)
    try:
        capsys.readouterr()
        code = main.main(_argv(lang, "resolve", cid, "--close", "--because", REASON))
        out, err = capsys.readouterr()
    finally:
        state_dir.chmod(0o700)
    assert code == EXIT_CONFIG
    path = state_dir / "state.json"
    if lang == "en":
        assert err.strip() == (
            f"DENIED (config): the controller state at {path} could not be written "
            f"(EACCES: Permission denied); check the directory and file are writable")
    else:
        assert err.strip() == (
            f"DENIED (config): 无法写入位于 {path} 的控制器状态（EACCES：Permission "
            f"denied）；请确认该目录和文件可写")
    assert "Traceback" not in out + err
    assert git("rev-parse", "HEAD", cwd=root) == head
    state = json.loads(path.read_text())
    assert state["cycles"][cid]["status"] == "ESCALATED"


# ---------------------------------------------------------- the ledger append
def _ledger_sentence(path, name, why):
    return (f"the evidence ledger at {path} could not be written ({name}: {why}); "
            f"check the file and its directory are writable")


def test_the_ledger_refuses_a_read_only_file(tmp_path):
    """The reviewer's reproduction: an existing, valid, empty ledger at 0400.
    Mutation caught: the append's `os.open` unwrapped -- a raw
    PermissionError."""
    path = tmp_path / "evidence.jsonl"
    path.write_bytes(b"")
    path.chmod(0o400)
    with pytest.raises(ConfigDenial) as denied:
        EvidenceLedger(path).append("note", run_id="r", payload={})
    assert denied.value.reason == _ledger_sentence(path, "EACCES", "Permission denied")


def test_the_ledger_refuses_a_directory_replaced_after_the_lock_check(
        tmp_path, monkeypatch):
    """The directory is replaced by a regular file right after
    `require_current()`. Mutation caught: the same unwrapped `os.open` -- a
    raw NotADirectoryError."""
    folder = tmp_path / "led"
    path = folder / "evidence.jsonl"
    ledger = EvidenceLedger(path)
    ledger.append("note", run_id="r", payload={"n": 0})
    real = chain_mod.locks.HeldLock.require_current

    def check_then_replace(self):
        real(self)
        folder.rename(tmp_path / "led-moved")
        folder.write_text("not a directory")
    monkeypatch.setattr(chain_mod.locks.HeldLock, "require_current", check_then_replace)
    with pytest.raises(ConfigDenial) as denied:
        ledger.append("note", run_id="r", payload={"n": 1})
    assert denied.value.reason == _ledger_sentence(path, "ENOTDIR", "Not a directory")


def test_a_failed_write_leaves_no_partial_line(tmp_path, monkeypatch):
    """A write that fails part-way (half the line on disk, then ENOSPC) is
    taken back, and the next append chains normally. Mutation caught:
    dropping the `ftruncate` -- the partial line stays and the next append is
    refused as a torn tail."""
    path = tmp_path / "evidence.jsonl"
    ledger = EvidenceLedger(path)
    ledger.append("note", run_id="r", payload={"n": 0})
    before = path.read_bytes()
    real_write = os.write

    def half_then_full(fd, data):
        real_write(fd, data[: len(data) // 2])
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(chain_mod.os, "write", half_then_full)
    with pytest.raises(ConfigDenial) as denied:
        ledger.append("note", run_id="r", payload={"n": 1})
    monkeypatch.undo()
    assert "(ENOSPC: No space left on device)" in denied.value.reason
    assert path.read_bytes() == before
    EvidenceLedger(path).append("note", run_id="r", payload={"n": 2})
    assert [e["payload"]["n"] for e in EvidenceLedger(path).entries()] == [0, 2]
    assert EvidenceLedger(path).verify().ok


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_ledger_sentence_reaches_main_in_both_languages(
        escalated, monkeypatch, capsys, lang):
    """No CLI command appends to the evidence ledger without a full MCP
    build, so `status` stands in: its command function is replaced by one
    that appends to a read-only ledger, and `main()`'s handling of the
    resulting refusal is what is under test. Mutation caught: the ledger's
    refusal not being a Denial (a traceback through `main()`)."""
    root, _cid = escalated
    path = root / ".crossaudit" / "evidence.jsonl"
    path.write_bytes(b"")
    path.chmod(0o400)

    def appends(_args):
        EvidenceLedger(path).append("note", run_id="r", payload={})
        return 0
    monkeypatch.setattr(main, "cmd_status", appends)
    capsys.readouterr()
    assert main.main(_argv(lang, "status")) == EXIT_CONFIG
    out, err = capsys.readouterr()
    if lang == "en":
        assert err.strip() == "DENIED (config): " + _ledger_sentence(
            path, "EACCES", "Permission denied")
    else:
        assert err.strip() == (f"DENIED (config): 无法写入位于 {path} 的证据账本"
                               f"（EACCES：Permission denied）；请确认该文件及其目录可写")
    assert "Traceback" not in out + err


# ---------------------------------------------------------- the last resort
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_untranslated_os_error_is_still_one_sentence(
        escalated, monkeypatch, capsys, lang):
    """An OSError no layer turned into a Denial (EIO from deep inside a
    command). Mutation caught: removing `main()`'s `except OSError` -- the
    error escapes `main()` as a traceback."""
    _root, _cid = escalated

    def deep_failure(_args):
        raise OSError(errno.EIO, "Input/output error", "/dev/disk-that-failed")
    monkeypatch.setattr(main, "cmd_status", deep_failure)
    capsys.readouterr()
    assert main.main(_argv(lang, "status")) == EXIT_CONFIG
    out, err = capsys.readouterr()
    if lang == "en":
        assert err.strip() == ("an operating-system error stopped this command: "
                               "Input/output error (EIO) at /dev/disk-that-failed")
    else:
        assert err.strip() == ("一个操作系统错误中止了此命令：Input/output error（EIO）"
                               "，位置：/dev/disk-that-failed")
    assert "Traceback" not in out + err
