"""E6 analysis, protocol e6-v4 (PREREGISTRATION-E6.md). No model calls.

Cells. A unit (one problem) has programs a and b (implementations of rules A and B) and contracts A and B. Under
contract X, program X is correct and the other program defective.
- Unrevealed arms (none, menu) are scored under both contracts with the same readings (balanced counterfactual
  scoring, not extra observations; Lemma: flag TPR = FPR).
- resolve-X and sentence-X reveal contract X.
Per (unit, program, arm, configuration) the deployable policy flags when at least t of its valid readings flag (two
scheduled; one if the other is exhausted). Its verified diagnosis is a target-discrepancy verified witness (valid
input, in the class, judged against the contract's oracle) among its flagging readings.
A unit's value is the equally weighted mean over the configurations of the arm; a unit missing any required cell
is excluded from that contrast and counted, with best and worst bounds reported.

    python benchmarks/code/icml/analyse_e6.py --split dev [--kind det] [--allow-incomplete]
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
VD_FIELD = "verified_diagnosis"   # sensitivity runs set "verified_refdomain" or "verified_offclass"
ALPHA_FPR = 0.10      # v4.1: budget for the resolved clean-flag rate, certified by a betting upper bound


def table(split: str) -> tuple[dict, dict]:
    aud = [r for r in e1.load(e6.AUD) if r["split"] == split and r.get("protocol") == e6.PROTOCOL]
    seen = set()
    for r in aud:
        if r.get("ok"):
            k = tuple(r["key"])
            if k in seen:
                raise SystemExit(f"duplicate valid reading {k}")
            seen.add(k)
    us = e6.units(split)
    probs = {p.problem_id: p for p in e6.problems(split)}
    wit = {}
    for r in e1.load(e6.WIT):
        if not r.get("infra"):
            prev = wit.get(r["input_sha256"])
            if prev is not None and any(prev.get(f) != r.get(f) for f in
                                        ("verified_diagnosis", "verified_refdomain", "verified_offclass")):
                raise SystemExit(f"conflicting witness scores {r['key']}")
            wit[r["input_sha256"]] = r
    cells: dict = {}
    for r in aud:
        if not r.get("ok"):
            continue
        pid, prog, arm, cfg, k = r["key"]
        if pid not in us:
            continue                                     # superseded unit
        vd = {}
        for c in "ab":
            if r["flagged"] and r.get("witnesses"):
                w = wit.get(e6.witness_key(r, us[pid], c, probs[pid]))
                if w is None:
                    raise SystemExit(f"unscored witness set {r['key']} contract {c}")
                vd[c] = bool(w[VD_FIELD])
            else:
                vd[c] = False
        cells.setdefault((pid, prog, arm, cfg), []).append(
            {"flag": bool(r["flagged"]), "vd": vd, "esc": bool(r.get("escalated"))})
    return cells, us


def policy(readings: list, t: int) -> tuple[bool, dict]:
    flag = sum(x["flag"] for x in readings) >= min(t, len(readings))
    return flag, {c: flag and any(x["vd"][c] for x in readings) for c in "ab"}


def unit_value(cells, pid, arm_group: str, cfgs, t: int) -> dict | None:
    """Mean over configurations; None if any required cell is missing (registered complete-case rule)."""
    vals = []
    for cfg in cfgs:
        def cell(prog, arm):
            rs = cells.get((pid, prog, arm, cfg))
            return policy(rs, t) if rs else None
        if arm_group in ("resolve", "sentence"):
            ca, cb = cell("a", f"{arm_group}-a"), cell("b", f"{arm_group}-b")     # correct programs
            da, db = cell("b", f"{arm_group}-a"), cell("a", f"{arm_group}-b")     # defective programs
            if None in (ca, cb, da, db):
                return None
            vals.append({"tpr": (da[0] + db[0]) / 2, "fpr": (ca[0] + cb[0]) / 2, "cov": (da[1]["a"] + db[1]["b"]) / 2,
                         "any_clean_flag": float(ca[0] or cb[0])})
        else:
            pa, pb = cell("a", arm_group), cell("b", arm_group)
            if None in (pa, pb):
                return None
            f = (pa[0] + pb[0]) / 2
            vals.append({"tpr": f, "fpr": f, "cov": (pa[1]["b"] + pb[1]["a"]) / 2,
                         "r_b": float(pa[1]["b"]), "r_a": float(pb[1]["a"]),
                         "flag_a": float(pa[0]), "flag_b": float(pb[0]), "any_clean_flag": float(pa[0] or pb[0])})
    return {k: statistics.mean(v[k] for v in vals) for k in vals[0]}


def boot(values: dict, seed=SEED, b=B) -> dict | None:
    xs = list(values.values())
    if not xs:
        return None
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choice(xs) for _ in xs) for _ in range(b))
    return {"est": 100 * statistics.mean(xs), "lo": 100 * draws[math.floor(0.025 * b)],
            "hi": 100 * draws[math.ceil(0.975 * b) - 1], "n": len(xs),
            "sd_unit": 100 * (statistics.stdev(xs) if len(xs) > 1 else 0.0)}


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided exact (Clopper-Pearson) upper bound for k events in n, by bisection on the binomial tail."""
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        tail = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(k + 1))
        lo, hi = (mid, hi) if tail > 1 - conf else (lo, mid)
    return hi


def betting_upper(xs: list, alpha: float = 0.05, seed: int = SEED) -> float:
    """One-sided (1 - alpha) upper confidence bound for the mean of i.i.d. values in [0, 1], by the hedged
    capital-betting method of Waudby-Smith and Ramdas (JRSS-B 2024): m is excluded when the capital of a bettor
    wagering that the mean is below m reaches 1/alpha. Values are taken in a seeded random order."""
    if not xs:
        return 1.0
    xs = list(xs)
    random.Random(seed).shuffle(xs)
    n = len(xs)
    # predictable plug-in bets from running mean and variance with a weak prior
    lams, mu, var = [], 0.5, 0.25
    for i, x in enumerate(xs):
        lams.append(math.sqrt(2 * math.log(1 / alpha) / (n * var)))
        mu = (mu * (i + 1) + x) / (i + 2)
        var = (var * (i + 1) + (x - mu) ** 2) / (i + 2)

    def excluded(m: float) -> bool:
        cap = 1.0
        for x, lam in zip(xs, lams):
            cap *= 1 - min(lam, 0.75 / (1 - m)) * (x - m)   # bet that the mean is below m; factor >= 0.25 > 0
            if cap >= 1 / alpha:
                return True
        return False
    lo, hi = sum(xs) / n, 1.0
    if not excluded(1.0 - 1e-6):
        return 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if excluded(mid) else (mid, hi)
    return hi


def betting_interval(diffs: list, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided (1 - alpha) interval for the mean of values in [-1, 1]: two one-sided betting bounds at alpha / 2 on
    the rescaled values (x + 1) / 2 and (1 - x) / 2."""
    up = betting_upper([(d + 1) / 2 for d in diffs], alpha / 2) * 2 - 1
    lo = 1 - 2 * betting_upper([(1 - d) / 2 for d in diffs], alpha / 2)
    return lo, up


def fpr_bound(uv: dict) -> dict:
    """Registered boundary safeguard: the problem-level indicator of any clean-cell flag is a conservative upper
    proxy for the mean clean-flag rate; its exact one-sided 95% bound must be below alpha."""
    k = sum(1 for v in uv.values() if v["any_clean_flag"] > 0)
    n = len(uv)
    return {"units_with_any_clean_flag": k, "n": n, "upper95": 100 * cp_upper(k, n)}


def fpr_compliant(level_row: dict) -> bool:
    """Registered budget rule (v4.1, after GPT review P4): the one-sided 95% betting upper bound on the mean
    problem-level resolved clean-flag rate is below alpha_FPR."""
    return level_row["fpr_betting_upper95"] < 100 * ALPHA_FPR


def population(split: str) -> list:
    """Registered population: v4-admitted units; both registered judges, by identity, rate the domain valid and (open)
    both rules compatible or (det) RULE_A incompatible and RULE_B compatible."""
    want = ("incompatible", "compatible") if e6.KIND == "det" else ("compatible", "compatible")
    props = e6.proposals(split)
    probs = {p.problem_id: p for p in e6.problems(split)}
    votes: dict = {}
    for r in e1.load(e6.JUDGE):
        if r.get("ok") and r["problem_id"] in props:
            pid, pr = r["problem_id"], props[r["problem_id"]]
            a_first = int(e6.sha("judge-order|" + pid), 16) % 2 == 0
            r1, r2 = (pr["rule_a"], pr["rule_b"]) if a_first else (pr["rule_b"], pr["rule_a"])
            want_sha = e6.sha(e6.JUDGE_PROMPT.format(spec=probs[pid].spec.rstrip(), visible=probs[pid].visible_tests_text(),
                                                     r1=r1, r2=r2))
            if r["prompt_sha256"] != want_sha:
                raise SystemExit(f"judge prompt hash mismatch: {pid} {r['judge']}")
            votes.setdefault(pid, {})[r["judge"]] = (r.get("domain"), r["a"], r["b"])
    return sorted(pid for pid in e6.units(split)
                  if all(votes.get(pid, {}).get(j) == ("valid",) + want for j in e6.JUDGE_ROUTES))


def contrast(cells, units, g1, g2, cfgs1, cfgs2, metric, t):
    vals, missing = {}, 0
    for pid in units:
        x, y = unit_value(cells, pid, g1, cfgs1, t), unit_value(cells, pid, g2, cfgs2, t)
        if x is None or y is None:
            missing += 1
            continue
        vals[pid] = x[metric] - y[metric]
    return with_bounds(boot(vals), vals, missing, lo=-1.0, hi=1.0)


def with_bounds(b: dict | None, values: dict, missing: int, lo: float = 0.0, hi: float = 1.0) -> dict:
    """Attach the registered missing-data bounds (excluded units at the worst and best value) and counts."""
    out = dict(b) if b else {"est": None}
    n = len(values) + missing
    out["excluded_missing"] = missing
    out["bound_low"] = 100 * (sum(values.values()) + lo * missing) / n if n else None
    out["bound_high"] = 100 * (sum(values.values()) + hi * missing) / n if n else None
    return out


def level(cells, units, g, cfgs, t):
    uv = {pid: v for pid in units if (v := unit_value(cells, pid, g, cfgs, t)) is not None}
    miss = len(units) - len(uv)
    out = {m: with_bounds(boot({k: v[m] for k, v in uv.items()}), {k: v[m] for k, v in uv.items()}, miss)
           for m in ("tpr", "fpr", "cov")}
    out["fpr_bound"] = fpr_bound(uv)
    out["fpr_betting_upper95"] = 100 * betting_upper([v["fpr"] for v in uv.values()])
    out["excluded_missing"] = len(units) - len(uv)
    return out, uv


def convention(cells, units, cfgs, t) -> dict:
    """Convention advantage (r_B - r_A) / 2 in the none arm, with the registered missing-data bounds (P6)."""
    _, nv = level(cells, units, "none", cfgs, t)
    vals = {k: (v["r_b"] - v["r_a"]) / 2 for k, v in nv.items()}
    return with_bounds(boot(vals), vals, len(units) - len(nv), lo=-0.5, hi=0.5)


def routing(cells, units, arm, cfg):
    """Menu decision routing: share of readings that block, escalate, or neither (pass)."""
    rs = [x for pid in units for prog in "ab" for x in cells.get((pid, prog, arm, cfg), [])]
    n = len(rs) or 1
    return {"n": len(rs), "block": sum(x["flag"] for x in rs) / n,
            "escalate": sum(x["esc"] and not x["flag"] for x in rs) / n,
            "pass": sum(not x["flag"] and not x["esc"] for x in rs) / n}


def merged_open(split: str, allow_incomplete: bool):
    """The registered open population: first-attempt primary units, plus second-attempt (open2) primary units for
    problems without a first-attempt primary unit. Cells, units, completeness and behaviour of both kinds."""
    cells, units, status, beh = {}, [], {}, {}
    taken: set = set()
    previous = e6.KIND
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        if not e6.UNITS.exists():
            continue
        try:
            status[kind] = e6.completeness(split)
        except SystemExit as err:
            if not allow_incomplete:
                e6.set_kind(previous)
                raise
            status[kind] = {"incomplete": str(err)}
        c, _ = table(split)
        pop = [u for u in population(split) if u not in taken]
        taken |= set(pop)
        cells.update({k: v for k, v in c.items() if k[0] in pop})
        units += pop
        beh.update({r["problem_id"]: r for r in e1.load(e6.BEHAV) if "n_A" in r and r["problem_id"] in pop})
    e6.set_kind(previous)
    return cells, sorted(units), status, beh


def analyse(split: str, allow_incomplete: bool) -> dict:
    cells, units, status, beh = merged_open(split, allow_incomplete)
    C, S = e6.CONFIGS, e6.SENTENCE_CONFIGS
    res = {"split": split, "protocol": e6.PROTOCOL, "n_units": len(units), "completeness": status}
    t = 1
    lv = {}
    for name, cfgs in [("all", C)] + [(c, (c,)) for c in C]:
        for g in ("none", "menu", "resolve"):
            lv[f"{name}|{g}"] = level(cells, units, g, cfgs, t)[0]
    for name, cfgs in [("sentence-configs", S)] + [(c, (c,)) for c in S]:
        lv[f"{name}|sentence"] = level(cells, units, "sentence", cfgs, t)[0]
        lv[f"{name}|resolve"] = level(cells, units, "resolve", cfgs, t)[0]
    res["levels"] = lv
    res["E6_1_cov_resolve_minus_menu"] = contrast(cells, units, "resolve", "menu", C, C, "cov", t)
    res["E6_1_abs_resolve_cov"] = lv["all|resolve"]["cov"]
    res["E6_1_abs_resolve_fpr_bound"] = lv["all|resolve"]["fpr_bound"]
    _, nv = level(cells, units, "none", C, t)
    res["E6_2_convention_advantage_none"] = convention(cells, units, C, t)
    res["E6_3_cov_high_minus_low_resolve"] = contrast(cells, units, "resolve", "resolve",
                                                      [c for c in C if c.endswith("high")],
                                                      [c for c in C if c.endswith("low")], "cov", t)
    res["E6_5_cov_sentence_minus_none"] = contrast(cells, units, "sentence", "none", S, S, "cov", t)
    res["sentence_minus_resolve_cov"] = contrast(cells, units, "sentence", "resolve", S, S, "cov", t)
    res["check_unrevealed_J_none"] = boot({k: v["tpr"] - v["fpr"] for k, v in nv.items()})
    res["flag_pref_a_minus_b_none"] = boot({k: v["flag_a"] - v["flag_b"] for k, v in nv.items()})
    res["per_config"] = {c: {"E6_1": contrast(cells, units, "resolve", "menu", (c,), (c,), "cov", t),
                             "E6_2": convention(cells, units, (c,), t)}
                         for c in C}
    vendors = {"gpt": [c for c in C if "gpt" in c], "claude": [c for c in C if "claude" in c]}
    res["per_vendor"] = {v: {"levels": {g: level(cells, units, g, cs, t)[0] for g in ("none", "menu", "resolve")},
                             "E6_1": contrast(cells, units, "resolve", "menu", cs, cs, "cov", t),
                             "E6_2": convention(cells, units, cs, t)}
                         for v, cs in vendors.items()}
    bench = {"humaneval": [u for u in units if u.startswith("HumanEval")], "mbpp": [u for u in units if u.startswith("Mbpp")]}
    res["per_benchmark_E6_2"] = {b: convention(cells, us_, C, t) for b, us_ in bench.items()}
    both = [u for u in units if beh.get(u, {}).get("n_A", 0) >= 1 and beh.get(u, {}).get("n_B", 0) >= 1]
    res["behavioural_subset"] = {"n": len(both), "E6_1": contrast(cells, both, "resolve", "menu", C, C, "cov", t),
                                 "E6_2": convention(cells, both, C, t)}
    res["behaviour_counts"] = {k: sum(beh.get(u, {}).get(k, 0) for u in units) for k in ("n_A", "n_B", "n_other")}
    res["t2"] = {"E6_1": contrast(cells, units, "resolve", "menu", C, C, "cov", 2),
                 "resolve": level(cells, units, "resolve", C, 2)[0]}
    res["routing_menu"] = {c: routing(cells, units, "menu", c) for c in C}
    res["routing_none"] = {c: routing(cells, units, "none", c) for c in C}
    eq = res["E6_3_cov_high_minus_low_resolve"]
    if eq.get("est") is not None:
        hi_c = [c for c in C if c.endswith("high")]
        lo_c = [c for c in C if c.endswith("low")]
        ds = []
        for pid in units:
            x, y = unit_value(cells, pid, "resolve", hi_c, t), unit_value(cells, pid, "resolve", lo_c, t)
            if x is not None and y is not None:
                ds.append(x["cov"] - y["cov"])
        bl, bu = betting_interval(ds)
        eq["betting_lo"], eq["betting_hi"] = 100 * bl, 100 * bu
    res["verdicts"] = {
        "E6_1": bool(res["E6_1_cov_resolve_minus_menu"].get("lo") is not None
                     and res["E6_1_cov_resolve_minus_menu"]["lo"] > 0
                     and lv["all|resolve"]["cov"].get("lo") is not None and lv["all|resolve"]["cov"]["lo"] >= 50),
        "E6_1b_fpr_budget": fpr_compliant(lv["all|resolve"]),
        "E6_2": bool(res["E6_2_convention_advantage_none"].get("lo") is not None
                     and res["E6_2_convention_advantage_none"]["lo"] > 0),
        "E6_3_equivalent_within_10": bool(eq.get("betting_lo") is not None and eq["betting_lo"] > -10
                                          and eq["betting_hi"] < 10),
        "E6_5": bool(res["E6_5_cov_sentence_minus_none"].get("lo") is not None
                     and res["E6_5_cov_sentence_minus_none"]["lo"] > 0),
    }
    # registered order: each claimed only if all earlier ones hold
    v, chain = res["verdicts"], True
    for k in ("E6_1", "E6_2", "E6_5", "E6_3_equivalent_within_10"):
        chain = chain and v[k]
        v[k + "_claimed"] = chain
    return res


def analyse_det(split: str, allow_incomplete: bool) -> dict:
    """E6-4: positive controls under contract B, none arm: TPR = flag on program a, FPR = flag on program b."""
    try:
        status = e6.completeness(split)
    except SystemExit as err:
        if not allow_incomplete:
            raise
        status = {"incomplete": str(err)}
    cells, _ = table(split)
    units = population(split)
    out, missing = {}, 0
    for pid in units:
        vals = []
        for cfg in e6.CONFIGS:
            ra, rb = cells.get((pid, "a", "none", cfg)), cells.get((pid, "b", "none", cfg))
            if not (ra and rb):
                vals = None
                break
            fa, va = policy(ra, 1)
            fb, _ = policy(rb, 1)
            vals.append({"j": fa - fb, "tpr": fa, "fpr": fb, "cov": va["b"]})
        if vals is None:
            missing += 1
            continue
        out[pid] = {k: statistics.mean(v[k] for v in vals) for k in vals[0]}
    jv = {k: v["j"] for k, v in out.items()}
    res = {"split": split, "n_units": len(units), "excluded_missing": missing, "completeness": status,
           "E6_4_J_none": with_bounds(boot(jv), jv, missing, lo=-1.0, hi=1.0),
           **{m: with_bounds(boot({k: v[m] for k, v in out.items()}), {k: v[m] for k, v in out.items()}, missing)
              for m in ("tpr", "fpr", "cov")}}
    res["verdicts"] = {"E6_4": bool(res["E6_4_J_none"].get("lo") is not None and res["E6_4_J_none"]["lo"] > 0)}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--kind", choices=["open", "open2", "det"], default="open")
    ap.add_argument("--allow-incomplete", action="store_true", help="development use only")
    ap.add_argument("--credit", choices=["verified_diagnosis", "verified_refdomain", "verified_offclass"],
                    default="verified_diagnosis", help="registered sensitivity analyses of witness credit")
    a = ap.parse_args()
    VD_FIELD = a.credit
    e6.set_kind(a.kind)
    out = (analyse_det if a.kind == "det" else analyse)(a.split, a.allow_incomplete)
    name = ("e6det" if a.kind == "det" else "e6") + ("" if a.credit == "verified_diagnosis" else "_" + a.credit)
    (e1.REC / f"{name}_results_v4_{a.split}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("levels", "per_config")}, indent=1))
