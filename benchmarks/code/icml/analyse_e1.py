"""Registered analysis for E1/E2 (PREREGISTRATION-E1.md, "Hypotheses" and "E2"). Frozen before test audits.

    python benchmarks/code/icml/analyse_e1.py --split test [--out records/icml/e1_results_test.json]
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e1  # noqa: E402

AUDITORS = e1.PRIMARY_AUDITORS
B, SEED = 10000, 20261110


def readings_table(split: str):
    items = {i["item_id"]: i for i in json.loads(e1.ITEMS_PATH.read_text()) if i["split"] == split}
    cons = e1.admitted_constructions()
    items = {k: v for k, v in items.items() if k in cons}
    wit = {(r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"]): r for r in e1.load(e1.WIT_PATH)}
    table: dict = {}
    for r in e1.load(e1.AUD_PATH):
        if not r.get("ok") or r["item_id"] not in items:
            continue
        key = (r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"])
        w = wit.get(key, {})
        table[key] = {"flag": bool(r["flagged"]), "any": bool(r.get("any_finding")),
                      "vd": bool(r["flagged"] and w.get("verified_diagnosis")),
                      "wd": bool(r["flagged"] and w.get("disagreement"))}
    return items, table


def union(table, iid, kind, arm, auditor, readings, metric):
    vals = [table.get((iid, kind, arm, auditor, k)) for k in readings]
    if any(v is None for v in vals):
        return None
    return float(any(v[metric] for v in vals))


def arm_value(table, iid, kind, arm, auditor, metric, size):
    """C2/P2: both readings; O4: all four; O2: mean over the six two-subsets of the four."""
    if arm == "orig" and size == 2:
        vals = [union(table, iid, kind, "orig", auditor, s, metric) for s in itertools.combinations(range(4), 2)]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None
    n = 4 if arm == "orig" else 2
    return union(table, iid, kind, arm, auditor, range(n), metric)


def item_values(items, table, kind, a, sa, b, sb, metric, auditors):
    """Per item: mean over auditors of (value(a) - value(b)); items missing any value are dropped."""
    out = {}
    for iid in items:
        diffs = []
        for au in auditors:
            va = arm_value(table, iid, kind, a, au, metric, sa)
            vb = arm_value(table, iid, kind, b, au, metric, sb)
            if va is None or vb is None:
                break
            diffs.append(va - vb)
        else:
            out[iid] = sum(diffs) / len(diffs)
    return out


def level_values(items, table, kind, arm, size, metric, auditors):
    out = {}
    for iid in items:
        vals = [arm_value(table, iid, kind, arm, au, metric, size) for au in auditors]
        if all(v is not None for v in vals):
            out[iid] = sum(vals) / len(vals)
    return out


def cluster_boot(values: dict, items: dict, seed=SEED, b=B):
    by_problem: dict = {}
    for iid, v in values.items():
        by_problem.setdefault(items[iid]["problem_id"], []).append(v)
    probs = list(by_problem)
    if not probs:
        return None
    rng = random.Random(seed)
    est = sum(values.values()) / len(values)
    draws = []
    for _ in range(b):
        vs = [x for p in (rng.choice(probs) for _ in probs) for x in by_problem[p]]
        draws.append(sum(vs) / len(vs))
    draws.sort()
    return {"est": 100 * est, "lo": 100 * draws[int(0.025 * b)], "hi": 100 * draws[int(0.975 * b) - 1],
            "n_items": len(values), "n_problems": len(probs)}


def contrast(items, table, kind, a, sa, b, sb, metric, auditors=AUDITORS):
    return cluster_boot(item_values(items, table, kind, a, sa, b, sb, metric, auditors), items)


def subset_items(items, gen):
    return {k: v for k, v in items.items() if v["generator"] == gen}


def analyse(split: str) -> dict:
    items, table = readings_table(split)
    res = {"split": split, "n_items": len(items), "n_problems": len({v["problem_id"] for v in items.values()}),
           "readings_valid": len(table)}
    res["H1_vd_clause_minus_placebo"] = contrast(items, table, "defective", "clause", 2, "placebo", 2, "vd")
    res["H2_flag_correct_clause_minus_placebo"] = contrast(items, table, "correct", "clause", 2, "placebo", 2, "flag")
    res["H3_vd_clause2_minus_orig4"] = contrast(items, table, "defective", "clause", 2, "orig", 4, "vd")
    res["H4_vd_placebo2_minus_orig2"] = contrast(items, table, "defective", "placebo", 2, "orig", 2, "vd")
    h = res
    res["verdicts"] = {
        "H1": h["H1_vd_clause_minus_placebo"] and h["H1_vd_clause_minus_placebo"]["lo"] > 0,
        "H1_substantive": h["H1_vd_clause_minus_placebo"] and h["H1_vd_clause_minus_placebo"]["est"] >= 5,
        "H2": h["H2_flag_correct_clause_minus_placebo"] and h["H2_flag_correct_clause_minus_placebo"]["hi"] < 10,
        "H3": h["H3_vd_clause2_minus_orig4"] and h["H3_vd_clause2_minus_orig4"]["lo"] > 0,
        "H4": h["H4_vd_placebo2_minus_orig2"] and -5 <= h["H4_vd_placebo2_minus_orig2"]["lo"]
              and h["H4_vd_placebo2_minus_orig2"]["hi"] <= 5,
    }
    levels = {}
    for kind, metric in (("defective", "vd"), ("defective", "wd"), ("defective", "flag"), ("correct", "flag")):
        for arm, size in (("orig", 2), ("orig", 4), ("clause", 2), ("placebo", 2)):
            levels[f"{kind}|{metric}|{arm}{size}"] = cluster_boot(
                level_values(items, table, kind, arm, size, metric, AUDITORS), items)
    res["levels"] = levels
    sec = {}
    for au in AUDITORS:
        sec[au] = {"H1": contrast(items, table, "defective", "clause", 2, "placebo", 2, "vd", [au]),
                   "H2": contrast(items, table, "correct", "clause", 2, "placebo", 2, "flag", [au]),
                   "H3": contrast(items, table, "defective", "clause", 2, "orig", 4, "vd", [au]),
                   "flag_defective_clause_minus_placebo":
                       contrast(items, table, "defective", "clause", 2, "placebo", 2, "flag", [au])}
    for g in e1.GENERATORS:
        sub = subset_items(items, g)
        sec[g] = {"H1": contrast(sub, table, "defective", "clause", 2, "placebo", 2, "vd"),
                  "H2": contrast(sub, table, "correct", "clause", 2, "placebo", 2, "flag")}
    res["secondary"] = sec
    # E2: operating characteristics on the original arm, exact subset averaging over K = 1..4
    e2 = {}
    for au in AUDITORS:
        for g in e1.GENERATORS:
            sub = subset_items(items, g)
            for rule in ("flag", "any", "vd"):
                curve = []
                for K in range(1, 5):
                    def rate(kind):
                        vals = []
                        for iid in sub:
                            us = [union(table, iid, kind, "orig", au, s, rule if kind == "defective" or rule != "vd"
                                        else "flag") for s in itertools.combinations(range(4), K)]
                            us = [u for u in us if u is not None]
                            if us:
                                vals.append(sum(us) / len(us))
                        return 100 * sum(vals) / len(vals) if vals else None
                    curve.append({"K": K, "defective": rate("defective"), "correct": rate("correct")})
                e2[f"{au}|{g}|{rule}"] = curve
    res["E2"] = e2
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = analyse(a.split)
    path = Path(a.out) if a.out else e1.REC / f"e1_results_{a.split}.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n_items", "n_problems", "readings_valid", "verdicts")}, indent=1))
    for k in ("H1_vd_clause_minus_placebo", "H2_flag_correct_clause_minus_placebo", "H3_vd_clause2_minus_orig4",
              "H4_vd_placebo2_minus_orig2"):
        print(k, out[k])
