"""Two paths round 14 found unsafe in the escalation rows (review 2026-10-23
round 14; D176 rulings 46-47): a post-commit confirmation that fails is
still an escalation, and the lineage walk has no silent cap. Each test names
the mutation it catches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n, main
from crossaudit.cli.main import _lineage_parent
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_OK, IntegrityDenial
from crossaudit.gitio import git, parent

from .conftest import BAD_RESULTS, GOOD_RESULTS, write_increment
from .test_resolve_commits_the_ruling import REASON, escalated, ruling_rows  # noqa: F401

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


def _escalation_rows(root: Path) -> list[dict]:
    rows = [json.loads(ln) for ln in (root / LOG).read_text().split("\n") if ln]
    return [r for r in rows if r.get("kind") == "escalation"]


# ------------------------------------------------ ruling 46
def test_a_failed_confirmation_after_the_commit_is_still_an_escalation(
        escalated, monkeypatch, capsys):
    """The escalation row's commit lands; the read that confirms it times out.
    No traceback: the cycle is ESCALATED with the row uncommitted in the
    state, status says so, a ruling refuses by name while the log cannot be
    read, and once it can, the next ruling recognises the row already at
    HEAD (no second escalation row) and proceeds. Mutations caught: the
    confirmation left outside the conversion (escalate() raises and the cycle
    stays OPEN); writing the escalation row again instead of recognising it."""
    root, cid = escalated
    cfg = load()
    rulings.rule(cfg, _store(root), cid, "reopen", "try once more")
    rows_before = len(_escalation_rows(root))
    head = git("rev-parse", "HEAD", cwd=root)
    real = rulings._bounded_bytes
    broken = {"on": True}

    def confirmation_times_out(cfg_, args, deadline):
        if broken["on"] and args == ("cat-file", "blob", f"HEAD:{LOG}"):
            raise rulings._StepFailed("git cat-file timed out after 5s")
        return real(cfg_, args, deadline)
    monkeypatch.setattr(rulings, "_bounded_bytes", confirmation_times_out)
    _store(root).escalate(cid, "build round budget spent (3)", kind="audit")
    state = _state(root)["cycles"][cid]
    assert state["status"] == "ESCALATED"
    assert state["escalation_commit"] == ""
    assert state["escalation_error"] == (
        "the committed escalation row could not be confirmed: git cat-file timed out "
        "after 5s")
    assert int(git("rev-list", "--count", f"{head}..HEAD", cwd=root)) == 1  # it landed
    capsys.readouterr()
    assert main.main(["status"]) == EXIT_OK
    assert ("escalation not committed (the committed escalation row could not be "
            "confirmed: git cat-file timed out after 5s)") in capsys.readouterr().out
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    # While the log cannot be read, the retry cannot recognise the row and the
    # ruling's own strict read refuses, by name.
    assert denied.value.reason == ("the committed rulings log could not be read (git "
                                   "cat-file timed out after 5s); no ruling is made "
                                   "until it can be")
    assert _state(root)["cycles"][cid]["escalation_commit"] == ""
    broken["on"] = False
    landed = git("rev-parse", "HEAD", cwd=root)
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert "reconciled" not in result
    assert len(_escalation_rows(root)) == rows_before + 1          # recognised, once
    assert result["ruling"]["escalation_commit"] == landed
    assert int(git("rev-list", "--count", f"{landed}..HEAD", cwd=root)) == 1
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


# ------------------------------------------------ ruling 47
def test_a_long_run_of_ledger_commits_does_not_hide_the_escalated_work(science, cfg):
    """A work commit, its escalation, then 70 more ledger-only commits (more
    than the old cap of 64), then a child work commit. Lineage walks to the
    escalated work and the pending-decision lock holds. Mutation caught: a
    capped walk that returns a ledger commit -- the child would open a fresh
    OPEN cycle past the lock."""
    sha = write_increment(science, BAD_RESULTS, "Bad.", "defective")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    store.record_verdict(cycle["cycle_id"], sha, "ESCALATE", "r1", cfg.max_rounds)
    filler = science / cfg.ledger_dir / "filler.txt"
    for n in range(70):
        filler.write_text(f"{n}\n")
        git("add", "--", str(filler.relative_to(science)), cwd=science)
        git("commit", "-q", "-m", f"ledger filler {n}", cwd=science)
    child = write_increment(science, GOOD_RESULTS, "Fixed.", "revision")
    assert _lineage_parent(cfg, child) == sha
    advanced = store.open_or_advance(cfg.science_repo, child, _lineage_parent(cfg, child))
    assert advanced.get("blocked_by_escalation") is True


# ------------------------------------------------ the row budget
@pytest.mark.parametrize("configured,expected", [("2", 2.0), ("500", 90.0), (None, 90.0)])
def test_a_ledger_rows_budget_is_the_smaller_of_90s_and_the_git_timeout(
        monkeypatch, configured, expected):
    """Ruling rows and escalation rows both take their deadline from
    `rulings.row_budget()`. Mutation caught: ignoring CROSSAUDIT_GIT_TIMEOUT
    (a repository bounded to 2 s would hold the lock 90 s for a row)."""
    if configured is None:
        monkeypatch.delenv("CROSSAUDIT_GIT_TIMEOUT", raising=False)
    else:
        monkeypatch.setenv("CROSSAUDIT_GIT_TIMEOUT", configured)
    assert rulings.row_budget() == expected
    import inspect
    for fn in (rulings.record_escalation, rulings._record, rulings.rule):
        assert "row_budget()" in inspect.getsource(fn), fn.__name__
