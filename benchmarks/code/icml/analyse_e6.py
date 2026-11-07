"""E6 analysis (CEILING_PROGRAM.md v3, section 3). Development use: calibrate the deployable policy, describe the
pilot, and estimate the problem-level variance for the power simulation. No model calls.

Cells. A unit (one problem) has programs a and b (implementations of rules A and B) and contracts A and B.
Under contract X, program X is correct and the other program is defective.
- Unrevealed arms (none, menu): the same readings are scored under both contracts (Lemma: flag TPR = FPR).
- resolve-X: contract X only.
Per (unit, config, arm, program), the deployable policy flags when at least t of the k readings flag; its verified
diagnosis is any verified witness among the readings that flag (scored against the contract's oracle).

    python benchmarks/code/icml/analyse_e6.py --split dev
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics

import e1
import e6

B, SEED = 10000, 20261113


def table(split: str):
    aud = [r for r in e1.load(e6.AUD) if r.get("ok") and r["split"] == split]
    wit = {}
    for r in e1.load(e6.WIT):
        if not r.get("infra"):
            wit[(tuple(r["key"]), r["contract"])] = r["verified_diagnosis"]
    cells: dict = {}
    for r in aud:
        pid, prog, arm, cfg, k = r["key"]
        vd = {c: bool(r["flagged"] and wit.get((tuple(r["key"]), c), False)) for c in "ab"}
        cells.setdefault((pid, prog, arm, cfg), []).append({"flag": bool(r["flagged"]), "vd": vd})
    return cells


def policy(readings: list, t: int) -> tuple[bool, dict]:
    flags = [x["flag"] for x in readings]
    flag = sum(flags) >= t
    vd = {c: flag and any(x["vd"][c] for x in readings) for c in "ab"}
    return flag, vd


def unit_values(cells, units, arm_group: str, cfgs, t: int) -> dict:
    """Per unit: tpr, fpr (flag), cov (verified diagnosis on defective cells), averaged over configurations."""
    out = {}
    for pid in units:
        vals = []
        for cfg in cfgs:
            def cell(prog, arm):
                rs = cells.get((pid, prog, arm, cfg))
                return policy(rs, t) if rs else None
            if arm_group == "resolve":
                ca, cb = cell("a", "resolve-a"), cell("b", "resolve-b")      # correct programs
                da, db = cell("b", "resolve-a"), cell("a", "resolve-b")      # defective programs
                if None in (ca, cb, da, db):
                    continue
                vals.append({"tpr": (da[0] + db[0]) / 2, "fpr": (ca[0] + cb[0]) / 2,
                             "cov": (da[1]["a"] + db[1]["b"]) / 2})
            else:
                pa, pb = cell("a", arm_group), cell("b", arm_group)
                if None in (pa, pb):
                    continue
                f = (pa[0] + pb[0]) / 2
                vals.append({"tpr": f, "fpr": f, "cov": (pa[1]["b"] + pb[1]["a"]) / 2,
                             "r_b": float(pa[1]["b"]), "r_a": float(pb[1]["a"]),
                             "flag_a": float(pa[0]), "flag_b": float(pb[0])})
        if vals:
            out[pid] = {k: statistics.mean(v[k] for v in vals) for k in vals[0]}
    return out


def boot(values: dict, seed=SEED, b=B) -> dict | None:
    xs = list(values.values())
    if not xs:
        return None
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choice(xs) for _ in xs) for _ in range(b))
    return {"est": 100 * statistics.mean(xs), "lo": 100 * draws[math.floor(0.025 * b)],
            "hi": 100 * draws[math.ceil(0.975 * b) - 1], "n": len(xs),
            "sd_unit": 100 * (statistics.stdev(xs) if len(xs) > 1 else 0.0)}


def analyse(split: str) -> dict:
    cells = table(split)
    units = sorted(e6.units(split))
    res = {"split": split, "n_units": len(units), "readings": sum(len(v) for v in cells.values())}
    cfg_sets = {"all": e6.CONFIGS, **{c: (c,) for c in e6.CONFIGS}}
    for t in (1, 2):
        lv = {}
        for name, cfgs in cfg_sets.items():
            for arm in ("none", "menu", "resolve"):
                uv = unit_values(cells, units, arm, cfgs, t)
                for m in ("tpr", "fpr", "cov"):
                    lv[f"t{t}|{name}|{arm}|{m}"] = boot({k: v[m] for k, v in uv.items()})
        res[f"levels_t{t}"] = lv
        r = unit_values(cells, units, "resolve", e6.CONFIGS, t)
        m = unit_values(cells, units, "menu", e6.CONFIGS, t)
        n = unit_values(cells, units, "none", e6.CONFIGS, t)
        res[f"E6_1_cov_resolve_minus_menu_t{t}"] = boot({k: r[k]["cov"] - m[k]["cov"] for k in r if k in m})
        res[f"J_resolve_t{t}"] = boot({k: r[k]["tpr"] - r[k]["fpr"] for k in r})
        res[f"E6_2_convention_advantage_none_t{t}"] = boot({k: (v["r_b"] - v["r_a"]) / 2 for k, v in n.items()})
        res[f"flag_pref_a_minus_b_none_t{t}"] = boot({k: v["flag_a"] - v["flag_b"] for k, v in n.items()})
        hi = [c for c in e6.CONFIGS if c.endswith("high")]
        lo = [c for c in e6.CONFIGS if c.endswith("low")]
        rh, rl = unit_values(cells, units, "resolve", hi, t), unit_values(cells, units, "resolve", lo, t)
        res[f"E6_3_cov_high_minus_low_resolve_t{t}"] = boot({k: rh[k]["cov"] - rl[k]["cov"] for k in rh if k in rl})
    return res


def power_table(sd_points: float) -> dict:
    """Problems needed for 80% power, two-sided 5%, at effects of 10, 15 and 20 points (normal approximation)."""
    z = 1.959964 + 0.841621
    return {f"{d}pt": math.ceil((z * sd_points / d) ** 2) for d in (10, 15, 20)} if sd_points else {}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    a = ap.parse_args()
    out = analyse(a.split)
    for key in ("E6_1_cov_resolve_minus_menu_t1", "E6_2_convention_advantage_none_t1"):
        if out.get(key):
            out[f"power_{key}"] = power_table(out[key]["sd_unit"])
    (e1.REC / f"e6_results_{a.split}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("levels")}, indent=1))
