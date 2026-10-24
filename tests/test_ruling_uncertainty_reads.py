"""How uncertainty is read (review 2026-10-23 round 11; D176 rulings 36-38):
an unreadable HEAD proves nothing, "branch absent" means Git said so, and a
committed row for the current escalation that does not match completely is a
refusal, judged by its place in the committed log. Each test names the
mutation it catches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n, main
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_OK, IntegrityDenial
from crossaudit.gitio import git

from .test_resolve_commits_the_ruling import REASON, escalated  # noqa: F401
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


def _committed_lines(root: Path) -> list[str]:
    """The committed ruling lines (escalation rows excluded: D176 ruling 43)."""
    return [ln for ln in git("show", f"HEAD:{LOG}", cwd=root).split("\n")
            if ln.strip() and json.loads(ln).get("kind") != "escalation"]


# ------------------------------------------------ ruling 36
def test_a_landed_commit_with_unreadable_head_checks_is_uncertain(
        escalated, monkeypatch):
    """`git commit` really commits but reports failure, and both HEAD reads
    around it are unreadable. Mutation caught: comparing unreadable reads as
    equal (round 10's "" == "") -- the commit is marked "did not land", the
    log restored over a committed row, the intent cleared, and the next
    ruling commits a second row."""
    root, cid = escalated
    cfg = load()
    head = git("rev-parse", "HEAD", cwd=root)
    real_step, real_bounded = rulings._git_step, rulings._bounded
    stage = {"commit": False}

    def step(cfg_, deadline, *args):
        # The subcommand past the explicit identity's `-c` pairs.
        verb = rulings._verb(args)
        if verb == "add":
            stage["commit"] = True
        real_step(cfg_, deadline, *args)
        if verb == "commit":
            raise rulings._StepFailed("git commit failed: injected after landing")

    def bounded(cfg_, args, deadline):
        if stage["commit"] and args == ("rev-parse", "--verify", "-q", "HEAD"):
            return 128, "", "fatal: unable to read HEAD"
        return real_bounded(cfg_, args, deadline)
    monkeypatch.setattr(rulings, "_git_step", step)
    monkeypatch.setattr(rulings, "_bounded", bounded)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    assert denied.value.reason == (
        f"the ruling on cycle {cid} may have been committed to the ledger (git commit "
        f"failed: injected after landing); the cycle stays ESCALATED, and the next "
        f"ruling on this cycle recovers it")
    assert int(git("rev-list", "--count", f"{head}..HEAD", cwd=root)) == 1
    assert len(_committed_lines(root)) == 1
    assert len([ln for ln in (root / LOG).read_text().split("\n")
                if ln and json.loads(ln).get("kind") != "escalation"]) == 1
    assert cid in _state(root)["pending_rulings"]
    sha = git("rev-parse", "HEAD", cwd=root)
    assert rulings.rule(cfg, _store(root), cid, "close", "again")["reconciled"] is True
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


# ------------------------------------------------ ruling 37
def test_a_failing_show_ref_is_not_an_unborn_branch(escalated, monkeypatch):
    """During recovery `rev-parse HEAD` fails and `show-ref` fails with an
    error (not Git's quiet "ref missing"). Mutation caught: accepting any
    non-zero show-ref as "branch absent" -- the intent is cleared and a
    second ruling committed."""
    root, cid = escalated
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    real = rulings._bounded

    def broken_refs(cfg_, args, deadline):
        if args == ("rev-parse", "--verify", "-q", "HEAD"):
            return 128, "", ""
        if args[:2] == ("show-ref", "--verify"):
            return 128, "", "fatal: cannot read packed-refs\n"
        return real(cfg_, args, deadline)
    monkeypatch.setattr(rulings, "_bounded", broken_refs)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", "again")
    monkeypatch.undo()
    assert denied.value.reason == ("the committed rulings log could not be read "
                                   "(fatal: cannot read packed-refs); no ruling is "
                                   "made until it can be")
    assert cid in _state(root)["pending_rulings"]
    assert git("rev-parse", "HEAD", cwd=root) == sha


# ------------------------------------------------ ruling 38: log order
def _forge(root: Path, cid: str, **claims) -> str:
    """A hand-written, unsigned ruling row committed to the audit repository.
    ``claims`` adds what a prior real ruling would carry (D176 ruling 42:
    the first escalation's ``escalated_at`` and ``escalation_commit``)."""
    cycle = _state(root)["cycles"][cid]
    forged = {"cycle_id": cid, "action": "close", "reason": "forged", "by": "x",
              "t": 0, "at": "1970-01-01T00:00:00Z", "round": cycle["round"],
              "active_sha": cycle["active_sha"], "status_after": "BLOCKED",
              "escalation_reason": "", "intent": "f" * 32, **claims}
    (root / "cycles").mkdir(exist_ok=True)
    with open(root / LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n")
    git("add", "--", LOG, cwd=root)
    git("commit", "-q", "-m", "an unrelated commit", "--", LOG, cwd=root)
    return git("rev-parse", "HEAD", cwd=root)


def test_a_foreign_row_on_an_earlier_escalation_is_listed_and_does_not_block(
        escalated, monkeypatch, capsys):
    """A genuine ruling answers the first escalation; then a forged row that
    claims that same first escalation (its `escalated_at` and
    `escalation_commit`, the shape a prior real ruling has: D176 ruling 42)
    is committed; then the cycle stops again and a ruling's intent is left
    with no commit. The forged row stays in history: it names an escalation
    that is no longer current, so it is neither applied nor blocking, and
    status lists it as unverified (it carries no signature). The new
    ruling proceeds. Mutation caught: considering rows for an earlier
    escalation as candidates -- the forged row would block the cycle."""
    root, cid = escalated
    cfg = load()
    first = rulings.escalation_identity(cfg, cid)
    first_at = _state(root)["cycles"][cid].get("escalated_at")
    rulings.rule(cfg, _store(root), cid, "reopen", "the genuine ruling")
    forged_sha = _forge(root, cid, escalated_at=first_at, escalation_commit=first)
    _store(root).escalate(cid, "round budget spent again", kind="audit")
    with _store(root)._locked() as state:
        state.setdefault("pending_rulings", {})[cid] = {
            "action": "close", "nonce": "a" * 32, "reason_sha256": "", "by": "",
            "started_at": 0}
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    row = next(r for r in json.loads(capsys.readouterr().out)["cycles"]
               if r["cycle_id"] == cid)
    assert [f["commit"] for f in row.get("unverified_rulings", [])] == [forged_sha[:12]]
    assert "ruling_pending" not in row
    head = git("rev-parse", "HEAD", cwd=root)
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert result.get("intent_cleared") is True
    assert int(git("rev-list", "--count", f"{head}..HEAD", cwd=root)) == 1
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"
