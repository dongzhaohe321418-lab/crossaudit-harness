"""Pin the arithmetic of study 2's two primary numbers.

Both are computed from data a live run produces, so neither can be checked by re-reading
the run. They are checked here instead, over hand-built cases whose answers are countable:

* ``_revision_pair`` -- the within-instance pre-revision / post-revision difference that
  answers "does revision help or harm";
* ``_instrument_audit`` -- the auditor's recall against CLEAR's ground truth, which is what
  turns "the auditor said nothing" from a quiet success into a measured miss.
"""

from __future__ import annotations

import pytest

from clear import ItemJudgement, ScoredOutput, score_sample
from run import ArmResult, _instrument_audit, _revision_pair, rubric_constitution
from tasks import get_task

TASK = get_task("T03MaterialSEG")


def scored(sample_id: str, hits: list[bool]) -> ScoredOutput:
    """A ScoredOutput where item *i* is fully correct iff ``hits[i]``."""
    judgements = [
        ItemJudgement(item.key, precision_hit=hit, recall_hit=hit)
        for item, hit in zip(TASK.items, hits)
    ]
    return ScoredOutput(score=score_sample(sample_id, judgements, n_items=len(TASK.items)))


class StubAdjudicator:
    """Maps findings onto rubric items from a lookup table keyed by rule."""

    def __init__(self, table: dict[str, list[int]], fail: set[str] = frozenset()) -> None:
        self.table = table
        self.fail = fail

    def map_finding(self, task, finding):
        if finding.rule in self.fail:
            raise RuntimeError("provider exploded")
        return self.table.get(finding.rule, [])


# --------------------------------------------------------------------------------------
# _revision_pair
# --------------------------------------------------------------------------------------


def test_no_revision_is_none_not_zero():
    """A loop that passed at round one contributes no pair.

    Scoring it as a zero would be the study-1 mistake in a new place: it would put eleven
    non-revisions into the denominator of a question about revisions.
    """
    assert _revision_pair({1: scored("s#r1", [True] * 6)}) is None
    assert _revision_pair({}) is None


def test_revision_pair_reports_the_within_instance_difference():
    pre = scored("s#r1", [True, False, False, False, False, False])
    post = scored("s#r2", [True, True, True, False, False, False])
    pair = _revision_pair({1: pre, 2: post})

    assert pair["pre_round"] == 1 and pair["post_round"] == 2
    assert pair["pre_f1"] == pytest.approx(1 / 6)
    assert pair["post_f1"] == pytest.approx(3 / 6)
    assert pair["delta_f1"] == pytest.approx(2 / 6)
    assert pair["items_fixed"] == sorted(TASK.items[i].key for i in (1, 2))
    assert pair["items_broken"] == []


def test_revision_that_trades_one_item_for_another_is_visible_as_both():
    """The study-1 finding in miniature: a real fix that costs something elsewhere."""
    pre = scored("s#r1", [True, True, False, False, False, False])
    post = scored("s#r2", [False, True, True, False, False, False])
    pair = _revision_pair({1: pre, 2: post})

    assert pair["delta_f1"] == pytest.approx(0.0)
    assert pair["items_fixed"] == [TASK.items[2].key]
    assert pair["items_broken"] == [TASK.items[0].key]


def test_revision_pair_spans_first_to_last_round():
    rounds = {
        1: scored("s#r1", [False] * 6),
        2: scored("s#r2", [True] + [False] * 5),
        3: scored("s#r3", [True, True] + [False] * 4),
    }
    pair = _revision_pair(rounds)
    assert (pair["pre_round"], pair["post_round"], pair["n_revisions"]) == (1, 3, 2)
    assert pair["delta_f1"] == pytest.approx(2 / 6)


# --------------------------------------------------------------------------------------
# _instrument_audit
# --------------------------------------------------------------------------------------


def finding(rule: str, round_no: int = 1, severity: str = "BLOCKER") -> dict:
    return {
        "round": round_no,
        "severity": severity,
        "rule": rule,
        "artifact": "work/synthesis/explanation.md",
        "tier": "model",
        "state": "alleged",
        "observation": "something is wrong",
    }


def test_a_silent_auditor_scores_zero_recall_not_a_pass():
    """Six items wrong, nothing said. That is 0/6, and the study must be able to say so."""
    result = ArmResult(arm="B", sample_id="s", ok=True, findings=[])
    _mapped, recall = _instrument_audit(
        StubAdjudicator({}), TASK, result, {1: scored("s#r1", [False] * 6)}
    )
    assert len(recall) == 1
    assert recall[0]["n_findings"] == 0
    assert recall[0]["n_items_wrong"] == 6
    assert recall[0]["n_wrong_and_named"] == 0
    assert recall[0]["recall"] == 0.0


def test_recall_counts_only_the_wrong_items_the_auditor_named():
    rounds = {1: scored("s#r1", [True, False, False, False, True, True])}
    result = ArmResult(
        arm="B",
        sample_id="s",
        ok=True,
        findings=[finding("CA-RUBRIC-002"), finding("CA-RUBRIC-005")],
    )
    mapped, recall = _instrument_audit(
        StubAdjudicator({"CA-RUBRIC-002": [1], "CA-RUBRIC-005": [4]}), TASK, result, rounds
    )

    # item 2 was wrong and was named; item 5 was correct and was named anyway.
    assert recall[0]["n_items_wrong"] == 3
    assert recall[0]["n_items_named"] == 2
    assert recall[0]["n_wrong_and_named"] == 1
    assert recall[0]["n_named_but_correct"] == 1
    assert recall[0]["recall"] == pytest.approx(1 / 3)
    assert [m["verdict"] for m in mapped] == ["confirmed", "false_positive"]


def test_two_findings_about_one_item_are_one_named_item():
    """Recall is over items, not findings; naming the same item twice is not two hits."""
    rounds = {1: scored("s#r1", [False] * 6)}
    result = ArmResult(
        arm="B", sample_id="s", ok=True,
        findings=[finding("CA-RUBRIC-001"), finding("CA-CONTENT-001", severity="ADVISORY")],
    )
    _mapped, recall = _instrument_audit(
        StubAdjudicator({"CA-RUBRIC-001": [0], "CA-CONTENT-001": [0]}), TASK, result, rounds
    )
    assert recall[0]["n_findings"] == 2
    assert recall[0]["n_blockers"] == 1
    assert recall[0]["n_advisories"] == 1
    assert recall[0]["n_items_named"] == 1
    assert recall[0]["recall"] == pytest.approx(1 / 6)


def test_a_finding_about_no_rubric_item_is_unmapped_and_never_a_false_positive():
    rounds = {1: scored("s#r1", [False] * 6)}
    result = ArmResult(arm="B", sample_id="s", ok=True, findings=[finding("CA-USABILITY-001")])
    mapped, recall = _instrument_audit(StubAdjudicator({}), TASK, result, rounds)
    assert mapped[0]["verdict"] == "unmapped"
    assert recall[0]["n_items_named"] == 0


def test_an_adjudicator_failure_is_recorded_not_scored():
    rounds = {1: scored("s#r1", [False] * 6)}
    result = ArmResult(arm="B", sample_id="s", ok=True, findings=[finding("CA-RUBRIC-003")])
    mapped, _recall = _instrument_audit(
        StubAdjudicator({}, fail={"CA-RUBRIC-003"}), TASK, result, rounds
    )
    assert mapped[0]["verdict"] == "unreadable"
    assert "provider exploded" in mapped[0]["note"]


def test_findings_are_judged_against_the_round_they_were_raised_on():
    """A round-1 finding is right or wrong about the round-1 output, not the final one."""
    rounds = {
        1: scored("s#r1", [False] * 6),
        2: scored("s#r2", [True] * 6),
    }
    result = ArmResult(arm="B", sample_id="s", ok=True, findings=[finding("CA-RUBRIC-001", 1)])
    mapped, recall = _instrument_audit(
        StubAdjudicator({"CA-RUBRIC-001": [0]}), TASK, result, rounds
    )
    assert mapped[0]["verdict"] == "confirmed"
    assert recall[0]["recall"] == pytest.approx(1 / 6)
    assert recall[1]["n_items_wrong"] == 0
    assert recall[1]["recall"] is None


# --------------------------------------------------------------------------------------
# the rubric-derived constitution
# --------------------------------------------------------------------------------------


def test_rubric_constitution_is_a_pure_function_of_the_rubric():
    text = rubric_constitution(TASK)
    for index, item in enumerate(TASK.items, start=1):
        assert f"### CA-RUBRIC-{index:03d}" in text
        # transcribed, not paraphrased -- the description appears verbatim
        assert item.description in text
        assert item.name in text
    assert rubric_constitution(TASK) == text
