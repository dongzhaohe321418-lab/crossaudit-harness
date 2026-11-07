"""Registered analysis for E1/E2 (PREREGISTRATION-E1.md, "Hypotheses", "E2" and Amendment 2). Frozen before
test audits.

Missing data (Amendment 2): an arm's union is taken over its valid readings and is missing only if the arm has
none; the two-reading original-arm value averages the six two-reading subsets whose readings are both valid;
an item's pooled value is the mean over the auditors whose contrast exists, and the item is dropped only if no
auditor's contrast exists. Bootstrap percentile convention: with the B sorted draws indexed from 0, the
interval is [draw floor(0.025 B), draw ceil(0.975 B) - 1].

    python benchmarks/code/icml/analyse_e1.py --split test [--out records/icml/e1_results_test.json]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e1  # noqa: E402

AUDITORS = e1.PRIMARY_AUDITORS
B, SEED = 10000, 20261110


def readings_table(split: str, admitted_only: bool = True):
    status = e1.completeness(split)
    problems = {p.problem_id: p for p in e1.load_problems()}
    items = {i["item_id"]: i for i in json.loads(e1.ITEMS_PATH.read_text()) if i["split"] == split}
    cons = e1.admitted_constructions()
    if admitted_only:
        items = {k: v for k, v in items.items() if k in cons}
    wit = {r["input_sha256"]: r for r in e1.load(e1.WIT_PATH) if not r.get("infra")}
    table: dict = {}
    for r in e1.load(e1.AUD_PATH):
        if not r.get("ok") or r["item_id"] not in items:
            continue
        key = (r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"])
        item = items[r["item_id"]]
        w = wit[e1.witness_key(r, item, problems[item["problem_id"]])] if r.get("witnesses") else {}
        table[key] = {"flag": bool(r["flagged"]), "any": bool(r.get("any_finding")),
                      "vd": bool(r["flagged"] and w.get("verified_diagnosis")),
                      "wd": bool(r["flagged"] and w.get("disagreement"))}
    return items, table, status


def union(table, iid, kind, arm, auditor, readings, metric, complete=False):
    """Union over the valid readings among `readings` (all of them required when `complete`)."""
    vals = [table.get((iid, kind, arm, auditor, k)) for k in readings]
    if complete and any(v is None for v in vals):
        return None
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return float(any(v[metric] for v in vals))


def arm_value(table, iid, kind, arm, auditor, metric, size):
    """C2/P2: both readings; O4: all four; O2: mean over the six two-subsets of the four."""
    if arm == "orig" and size == 2:
        vals = [union(table, iid, kind, "orig", auditor, s, metric, complete=True)
                for s in itertools.combinations(range(4), 2)]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None
    return union(table, iid, kind, arm, auditor, range(e1.READINGS[arm]), metric)


def item_values(items, table, kind, a, sa, b, sb, metric, auditors):
    """Per item: mean over the auditors whose contrast exists; an item with no auditor's contrast is dropped."""
    out = {}
    for iid in items:
        diffs = []
        for au in auditors:
            va = arm_value(table, iid, kind, a, au, metric, sa)
            vb = arm_value(table, iid, kind, b, au, metric, sb)
            if va is not None and vb is not None:
                diffs.append(va - vb)
        if diffs:
            out[iid] = sum(diffs) / len(diffs)
    return out


def level_values(items, table, kind, arm, size, metric, auditors):
    out = {}
    for iid in items:
        vals = [v for v in (arm_value(table, iid, kind, arm, au, metric, size) for au in auditors) if v is not None]
        if vals:
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
    out = {"est": 100 * est, "lo": 100 * draws[int(0.025 * b)], "hi": 100 * draws[int(0.975 * b) - 1],
           "n_items": len(values), "n_problems": len(probs)}
    if all(sum(by_problem[q]) == 0 and all(v == 0 for v in by_problem[q]) for q in probs) or \
            all(abs(sum(by_problem[q]) / len(by_problem[q])) == 0 for q in probs):
        # every problem-level contrast is zero (registered wording), including +1/-1 cancelling within a problem
        # Amendment 4 (B7): the percentile interval collapses to [0, 0]; report, as a sensitivity that does not change
        # the H2/H4 verdict rules, the exact one-sided 95% upper bound for a problem-level event probability with
        # zero events in n problems, 1 - 0.05 ** (1 / n)
        out["exact_upper95_if_all_zero"] = 100 * (1 - 0.05 ** (1 / len(probs)))
    return out


def contrast(items, table, kind, a, sa, b, sb, metric, auditors=AUDITORS):
    return cluster_boot(item_values(items, table, kind, a, sa, b, sb, metric, auditors), items)


def subset_items(items, gen):
    return {k: v for k, v in items.items() if v["generator"] == gen}


CONTRASTS = {  # name: (kind, arm a, size a, arm b, size b, metric)
    "H1_vd_clause_minus_placebo": ("defective", "clause", 2, "placebo", 2, "vd"),
    "H2_flag_correct_clause_minus_placebo": ("correct", "clause", 2, "placebo", 2, "flag"),
    "H3_vd_clause2_minus_orig4": ("defective", "clause", 2, "orig", 4, "vd"),
    "H4_vd_placebo2_minus_orig2": ("defective", "placebo", 2, "orig", 2, "vd"),
    "H5_vd_clause_minus_pointer": ("defective", "clause", 2, "pointer", 2, "vd"),
}


def analyse(split: str) -> dict:
    items, table, status = readings_table(split)
    res = {"split": split, "n_items": len(items), "n_problems": len({v["problem_id"] for v in items.values()}),
           "readings_valid": len(table), "completeness": status}
    for name, (kind, a, sa, b, sb, metric) in CONTRASTS.items():
        res[name] = contrast(items, table, kind, a, sa, b, sb, metric)
    h = res
    res["verdicts"] = {
        "H1": h["H1_vd_clause_minus_placebo"] and h["H1_vd_clause_minus_placebo"]["lo"] > 0,
        "H1_substantive": h["H1_vd_clause_minus_placebo"] and h["H1_vd_clause_minus_placebo"]["est"] >= 5,
        "H2": h["H2_flag_correct_clause_minus_placebo"] and h["H2_flag_correct_clause_minus_placebo"]["hi"] < 10,
        "H3": h["H3_vd_clause2_minus_orig4"] and h["H3_vd_clause2_minus_orig4"]["lo"] > 0,
        "H4": h["H4_vd_placebo2_minus_orig2"] and -5 <= h["H4_vd_placebo2_minus_orig2"]["lo"]
              and h["H4_vd_placebo2_minus_orig2"]["hi"] <= 5,
        "H5": h["H5_vd_clause_minus_pointer"] and h["H5_vd_clause_minus_pointer"]["lo"] > 0,
    }
    res["descriptive"] = {
        "vd_pointer_minus_placebo": contrast(items, table, "defective", "pointer", 2, "placebo", 2, "vd"),
        "flag_correct_pointer_minus_placebo": contrast(items, table, "correct", "pointer", 2, "placebo", 2, "flag"),
    }
    levels = {}
    for kind, metric in (("defective", "vd"), ("defective", "wd"), ("defective", "flag"), ("correct", "flag")):
        for arm, size in (("orig", 2), ("orig", 4), ("clause", 2), ("placebo", 2), ("pointer", 2)):
            levels[f"{kind}|{metric}|{arm}{size}"] = cluster_boot(
                level_values(items, table, kind, arm, size, metric, AUDITORS), items)
    res["levels"] = levels
    sec = {}
    subsets = {au: (items, [au]) for au in AUDITORS}
    subsets.update({g: (subset_items(items, g), AUDITORS) for g in e1.GENERATORS})
    for name, (sub, aus) in subsets.items():
        sec[name] = {}
        for cname, (kind, a, sa, b, sb, metric) in CONTRASTS.items():
            sec[name][cname] = contrast(sub, table, kind, a, sa, b, sb, metric, aus)
            if kind == "defective":
                for alt in ("flag", "wd"):
                    sec[name][cname.replace("_vd_", f"_{alt}_")] = contrast(sub, table, kind, a, sa, b, sb, alt, aus)
    for cname, (kind, a, sa, b, sb, metric) in CONTRASTS.items():
        if kind == "defective":
            for alt in ("flag", "wd"):
                sec.setdefault("pooled_alt_metrics", {})[cname.replace("_vd_", f"_{alt}_")] = contrast(
                    items, table, kind, a, sa, b, sb, alt)
    gen_ctl = {k: v for k, v in items.items() if v.get("control_source") in ("same", "other")}
    sec["H2_generated_controls_only"] = contrast(gen_ctl, table, "correct", "clause", 2, "placebo", 2, "flag")
    sec["correct_flag_by_control_source"] = {
        src: cluster_boot(level_values({k: v for k, v in items.items() if v.get("control_source") == src},
                                       table, "correct", "orig", 4, "flag", AUDITORS), items)
        for src in ("same", "other", "reference")}
    res["secondary"] = sec
    # Amendment 4 item 8: witness bridge (requires complete, current classifications)
    e1.bridge_complete(split)
    bc = e1.bridge_classes()
    per_item: dict = {}
    for (iid, _call), cl in bc.items():
        if iid in items:
            per_item.setdefault(iid, []).append(cl)
    res["bridge"] = {"items_with_verified_diagnosis": len(per_item),
                     "with_determined_witness": sum("DETERMINED" in v for v in per_item.values()),
                     "not_established_contract_independent": sum("DETERMINED" not in v for v in per_item.values()),
                     "witness_classes": {c: sum(v.count(c) for v in per_item.values())
                                         for c in e1.TAX2_CLASSES + ("DISPUTED",)},
                     "by_item_class": {c: {"items": sum(1 for k in per_item if tax.get(k) == c),
                                           "with_determined": sum(1 for k, v in per_item.items()
                                                                  if tax.get(k) == c and "DETERMINED" in v)}
                                       for c in e1.TAX2_CLASSES + ("DISPUTED",)}}
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
                                        else "flag", complete=True) for s in itertools.combinations(range(4), K)]
                            us = [u for u in us if u is not None]
                            if us:
                                vals.append(sum(us) / len(us))
                        return 100 * sum(vals) / len(vals) if vals else None
                    curve.append({"K": K, "defective": rate("defective"), "correct": rate("correct")})
                e2[f"{au}|{g}|{rule}"] = curve
    res["E2"] = e2
    return res


def two_group_boot(values: dict, groups: dict, g1: str, g2: str, items: dict, seed=SEED, b=B):
    """mean(g1) - mean(g2) over items, resampling problems with all their items."""
    by_problem: dict = {}
    for iid, v in values.items():
        if groups.get(iid) in (g1, g2):
            by_problem.setdefault(items[iid]["problem_id"], []).append((groups[iid], v))

    def diff(rows):
        a = [v for g, v in rows if g == g1]
        c = [v for g, v in rows if g == g2]
        return None if not a or not c else sum(a) / len(a) - sum(c) / len(c)
    allrows = [r for rs in by_problem.values() for r in rs]
    est = diff(allrows)
    if est is None:
        return None
    rng = random.Random(seed)
    probs = list(by_problem)
    draws = []
    for _ in range(b):
        d = diff([r for p in (rng.choice(probs) for _ in probs) for r in by_problem[p]])
        if d is not None:
            draws.append(d)
    draws.sort()
    n = len(draws)
    return {"est": 100 * est, "lo": 100 * draws[int(0.025 * n)], "hi": 100 * draws[math.ceil(0.975 * n) - 1],
            "n_g1": sum(1 for g, _ in allrows if g == g1), "n_g2": sum(1 for g, _ in allrows if g == g2),
            "valid_draws": n}


def analyse_taxonomy(split: str) -> dict:
    """Amendment 3: original-arm rates by what the task's words say about the first failing input (all selected
    items), and H6: four-reading verified diagnosis on DETERMINED items exceeds that on OPEN items."""
    items, table, status = readings_table(split, admitted_only=False)
    tax = e1.taxonomy2()           # Amendment 4: taxonomy v4
    unclassified = [k for k in items if k not in tax]
    if unclassified:      # A4 B6: every selected item needs both classifications; nothing is dropped silently
        raise SystemExit(f"{len(unclassified)} selected items lack two taxonomy classifications")
    cons = e1.admitted_constructions()
    res = {"split": split, "n_items": len(items), "class_counts": {}, "completeness": status}
    for c in e1.TAX2_CLASSES + ("DISPUTED",):
        res["class_counts"][c] = sum(1 for k in items if tax[k] == c)
    res["admitted_by_class"] = {c: sum(1 for k in items if tax[k] == c and k in cons)
                                for c in e1.TAX2_CLASSES + ("DISPUTED",)}
    votes: dict = {}
    for r in e1.load(e1.TAX2_PATH):
        if r.get("ok") and r["item_id"] in items:
            votes.setdefault(r["item_id"], {})[r["adjudicator"]] = r["class"]
    pairs = [tuple(v[a] for a in e1.ADJUDICATORS) for v in votes.values() if len(v) == 2]
    if pairs:
        po = sum(x == y for x, y in pairs) / len(pairs)
        pe = sum((sum(x == c for x, _ in pairs) / len(pairs)) * (sum(y == c for _, y in pairs) / len(pairs))
                 for c in e1.TAX2_CLASSES)
        res["agreement"] = {"n": len(pairs), "observed": po, "kappa": (po - pe) / (1 - pe) if pe < 1 else None}
    levels = {}
    for c in e1.TAX2_CLASSES + ("DISPUTED",):
        sub = {k: v for k, v in items.items() if tax[k] == c}
        for kind, metric in (("defective", "vd"), ("defective", "wd"), ("defective", "flag"), ("correct", "flag")):
            levels[f"{c}|{kind}|{metric}|orig4"] = cluster_boot(
                level_values(sub, table, kind, "orig", 4, metric, AUDITORS), sub)
    res["levels"] = levels
    vd = level_values(items, table, "defective", "orig", 4, "vd", AUDITORS)
    fl = level_values(items, table, "defective", "orig", 4, "flag", AUDITORS)
    res["H6_vd_orig4_determined_minus_open"] = two_group_boot(vd, tax, "DETERMINED", "OPEN", items)
    res["verdicts"] = {"H6": bool(res["H6_vd_orig4_determined_minus_open"]
                                  and res["H6_vd_orig4_determined_minus_open"]["lo"] > 0)}
    # A4 B6: the full registered secondary matrix: {vd, flag} x {DETERMINED-OPEN, DETERMINED-AT_ODDS} x
    # {pooled, each auditor}, with effective counts in every cell
    sec = {}
    for metric in ("vd", "flag"):
        for other in ("OPEN", "AT_ODDS"):
            for who in ["pooled"] + AUDITORS:
                aus = AUDITORS if who == "pooled" else [who]
                vals = level_values(items, table, "defective", "orig", 4, metric, aus)
                sec[f"{metric}|DETERMINED-{other}|{who}"] = two_group_boot(vals, tax, "DETERMINED", other, items)
    res["secondary"] = sec
    # Amendment 4 item 8: witness bridge (requires complete, current classifications)
    e1.bridge_complete(split)
    bc = e1.bridge_classes()
    per_item: dict = {}
    for (iid, _call), cl in bc.items():
        if iid in items:
            per_item.setdefault(iid, []).append(cl)
    res["bridge"] = {"items_with_verified_diagnosis": len(per_item),
                     "with_determined_witness": sum("DETERMINED" in v for v in per_item.values()),
                     "not_established_contract_independent": sum("DETERMINED" not in v for v in per_item.values()),
                     "witness_classes": {c: sum(v.count(c) for v in per_item.values())
                                         for c in e1.TAX2_CLASSES + ("DISPUTED",)},
                     "by_item_class": {c: {"items": sum(1 for k in per_item if tax.get(k) == c),
                                           "with_determined": sum(1 for k, v in per_item.items()
                                                                  if tax.get(k) == c and "DETERMINED" in v)}
                                       for c in e1.TAX2_CLASSES + ("DISPUTED",)}}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default="")
    ap.add_argument("--taxonomy", action="store_true")
    a = ap.parse_args()
    if a.taxonomy:
        out = analyse_taxonomy(a.split)
        (e1.REC / f"e1_taxonomy_{a.split}.json").write_text(json.dumps(out, indent=1))
        print(json.dumps({k: out[k] for k in ("n_items", "class_counts", "admitted_by_class", "verdicts")},
                         indent=1))
        print(out["H6_vd_orig4_determined_minus_open"], out.get("agreement"))
        raise SystemExit(0)
    out = analyse(a.split)
    path = Path(a.out) if a.out else e1.REC / f"e1_results_{a.split}.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n_items", "n_problems", "readings_valid", "verdicts")}, indent=1))
    for k in CONTRASTS:
        print(k, out[k])
