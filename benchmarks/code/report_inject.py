"""Study 22 — the ceiling on defects the specification determines.

    python benchmarks/code/report_inject.py

Reads the cached readings, computes §3's hypotheses and §4's secondaries exactly as
`inject/PREREGISTRATION.md` and its five amendments fix them, and writes
`records/inject/numbers.json` and `records/inject/tables.md`. No model call.

Helpers are ceiling 1's and study 18's, imported rather than reimplemented: the Wilson
interval, the problem-cluster percentile bootstrap, the exact McNemar test, the cluster
sign-flip test, the union curve and the constrained saturation fit.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

import explore  # noqa: E402
import report_ceiling as rc  # noqa: E402

RECORDS = HERE / "records"
INJECT = RECORDS / "inject"
CEILING = RECORDS / "ceiling"
BOOT_SEED = 20260916          # §3
BOOTSTRAP = 10_000
K_MAX = 8

#: ceiling 1's frozen comparator, quoted from records/ceiling/numbers.json, not retyped.
def ceiling1_cross() -> dict:
    n = json.loads((CEILING / "numbers.json").read_text(encoding="utf-8"))
    return n["ceiling1"]["families"]["cross"]


def load_arm(arm: str, ids: list[str]) -> dict[int, dict[str, bool]]:
    """draw -> instance -> flagged, for one arm, from this study's cache (and, for the
    twin arm's ten instances that ceiling 1 already audited, from ceiling 1's)."""
    out: dict[int, dict[str, bool]] = {}
    scope = set(ids)
    for draw in range(1, K_MAX + 1):
        key = ("holistic", "cross", draw)
        explore.EXPLORE = INJECT
        found = explore.load_detector(key, scope)
        if arm == "twin":
            explore.EXPLORE = CEILING
            found.update(explore.load_detector(key, scope))
            explore.EXPLORE = INJECT
        out[draw] = {i: bool(v["flagged"]) for i, v in found.items()}
    return out


def union_flags(draws: dict[int, dict[str, bool]], ids: list[str], k: int) -> dict[str, bool]:
    ds = sorted(draws)[:k]
    return {i: any(draws[d].get(i) for d in ds) for i in ids}


def counts_k(draws: dict[int, dict[str, bool]], ids: list[str]) -> dict[str, int]:
    return {i: sum(1 for d in sorted(draws) if draws[d].get(i)) for i in ids}


def two_sample_difference(flags_a: dict[str, bool], probs_a: dict[str, str],
                          flags_b: dict[str, bool], probs_b: dict[str, str],
                          seed: int) -> dict:
    """§3: the populations are different instances, so the difference is NOT paired.
    Each population's problems are resampled independently."""
    def by_problem(flags, probs):
        out: dict[str, list[int]] = {}
        for i, f in flags.items():
            out.setdefault(probs[i], []).append(int(f))
        return out
    ba, bb = by_problem(flags_a, probs_a), by_problem(flags_b, probs_b)
    ka, na = sum(flags_a.values()), len(flags_a)
    kb, nb = sum(flags_b.values()), len(flags_b)
    rng = random.Random(seed)
    keys_a, keys_b = sorted(ba), sorted(bb)
    draws = []
    for _ in range(BOOTSTRAP):
        acc_a = cnt_a = acc_b = cnt_b = 0
        for _ in range(len(keys_a)):
            vals = ba[keys_a[rng.randrange(len(keys_a))]]
            acc_a += sum(vals); cnt_a += len(vals)
        for _ in range(len(keys_b)):
            vals = bb[keys_b[rng.randrange(len(keys_b))]]
            acc_b += sum(vals); cnt_b += len(vals)
        if cnt_a and cnt_b:
            draws.append(100 * (acc_a / cnt_a - acc_b / cnt_b))
    draws.sort()
    return {"a": {"k": ka, "n": na, "rate": ka / na, "wilson95": list(rc.wilson(ka, na)),
                  "n_problems": len(ba)},
            "b": {"k": kb, "n": nb, "rate": kb / nb, "wilson95": list(rc.wilson(kb, nb)),
                  "n_problems": len(bb)},
            "difference_points": 100 * (ka / na - kb / nb),
            "cluster_ci95_points": [rc.percentile(draws, 0.025), rc.percentile(draws, 0.975)],
            "paired": False,
            "note": "two-sample: the populations are different instances, so each one's "
                    "problems are resampled independently (§3); this difference carries the "
                    "problem-mix confound Amendment 5 fixes in advance"}


def paired_difference(flags_i: dict[str, bool], flags_t: dict[str, bool],
                      probs: dict[str, str], ids: list[str]) -> dict:
    """§3 H22b, Amendment 4: each instance against its own twin. No problem-mix confound."""
    by_problem: dict[str, list[float]] = {}
    for i in ids:
        by_problem.setdefault(probs[i], []).append(float(flags_i[i]) - float(flags_t[i]))
    lo, hi = rc.cluster_bootstrap_ci(by_problem, BOOTSTRAP, BOOT_SEED)
    b = sum(1 for i in ids if flags_i[i] and not flags_t[i])
    c = sum(1 for i in ids if not flags_i[i] and flags_t[i])
    ki, kt, n = sum(flags_i[i] for i in ids), sum(flags_t[i] for i in ids), len(ids)
    return {"n": n, "injected": {"k": ki, "rate": ki / n, "wilson95": list(rc.wilson(ki, n))},
            "twin": {"k": kt, "rate": kt / n, "wilson95": list(rc.wilson(kt, n))},
            "difference_points": 100 * (ki - kt) / n,
            "cluster_ci95_points": [100 * lo, 100 * hi],
            "tango_ci95_points": [100 * x for x in rc.tango_score_interval(b, c, n)],
            "injected_only": b, "twin_only": c,
            "one_signed_discordance": (b == 0) != (c == 0) and (b + c) > 0,
            "mcnemar_exact_p": rc.mcnemar_exact(b, c),
            "signflip": rc.signflip_p(by_problem), "paired": True}


def build() -> dict:
    population = json.loads((INJECT / "population.json").read_text(encoding="utf-8"))
    base_ids = population["population_instance_ids"]
    inj_ids = [f"inj:{i}" for i in base_ids]
    probs = {f"inj:{i}": i.split(":", 1)[1] for i in base_ids}
    probs.update({i: i.split(":", 1)[1] for i in base_ids})

    arm_i = load_arm("I", inj_ids)
    arm_t = load_arm("twin", base_ids)
    complete_i = [d for d in arm_i if len(arm_i[d]) == len(inj_ids)]
    complete_t = [d for d in arm_t if len(arm_t[d]) == len(base_ids)]
    k_i, k_t = len(complete_i), len(complete_t)
    k_common = min(k_i, k_t, K_MAX)

    c1 = ceiling1_cross()
    p_rate = c1["P"]["union_at_kmax"]
    p_k, p_n = c1["P"]["union_at_kmax_count"], c1["P"]["n_instances"]
    # ceiling 1's stratum-P instances and their problems, for the two-sample resample
    p_instances = [json.loads(l)["instance_id"]
                   for l in (RECORDS / "study2" / "instances.jsonl").read_text(
                       encoding="utf-8").splitlines()
                   if l.strip() and json.loads(l)["stratum"] == "P"]
    p_flags_path = CEILING / "cache"
    explore.EXPLORE = CEILING
    p_draws = {d: {i: bool(v["flagged"])
                   for i, v in explore.load_detector(("holistic", "cross", d),
                                                     set(p_instances)).items()}
               for d in range(1, 9)}
    explore.EXPLORE = INJECT
    p_union = union_flags(p_draws, p_instances, 8)
    p_probs = {i: i.split(":", 1)[1] for i in p_instances}
    assert sum(p_union.values()) == p_k, (sum(p_union.values()), p_k)

    flags_i = union_flags(arm_i, inj_ids, k_common)
    flags_t = union_flags(arm_t, base_ids, k_common)
    flags_t_by_inj = {f"inj:{i}": flags_t[i] for i in base_ids}

    h22a = two_sample_difference(flags_i, probs, p_union, p_probs, BOOT_SEED)
    h22b = paired_difference(flags_i, flags_t_by_inj, probs, inj_ids)
    flags_i1 = union_flags(arm_i, inj_ids, 1)
    h22c = two_sample_difference(
        flags_i1, probs,
        union_flags(p_draws, p_instances, 1), p_probs, BOOT_SEED + 1)

    ks_by_problem: dict[str, list[int]] = {}
    for i, k in counts_k({d: arm_i[d] for d in complete_i}, inj_ids).items():
        ks_by_problem.setdefault(probs[i], []).append(k)
    curve = rc.union_curve([k for v in ks_by_problem.values() for k in v], k_common)
    fit = rc.fit_saturation(curve)
    gain = 100 * (curve[-1] - curve[-2]) if len(curve) > 1 else None
    h22d = {"k_max": k_common, "curve": curve,
            "curve_ci95": rc.curve_cluster_cis(ks_by_problem, k_common, BOOTSTRAP, BOOT_SEED)
            if hasattr(rc, "curve_cluster_cis") else None,
            "fit": fit, "last_step_gain_points": gain,
            "flattening_bar_met": (gain is not None and gain <= 1.0),
            "asymptote_is_extrapolation": not (gain is not None and gain <= 1.0)}

    rows = population["rows"]
    def split(predicate, name, seed_offset):
        a = [i for i in inj_ids if predicate(rows[i[4:]])]
        b = [i for i in inj_ids if not predicate(rows[i[4:]])]
        return {"name": name,
                "yes": rc.clustered_rate({i: flags_i[i] for i in a}, a,
                                         {i: {"problem_id": probs[i]} for i in a},
                                         BOOTSTRAP, BOOT_SEED + seed_offset) if a else None,
                "no": rc.clustered_rate({i: flags_i[i] for i in b}, b,
                                        {i: {"problem_id": probs[i]} for i in b},
                                        BOOTSTRAP, BOOT_SEED + seed_offset + 1) if b else None}
    median_diff = sorted(rows[i[4:]].get("changed_lines") or 0 for i in inj_ids)[len(inj_ids) // 2]
    p_problems = {i.split(":", 1)[1] for i in p_instances}
    secondaries = {
        "diff_size": {**split(lambda r: (r.get("changed_lines") or 0) > median_diff,
                              f"more than {median_diff} changed lines", 10),
                      "median_changed_lines": median_diff},
        "branched": split(lambda r: bool(r.get("branched")), "the changed line sits under a conditional", 20),
        "problem_also_in_P": split(lambda r: r["problem_id"] in p_problems,
                                   "the problem also contributes a stratum-P instance", 30),
    }

    # §4.1's probe, and a POST-HOC cross-tab it makes possible: does the auditor's recall
    # track what the probe can see? Asked after both were in hand; labelled post hoc.
    probe_path = INJECT / "probe.json"
    probe = json.loads(probe_path.read_text(encoding="utf-8")) if probe_path.exists() else None
    probe_xtab = None
    if probe is not None:
        raw = json.loads((Path.home() / "Documents/Crossaudit/study-data/wt-inject-runs"
                          / "probe.json").read_text(encoding="utf-8"))
        said = {k: v["said"] for k, v in raw.items() if k.startswith("inj:")}
        buckets: dict[str, list[bool]] = {}
        for i in inj_ids:
            buckets.setdefault(said.get(i, "?"), []).append(flags_i[i])
        probe_xtab = {"POST_HOC": True,
                      "note": "asked after §4.1's probe and the audit were both in hand",
                      "by_probe_verdict": {k: {"n": len(v), "caught": sum(v)}
                                           for k, v in sorted(buckets.items())},
                      "auditor_misses": sorted(i for i in inj_ids if not flags_i[i]),
                      "probe_verdict_of_the_misses": [said.get(i, "?") for i in
                                                      sorted(i for i in inj_ids if not flags_i[i])]}

    if probe is not None:
        total = probe["n_injected"] + probe["n_natural"]
        probe["accuracy_bounds_if_unanswered_counted"] = {
            "all_unanswered_wrong": probe["correct"] / total,
            "all_unanswered_right": (probe["correct"] + probe["n_unparsed"]) / total,
            "n_total_items": total,
            "note": "the unanswered items skew toward injected ones, so the answered-only "
                    "accuracy may overstate separability among the hard cases"}

    out = {
        "study": "study22 / injection", "seed": BOOT_SEED, "bootstrap_reps": BOOTSTRAP,
        "detectability_probe": probe,
        "recall_by_probe_verdict_POST_HOC": probe_xtab,
        "population": {"n": len(base_ids), "n_problems": len({probs[i] for i in inj_ids}),
                       "n_with_ceiling1_twin": population["n_in_ceiling1_audit_set"],
                       "construction_spend_usd": population["build_spend_usd"]},
        "draws": {"I_complete": k_i, "twin_complete": k_t, "k_common": k_common},
        "comparator_ceiling1_cross_P": {"k": p_k, "n": p_n, "rate": p_rate,
                                        "cluster_ci95": c1["P"]["union_at_kmax_block"]["cluster_ci95"],
                                        "wilson95": c1["P"]["union_at_kmax_wilson95"]},
        "H22a_primary": h22a, "H22b_paired": h22b, "H22c_single_draw": h22c, "H22d_curve": h22d,
        "secondaries": secondaries,
        "kill": {"rule": "H22a's interval includes zero → study 21's post-hoc split does not "
                         "replicate prospectively",
                 "fires": h22a["cluster_ci95_points"][0] <= 0 <= h22a["cluster_ci95_points"][1]},
    }
    return out


def main() -> int:
    out = build()
    INJECT.mkdir(parents=True, exist_ok=True)
    (INJECT / "numbers.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    (INJECT / "tables.md").write_text(render_tables(out), encoding="utf-8")
    a, b = out["H22a_primary"], out["H22b_paired"]
    print(f"K_common {out['draws']['k_common']}; |I| {out['population']['n']}")
    print(f"H22a  I {a['a']['k']}/{a['a']['n']} = {100*a['a']['rate']:.1f}%  vs  "
          f"ceiling 1 cross on P {a['b']['k']}/{a['b']['n']} = {100*a['b']['rate']:.1f}%  "
          f"→ {a['difference_points']:+.1f} points "
          f"[{a['cluster_ci95_points'][0]:+.1f}, {a['cluster_ci95_points'][1]:+.1f}]")
    print(f"H22b  injected {b['injected']['k']}/{b['n']} vs twin {b['twin']['k']}/{b['n']} "
          f"→ {b['difference_points']:+.1f} points "
          f"[{b['cluster_ci95_points'][0]:+.1f}, {b['cluster_ci95_points'][1]:+.1f}]; "
          f"discordant {b['injected_only']}/{b['twin_only']}; McNemar p {b['mcnemar_exact_p']:.2e}")
    print(f"kill fires: {out['kill']['fires']}")
    print(f"curve {[round(100*x, 1) for x in out['H22d_curve']['curve']]}; "
          f"last-step gain {out['H22d_curve']['last_step_gain_points']:.2f} pts; "
          f"flat {out['H22d_curve']['flattening_bar_met']}")
    return 0




# ---------------------------------------------------------------------------------
# tables — rendered from numbers.json alone and spliced verbatim (inject/splice_tables.py)
# ---------------------------------------------------------------------------------

def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def _iv(pair, signed: bool = False) -> str:
    fmt = "{:+.1f}" if signed else "{:.1f}"
    return f"[{fmt.format(pair[0])}, {fmt.format(pair[1])}]"


def _rate(block: dict) -> str:
    """EXPERIMENT_RECORD §9: five or fewer is a count, not a rate."""
    if block["k"] <= 5 or block["n"] - block["k"] <= 5:
        return f"**{block['k']} of {block['n']}**"
    return (f"**{block['k']} of {block['n']}** = {_pct(block['rate'])}% "
            f"(Wilson {_iv([100 * x for x in block['wilson95']])})")


def render_tables(n: dict) -> str:
    L: list[str] = []
    a, b, c, d = n["H22a_primary"], n["H22b_paired"], n["H22c_single_draw"], n["H22d_curve"]
    cmp_ = n["comparator_ceiling1_cross_P"]

    L += ["<!-- TABLE primary -->", "",
          f"| population | n (problems) | union recall at K = {d['k_max']} | 95% cluster CI |",
          "|---|---:|---|---|",
          f"| I — defects the specification determines, injected | {a['a']['n']} ({a['a']['n_problems']}) "
          f"| {_rate(a['a'])} | — |",
          f"| ceiling 1's stratum P — the natural residual | {a['b']['n']} ({a['b']['n_problems']}) "
          f"| {_rate(a['b'])} | {_iv([100 * x for x in cmp_['cluster_ci95']])} |",
          f"| **difference (two-sample, not paired)** | | **{a['difference_points']:+.1f} points** "
          f"| **{_iv(a['cluster_ci95_points'], signed=True)}** |", ""]

    L += ["<!-- TABLE paired -->", "",
          "Each injected instance against its own unmodified twin: same problem, same "
          "specification, same generator, same code but for the injected lines, same auditor, "
          f"same K = {d['k_max']} (Amendment 4).", "",
          "| arm | flagged | 95% Wilson |", "|---|---:|---|",
          f"| injected | {b['injected']['k']} of {b['n']} | {_iv([100 * x for x in b['injected']['wilson95']])} |",
          f"| unmodified twin | {b['twin']['k']} of {b['n']} | {_iv([100 * x for x in b['twin']['wilson95']])} |",
          f"| **difference (paired)** | **{b['difference_points']:+.1f} points** "
          f"| **cluster {_iv(b['cluster_ci95_points'], signed=True)}** |", "",
          f"Discordant pairs: {b['injected_only']} where only the injected instance was flagged, "
          f"{b['twin_only']} where only the twin was. Exact McNemar p = {b['mcnemar_exact_p']:.2e}; "
          f"cluster sign-flip p = {b['signflip'].get('p', float('nan')):.2e}. "
          + ("Every discordant pair points one way, so the percentile bootstrap's bound is an "
             "artefact and the Tango interval "
             f"{_iv(b['tango_ci95_points'], signed=True)} is the one to read (ceiling 1 Amendment 5)."
             if b["one_signed_discordance"] else ""), ""]

    L += ["<!-- TABLE curve -->", "",
          "| K | union recall on I |", "|---:|---|"]
    for k, v in enumerate(d["curve"], start=1):
        L.append(f"| {k} | {_pct(v)}% |")
    L += ["",
          f"Last-step gain {d['last_step_gain_points']:.2f} points; the preregistered flattening "
          f"bar (at most 1.0) is {'met' if d['flattening_bar_met'] else 'not met'}, so the fitted "
          f"asymptote {_pct(d['fit']['A'])}% "
          + ("is quotable" if d["flattening_bar_met"] else "is an extrapolation and the raw union "
             f"at K = {d['k_max']} is the number to quote") + ".",
          f"Single reading, I against the natural residual: {c['difference_points']:+.1f} points "
          f"{_iv(c['cluster_ci95_points'], signed=True)}.", ""]

    p = n.get("detectability_probe")
    if p:
        bounds = p["accuracy_bounds_if_unanswered_counted"]
        L += ["<!-- TABLE probe -->", "",
              "| quantity | value |", "|---|---|",
              f"| prober | `{p['prober']}` — not the auditor, not a gate |",
              f"| items | {p['n_injected']} injected, {p['n_natural']} natural |",
              f"| answered | {p['n_answered']}; unparsed {p['n_unparsed']} |",
              f"| accuracy on the answered | **{_pct(p['accuracy'])}%** "
              f"(Wilson {_iv([100 * x for x in p['wilson95']])}) |",
              f"| accuracy over all {bounds['n_total_items']} items | between "
              f"{_pct(bounds['all_unanswered_wrong'])}% and {_pct(bounds['all_unanswered_right'])}% |",
              f"| covers chance | {'yes' if p['covers_chance'] else '**no**'} |",
              f"| injected called edited | {p['by_truth']['EDITED']['said_edited']} of {p['by_truth']['EDITED']['n']} |",
              f"| natural called edited | {p['by_truth']['ONEPASS']['said_edited']} of {p['by_truth']['ONEPASS']['n']} |",
              ""]

    x = n.get("recall_by_probe_verdict_POST_HOC")
    if x:
        L += ["<!-- TABLE xtab -->", "",
              "POST HOC: asked after the probe and the audit were both in hand.", "",
              "| the probe called it | n | the auditor caught |", "|---|---:|---:|"]
        for verdict, v in x["by_probe_verdict"].items():
            label = {"EDITED": "edited (artificial)", "ONEPASS": "written in one pass (natural)",
                     "?": "it would not say"}[verdict]
            L.append(f"| {label} | {v['n']} | {v['caught']} |")
        L += ["", f"The auditor's only misses were {', '.join('`' + i[4:] + '`' for i in x['auditor_misses'])}, "
              f"which the probe called {' and '.join(x['probe_verdict_of_the_misses']).lower()}.", ""]

    s = n["secondaries"]
    L += ["<!-- TABLE splits -->", "",
          "| split | group | caught |", "|---|---|---:|"]
    # a fixed order: numbers.json is written with sorted keys, so insertion order is not
    # stable across a round trip and the renderer must not depend on it
    for key in ("diff_size", "branched", "problem_also_in_P"):
        block = s.get(key)
        if block is None:
            continue
        if not (block.get("yes") and block.get("no")):
            continue
        L.append(f"| {block['name']} | yes | {block['yes']['k']} of {block['yes']['n']} |")
        L.append(f"| | no | {block['no']['k']} of {block['no']['n']} |")
    L.append("")
    return "\n".join(L).rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
