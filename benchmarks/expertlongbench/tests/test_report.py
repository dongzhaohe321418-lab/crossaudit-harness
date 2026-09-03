"""Tests for the report.

The load-bearing property here is not arithmetic but honesty: a run where the audit loop
loses must say so in its first sentence, and a rate resting on four findings must not be
presented as if it settled anything.
"""

from __future__ import annotations

import pytest

from report import (
    compare,
    headline,
    render,
    significance_sentence,
    summarise_arm,
    summarise_blockers,
)


def instance(sample_id: str, a_f1: float | None, b_f1: float | None, *,
             adjudications=None, a_cost=0.01, b_cost=0.05):
    def arm(f1, cost, rounds):
        if f1 is None:
            return {"ok": False, "score": None, "cost_usd": cost, "wall_s": 1.0,
                    "score_cost_usd": 0.0, "rounds": 0}
        return {
            "ok": True,
            "cost_usd": cost,
            "wall_s": 1.0,
            "rounds": rounds,
            "score_cost_usd": 0.002,
            "score": {"sample_id": sample_id, "n_items": 6, "f1": f1,
                      "precision": f1, "recall": f1, "accuracy": f1, "per_item": {}},
        }

    arms = {"A": arm(a_f1, a_cost, 1), "B": arm(b_f1, b_cost, 2)}
    if adjudications is not None:
        arms["B"]["adjudications"] = adjudications
    return {"sample_id": sample_id, "arms": arms}


# --------------------------------------------------------------------------------------
# the headline must not bury a loss
# --------------------------------------------------------------------------------------


def test_a_win_for_the_loop_is_stated_as_a_win():
    instances = [instance(f"s{i}", 0.20, 0.30) for i in range(6)]
    text = headline(compare(instances), None, None)
    assert "+10.0 F1 higher" in text
    assert "worse" not in text


def test_a_loss_for_the_loop_says_worse_in_the_headline():
    """A negative result is the most valuable thing this study can produce.

    It must be legible in the first sentence, not softened into a delta a reader has to
    work out the sign of.
    """
    instances = [instance(f"s{i}", 0.30, 0.20) for i in range(6)]
    text = headline(compare(instances), None, None)
    assert "worse" in text
    assert "-10.0" in text


def test_a_tie_is_stated_as_a_tie():
    instances = [instance(f"s{i}", 0.25, 0.25) for i in range(4)]
    assert "identically" in headline(compare(instances), None, None)


def test_the_headline_always_carries_the_sample_size():
    instances = [instance(f"s{i}", 0.2, 0.3) for i in range(7)]
    assert "n = 7" in headline(compare(instances), None, None)


def test_no_paired_instances_is_reported_as_no_result():
    assert "No paired result" in headline(None, None, None)


# --------------------------------------------------------------------------------------
# pairing
# --------------------------------------------------------------------------------------


def test_only_instances_scored_in_both_arms_are_paired():
    instances = [
        instance("a", 0.2, 0.3),
        instance("b", 0.4, None),   # arm B failed
        instance("c", None, 0.5),   # arm A failed
        instance("d", 0.1, 0.2),
    ]
    comparison = compare(instances)
    assert comparison.n_pairs == 2
    assert comparison.mean_a == pytest.approx(0.15)
    assert comparison.mean_b == pytest.approx(0.25)


def test_wins_and_ties_are_counted():
    instances = [instance("a", 0.2, 0.3), instance("b", 0.5, 0.1), instance("c", 0.4, 0.4)]
    comparison = compare(instances)
    assert (comparison.wins_b, comparison.wins_a, comparison.ties) == (1, 1, 1)


def test_arm_summary_counts_failures_separately_from_scores():
    instances = [instance("a", 0.2, 0.3), instance("b", 0.4, None)]
    arm_b = summarise_arm(instances, "B")
    assert arm_b.n_attempted == 2
    assert arm_b.n_scored == 1
    assert arm_b.failures == 1
    assert arm_b.mean_f1 == pytest.approx(0.3)  # the failure is not averaged in as a zero


# --------------------------------------------------------------------------------------
# refusing to overclaim
# --------------------------------------------------------------------------------------


def test_below_six_pairs_the_report_says_the_p_value_settles_nothing():
    instances = [instance(f"s{i}", 0.1, 0.9) for i in range(4)]
    sentence = significance_sentence(compare(instances))
    assert "settles nothing" in sentence
    assert "pilot" in sentence


def test_a_non_significant_result_is_not_reported_as_no_effect():
    instances = [instance("a", 0.2, 0.3), instance("b", 0.5, 0.1), instance("c", 0.4, 0.45),
                 instance("d", 0.3, 0.2), instance("e", 0.1, 0.15), instance("f", 0.6, 0.5)]
    sentence = significance_sentence(compare(instances))
    assert "not significant" in sentence
    assert "as with no effect at all" in sentence


def test_a_significant_result_is_still_hedged_on_a_small_sample():
    instances = [instance(f"s{i}", 0.1, 0.9) for i in range(8)]
    sentence = significance_sentence(compare(instances))
    assert "evidence, not a settled effect" in sentence


# --------------------------------------------------------------------------------------
# the confirmation rate
# --------------------------------------------------------------------------------------


def test_unmapped_findings_are_excluded_from_both_rates():
    """A complaint about a missing file is not a false positive; the rubric is just silent."""
    adjudications = [
        {"rule": "CA-CONTENT-002", "verdict": "confirmed"},
        {"rule": "CA-CONTENT-002", "verdict": "confirmed"},
        {"rule": "CA-CONTENT-002", "verdict": "false_positive"},
        {"rule": "CA-TASK-001", "verdict": "unmapped"},
        {"rule": "CA-TASK-001", "verdict": "unmapped"},
    ]
    summary = summarise_blockers([instance("a", 0.2, 0.3, adjudications=adjudications)])
    assert summary.total_blockers == 5
    assert summary.rubric_relevant == 3
    assert summary.unmapped == 2
    assert summary.confirmation_rate.point == pytest.approx(2 / 3)
    assert summary.confirmation_rate.total == 3
    assert summary.false_positive_rate.point == pytest.approx(1 / 3)


def test_the_two_rates_sum_to_one_over_the_rubric_relevant_findings():
    adjudications = [{"rule": "R", "verdict": v} for v in
                     ["confirmed", "confirmed", "false_positive", "unmapped"]]
    summary = summarise_blockers([instance("a", 0.2, 0.3, adjudications=adjudications)])
    assert summary.confirmation_rate.point + summary.false_positive_rate.point == pytest.approx(1.0)


def test_no_blockers_at_all_is_reported_rather_than_shown_as_zero_percent():
    summary = summarise_blockers([instance("a", 0.2, 0.3, adjudications=[])])
    assert summary.total_blockers == 0
    text = render({"plan": {"task": "T", "n": 1},
                   "instances": [instance("a", 0.2, 0.3, adjudications=[])]})
    assert "raised no BLOCKER" in text
    assert "cannot inform" in text


def test_findings_are_broken_down_by_rule():
    adjudications = [
        {"rule": "CA-CONTENT-002", "verdict": "confirmed"},
        {"rule": "CA-TASK-001", "verdict": "false_positive"},
    ]
    summary = summarise_blockers([instance("a", 0.2, 0.3, adjudications=adjudications)])
    assert summary.by_rule["CA-CONTENT-002"]["confirmed"] == 1
    assert summary.by_rule["CA-TASK-001"]["false_positive"] == 1


def test_unreadable_adjudications_are_surfaced_not_hidden():
    adjudications = [{"rule": "R", "verdict": "unreadable"}]
    summary = summarise_blockers([instance("a", 0.2, 0.3, adjudications=adjudications)])
    assert summary.unreadable == 1
    assert summary.rubric_relevant == 0


# --------------------------------------------------------------------------------------
# the whole document
# --------------------------------------------------------------------------------------


def test_render_carries_sample_size_models_and_cost():
    payload = {
        "plan": {
            "task": "T03MaterialSEG",
            "n": 3,
            "seed": 7,
            "corpus_sha256": "abc123def4567890",
            "models": {"generator": "anthropic:m", "auditor": "openai:j", "judge": "openai:j"},
            "settings": {"max_rounds": 3},
        },
        "instances": [
            instance("a", 0.2, 0.3, adjudications=[{"rule": "R", "verdict": "confirmed"}]),
            instance("b", 0.1, 0.4),
            instance("c", 0.3, 0.2),
        ],
    }
    text = render(payload)
    assert "n = 3" in text
    assert "anthropic:m" in text
    assert "openai:j" in text
    assert "What it cost" in text
    assert "5.0×" in text  # arm B 0.05 vs arm A 0.01 per instance
    assert "rest on **1 findings**" in text
    assert "far too few to set a policy default" in text


def test_a_losing_run_renders_the_loss_first():
    payload = {"plan": {"task": "T", "n": 6},
               "instances": [instance(f"s{i}", 0.5, 0.2) for i in range(6)]}
    text = render(payload)
    first_paragraph = text.split("\n\n")[1]
    assert "worse" in first_paragraph
