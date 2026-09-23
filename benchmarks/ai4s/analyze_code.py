#!/usr/bin/env python3
"""A4S-1 analysis: the outcomes registered in `PREREGISTRATION-CODE.md`.

Reuses the reviewed statistics of the ceiling study (`benchmarks/code/report_ceiling.py`): exact
subset-averaged union curves, the problem-cluster percentile bootstrap, and the paired difference
with exact McNemar and the cluster sign-flip test. This study's seed (20260925) and 10,000
resamples are passed explicitly.

Primary: `cross` union recall at K = 8 on the defective stratum with the union false-positive rate
on the correct stratum. Secondary: the K ladder and the K = 7 -> 8 gain (the flattening statistic);
`self` at K = 8; the paired self - cross contrast at K = 8 (H3), with the K = 1 contrast beside it;
the pooled two-family union. The residual (defective, no flag in 16 readings) is listed for the
rating sheet. Only complete instances (8 ok readings per family) enter; incomplete ones are listed.

    python benchmarks/ai4s/analyze_code.py --out benchmarks/code/records/ai4s/code_results.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "benchmarks/code"))
import report_ceiling as rc  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
AUDIT = AI4S / "runs/audit"
STRATA = REPO / "benchmarks/code/records/ai4s/strata.json"
K = 8
SEED = 20260925
REPS = 10_000


def problem(iid: str) -> str:
    return iid.rsplit(".", 2)[0]


def load(fam: str) -> dict[str, dict[int, bool]]:
    out: dict[str, dict[int, bool]] = defaultdict(dict)
    for d in range(1, K + 1):
        f = AUDIT / f"{fam}.d{d}.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if r.get("ok"):
                        out[r["instance_id"]][d] = bool(r["flagged"])
    return out


def by_cluster(values: dict[str, float]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for iid, v in values.items():
        out[problem(iid)].append(v)
    return out


def rate(values: dict[str, float]) -> dict:
    n = len(values)
    lo, hi = rc.cluster_bootstrap_ci(by_cluster(values), REPS, SEED)
    return {"n": n, "problems": len(by_cluster(values)),
            "pct": round(100 * sum(values.values()) / n, 1) if n else None,
            "ci": [round(100 * lo, 1), round(100 * hi, 1)] if lo is not None else None}


def union_value(k: int, K_: int) -> float:
    """Probability that a random K_-subset of the 8 draws contains at least one of k flags."""
    return 1.0 - (math.comb(K - k, K_) / math.comb(K, K_) if K - k >= K_ else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    strata = json.loads(STRATA.read_text(encoding="utf-8"))
    fams = {f: load(f) for f in ("cross", "self")}
    out: dict = {"seed": SEED, "reps": REPS}
    for name in ("defective", "correct"):
        ids = strata[name]
        complete = [i for i in ids if all(len(fams[f].get(i, {})) == K for f in fams)]
        out[f"{name}_complete"] = len(complete)
        out[f"{name}_incomplete"] = sorted(set(ids) - set(complete))[:20]
    D = [i for i in strata["defective"] if all(len(fams[f].get(i, {})) == K for f in fams)]
    C = [i for i in strata["correct"] if all(len(fams[f].get(i, {})) == K for f in fams)]
    counts = {f: {i: sum(fams[f][i].values()) for i in D + C} for f in fams}

    out["families"] = {}
    for f in fams:
        fam: dict = {}
        for label, ids in (("recall", D), ("false_positive", C)):
            ks = [counts[f][i] for i in ids]
            curve = rc.union_curve(ks, K)
            fam[f"{label}_curve_pct"] = [round(100 * x, 2) for x in curve]
            fam[f"{label}_at_K"] = {str(Kk): rate({i: union_value(counts[f][i], Kk) for i in ids})
                                    for Kk in (1, K)}
        gain = {i: union_value(counts[f][i], K) - union_value(counts[f][i], K - 1) for i in D}
        lo, hi = rc.cluster_bootstrap_ci(by_cluster(gain), REPS, SEED)
        fam["flattening_gain_K7_to_K8_points"] = {
            "point": round(100 * sum(gain.values()) / len(gain), 2),
            "ci": [round(100 * lo, 2), round(100 * hi, 2)]}
        out["families"][f] = fam

    # H3 at K = 8: per instance, flagged by any self reading minus flagged by any cross reading.
    signed8 = defaultdict(list)
    for i in D:
        signed8[problem(i)].append(int(counts["self"][i] > 0) - int(counts["cross"][i] > 0))
    pdiff = rc.paired_difference(dict(signed8), reps=REPS, seed=SEED)
    out["self_minus_cross_K8"] = {
        "delta_points": round(100 * pdiff["delta"], 1),
        "ci": [round(100 * x, 1) for x in pdiff["ci95"]],
        "b_self_only": pdiff["b"], "c_cross_only": pdiff["c"],
        "one_signed_discordance": pdiff["one_signed_discordance"],
        "tango_ci": [round(100 * x, 1) for x in pdiff["tango_ci95"]] if pdiff["tango_ci95"] else None,
        "p_exact_mcnemar": pdiff["p_exact"],
        "p_signflip_cluster": pdiff["p_signflip_cluster"]}
    # Beside it, K = 1: the mean single-reading flag rate difference (sampling differs by family).
    v1 = {i: union_value(counts["self"][i], 1) - union_value(counts["cross"][i], 1) for i in D}
    lo, hi = rc.cluster_bootstrap_ci(by_cluster(v1), REPS, SEED)
    out["self_minus_cross_K1_mean"] = {
        "delta_points": round(100 * sum(v1.values()) / len(v1), 1),
        "ci": [round(100 * lo, 1), round(100 * hi, 1)],
        "p_signflip_cluster": rc.signflip_p(by_cluster(v1))}
    pooled = {label: rate({i: float(counts["cross"][i] + counts["self"][i] > 0) for i in ids})
              for label, ids in (("recall", D), ("false_positive", C))}
    out["pooled_two_family_union_16"] = pooled
    out["residual"] = sorted(i for i in D if counts["cross"][i] + counts["self"][i] == 0)
    out["residual_n"] = len(out["residual"])
    out["residual_problems"] = len({problem(i) for i in out["residual"]})
    text = json.dumps(out, indent=1, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
