"""The intent survives every uncertain commit, a corrupt HEAD is never "no
commit yet", and the intent's fields are bound to the committed row (review
2026-10-23 round 10; D176 rulings 33 and 34). Each test names the mutation it
catches.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import git

from .test_admission_and_console import console, fetch  # noqa: F401
from .test_resolve_commits_the_ruling import (REASON, REFUSING_HOOK, escalated,  # noqa: F401
                                              install_hook)
from .test_ruling_two_phase_intent import _fail_phase3_write

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
    return ([json.loads(ln) for ln in path.read_text().split("\n") if ln]
            if path.exists() else [])


def _count(root: Path, since: str) -> int:
    return int(git("rev-list", "--count", f"{since}..HEAD", cwd=root))


# ------------------------------------------------ ruling 33: uncertainty keeps it
@pytest.mark.parametrize("second", ["close", "reopen"])
def test_a_landed_commit_whose_confirmation_read_fails_keeps_the_intent(
        escalated, monkeypatch, second):
    """The commit lands; the post-commit `cat-file` fails once. Mutation
    caught: clearing the intent on any phase-2 failure (round 9's broad
    except) -- the next ruling finds no intent and writes a second row."""
    root, cid = escalated
    cfg = load()
    head = git("rev-parse", "HEAD", cwd=root)
    real = rulings._bounded_bytes
    calls = {"n": 0}

    def confirmation_fails_once(cfg, args, deadline):
        if args[:2] == ("cat-file", "blob") and calls["n"] == 0:
            calls["n"] += 1
            return 128, b"", "fatal: unable to read blob\n"
        return real(cfg, args, deadline)
    monkeypatch.setattr(rulings, "_bounded_bytes", confirmation_fails_once)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    assert denied.value.reason == (
        f"the ruling on cycle {cid} was committed as {sha[:12]}, but the committed "
        f"{LOG} could not be read back to confirm it (fatal: unable to read blob); "
        f"the cycle stays ESCALATED, and the next ruling on this cycle recovers it")
    assert _count(root, head) == 1 and len(_rows(root)) == 1
    assert cid in _state(root)["pending_rulings"]
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    if second == "close":
        assert rulings.rule(cfg, _store(root), cid, "close", "again")["reconciled"]
    else:
        with pytest.raises(IntegrityDenial, match="already stands"):
            rulings.rule(cfg, _store(root), cid, "reopen", "other")
    assert git("rev-parse", "HEAD", cwd=root) == sha            # no second commit
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


def test_a_commit_that_definitely_did_not_land_clears_the_intent(escalated):
    """A rejecting pre-commit hook: `git commit` failed and HEAD is
    unchanged, so the intent is cleared. Mutation caught: treating a commit
    refused with HEAD unchanged as uncertain (the next ruling would carry a
    needless "earlier attempt" note)."""
    root, cid = escalated
    cfg = load()
    install_hook(root, REFUSING_HOOK)
    head = git("rev-parse", "HEAD", cwd=root)
    with pytest.raises(IntegrityDenial, match="nothing was recorded"):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert cid not in _state(root).get("pending_rulings", {})


# ------------------------------------------------ ruling 33: a corrupt HEAD
def test_a_failed_rev_parse_during_recovery_is_refused_not_no_commit(
        escalated, monkeypatch):
    """After a post-commit state-write failure, `git rev-parse --verify HEAD`
    fails during recovery while HEAD names an existing branch. Mutation
    caught: treating every rev-parse failure as "no commit yet" (round 9) --
    the intent is cleared and a second ruling committed."""
    root, cid = escalated
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    real = rulings._bounded

    def corrupt_head(cfg, args, deadline):
        if args == ("rev-parse", "--verify", "-q", "HEAD"):
            return 128, "", "fatal: corrupt HEAD"
        return real(cfg, args, deadline)
    monkeypatch.setattr(rulings, "_bounded", corrupt_head)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", "again")
    monkeypatch.undo()
    assert denied.value.reason == ("the committed rulings log could not be read "
                                   "(fatal: corrupt HEAD); no ruling is made until "
                                   "it can be")
    assert cid in _state(root)["pending_rulings"]
    assert git("rev-parse", "HEAD", cwd=root) == sha


def test_a_genuinely_unborn_repository_reads_as_no_rows(console):  # noqa: F811
    """A fresh `git init` (no commit) with an intent present: no rows, the
    intent is cleared and the ruling proceeds as the repository's first
    commit. Mutation caught: refusing an unborn HEAD (the first ruling in a
    new project could never be recovered from a crash)."""
    _s, body, _h = fetch(console.replace("/?t=", "/api/state?t="))
    root = Path(json.loads(body)["root"])
    assert git("rev-parse", "-q", "--verify", "HEAD", cwd=root, check=False) == ""
    store = _store(root)
    cid = store.open_or_advance("t/p", "a" * 40, None)["cycle_id"]
    store.escalate(cid, "round budget spent")
    cfg = load(root / "crossaudit.yml")
    assert rulings.committed_rows(cfg, strict=True) == []
    with store._locked() as state:
        state.setdefault("pending_rulings", {})[cid] = {
            "action": "close", "nonce": "b" * 32, "reason_sha256": "", "by": "",
            "started_at": 0}
    result = rulings.rule(cfg, store, cid, "close", REASON)
    assert result.get("intent_cleared") is True
    assert int(git("rev-list", "--count", "HEAD", cwd=root)) == 1
    assert store.cycle(cid)["status"] == "BLOCKED"


# ------------------------------------------------ ruling 34: the binding
def test_a_filter_that_rewrites_the_nonce_stops_phase_3(escalated):
    """A clean filter rewrites the `intent` value in the committed line.
    Mutation caught: confirming on four fields without the nonce (round 9)
    -- phase 3 applies the state change although the commit carries another
    nonce."""
    root, cid = escalated
    cfg = load()
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    (gitdir / "info").mkdir(exist_ok=True)
    (gitdir / "info" / "attributes").write_text(f"{LOG} filter=nonce\n")
    git("config", "filter.nonce.clean",
        "sed 's/\"intent\": \"[0-9a-f]*\"/\"intent\": \"00000000\"/'", cwd=root)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert "could not be confirmed to contain it (a filter or hook changed the file)" \
        in denied.value.reason
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    assert cid in _state(root)["pending_rulings"]


def test_a_forged_local_intent_cannot_apply_a_committed_row(escalated, monkeypatch):
    """A genuine committed `close` row (its state write failed) and a local
    intent edited to say `reopen` with the right nonce. Mutation caught:
    recovery matching on cycle and nonce only (round 9) -- the forged intent
    would pass and the committed action be applied under it."""
    root, cid = escalated
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    store = _store(root)
    with store._locked() as state:
        state["pending_rulings"][cid]["action"] = "reopen"
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, store, cid, "reopen", REASON)
    assert denied.value.reason == (f"the committed ruling for cycle {cid} does not "
                                   f"match this controller's intent (action); nothing "
                                   f"was applied")
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    assert git("rev-parse", "HEAD", cwd=root) == sha
    with store._locked() as state:
        state["pending_rulings"][cid]["action"] = "close"
        state["pending_rulings"][cid]["reason_sha256"] = "0" * 64
    with pytest.raises(IntegrityDenial, match=r"\(reason_sha256\); nothing was applied"):
        rulings.rule(cfg, store, cid, "close", REASON)


def test_confirm_committed_refuses_a_row_whose_nonce_differs(escalated):
    """The reviewer's direct call: the committed row, with only its `intent`
    changed. Mutation caught: the four-field comparison."""
    root, cid = escalated
    cfg = load()
    rulings.rule(cfg, _store(root), cid, "close", REASON)
    row = dict(_rows(root)[-1], commit=git("rev-parse", "HEAD", cwd=root))
    rulings._confirm_committed(cfg, root / LOG, LOG, dict(row), time.monotonic() + 5)
    row["intent"] = "c" * 32
    with pytest.raises(IntegrityDenial):
        rulings._confirm_committed(cfg, root / LOG, LOG, row, time.monotonic() + 5)
