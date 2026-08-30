"""A decision already made is superseded, never erased (D34, D36).

The shipped screen says "Changing the rules never changes a decision already
made", and the independent honesty audit executed that claim rather than reading
it: one immutable SHA processed as round 1 BLOCKED; the constitution alone was
loosened and committed; the same SHA re-entered the same cycle as round 2 and
became PASSED, and the cycle's operative status changed BLOCKED -> PASSED. D8's
entire safety argument — that a person may freely edit their own constitution
because rule changes take effect only between cycles — rested on that claim.

D36 settles the shape, and it is two clauses because there were two defects:

  1. The standard moved INSIDE a cycle. `cmd_audit` re-read the constitution
     from the working tree every round, so a loosened file re-judged work the
     cycle had already decided on. The constitution is now pinned when the cycle
     opens.
  2. A reached verdict was ERASED, not superseded. `open_or_advance` reset a
     BLOCKED status to OPEN on the same SHA and the verdict recorder then
     assigned the cycle's status from the new round unconditionally. Clause 1
     closes the demonstrated route; clause 2 closes the class, and D7 says the
     class rather than the instance.

Both directions are tested, because a fix that only blocks is as wrong as one
that only permits: D8 exists to let somebody loosen a rule that was WRONG and
re-audit under it. What must not happen is the earlier decision ceasing to exist.
"""
from __future__ import annotations

import pytest

from crossaudit.controller import StateStore
from crossaudit.controller.state import BLOCKED, OPEN, PASSED
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import git


def _store(cfg) -> StateStore:
    return StateStore(cfg.root / cfg.state_dir / "state.json")


def _loosen(cfg, marker: str = "ADVISORY") -> str:
    """Weaken the constitution and commit it. Returns the new commit."""
    const = cfg.root / cfg.constitution
    const.write_text(const.read_text().replace("**BLOCKER.**", f"**{marker}.**"))
    git("add", "--", cfg.constitution, cwd=cfg.root)
    git("commit", "-q", "-m", "loosen the rules", cwd=cfg.root)
    return git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)


# ------------------------------------------------- the auditor's exact sequence
def test_a_blocked_decision_cannot_be_undone_by_loosening_the_rules(cfg):
    """The reported defect, reproduced against the controller that shipped it."""
    store = _store(cfg)
    sha = "a" * 40
    strict = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)

    cycle = store.open_or_advance(cfg.science_repo, sha, None,
                                  constitution_commit=strict)
    cid = cycle["cycle_id"]
    assert store.record_verdict(cid, sha, "BLOCK", "r1", max_rounds=3) == BLOCKED

    loosened = _loosen(cfg)
    assert loosened != strict, "the fixture did not actually change the rules"

    # Round 2 on the SAME commit is where the status used to flip.
    again = store.open_or_advance(cfg.science_repo, sha, None,
                                  constitution_commit=loosened)
    assert again.get("verdict_already_recorded") is True, (
        "the same commit was advanced past a decision it had already reached")
    assert again["status"] == BLOCKED, "the recorded decision did not survive"

    # And the cycle still says what it said.
    assert store.cycle(cid)["status"] == BLOCKED
    assert store.cycle(cid)["constitution_commit"] == strict, (
        "the cycle's standard moved after it had been opened")


def test_the_pin_means_a_later_round_is_judged_by_the_standard_it_started_under(cfg):
    """Clause 1, on its own: advancing to NEW work keeps the opening standard."""
    store = _store(cfg)
    strict = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    cycle = store.open_or_advance(cfg.science_repo, "a" * 40, None,
                                  constitution_commit=strict)
    cid = cycle["cycle_id"]
    store.record_verdict(cid, "a" * 40, "BLOCK", "r1", max_rounds=3)

    loosened = _loosen(cfg)
    # The generator revises: a NEW commit, same cycle. This is the loop's normal
    # path and it must keep working.
    advanced = store.continue_cycle(cid, cfg.science_repo, "b" * 40)
    assert advanced["round"] == 2
    assert store.cycle(cid)["constitution_commit"] == strict, (
        f"a mid-cycle rule change moved the standard to {loosened[:12]}")


def test_a_verdict_cannot_be_recorded_twice_for_one_round(cfg):
    """Clause 2 at the recorder: the record is appended to, never rewritten."""
    store = _store(cfg)
    sha = "a" * 40
    cycle = store.open_or_advance(cfg.science_repo, sha, None,
                                  constitution_commit="c" * 40)
    cid = cycle["cycle_id"]
    assert store.record_verdict(cid, sha, "BLOCK", "r1", max_rounds=3) == BLOCKED
    with pytest.raises(IntegrityDenial) as caught:
        store.record_verdict(cid, sha, "PASS", "r2", max_rounds=3)
    assert "already recorded a verdict" in str(caught.value)
    assert store.cycle(cid)["status"] == BLOCKED


# ------------------------------------------------------- the permitted direction
def test_a_legitimate_re_audit_produces_a_NEW_verdict_without_erasing_the_old(cfg):
    """D8's protected case: the rule was wrong, so loosen it and judge afresh.

    A fix that only blocks would be as wrong as one that only permits. New work
    under the new standard must reach a new decision, and the earlier decision
    must still be there, still saying what it said, still naming what it was
    judged against.
    """
    store = _store(cfg)
    strict = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    first = store.open_or_advance(cfg.science_repo, "a" * 40, None,
                                  constitution_commit=strict)
    cid = first["cycle_id"]
    store.record_verdict(cid, "a" * 40, "BLOCK", "r1", max_rounds=3)

    loosened = _loosen(cfg)
    # A new increment, judged under the standard now in force.
    second = store.open_or_advance(cfg.science_repo, "d" * 40, None,
                                   constitution_commit=loosened)
    assert second["cycle_id"] != cid, "a new increment must be a new cycle"
    assert store.record_verdict(second["cycle_id"], "d" * 40, "PASS", "r3",
                                max_rounds=3) == PASSED

    # The new decision exists...
    assert store.cycle(second["cycle_id"])["status"] == PASSED
    assert store.cycle(second["cycle_id"])["constitution_commit"] == loosened
    # ...and the old one was not touched by it.
    old = store.cycle(cid)
    assert old["status"] == BLOCKED
    assert old["constitution_commit"] == strict
    recorded = old["verdicts"]
    assert len(recorded) == 1
    assert recorded[0]["verdict"] == "BLOCK"
    assert recorded[0]["constitution_commit"] == strict, (
        "the record must name the standard the decision was made against")


def test_the_build_loops_revision_rounds_still_work(cfg):
    """BLOCKED -> revise -> re-audit within one cycle is the loop's whole design.

    It re-judges DIFFERENT work against the SAME standard, which is not revising
    a decision, so clause 2 must not touch it.
    """
    store = _store(cfg)
    cycle = store.open_or_advance(cfg.science_repo, "a" * 40, None,
                                  constitution_commit="c" * 40)
    cid = cycle["cycle_id"]
    assert store.record_verdict(cid, "a" * 40, "BLOCK", "r1", max_rounds=5) == BLOCKED
    advanced = store.continue_cycle(cid, cfg.science_repo, "b" * 40)
    assert advanced["round"] == 2 and advanced["status"] == OPEN
    assert store.record_verdict(cid, "b" * 40, "PASS", "r2", max_rounds=5) == PASSED
    # Superseded, not erased: both decisions are in the record.
    rows = store.cycle(cid)["verdicts"]
    assert [r["verdict"] for r in rows] == ["BLOCK", "PASS"]
    assert [r["sha"] for r in rows] == ["a" * 40, "b" * 40]


def test_an_interrupted_round_still_resumes(cfg):
    """A round that never reached a verdict is not a decision, so it resumes.

    This is the branch clause 2 must not swallow: the audit crashed, the provider
    timed out, the machine died. Incrementing there would spend the revision
    budget on transient failures.
    """
    store = _store(cfg)
    sha = "a" * 40
    cycle = store.open_or_advance(cfg.science_repo, sha, None,
                                  constitution_commit="c" * 40)
    resumed = store.open_or_advance(cfg.science_repo, sha, None,
                                    constitution_commit="c" * 40)
    assert resumed["round"] == cycle["round"] == 1
    assert not resumed.get("verdict_already_recorded")


def test_a_cycle_written_before_this_change_still_loads(cfg):
    """Old state has no pin and no verdicts list; it must not crash or lie.

    The protection begins with the first verdict recorded after the upgrade
    rather than being asserted retroactively about history we do not have.
    """
    import json
    store = _store(cfg)
    cycle = store.open_or_advance(cfg.science_repo, "a" * 40, None,
                                  constitution_commit="c" * 40)
    cid = cycle["cycle_id"]
    path = cfg.root / cfg.state_dir / "state.json"
    state = json.loads(path.read_text())
    state["cycles"][cid].pop("verdicts", None)
    state["cycles"][cid].pop("constitution_commit", None)
    state["cycles"][cid]["status"] = BLOCKED
    path.write_text(json.dumps(state))

    legacy = store.open_or_advance(cfg.science_repo, "a" * 40, None,
                                   constitution_commit="c" * 40)
    assert not legacy.get("verdict_already_recorded"), (
        "a pre-upgrade cycle must keep behaving as it did, not be retro-blocked")
    assert legacy["round"] == 2


# ------------------------------------------- D10: demonstrate the guards fail
def test_the_integrity_guards_go_red_when_the_old_behaviour_returns(cfg,
                                                                    monkeypatch):
    """Mutate the shipped functions back to what they did, and watch both fail.

    Mutation one: `_has_verdict_for` forgets, which restores the re-advance.
    Mutation two: `_recorded_verdict` forgets, which restores the overwrite.
    Checked against a live unmutated run in the same session (D10 as amended).
    """
    from crossaudit.controller import state as st

    store = _store(cfg)
    sha = "a" * 40
    honest = store.open_or_advance(cfg.science_repo, sha, None,
                                   constitution_commit="c" * 40)
    cid = honest["cycle_id"]
    store.record_verdict(cid, sha, "BLOCK", "r1", max_rounds=3)
    blocked = store.open_or_advance(cfg.science_repo, sha, None)
    assert blocked.get("verdict_already_recorded") is True, "baseline is not honest"

    monkeypatch.setattr(st, "_has_verdict_for", lambda cycle, sha: False)
    monkeypatch.setattr(st, "_recorded_verdict", lambda cycle, round_, sha: None)
    reopened = store.open_or_advance(cfg.science_repo, sha, None)
    assert not reopened.get("verdict_already_recorded"), (
        "the mutation did not take; this demonstration proves nothing")
    assert reopened["status"] == OPEN
    assert store.record_verdict(cid, sha, "PASS", "r2", max_rounds=3) == PASSED
    assert store.cycle(cid)["status"] == PASSED, (
        "the mutation did not reproduce the erasure; the guard proves nothing")


# ------------- the fact the shipped copy rests on, guarded at the point of use
def test_a_later_round_audits_the_pinned_constitution_not_the_working_tree(
        cfg, monkeypatch, tmp_path):
    """The sentence is only true because the standard is pinned. Guard the USE.

    Raised by the design engineer while reviewing the Chinese: the copy's claim
    holds only while the pinned constitution and the one a later round actually
    applies cannot diverge. The tests above assert the cycle STORES its pin;
    this one asserts `cmd_audit` USES it — which is the fact the sentence
    depends on, in both languages.
    """
    import argparse

    from crossaudit.cli import main as _main
    from tests.conftest import write_increment

    strict_text = (cfg.root / cfg.constitution).read_text()
    strict = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)

    sha = write_increment(cfg.root, {"quantities": []}, "s", "increment one")
    store = _store(cfg)
    opened = store.open_or_advance(cfg.science_repo, sha, None,
                                   constitution_commit=strict)
    store.record_verdict(opened["cycle_id"], sha, "BLOCK", "r1", max_rounds=5)

    loosened = _loosen(cfg)
    assert loosened != strict
    assert (cfg.root / cfg.constitution).read_text() != strict_text, (
        "the working tree did not actually change")

    # The generator revises: a new commit continuing the same cycle.
    revised = write_increment(cfg.root, {"quantities": []}, "s2", "increment two")
    seen: dict = {}

    def capture(**kwargs):
        seen.update(kwargs)
        raise SystemExit(0)          # stop before any provider call

    monkeypatch.setattr(_main, "run_audit", capture)
    monkeypatch.chdir(cfg.root)
    args = argparse.Namespace(sha=revised, scope=None, json=False, retention=None,
                              allow_custom_endpoint=False, on_step=None,
                              continue_cycle=opened["cycle_id"], offline=True)
    with pytest.raises(SystemExit):
        _main.cmd_audit(args)

    assert seen, "cmd_audit never reached the audit"
    assert seen["constitution_commit"] == strict, (
        f"a later round cited {seen['constitution_commit'][:12]}, not the "
        f"standard the cycle was opened under")
    assert seen["constitution"] == strict_text, (
        "a later round applied the loosened bytes from the working tree")
