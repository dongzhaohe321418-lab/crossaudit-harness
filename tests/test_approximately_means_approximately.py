"""`approximately` must not be redefined as a number.

CA-TASK-001 read: *"A length stated approximately must be within 5%."* A user
writes *about 300 words*; 313 blocks. That is not strictness — it is the product
redefining the word the person chose, and the cheapest way to satisfy it is
mechanical text counted to the character: optimising for the auditor rather than
for the person who asked.

The rest of the rule is unchanged. Missing, substituted, extra and materially
noncompliant deliverables still block, and an explicit `exact` still blocks
precisely.
"""
from __future__ import annotations

import re

import pytest

from crossaudit.constitution import universal_task_rule

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


def test_the_five_percent_band_is_gone():
    """The number that redefined the word."""
    assert "within 5%" not in CRITERION, (
        "`approximately` is bounded by a percentage again")
    assert not re.search(r"within \d+%", CRITERION), (
        "a different percentage is still redefining the user's word")


def test_an_approximate_length_can_never_block():
    """This is the whole point: the incentive to count characters is removed."""
    assert "never raise it as a BLOCKER" in CRITERION, (
        "an approximate length can block again")
    approx = CRITERION[CRITERION.index("A length stated approximately"):]
    approx = approx[:approx.index("A missing,")]
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
    """A rule a person can read is one they can tell is wrong."""
    assert "about 300 words" in CRITERION and "313" in CRITERION, (
        "the clause states a policy without showing what it means")
