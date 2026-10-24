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


def test_a_ruling_commit_is_bounded_by_the_configured_git_timeout(escalated, monkeypatch):
    """Executable, not a source search (review round 15, D176 ruling 50): a
    pre-commit hook that sleeps 30 s and CROSSAUDIT_GIT_TIMEOUT=2. The
    ruling is refused within a few seconds, saying git commit timed out
    after 2s; the log is put back and the cycle stays ESCALATED. Mutation
    caught: `rule()`'s record path taking its deadline from COMMIT_TIMEOUT_S
    (90 s) instead of `row_budget()` -- the ruling waits out the hook (about
    30 s) and lands, failing the elapsed bound and the refusal."""
    import time

    from .test_resolve_commits_the_ruling import install_hook

    root, cid = escalated
    cfg = load()
    log_before = (root / LOG).read_bytes()
    head = git("rev-parse", "HEAD", cwd=root)
    install_hook(root, "#!/bin/sh\nexec sleep 30\n")
    monkeypatch.setenv("CROSSAUDIT_GIT_TIMEOUT", "2")
    began = time.monotonic()
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    elapsed = time.monotonic() - began
    assert elapsed < 10, elapsed
    assert "(git commit timed out after 2s)" in denied.value.reason
    assert (root / LOG).read_bytes() == log_before
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    (gitdir / "index.lock").unlink(missing_ok=True)   # left by the killed git
