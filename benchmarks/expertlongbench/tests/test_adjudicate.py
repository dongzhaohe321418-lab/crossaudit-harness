"""Unit tests for BLOCKER adjudication.

The confirmation rate is the number D142 waits on, so the way a finding becomes
"confirmed" has to be mechanical once the mapping step has answered. These tests script
the mapping and check the mechanics.
"""

from __future__ import annotations

import pytest

from adjudicate import (
    CONFIRMED,
    FALSE_POSITIVE,
    UNMAPPED,
    UNREADABLE,
    Adjudicator,
    Finding,
    parse_item_numbers,
    parse_report_findings,
)
from clear import Completion, ItemJudgement
from tasks import RubricItem, Task

TOY = Task(
    task_id="TOY",
    domain="toy",
    model_prompt="",
    items=tuple(
        RubricItem(key=f"k{i}", name=f"Item {i}", description=f"the {i}th thing")
        for i in range(1, 5)
    ),
)


class ScriptedClient:
    def __init__(self, answers):
        self.answers = list(answers)

    def complete(self, *, model, system, user, max_tokens=4096, temperature=0.0):
        return Completion(text=self.answers.pop(0), model=model, cost_usd=0.0001)


class BrokenClient:
    def complete(self, **_kwargs):
        raise RuntimeError("provider is down")


def judgements(**flags):
    """``k1=True`` means item 1 was mutually contained, i.e. CLEAR said it was right."""
    return [
        ItemJudgement(key=key, precision_hit=value, recall_hit=value)
        for key, value in flags.items()
    ]


BLOCKER = Finding(severity="BLOCKER", rule="CA-CONTENT-002", artifact="work/explanation.md",
                  observation="the atmosphere claim contradicts the recipe", round_no=1)


# --------------------------------------------------------------------------------------
# parsing the mapping answer
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [("1", [0]), ("2,4", [1, 3]), ("NONE", []), ("none", []), ("Items 1 and 3", [0, 2]),
     ("3, 3", [2]), ("", [])],
)
def test_parse_item_numbers(text, expected):
    assert parse_item_numbers(text, 4) == expected


def test_out_of_range_items_are_dropped_not_raised():
    """A model that invents item 9 of a 4-item rubric has failed to map the finding."""
    assert parse_item_numbers("9", 4) == []
    assert parse_item_numbers("2, 9", 4) == [1]


def test_none_wins_over_a_stray_number():
    assert parse_item_numbers("NONE (not item 2)", 4) == []


# --------------------------------------------------------------------------------------
# the verdict mechanics
# --------------------------------------------------------------------------------------


def test_a_finding_about_an_item_clear_scored_wrong_is_confirmed():
    adj = Adjudicator(ScriptedClient(["2"]), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=True, k2=False, k3=True, k4=True))
    assert decision.verdict == CONFIRMED
    assert decision.cited_items == ("k2",)
    assert decision.item_was_wrong == {"k2": True}


def test_a_finding_about_an_item_clear_scored_right_is_a_false_positive():
    adj = Adjudicator(ScriptedClient(["2"]), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=False, k2=True, k3=False, k4=False))
    assert decision.verdict == FALSE_POSITIVE
    assert decision.item_was_wrong == {"k2": False}


def test_any_cited_item_being_wrong_confirms_the_finding():
    adj = Adjudicator(ScriptedClient(["1,2"]), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=True, k2=False, k3=True, k4=True))
    assert decision.verdict == CONFIRMED
    assert decision.item_was_wrong == {"k1": False, "k2": True}


def test_all_cited_items_right_is_a_false_positive_even_when_others_are_wrong():
    adj = Adjudicator(ScriptedClient(["1"]), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=True, k2=False, k3=False, k4=False))
    assert decision.verdict == FALSE_POSITIVE


def test_a_finding_about_no_rubric_item_is_neither_confirmed_nor_a_false_positive():
    """Formatting and process objections are legitimate; the rubric just cannot rule on them.

    Scoring them either way would corrupt both rates.
    """
    adj = Adjudicator(ScriptedClient(["NONE"]), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=True, k2=True, k3=True, k4=True))
    assert decision.verdict == UNMAPPED
    assert decision.cited_items == ()


def test_accuracy_not_precision_alone_decides_wrongness():
    """CLEAR's 'accuracy' is mutual containment; a one-directional hit is not agreement."""
    adj = Adjudicator(ScriptedClient(["1"]), model="v:m")
    one_way = [ItemJudgement(key="k1", precision_hit=True, recall_hit=False)]
    decision = adj.adjudicate(TOY, BLOCKER, one_way)
    assert decision.verdict == CONFIRMED


def test_a_provider_failure_is_recorded_not_scored():
    adj = Adjudicator(BrokenClient(), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=True))
    assert decision.verdict == UNREADABLE
    assert "provider is down" in decision.note


def test_a_missing_clear_verdict_is_unreadable_not_a_guess():
    adj = Adjudicator(ScriptedClient(["3"]), model="v:m")
    decision = adj.adjudicate(TOY, BLOCKER, judgements(k1=True))
    assert decision.verdict == UNREADABLE
    assert "k3" in decision.note


# --------------------------------------------------------------------------------------
# reading findings out of a report
# --------------------------------------------------------------------------------------


REPORT = """\
# Audit report

## Findings

### [BLOCKER] CA-CONTENT-002 — work/explanation.md
The explanation states the atmosphere is oxidising, but the recipe reduces in 5% H2/Ar.

### [ADVISORY] CA-USABILITY-001 — work/explanation.md
Consider shorter bullets.

### [BLOCKER] DCL:complete — work/explanation.md
The deliverable ends mid-sentence.

## Evidence

| id | verified by a check |
"""


def test_parse_report_findings_reads_severity_rule_artifact_and_observation():
    findings = parse_report_findings(REPORT, round_no=2)
    assert [f.severity for f in findings] == ["BLOCKER", "ADVISORY", "BLOCKER"]
    assert [f.rule for f in findings] == ["CA-CONTENT-002", "CA-USABILITY-001", "DCL:complete"]
    assert all(f.artifact == "work/explanation.md" for f in findings)
    assert all(f.round_no == 2 for f in findings)
    assert "5% H2/Ar" in findings[0].observation


def test_parse_report_findings_tags_the_deterministic_tier():
    findings = parse_report_findings(REPORT)
    assert findings[0].tier == "model"
    assert findings[2].tier == "deterministic"


def test_the_observation_stops_at_the_next_report_section():
    findings = parse_report_findings(REPORT)
    assert "Evidence" not in findings[2].observation
    assert "verified by a check" not in findings[2].observation


def test_a_report_with_no_findings_yields_none():
    assert parse_report_findings("# Audit report\n\nNo findings.\n") == []
