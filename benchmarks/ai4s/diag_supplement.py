#!/usr/bin/env python3
"""A4S-4 supplement, written after review round 1 (codex-review-a4s4, codex-review-paper4).

1. REGISTERED, previously omitted: each tier's count and share by fault type with its interval
   (the registration's "also reported" list; the round-1 report gave counts only).
2. POST HOC: the fifteen items the union adds under the registered rule, each with the agent's
   reading of its matching finding against the manifest (verdicts below; three were revised after
   review round 2 to "LOCATES ONLY"), the H1 contrast counting only the items whose finding locates
   the fault with the right columns (not "PARTLY WRONG"), and the count whose finding also explains
   the injected transformation correctly (neither "PARTLY WRONG" nor "LOCATES ONLY").
3. The seed-7 inspection sample of the round-1 report, reconstructed exactly (population: for each
   `cross` reading of a faulty item, its first BLOCKER text the registered rule counts; order:
   reading files d1..d4 in line order; `random.Random(7).shuffle`; first ten).

Writes records/ai4s/diag_supplement.json.
"""
from __future__ import annotations

import json
import random
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_diag as A  # noqa: E402
from diag_match import diagnoses, reading_diagnoses, validator_texts  # noqa: E402

REC = HERE.parents[1] / "benchmarks/code/records/ai4s"
READ = REC / "diag_readings"

# The agent's reading of each union-only item's matching finding (post hoc; not independent).
UNION_ONLY_VERDICTS = {
    "airfoil.F1.0": "names the column and the 1000x metre/millimetre scaling",
    "airfoil.F1.3": "names the column and a 1000x error",
    "airfoil.F5.1": "names both columns and says they are swapped",
    "airfoil.F5.2": "names both columns and says they are swapped",
    "airfoil.F5.4": "names both columns and says they are substituted/swapped",
    "concrete.F1.0": "names the column and values about 1000x the rest",
    "concrete.F1.1": "LOCATES ONLY: names the column and values far outside the MPa range; does not "
                     "identify the psi conversion",
    "concrete.F1.2": "LOCATES ONLY: names the column and anomalous values it calls decimal-shifted; "
                     "the injection is a 145.038x psi conversion",
    "concrete.F1.3": "LOCATES ONLY: names the column and anomalous values, with a wrong 100x "
                     "reconstruction (the injection is 145.038x psi); its draw-4 reading does describe "
                     "values in another unit",
    "concrete.F1.4": "names the column and values scaled by 1000",
    "concrete.F5.0": "PARTLY WRONG: reports a three-column reassignment including coarse aggregate; "
                     "the injected fault swaps superplasticizer and fine aggregate only",
    "concrete.F5.3": "names both columns and says they are swapped",
    "concrete.F5.4": "names both columns and says they are interchanged",
    "supercond.F1.3": "names the column and a mean radius impossible in pm (angstrom values)",
    "supercond.F5.1": "names both columns and says their values are reversed",
}


def mcnemar(b: int, c: int) -> float:
    n, k = b + c, min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main() -> int:
    items, nflag, diag, _ = A.load(READ, REC / "data_items_ho.json")
    m = {"cross": 1, "self": 4}
    faulty = [i for i, it in items.items() if it["fault"]]
    v = {i: reading_diagnoses(items[i]["dataset"], items[i]["fault"], items[i]["params"],
                              validator_texts(items[i]["validator"]["checks"])) for i in faulty}
    tiers = {
        "validator": lambda i: v[i],
        "cross": lambda i: nflag["cross"][i] >= m["cross"] and diag["cross"][i],
        "self": lambda i: nflag["self"][i] >= m["self"] and diag["self"][i],
    }
    tiers["validator_or_cross"] = lambda i: v[i] or tiers["cross"](i)
    by_fault = {}
    for name, pred in tiers.items():
        by_fault[name] = {}
        for f in sorted({items[i]["fault"] for i in faulty}):
            ids = {i for i in faulty if items[i]["fault"] == f}
            k = sum(pred(i) for i in ids)
            ci = A.boot_ci(items, lambda s, ids=ids, pred=pred: (
                sum(pred(i) for i in s if i in ids) / max(1, sum(1 for i in s if i in ids))))
            by_fault[name][f] = {"diagnosed": k, "of": len(ids), "pct": 100 * k / len(ids), "ci": ci}

    only = sorted(i for i in faulty if tiers["validator_or_cross"](i) and not v[i])
    assert only == sorted(UNION_ONLY_VERDICTS), only
    strict = [i for i in only if not UNION_ONLY_VERDICTS[i].startswith("PARTLY WRONG")]
    explains = [i for i in strict if not UNION_ONLY_VERDICTS[i].startswith("LOCATES ONLY")]
    F = set(faulty)
    strict_ci = A.boot_ci(items, lambda s: (sum(1 for i in s if i in strict) /
                                            max(1, sum(1 for i in s if i in F))))
    rows = [json.loads(l) for d in range(1, 5) for l in (READ / f"cross.d{d}.jsonl").read_text().splitlines()]
    pop = []
    for r in rows:
        it = items[r["instance_id"]]
        if it["fault"]:
            for t in r["blocker_texts"]:
                if diagnoses(it["dataset"], it["fault"], it["params"], t):
                    pop.append({"item": r["instance_id"], "draw": r["draw"], "text": t})
                    break
    random.Random(7).shuffle(pop)
    out = {
        "registered_by_fault_with_intervals": by_fault,
        "posthoc_union_only_verdicts": UNION_ONLY_VERDICTS,
        "posthoc_H1_strict": {"added_items": len(strict), "points": 100 * len(strict) / len(faulty),
                              "ci": strict_ci, "discordant": [len(strict), 0],
                              "mcnemar_exact_p": mcnemar(len(strict), 0)},
        "posthoc_right_columns_and_explanation": {
            "items": len(explains), "points": 100 * len(explains) / len(faulty),
            "ci": A.boot_ci(items, lambda s: (sum(1 for i in s if i in explains) /
                                              max(1, sum(1 for i in s if i in F))))},
        "inspection_sample_seed7": pop[:10],
        "self_operating_point_note": ("self at m=4 counts an item when all four readings flag and at "
                                      "least one flagging reading's text meets the rule"),
    }
    (REC / "diag_supplement.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["posthoc_H1_strict"], indent=1))
    for name in by_fault:
        print(name, {f: f"{d['diagnosed']}/{d['of']} [{d['ci'][0]:.1f}, {d['ci'][1]:.1f}]"
                     for f, d in by_fault[name].items()})
    print("sample:", [(s["item"], s["draw"]) for s in out["inspection_sample_seed7"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
