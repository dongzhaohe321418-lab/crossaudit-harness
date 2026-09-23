#!/usr/bin/env python3
"""A4S-2 analysis, the outcomes registered in `PREREGISTRATION-RESULTS.md` (Amendments 1-3).

Three auditors on the same items: the LLM (`cross`, flag = a model BLOCKER; union over the K = 4
draws, exact subset averaging for K < 4), the shipped `science` profile (flag = a hard failure in
the same run_audit call), and re-execution (`records/ai4s/results_reexec.json`). Per auditor and for
the unions LLM+DCL and LLM+re-execution: recall by fault type and overall on faulty items, and
false positives on clean items. Intervals: problem-cluster percentile bootstrap, 10,000, seed
20260927. The registration's "McNemar-type comparisons within instance" is computed two ways and
both are reported: (a) exact McNemar between two auditors on the faulty items; (b) per auditor,
within instance, faulty-flagged-and-clean-not against clean-flagged-and-faulty-not, exact binomial.

    python benchmarks/ai4s/analyze_results.py --out benchmarks/code/records/ai4s/results_results.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import defaultdict
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AI4S = Path.home() / "Documents/Crossaudit/ai4s"
RUNS = AI4S / "runs/results_audit"
MANIFEST = REPO / "benchmarks/code/records/ai4s/results_items.json"
REEXEC = REPO / "benchmarks/code/records/ai4s/results_reexec.json"
K_MAX = 4
SEED = 20260927
B = 10_000
FAULTS = ["R1", "R2", "R3", "R4", "R5", "F1", "F4"]


def union_at_k(flags: list[bool], k: int) -> float:
    subs = list(itertools.combinations(range(len(flags)), k))
    return sum(any(flags[i] for i in s) for s in subs) / len(subs)


def cluster_boot(vals: dict[str, list[float]], rng: random.Random) -> tuple[float, float]:
    import numpy as np
    gen = np.random.default_rng(rng.randrange(2**32))
    keys = list(vals)
    sums = np.array([sum(vals[k]) for k in keys], dtype=float)
    ns = np.array([len(vals[k]) for k in keys], dtype=float)
    idx = gen.integers(0, len(keys), size=(B, len(keys)))
    stats = np.sort(sums[idx].sum(axis=1) / ns[idx].sum(axis=1))
    return 100 * stats[int(0.025 * B)], 100 * stats[int(0.975 * B) - 1]


def rate(items: list[dict], val: dict[str, float]) -> dict:
    if not items:
        return {"n": 0}
    by: dict[str, list[float]] = defaultdict(list)
    for it in items:
        by[it["problem"]].append(val[it["item"]])
    point = 100 * sum(val[it["item"]] for it in items) / len(items)
    lo, hi = cluster_boot(by, random.Random(SEED))
    return {"n": len(items), "flagged": round(sum(val[it["item"]] for it in items), 2),
            "pct": round(point, 1), "ci": [round(lo, 1), round(hi, 1)]}


def exact_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = []
    for inst in man["instances"]:
        for e in inst["items"]:
            items.append({"item": e["item"], "instance": inst["instance"],
                          "problem": inst["instance"].split(".")[0], "kind": e["kind"],
                          "fault": e["fault"], "dcl_builder": e["dcl_hard_failures"]})
    reads: dict[str, dict[int, dict]] = defaultdict(dict)
    for d in range(1, K_MAX + 1):
        f = RUNS / f"cross.d{d}.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if r.get("ok"):
                        reads[r["instance_id"]][d] = r
    complete = [it for it in items if len(reads.get(it["item"], {})) == K_MAX]
    out: dict = {"n_items": len(items), "n_complete": len(complete),
                 "incomplete": sorted(it["item"] for it in items if it not in complete)[:20]}
    cset = {it["item"] for it in complete}
    # Keep an instance only if both of its items are complete, so the pairing holds.
    inst_ok = {i for i in {it["instance"] for it in complete}
               if all(x["item"] in cset for x in items if x["instance"] == i)}
    use = [it for it in items if it["instance"] in inst_ok]
    clean = [it for it in use if it["kind"] == "clean"]
    faulty = [it for it in use if it["kind"] == "faulty"]
    out["n_instances"] = len(inst_ok)

    llm_flags = {it["item"]: [reads[it["item"]][d]["flagged"] for d in range(1, K_MAX + 1)]
                 for it in use}
    dcl_read = {it["item"]: {reads[it["item"]][d]["dcl_hard_failures"] > 0 for d in range(1, K_MAX + 1)}
                for it in use}
    out["dcl_constant_across_draws"] = all(len(v) == 1 for v in dcl_read.values())
    dcl = {i: float(next(iter(v))) for i, v in dcl_read.items()}
    out["dcl_agrees_with_builder"] = all(
        dcl[it["item"]] == float(it["dcl_builder"] > 0) for it in use)
    rx = {r["item"]: float(r["flagged"]) for r in json.loads(REEXEC.read_text(encoding="utf-8"))}

    auditors: dict[str, dict[str, float]] = {}
    for k in range(1, K_MAX + 1):
        auditors[f"llm_k{k}"] = {i: union_at_k(f, k) for i, f in llm_flags.items()}
    llm = auditors[f"llm_k{K_MAX}"]
    auditors["dcl"] = dcl
    auditors["reexec"] = {it["item"]: rx[it["item"]] for it in use}
    auditors["llm_or_dcl"] = {i: float(llm[i] or dcl[i]) for i in llm}
    auditors["llm_or_reexec"] = {i: float(llm[i] or rx[i]) for i in llm}
    out["auditors"] = {}
    for name, val in auditors.items():
        out["auditors"][name] = {
            "recall": rate(faulty, val), "clean_fp": rate(clean, val),
            "by_fault": {f: rate([it for it in faulty if it["fault"] == f], val) for f in FAULTS}}

    # (a) auditor vs auditor on faulty items, exact McNemar, K = K_MAX union for the LLM.
    pairs = {}
    for a, b in (("llm_k4", "dcl"), ("llm_k4", "reexec"), ("dcl", "reexec")):
        va, vb = auditors[a], auditors[b]
        only_a = sum(1 for it in faulty if va[it["item"]] and not vb[it["item"]])
        only_b = sum(1 for it in faulty if vb[it["item"]] and not va[it["item"]])
        pairs[f"{a}_vs_{b}"] = {"only_first": only_a, "only_second": only_b,
                                "p_exact": round(exact_two_sided(only_a, only_b), 4)}
    out["mcnemar_between_auditors_on_faulty"] = pairs
    # (b) within instance, per auditor.
    within = {}
    for name in ("llm_k4", "dcl", "reexec"):
        v = auditors[name]
        b_ = c_ = 0
        for i in inst_ok:
            cl = next(it for it in clean if it["instance"] == i)
            fa = next(it for it in faulty if it["instance"] == i)
            b_ += bool(v[fa["item"]]) and not v[cl["item"]]
            c_ += bool(v[cl["item"]]) and not v[fa["item"]]
        within[name] = {"faulty_only": b_, "clean_only": c_, "p_exact": round(exact_two_sided(b_, c_), 6)}
    out["within_instance"] = within
    out["llm_flagged_clean_items"] = sorted(it["item"] for it in clean if llm[it["item"]])
    out["llm_missed_faulty_items"] = sorted(it["item"] for it in faulty if not llm[it["item"]])
    text = json.dumps(out, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
