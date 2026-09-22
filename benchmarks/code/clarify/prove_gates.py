#!/usr/bin/env python3
"""Plant a violation against each of P3's gates and show it is caught.

A gate nobody has seen fail is not a gate. This programme has learned that four times over in
one month: a digest that froze a defect as faithfully as a fix, a binding that protected one
sentence of a six-sentence withdrawal, a check that called comment-stripping "visible", and a
skip-path test that asserted `pytest.skip` raises. Each looked like a check and was not.

Run before any P3 reading is bought. Non-zero exit means a gate did not fire.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates  # noqa: E402

ORIGINAL = ("Return the list sorted ascending. " * 6).strip()
CLARIFIED = ORIGINAL + " When two elements compare equal, keep their original relative order."
PLACEBO = ORIGINAL + " This function is part of the collections utilities in this module."
WITNESS = {"cases": [{"input": "[[3, 1, 2]]", "expected": "[1, 2, 3]", "actual": "[3, 2, 1]"}]}
HIDDEN = "assert sort_list([3, 1, 2]) == [1, 2, 3]\nassert sort_list([]) == []"


def conditions(spec_clarified=CLARIFIED, spec_placebo=PLACEBO,
               candidate="def f(x):\n    return x", visible="assert f(1) == 1",
               candidate_clarified=None, visible_placebo=None):
    return {
        "original": {"spec": ORIGINAL, "candidate": candidate, "visible_tests": visible},
        "clarified": {"spec": spec_clarified,
                      "candidate": candidate_clarified or candidate, "visible_tests": visible},
        "placebo": {"spec": spec_placebo, "candidate": candidate,
                    "visible_tests": visible_placebo or visible},
    }


CASES = [
    ("clean run passes", conditions(), WITNESS, HIDDEN, 0),
    ("candidate differs in one condition",
     conditions(candidate_clarified="def f(x):\n    return x  # edited"), WITNESS, HIDDEN, 1),
    ("visible suite differs in one condition",
     conditions(visible_placebo="assert f(1) == 1  # edited"), WITNESS, HIDDEN, 1),
    ("clarification leaks the failing input",
     conditions(spec_clarified=ORIGINAL + " On the input [[3, 1, 2]] return them in order."),
     WITNESS, HIDDEN, 1),
    ("clarification leaks the expected value",
     conditions(spec_clarified=ORIGINAL + " The result there is [1, 2, 3] and nothing else."),
     WITNESS, HIDDEN, 1),
    # This case used to quote a hidden line that also contained the expected value, so it was
    # caught by the expected-value rule and the hidden-line rule was never exercised. The line
    # quoted here appears in the hidden program and in no witness field, which is the only way
    # to know the third rule works.
    ("clarification quotes a hidden test line (isolated)",
     conditions(spec_clarified=ORIGINAL + " assert sort_list([]) == []"),
     {"cases": [{"input": "[[3, 1, 2]]", "expected": "[9, 9, 9]", "actual": "[3, 2, 1]"}]},
     HIDDEN, 1),
    ("placebo is far shorter than the clarification",
     conditions(spec_placebo=ORIGINAL + " Also note this."), WITNESS, HIDDEN, 1),
    ("placebo adds nothing at all",
     conditions(spec_placebo=ORIGINAL), WITNESS, HIDDEN, 1),
]


def main() -> int:
    failures = []
    for name, conds, witness, hidden, expect_problems in CASES:
        problems = gates.run_all("TEST", conds, witness, hidden)
        caught = len(problems) > 0
        want = expect_problems > 0
        mark = "ok " if caught == want else "FAIL"
        if caught != want:
            failures.append(name)
        detail = problems[0].split(": ", 1)[1][:72] if problems else "no problems"
        print(f"  [{mark}] {name:44s} -> {detail}")
    if failures:
        print(f"\n{len(failures)} gate(s) did not behave as required: {failures}")
        return 1
    print(f"\nall {len(CASES)} planted cases behave as required; the gates may be relied on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
