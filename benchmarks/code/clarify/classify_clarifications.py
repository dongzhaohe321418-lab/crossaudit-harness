#!/usr/bin/env python3
"""Classify every clarification against the hidden oracle it was supposed to settle.

**The first review's blocking finding.** The registration describes the manipulation as adding
"the rule the hidden suite tests and the prose leaves open". The generator is shown the failing
**inputs** and not their expected outputs (§2 and `generate.py`), so what it actually adds is a
rule it INFERRED from inputs alone -- and that rule sometimes contradicts the oracle outright.
A numerical criterion can pass while that description is false, so the description is checked.

The classification is per **exercised input**, not per instance, because an addition can be
right about one failing case and wrong about another: `b2:Mbpp/559` states the empty-list case
correctly and the all-negative case backwards, and the hidden suite exercises both.

Each row records the added sentences, the witness's exercised inputs with the oracle's expected
value, and a hand verdict with its reason. **Hand verdicts are recorded as data, written after
the outcome was known, and the table is published so a reader can disagree with any row** --
which is the only honest form for a judgement that cannot be mechanised.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from adjudication_sheet import added_sentences  # noqa: E402

COND = HERE.parent / "records/clarify/conditions.json"
DUMP = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs/residual/index.json"
OUT = HERE.parent / "records/clarify/clarification_classification.json"

#: instance -> (verdict, reason). Verdicts:
#:   consistent   — the added rule predicts the oracle's value on every exercised input
#:   partial      — it predicts the oracle on some exercised inputs and contradicts on others
#:   contradicts  — it contradicts the oracle on the exercised inputs
#:   broadens     — it relaxes a precondition the original prose stated, rather than settling
#:                  something the prose left open
VERDICTS = {
 "b1:Mbpp/102": ("contradicts", "says leading/trailing separators produce ignored empty components; the oracle preserves them (`___python_program` -> `___PythonProgram`)"),
 "b1:Mbpp/103": ("contradicts", "says the zero-index boundary value is 1; the oracle expects 0 at (0, 0)"),
 "b1:Mbpp/278": ("contradicts", "says count all elements, so 6 for a 6-tuple; the oracle expects 5"),
 "b1:Mbpp/294": ("contradicts", "says only numeric elements count; the oracle returns `False` on a list containing a string and a float"),
 "b1:Mbpp/305": ("partial", "the `None`-when-fewer-than-two rule matches the exercised inputs; the case-insensitivity it also adds does not — a later witness expects the uppercase-P match"),
 "b1:Mbpp/391": ("consistent", "shared indices, element-except-last as successive keys, last as value; matches every exercised case"),
 "b1:Mbpp/410": ("contradicts", "says non-integers are considered, which gives 2.5; the oracle expects 5"),
 "b1:Mbpp/459": ("contradicts", "says every non-uppercase character is left unchanged; the oracle keeps only lowercase letters"),
 "b1:Mbpp/556": ("consistent", "only the first n elements, unordered pairs counted once; matches n=1 -> 0 and n=10 -> 25"),
 "b1:Mbpp/558": ("contradicts", "says align by place value padding leading zeros, giving 14 on (12345, 9); the oracle expects 8, which is left-aligned truncation"),
 "b1:Mbpp/559": ("consistent", "empty or all-negative returns 0; matches both exercised cases"),
 "b1:Mbpp/576": ("consistent", "same relative order, not necessarily contiguous; matches every exercised case"),
 "b1:Mbpp/790": ("contradicts", "says odd indices may hold any value, which predicts True; the oracle expects False"),
 "b1:Mbpp/806": ("contradicts", "says the longest uppercase run's length, which is 1 for 'Aaa'; the oracle expects 0"),
 "b2:Mbpp/103": ("contradicts", "same as b1: says 1 at (0, 0); the oracle expects 0"),
 "b2:Mbpp/137": ("contradicts", "says an all-zero array gives 0.0; the oracle expects `inf`"),
 "b2:Mbpp/278": ("contradicts", "says return the number of elements, so 6 for a 6-tuple; the oracle expects 5"),
 "b2:Mbpp/294": ("contradicts", "same as b1: only numeric counts, while the oracle returns `False`"),
 "b2:Mbpp/305": ("partial", "same split as b1 — the `None` rule matches, the case-insensitivity does not"),
 "b2:Mbpp/391": ("consistent", "shared indices, count equal to the shortest input; matches every exercised case"),
 "b2:Mbpp/410": ("contradicts", "same as b1: non-integers considered gives 2.5, the oracle expects 5"),
 "b2:Mbpp/459": ("contradicts", "same as b1: non-alphabetic characters preserved, while the oracle removes them"),
 "b2:Mbpp/556": ("consistent", "the second argument bounds which elements form pairs; matches both exercised cases"),
 "b2:Mbpp/558": ("contradicts", "same as b1: place-value alignment gives 14, the oracle expects 8"),
 "b2:Mbpp/559": ("partial", "the empty-list rule (return 0) matches an exercised case; the all-negative rule states the greatest negative element where the oracle expects 0"),
 "b2:Mbpp/576": ("consistent", "same order without requiring consecutiveness; matches every exercised case"),
 "b2:Mbpp/597": ("broadens", "the original prose states the arrays ARE sorted; the addition relaxes that precondition and requires an ascending sort. It predicts the oracle's values, but it changes a stated requirement rather than settling an omission"),
 "b2:Mbpp/74":  ("contradicts", "requires a bijection between pattern values and sequence values; the oracle returns True on six identical values against distinct patterns"),
 "b2:Mbpp/790": ("contradicts", "same as b1: predicts True where the oracle expects False"),
 "b2:Mbpp/806": ("contradicts", "same as b1: predicts 1 for 'Aaa' where the oracle expects 0"),
 "b2:Mbpp/92":  ("contradicts", "requires at least three digits; the oracle returns True for the two-digit 82"),
 "b1:Mbpp/427": ("contradicts", "says reverse ALL hyphen-separated fields without validating their number or width; the oracle applies a width-constrained substitution and leaves the unmatched tail in place ('2021-1-026' -> '02-1-20216', not '026-1-2021')"),
}


def main() -> int:
    conds = json.loads(COND.read_text(encoding="utf-8"))["conditions"]
    wit = {r["instance_id"]: r for r in json.loads(DUMP.read_text(encoding="utf-8"))}
    missing = sorted(set(conds) - set(VERDICTS))
    extra = sorted(set(VERDICTS) - set(conds))
    if missing or extra:
        raise SystemExit(f"ERR: classification does not cover the population. "
                         f"missing={missing} extra={extra}")

    rows, tally = {}, {}
    for iid in sorted(conds):
        verdict, reason = VERDICTS[iid]
        cases = (wit[iid].get("witness") or {}).get("cases") or []
        rows[iid] = {
            "verdict": verdict, "reason": reason,
            "added": added_sentences(conds[iid]["original"]["spec"],
                                     conds[iid]["clarified"]["spec"]),
            "exercised": [{"input": c.get("input"), "oracle_expects": c.get("expected")}
                          for c in cases[:3]],
        }
        tally[verdict] = tally.get(verdict, 0) + 1

    OUT.write_text(json.dumps({
        "what_this_is": "a hand classification of each clarification against the hidden oracle, "
                        "written after the outcome was known and published row by row so it "
                        "can be disputed",
        "verdict_meanings": {
            "consistent": "predicts the oracle's value on every exercised input",
            "partial": "predicts it on some exercised inputs and contradicts on others",
            "contradicts": "contradicts the oracle on the exercised inputs",
            "broadens": "relaxes a precondition the original prose stated rather than settling "
                        "an omission",
        },
        "tally": tally, "n": len(rows), "rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for v in ("consistent", "broadens", "partial", "contradicts"):
        print(f"  {v:12s} {tally.get(v, 0):2d}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
