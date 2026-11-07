"""Registered E3 analysis (PREREGISTRATION-E3.md). Scores by code against the manifest; no model calls.

    python benchmarks/ai4s_e3/score_e3.py --split test
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code" / "icml"))
import e1  # noqa: E402
from build_e3 import REC  # noqa: E402
from spec_e3 import DATASETS, FAULT_NAMES  # noqa: E402
from audit_e3 import current  # noqa: E402

AUDITORS = ["aud-gpt-terra", "aud-claude-sonnet"]
B, SEED = 10000, 20261112


def model_scores(reply: dict, item: dict) -> tuple[bool, bool]:
    blockers = [f for f in (reply.get("findings") or []) if f.get("severity") == "BLOCKER"]
    flag = bool(blockers)
    if item["fault"] is None:
        return flag, False
    want = FAULT_NAMES[item["fault"]]
    p = item["params"]
    target_cols = set(p.get("columns") or ([p["column"]] if "column" in p else []))
    loc = any(f.get("fault_type") == want and (item["fault"] == "F3" or target_cols & set(f.get("columns") or []))
              for f in blockers)
    return flag, loc


def validator_scores(checks: list[str], item: dict) -> tuple[bool, bool]:
    flag = bool(checks)
    if item["fault"] is None:
        return flag, False
    f, p = item["fault"], item["params"]
    col = p.get("column")
    cols = set(p.get("columns") or [])
    tgt = DATASETS[item["dataset"]]["target"]

    def names(c):
        return c.split(":")[-1]
    if f in ("F1", "F6"):
        loc = any(c.split(":")[0] in ("sentinel", "negative", "range") and names(c) == col
                  or c == f"profile:oop:{col}" for c in checks)
    elif f == "F2":
        loc = f"negative:{col}" in checks
    elif f == "F3":
        loc = "duplicates" in checks
    elif f == "F4":
        loc = any(c.startswith("profile:corr:") for c in checks) or f"profile:med:{tgt}" in checks
    elif f == "F5":
        loc = any(names(c) in cols for c in checks)
    else:
        loc = f"integer:{col}" in checks
    return flag, loc


def table(split: str):
    items = {i["item"]: i for i in json.loads((REC / "items.json").read_text())["items"] if i["split"] == split}
    reads: dict = {}
    for r in e1.load(REC / "audits.jsonl"):
        if r.get("ok") and r["item"] in items and current(r):
            reads[(r["item"], r["mode"], r["auditor"], r["reading"])] = model_scores(r["reply"], items[r["item"]])
    return items, reads


def per_item(items, reads, mode, metric, validator=None, auditors=AUDITORS):
    """Item value: mean over the auditors with at least one valid reading of (validator OR union over that
    auditor's valid readings), on flag (0) or localised (1); amendment 1."""
    out = {}
    idx = 0 if metric == "flag" else 1
    for iid, it in items.items():
        vals = []
        for au in auditors:
            keys = [k for k in ((iid, mode, au, r) for r in range(1 if mode == "agentic" else 2)) if k in reads]
            if not keys:
                continue
            m = any(reads[k][idx] for k in keys)
            v = validator_scores(it[validator], it)[idx] if validator else False
            vals.append(float(m or v))
        if vals:
            out[iid] = sum(vals) / len(vals)
    return out


def boot(diff: dict, items: dict):
    by_ds: dict = {}
    for iid, v in diff.items():
        by_ds.setdefault(items[iid]["dataset"], []).append(v)
    if not by_ds:
        return None
    rng = random.Random(SEED)
    ds = list(by_ds)
    est = sum(diff.values()) / len(diff)
    draws = []
    for _ in range(B):
        vs = []
        for d in (rng.choice(ds) for _ in ds):
            xs = by_ds[d]
            vs += [rng.choice(xs) for _ in xs]
        draws.append(sum(vs) / len(vs))
    draws.sort()
    return {"est": 100 * est, "lo": 100 * draws[int(0.025 * B)], "hi": 100 * draws[int(0.975 * B) - 1],
            "n_items": len(diff), "n_datasets": len(ds)}


def validator_only(items, validator, metric):
    idx = 0 if metric == "flag" else 1
    return {iid: float(validator_scores(it[validator], it)[idx]) for iid, it in items.items()}


def analyse(split: str) -> dict:
    items, reads = table(split)
    faulty = {k: v for k, v in items.items() if v["fault"]}
    clean = {k: v for k, v in items.items() if not v["fault"]}
    res = {"split": split, "n_faulty": len(faulty), "n_clean": len(clean), "readings_ok": len(reads)}
    expected = {(iid, m, au, r) for iid, it in items.items() for au in AUDITORS
                for m, n in (("agentic", 1), ("reading", 2)) if m == "agentic" or it["size"] == 120
                for r in range(n)}
    res["missing_by_mode_auditor"] = {f"{m}|{au}": sum(1 for k in expected - set(reads) if k[1] == m and k[2] == au)
                                      for m in ("agentic", "reading") for au in AUDITORS}

    def gain(sub, metric, mode="agentic", validator="profile_validator", auditors=AUDITORS):
        u = per_item(sub, reads, mode, metric, validator, auditors)
        v = validator_only(sub, validator, metric)
        return boot({k: u[k] - v[k] for k in u}, sub)
    res["H1_loc_union_minus_profile"] = gain(faulty, "loc")
    res["H2_cleanflag_union_minus_profile"] = gain(clean, "flag")
    res["H3_loc_gain_12000"] = gain({k: v for k, v in faulty.items() if v["size"] == 12000}, "loc")
    small = {k: v for k, v in faulty.items() if v["size"] == 120}
    ag, rd = per_item(small, reads, "agentic", "loc"), per_item(small, reads, "reading", "loc")
    res["H4_agentic_minus_reading_loc_120"] = boot({k: ag[k] - rd[k] for k in ag if k in rd}, small)
    v = res
    res["verdicts"] = {"H1": bool(v["H1_loc_union_minus_profile"] and v["H1_loc_union_minus_profile"]["lo"] > 0),
                       "H2": bool(v["H2_cleanflag_union_minus_profile"] and v["H2_cleanflag_union_minus_profile"]["hi"] < 10),
                       "H3": bool(v["H3_loc_gain_12000"] and v["H3_loc_gain_12000"]["lo"] > 0),
                       "H4": bool(v["H4_agentic_minus_reading_loc_120"] and v["H4_agentic_minus_reading_loc_120"]["lo"] > 0)}
    levels = {}
    for name, sub in (("faulty", faulty), ("clean", clean)):
        for metric in ("flag", "loc"):
            if name == "clean" and metric == "loc":
                continue
            levels[f"{name}|{metric}|profile"] = boot(validator_only(sub, "profile_validator", metric), sub)
            levels[f"{name}|{metric}|card"] = boot(validator_only(sub, "card_validator", metric), sub)
            for mode in ("agentic", "reading"):
                levels[f"{name}|{metric}|model_{mode}"] = boot(per_item(sub, reads, mode, metric), sub)
                levels[f"{name}|{metric}|union_profile_{mode}"] = boot(per_item(sub, reads, mode, metric, "profile_validator"), sub)
    res["levels"] = levels
    by_fault = {}
    for f in FAULT_NAMES:
        sub = {k: v for k, v in faulty.items() if v["fault"] == f}
        by_fault[f] = {"profile_loc": boot(validator_only(sub, "profile_validator", "loc"), sub),
                       "model_agentic_loc": boot(per_item(sub, reads, "agentic", "loc"), sub),
                       "union_loc": boot(per_item(sub, reads, "agentic", "loc", "profile_validator"), sub)}
    res["by_fault"] = by_fault
    res["per_auditor"] = {au: {"H1": gain(faulty, "loc", auditors=[au]), "H2": gain(clean, "flag", auditors=[au])}
                          for au in AUDITORS}
    res["card_instead"] = {"loc_gain": gain(faulty, "loc", validator="card_validator"),
                           "cleanflag_gain": gain(clean, "flag", validator="card_validator")}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    out = analyse(a.split)
    (REC / f"e3_results_{a.split}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n_faulty", "n_clean", "readings_ok", "verdicts")}, indent=1))
    for k in ("H1_loc_union_minus_profile", "H2_cleanflag_union_minus_profile", "H3_loc_gain_12000",
              "H4_agentic_minus_reading_loc_120"):
        print(k, out[k])
