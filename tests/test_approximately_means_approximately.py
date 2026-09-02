"""`approximately` must not be redefined as a number.

CA-TASK-001 read: *"A length stated approximately must be within 5%."* A user
writes *about 300 words*; 320 blocks. That is not strictness — it is the product
redefining the word the person chose, and the cheapest way to satisfy it is
mechanical text counted to the character: optimising for the auditor rather than
for the person who asked.

The rest of the rule is unchanged. Missing, substituted, extra and materially
noncompliant deliverables still block, and an explicit `exact` still blocks
precisely. An approximate length is not a BLOCKER *on its own*; a departure so
large that the deliverable is a different thing (40 or 3,000 words for "about
300") is materially noncompliant under the clause that already blocks that —
the rule does not contradict itself at the extremes, and it does not reward
under-delivery.

The interpretation reaches every init path, not only the model-drafted one:
both scaffold templates carry it, and the auditor's SYSTEM prompt states it in
one added sentence so an auditor reading a committed constitution applies the
same reading.
"""
from __future__ import annotations

import re

import pytest

from crossaudit.auditor import prompt as pm
from crossaudit.constitution import universal_task_rule
from crossaudit.scaffold import read as read_template

RULE = universal_task_rule()
CRITERION = " ".join(RULE.criterion.split())

#: The clauses that must survive untouched. The brief was to narrow one clause,
#: not to loosen the rule, so these are pinned verbatim.
SURVIVING = (
    "every objectively testable requirement in that task must be satisfied",
    "the requested deliverable count, file type or format, named subject, "
    "explicit inclusions or exclusions, and stated length",
    "A missing, substituted, extra, or materially noncompliant deliverable is "
    "a BLOCKER",
    "If no committed task is supplied, this rule has no additional effect",
)

#: The property phrase. A test on `\d+%` alone guards a spelling: the review's
#: mutation M6 ("within one twentieth", i.e. 5% in words) survived it. Pinning
#: the phrase is what makes M6 redden — verified by applying M6 to
#: constitution.py: this file then fails in `test_the_five_percent_band_is_gone`.
QUARTER = "more than a quarter of the stated length"


def _approximate_clause(text: str) -> str:
    approx = text[text.index("A length stated approximately"):]
    return approx[:approx.index("A missing,")]


def test_the_five_percent_band_is_gone():
    """The number that redefined the word — and its spelled-out forms.

    Mutation M6 from the review (replace "more than a quarter" with "within one
    twentieth") reddens here on the first assertion; M1 (restore "within 5%")
    reddens on the second and third.
    """
    assert QUARTER in CRITERION, (
        "the approximate-length tolerance is no longer a quarter OF THE STATED "
        "LENGTH; a narrower band, or one that does not say what it is a "
        "fraction of, is the old defect back in different words")
    assert "within 5%" not in CRITERION, (
        "`approximately` is bounded by a percentage again")
    assert not re.search(r"within \d+%", CRITERION), (
        "a different percentage is still redefining the user's word")
    assert not re.search(r"within (one|a|two|three) \w+", _approximate_clause(CRITERION)), (
        "a fraction spelled in words is still a band")


def test_an_approximate_length_does_not_block_on_its_own():
    """The incentive to count characters is removed, without the rule
    contradicting its own "materially noncompliant is a BLOCKER" clause."""
    approx = _approximate_clause(CRITERION)
    assert "not a BLOCKER on its own" in approx, (
        "an approximate length can block by itself again")
    assert "never" not in approx, (
        "an absolute `never` re-creates the contradiction with the materially-"
        "noncompliant clause, and rewards under-delivery")
    assert "materially noncompliant under the next sentence" in approx, (
        "the extreme case (a fraction or a multiple of what was asked) must be "
        "routed to the clause that already blocks it, not left to the model")
    assert "a fraction or a multiple of what was asked" in approx
    assert "ADVISORY" in approx, "an approximate departure has no way to be noted"
    assert "guide, not a threshold" in approx


def test_an_exact_length_still_blocks_precisely():
    """Only an explicit `exactly` gets exact treatment."""
    assert "A length stated as exact must match exactly" in CRITERION, (
        "the rule no longer holds an explicitly exact length to its number")


def test_the_rule_still_blocks():
    """Narrow one clause; do not soften the rule."""
    assert RULE.severity == "BLOCKER"
    assert RULE.id == "CA-TASK-001"


@pytest.mark.parametrize("clause", SURVIVING)
def test_every_other_clause_survives_verbatim(clause):
    assert clause in CRITERION, f"a clause was lost while narrowing one: {clause[:50]!r}"


def test_the_rule_says_why_in_the_words_a_person_would_use():
    """A rule a person can read is one they can tell is wrong.

    320 for "about 300" is 6.7%: a case the old 5% band actually blocked. (313,
    the example first used, was already inside the old band and illustrated
    nothing.)
    """
    assert "about 300 words" in CRITERION and "320" in CRITERION, (
        "the clause states a policy without showing what it means")
    assert "313" not in CRITERION, "the example must be one the old band blocked"


@pytest.mark.parametrize("template", ["GENERAL_AUDIT_RULES.md", "AUDIT_RULES.md"])
def test_template_projects_get_the_same_reading(template):
    """`crossaudit init`, the wizard's template mode and the console's starter
    project copy these files rather than rendering `universal_task_rule()`.
    Without this, a template project's auditor could still block 320."""
    text = " ".join(read_template(template).split())
    task = text[text.index("### CA-TASK-001"):]
    task = task[:task.index("### ", 4)]
    assert QUARTER in task, f"{template}: CA-TASK-001 does not carry the tolerance"
    assert "not a BLOCKER on its own" in task, template
    assert "guide, not a threshold" in task, template
    assert "materially noncompliant" in task, template


def test_the_auditor_prompt_states_the_same_reading():
    """The SYSTEM prompt tells every auditor, on every project, how to read an
    approximate length — the one path that reaches a constitution already
    committed. One sentence, additive; the rest of the bullet is pinned by
    test_loop_integrity."""
    system = " ".join(pm.SYSTEM.split())
    assert "CA-TASK-001" in system
    assert "more than a quarter of the stated length is ADVISORY" in system, (
        "the prompt's reading of an approximate departure is no longer ADVISORY")
    assert "guide, not a threshold" in system
    assert "a fraction or a multiple of what was asked" in system
