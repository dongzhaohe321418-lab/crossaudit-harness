#!/usr/bin/env python3
"""A4S-4 analysis: correct diagnosis at a fixed false-positive budget, on held-out data items.

Registered in `PREREGISTRATION-DIAG.md`. Operating points are fixed on A4S-3 (development) and
applied unchanged to the held-out items. Diagnosis is decided by `diag_match` alone; no model
judges any outcome. Writes `records/ai4s/diag_results.json`.

    python benchmarks/ai4s/analyze_diag.py            # held-out analysis
    python benchmarks/ai4s/analyze_diag.py --dev      # the operating points, from A4S-3 only
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from diag_match import reading_diagnoses, validator_texts  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
REC = HERE.parents[1] / "benchmarks/code/records/ai4s"
K = 4
BUDGET = 0.10
BOOT = 10_000
SEED = 20261001
FAMILIES = ("cross", "self")


def load(runs: Path, manifest: Path):
    items = {i["item"]: i for i in json.loads(manifest.read_text())["items"]}
    nflag = {f: defaultdict(int) for f in FAMILIES}
    diag = {f: defaultdict(bool) for f in FAMILIES}
    reads = {f: defaultdict(int) for f in FAMILIES}
    for f in FAMILIES:
        for d in range(1, K + 1):
            for line in (runs / f"{f}.d{d}.jsonl").read_text().splitlines():
                r = json.loads(line)
                if not r.get("ok"):
                    continue
                iid = r["instance_id"]
                it = items[iid]
                reads[f][iid] += 1
                nflag[f][iid] += bool(r["flagged"])
                if it["fault"] and r["flagged"]:
                    diag[f][iid] |= reading_diagnoses(it["dataset"], it["fault"], it["params"],
                                                      r["blocker_texts"])
    return items, nflag, diag, reads


def operating_points(items, nflag) -> dict:
    """Smallest vote threshold m (flag if >= m of K readings flag) whose clean-flag rate <= BUDGET."""
    clean = [i for i, it in items.items() if not it["fault"]]
    out = {}
    for f in FAMILIES:
        rates = {m: sum(nflag[f][i] >= m for i in clean) / len(clean) for m in range(1, K + 1)}
        ok = [m for m in range(1, K + 1) if rates[m] <= BUDGET]
        out[f] = {"m": min(ok) if ok else None, "dev_clean_rate": rates}
    return out


def boot_ci(items, stat, seed=SEED) -> list[float]:
    """Percentile interval, items resampled within dataset (A4S-3's unit), BOOT resamples."""
    by = defaultdict(list)
    for i, it in items.items():
        by[it["dataset"]].append(i)
    rng = random.Random(seed)
    vals = []
    for _ in range(BOOT):
        sample = [rng.choice(v) for v in by.values() for _ in v]
        vals.append(stat(sample))
    vals.sort()
    return [100 * vals[int(0.025 * BOOT)], 100 * vals[int(0.975 * BOOT) - 1]]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    args = ap.parse_args()
    dev_items, dev_nflag, _, _ = load(AI4S / "runs/data_audit", REC / "data_items.json")
    ops = operating_points(dev_items, dev_nflag)
    if args.dev:
        print(json.dumps(ops, indent=1))
        return 0
    m = {f: ops[f]["m"] for f in FAMILIES}
    items, nflag, diag, reads = load(AI4S / "runs/data_audit_ho", REC / "data_items_ho.json")
    faulty = [i for i, it in items.items() if it["fault"]]
    clean = [i for i, it in items.items() if not it["fault"]]
    incomplete = {f: sum(reads[f][i] < K for i in items) for f in FAMILIES}

    def flagged(f, i):
        return nflag[f][i] >= m[f]

    def diagnosed(f, i):
        return flagged(f, i) and diag[f][i]

    vdiag = {i: reading_diagnoses(items[i]["dataset"], items[i]["fault"], items[i]["params"],
                                  validator_texts(items[i]["validator"]["checks"])) for i in faulty}
    vflag = {i: items[i]["validator"]["flagged"] for i in items}
    union = {i: vdiag[i] or diagnosed("cross", i) for i in faulty}

    def rate(ids, pred):
        return lambda sample: (sum(pred(i) for i in sample if i in ids) /
                               max(1, sum(1 for i in sample if i in ids)))
    F, C = set(faulty), set(clean)
    res = {"budget": BUDGET, "operating_points": ops, "incomplete_items": incomplete,
           "n_faulty": len(faulty), "n_clean": len(clean)}
    for name, pred_d, pred_c in [
        ("validator", lambda i: vdiag[i], lambda i: vflag[i]),
        ("cross", lambda i: diagnosed("cross", i), lambda i: flagged("cross", i)),
        ("self", lambda i: diagnosed("self", i), lambda i: flagged("self", i)),
        ("validator_or_cross", lambda i: union[i], lambda i: vflag[i] or flagged("cross", i)),
    ]:
        res[name] = {
            "diagnosed": sum(pred_d(i) for i in faulty),
            "diagnosed_pct_ci": boot_ci(items, rate(F, pred_d)),
            "clean_flagged": sum(pred_c(i) for i in clean),
            "clean_pct_ci": boot_ci(items, rate(C, pred_c)),
            "by_fault": dict(sorted(Counter(items[i]["fault"] for i in faulty if pred_d(i)).items())),
        }
    for name, f in [("cross", "cross"), ("self", "self")]:
        res[name]["flagged_faulty"] = sum(flagged(f, i) for i in faulty)

    def paired(a, b):
        d = lambda sample: (sum(a(i) - b(i) for i in sample if i in F) /  # noqa: E731
                            max(1, sum(1 for i in sample if i in F)))
        bb = sum(a(i) and not b(i) for i in faulty)
        cc = sum(b(i) and not a(i) for i in faulty)
        return {"points": 100 * (sum(a(i) for i in faulty) - sum(b(i) for i in faulty)) / len(faulty),
                "ci": boot_ci(items, d), "discordant_a_only": bb, "discordant_b_only": cc,
                "mcnemar_exact_p": mcnemar_exact(bb, cc)}

    h1 = paired(lambda i: union[i], lambda i: vdiag[i])
    union_clean = res["validator_or_cross"]["clean_flagged"] / len(clean)
    h1["holds"] = h1["ci"][0] > 0 and union_clean <= BUDGET
    h1["rule"] = ("holds iff the paired interval's lower end exceeds 0 and the union's held-out "
                  "clean-flag rate is at most the budget")
    res["H1_union_minus_validator"] = h1
    res["H2_cross_minus_self_route_comparison"] = paired(lambda i: diagnosed("cross", i),
                                                         lambda i: diagnosed("self", i))
    res["S1_flags_without_diagnosis"] = {
        f: sum(flagged(f, i) and not diag[f][i] for i in faulty) for f in FAMILIES}
    out = REC / "diag_results.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "operating_points"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
