"""Unit tests for the CLEAR reimplementation.

Every case here is one whose answer is *arithmetic*, not a model's opinion: the judge is a
scripted stub, so the expected F1 can be computed by hand from the paper's definitions
(S-4.1). If one of these fails, the scorer has drifted from the paper.
"""

from __future__ import annotations

import math

import pytest

from clear import (
    JUDGE_USER,
    NA,
    ClearScorer,
    Completion,
    ItemJudgement,
    NAPolicy,
    ScoreCost,
    aggregate,
    is_na,
    parse_mapper_json,
    parse_yes_no,
    score_sample,
)
from tasks import RubricItem, Task, get_task

# --------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------

TOY = Task(
    task_id="TOY",
    domain="toy",
    model_prompt="do the toy task",
    items=tuple(
        RubricItem(key=f"k{i}", name=f"Item {i}", description=f"the {i}th thing")
        for i in range(1, 5)
    ),
)


class ScriptedClient:
    """A stub :class:`clear.ModelClient` that replays fixed answers and records calls."""

    def __init__(self, mapper_json: str, verdicts: list[str]):
        self.mapper_json = mapper_json
        self.verdicts = list(verdicts)
        self.calls: list[dict] = []

    def complete(self, *, model, system, user, max_tokens=4096, temperature=0.0):
        self.calls.append({"model": model, "system": system, "user": user})
        if "Model Answer:" in user:
            if not self.verdicts:
                raise AssertionError("judge called more times than the script allows")
            text = self.verdicts.pop(0)
        else:
            text = self.mapper_json
        return Completion(
            text=text, model=model, input_tokens=10, output_tokens=2, cost_usd=0.001, latency_s=0.5
        )

    @property
    def judge_calls(self):
        return [c for c in self.calls if "Model Answer:" in c["user"]]


def judgements(pattern: list[tuple[bool, bool]]) -> list[ItemJudgement]:
    return [
        ItemJudgement(key=f"k{i}", precision_hit=p, recall_hit=r)
        for i, (p, r) in enumerate(pattern, start=1)
    ]


# --------------------------------------------------------------------------------------
# the arithmetic (S-4.1)
# --------------------------------------------------------------------------------------


def test_all_items_hit_scores_one():
    score = score_sample("s", judgements([(True, True)] * 4))
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.accuracy == 1.0
    assert score.f1 == 1.0


def test_nothing_hit_scores_zero_and_f1_is_not_nan():
    score = score_sample("s", judgements([(False, False)] * 4))
    assert (score.precision, score.recall, score.accuracy) == (0.0, 0.0, 0.0)
    assert score.f1 == 0.0
    assert not math.isnan(score.f1)


def test_precision_and_recall_are_independent_directions():
    # 2 of 4 precision hits, 4 of 4 recall hits -> P=0.5, R=1.0, F1 = 2*.5*1/1.5
    score = score_sample("s", judgements([(True, True), (True, True), (False, True), (False, True)]))
    assert score.precision == 0.5
    assert score.recall == 1.0
    assert score.f1 == pytest.approx(2 * 0.5 * 1.0 / 1.5)
    assert score.f1 == pytest.approx(0.6666666666666666)


def test_accuracy_is_mutual_containment_only():
    # one item hits both, one hits precision only, one hits recall only, one hits neither
    score = score_sample(
        "s", judgements([(True, True), (True, False), (False, True), (False, False)])
    )
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.accuracy == 0.25  # only the first item is mutual
    assert score.f1 == 0.5


def test_denominator_is_the_whole_checklist_not_the_judged_subset():
    """S-4.1's denominator is 'the fraction of checklist items', unqualified.

    Scoring 2 hits out of a 4-item rubric must be 0.5, never 1.0 -- a scorer that silently
    drops unjudged items would inflate every number in the study.
    """
    with pytest.raises(ValueError, match="every rubric item must be judged"):
        score_sample("s", judgements([(True, True), (True, True)]), n_items=4)


def test_task_score_is_the_mean_of_sample_f1s_not_the_f1_of_pooled_counts():
    """S-4.1: 'we obtain the task-level performance by averaging the sample-level metrics'.

    These two samples are chosen so the two aggregations differ, which is the only way to
    prove which one is implemented.
    """
    perfect = score_sample("a", judgements([(True, True)] * 4))  # F1 = 1.0
    lopsided = score_sample(  # P=1.0, R=0.25 -> F1 = 2*1*.25/1.25 = 0.4
        "b", judgements([(True, True), (True, False), (True, False), (True, False)])
    )
    assert lopsided.f1 == pytest.approx(0.4)

    task = aggregate("TOY", [perfect, lopsided])
    assert task.mean_f1 == pytest.approx((1.0 + 0.4) / 2)  # 0.7 -- macro over samples

    # The pooled alternative would be P = 8/8 = 1.0, R = 5/8 = 0.625,
    # F1 = 2*1*0.625/1.625 = 0.769..., which is NOT what we report.
    pooled_p, pooled_r = 8 / 8, 5 / 8
    pooled_f1 = 2 * pooled_p * pooled_r / (pooled_p + pooled_r)
    assert task.mean_f1 != pytest.approx(pooled_f1)
    assert task.mean_precision == pytest.approx(1.0)
    assert task.mean_recall == pytest.approx((1.0 + 0.25) / 2)


def test_aggregate_refuses_an_empty_study():
    with pytest.raises(ValueError):
        aggregate("TOY", [])


# --------------------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Yes", True),
        ("No", False),
        ("yes", True),
        (" NO ", False),
        ("Correct: Yes", True),
        ("**No**", False),
    ],
)
def test_parse_yes_no(text, expected):
    assert parse_yes_no(text) is expected


def test_parse_yes_no_refuses_to_guess():
    """A judgement we cannot read must fail loudly, never default.

    A silent default would push every unreadable verdict in one direction and bias the
    whole study by exactly the rate at which the judge misbehaves.
    """
    with pytest.raises(ValueError, match="did not answer"):
        parse_yes_no("I would rather not say.")


def test_parse_mapper_json_handles_fences_and_missing_keys():
    text = '```json\n{"item_1": "alpha", "item_3": ["b", "c"]}\n```'
    mapped = parse_mapper_json(text, TOY.items)
    assert mapped["k1"] == "alpha"
    assert mapped["k2"] == NA          # absent -> the output said nothing about it
    assert mapped["k3"] == '["b", "c"]'  # non-string values are serialised, not dropped
    assert mapped["k4"] == NA


def test_parse_mapper_json_accepts_rubric_keys_as_well_as_item_numbers():
    mapped = parse_mapper_json('{"k1": "alpha", "Item 2": "beta"}', TOY.items)
    assert mapped["k1"] == "alpha"
    assert mapped["k2"] == "beta"


def test_parse_mapper_json_rejects_non_json():
    with pytest.raises(ValueError, match="no JSON object"):
        parse_mapper_json("I could not do that.", TOY.items)


def test_empty_string_counts_as_na():
    assert parse_mapper_json('{"item_1": "   "}', TOY.items)["k1"] == NA


@pytest.mark.parametrize("value", ["N/A", "n/a", " NA ", "", None])
def test_is_na(value):
    assert is_na(value)


def test_is_na_is_not_fooled_by_content():
    assert not is_na("N/A was not applicable because ...")


# --------------------------------------------------------------------------------------
# the judge wiring -- the direction of containment is the easiest thing to invert silently
# --------------------------------------------------------------------------------------


def test_recall_puts_the_response_in_the_model_answer_slot():
    """S-C.2 / Table 44: the slot named 'Model Answer' is the *container*.

    The caption calls this configuration 'for recall measurement', so recall must ask
    'does the response contain the reference'.
    """
    client = ScriptedClient('{"item_1": "RESPONSE_TEXT"}', ["Yes", "Yes"])
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j")
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])

    scorer.score(one_item, "s", "output", {"k1": "REFERENCE_TEXT"})

    recall_call, precision_call = client.judge_calls  # recall is issued first
    assert "Model Answer: Item 1: RESPONSE_TEXT" in recall_call["user"]
    assert "Reference Answer: Item 1: REFERENCE_TEXT" in recall_call["user"]

    # precision reverses the roles (S-C.2: "By reversing the roles ...")
    assert "Model Answer: Item 1: REFERENCE_TEXT" in precision_call["user"]
    assert "Reference Answer: Item 1: RESPONSE_TEXT" in precision_call["user"]


def test_the_two_directions_are_scored_into_the_right_metrics():
    """Recall Yes / precision No must give R=1, P=0 -- not the other way round."""
    client = ScriptedClient('{"item_1": "long response"}', ["Yes", "No"])
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j")
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])

    result = scorer.score(one_item, "s", "output", {"k1": "short ref"})
    assert result.score.recall == 1.0
    assert result.score.precision == 0.0
    assert result.score.f1 == 0.0


def test_judge_and_mapper_use_their_own_models():
    client = ScriptedClient('{"item_1": "x"}', ["Yes", "Yes"])
    scorer = ClearScorer(client, mapper_model="mapper:M", judge_model="judge:J")
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])
    scorer.score(one_item, "s", "output", {"k1": "y"})

    models = [c["model"] for c in client.calls]
    assert models == ["mapper:M", "judge:J", "judge:J"]


def test_judge_prompt_is_the_papers_two_slot_template():
    filled = JUDGE_USER.format(model_answer="A", reference_answer="B")
    assert filled == "Model Answer: A\n\nReference Answer: B\n\nCorrect:"


# --------------------------------------------------------------------------------------
# end to end over a whole rubric
# --------------------------------------------------------------------------------------


def test_end_to_end_f1_is_exactly_the_hand_computed_value():
    """4 items; scripted verdicts give 2/4 precision and 3/4 recall.

    Verdicts are consumed in (recall, precision) order per item.
    """
    verdicts = [
        "Yes", "Yes",   # item 1: recall hit, precision hit
        "Yes", "Yes",   # item 2: recall hit, precision hit
        "Yes", "No",    # item 3: recall hit, precision miss
        "No", "No",     # item 4: both miss
    ]
    client = ScriptedClient(
        '{"item_1": "a", "item_2": "b", "item_3": "c", "item_4": "N/A"}', verdicts
    )
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j")
    reference = {f"k{i}": f"ref{i}" for i in range(1, 5)}

    result = scorer.score(TOY, "sample-1", "some output", reference)

    assert result.score.n_items == 4
    assert result.score.precision == 0.5          # 2/4
    assert result.score.recall == 0.75            # 3/4
    assert result.score.accuracy == 0.5           # items 1 and 2 are mutual
    assert result.score.f1 == pytest.approx(2 * 0.5 * 0.75 / 1.25)
    assert result.score.f1 == pytest.approx(0.6)


def test_cost_is_accumulated_over_every_call():
    client = ScriptedClient('{"item_1": "a", "item_2": "b", "item_3": "c", "item_4": "d"}',
                            ["Yes"] * 8)
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j")
    result = scorer.score(TOY, "s", "out", {f"k{i}": f"r{i}" for i in range(1, 5)})

    # 1 mapper call + 2 judge calls per item over 4 items
    assert result.cost.calls == 9
    assert result.cost.cost_usd == pytest.approx(9 * 0.001)
    assert result.cost.input_tokens == 90


def test_an_empty_output_is_all_na_and_costs_no_mapper_call():
    client = ScriptedClient("{}", ["No"] * 8)
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j")
    result = scorer.score(TOY, "s", "   ", {f"k{i}": f"r{i}" for i in range(1, 5)})

    assert all(v == NA for v in result.mapped.values())
    assert result.cost.calls == 8  # judges only; the mapper was never asked
    assert result.score.f1 == 0.0


def test_a_rubric_that_has_drifted_from_the_dataset_fails_loudly():
    client = ScriptedClient('{"item_1": "a"}', ["Yes", "Yes"])
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j")
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])
    with pytest.raises(KeyError, match="rubric in"):
        scorer.score(one_item, "s", "out", {"a-different-key": "x"})


# --------------------------------------------------------------------------------------
# the N/A policy
# --------------------------------------------------------------------------------------


def test_literal_policy_sends_na_items_to_the_judge():
    """The default reading of S-4.1: no carve-out, every item is judged."""
    client = ScriptedClient('{"item_1": "N/A"}', ["No", "No"])
    scorer = ClearScorer(client, mapper_model="v:m", judge_model="v:j", na_policy=NAPolicy.LITERAL)
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])
    result = scorer.score(one_item, "s", "out", {"k1": "N/A"})

    assert len(client.judge_calls) == 2
    assert result.score.f1 == 0.0


def test_exact_match_policy_short_circuits_both_na_without_a_model_call():
    client = ScriptedClient('{"item_1": "N/A"}', [])
    scorer = ClearScorer(
        client, mapper_model="v:m", judge_model="v:j", na_policy=NAPolicy.EXACT_MATCH
    )
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])
    result = scorer.score(one_item, "s", "out", {"k1": "N/A"})

    assert client.judge_calls == []
    assert result.score.f1 == 1.0


def test_exact_match_policy_still_judges_a_mixed_item():
    client = ScriptedClient('{"item_1": "the model said something"}', ["No", "No"])
    scorer = ClearScorer(
        client, mapper_model="v:m", judge_model="v:j", na_policy=NAPolicy.EXACT_MATCH
    )
    one_item = Task(task_id="ONE", domain="toy", model_prompt="", items=TOY.items[:1])
    scorer.score(one_item, "s", "out", {"k1": "N/A"})
    assert len(client.judge_calls) == 2


# --------------------------------------------------------------------------------------
# the transcribed rubric must match the pinned dataset
# --------------------------------------------------------------------------------------


def test_t03_rubric_matches_the_pinned_manifest():
    """tasks.py is transcribed from the paper; manifest.json is derived from the data.

    They must agree, or the scorer is scoring against a rubric the data does not carry.
    """
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).resolve().parents[1] / "manifest.json").read_text())
    pinned = set(manifest["tasks"]["T03MaterialSEG"]["checklist_items"])
    assert set(get_task("T03MaterialSEG").keys) == pinned


def test_score_cost_starts_empty():
    cost = ScoreCost()
    assert (cost.calls, cost.cost_usd, cost.input_tokens) == (0, 0.0, 0)
