"""A ruling committed to the ledger whose state change could not be written is
recovered at the next ruling on that cycle (review 2026-10-23 round 8; D176
ruling 27, superseded in mechanism by ruling 30: the recovery now follows the
local intent's nonce, see test_ruling_two_phase_intent.py). Also round 8's two P2: the credentials bootstrap inside
`main()`'s OS-error boundary (ruling 28) and the ledger's close (ruling 29).

Each test names the mutation it catches.
"""
from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n, main, tuiapp
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_CONFIG, EXIT_INTEGRITY, EXIT_OK, ConfigDenial
from crossaudit.gitio import git
from crossaudit.ledger import chain as chain_mod
from crossaudit.ledger.chain import EvidenceLedger

from .test_admission_and_console import console, fetch, post_json_to, rejected  # noqa: F401
from .test_resolve_commits_the_ruling import REASON, escalated  # noqa: F401

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _fail_the_next_state_write(monkeypatch):
    """The state write AFTER the commit fails once with ENOSPC: the
    reviewer's round-8 reproduction. Since the two-phase ruling (D176 ruling
    30) a ruling writes the state twice -- the intent before the commit
    (write 1) and the state change after it (write 2) -- so it is write 2
    that fails here."""
    real = StateStore._write
    calls = {"n": 0}

    def failing(self, state):
        calls["n"] += 1
        if calls["n"] == 2:
            try:
                raise OSError(errno.ENOSPC, "No space left on device")
            except OSError as exc:
                raise self._unwritable(exc) from exc
        return real(self, state)
    monkeypatch.setattr(StateStore, "_write", failing)


def _state(root: Path) -> dict:
    return json.loads((root / ".crossaudit" / "state.json").read_text())


def _rows(root: Path) -> list[dict]:
    return [json.loads(line) for line in
            (root / "cycles" / "rulings.jsonl").read_text().split("\n") if line]


def _status_row(capsys, cid):
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    doc = json.loads(capsys.readouterr().out)
    return next(r for r in doc["cycles"] if r["cycle_id"] == cid)


def _committed_then_failed(root, cid, monkeypatch, capsys, *argv_prefix):
    """resolve --close whose state write fails after the commit."""
    head = git("rev-parse", "HEAD", cwd=root)
    _fail_the_next_state_write(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    capsys.readouterr()
    code = main.main([*argv_prefix, "resolve", cid, "--close", "--because", REASON])
    err = capsys.readouterr().err
    sha = git("rev-parse", "HEAD", cwd=root)
    return head, sha, code, err


def test_a_failed_state_write_after_the_commit_names_the_committed_ruling(
        escalated, monkeypatch, capsys):
    """Mutation caught: letting the plain "controller state could not be
    written" refusal through after a commit -- it says nothing of the
    committed ruling, and the person rules again."""
    root, cid = escalated
    head, sha, code, err = _committed_then_failed(root, cid, monkeypatch, capsys)
    assert code == EXIT_INTEGRITY
    assert git("rev-list", "--count", f"{head}..{sha}", cwd=root) == "1"
    assert err.strip() == (
        f"DENIED (integrity): the ruling on cycle {cid} was committed to the ledger "
        f"as {sha[:12]}, but the cycle's state could not be written (ENOSPC: No "
        f"space left on device); the state is unchanged, and the next ruling on "
        f"this cycle applies the committed ruling")
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    # status, read-only, marks it.
    row = _status_row(capsys, cid)
    assert row["ruling_pending"] is True
    main.main(["status"])
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith(cid))
    assert "ruling committed, state pending" in line


def test_the_same_ruling_again_applies_the_committed_one_without_a_new_commit(
        escalated, monkeypatch, capsys):
    """Mutation caught: `rule()` without the committed-ruling check -- the
    second resolve commits a second row (HEAD moves) for one decision."""
    root, cid = escalated
    _head, sha, _code, _err = _committed_then_failed(root, cid, monkeypatch, capsys)
    capsys.readouterr()
    assert main.main(["resolve", cid, "--close", "--because", "again"]) == EXIT_OK
    out = capsys.readouterr().out
    row = _rows(root)[-1]
    assert out.splitlines()[0] == (
        f"the ruling of {row['at']} (close, {sha[:12]}) was already in the ledger; "
        f"the cycle's state now reflects it; no new ruling was written")
    assert git("rev-parse", "HEAD", cwd=root) == sha            # no new commit
    assert len(_rows(root)) == 1
    state = _state(root)
    assert state["cycles"][cid]["status"] == "BLOCKED"
    assert state["cycles"][cid]["closed_by_human"] is True
    resolution = [h for h in state["history"] if h.get("event") == "human_resolution"]
    assert len(resolution) == 1 and resolution[0]["reconciled"] is True
    assert "ruling_pending" not in _status_row(capsys, cid)


def test_the_opposite_ruling_is_refused_and_the_committed_one_stands(
        escalated, monkeypatch, capsys):
    """Mutation caught: honouring the new request (a reopen commit over a
    committed close) instead of the ledger."""
    root, cid = escalated
    _head, sha, _code, _err = _committed_then_failed(root, cid, monkeypatch, capsys)
    capsys.readouterr()
    code = main.main(["resolve", cid, "--reopen", "--because", "changed my mind"])
    err = capsys.readouterr().err
    assert code == EXIT_INTEGRITY
    assert err.strip() == (f"DENIED (integrity): a committed ruling (close, "
                           f"{sha[:12]}) already stands for cycle {cid}; the state "
                           f"now reflects it")
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"
    # And now the cycle is no longer ESCALATED: the existing rule refuses.
    code = main.main(["resolve", cid, "--reopen", "--because", "again"])
    assert code == EXIT_INTEGRITY
    assert "not ESCALATED" in capsys.readouterr().err


def test_the_sentences_speak_chinese(escalated, monkeypatch, capsys):
    """Mutation caught: either sentence without a Chinese entry/key."""
    root, cid = escalated
    _head, sha, _code, err = _committed_then_failed(
        root, cid, monkeypatch, capsys, "--lang", "zh")
    assert err.strip().startswith(
        f"DENIED (integrity): 周期 {cid} 的裁决已作为 {sha[:12]} 提交到账本，但周期状态无法写入")
    capsys.readouterr()
    assert main.main(["--lang", "zh", "resolve", cid, "--close", "--because", "x"]) == EXIT_OK
    assert capsys.readouterr().out.splitlines()[0].endswith(
        f"的裁决（close，{sha[:12]}）已在账本中；周期状态现已与之一致；没有写入新的裁决")


def test_the_tui_reconciles_with_the_same_sentence(escalated, monkeypatch, capsys):
    """Mutation caught: `rule_on` printing "Ruling recorded" for a ruling it
    did not record."""
    root, cid = escalated
    _head, sha, _code, _err = _committed_then_failed(root, cid, monkeypatch, capsys)
    lines = tuiapp.rule_on(load(), cid, "close", "again")
    row = _rows(root)[-1]
    assert lines[0] == (f"the ruling of {row['at']} (close, {sha[:12]}) was already "
                        f"in the ledger; the cycle's state now reflects it; no new "
                        f"ruling was written")
    assert git("rev-parse", "HEAD", cwd=root) == sha


def test_the_console_reconciles_and_refuses_the_opposite(console, monkeypatch):  # noqa: F811
    """Through `/api/escalation`. Mutations caught: the console committing a
    second ruling; or its response not saying the ruling was reconciled."""
    _s, body, _h = fetch(console.replace("/?t=", "/api/state?t="))
    root = Path(json.loads(body)["root"])
    store = StateStore(root / ".crossaudit" / "state.json")
    a = store.open_or_advance("t/p", "a" * 40, None)["cycle_id"]
    b = store.open_or_advance("t/p", "b" * 40, None)["cycle_id"]
    for cid in (a, b):
        store.escalate(cid, "round budget spent")
    cfg = load(root / "crossaudit.yml")
    for cid in (a, b):
        _fail_the_next_state_write(monkeypatch)
        with pytest.raises(Exception) as denied:
            rulings.rule(cfg, store, cid, "close", REASON)
        assert "was committed to the ledger as" in str(denied.value)
        monkeypatch.undo()
    head = git("rev-parse", "HEAD", cwd=root)
    code, result, _h = post_json_to(console, "/api/escalation", {
        "cycle_id": a, "action": "close", "reason": "again"})
    assert code == 200 and result["status"] == "BLOCKED" and result["reconciled"] is True
    assert result["message"].endswith(
        "was already in the ledger; the cycle's state now reflects it; no new "
        "ruling was written")
    assert "已在账本中" in result["message_zh"]
    status, raw, _h = rejected(lambda: post_json_to(console, "/api/escalation", {
        "cycle_id": b, "action": "reopen", "reason": "the other way"}))
    assert 400 <= status < 500
    assert json.loads(raw)["reason"].startswith(f"a committed ruling (close, ")
    assert git("rev-parse", "HEAD", cwd=root) == head            # no new commit


# ------------------------------------------------ ruling 28: the bootstrap
@pytest.mark.parametrize("mode", ["en", "zh", "json"])
def test_an_unreadable_credentials_file_is_one_sentence(
        escalated, monkeypatch, capsys, tmp_path, mode):
    """Mutation caught: `wizard.load_keys_into_env()` back outside `main()`'s
    try -- a raw PermissionError."""
    keys = tmp_path / "keys.env"
    keys.write_text("export X=1\n")
    keys.chmod(0o000)
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(keys))
    argv = {"en": ["status"], "zh": ["--lang", "zh", "status"],
            "json": ["--json", "status"]}[mode]
    capsys.readouterr()
    try:
        code = main.main(argv)
    finally:
        keys.chmod(0o600)
    out, err = capsys.readouterr()
    assert code == EXIT_CONFIG
    assert "Traceback" not in out + err
    if mode == "en":
        assert err.strip() == ("an operating-system error stopped this command: "
                               f"Permission denied (EACCES) at {keys}")
    elif mode == "zh":
        assert err.strip() == ("一个操作系统错误中止了此命令：Permission denied（EACCES）"
                               f"，位置：{keys}")
    else:
        doc = json.loads(out)
        assert doc["kind"] == "os_error" and doc["exit_code"] == EXIT_CONFIG


# ------------------------------------------------ ruling 29: the ledger's close
def test_a_close_that_fails_after_the_write_does_not_claim_nothing_was_written(
        tmp_path, monkeypatch):
    """The ledger fd is closed, then the close reports EIO. Mutations caught:
    the close outside the conversion (a raw OSError), or reported with the
    "could not be written" sentence although the entry is on disk."""
    path = tmp_path / "evidence.jsonl"
    ledger = EvidenceLedger(path)
    ledger.append("note", run_id="r", payload={"n": 0})
    real_close = os.close
    calls = {"n": 0}

    def close_then_eio(fd):
        calls["n"] += 1
        real_close(fd)
        if calls["n"] == 1:
            raise OSError(errno.EIO, "Input/output error")
    monkeypatch.setattr(chain_mod.os, "close", close_then_eio)
    with pytest.raises(ConfigDenial) as denied:
        ledger.append("note", run_id="r", payload={"n": 1})
    monkeypatch.undo()
    assert denied.value.reason == (
        f"the evidence ledger at {path} could not be closed cleanly after writing "
        f"(EIO: Input/output error); the entry may have been recorded, and the next "
        f"append verifies the chain")
    EvidenceLedger(path).append("note", run_id="r", payload={"n": 2})
    assert [e["payload"]["n"] for e in EvidenceLedger(path).entries()] == [0, 1, 2]
    assert EvidenceLedger(path).verify().ok
