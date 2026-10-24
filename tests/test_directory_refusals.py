"""A missing parent directory that cannot be created is a refusal, not a
traceback (review 2026-10-23 round 6, finding 1).

The reviewer put a regular file where `.crossaudit/` should be and got
`FileExistsError` through `main()`, which catches only `Denial`. Every
`mkdir` for the controller state, the evidence ledger and a lock file now
goes through `locks.ensure_directory`. Each test names the mutation it
catches.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from crossaudit import locks
from crossaudit.cli import main
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_CONFIG, ConfigDenial
from crossaudit.ledger.chain import EvidenceLedger

from .test_resolve_commits_the_ruling import REASON, escalated  # noqa: F401

TAIL = "(EEXIST: File exists); check the path is a directory you can write"


def _blocked(tmp_path: Path) -> Path:
    """A regular file where a directory should be."""
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    return blocker


def test_the_store_refuses_when_its_directory_is_a_file(tmp_path):
    """Mutation caught: `StateStore._locked` calling `mkdir` directly -- a raw
    FileExistsError."""
    blocker = _blocked(tmp_path)
    with pytest.raises(ConfigDenial) as denied:
        StateStore(blocker / "state.json").open_or_advance("t/p", "a" * 40, None)
    assert denied.value.reason == (
        f"the directory {blocker} for the controller state could not be created {TAIL}")


def test_the_ledger_refuses_when_its_directory_is_a_file(tmp_path):
    """Mutation caught: `EvidenceLedger.append` creating its directory
    without the helper (the lock's sentence, or a raw error, would answer)."""
    blocker = _blocked(tmp_path)
    with pytest.raises(ConfigDenial) as denied:
        EvidenceLedger(blocker / "evidence.jsonl").append(
            "note", run_id="r", payload={})
    assert denied.value.reason == (
        f"the directory {blocker} for the evidence ledger could not be created {TAIL}")


def test_a_lock_refuses_when_its_directory_is_a_file(tmp_path):
    """Mutation caught: `locks.acquire` calling `mkdir` directly."""
    blocker = _blocked(tmp_path)
    with pytest.raises(ConfigDenial) as denied:
        locks.acquire(blocker / "x.lock", 0.1, lambda pid: ConfigDenial("busy"))
    assert denied.value.reason == (
        f"the directory {blocker} for the lock file could not be created {TAIL}")


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_resolve_on_a_project_whose_state_directory_is_a_file(
        escalated, monkeypatch, capsys, lang):
    """Through `main()`: `.crossaudit` replaced by a regular file. Mutation
    caught: any of the three sites raising the OSError past `main()` -- a
    traceback and no exit code."""
    root, cid = escalated
    state_dir = root / ".crossaudit"
    shutil.rmtree(state_dir)
    state_dir.write_text("not a directory")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    capsys.readouterr()
    argv = (["--lang", "zh"] if lang == "zh" else []) + [
        "resolve", cid, "--close", "--because", REASON]
    assert main.main(argv) == EXIT_CONFIG
    out, err = capsys.readouterr()
    if lang == "en":
        assert err.strip() == (
            f"DENIED (config): the directory {state_dir} for the controller state "
            f"could not be created {TAIL}")
    else:
        assert err.strip() == (
            f"DENIED (config): 无法创建用于控制器状态的目录 {state_dir}"
            f"（EEXIST：File exists）；请确认该路径是你可写入的目录")
    assert "Traceback" not in out + err
