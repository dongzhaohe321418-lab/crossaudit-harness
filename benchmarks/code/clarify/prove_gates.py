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

# Six DISTINCT five-word sentences. They were six copies of one sentence until 2026-09-22,
# which made "reordered" and "dropped a sentence" impossible to plant: every sentence matched
# every other one.
SENTS = ["Return the list sorted ascending.",
         "Accept any comparable element type.",
         "Leave the caller's list untouched.",
         "Return a newly allocated list.",
         "Raise nothing on empty input.",
         "Treat missing values as absent."]
ORIGINAL = " ".join(SENTS)
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
    ("clean run passes", conditions(), WITNESS, HIDDEN, ""),
    ("candidate differs in one condition",
     conditions(candidate_clarified="def f(x):\n    return x  # edited"), WITNESS, HIDDEN,
     "candidate"),
    ("visible suite differs in one condition",
     conditions(visible_placebo="assert f(1) == 1  # edited"), WITNESS, HIDDEN, "visible"),
    ("clarification leaks the failing input",
     conditions(spec_clarified=ORIGINAL + " On the input [[3, 1, 2]] return them in order."),
     WITNESS, HIDDEN, "input of a failing case"),
    ("clarification leaks the expected value",
     conditions(spec_clarified=ORIGINAL + " The result there is [1, 2, 3] and nothing else."),
     WITNESS, HIDDEN, "expected of a failing case"),
    # The witness's expected value is changed here so the quoted hidden line is caught by the
    # hidden-line rule and by nothing else.
    # Amendment 8: the bare truth value is the predicate's own vocabulary, but it is still a
    # leak the moment it stands beside the input it belongs to.
    ("bare True is not a leak on its own",
     conditions(spec_clarified=ORIGINAL + " Return True whenever two of the elements compare exactly equal here."),
     {"cases": [{"input": "[[9, 9, 9]]", "expected": "True", "actual": "False"}]}, HIDDEN, ""),
    ("bare True IS a leak when the failing input stands beside it",
     conditions(spec_clarified=ORIGINAL + " On [[9, 9, 9]] the function returns True always."),
     {"cases": [{"input": "[[9, 9, 9]]", "expected": "True", "actual": "False"}]}, HIDDEN,
     "input of a failing case"),
    ("a substantive expected value is still a leak on its own",
     conditions(spec_clarified=ORIGINAL + " The result is [1, 2, 3] whenever ties are broken."),
     {"cases": [{"input": "[[9, 9, 9]]", "expected": "[1, 2, 3]", "actual": "[3, 2, 1]"}]},
     HIDDEN, "expected of a failing case"),
    # A line printed in the specification itself is public, not hidden. Until the first review
    # of P3 this gate excluded an instance for quoting three assertions its own specification
    # prints.
    ("a line that is public in the specification is not a leak",
     conditions(spec_clarified=CLARIFIED),
     WITNESS, "assert sort_list([]) == []\n" + SENTS[0] + " " + SENTS[1], ""),
    ("clarification quotes a hidden test line (isolated)",
     conditions(spec_clarified=ORIGINAL + " assert sort_list([]) == [] and nothing more here."),
     {"cases": [{"input": "[[3, 1, 2]]", "expected": "[9, 9, 9]", "actual": "[3, 2, 1]"}]},
     HIDDEN, "hidden-test line"),
    ("placebo is far shorter than the clarification",
     conditions(spec_placebo=ORIGINAL + " Also note this."), WITNESS, HIDDEN, "word counts"),
    ("placebo adds nothing at all",
     conditions(spec_placebo=ORIGINAL), WITNESS, HIDDEN, "added no words"),
    # Gates 4 and 5. Each keeps both arms' ADDED word counts inside the length band, so the
    # length gate cannot fire and the planted violation is the only thing left to catch.
    ("clarification rewrites a sentence that was already there",
     conditions(spec_clarified=" ".join(["Return the array sorted ascending."] + SENTS[1:])
                + " When two elements compare equal, keep their original relative order."),
     WITNESS, HIDDEN, "does not preserve"),
    ("placebo drops a sentence that was already there",
     conditions(spec_placebo=" ".join(SENTS[1:])
                + " This function is part of the collections utilities in this module,"
                  " alongside five other helpers."),
     WITNESS, HIDDEN, "does not preserve"),
    ("clarification reorders the original's sentences",
     conditions(spec_clarified=" ".join([SENTS[1], SENTS[0]] + SENTS[2:])
                + " When two elements compare equal, keep their original relative order."),
     WITNESS, HIDDEN, "does not preserve"),
    ("adding before the original is allowed",
     conditions(spec_clarified="When two elements compare equal, keep their original relative"
                                " order. " + ORIGINAL), WITNESS, HIDDEN, ""),
    ("edited arm echoes the prompt's scaffolding header",
     conditions(spec_clarified="SPECIFICATION:\n" + CLARIFIED), WITNESS, HIDDEN,
     "scaffolding"),
    ("scaffolding echo is caught in the placebo arm too",
     conditions(spec_placebo="SPECIFICATION:\n" + ORIGINAL
                + " This function is part of the collections utilities here."),
     WITNESS, HIDDEN, "scaffolding"),
]

# Gate 5 is only as good as the lines the caller passes it. These are the lines
# `generate.py` uses to build its prompts; if that prompt changes, this list must change with
# it, and the two scaffolding cases above are what notices.
SCAFFOLD = ["SPECIFICATION:",
            "The hidden suite exercises these inputs, where the prose is silent:"]


def main() -> int:
    failures = []
    # A case caught by a rule other than the one it plants proves nothing about that rule --
    # this programme has now made that mistake twice, once with a hidden line that was also an
    # expected value, and once with three length-matched cases that all tripped the length
    # gate. Each case therefore names the text its intended gate produces, and a case caught
    # by a different gate FAILS.
    for name, conds, witness, hidden, want_substr in CASES:
        problems = gates.run_all("TEST", conds, witness, hidden, SCAFFOLD)
        caught = len(problems) > 0
        want = bool(want_substr)
        ok = (caught == want) and (not want or any(want_substr in p for p in problems))
        mark = "ok " if ok else "FAIL"
        if not ok:
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
