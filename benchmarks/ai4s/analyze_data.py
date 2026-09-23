#!/usr/bin/env python3
"""A4S-3 analysis, exactly the outcomes registered in `PREREGISTRATION-DATA.md`.

Per family: union recall at K (exact average over all size-K subsets of the K_max draws) on
faulty items, by fault type and overall; the same union's false-positive rate on clean items;
intervals from a bootstrap over items within dataset (10,000, seed 20260926). The four-cluster
dataset bootstrap is not computed, as registered. Then the frozen validator's recall and false
positives, the union of the LLM with the validator, the faulty items only the LLM catches, and
localisation (a flagging BLOCKER text names the faulted column; case-insensitive substring).

Only readings with ok=true count; an item missing a draw is reported, never imputed.

    python benchmarks/ai4s/analyze_data.py            # all families present
    python benchmarks/ai4s/analyze_data.py --out records/ai4s/data_results.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AI4S = Path.home() / "Documents/Crossaudit/ai4s"
RUNS = AI4S / "runs/data_audit"
MANIFEST = REPO / "benchmarks/code/records/ai4s/data_items.json"
K_MAX = 4
SEED = 20260926
B = 10_000
FAULTS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]


def load_family(fam: str) -> dict[str, dict[int, dict]]:
    """item -> draw -> reading (ok readings only)."""
    out: dict[str, dict[int, dict]] = defaultdict(dict)
    for d in range(1, K_MAX + 1):
        f = RUNS / f"{fam}.d{d}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("ok"):
                    out[r["instance_id"]][d] = r
    return out


def union_at_k(flags: list[bool], k: int) -> float:
    """Exact probability that a random size-k subset of the draws contains a flag."""
    n = len(flags)
    subs = list(itertools.combinations(range(n), k))
    return sum(any(flags[i] for i in s) for s in subs) / len(subs)


def boot(values_by_ds: dict[str, list[float]], rng: random.Random) -> tuple[float, float]:
    """Percentile interval, resampling items within each dataset (numpy, seeded from rng)."""
    import numpy as np
    gen = np.random.default_rng(rng.randrange(2**32))
    groups = [np.asarray(v, dtype=float) for v in values_by_ds.values() if v]
    total = sum(len(g) for g in groups)
    sums = np.zeros(B)
    for g in groups:
        sums += g[gen.integers(0, len(g), size=(B, len(g)))].sum(axis=1)
    stats = np.sort(sums / total)
    return 100 * stats[int(0.025 * B)], 100 * stats[int(0.975 * B) - 1]


def rate(items: list[dict], val: dict[str, float], rng: random.Random) -> dict:
    by_ds: dict[str, list[float]] = defaultdict(list)
    for it in items:
        by_ds[it["dataset"]].append(val[it["item"]])
    n = len(items)
    point = 100 * sum(val[it["item"]] for it in items) / n if n else float("nan")
    lo, hi = boot(by_ds, rng) if n else (float("nan"), float("nan"))
    return {"n": n, "pct": round(point, 1), "ci": [round(lo, 1), round(hi, 1)]}


def names_column(texts: list[str], cols: list[str]) -> bool:
    low = " ".join(texts).lower()
    return any(c.lower() in low for c in cols)


def fault_columns(params: dict) -> list[str]:
    if "column" in params:
        return [params["column"]]
    return list(params.get("columns", []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    clean = [m for m in man if m["fault"] is None]
    faulty = [m for m in man if m["fault"]]
    result: dict = {"n_items": len(man), "families": {}}

    validator = {m["item"]: float(m["validator"]["flagged"]) for m in man}
    rng = random.Random(SEED)
    result["validator"] = {
        "clean_fp": rate(clean, validator, rng),
        "recall": rate(faulty, validator, rng),
        "by_fault": {f: rate([m for m in faulty if m["fault"] == f], validator, rng) for f in FAULTS},
    }

    for fam in ("cross", "self"):
        reads = load_family(fam)
        if not reads:
            continue
        complete = [m for m in man if len(reads.get(m["item"], {})) == K_MAX]
        missing = sorted(m["item"] for m in man if len(reads.get(m["item"], {})) < K_MAX)
        fam_out: dict = {"items_complete": len(complete), "items_incomplete": missing[:20],
                         "n_incomplete": len(missing), "by_k": {}}
        cset = {m["item"] for m in complete}
        cl = [m for m in clean if m["item"] in cset]
        fa = [m for m in faulty if m["item"] in cset]
        flags = {m["item"]: [reads[m["item"]][d]["flagged"] for d in range(1, K_MAX + 1)]
                 for m in complete}
        for k in range(1, K_MAX + 1):
            u = {i: union_at_k(f, k) for i, f in flags.items()}
            rng = random.Random(SEED)
            fam_out["by_k"][k] = {
                "recall": rate(fa, u, rng),
                "clean_fp": rate(cl, u, rng),
                "by_fault": {f: rate([m for m in fa if m["fault"] == f], u, rng) for f in FAULTS},
            }
        # K = K_MAX union: any draw flagged.
        anyflag = {i: float(any(f)) for i, f in flags.items()}
        both = {i: float(anyflag[i] or validator[i]) for i in anyflag}
        rng = random.Random(SEED)
        fam_out["union_with_validator"] = {
            "recall": rate(fa, both, rng), "clean_fp": rate(cl, both, rng),
            "by_fault": {f: rate([m for m in fa if m["fault"] == f], both, rng) for f in FAULTS}}
        only_llm = [m for m in fa if anyflag[m["item"]] and not validator[m["item"]]]
        fam_out["llm_only"] = {
            "n": len(only_llm),
            "by_fault": {f: sum(1 for m in only_llm if m["fault"] == f) for f in FAULTS},
            "validator_missed_by_fault": {f: sum(1 for m in fa if m["fault"] == f
                                                 and not validator[m["item"]]) for f in FAULTS},
            "items": [m["item"] for m in only_llm]}
        loc: dict[str, list[int]] = {f: [0, 0] for f in FAULTS if f != "F3"}
        for m in fa:
            if m["fault"] == "F3" or not anyflag[m["item"]]:
                continue
            texts = [t for d in range(1, K_MAX + 1) for t in reads[m["item"]][d]["blocker_texts"]]
            loc[m["fault"]][1] += 1
            loc[m["fault"]][0] += names_column(texts, fault_columns(m["params"]))
        fam_out["localisation"] = {f: {"named": a, "flagged": b} for f, (a, b) in loc.items()}
        fam_out["clean_flagged_items"] = sorted(m["item"] for m in cl if anyflag[m["item"]])
        result["families"][fam] = fam_out

    text = json.dumps(result, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
