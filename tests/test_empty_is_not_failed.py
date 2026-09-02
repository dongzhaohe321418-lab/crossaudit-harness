"""An empty scope is neither a pass nor a failure.

A brand-new user ran `init` then `check` and was told **BLOCKED, 2 hard
failures**, in vocabulary (`DCL:schema`, `audited scope`) they had no way to
read — before they had written anything. Absence and failure collapsed into one
value, which is the same defect the receipt path carried: there a corrupt
evidence ledger became indistinguishable from "no tools used".

The third state must never read as a pass and must never admit anything. That
guard matters more than the friendlier sentence, and it is asserted first here.
"""
from __future__ import annotations

import pytest

from crossaudit.cli import main as cli_main
from crossaudit.dcl.framework import (NOTHING_TO_AUDIT, run_checks,
                                      scope_started)

SCAFFOLD = {"experiments/README.md": b"# put your work here\n"}
STARTED_NO_SCHEMA = {"experiments/demo/notes.txt": b"working\n"}
STARTED_WITH_RESULTS = {"experiments/demo/results.json": b"{}"}


# ------------------------------------------------ the weakening guard, first
@pytest.mark.parametrize("files", [{}, SCAFFOLD])
def test_an_empty_scope_cannot_produce_a_passing_verdict(files):
    """The thing to guard hardest: an empty directory is not a clean verdict."""
    result = run_checks(files, ["schema"]).as_dict()
    assert result["verdict"] != "PASS", (
        "an empty scope reached PASS; an empty directory has become a route to "
        "a clean verdict, which is worse than the alarming message it replaced")
    assert result["verdict"] == NOTHING_TO_AUDIT
    assert result["scope_started"] is False


def test_an_unstarted_scope_cannot_reach_pass_through_the_audit_either():
    """`check` is not the only consumer.

    The audit ladder decides BLOCKED from `total_hard_failures`, which an
    unstarted scope leaves at zero — so without an explicit branch it would fall
    through the model tier toward PASS. This asserts the branch exists in the
    shipped ladder and is reached before any PASS is assigned.
    """
    import inspect

    from crossaudit.auditor import run as run_mod

    source = inspect.getsource(run_mod)
    ladder = source[source.index('if escalation_lock:'):]
    ladder = ladder[:ladder.index('\n\n')] if '\n\n' in ladder else ladder
    assert 'scope_started' in ladder, (
        "the audit verdict ladder no longer consults scope_started, so an "
        "unstarted scope can fall through to the model tier and reach PASS")
    assert ladder.index('scope_started') < ladder.index('"PASS"') if '"PASS"' in ladder else True


def test_the_third_state_is_a_distinct_value_not_a_missing_one():
    """If it funnels back into one value downstream, it has been renamed."""
    empty = run_checks(SCAFFOLD, ["schema"]).as_dict()
    blocked = run_checks(STARTED_WITH_RESULTS, ["schema"]).as_dict()
    started_clean = run_checks(
        {"experiments/demo/results.json":
             b'{"quantities": [{"name": "x", "value": 1, "unit": "m", "source": "s"}]}',
         "experiments/demo/metadata.yml":
             b"code_version: abc\ninputs: [data@v1]\n"}, ["schema"]).as_dict()
    verdicts = {empty["verdict"], blocked["verdict"], started_clean["verdict"]}
    assert len(verdicts) == 3, f"the three states collapsed into {verdicts}"
    assert empty["verdict"] == NOTHING_TO_AUDIT


# ------------------------------------------------- the two BLOCKED cases hold
def test_a_started_scope_missing_its_files_still_blocks():
    """The boss's table row that must not move."""
    result = run_checks(STARTED_NO_SCHEMA, ["schema"]).as_dict()
    assert result["verdict"] == "BLOCKED"
    assert result["total_hard_failures"] >= 1


def test_malformed_files_still_block():
    result = run_checks(
        {"experiments/demo/results.json": b"{not json",
         "experiments/demo/metadata.yml": b"code_version: v\ninputs: [a@1]\n"},
        ["schema"]).as_dict()
    assert result["verdict"] == "BLOCKED"


def test_scope_started_errs_toward_started():
    """Saying started when it is not keeps today's behaviour; the reverse hides
    a real failure. So any hint of work counts."""
    assert scope_started({}) is False
    assert scope_started(SCAFFOLD) is False
    assert scope_started({"experiments/results.json": b"{}"}) is True
    assert scope_started({"experiments/metadata.yml": b""}) is True
    assert scope_started({"experiments/demo/anything.txt": b""}) is True


# -------------------------------------------------------- what a person reads
def test_the_new_user_sentence_carries_no_product_jargon():
    """They are being told the wrong thing in the wrong vocabulary."""
    said = cli_main.NOTHING_TO_AUDIT_SENTENCE + " " + cli_main.NOTHING_TO_AUDIT_NEXT
    for jargon in ("DCL", "audited scope", "BLOCKER", "hard failure", "verdict"):
        assert jargon not in said, f"the first thing a new user reads says {jargon!r}"
    assert "Nothing to check yet" in cli_main.NOTHING_TO_AUDIT_SENTENCE
    assert "{scope}" in cli_main.NOTHING_TO_AUDIT_NEXT, (
        "the next step does not name where to put the work")
