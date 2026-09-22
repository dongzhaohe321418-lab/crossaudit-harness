#!/usr/bin/env python3
"""Plant findings against Amendment 12's overlap check and show it separates them.

The check exists to say whether clarified-arm findings are quoting the clarification back. If it
cannot tell a finding that reproduces the added sentence from one that diagnoses the same bug in
its own words, its counts mean nothing and the adjudication's blinding is unmeasured.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adjudication_sheet import (added_sentences, overlap,  # noqa: E402
                                vocabulary_overlap)

ORIGINAL = ("Write a function to convert a snake case string to camel case string. "
            "The function takes one string argument and returns a string.")
CLARIFIED = (ORIGINAL + " Treat one or more consecutive underscores as separators and ignore "
             "empty components, including those at the beginning or end of the string.")

# name, finding text, expected: quotation high?, vocabulary high?
#
# The two metrics answer different questions and the planted cases say so. A close paraphrase
# is NOT quotation -- reordering breaks the run -- and the first version of this file expected
# the run metric to catch it, scored 0.41, and would have been "fixed" by lowering the
# threshold. It was the expectation that was wrong.
CASES = [
    ("verbatim quotation of the added sentence",
     "The code does not treat one or more consecutive underscores as separators and ignore "
     "empty components, including those at the beginning or end of the string.", True, True),
    ("close paraphrase, same words reordered",
     "Consecutive underscores are not treated as separators, and empty components at the "
     "beginning or end of the string are not ignored.", False, True),
    ("the same defect diagnosed in the auditor's own words",
     "`snake_to_camel` maps each split piece through `capitalize()`, so a run of two delimiters "
     "yields a stray placeholder instead of being skipped.", False, False),
    ("a finding about something else entirely",
     "The function has no type annotations and its name shadows a builtin in this module.",
     False, False),
    ("an empty finding", "", False, False),
]


def main() -> int:
    added = added_sentences(ORIGINAL, CLARIFIED)
    if len(added) != 1:
        print(f"  [FAIL] the added sentence was not recovered: {added}")
        return 1
    print(f"  [ok ] the added sentence is recovered: {added[0][:60]}...")

    failures = []
    for name, text, want_q, want_v in CASES:
        q, v = overlap(text, added), vocabulary_overlap(text, added)
        ok = (q >= 0.5) == want_q and (v >= 0.5) == want_v
        if not ok:
            failures.append(f"{name}: quotation {q:.2f} (wanted {'high' if want_q else 'low'}), "
                            f"vocabulary {v:.2f} (wanted {'high' if want_v else 'low'})")
        print(f"  [{'ok ' if ok else 'FAIL'}] {name:44s} quotation {q:.2f}  vocabulary {v:.2f}")

    # the check must also be blind to a condition that added nothing
    if overlap("any text at all", []) != 0.0 or vocabulary_overlap("any text", []) != 0.0:
        failures.append("an empty addition did not score zero on both metrics")

    for f in failures:
        print(f"      {f}")
    if failures:
        print(f"\n{len(failures)} case(s) did not behave as required")
        return 1
    print("\nquotation and shared vocabulary are measured separately, and a paraphrase\nregisters on the second and not the first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
