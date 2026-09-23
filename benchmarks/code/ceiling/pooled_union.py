#!/usr/bin/env python3
"""The pooled twenty-reading union (cross 8 + self 8 + astra 4) on BOTH strata.

The paper quoted the pooled recall, 53/110 = 48.2%, beside the shipped route's 16.0% false
positives, which belong to eight readings of one route. Manuscript review paper1 r5 recomputed
the pooled union on the correct stratum: 54/150. This writes both, with ceiling 1's own interval
code and seed, so the pooled recall is never quoted without its own price.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import ceiling  # noqa: E402
import explore  # noqa: E402
import report_ceiling as rc  # noqa: E402

OUT = HERE.parent / "records/ceiling/pooled_union.json"


def main() -> int:
    explore.EXPLORE = ceiling.CEILING_CACHE
    inst = explore.load_instances()
    scope = ceiling.in_scope(inst, explore.load_audit_set())
    keys = ([("holistic", "cross", d) for d in range(1, 9)]
            + [("holistic", "self", d) for d in range(1, 9)]
            + [("holistic", "astra", d) for d in range(1, 5)])
    flag = {i: 0 for i in scope}
    for k in keys:
        have = ceiling.load_detector_everywhere(k, set(scope))
        assert len(have) == len(scope), f"{k}: {len(have)} of {len(scope)}"
        for i, r in have.items():
            flag[i] |= int(bool(r.get("flagged")))
    seed = json.loads((HERE.parent / "records/ceiling/numbers.json").read_text())["bootstrap_seed"]
    rec = {"readings": {"cross": 8, "self": 8, "astra": 4}, "seed": seed, "reps": 10000}
    for s in ("P", "C"):
        ids = [i for i in scope if inst[i]["stratum"] == s]
        rec[s] = rc.clustered_rate(flag, ids, inst, 10000, seed)
    OUT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for s in ("P", "C"):
        r = rec[s]
        print(s, f"{r['k']}/{r['n']} = {100*r['rate']:.1f}%",
              [round(100 * x, 1) for x in r["cluster_ci95"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
