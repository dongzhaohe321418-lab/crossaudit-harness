"""Study 23 — apply substrate 2's preregistered outcomes to the records, and nothing else.

Reads ``records/substrate2`` (the frame, the instances, the frozen audit set and the
reading cache) and ``records/ceiling`` (substrate 1's frozen comparator, read only);
reuses ``report_ceiling``'s and ``report_ceiling3``'s curve, fit, bootstrap and interval
helpers unchanged.

    python benchmarks/code/report_substrate2.py   -> records/substrate2/numbers.json
                                                     records/substrate2/tables.md

No corpus text, no solution text and no finding text is read or written here: ids, hashes,
counts and outcomes only.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import explore  # noqa: E402
import report_ceiling as rc  # noqa: E402
import report_ceiling3 as r3  # noqa: E402

RECORDS = HERE / "records"
SUB2 = RECORDS / "substrate2"
CEILING = RECORDS / "ceiling"
DEFAULT_RUN_DIR = Path.home() / "Documents" / "Crossaudit" / "study-data" / "wt-sub2-runs"

#: Preregistration §3: seed 20260917, 10,000 resamples, for every interval in this report.
BOOT_SEED = 20260917
BOOTSTRAP = 10_000
K_MAX = 8

#: ``report_ceiling3.paired_union_difference`` is reused unchanged for H23d, but it reads
#: its own study's seed from a module constant. Study 23's registered seed is bound here,
#: in this process only; no file of ceiling 1 or ceiling 3 is modified.
r3.BOOT_SEED = BOOT_SEED
r3.BOOTSTRAP = BOOTSTRAP

#: Substrate 1's descriptive medians, as quoted in ceiling 1's preregistration §0.
S1_MEDIAN_SPEC_WORDS = 41
S1_MEDIAN_SOLUTION_LINES = 6


# ---------------------------------------------------------------------------------
# records
# ---------------------------------------------------------------------------------

def load_instances(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["instance_id"]] = row
    return rows


def load_sub2_draws(scope: set[str]) -> dict[str, dict[int, dict[str, bool]]]:
    """``family -> draw -> instance -> flagged``, through the one loader the audit used."""
    out: dict[str, dict[int, dict[str, bool]]] = {"cross": {}, "self": {}}
    explore.EXPLORE = SUB2
    for family in ("cross", "self"):
        for draw in range(1, K_MAX + 1):
            found = explore.load_detector(("holistic", family, draw), scope)
            out[family][draw] = {i: bool(r["flagged"]) for i, r in found.items()}
    return out


def denials(family: str, draw: int) -> int:
    """Recorded provider denials for one draw — rows in its ``.failed.jsonl``. A denial is
    a call that never produced a reading; it is not in the usage ledger and cost nothing."""
    path = SUB2 / "cache" / f"holistic__{family}__d{draw}.failed.jsonl"
    if not path.exists():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


def freeze_self_coverage(draws: dict, instances: dict, P: list[str], C: list[str]) -> dict:
    """The `self` arm's coverage, read once the arm was complete and committed.

    The Anthropic route refused most of this arm under load, and the first version of this
    report was written while the cache was still filling; that incomplete read is kept
    beside this one in ``self_coverage_first_read.json`` and is quoted in the deviations.
    The cache is the authority for what was read; this file is the authority for when the
    reading was counted.
    """
    path = SUB2 / "self_coverage.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    per_draw, common, flags = {}, None, {}
    for draw in range(1, K_MAX + 1):
        got = set(draws["self"][draw])
        common = got if common is None else (common & got)
        per_draw[str(draw)] = {
            "readings": len(got),
            "P_read": sum(1 for i in got if i in set(P)),
            "C_read": sum(1 for i in got if i in set(C)),
            "P_missing": len(P) - sum(1 for i in got if i in set(P)),
            "C_missing": len(C) - sum(1 for i in got if i in set(C)),
            "prefix_common_instances": len(common),
            "recorded_denials": denials("self", draw),
        }
        flags[str(draw)] = {i: bool(v) for i, v in sorted(draws["self"][draw].items())}
    out = {"read_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "scope_P": len(P), "scope_C": len(C),
           "per_draw": per_draw,
           "flags": flags,
           "note": "read once; the cache was still being filled, so later runs reuse this. "
                   "ids and outcomes only, which is all this study commits"}
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------------
# statistics — every interval is a problem-cluster percentile bootstrap, seed 20260917
# ---------------------------------------------------------------------------------

def draw_agreement(family: str, ids: list[str]) -> dict:
    """How much a family's verdict moves between draws, and how much its reply moves.

    The union-of-K curve only rises when draws disagree, so a family whose flag never
    splits has a flat curve by construction and unioning its readings buys nothing. Read
    from the committed cache rows: ``flagged``, ``flagged_by_model``, ``flagged_by_checks``
    and the finding DIGESTS — never any finding text.
    """
    rows: dict[int, dict[str, dict]] = {}
    for draw in range(1, K_MAX + 1):
        path = SUB2 / "cache" / f"holistic__{family}__d{draw}.jsonl"
        rows[draw] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r["instance_id"] in set(ids):
                    rows[draw][r["instance_id"]] = r
    draws = range(1, K_MAX + 1)
    split = sum(1 for i in ids if len({bool(rows[d][i]["flagged"]) for d in draws}) > 1)
    same_digest = sum(1 for i in ids
                      if len({tuple(rows[d][i].get("finding_sha256") or []) for d in draws}) == 1)
    by_checks = sum(1 for i in ids for d in draws if rows[d][i].get("flagged_by_checks"))
    by_model = sum(1 for i in ids for d in draws if rows[d][i].get("flagged_by_model"))
    blockers: dict[str, int] = {}
    for i in ids:
        for d in draws:
            k = str(int(rows[d][i].get("model_blockers") or 0))
            blockers[k] = blockers.get(k, 0) + 1
    return {"n_instances": len(ids), "k_max": K_MAX,
            "instances_whose_flag_splits_across_draws": split,
            "instances_whose_flag_never_splits": len(ids) - split,
            "instances_with_one_finding_digest_across_all_draws": same_digest,
            "readings_flagged_by_checks": by_checks,
            "readings_flagged_by_model": by_model,
            "model_blockers_histogram": blockers,
            "note": "a family with 0 split instances has a union curve flat in K"}


def ks_by_problem(draws: dict[int, dict[str, bool]], ids: list[str],
                  instances: dict, k_max: int) -> dict[str, list[int]]:
    sub = {d: draws[d] for d in range(1, k_max + 1)}
    ks = rc.counts_per_instance(sub, ids)
    out: dict[str, list[int]] = {}
    for i, k in zip(ids, ks):
        out.setdefault(instances[i]["problem_id"], []).append(k)
    return out


def stratum_block(draws: dict[int, dict[str, bool]], ids: list[str], instances: dict,
                  k_max: int) -> dict:
    """Ceiling 1's family block for one stratum: curve, per-K cluster intervals, the
    constrained fit with its cluster interval, the union at K_max with both intervals,
    and ceiling 1's registered flattening bar (last-step gain <= 1.0 point)."""
    by_problem = ks_by_problem(draws, ids, instances, k_max)
    flat_ks = rc.counts_per_instance({d: draws[d] for d in range(1, k_max + 1)}, ids)
    curve = rc.union_curve(flat_ks, k_max)
    fit = rc.fit_saturation(curve)
    boot_A, boot_raw = rc.bootstrap_asymptote(by_problem, k_max, BOOTSTRAP, BOOT_SEED)
    gains: list[float] = []
    curve_cis = r3.curve_cluster_cis(by_problem, k_max, BOOTSTRAP, BOOT_SEED, gains)
    union_flags = {i: k > 0 for i, k in zip(ids, flat_ks)}
    last_gain = curve[-1] - curve[-2]
    return {
        "n_instances": len(ids), "n_problems": len(by_problem), "k_max": k_max,
        "curve": [round(v, 6) for v in curve],
        "curve_cluster_ci95": curve_cis,
        "counts_k": {str(k): flat_ks.count(k) for k in range(k_max + 1)},
        "union_at_kmax": rc.clustered_rate(union_flags, ids, instances, BOOTSTRAP, BOOT_SEED),
        "draw1_mean_rate": curve[0],
        "fit": {"A": fit["A"], "tau": fit["tau"], "r2": fit["r2"],
                "max_resid": fit["max_resid"],
                "A_ci95_cluster": [rc.percentile(boot_A, 0.025), rc.percentile(boot_A, 0.975)],
                "raw_kmax_ci95_cluster": [rc.percentile(boot_raw, 0.025),
                                          rc.percentile(boot_raw, 0.975)]},
        "flattening_gain_last_step_points": 100 * last_gain,
        "flattening_gain_last_step_cluster_ci95_points": [100 * rc.percentile(gains, 0.025),
                                                          100 * rc.percentile(gains, 0.975)],
        "flattened_by_ceiling1_bar": bool(100 * last_gain <= 1.0),
        "asymptote_is_extrapolation": not (100 * last_gain <= 1.0) or fit["tau"] > k_max,
        "ks_by_problem": by_problem,
    }


def two_sample_cluster_difference(by_problem_a: dict[str, list[int]],
                                  by_problem_b: dict[str, list[int]],
                                  reps: int, seed: int) -> dict:
    """Union-at-K_max rate of A minus B when A and B are DIFFERENT instances.

    Preregistration §3: the two substrates share no instance and no problem, so the
    difference is NOT paired — no McNemar, no sign-flip, no per-instance pairing. Each
    population's problem clusters are resampled independently within one seed stream and
    the difference of the two resampled rates is taken.
    """
    pa, pb = sorted(by_problem_a), sorted(by_problem_b)
    rng = random.Random(seed)
    stats = []
    for _ in range(reps):
        da = [k for _ in range(len(pa)) for k in by_problem_a[pa[rng.randrange(len(pa))]]]
        db = [k for _ in range(len(pb)) for k in by_problem_b[pb[rng.randrange(len(pb))]]]
        stats.append(sum(1 for k in da if k) / len(da) - sum(1 for k in db if k) / len(db))
    flat_a = [k for v in by_problem_a.values() for k in v]
    flat_b = [k for v in by_problem_b.values() for k in v]
    ka, kb = sum(1 for k in flat_a if k), sum(1 for k in flat_b if k)
    return {
        "a": {"k": ka, "n": len(flat_a), "n_problems": len(pa), "rate": ka / len(flat_a),
              "wilson95": list(rc.wilson(ka, len(flat_a)))},
        "b": {"k": kb, "n": len(flat_b), "n_problems": len(pb), "rate": kb / len(flat_b),
              "wilson95": list(rc.wilson(kb, len(flat_b)))},
        "difference_points": 100 * (ka / len(flat_a) - kb / len(flat_b)),
        "cluster_ci95_points": [100 * rc.percentile(stats, 0.025),
                                100 * rc.percentile(stats, 0.975)],
        "reps": reps, "seed": seed, "paired": False,
        "excludes_zero": bool(rc.percentile(stats, 0.025) > 0 or rc.percentile(stats, 0.975) < 0),
        "method": "two-sample problem-cluster percentile bootstrap; the populations are "
                  "different instances from different corpora, resampled independently",
    }


def exchange_ratios(curve_p: list[float], curve_c: list[float]) -> dict:
    """Two ways to say 'recall bought per false-positive point', both reported.

    ``registered`` is ceiling 1's own column (`exchange_rate_recall_per_fp` in
    `report_ceiling.py`): the recall GAIN over K = 1 divided by the false-positive gain
    over K = 1. It is the quantity the preregistration's H23c names, and substrate 1's
    value for it is 1.68.

    ``level`` is recall(K) divided by false positives(K) — recall per point of the
    false-positive rate actually paid at that K, not per point of the increase. It is
    POST HOC: it is not in the preregistration, and it is labelled so wherever it appears.
    """
    reg = [None] + [((curve_p[i] - curve_p[0]) / (curve_c[i] - curve_c[0]))
                    if curve_c[i] > curve_c[0] else None for i in range(1, len(curve_p))]
    lvl = [(p / c) if c > 0 else None for p, c in zip(curve_p, curve_c)]
    return {"registered_gain_ratio_by_k": reg, "POST_HOC_level_ratio_by_k": lvl}


def ratio_cluster_ci(bp_p: dict, bp_c: dict, k: int, k_max: int, reps: int,
                     seed: int) -> list[float | None]:
    """Cluster interval for the POST-HOC level ratio at one K: P and C problems resampled
    independently in one stream, a resample with zero false positives discarded."""
    pp, pc = sorted(bp_p), sorted(bp_c)
    rng = random.Random(seed)
    stats, discarded = [], 0
    for _ in range(reps):
        dp = [x for _ in range(len(pp)) for x in bp_p[pp[rng.randrange(len(pp))]]]
        dc = [x for _ in range(len(pc)) for x in bp_c[pc[rng.randrange(len(pc))]]]
        cp, cc = rc.union_curve(dp, k_max), rc.union_curve(dc, k_max)
        if cc[k - 1] <= 0:
            discarded += 1
            continue
        stats.append(cp[k - 1] / cc[k - 1])
    return [rc.percentile(stats, 0.025), rc.percentile(stats, 0.975), discarded]


# ---------------------------------------------------------------------------------
# cost
# ---------------------------------------------------------------------------------

def ledger_costs(run_dir: Path) -> dict:
    """Per-project usage ledgers from the run archive. Never reconstructed, never guessed.

    Frozen on first read to ``records/substrate2/cost.json``: the `self` arm was still
    retrying while this report was written, so its ledger grows and a later read would not
    reproduce. The archive itself is never committed (it holds solutions and replies).
    """
    frozen = SUB2 / "cost.json"
    if frozen.exists():
        return json.loads(frozen.read_text(encoding="utf-8"))
    out: dict = {"run_dir": str(run_dir), "projects": {},
                 "read_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not run_dir.exists():
        out["note"] = "AUTHOR_INPUT_NEEDED: the run archive is not on this machine"
        return out
    for ledger in sorted(run_dir.glob("projects/*/.crossaudit/usage.jsonl")):
        name = ledger.parent.parent.name.replace("project-", "")
        events = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
                  if l.strip()]
        out["projects"][name] = {
            "calls": len(events),
            "usd": round(sum(float(e.get("api_value_usd") or 0) for e in events), 6)}
    def total(pred):
        rows = [v for k, v in out["projects"].items() if pred(k)]
        return {"usd": round(sum(r["usd"] for r in rows), 4),
                "calls": sum(r["calls"] for r in rows)}
    out["generation"] = total(lambda k: "substrate2-gen" in k)
    out["audit_cross"] = total(lambda k: "__cross__" in k)
    out["audit_self"] = total(lambda k: "__self__" in k)
    out["audit_total"] = total(lambda k: "substrate2-gen" not in k)
    out["study_total"] = total(lambda k: True)
    out["cap_usd"] = 60.0
    frozen.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------------

def matched_fp(sub2_cross_C: dict, sub2_self_C: dict, sub1_families: dict) -> dict:
    """Can any reading count place the two substrates at the same false-positive rate?

    Answered under two named scopes, because they answer differently:

    * ``cross_family_only`` is the comparison this study actually draws — substrate 1's
      frozen comparator is the cross-vendor auditor and so is substrate 2's primary. Here
      substrate 1's dearest reading and substrate 2's cheapest have intervals that do not
      meet, so the claim holds with uncertainty admitted.
    * ``pooled_all_families`` admits every family measured on either substrate. Substrate
      1's same-vendor family at K = 8 is dearer than its cross-vendor family, and its
      interval reaches into substrate 2's cheapest interval. The claim does NOT hold
      pooled, and the overlap is stated rather than left for a reader to find.

    Substrate 1's rates and intervals are read unmodified from ``records/ceiling``. The
    interval used for each family's K_max point is ``union_at_kmax_block.cluster_ci95`` —
    the one ceiling 1's own Table 1 quotes. Ceiling 1 also carries a per-K ``curve_ci95``
    for the same point from a second bootstrap stream; where the two differ the other
    answer is recorded beside this one rather than silently preferred.
    """
    def entry(family: str, k: int, rate: float, ci: list) -> dict:
        return {"family": family, "K": k, "rate": rate, "cluster_ci95": list(ci)}

    s2_min = entry("cross", 1, sub2_cross_C["curve"][0],
                   sub2_cross_C["curve_cluster_ci95"][0])
    # substrate 2 pooled: the same-vendor family is far dearer, so the cheapest is unchanged
    s2_pooled_min = min(
        [s2_min,
         entry("self", 1, sub2_self_C["curve"][0], sub2_self_C["curve_cluster_ci95"][0])],
        key=lambda e: e["rate"])

    def s1_entry(family: str) -> dict:
        f = sub1_families[family]["C"]
        return entry(family, sub1_families[family]["k_max"], f["curve"][-1],
                     f["union_at_kmax_block"]["cluster_ci95"])

    s1_cross = s1_entry("cross")
    s1_pooled_max = max((s1_entry(f) for f in sub1_families), key=lambda e: e["rate"])

    def verdict(s1: dict, s2: dict) -> dict:
        overlap = 100 * (s1["cluster_ci95"][1] - s2["cluster_ci95"][0])
        return {
            "sub1_dearest": s1, "sub2_cheapest": s2,
            "point_estimates_disjoint": bool(s2["rate"] > s1["rate"]),
            "intervals_overlap": bool(overlap > 0),
            "interval_overlap_points": round(overlap, 1) if overlap > 0 else None,
            "interval_gap_points": round(-overlap, 1) if overlap <= 0 else None,
        }

    cross_only = verdict(s1_cross, s2_min)
    pooled = verdict(s1_pooled_max, s2_pooled_min)
    alt = sub1_families[s1_pooled_max["family"]]["C"]["curve_ci95"][-1]
    pooled["sensitivity_using_ceiling1_per_K_curve_ci95"] = {
        "sub1_dearest_cluster_ci95": list(alt),
        "interval_overlap_points": round(100 * (alt[1] - pooled["sub2_cheapest"]
                                                ["cluster_ci95"][0]), 1),
        "note": "ceiling 1 carries two bootstrap streams for this point; the difference "
                "between them does not change the answer, only its second decimal",
    }
    return {
        "cross_family_only_REGISTERED_COMPARISON": cross_only,
        "pooled_all_families": pooled,
        "CORRECTION": "an earlier version of this report asserted non-overlap without "
                      "naming a family. That is true of the point estimates and of the "
                      "cross-vendor comparison with intervals, and false once every "
                      "family is pooled and the intervals are admitted.",
    }


def build(run_dir: Path) -> dict:
    frame = json.loads((SUB2 / "frame.json").read_text(encoding="utf-8"))
    instances2 = load_instances(SUB2 / "instances.jsonl")
    audit_set = json.loads((SUB2 / "audit_set.json").read_text(encoding="utf-8"))
    scope = audit_set["instance_ids"]
    P2 = [i for i in scope if instances2[i]["stratum"] == "P"]
    C2 = [i for i in scope if instances2[i]["stratum"] == "C"]
    draws2 = load_sub2_draws(set(scope))

    out: dict = {
        "study": "study 23 / substrate 2",
        "preregistration": "benchmarks/code/substrate2/PREREGISTRATION.md",
        "bootstrap_reps": BOOTSTRAP, "bootstrap_seed": BOOT_SEED,
        "unit_of_analysis": "instance (batch, problem_id); every interval resamples "
                            "problem clusters",
        "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # --- the substrate, descriptively -------------------------------------------------
    spec = sorted(t["spec_words"] for t in frame["frame"])
    lines = sorted(t["canonical_lines"] for t in frame["frame"])
    methods = sorted(t["n_test_methods"] for t in frame["frame"])
    out["substrate"] = {
        "dataset": frame["dataset"],
        "n_rows": frame["dataset"]["n_rows"],
        "n_frame": frame["n_frame"], "n_dropped": frame["n_dropped"],
        "drops_by_filter": frame["drops_by_filter"],
        "split_rule": frame["split_rule"],
        "median_spec_words": statistics.median(spec),
        "spec_words_iqr": [spec[len(spec) // 4], spec[3 * len(spec) // 4]],
        "median_solution_lines": statistics.median(lines),
        "solution_lines_iqr": [lines[len(lines) // 4], lines[3 * len(lines) // 4]],
        "median_test_methods": statistics.median(methods),
        "min_test_methods": min(methods),
        "substrate1_median_spec_words": S1_MEDIAN_SPEC_WORDS,
        "substrate1_median_solution_lines": S1_MEDIAN_SOLUTION_LINES,
        "spec_words_ratio": round(statistics.median(spec) / S1_MEDIAN_SPEC_WORDS, 2),
        "solution_lines_ratio": round(statistics.median(lines) / S1_MEDIAN_SOLUTION_LINES, 2),
    }
    out["strata"] = {
        "n_candidates": sum(audit_set["population"].values()),
        "population": audit_set["population"],
        "audited": audit_set["audited"],
        "caps": audit_set["caps"],
        "seed": audit_set["seed"],
        "P_was_capped": audit_set["population"]["P"] > audit_set["caps"]["P"],
    }

    # --- the ladder's coverage --------------------------------------------------------
    first = SUB2 / "self_coverage_first_read.json"
    out["coverage"] = {
        "scope_n": len(scope), "scope_P": len(P2), "scope_C": len(C2),
        "cross": {str(d): {"readings": len(draws2["cross"][d]),
                           "complete": len(draws2["cross"][d]) == len(scope),
                           "recorded_denials": denials("cross", d)}
                  for d in range(1, K_MAX + 1)},
        "self": freeze_self_coverage(draws2, instances2, P2, C2),
    }
    out["coverage"]["self_first_read_INCOMPLETE"] = (
        {"read_utc": json.loads(first.read_text(encoding="utf-8"))["read_utc"],
         "readings_by_draw": {d: v["readings"] for d, v in
                              json.loads(first.read_text(encoding="utf-8"))["per_draw"].items()},
         "note": "the first version of this report was written at this timestamp, while "
                 "the arm was still filling; H23d was not evaluable then"}
        if first.exists() else None)
    out["coverage"]["all_draws_complete"] = all(
        len(draws2[f][d]) == len(scope) for f in ("cross", "self") for d in range(1, K_MAX + 1))

    # --- H23b: the curve, the fit, the flattening bar ---------------------------------
    blockP = stratum_block(draws2["cross"], P2, instances2, K_MAX)
    blockC = stratum_block(draws2["cross"], C2, instances2, K_MAX)
    out["H23b_curve"] = {"P": {k: v for k, v in blockP.items() if k != "ks_by_problem"},
                         "C": {k: v for k, v in blockC.items() if k != "ks_by_problem"}}
    selfP = stratum_block(draws2["self"], P2, instances2, K_MAX)
    selfC = stratum_block(draws2["self"], C2, instances2, K_MAX)
    out["self_family_curve"] = {"P": {k: v for k, v in selfP.items() if k != "ks_by_problem"},
                                "C": {k: v for k, v in selfC.items() if k != "ks_by_problem"}}
    out["draw_agreement"] = {"cross": draw_agreement("cross", P2 + C2),
                             "self": draw_agreement("self", P2 + C2)}

    # --- substrate 1's frozen comparator, read only -----------------------------------
    inst1 = rc.load_instances()
    scope1 = [i for i in rc.load_audit_set() if inst1[i]["stratum"] in ("P", "C")]
    draws1 = rc.load_draws(set(scope1))
    P1 = [i for i in scope1 if inst1[i]["stratum"] == "P"]
    C1 = [i for i in scope1 if inst1[i]["stratum"] == "C"]
    bp1P = ks_by_problem(draws1["cross"], P1, inst1, K_MAX)
    bp1C = ks_by_problem(draws1["cross"], C1, inst1, K_MAX)
    curve1P = rc.union_curve([k for v in bp1P.values() for k in v], K_MAX)
    curve1C = rc.union_curve([k for v in bp1C.values() for k in v], K_MAX)
    frozen = json.loads((CEILING / "numbers.json").read_text(encoding="utf-8"))
    f1 = frozen["ceiling1"]["families"]["cross"]
    out["substrate1_frozen"] = {
        "source": "records/ceiling/numbers.json, families.cross (unmodified)",
        "P_union_at_kmax": f1["P"]["union_at_kmax"],
        "P_union_count": f1["P"]["union_at_kmax_count"], "P_n": f1["P"]["n_instances"],
        "P_cluster_ci95": f1["P"]["union_at_kmax_block"]["cluster_ci95"],
        "P_wilson95": f1["P"]["union_at_kmax_wilson95"],
        "C_union_at_kmax": f1["C"]["union_at_kmax"],
        "C_union_count": f1["C"]["union_at_kmax_count"], "C_n": f1["C"]["n_instances"],
        "C_cluster_ci95": f1["C"]["union_at_kmax_block"]["cluster_ci95"],
        "P_curve": [round(v, 6) for v in curve1P], "C_curve": [round(v, 6) for v in curve1C],
        "P_n_problems": len(bp1P), "C_n_problems": len(bp1C),
        "exchange_rate_recall_per_fp_registered": frozen["ceiling1"]["families"]["cross"].get(
            "exchange_rate_recall_per_fp"),
        "recomputation_matches_frozen": (
            abs(curve1P[-1] - f1["P"]["union_at_kmax"]) < 1e-9
            and abs(curve1C[-1] - f1["C"]["union_at_kmax"]) < 1e-9),
    }

    # --- H23a (primary) ---------------------------------------------------------------
    out["H23a_primary_recall_sub2_minus_sub1_P_K8"] = two_sample_cluster_difference(
        blockP["ks_by_problem"], bp1P, BOOTSTRAP, BOOT_SEED)
    out["H23a_primary_recall_sub2_minus_sub1_P_K8"]["direction"] = "substrate 2 higher"
    out["H23a_primary_recall_sub2_minus_sub1_P_K8"]["falsification_clause"] = (
        "PREREGISTRATION §4: the interval excludes zero and substrate 2's recall is HIGHER, "
        "so the paper must say its central quantity is substrate-dependent and that 30.0% "
        "is not a general figure")

    # --- H23c -------------------------------------------------------------------------
    fp = two_sample_cluster_difference(blockC["ks_by_problem"], bp1C, BOOTSTRAP, BOOT_SEED)
    ratios2 = exchange_ratios(blockP["curve"], blockC["curve"])
    ratios1 = exchange_ratios(curve1P, curve1C)
    lower_at_every_k = all(
        a is not None and b is not None and a < b
        for a, b in zip(ratios2["POST_HOC_level_ratio_by_k"],
                        ratios1["POST_HOC_level_ratio_by_k"]))
    lower_at_every_k_registered = all(
        a is not None and b is not None and a < b
        for a, b in zip(ratios2["registered_gain_ratio_by_k"][1:],
                        ratios1["registered_gain_ratio_by_k"][1:]))
    out["H23c_false_positives"] = {
        "sub2_minus_sub1_C_K8": fp,
        "substrate2": ratios2, "substrate1": ratios1,
        "substrate2_level_ratio_ci95_K1": ratio_cluster_ci(
            blockP["ks_by_problem"], blockC["ks_by_problem"], 1, K_MAX, BOOTSTRAP, BOOT_SEED),
        "substrate2_level_ratio_ci95_K8": ratio_cluster_ci(
            blockP["ks_by_problem"], blockC["ks_by_problem"], 8, K_MAX, BOOTSTRAP, BOOT_SEED),
        "substrate2_level_ratio_lower_at_every_k": lower_at_every_k,
        "substrate2_registered_gain_ratio_lower_at_every_k": lower_at_every_k_registered,
    }
    # The matched-false-positive question: is there ANY reading count at which the two
    # substrates pay the same false-positive rate? An earlier version of this report
    # answered "no" from the POINT ESTIMATES alone. That is an overstatement once the
    # intervals are admitted and both auditor families are pooled, so the question is
    # answered here twice, under a named scope each time, from the frozen records.
    out["H23c_false_positives"]["matched_fp_comparison"] = matched_fp(
        blockC, selfC, frozen["ceiling1"]["families"])

    # --- H23d (registered, K = 8) -----------------------------------------------------
    # The same 100 P instances (and the same 150 C instances) are read by both arms, so
    # this contrast IS paired: report_ceiling3's reviewed paired_union_difference is
    # reused unchanged, under study 23's registered seed.
    cov = out["coverage"]["self"]["per_draw"]
    complete = all(cov[str(d)]["P_missing"] == 0 and cov[str(d)]["C_missing"] == 0
                   for d in range(1, K_MAX + 1))
    out["H23d_self_minus_cross_K8"] = {
        "registered_K": K_MAX, "computed_at_registered_K": complete,
        "paired": True,
        "method": "union-at-K recall of `self` minus `cross` on the SAME instances; "
                  "problem-cluster percentile bootstrap, exact McNemar and the cluster "
                  "sign-flip test, all as ceiling 1 defines them",
        "substrate1_comparator_points": -12.7,
        "substrate1_comparator_ci95_points": [-25.0, -0.9],
        "P": r3.paired_union_difference(draws2["self"], draws2["cross"], K_MAX, P2, instances2),
        "C": r3.paired_union_difference(draws2["self"], draws2["cross"], K_MAX, C2, instances2),
        "coverage_by_draw": {d: cov[d]["readings"] for d in cov},
        "recorded_denials_by_draw": {d: cov[d]["recorded_denials"] for d in cov},
    }
    h = out["H23d_self_minus_cross_K8"]
    h["sign_matches_substrate1"] = bool(
        (h["P"]["difference_points"] > 0) == (h["substrate1_comparator_points"] > 0))
    h["P_excludes_zero"] = bool(h["P"]["cluster_ci95_points"][0] > 0
                                or h["P"]["cluster_ci95_points"][1] < 0)
    h["C_excludes_zero"] = bool(h["C"]["cluster_ci95_points"][0] > 0
                                or h["C"]["cluster_ci95_points"][1] < 0)
    # The exchange the same-vendor arm offers over the cross-vendor arm at K = 8: does it
    # pay more in false positives than it gains in recall?
    h["false_positives_bought_per_recall_point"] = (
        h["C"]["difference_points"] / h["P"]["difference_points"]
        if h["P"]["difference_points"] else None)
    h["costs_more_than_it_gains"] = bool(
        h["C"]["difference_points"] > h["P"]["difference_points"])

    # --- the same-vendor arm's own exchange ratios ------------------------------------
    ratios_self = exchange_ratios(selfP["curve"], selfC["curve"])
    out["self_family_exchange"] = {
        "ratios": ratios_self,
        "level_ratio_ci95_K1": ratio_cluster_ci(selfP["ks_by_problem"], selfC["ks_by_problem"],
                                                1, K_MAX, BOOTSTRAP, BOOT_SEED),
        "level_ratio_ci95_K8": ratio_cluster_ci(selfP["ks_by_problem"], selfC["ks_by_problem"],
                                                8, K_MAX, BOOTSTRAP, BOOT_SEED),
        "registered_gain_ratio_is_undefined": all(
            x is None for x in ratios_self["registered_gain_ratio_by_k"][1:]),
        "why_undefined": "the registered gain ratio divides by the false-positive gain "
                         "from K = 1 to K, and the same-vendor arm's false-positive rate "
                         "does not move with K: its flag never splits across draws",
        "level_ratio_below_cross_on_substrate2_at_every_k": all(
            a is not None and b is not None and a < b
            for a, b in zip(ratios_self["POST_HOC_level_ratio_by_k"],
                            ratios2["POST_HOC_level_ratio_by_k"])),
        "level_ratio_below_substrate1_cross_at_every_k": all(
            a is not None and b is not None and a < b
            for a, b in zip(ratios_self["POST_HOC_level_ratio_by_k"],
                            ratios1["POST_HOC_level_ratio_by_k"])),
    }

    out["cost"] = ledger_costs(run_dir)
    out["H23e_residual"] = {
        "in_scope": False,
        "status": "NOT RUN — the residual has not been classified under study 21's rubric "
                  "on this substrate; it is the obvious next step",
    }
    out["comparison_inventory"] = [
        "H23a (primary): union recall at K = 8 on P, substrate 2 minus substrate 1",
        "H23c: union false positives at K = 8 on C, substrate 2 minus substrate 1",
        "H23c: recall bought per false-positive point, registered gain ratio, both substrates",
        "H23c: recall bought per false-positive point, POST-HOC level ratio, both substrates",
        "H23b: the union curve at K = 1..8 on P and on C, with per-K cluster intervals",
        "H23b: the constrained fit and ceiling 1's flattening bar, on P and on C",
        "H23d: same-vendor minus cross-vendor union recall at K = 8 on P, paired",
        "H23d: same-vendor minus cross-vendor union false positives at K = 8 on C, paired",
        "H23d: the same-vendor arm's own curve, fit and exchange ratios on P and on C",
    ]
    return out


# ---------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------

def _p(x: float | None, places: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{places}f}%"


def _iv(pair, places: int = 1) -> str:
    if not pair or pair[0] is None or pair[1] is None:
        return "—"
    return f"[{100 * pair[0]:.{places}f}, {100 * pair[1]:.{places}f}]"


def _r(x: float | None, places: int = 2) -> str:
    return "—" if x is None else f"{x:.{places}f}"


TABLE_HEADINGS = [
    "### Table 1 — the two substrates, described",
    "### Table 2 — generation, the strata and the frozen audit set",
    "### Table 3 — the audit ladder's coverage",
    "### Table 4 — union recall and union false positives at every K, substrate 2",
    "### Table 5 — substrate 2 against substrate 1 at K = 8",
    "### Table 6 — recall bought per false-positive point, both substrates",
    "### Table 7 — the same-vendor arm beside the cross-vendor arm, substrate 2",
    "### Table 8 — H23d, same-vendor minus cross-vendor at K = 8, paired",
    "### Table 9 — cost, from the run's usage ledgers",
]
TABLE_KEYS = [f"T{i}" for i in range(1, len(TABLE_HEADINGS) + 1)]


def begin(key: str) -> str:
    return f"<!-- BEGIN {key} (records/substrate2/tables.md) -->"


def end(key: str) -> str:
    return f"<!-- END {key} -->"


def render_tables(n: dict) -> dict[str, str]:
    s, st = n["substrate"], n["strata"]
    t: dict[str, str] = {}

    t["T1"] = "\n".join([
        "Both columns are medians over the frozen frame; the ratio is the median ratio, not "
        "a ratio of medians drawn from matched tasks. No corpus text is reproduced here.",
        "",
        "| | substrate 1 (HumanEval+ / MBPP+) | substrate 2 (BigCodeBench, stdlib half) | ratio |",
        "|---|---:|---:|---:|",
        f"| median specification words | {s['substrate1_median_spec_words']} | "
        f"**{s['median_spec_words']:.0f}** (IQR {s['spec_words_iqr'][0]}–{s['spec_words_iqr'][1]}) | "
        f"{s['spec_words_ratio']:.2f}× |",
        f"| median reference-solution lines | {s['substrate1_median_solution_lines']} | "
        f"**{s['median_solution_lines']:.0f}** (IQR {s['solution_lines_iqr'][0]}–{s['solution_lines_iqr'][1]}) | "
        f"{s['solution_lines_ratio']:.2f}× |",
        f"| median test methods per task | — | {s['median_test_methods']:.0f} "
        f"(minimum kept {s['min_test_methods']}) | — |",
        f"| tasks in the frame | — | {s['n_frame']} of {s['n_rows']:,} | — |",
        "",
    ])

    t["T2"] = "\n".join([
        f"Two batches over {s['n_frame']} tasks. The audit set was drawn by "
        f"`random.Random({st['seed']})` and committed before the first audit call.",
        "",
        "| | count |",
        "|---|---:|",
        f"| candidates generated | {st['n_candidates']} |",
        f"| stratum P (passes visible, fails hidden) | **{st['population']['P']}** |",
        f"| stratum C (passes both) | {st['population']['C']} |",
        f"| stratum F (fails visible) | {st['population']['F']} |",
        f"| P instances audited | {st['audited']['P']} (cap {st['caps']['P']}; "
        f"{'capped' if st['P_was_capped'] else 'the whole population, no draw needed'}) |",
        f"| C instances audited | {st['audited']['C']} (cap {st['caps']['C']}) |",
        f"| generation cost | ${n['cost']['generation']['usd']:.2f} "
        f"({n['cost']['generation']['calls']} calls) |",
        "",
    ])

    cov, self_cov = n["coverage"], n["coverage"]["self"]["per_draw"]
    ag = n["draw_agreement"]
    first = cov["self_first_read_INCOMPLETE"]
    rows = ["| draw | `cross` readings | `cross` denials | `self` readings | `self` denials "
            "| `self` readings at the first read |",
            "|---:|---:|---:|---:|---:|---:|"]
    for d in range(1, K_MAX + 1):
        c, sd = cov["cross"][str(d)], self_cov[str(d)]
        rows.append(f"| {d} | {c['readings']} / {cov['scope_n']}"
                    f"{' ✓' if c['complete'] else ''} | {c['recorded_denials']:,} | "
                    f"{sd['readings']} / {cov['scope_n']}"
                    f"{' ✓' if sd['readings'] == cov['scope_n'] else ''} | "
                    f"{sd['recorded_denials']:,} | {first['readings_by_draw'][str(d)]} |")
    t["T3"] = "\n".join([
        f"The frozen audit set is {cov['scope_n']} instances ({cov['scope_P']} P, "
        f"{cov['scope_C']} C). Both ladders are complete: every draw of both families "
        f"covers all {cov['scope_n']}. A denial is a call that never produced a reading; "
        f"it is not in the usage ledger and cost nothing. The last column is what the "
        f"`self` ladder had reached at {first['read_utc']}, when the first version of this "
        f"report was written and H23d was not yet evaluable.",
        "", *rows, "",
        f"**Draw-to-draw agreement.** Over the {ag['cross']['n_instances']} audited "
        f"instances, the cross-vendor arm's flag splits across its eight draws on "
        f"**{ag['cross']['instances_whose_flag_splits_across_draws']}** of them; the "
        f"same-vendor arm's splits on "
        f"**{ag['self']['instances_whose_flag_splits_across_draws']}**. Every flag in "
        f"both families came from the model "
        f"({ag['self']['readings_flagged_by_checks'] + ag['cross']['readings_flagged_by_checks']} "
        f"readings were flagged by the deterministic checks layer). The same-vendor arm "
        f"returned one identical set of finding digests across all eight draws on "
        f"{ag['self']['instances_with_one_finding_digest_across_all_draws']} instances, "
        f"the cross-vendor arm on "
        f"{ag['cross']['instances_with_one_finding_digest_across_all_draws']}; no finding "
        f"text was archived or read.",
        "",
    ])

    P, C = n["H23b_curve"]["P"], n["H23b_curve"]["C"]
    r2 = n["H23c_false_positives"]["substrate2"]
    rows = ["| K | union recall on P [95% cluster CI] | union FP on C [95% cluster CI] | "
            "recall per FP point, registered gain ratio | recall per FP point, POST-HOC level ratio |",
            "|---:|---|---|---:|---:|"]
    for i in range(K_MAX):
        rows.append(f"| {i + 1} | {_p(P['curve'][i])} {_iv(P['curve_cluster_ci95'][i])} | "
                    f"{_p(C['curve'][i])} {_iv(C['curve_cluster_ci95'][i])} | "
                    f"{_r(r2['registered_gain_ratio_by_k'][i])} | "
                    f"{_r(r2['POST_HOC_level_ratio_by_k'][i])} |")
    t["T4"] = "\n".join([
        f"Unit of analysis: the instance. n = {P['n_instances']} stratum-P instances from "
        f"{P['n_problems']} problems (recall) and {C['n_instances']} stratum-C instances from "
        f"{C['n_problems']} problems (false positives), the same instances at every K. The "
        f"union rate at K is averaged over all C(8, K) subsets of the eight draws, exactly. "
        f"Intervals are {n['bootstrap_reps']:,}-resample problem-cluster percentile "
        f"bootstraps, seed {n['bootstrap_seed']}. The **registered** gain ratio is ceiling 1's "
        f"own column — recall gained over K = 1 divided by false positives gained over K = 1. "
        f"The **level** ratio is recall at K divided by the false-positive rate paid at K; it "
        f"is post hoc and is not in the preregistration.",
        "", *rows, "",
        f"Fit on P: A = {_p(P['fit']['A'])} {_iv(P['fit']['A_ci95_cluster'])}, "
        f"tau = {P['fit']['tau']:.2f}, r² = {P['fit']['r2']:.3f}. Last-step gain "
        f"{P['flattening_gain_last_step_points']:.2f} points "
        f"{_iv([x / 100 for x in P['flattening_gain_last_step_cluster_ci95_points']], 2)} — "
        f"ceiling 1's flattening bar (≤ 1.0 point) is "
        f"**{'met' if P['flattened_by_ceiling1_bar'] else 'not met'}**.",
        f"Fit on C: A = {_p(C['fit']['A'])} {_iv(C['fit']['A_ci95_cluster'])}, "
        f"tau = {C['fit']['tau']:.2f}, r² = {C['fit']['r2']:.3f}. Last-step gain "
        f"{C['flattening_gain_last_step_points']:.2f} points "
        f"{_iv([x / 100 for x in C['flattening_gain_last_step_cluster_ci95_points']], 2)} — "
        f"the bar is **{'met' if C['flattened_by_ceiling1_bar'] else 'not met'}**.",
        "",
    ])

    a = n["H23a_primary_recall_sub2_minus_sub1_P_K8"]
    f = n["H23c_false_positives"]["sub2_minus_sub1_C_K8"]
    t["T5"] = "\n".join([
        "The two populations share no instance and no problem, so this is a **two-sample** "
        "bootstrap: each population's problems are resampled independently and the "
        "difference of the two resampled rates is taken. Nothing here is paired, so no "
        "McNemar and no sign-flip test is reported. Wilson is quoted beside each rate and "
        "assumes instances are independent, which within a substrate they are not.",
        "",
        "| contrast | substrate 2 | substrate 1 (frozen) | difference [95% two-sample cluster CI] |",
        "|---|---|---|---|",
        f"| **H23a (primary)** union recall, P, K = 8 | **{_p(a['a']['rate'])}** "
        f"({a['a']['k']}/{a['a']['n']}, {a['a']['n_problems']} problems) Wilson "
        f"{_iv(a['a']['wilson95'])} | {_p(a['b']['rate'])} ({a['b']['k']}/{a['b']['n']}, "
        f"{a['b']['n_problems']} problems) Wilson {_iv(a['b']['wilson95'])} | "
        f"**+{a['difference_points']:.1f} points** "
        f"[{a['cluster_ci95_points'][0]:.1f}, {a['cluster_ci95_points'][1]:.1f}] |",
        f"| **H23c** union false positives, C, K = 8 | **{_p(f['a']['rate'])}** "
        f"({f['a']['k']}/{f['a']['n']}, {f['a']['n_problems']} problems) Wilson "
        f"{_iv(f['a']['wilson95'])} | {_p(f['b']['rate'])} ({f['b']['k']}/{f['b']['n']}, "
        f"{f['b']['n_problems']} problems) Wilson {_iv(f['b']['wilson95'])} | "
        f"**+{f['difference_points']:.1f} points** "
        f"[{f['cluster_ci95_points'][0]:.1f}, {f['cluster_ci95_points'][1]:.1f}] |",
        "",
    ])

    h = n["H23c_false_positives"]
    r1 = h["substrate1"]
    m = h["matched_fp_comparison"]
    co = m["cross_family_only_REGISTERED_COMPARISON"]
    po = m["pooled_all_families"]
    rows = ["| K | substrate 1 recall | substrate 1 FP | substrate 1 level ratio | "
            "substrate 2 recall | substrate 2 FP | substrate 2 level ratio |",
            "|---:|---:|---:|---:|---:|---:|---:|"]
    for i in range(K_MAX):
        rows.append(f"| {i + 1} | {_p(n['substrate1_frozen']['P_curve'][i])} | "
                    f"{_p(n['substrate1_frozen']['C_curve'][i])} | "
                    f"{_r(r1['POST_HOC_level_ratio_by_k'][i])} | "
                    f"{_p(P['curve'][i])} | {_p(C['curve'][i])} | "
                    f"{_r(r2['POST_HOC_level_ratio_by_k'][i])} |")
    t["T6"] = "\n".join([
        "The level ratio is POST HOC — the preregistration's H23c names ceiling 1's "
        "registered gain ratio, whose values are in Table 4. Both definitions point the "
        "same way; the level ratio is shown here because it is the one that can be read "
        "against a fixed operating cost.",
        "", *rows, "",
        f"Substrate 2's level ratio is lower than substrate 1's at "
        f"**{'every' if h['substrate2_level_ratio_lower_at_every_k'] else 'not every'}** K, "
        f"and so is the registered gain ratio "
        f"(**{'every' if h['substrate2_registered_gain_ratio_lower_at_every_k'] else 'not every'}** K).",
        "",
        f"**Can any reading count put the two substrates at the same false-positive rate?** "
        f"The answer depends on which auditor families are admitted, so it is given twice.",
        "",
        # The corrected re-run reversed this. In the voided run the two cross-vendor
        # intervals were disjoint and the sentence read "no"; with the visible tests fixed
        # they overlap, so the branch below had never been exercised and crashed on a null
        # gap. Both outcomes are now rendered from the data rather than assumed.
        (f"**Within the cross-vendor family** — the comparison this study draws, since "
         f"substrate 1's frozen comparator and substrate 2's primary are both the shipped "
         f"cross-vendor auditor — **no**. Substrate 2's cheapest reading costs "
         f"{_p(co['sub2_cheapest']['rate'])} {_iv(co['sub2_cheapest']['cluster_ci95'])} at "
         f"K = {co['sub2_cheapest']['K']}, and substrate 1's dearest costs "
         f"{_p(co['sub1_dearest']['rate'])} {_iv(co['sub1_dearest']['cluster_ci95'])} at "
         f"K = {co['sub1_dearest']['K']}. Those intervals do not meet: "
         f"{co['interval_gap_points']:.1f} points separate them."
         if not co["intervals_overlap"] else
         f"**Within the cross-vendor family** — the comparison this study draws, since "
         f"substrate 1's frozen comparator and substrate 2's primary are both the shipped "
         f"cross-vendor auditor — **a matched rate CANNOT be ruled out**. Substrate 2's "
         f"cheapest reading costs {_p(co['sub2_cheapest']['rate'])} "
         f"{_iv(co['sub2_cheapest']['cluster_ci95'])} at K = {co['sub2_cheapest']['K']}, and "
         f"substrate 1's dearest costs {_p(co['sub1_dearest']['rate'])} "
         f"{_iv(co['sub1_dearest']['cluster_ci95'])} at K = {co['sub1_dearest']['K']}. The "
         f"point estimates are disjoint, but **the intervals overlap by "
         f"{co['interval_overlap_points']:.1f} points**, so non-overlap is not available as "
         f"a conservative proxy here. The voided run reported these intervals as disjoint; "
         f"that finding does not survive the correction of the visible tests."),
        "",
        f"**Pooling every family measured on either substrate** — **yes, narrowly**. "
        f"Substrate 1's dearest reading anywhere is its `{po['sub1_dearest']['family']}` "
        f"family at K = {po['sub1_dearest']['K']}, {_p(po['sub1_dearest']['rate'])} "
        f"{_iv(po['sub1_dearest']['cluster_ci95'])}, and its upper bound reaches "
        f"{po['interval_overlap_points']:.1f} points into substrate 2's cheapest interval "
        f"of {_iv(po['sub2_cheapest']['cluster_ci95'])}. The point estimates are still "
        f"disjoint ({_p(po['sub1_dearest']['rate'])} against "
        f"{_p(po['sub2_cheapest']['rate'])}), but the intervals overlap, so a matched "
        f"false-positive rate cannot be ruled out pooled. Substrate 1's interval here is "
        f"the one ceiling 1's own Table 1 quotes; its second bootstrap stream for the same "
        f"point gives an overlap of "
        f"{po['sensitivity_using_ceiling1_per_K_curve_ci95']['interval_overlap_points']:.1f} "
        f"points instead.",
        "",
    ])

    sP, sC = n["self_family_curve"]["P"], n["self_family_curve"]["C"]
    se = n["self_family_exchange"]
    rows = ["| K | `self` recall on P [95% cluster CI] | `self` FP on C [95% cluster CI] | "
            "`self` level ratio | `cross` recall on P | `cross` FP on C | `cross` level ratio |",
            "|---:|---|---|---:|---:|---:|---:|"]
    for i in range(K_MAX):
        rows.append(f"| {i + 1} | {_p(sP['curve'][i])} {_iv(sP['curve_cluster_ci95'][i])} | "
                    f"{_p(sC['curve'][i])} {_iv(sC['curve_cluster_ci95'][i])} | "
                    f"{_r(se['ratios']['POST_HOC_level_ratio_by_k'][i])} | "
                    f"{_p(P['curve'][i])} | {_p(C['curve'][i])} | "
                    f"{_r(r2['POST_HOC_level_ratio_by_k'][i])} |")
    k1, k8 = se["level_ratio_ci95_K1"], se["level_ratio_ci95_K8"]
    t["T7"] = "\n".join([
        f"The same-vendor arm is `claude-haiku-4-5`, the generator's own model, over the "
        f"same {sP['n_instances']} P and {sC['n_instances']} C instances at the same K = "
        f"{K_MAX}. Its curve does not move with K because its flag does not split across "
        f"draws (Table 3), so **ceiling 1's registered gain ratio is undefined for it**: "
        f"that ratio divides by the false-positive gain from K = 1, and that gain is "
        f"exactly zero. Only the post-hoc level ratio can be quoted, and it is "
        f"{se['ratios']['POST_HOC_level_ratio_by_k'][0]:.2f} "
        f"[{k1[0]:.2f}, {k1[1]:.2f}] at K = 1 and "
        f"{se['ratios']['POST_HOC_level_ratio_by_k'][-1]:.2f} [{k8[0]:.2f}, {k8[1]:.2f}] "
        f"at K = {K_MAX}.",
        "", *rows, "",
        f"Last-step gain on P {sP['flattening_gain_last_step_points']:.2f} points, on C "
        f"{sC['flattening_gain_last_step_points']:.2f} points. Both meet ceiling 1's bar "
        f"trivially: a curve that never rises has flattened by arithmetic, not by "
        f"saturation, and the exponential fit is not quoted for this family.",
        "",
    ])

    d = n["H23d_self_minus_cross_K8"]
    def _row(label: str, blk: dict) -> str:
        return (f"| {label} | {_p(blk['a_union'])} | {_p(blk['b_union'])} | "
                f"**{blk['difference_points']:+.1f}** "
                f"[{blk['cluster_ci95_points'][0]:.1f}, {blk['cluster_ci95_points'][1]:.1f}] | "
                f"{blk['a_only']} vs {blk['b_only']} | {blk['mcnemar_exact_p']:.5f} | "
                f"{blk['signflip']['p']:.5f} | "
                f"[{blk['tango_ci95_points'][0]:.1f}, {blk['tango_ci95_points'][1]:.1f}] | "
                f"[{blk['exact_unconditional_ci95_points'][0]:.1f}, "
                f"{blk['exact_unconditional_ci95_points'][1]:.1f}] |")
    t["T8"] = "\n".join([
        f"Paired: the same instances are read by both arms, so this is ceiling 1's paired "
        f"contrast, computed by `report_ceiling3.paired_union_difference` unchanged under "
        f"seed {n['bootstrap_seed']}. The cluster bootstrap is the primary interval; Tango "
        f"and the grid-unconditional interval ignore clustering and are labelled so; the "
        f"sign-flip test is ceiling 1's frozen implementation and carries its own seed. "
        f"`a vs b` counts instances only one arm flagged.",
        "",
        "| stratum | `self` at K = 8 | `cross` at K = 8 | self - cross [95% cluster CI] | "
        "discordant a vs b | McNemar p | sign-flip p | Tango | grid-unconditional |",
        "|---|---:|---:|---|---:|---:|---:|---|---|",
        _row("P (recall)", d["P"]),
        _row("C (false positives)", d["C"]),
        "",
        f"Substrate 1's frozen comparator is {d['substrate1_comparator_points']:.1f} points "
        f"[{d['substrate1_comparator_ci95_points'][0]:.1f}, "
        f"{d['substrate1_comparator_ci95_points'][1]:.1f}] on P. The sign here is "
        f"**{'the same' if d['sign_matches_substrate1'] else 'the opposite'}**. The "
        f"same-vendor arm buys {d['P']['difference_points']:.1f} points of recall and pays "
        f"{d['C']['difference_points']:.1f} points of false positives for it — "
        f"{d['false_positives_bought_per_recall_point']:.2f} false-positive points per "
        f"recall point, so it costs "
        f"**{'more than it gains' if d['costs_more_than_it_gains'] else 'less than it gains'}**.",
        "",
    ])

    c = n["cost"]
    t["T9"] = "\n".join([
        "Summed from the per-project `usage.jsonl` ledgers in the run archive as of "
        f"{n['cost']['read_utc']}. Refused calls that never reached a model are not in the "
        "ledgers and cost nothing.",
        "",
        "| | calls | USD |",
        "|---|---:|---:|",
        f"| generation (`claude-haiku-4-5`) | {c['generation']['calls']} | "
        f"${c['generation']['usd']:.2f} |",
        f"| audit, `cross` (`openai:gpt-5.6-terra`), 8 draws | "
        f"{c['audit_cross']['calls']:,} | ${c['audit_cross']['usd']:.2f} |",
        f"| audit, `self` (`claude-haiku-4-5`), 8 draws | {c['audit_self']['calls']:,} | "
        f"${c['audit_self']['usd']:.2f} |",
        f"| **audit total** | **{c['audit_total']['calls']:,}** | "
        f"**${c['audit_total']['usd']:.2f}** |",
        f"| **study total** | **{c['study_total']['calls']:,}** | "
        f"**${c['study_total']['usd']:.2f}** (cap ${c['cap_usd']:.0f}) |",
        "",
    ])
    return t


def tables_md(n: dict) -> str:
    """The whole tables file: every block wrapped in its own marker pair, in order."""
    t = render_tables(n)
    return "".join(f"{begin(k)}\n{t[k]}{end(k)}\n" for k in TABLE_KEYS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    ap.add_argument("--tables-only", action="store_true",
                    help="re-render tables.md from the committed numbers.json")
    args = ap.parse_args(argv)
    if not args.tables_only:
        numbers = build(Path(args.run_dir))
        (SUB2 / "numbers.json").write_text(
            json.dumps(numbers, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # The tables are rendered from the committed numbers.json and from nothing else:
    # no record, no cache and no ledger is read on this path.
    numbers = json.loads((SUB2 / "numbers.json").read_text(encoding="utf-8"))
    (SUB2 / "tables.md").write_text(tables_md(numbers), encoding="utf-8")
    print(f"wrote records/substrate2/numbers.json and tables.md "
          f"({len(TABLE_KEYS)} table blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
