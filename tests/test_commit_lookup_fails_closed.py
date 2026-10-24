"""A ``git log`` that cannot answer while a ruling locates a row's commit is
a refusal, never "no commit" (D176 ruling 57). Seen once on the pull
request's CI: after an escalation whose row committed but whose confirmation
failed, the next ruling's lookup returned nothing and the escalation row was
written a second time. Each test names the mutation it catches. The hang is
real: ``git`` on PATH is a shim that sleeps past the bound on ``log``.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import git

from .test_resolve_commits_the_ruling import REASON, escalated, ruling_rows  # noqa: F401

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the shim is a sh script")

LOG = "cycles/rulings.jsonl"
REAL_GIT = shutil.which("git")
UNREADABLE = ("the committed rulings log could not be read (git log timed out after 1s); "
              "no ruling is made until it can be")


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _store(root: Path) -> StateStore:
    return StateStore(root / ".crossaudit" / "state.json")


def _state(root: Path) -> dict:
    return json.loads((root / ".crossaudit" / "state.json").read_text())


def _escalation_rows(root: Path) -> list[dict]:
    rows = [json.loads(ln) for ln in (root / LOG).read_text().split("\n") if ln]
    return [r for r in rows if r.get("kind") == "escalation"]


class _Switch:
    def __init__(self, monkeypatch, marker: Path):
        self._mp = monkeypatch
        self.marker = marker

    def hang(self, verb: str = "log", *, after_marker: bool = False) -> None:
        """Make ``git <verb>`` sleep past the bound: at once, or only once
        ``self.marker`` exists (a hook creates it, so a step BEFORE the
        commit still answers and the one AFTER it hangs)."""
        self._mp.setenv("HANG_GIT_VERB", verb)
        self._mp.setenv("HANG_GIT_AFTER", str(self.marker) if after_marker else "")

    def answer(self) -> None:
        self._mp.delenv("HANG_GIT_VERB", raising=False)
        self._mp.delenv("HANG_GIT_AFTER", raising=False)
        if self.marker.exists():
            self.marker.unlink()


@pytest.fixture
def hanging_git(tmp_path, monkeypatch) -> _Switch:
    """``git`` on PATH runs the real git, except that the verb named by
    HANG_GIT_VERB first sleeps past the bound (when HANG_GIT_AFTER names a
    file, only once that file exists). The cleanup bound is lowered to 1 s
    so the refusal is quick; the sentence names that bound."""
    shim = tmp_path / "git-shim"
    shim.mkdir()
    (shim / "git").write_text(
        "#!/bin/sh\n"
        'if [ -n "$HANG_GIT_VERB" ] && [ "$1" = "$HANG_GIT_VERB" ]; then\n'
        '  if [ -z "$HANG_GIT_AFTER" ] || [ -f "$HANG_GIT_AFTER" ]; then sleep 30; fi\n'
        "fi\n"
        f'exec "{REAL_GIT}" "$@"\n')
    (shim / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(rulings, "CLEANUP_TIMEOUT_S", 1.0)
    return _Switch(monkeypatch, tmp_path / "after-the-commit")


# ------------------------------------------------ ruling 57
def test_a_lookup_that_cannot_answer_never_writes_the_escalation_row_again(
        escalated, monkeypatch, hanging_git):
    """The CI sequence, made deterministic. An escalation whose row committed
    but whose confirmation failed (nonce kept in the state, `escalation_commit`
    empty); on the next ruling, `git log` -- the step that locates the row's
    commit -- hangs past its bound. The ruling is refused by name, no row is
    written, nothing is committed and the nonce is kept; once git answers, the
    row at HEAD is recognised once and the ruling proceeds. Mutation caught:
    `commit_of` reading a failed `git log` as "no commit" -- the escalation
    row is written a second time and the ruling proceeds on the duplicate."""
    root, cid = escalated
    cfg = load()
    rulings.rule(cfg, _store(root), cid, "reopen", "try once more")
    rows_before = len(_escalation_rows(root))
    real = rulings._bounded_bytes
    broken = {"on": True}

    def confirmation_times_out(cfg_, args, deadline):
        if broken["on"] and args == ("cat-file", "blob", f"HEAD:{LOG}"):
            raise rulings._StepFailed("git cat-file timed out after 1s")
        return real(cfg_, args, deadline)
    monkeypatch.setattr(rulings, "_bounded_bytes", confirmation_times_out)
    _store(root).escalate(cid, "build round budget spent (3)", kind="audit")
    broken["on"] = False
    state = _state(root)["cycles"][cid]
    assert state["status"] == "ESCALATED" and state["escalation_commit"] == ""
    nonce = state["escalation_nonce"]
    assert nonce
    head = git("rev-parse", "HEAD", cwd=root)
    assert len(_escalation_rows(root)) == rows_before + 1

    hanging_git.hang("log")
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    hanging_git.answer()
    assert denied.value.reason == UNREADABLE
    assert git("rev-parse", "HEAD", cwd=root) == head               # nothing committed
    assert len(_escalation_rows(root)) == rows_before + 1          # not written again
    after = _state(root)["cycles"][cid]
    assert after["status"] == "ESCALATED" and after["escalation_commit"] == ""
    assert after["escalation_nonce"] == nonce
    assert after["escalation_error"] == UNREADABLE

    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert "reconciled" not in result
    assert len(_escalation_rows(root)) == rows_before + 1          # recognised, once
    assert result["ruling"]["escalation_commit"] == head
    assert int(git("rev-list", "--count", f"{head}..HEAD", cwd=root)) == 1  # the close
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


def test_a_ruling_refuses_by_name_while_the_escalation_commit_cannot_be_located(
        escalated, hanging_git):
    """A normally committed escalation; `git log` hangs during the ruling.
    Refused as the log being unreadable -- not as the ledger holding no
    verified escalation row -- with nothing committed and the state unchanged;
    once git answers the ruling proceeds on the same escalation. Mutation
    caught: a non-strict lookup in `assess` -- the identity reads as "" and
    the refusal blames the ledger for a row it holds."""
    root, cid = escalated
    cfg = load()
    before = _state(root)["cycles"][cid]
    assert before["escalation_commit"]
    head = git("rev-parse", "HEAD", cwd=root)
    hanging_git.hang("log")
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    hanging_git.answer()
    assert denied.value.reason == UNREADABLE
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert _state(root)["cycles"][cid] == before
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert result["ruling"]["escalation_commit"] == before["escalation_commit"]
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


def test_a_timed_out_step_names_the_bound_it_had_and_display_reads_stay_lenient(
        escalated, hanging_git):
    """`_bounded_bytes` names the bound in force for the step, carried on its
    deadline: a lookup under the 1 s bound says "after 1s", not the 90 s row
    budget (a row's own step names the row budget, whatever earlier steps
    consumed: `test_a_slow_filter_plus_a_slow_hook_share_one_deadline`); and
    the non-strict `commit_of` (status, display) answers "" without raising.
    Mutations caught: reporting `row_budget()` for every step; strict by
    default."""
    root, _cid = escalated
    cfg = load()
    hanging_git.hang("log")
    started = time.monotonic()
    with pytest.raises(rulings._StepFailed) as failed:
        rulings._bounded_bytes(cfg, ("log", "-n", "1", "--format=%H"),
                               rulings._until(rulings.CLEANUP_TIMEOUT_S))
    assert failed.value.why == "git log timed out after 1s"
    assert rulings.commit_of(cfg, {"kind": "escalation", "cycle_id": "x"}) == ""
    hanging_git.answer()
    assert time.monotonic() - started < 10                          # killed, not waited


def test_a_step_reached_with_no_time_left_says_so_and_never_starts_git(
        escalated, hanging_git):
    """A step whose deadline has already passed when it is reached (the row
    budget spent by the steps before it) is refused without starting git, and
    the sentence says that -- not "timed out after 90s", a bound it never had
    (review round 20). Mutation caught: reporting `row_budget()` on the
    expired branch."""
    root, _cid = escalated
    cfg = load()
    hanging_git.hang("log")                   # a started `git log` would take 1 s
    started = time.monotonic()
    with pytest.raises(rulings._StepFailed) as failed:
        rulings._bounded_bytes(cfg, ("log", "-n", "1"), rulings._until(-0.01))
    hanging_git.answer()
    assert failed.value.why == "git log was not started: its time budget was already spent"
    assert time.monotonic() - started < 0.5                         # never started


# ------------------------------------------------ the ruling's confirmation (round 21)
def test_a_confirmation_that_hangs_after_the_commit_is_bounded_on_its_own_and_recovered(
        escalated, hanging_git):
    """The ruling's commit lands; the read that confirms it (`git cat-file`)
    hangs. Bounded on its own at the cleanup bound, like the escalation row's
    confirmation: refused within seconds, by name, marked `commit_landed=yes`
    with the intent kept and the state unchanged; the next ruling applies the
    committed row (`reconciled`) and writes no second one. The hang starts
    only after the commit (a post-commit hook creates the marker), so the
    reads before it answer. Mutation caught: the confirmation bounded by what
    was left of the row's deadline (`max(deadline, floor)`, the old code) --
    the hang is waited out for the row budget and the sentence names it."""
    root, cid = escalated
    cfg = load()
    hooks = Path(git("rev-parse", "--absolute-git-dir", cwd=root)) / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "post-commit").write_text(f"#!/bin/sh\ntouch {hanging_git.marker}\n")
    (hooks / "post-commit").chmod(0o755)
    head = git("rev-parse", "HEAD", cwd=root)
    rows = len(ruling_rows(root))
    hanging_git.hang("cat-file", after_marker=True)
    started = time.monotonic()
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert time.monotonic() - started < 10
    hanging_git.answer()
    landed = git("rev-parse", "HEAD", cwd=root)
    assert landed != head
    assert denied.value.reason == (
        f"the ruling on cycle {cid} was committed as {landed[:12]}, but the committed "
        f"{LOG} could not be read back to confirm it (git cat-file timed out after 1s); "
        f"the cycle stays ESCALATED, and the next ruling on this cycle recovers it")
    assert denied.value.detail.get("commit_landed") == "yes"
    state = _state(root)
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert cid in state.get("pending_rulings", {})                # the intent stays
    assert len(ruling_rows(root)) == rows + 1
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert result.get("reconciled") is True
    assert result["ruling"]["commit"] == landed
    assert git("rev-parse", "HEAD", cwd=root) == landed            # no second commit
    assert len(ruling_rows(root)) == rows + 1                      # no second row
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"
