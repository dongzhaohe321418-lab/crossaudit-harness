"""A finding can now say what became of it. Nothing decides anything with it yet.

`BLOCKER` carried two meanings at once — *a model believes there is a problem*
and *there is a problem* — and the dashboard said "a defect was caught" because
the structure had nothing else to offer. It was not overclaiming by choice.

This slice adds the field and populates it. Blocking is unchanged, no surface
renders the words, and no receipt digest moves.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from crossaudit.auditor.run import finding_states
from crossaudit.console import overview
from crossaudit.dcl import framework
from crossaudit.dcl.framework import (ALLEGED, CONFIRMED, FINDING_STATES,
                                      Finding, run_checks)

SRC = Path(framework.__file__).parent.parent
STARTED = {"experiments/demo/notes.txt": b"x"}
CLEAN = {"experiments/demo/results.json":
         b'{"quantities":[{"name":"x","value":1,"unit":"m","source":"s"}]}',
         "experiments/demo/metadata.yml": b"code_version: abc\ninputs: [d@v1]\n"}


def test_all_six_states_exist_and_are_distinct():
    assert FINDING_STATES == ("alleged", "confirmed", "fixed", "withdrawn",
                              "overridden", "unresolved")
    assert len(set(FINDING_STATES)) == 6


# ------------------------------------------------- the two honest defaults
def test_a_deterministic_finding_is_confirmed_not_alleged():
    """Verdict-in-code: `hard_failures` never consults a model, and the audit
    ladder reads it BEFORE the model's verdict. Demoting these into allegations
    would give up the distinction the states exist for."""
    result = run_checks(STARTED, ["schema"]).as_dict()
    assert result["findings"], "the fixture raised nothing to inspect"
    for finding in result["findings"]:
        assert finding["state"] == CONFIRMED, (
            f"a deterministic finding is {finding['state']!r}; that layer was "
            f"never an allegation")


def test_a_model_finding_is_alleged():
    reply = {"findings": [{"severity": "BLOCKER", "rule": "CA-DATA-001",
                           "artifact": "r.json", "observation": "x"}]}
    rows = finding_states(run_checks(CLEAN, ["schema"]).as_dict(), reply)
    model = [r for r in rows if r["tier"] == "model"]
    assert model and all(r["state"] == ALLEGED for r in model), (
        "a model finding claims to be established")


def test_both_tiers_appear_in_one_record_with_their_own_states():
    reply = {"findings": [{"severity": "BLOCKER", "rule": "CA-DATA-001",
                           "artifact": "r.json", "observation": "x"}]}
    rows = finding_states(run_checks(STARTED, ["schema"]).as_dict(), reply)
    by_tier = {r["tier"]: r["state"] for r in rows}
    assert by_tier == {"deterministic": CONFIRMED, "model": ALLEGED}


# ------------------------------------------- constraint 1: nothing decides
def test_nothing_gates_on_the_new_field():
    """A slice that both introduces the states and changes what they gate is
    two changes, and the second cannot be reviewed while the first moves."""
    for module in ("dcl/framework.py", "auditor/run.py", "cli/main.py",
                   "receipt/build.py", "receipt/verify.py"):
        text = (SRC / module).read_text()
        for state in FINDING_STATES:
            assert f'== "{state}"' not in text and f'!= "{state}"' not in text, (
                f"{module} branches on the finding state; this slice adds the "
                f"field and populates it, it does not decide with it")


def test_blocking_is_unchanged_by_the_field():
    """The count that gates is still severity, untouched by state."""
    result = run_checks(STARTED, ["schema"]).as_dict()
    assert result["total_hard_failures"] == sum(
        1 for f in result["findings"] if f["severity"] == "BLOCKER")
    assert result["verdict"] == "BLOCKED"


# ------------------------------------ constraint 2: no user-facing surface
@pytest.mark.parametrize("state", FINDING_STATES)
def test_no_user_facing_surface_renders_a_state_word(state):
    """The product goal is a black box; a person must never meet "alleged"."""
    page = (SRC / "console/page.py").read_text()
    zh_and_markup = re.sub(r"^\s*//.*$", "", page, flags=re.M)
    assert f'"{state}"' not in zh_and_markup or state in ("fixed",), (
        f"the console renders the finding state {state!r} to a person")


def test_the_report_does_not_carry_the_state():
    """The report is what a user reads; it is deliberately not the states'
    home, which is why they live in a sidecar."""
    run = (SRC / "auditor/run.py").read_text()
    report_fn = run[run.index("## Deterministic findings"):run.index("def run_audit")]
    for state in FINDING_STATES:
        assert f'"{state}"' not in report_fn, (
            f"the report renders {state!r}; a person reads that surface")


# ------------------------------- constraint 3: old receipts still verify
def test_the_state_never_reaches_a_receipt_or_its_digest():
    """Findings are not in the receipt, and the sidecar is not bound by it.

    If this ever changes, every receipt already written stops verifying — the
    field would have been added at the cost of all history.
    """
    build = (SRC / "receipt/build.py").read_text()
    assert "findings" not in build, (
        "the receipt now carries findings; adding a field to them changes the "
        "digest of every receipt written from here, and breaks none written "
        "before only by luck")
    for state in FINDING_STATES:
        assert state not in build


def test_the_sidecar_is_written_beside_the_receipt_not_inside_it():
    main = (SRC / "cli/main.py").read_text()
    assert 'ledger / "findings.json"' in main, "the states are not persisted"
    receipt_line = main[main.index('ledger / "receipt.json"'):][:200]
    assert "finding_states" not in receipt_line


# ------------------------------------------- constraint 4: the dashboard
def test_the_dashboard_no_longer_claims_a_defect_was_caught():
    """Checkably false the moment a finding can be `alleged`."""
    text = (SRC / "console/overview.py").read_text()
    live = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    assert '"a defect was caught"' not in live, (
        "the dashboard still asserts a defect was established")
    assert '"a concern was raised"' in live, (
        "replaced with something other than what the system knows")


def test_the_replacement_reaches_a_chinese_reader():
    page = (SRC / "console/page.py").read_text()
    assert '"a concern was raised":' in page, "the new note has no Chinese form"
    assert '"a defect was caught":' not in page, (
        "a stale entry translates a string nothing renders")
