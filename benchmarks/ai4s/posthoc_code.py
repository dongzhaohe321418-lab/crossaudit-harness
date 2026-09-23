#!/usr/bin/env python3
"""A4S-1 post hoc descriptions, added after the registered outcomes were computed. None is registered.

1. Earlier-step defects: each instance's program holds the sample's own functions for steps 1..k; the
   flag rate is split by whether any earlier step of that sample failed its own tests.
2. Scope-type BLOCKERs: a pattern count of findings that the increment does not implement the whole
   multi-step problem (the framing artefact that motivated A4S-1b), per family and stratum.
3. A seeded sample (seed 20260929) of 20 flagged correct instances with clean chains, listed for reading.
Arm: `a` (runs/audit, A4S-1) or `b` (runs/audit_b, A4S-1b). Output: records/ai4s/code_posthoc_<arm>.json.
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AI4S = Path.home() / "Documents/Crossaudit/ai4s"
STRATA = REPO / "benchmarks/code/records/ai4s/strata.json"
SCOPE = re.compile(r"(implements only|provides only|contains only|defines only|only (defines|implements|provides|contains)"
                   r"|no [^.]{0,80}(calculation|computation|simulation|solver|routine|function|script)[^.]{0,40}(required|requested)"
                   r"|(does not|doesn't) (implement|provide|compute|return|perform)[^.]{0,80}(requested|required|overall|full|complete|final)"
                   r"|is not (a|the) (complete|full)|incomplete (script|implementation|program)|entire (script|problem|task)"
                   r"|the (full|overall|complete) (script|task|problem))", re.I)


def main() -> int:
    arm = sys.argv[1] if len(sys.argv) > 1 else "a"
    runs = AI4S / ("runs/audit" if arm == "a" else "runs/audit_b")
    ex = {}
    for line in (AI4S / "runs/execution.jsonl").read_text().splitlines():
        r = json.loads(line)
        ex[(r["problem_id"], r["sample"], r["step"])] = r["outcome"]
    s = json.loads(STRATA.read_text())
    texts = collections.defaultdict(list)
    for fam in ("cross", "self"):
        for d in range(1, 9):
            for line in (runs / f"{fam}.d{d}.jsonl").read_text().splitlines():
                r = json.loads(line)
                if r["flagged"]:
                    texts[(fam, r["instance_id"])] += r["blocker_texts"]

    def clean_chain(iid):
        pid, st, sm = iid.rsplit(".", 2)
        return all(ex.get((pid, int(sm[1:]), i)) not in ("fail", "timeout", "no-function")
                   for i in range(int(st) - 1))

    out = {"arm": arm, "earlier_step": {}, "scope": {}}
    for fam in ("cross", "self"):
        for name in ("defective", "correct"):
            ids = s[name]
            cc = [i for i in ids if clean_chain(i)]
            bad = [i for i in ids if not clean_chain(i)]
            out["earlier_step"][f"{fam}/{name}"] = {
                "clean_chain": f"{sum((fam, i) in texts for i in cc)}/{len(cc)}",
                "earlier_step_failed": f"{sum((fam, i) in texts for i in bad)}/{len(bad)}"}
            fl = [i for i in ids if (fam, i) in texts]
            out["scope"][f"{fam}/{name}"] = {
                "flagged": f"{len(fl)}/{len(ids)}",
                "any_scope_blocker": sum(any(SCOPE.search(t) for t in texts[(fam, i)]) for i in fl),
                "only_scope_blockers": sum(all(SCOPE.search(t) for t in texts[(fam, i)]) for i in fl)}
    pool = sorted(i for i in s["correct"] if clean_chain(i) and ("cross", i) in texts)
    out["sample_20"] = random.Random(20260929).sample(pool, min(20, len(pool)))
    rec = REPO / f"benchmarks/code/records/ai4s/code_posthoc_{arm}.json"
    rec.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "sample_20"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
