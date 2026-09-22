#!/usr/bin/env python3
"""P3's outcome: H3, computed exactly as the core registration and Amendment 11 fix it.

**The outcome is correct diagnosis**, not flagging and not naming. An instance counts as
correctly diagnosed in a condition when at least one of that condition's K = 4 readings carries
a finding both raters judged to state the behaviour the hidden suite expects at an input it
exercises. **Disagreement counts as not diagnosed**, as registered.

H3 has two halves and both are required: correct diagnosis higher under `clarified` than under
`original`, with the difference excluding zero; and the difference under `placebo` smaller than
under `clarified`. A rise under both conditions means the auditor responds to the specification
having been edited rather than to what the edit settles.

Flag rate and naming rate are computed beside it and **labelled as not the outcome**, because
they are the quantities this programme has mistaken for it three times.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import report_ceiling as rc  # noqa: E402

ROWS = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs/rows.jsonl"
SHEET = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs/sheet"
OUT = HERE.parent / "records/clarify/h3.json"
ARMS = ("original", "clarified", "placebo")
K = 4
SEED = 20260921
N_BOOT = 10000


def wilson(k: int, n: int) -> list[float]:
    if not n:
        return [None, None]
    z, p = 1.959963984540054, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [100 * (c - h), 100 * (c + h)]


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on the discordant pairs. b, c are the two discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    obs = min(b, c)
    tail = sum(math.comb(n, i) for i in range(obs + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def signflip_cluster(pairs: dict[str, list[tuple[int, int]]], n_perm: int = 10000) -> float:
    """Permutation p-value that respects clustering: the sign is flipped per PROBLEM.

    Flipping per instance would treat two instances of one problem as independent evidence.
    The registration asks for this one alongside McNemar and says it is the one that respects
    clustering, so it is the one reported as primary.
    """
    keys = sorted(pairs)
    obs = sum(t - r for k in keys for t, r in pairs[k])
    n = sum(len(pairs[k]) for k in keys)
    if n == 0:
        return 1.0
    obs /= n
    rng = random.Random(SEED)
    hits = 0
    for _ in range(n_perm):
        tot = 0
        for k in keys:
            s = 1 if rng.random() < 0.5 else -1
            tot += s * sum(t - r for t, r in pairs[k])
        if abs(tot / n) >= abs(obs) - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def cluster_ci(pairs: dict[str, list[tuple[int, int]]]) -> tuple[float, list[float]]:
    keys = sorted(pairs)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(N_BOOT):
        a = b = n = 0
        for _ in range(len(keys)):
            for t, r in pairs[keys[rng.randrange(len(keys))]]:
                a += t; b += r; n += 1
        if n:
            diffs.append(100 * (a - b) / n)
    diffs.sort()
    n_all = sum(len(v) for v in pairs.values())
    point = 100 * sum(t - r for v in pairs.values() for t, r in v) / n_all if n_all else None
    return point, [rc.percentile(diffs, 0.025), rc.percentile(diffs, 0.975)]


def union_at(flags: list[int], k: int) -> float:
    """Union at depth k, averaged exactly over all C(len,k) subsets -- not sampled."""
    idx = range(len(flags))
    subs = list(itertools.combinations(idx, k))
    return sum(1 for s in subs if any(flags[i] for i in s)) / len(subs) if subs else 0.0


def main() -> int:
    rows = [json.loads(l) for l in ROWS.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok")]
    key = {k["id"]: k for k in
           (json.loads(l) for l in (SHEET / "key.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip())}
    labels = {}
    for who in ("L1", "L2"):
        f = SHEET / f"{who}.csv"
        if not f.exists():
            raise SystemExit(f"ERR: {f} is missing. H3 is defined over TWO raters and "
                             "disagreement counts as not diagnosed; one rater is not the "
                             "registered outcome and this refuses to compute it.")
        import csv
        labels[who] = {r["id"]: r["label"] for r in csv.DictReader(f.open(encoding="utf-8"))}
        gaps = [sid for sid in key if sid not in labels[who]]
        if gaps:
            raise SystemExit(
                f"ERR: {who} has {len(gaps)} of {len(key)} items unlabelled ({gaps[:6]}). "
                "H3 counts disagreement as not diagnosed, so a MISSING label would be "
                "silently counted the same way as a considered `no` -- and the first run of "
                "this analysis did exactly that on five items. Fill them and re-run.")

    # Registered: both raters must say yes. Disagreement counts as not diagnosed.
    diagnosed_item = {sid: (labels["L1"].get(sid) == "yes" and labels["L2"].get(sid) == "yes")
                      for sid in key}

    # per instance, per arm, per draw: did any adjudicated finding diagnose it?
    per_draw: dict[tuple[str, str, int], int] = {}
    for r in rows:
        per_draw.setdefault((r["instance_id"], r["condition"], r["draw"]), 0)
    for sid, k in key.items():
        if diagnosed_item[sid]:
            per_draw[(k["instance_id"], k["arm"], k["draw"])] = 1

    instances = sorted({r["instance_id"] for r in rows})
    ladder, per_arm = {}, {}
    for arm in ARMS:
        per_arm[arm] = {}
        for iid in instances:
            flags = [per_draw.get((iid, arm, d), 0) for d in range(1, K + 1)]
            per_arm[arm][iid] = flags
        for k in range(1, K + 1):
            vals = [union_at(per_arm[arm][i], k) for i in instances]
            ladder.setdefault(arm, {})[k] = 100 * sum(vals) / len(vals) if vals else None

    def contrast(treat: str, ref: str) -> dict:
        pairs: dict[str, list[tuple[int, int]]] = {}
        b = c = 0
        for iid in instances:
            t = 1 if any(per_arm[treat][iid]) else 0
            r = 1 if any(per_arm[ref][iid]) else 0
            pairs.setdefault(iid.split(":", 1)[1], []).append((t, r))
            if t and not r:
                b += 1
            elif r and not t:
                c += 1
        point, ci = cluster_ci(pairs)
        return {"points": point, "cluster_ci95": ci, "n": len(instances),
                "n_problems": len(pairs), "discordant_treat_only": b,
                "discordant_ref_only": c, "mcnemar_exact_p": mcnemar_exact(b, c),
                "signflip_cluster_p": signflip_cluster(pairs)}

    rates = {arm: {"k": sum(1 for i in instances if any(per_arm[arm][i])), "n": len(instances)}
             for arm in ARMS}
    for arm in ARMS:
        rates[arm]["pct"] = 100 * rates[arm]["k"] / rates[arm]["n"] if rates[arm]["n"] else None
        rates[arm]["wilson"] = wilson(rates[arm]["k"], rates[arm]["n"])

    # Amendment 2's registered secondary: the instances that BOTH study 21's consensus and the
    # third rater call undetermined. It is required "beside the primary, always", and the first
    # version of this report omitted it -- a registration departure the first review found.
    def undetermined_by_l3() -> set[str]:
        import csv as _csv
        items = json.loads((Path.home() / "Desktop/CrossAudit-审计天花板/人类评分任务"
                            / "_items.json").read_text(encoding="utf-8"))
        lab = {r["rate_id"]: r["label"] for r in _csv.DictReader(
            (HERE.parent / "records/rate3/L3.csv").open(encoding="utf-8"))}
        return {it["instance"] for it in items
                if lab.get(it["rate_id"]) == "undetermined"}

    secondary_pop = sorted(set(instances) & undetermined_by_l3())

    def contrast_on(pop: list[str], treat: str, ref: str) -> dict:
        pairs: dict[str, list[tuple[int, int]]] = {}
        b = c = 0
        for iid in pop:
            t = 1 if any(per_arm[treat][iid]) else 0
            r = 1 if any(per_arm[ref][iid]) else 0
            pairs.setdefault(iid.split(":", 1)[1], []).append((t, r))
            if t and not r:
                b += 1
            elif r and not t:
                c += 1
        point, ci = cluster_ci(pairs)
        return {"points": point, "cluster_ci95": ci, "n": len(pop),
                "n_problems": len(pairs),
                "treat_k": sum(1 for i in pop if any(per_arm[treat][i])),
                "ref_k": sum(1 for i in pop if any(per_arm[ref][i])),
                "discordant_treat_only": b, "discordant_ref_only": c,
                "mcnemar_exact_p": mcnemar_exact(b, c),
                "signflip_cluster_p": signflip_cluster(pairs)}

    secondary = contrast_on(secondary_pop, "clarified", "original")

    primary = contrast("clarified", "original")
    placebo = contrast("placebo", "original")
    isolate = contrast("clarified", "placebo")

    half_one = bool(primary["cluster_ci95"][0] is not None and primary["cluster_ci95"][0] > 0)
    half_two = bool(placebo["points"] is not None and primary["points"] is not None
                    and placebo["points"] < primary["points"])

    # secondaries, labelled as not the outcome
    flag = {arm: 100 * sum(1 for r in rows if r["condition"] == arm and r.get("flagged"))
            / max(1, sum(1 for r in rows if r["condition"] == arm)) for arm in ARMS}
    nofind = {arm: sum(1 for r in rows if r["condition"] == arm and not (r.get("findings") or []))
              for arm in ARMS}

    out = {"K": K, "seed": SEED, "n_instances": len(instances),
           "rates_correct_diagnosis": rates, "ladder_union_at_k": ladder,
           "primary_clarified_minus_original": primary,
           "amendment_2_secondary_undetermined_by_both": {
               **secondary, "population": secondary_pop,
               "note": "registered in Amendment 2 to be reported beside the primary, always"},
           "placebo_minus_original": placebo,
           "post_hoc_clarified_minus_placebo": isolate,
           "H3": {"half_one_clarified_beats_original_excluding_zero": half_one,
                  "half_two_placebo_difference_smaller": half_two,
                  "holds": half_one and half_two,
                  "registered_kill": "if the clarified-minus-original difference does not "
                                     "exclude zero, H3 fails and the report says C4 remains a "
                                     "correlation"},
           "NOT_THE_OUTCOME": {"flag_rate_pct_per_reading": flag,
                               "readings_with_no_finding": nofind,
                               "note": "flag rate and no-finding counts are secondaries; three "
                                       "studies in this programme have read one of these as "
                                       "recognition"}}
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for arm in ARMS:
        r = rates[arm]
        print(f"{arm:10s} {r['k']:3d}/{r['n']:<3d} = {r['pct']:5.1f}% correctly diagnosed "
              f"(Wilson [{r['wilson'][0]:.1f}, {r['wilson'][1]:.1f}], too narrow)")
    for name, d in (("clarified - original  [H3's first half]", primary),
                    ("placebo   - original", placebo),
                    ("clarified - placebo   [post hoc]", isolate)):
        lo, hi = d["cluster_ci95"]
        print(f"\n{name}: {d['points']:+.1f} points, cluster [{lo:+.1f}, {hi:+.1f}]")
        print(f"    discordant {d['discordant_treat_only']}/{d['discordant_ref_only']}, "
              f"McNemar exact p={d['mcnemar_exact_p']:.4f}, "
              f"cluster sign-flip p={d['signflip_cluster_p']:.4f} (the one that respects clusters)")
    sc = secondary
    print(f"\n[Amendment 2 secondary] both-undetermined subgroup: {sc['n']} instances on "
          f"{sc['n_problems']} problems")
    if sc["points"] is None:
        print("    empty on this input; the subgroup is defined by rate3's L3 labels")
    else:
        lo2, hi2 = sc["cluster_ci95"]
        print(f"    clarified {sc['treat_k']}/{sc['n']}, original {sc['ref_k']}/{sc['n']}: "
              f"{sc['points']:+.1f} points, cluster [{lo2:+.1f}, {hi2:+.1f}], "
              f"sign-flip p={sc['signflip_cluster_p']:.4f}")
    print(f"\nH3 first half {'HOLDS' if half_one else 'FAILS'}; "
          f"second half {'HOLDS' if half_two else 'FAILS'}")
    print("H3 " + ("HOLDS" if (half_one and half_two) else
                   "FAILS — the report says C4 remains a correlation"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
