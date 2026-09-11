"""Study 20 — apply ceiling 4's preregistered outcomes to the records, and nothing else.

Reads ceiling 1's `cross` draws 1-8 exactly as ``ceiling4.py`` loads them (through
``explore.load_detector`` with ``explore.EXPLORE`` walked over the same cache directories,
so study 1's and study 2's committed arms are inherited as free sources) plus this study's
``records/ceiling4/cache``. Every estimator is study 18's or ceiling 1's, imported, not
reimplemented: ``report_ceiling3.family_block``, ``paired_union_difference``,
``curve_cluster_cis``, ``exchange_ratio_ci``, ``zibb_pi`` and ``load_any_finding``, over
``report_ceiling``'s ``wilson``, ``cluster_bootstrap_ci``, ``signflip_p``,
``bootstrap_asymptote``, ``fit_saturation``, ``clustered_rate`` and ``mixed_curve``.

``report_ceiling3``'s module globals FAMILIES, CACHES and BOOT_SEED are rebound **in this
process** so those helpers see study 20's families, cache directories and preregistered
seed (20260913, §2). ``report_ceiling3.py`` and ``report_ceiling.py`` are not modified;
``report_ceiling``'s own BOOT_SEED is left at ceiling 1's frozen value, so the cluster
sign-flip test's sampler seed is ceiling 1's 20260915 (= 20260908 + 7), which is disclosed
rather than changed.

``report_ceiling3.render_tables`` is the one helper NOT reused: its cells are hard-wired to
study 18's five families and to the shape of study 18's ``numbers.json``, and study 20 has
different families, different hypotheses and per-table splice markers. What is reused is the
pattern the sibling reviews settled on — every cell rendered from ``numbers.json`` and from
no record file, spliced byte for byte, with the renderer, the splicer and the test as the
only things that may touch a table.

    PYTHONPATH=src python benchmarks/code/report_ceiling4.py --run <archive dir>
        -> records/ceiling4/numbers.json, records/ceiling4/tables.md

No model call, no network: every reading is read from the caches and every ledger figure
from the archive's committed usage.jsonl files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import explore  # noqa: E402
import report_ceiling as rc  # noqa: E402
import report_ceiling3 as r3  # noqa: E402

RECORDS = HERE / "records"
CEILING4 = RECORDS / "ceiling4"

#: §2's seed and reps. The preregistration fixes both.
BOOT_SEED = 20260913
BOOTSTRAP = 10_000
ZIBB_REPS = 1_000
MIXED_REPS = 2_000
EXCHANGE_REPS = 2_000

#: The two K = 8 families of §2. ``cross`` is ceiling 1's, reused unchanged.
FAMILIES = ("cross", "cross-R")
#: Amendment 1's extra reading: the shipped constitution, one draw, texts archived.
CROSS_T = "cross-T"
#: Every family with readings on this substrate, for the §1.5 residual (H20d). ``cross-T``
#: is excluded: Amendment 1 says it enters no H20 contrast, and it is the same constitution
#: as ``cross`` so it would not be an independent family in any case.
RESIDUAL_FAMILIES = ("cross", "self", "astra", "self-strong", "self-frontier", "cross-R")

#: ``ceiling4.py``'s cache search path, in its order, plus this study's.
CACHES = (RECORDS / "explore", RECORDS / "ceiling", RECORDS / "ceiling3",
          RECORDS / "ceiling3b", CEILING4)

#: The product's false-positive constraint (explore/PREREGISTRATION.md §5), quoted by
#: ceiling 4 §2 H20c as "the product bar (6.7%)".
FP_CONSTRAINT = 0.067

#: Amendment 1's adjudication: the blind sheet's key (in the repo, no text) and the two
#: raters' returned labels. One row per sheet id, ``id,naming,recognition``; ``recognition``
#: is empty wherever ``naming`` is not ``yes``, which is study 19's protocol.
ADJ_KEY = HERE / "ceiling4" / "key-amendment1.jsonl"
ADJ_MANIFEST = HERE / "ceiling4" / "adjudication-manifest.json"
RATINGS = {"L1": CEILING4 / "L1-amendment1.csv", "L2": CEILING4 / "L2-amendment1.csv"}
ARM_ROUTE = {"T": "cross-T", "R": "cross-R"}

#: Amendment 1's kill, from the memo it adopts: below 20 of 110 on the registered primary.
AMENDMENT1_KILL_THRESHOLD = 20

#: ceiling 1's frozen K = 8 cluster interval for ``cross`` on P, as the preregistration
#: writes it in the kill rule. Quoted from the preregistration, not recomputed: the kill
#: is evaluated against the number that was registered.
CROSS_K8_CLUSTER_CI_PREREGISTERED = [19.8, 40.7]

explore.ROUTES.update({"cross-R": explore.ROUTES["cross"], "cross-T": explore.ROUTES["cross"],
                       "self-strong": "anthropic:claude-sonnet-4-6",
                       "self-frontier": "anthropic:claude-opus-4-8"})

# study 18's helpers, pointed at study 20's families, caches and seed (this process only)
r3.FAMILIES = RESIDUAL_FAMILIES + (CROSS_T,)
r3.CACHES = CACHES
r3.BOOT_SEED = BOOT_SEED
r3.BOOTSTRAP = BOOTSTRAP
r3.ZIBB_REPS = ZIBB_REPS


def load_draws(scope: set[str], families: tuple[str, ...]) -> dict[str, dict]:
    """``family -> draw -> instance -> flagged``, loaded as ``ceiling4.py`` loads it.

    A draw enters only when every in-scope instance has a record; an incomplete draw is
    recorded under a string key and never analysed (ceiling 1's rule, study 18's code).
    """
    out: dict[str, dict] = {f: {} for f in families}
    for family in families:
        for draw in range(1, 9):
            key = ("holistic", family, draw)
            found: dict[str, dict] = {}
            for directory in CACHES:
                explore.EXPLORE = directory
                found.update(explore.load_detector(key, scope))
            complete = {i: bool(r["flagged"]) for i, r in found.items() if i in scope}
            if len(complete) == len(scope):
                out[family][draw] = complete
            elif complete:
                out[family][f"partial-{draw}"] = complete
    explore.EXPLORE = CEILING4
    return out


def cache_rows(route: str, draw: int) -> list[dict]:
    path = CEILING4 / "cache" / f"holistic__{route}__d{draw}.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def failed_rows(route: str, draw: int) -> list[dict]:
    path = CEILING4 / "cache" / f"holistic__{route}__d{draw}.failed.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def s2_prompt_digests() -> dict[str, str]:
    """instance -> study 2's committed holistic-cross prompt digest (the base prompt)."""
    out: dict[str, str] = {}
    for line in (RECORDS / "study2" / "arm-holistic-cross.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["instance_id"]] = row.get("prompt_sha256")
    return out


def reply_format_and_cost(run_dir: Path | None) -> dict:
    """§3's reply-format secondary and the ledger cost, per draw.

    ``invalid_reason`` is the harness's own record of a reply it could not parse after the
    product's bounded repair; ``ledger_calls - readings`` is the count of repair re-asks
    (``explore.run_detector`` restarts ``run_id`` per pass, so call multiplicity per id is
    not a re-ask count — study 18's correction, inherited). ``prompt_sha256`` against study
    2's committed digest is the positive control on which constitution each route ran.
    """
    base = s2_prompt_digests()
    out: dict = {}
    for route, draws in ((r, range(1, 9)) for r in FAMILIES if r != "cross"):
        for d in draws:
            out.update(_one_draw_format(route, d, base, run_dir))
    out.update(_one_draw_format(CROSS_T, 1, base, run_dir))
    return out


def _one_draw_format(route: str, draw: int, base: dict, run_dir: Path | None) -> dict:
    rows = cache_rows(route, draw)
    if not rows:
        return {}
    ledger_calls = ledger_usd = long_replies = None
    if run_dir is not None:
        ledger = run_dir / "projects" / f"project-holistic__{route}__d{draw}" / ".crossaudit" / "usage.jsonl"
        if ledger.exists():
            ev = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
            ledger_calls = len(ev)
            ledger_usd = round(sum(float(e.get("api_value_usd") or 0) for e in ev), 6)
            long_replies = sum(1 for e in ev if int(e.get("output", 0) or 0) > 300)
    return {f"{route}-d{draw}": {
        "route": route, "draw": draw, "rows": len(rows),
        "invalid_reason_nonempty": sum(1 for r in rows if r.get("invalid_reason")),
        "verdict_escalate": sum(1 for r in rows if r.get("verdict") == "ESCALATE"),
        "rows_not_ok": sum(1 for r in rows if not r.get("ok")),
        "prompt_digest_equals_study2_base": sum(1 for r in rows if r.get("prompt_sha256") == base.get(r["instance_id"])),
        "ledger_calls": ledger_calls, "ledger_usd": ledger_usd,
        "ledger_calls_minus_readings": (None if ledger_calls is None else ledger_calls - len(rows)),
        "replies_over_300_output_tokens": long_replies,
        "provider_denial_rows_before_completion": len(failed_rows(route, draw)),
        "provider_denial_instances_before_completion": len({r["instance_id"] for r in failed_rows(route, draw)}),
        "cache_cost_usd_unreliable": round(sum(float(r.get("cost_usd") or 0) for r in rows), 6),
        "model_findings_any": sum(1 for r in rows if int(r.get("model_findings", 0) or 0) > 0),
        "model_blockers_any": sum(1 for r in rows if int(r.get("model_blockers", 0) or 0) > 0)}}


def asymptote_difference(draws: dict, ids: list[str], instances: dict, k_max: int) -> dict:
    """H20b: A(`cross-R`) − A(`cross`), the fit **refitted inside every resample**.

    One resampling stream over problem clusters; each resample draws the same problems for
    both families (they are measured on the same instances, so the difference is paired at
    the cluster), refits ceiling 1 §1.2's constrained saturation curve for each, and keeps
    the difference of the two asymptotes.
    """
    by_problem: dict[str, dict[str, list[int]]] = {}
    for fam in FAMILIES:
        sub = {d: draws[fam][d] for d in range(1, k_max + 1)}
        ks = rc.counts_per_instance(sub, ids)
        for i, k in zip(ids, ks):
            by_problem.setdefault(instances[i]["problem_id"], {}).setdefault(fam, []).append(k)
    problems = sorted(by_problem)

    def fit_pair(chosen: list[str]) -> tuple[float | None, float | None]:
        out = []
        for fam in FAMILIES:
            drawn = [k for p in chosen for k in by_problem[p][fam]]
            out.append(rc.fit_saturation(rc.union_curve(drawn, k_max))["A"])
        return out[1], out[0]          # cross-R, cross

    a_r, a_c = fit_pair(problems)
    rng = random.Random(BOOT_SEED)
    diffs: list[float] = []
    for _ in range(BOOTSTRAP):
        chosen = [problems[rng.randrange(len(problems))] for _ in range(len(problems))]
        r_, c_ = fit_pair(chosen)
        if r_ is not None and c_ is not None:
            diffs.append(r_ - c_)
    return {"k_max": k_max, "n": len(ids), "n_problems": len(problems),
            "A_cross_R": a_r, "A_cross": a_c,
            "difference_points": 100 * (a_r - a_c),
            "cluster_ci95_points": [100 * rc.percentile(diffs, 0.025), 100 * rc.percentile(diffs, 0.975)],
            "resamples_fitted": len(diffs), "reps": BOOTSTRAP, "seed": BOOT_SEED,
            "note": "the constrained fit of ceiling 1 §1.2, refitted inside each resample; "
                    "A is bounded to [0, 1] inside the objective, so an interval that reaches "
                    "100.0 has reached the constraint, not a measurement"}


def single_draw_rates(draws: dict, family: str, ids: list[str], instances: dict,
                      k_max: int) -> dict:
    """Each individual draw's rate on ``ids``, and the mean over draws with its interval.

    The mean over the K draws is the union curve's K = 1 point (``report_ceiling``'s
    ``clustered_mean`` of k_i/K per instance), which is what ceiling 1 calls a single-draw
    rate; the per-draw rates are listed beside it because the product bar of §2 H20c is a
    bar on one reading.
    """
    per_draw = []
    for d in range(1, k_max + 1):
        flags = draws[family][d]
        per_draw.append(rc.clustered_rate(flags, ids, instances, BOOTSTRAP, BOOT_SEED))
    sub = {d: draws[family][d] for d in range(1, k_max + 1)}
    ks = rc.counts_per_instance(sub, ids)
    mean = rc.clustered_mean({i: k / k_max for i, k in zip(ids, ks)}, ids, instances, BOOTSTRAP, BOOT_SEED)
    return {"per_draw": per_draw, "mean_over_draws": mean,
            "draws_at_or_below_bar": sum(1 for p in per_draw if p["rate"] <= FP_CONSTRAINT),
            "k_max": k_max}


def mixed_block(draws: dict, ids: list[str], instances: dict) -> dict:
    """§3's `mixed`: K/2 `cross` + K/2 `cross-R`, against each family alone at the same total."""
    by_prob_ids: dict[str, list[str]] = {}
    for i in ids:
        by_prob_ids.setdefault(instances[i]["problem_id"], []).append(i)
    probs = sorted(by_prob_ids)
    out: dict = {"cluster_reps": MIXED_REPS, "totals": {}}
    for total in (2, 4, 6, 8):
        per = total // 2
        m = rc.mixed_curve(draws, list(FAMILIES), ids, per)
        if m is None:
            continue
        rng = random.Random(BOOT_SEED)
        stats = []
        for _ in range(MIXED_REPS):
            resampled = [i for _ in range(len(probs)) for i in by_prob_ids[probs[rng.randrange(len(probs))]]]
            stats.append(rc.mixed_curve(draws, list(FAMILIES), resampled, per))
        out["totals"][f"K={total}"] = {
            "mixed_union": m,
            "cluster_ci95": [rc.percentile(stats, 0.025), rc.percentile(stats, 0.975)],
            "per_family_draws": per, "total_draws": total}
    return out


def residual_block(draws: dict, P: list[str], instances: dict) -> dict:
    """H20d: P instances no draw of any measured family ever blocked, with ceiling 1's labels."""
    families = [f for f in RESIDUAL_FAMILIES if any(isinstance(d, int) for d in draws[f])]
    per_family_k = {f: len([d for d in draws[f] if isinstance(d, int)]) for f in families}
    never = [i for i in P if not any(draws[f][d].get(i)
                                     for f in families for d in draws[f] if isinstance(d, int))]
    never_set = set(never)
    without_R = [f for f in families if f != "cross-R"]
    never_without_R = [i for i in P if not any(draws[f][d].get(i)
                                               for f in without_R for d in draws[f] if isinstance(d, int))]
    rcls = json.loads((RECORDS / "ceiling" / "residual_classification.json").read_text(encoding="utf-8"))["classification"]

    def labels_of(ids: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for i in ids:
            cat = rcls[i]["category"] if i in rcls else "UNCLASSIFIED (new to the residual)"
            counts[cat] = counts.get(cat, 0) + 1
        return dict(sorted(counts.items()))

    left = sorted(i for i in never_without_R if i not in never_set)
    c1 = json.loads((RECORDS / "ceiling" / "numbers.json").read_text(encoding="utf-8"))
    c1_ids = c1["ceiling1"]["residual"]["all_families"]["instance_ids"]
    return {
        "families": families, "draws_per_family": per_family_k,
        "total_draws": sum(per_family_k.values()),
        "residual": rc.clustered_rate({i: (i in never_set) for i in P}, P, instances, BOOTSTRAP, BOOT_SEED),
        "n": len(never), "by_category": labels_of(never),
        "study18_residual_n": len(never_without_R),
        "study18_by_category": labels_of(never_without_R),
        "left_the_residual_when_cross_R_was_added": left,
        "left_the_residual_by_category": labels_of(left),
        "new_to_the_residual": sorted(i for i in never if i not in set(never_without_R)),
        "ceiling1_residual_n": len(c1_ids),
        "instance_ids": never,
        "note": "cross-T is excluded by Amendment 1 (it enters no H20 contrast and runs the "
                "same constitution as cross); labels are ceiling 1 §1.5's classification of "
                "the same instances, not re-derived here"}


def cohen_kappa(a: int, b: int, c: int, d: int) -> float | None:
    """Cohen's kappa for a 2x2 agreement table, or None where it is undefined.

    ``a`` both yes, ``b`` first yes only, ``c`` second yes only, ``d`` both no. Kappa is
    undefined when the expected agreement is 1 — which happens when both raters give the
    same label to every item, so there is no marginal variation to correct for. Returning
    None there, and saying so, is the honest form: a perfect-concordance table is not
    kappa = 1, it is a table kappa cannot speak about.
    """
    n = a + b + c + d
    if not n:
        return None
    p_o = (a + d) / n
    p1, p2 = (a + b) / n, (a + c) / n
    p_e = p1 * p2 + (1 - p1) * (1 - p2)
    if math.isclose(p_e, 1.0):
        return None
    return (p_o - p_e) / (1 - p_e)


def load_ratings() -> dict[str, dict[str, tuple[str, str]]]:
    """rater -> sheet id -> (naming, recognition), from the committed csvs."""
    out: dict[str, dict[str, tuple[str, str]]] = {}
    for name, path in RATINGS.items():
        if not path.exists():
            return {}
        rows: dict[str, tuple[str, str]] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows[row["id"].strip()] = (row["naming"].strip(), row["recognition"].strip())
        out[name] = rows
    return out


def adjudication_block(P: list[str], instances: dict) -> dict:
    """Amendment 1, answered: the naming question, the recognition question, and the rates.

    Two questions, and they are not the same quantity, which is the thing most easily got
    wrong when both are in one table:

    * **naming** — study 19's REGISTERED question: does the finding name the input class,
      or the behaviour, on which the hidden test fails?
    * **defect-asserting** — naming yes AND the recognition label ``defect``, i.e. the
      finding says the code is WRONG on that class rather than that it is handled correctly
      or merely untested. This is post-hoc in study 19; ceiling 4 Amendment 1 REGISTERS it,
      and it is Amendment 1's primary rate, so it is the one the kill is evaluated on.

    Four reader rules for each, because kappa on the naming question is low and a verdict
    that survives the disagreement is worth more than one that does not: consensus (the
    preregistered rule — a disputed item counts as not named), L1 alone, L2 alone, either.
    Every rate is over the 110 P instances, with Wilson and the problem-cluster bootstrap.
    """
    ratings = load_ratings()
    if not ratings:
        return {"note": "no rater csv; the adjudication has not been answered"}
    key = {}
    for line in ADJ_KEY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            key[row["id"]] = row
    L1, L2 = ratings["L1"], ratings["L2"]
    ids = sorted(key)
    if not (set(ids) == set(L1) == set(L2)):
        return {"note": "AUTHOR_INPUT_NEEDED: the label files and the key do not cover the same ids"}

    yes = lambda r, i: r[i][0] == "yes"                                   # noqa: E731
    a = sum(1 for i in ids if yes(L1, i) and yes(L2, i))
    b = sum(1 for i in ids if yes(L1, i) and not yes(L2, i))
    c = sum(1 for i in ids if not yes(L1, i) and yes(L2, i))
    d = sum(1 for i in ids if not yes(L1, i) and not yes(L2, i))
    naming = {"items": len(ids), "both_yes": a, "L1_only": b, "L2_only": c, "both_no": d,
              "agree": a + d, "agreement": (a + d) / len(ids),
              "kappa": cohen_kappa(a, b, c, d),
              "L1_yes": a + b, "L2_yes": a + c, "disagreements": b + c,
              "disagreements_L1_no_L2_yes": c, "disagreements_L1_yes_L2_no": b,
              "more_inclusive_rater": "L2" if (a + c) > (a + b) else ("L1" if (a + b) > (a + c) else "neither"),
              "labels_used": {"L1": sorted({L1[i][0] for i in ids}), "L2": sorted({L2[i][0] for i in ids})}}

    consensus_yes = [i for i in ids if yes(L1, i) and yes(L2, i)]
    dd = sum(1 for i in consensus_yes if L1[i][1] == "defect" and L2[i][1] == "defect")
    dn = sum(1 for i in consensus_yes if L1[i][1] == "defect" and L2[i][1] != "defect")
    nd = sum(1 for i in consensus_yes if L1[i][1] != "defect" and L2[i][1] == "defect")
    nn = len(consensus_yes) - dd - dn - nd
    recognition = {
        "scope": "the consensus naming-yes items, as study 19 asks it",
        "items": len(consensus_yes), "both_defect": dd, "L1_only": dn, "L2_only": nd,
        "neither": nn, "agree": dd + nn,
        "agreement": ((dd + nn) / len(consensus_yes)) if consensus_yes else None,
        "kappa": cohen_kappa(dd, dn, nd, nn),
        "kappa_note": "kappa is undefined where both raters gave every item the same label: "
                      "expected agreement is 1 and there is no marginal variation to correct "
                      "for. That is perfect concordance, not kappa = 1.",
        "label_counts": {"L1": _counts(L1[i][1] for i in ids if yes(L1, i)),
                         "L2": _counts(L2[i][1] for i in ids if yes(L2, i))}}

    rules = {
        "consensus": lambda i, q: _q(L1, i, q) and _q(L2, i, q),
        "L1": lambda i, q: _q(L1, i, q),
        "L2": lambda i, q: _q(L2, i, q),
        "either": lambda i, q: _q(L1, i, q) or _q(L2, i, q)}
    arms: dict[str, dict] = {}
    for arm, route in ARM_ROUTE.items():
        arm_ids = [i for i in ids if key[i]["arm"] == arm]
        entry: dict = {"route": route, "items": len(arm_ids),
                       "P_instances_with_a_finding": len({key[i]["instance"] for i in arm_ids}),
                       "naming": {}, "defect_asserting": {}}
        for question in ("naming", "defect_asserting"):
            for rule, test in rules.items():
                hit = {key[i]["instance"] for i in arm_ids if test(i, question)}
                entry[question][rule] = rc.clustered_rate({i: (i in hit) for i in P}, P,
                                                          instances, BOOTSTRAP, BOOT_SEED)
                entry[question][rule]["items"] = sum(1 for i in arm_ids if test(i, question))
        arms[arm] = entry

    primary = arms["T"]["defect_asserting"]["consensus"]
    kill = {"rule": f"Amendment 1 adopts the memo's kill: below {AMENDMENT1_KILL_THRESHOLD} "
                    f"of 110 on cross-T's registered primary, the headline becomes "
                    f"'flag rate 30.0%, defect-naming recall X%'",
            "threshold_k": AMENDMENT1_KILL_THRESHOLD,
            "primary_k": primary["k"], "primary_n": primary["n"],
            "fired": primary["k"] < AMENDMENT1_KILL_THRESHOLD,
            "fired_under_every_rule": all(arms["T"]["defect_asserting"][r]["k"] < AMENDMENT1_KILL_THRESHOLD
                                          for r in rules),
            "fired_under_every_rule_and_question": all(
                arms["T"][q][r]["k"] < AMENDMENT1_KILL_THRESHOLD for q in ("naming", "defect_asserting")
                for r in rules)}
    manifest = json.loads(ADJ_MANIFEST.read_text(encoding="utf-8")) if ADJ_MANIFEST.exists() else {}
    return {"run": True, "naming": naming, "recognition": recognition, "arms": arms,
            "amendment1_kill": kill, "manifest": manifest,
            "primary_rule": "consensus, defect-asserting: a disputed item counts as NOT named, "
                            "which is the preregistered direction",
            "note": "naming and defect-asserting are different quantities and are reported "
                    "separately; the registered primary of Amendment 1 is the defect-asserting one"}


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v or "(empty)"] = out.get(v or "(empty)", 0) + 1
    return dict(sorted(out.items()))


def _q(rater: dict, i: str, question: str) -> bool:
    named = rater[i][0] == "yes"
    return named if question == "naming" else (named and rater[i][1] == "defect")


def cross_t_block(draws: dict, any_draws: dict, P: list[str], C: list[str],
                  instances: dict) -> dict:
    """Amendment 1: the shipped constitution, one reading, texts archived.

    What the record can carry without the adjudication is the **flag rate** — at least one
    BLOCKER, ceiling 1's rule — and the any-finding rate beside it. Amendment 1's primary
    rate ("P instances with a defect-asserting finding / 110") and the kill it names
    (below 20 of 110) are properties of the adjudication, which is not run here.
    """
    if 1 not in draws.get(CROSS_T, {}):
        return {"note": "no cross-T draw"}
    flags = draws[CROSS_T][1]
    out = {"k_max": 1,
           "P_flag_rate": rc.clustered_rate(flags, P, instances, BOOTSTRAP, BOOT_SEED),
           "C_flag_rate": rc.clustered_rate(flags, C, instances, BOOTSTRAP, BOOT_SEED),
           "amendment1_primary_rate": None,
           "amendment1_kill_evaluated": False,
           "note": "amendment1_primary_rate is the defect-NAMING rate and requires the "
                   "adjudication of the archived texts, which this analysis does not run; "
                   "the kill it names (below 20 of 110) is therefore not evaluated here"}
    if CROSS_T in any_draws and 1 in any_draws[CROSS_T]:
        af = any_draws[CROSS_T][1]
        out["P_any_finding_rate"] = rc.clustered_rate(af, P, instances, BOOTSTRAP, BOOT_SEED)
        out["C_any_finding_rate"] = rc.clustered_rate(af, C, instances, BOOTSTRAP, BOOT_SEED)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="study 20 / ceiling 4 analysis")
    ap.add_argument("--run", default="", help="the read-only run archive, for the ledgers")
    args = ap.parse_args(argv)
    run_dir = Path(args.run).expanduser() if args.run else None

    instances = rc.load_instances()
    audit_set = rc.load_audit_set()
    scope = [i for i in audit_set if instances[i]["stratum"] in ("P", "C")]
    P = [i for i in scope if instances[i]["stratum"] == "P"]
    C = [i for i in scope if instances[i]["stratum"] == "C"]
    draws = load_draws(set(scope), RESIDUAL_FAMILIES + (CROSS_T,))
    k_max = min(len([d for d in draws[f] if isinstance(d, int)]) for f in FAMILIES)

    out: dict = {
        "study": "study20 / ceiling 4",
        "preregistration": "benchmarks/code/ceiling4/PREREGISTRATION.md",
        "bootstrap": {"seed": BOOT_SEED, "reps": BOOTSTRAP, "unit": "problem",
                      "signflip_seed": "report_ceiling.BOOT_SEED + 7 (ceiling 1's frozen "
                                       "20260908 + 7 = 20260915), left unchanged",
                      "mixed_reps": MIXED_REPS, "exchange_reps": EXCHANGE_REPS,
                      "zibb_reps": ZIBB_REPS},
        "n_P": len(P), "n_C": len(C), "k_max": k_max,
        "routes": {"cross": "openai:gpt-5.6-terra, shipped constitution (ceiling 1, reused)",
                   "cross-R": "openai:gpt-5.6-terra, shipped constitution + loop.REFERENT_RULE",
                   "cross-T": "openai:gpt-5.6-terra, shipped constitution unchanged, texts archived"},
        "families": {}}

    for fam in FAMILIES:
        block = {"P": r3.family_block(draws[fam], P, instances, k_max, "P"),
                 "C": r3.family_block(draws[fam], C, instances, k_max, "C"),
                 "k_max": k_max}
        rec, fp = block["P"]["curve"], block["C"]["curve"]
        block["exchange_rate_recall_per_fp_EXPLORATORY"] = (
            ((rec[-1] - rec[0]) / (fp[-1] - fp[0])) if len(rec) > 1 and fp[-1] != fp[0] else None)
        block["exchange_rate_cluster_ci95_EXPLORATORY"] = r3.exchange_ratio_ci(
            block["P"].pop("ks_by_problem"), block["C"].pop("ks_by_problem"),
            k_max, EXCHANGE_REPS, BOOT_SEED)
        block["exchange_rate_label"] = ("EXPLORATORY: ceiling 1's exchange rate, carried over; "
                                        "not among study 20's preregistered outcomes")
        out["families"][fam] = block

    # ---- H20a, the primary -------------------------------------------------------
    h20a = r3.paired_union_difference(draws["cross-R"], draws["cross"], k_max, P, instances)
    out["primary_H20a_crossR_minus_cross_P"] = h20a
    r_union = out["families"]["cross-R"]["P"]["union_at_kmax"]
    inside = (CROSS_K8_CLUSTER_CI_PREREGISTERED[0] <= 100 * r_union["rate"]
              <= CROSS_K8_CLUSTER_CI_PREREGISTERED[1])
    includes_zero = h20a["cluster_ci95_points"][0] <= 0 <= h20a["cluster_ci95_points"][1]
    out["H20a_kill"] = {
        "rule": "H20a's interval includes zero, OR cross-R's eight-reading union falls "
                "inside cross's K=8 cluster interval [19.8, 40.7]",
        "cluster_ci95_includes_zero": includes_zero,
        "crossR_union_at_kmax_points": 100 * r_union["rate"],
        "cross_k8_cluster_ci95_points_preregistered": CROSS_K8_CLUSTER_CI_PREREGISTERED,
        "crossR_union_inside_cross_interval": inside,
        "cross_k8_cluster_ci95_points_recomputed_at_seed_20260913":
            [100 * x for x in out["families"]["cross"]["P"]["union_at_kmax"]["cluster_ci95"]],
        "fired": bool(includes_zero or inside),
        "note": "the kill is evaluated against the interval the preregistration names; the "
                "same interval recomputed at this study's seed is given beside it and moves "
                "the bound by less than a point"}

    # ---- H20b, the ceiling -------------------------------------------------------
    out["H20b_asymptote_difference_P"] = asymptote_difference(draws, P, instances, k_max)
    out["H20b_flattening"] = {
        fam: {"gain_last_step_points": 100 * out["families"][fam]["P"]["flattening_gain_last_step"],
              "gain_cluster_ci95_points": [100 * x for x in out["families"][fam]["P"]["flattening_gain_last_step_cluster_ci95"]],
              "bar_points": 1.0,
              "flattened": out["families"][fam]["P"]["flattened_by_ceiling1_bar"],
              "asymptote_is_extrapolation": out["families"][fam]["P"]["asymptote_is_extrapolation"],
              "raw_union_at_kmax": out["families"][fam]["P"]["union_at_kmax"]}
        for fam in FAMILIES}

    # ---- H20c, the cost ----------------------------------------------------------
    out["H20c_C_false_positives"] = r3.paired_union_difference(draws["cross-R"], draws["cross"], k_max, C, instances)
    out["H20c_single_draw_fp"] = {
        "bar": FP_CONSTRAINT,
        "bar_source": "explore/PREREGISTRATION.md §5, the product's false-positive constraint",
        "cross-R": single_draw_rates(draws, "cross-R", C, instances, k_max),
        "cross": single_draw_rates(draws, "cross", C, instances, k_max)}
    mean_r = out["H20c_single_draw_fp"]["cross-R"]["mean_over_draws"]
    out["H20c_single_draw_fp"]["crossR_mean_within_bar"] = bool(mean_r["rate"] <= FP_CONSTRAINT)
    out["H20c_single_draw_fp"]["crossR_mean_ci_within_bar"] = bool(mean_r["cluster_ci95"][1] <= FP_CONSTRAINT)

    # ---- H20d, the residual ------------------------------------------------------
    out["H20d_residual"] = residual_block(draws, P, instances)

    # ---- secondaries -------------------------------------------------------------
    out["secondary_mixed_cross_crossR_P"] = mixed_block(draws, P, instances)
    out["secondary_mixed_cross_crossR_C"] = mixed_block(draws, C, instances)
    any_draws = r3.load_any_finding(set(scope))
    out["secondary_any_finding_rule"] = {
        "label": "PREREGISTERED secondary (ceiling 4 §3): a FLAG rate — an instance on "
                 "which the model returned some finding at any severity — not a "
                 "defect-naming rate; no text was adjudicated",
        "families": {}}
    for fam in FAMILIES + (CROSS_T,):
        complete = sorted(k for k in any_draws.get(fam, {}) if isinstance(k, int))
        if not complete:
            continue
        sub = {d: any_draws[fam][d] for d in complete}
        entry: dict = {"k_max": len(complete)}
        for label, ids in (("P", P), ("C", C)):
            ks = rc.counts_per_instance(sub, ids)
            curve = rc.union_curve(ks, len(complete))
            by_problem: dict[str, list[int]] = {}
            for i, k in zip(ids, ks):
                by_problem.setdefault(instances[i]["problem_id"], []).append(k)
            entry[label] = {
                "curve": curve, "single_draw_mean": curve[0],
                "curve_cluster_ci95": r3.curve_cluster_cis(by_problem, len(complete), BOOTSTRAP, BOOT_SEED),
                "union_at_kmax": rc.clustered_rate({i: any(sub[d].get(i) for d in complete) for i in ids},
                                                   ids, instances, BOOTSTRAP, BOOT_SEED)}
        out["secondary_any_finding_rule"]["families"][fam] = entry

    out["secondary_reply_format_and_cost"] = reply_format_and_cost(run_dir)
    ledger = [v for v in out["secondary_reply_format_and_cost"].values() if v["ledger_usd"] is not None]
    out["cost"] = {
        "ledger_usd_total": round(sum(v["ledger_usd"] for v in ledger), 4) if ledger else None,
        "ledger_calls_total": sum(v["ledger_calls"] for v in ledger) if ledger else None,
        "readings_total": sum(v["rows"] for v in out["secondary_reply_format_and_cost"].values()),
        "budget_cap_usd": 30.0,
        "note": "the per-row cost_usd stamped into the cache is unreliable where a draw "
                "needed several passes (study 18's finding, inherited); the ledgers are the "
                "cost of record"}

    # ---- Amendment 1 --------------------------------------------------------------
    out["amendment1_cross_T"] = cross_t_block(draws, any_draws, P, C, instances)
    out["amendment1_adjudication"] = adjudication_block(P, instances)
    adj = out["amendment1_adjudication"]
    if adj.get("run"):
        prim = adj["arms"]["T"]["defect_asserting"]["consensus"]
        out["amendment1_cross_T"]["amendment1_primary_rate"] = prim
        out["amendment1_cross_T"]["amendment1_kill_evaluated"] = True
        out["amendment1_cross_T"]["amendment1_kill"] = adj["amendment1_kill"]
        out["amendment1_cross_T"]["note"] = (
            "amendment1_primary_rate is the registered defect-NAMING rate: P instances with a "
            "finding that names the failing class AND asserts the code is wrong on it, under "
            "the consensus rule. It rests on ONE reading of cross-T and says nothing about the "
            "naming content of cross's eight-reading union.")

    CEILING4.mkdir(parents=True, exist_ok=True)
    (CEILING4 / "numbers.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (CEILING4 / "tables.md").write_text(render_tables(out), encoding="utf-8")

    pr = out["primary_H20a_crossR_minus_cross_P"]
    print(f"H20a (K={pr['k']}): cross-R − cross on P = {pr['difference_points']:+.1f} points "
          f"cluster [{pr['cluster_ci95_points'][0]:+.1f}, {pr['cluster_ci95_points'][1]:+.1f}] "
          f"Tango [{pr['tango_ci95_points'][0]:+.1f}, {pr['tango_ci95_points'][1]:+.1f}] "
          f"grid [{pr['exact_unconditional_ci95_points'][0]:+.1f}, {pr['exact_unconditional_ci95_points'][1]:+.1f}] "
          f"({pr['a_only']} vs {pr['b_only']}; McNemar p={pr['mcnemar_exact_p']:.2e}; "
          f"sign-flip p={pr['signflip']['p']:.2e})")
    print(f"KILL: {'FIRED' if out['H20a_kill']['fired'] else 'did not fire'} "
          f"(zero in interval {out['H20a_kill']['cluster_ci95_includes_zero']}; "
          f"union {out['H20a_kill']['crossR_union_at_kmax_points']:.1f} inside "
          f"{CROSS_K8_CLUSTER_CI_PREREGISTERED} {out['H20a_kill']['crossR_union_inside_cross_interval']})")
    hb = out["H20b_asymptote_difference_P"]
    print(f"H20b: A(cross-R) {100*hb['A_cross_R']:.1f}%  A(cross) {100*hb['A_cross']:.1f}%  "
          f"difference {hb['difference_points']:+.1f} [{hb['cluster_ci95_points'][0]:+.1f}, {hb['cluster_ci95_points'][1]:+.1f}]")
    for fam in FAMILIES:
        f = out["H20b_flattening"][fam]
        print(f"   {fam:8s} gain {f['gain_last_step_points']:.2f} "
              f"[{f['gain_cluster_ci95_points'][0]:.2f}, {f['gain_cluster_ci95_points'][1]:.2f}] "
              f"flattened={f['flattened']} extrapolation={f['asymptote_is_extrapolation']}")
    hc = out["H20c_C_false_positives"]
    print(f"H20c: union FP on C {hc['difference_points']:+.1f} "
          f"[{hc['cluster_ci95_points'][0]:+.1f}, {hc['cluster_ci95_points'][1]:+.1f}] "
          f"({hc['a_only']} vs {hc['b_only']}); single-draw mean "
          f"{100*mean_r['rate']:.1f}% [{100*mean_r['cluster_ci95'][0]:.1f}, {100*mean_r['cluster_ci95'][1]:.1f}] "
          f"vs bar {100*FP_CONSTRAINT:.1f}%")
    hd = out["H20d_residual"]
    print(f"H20d: residual {hd['n']}/{hd['residual']['n']} "
          f"(was {hd['study18_residual_n']}); left {len(hd['left_the_residual_when_cross_R_was_added'])} "
          f"{hd['left_the_residual_by_category']}")
    ct = out["amendment1_cross_T"]
    if "P_flag_rate" in ct:
        p = ct["P_flag_rate"]
        print(f"cross-T: P flag {p['k']}/{p['n']} = {100*p['rate']:.1f}% "
              f"Wilson [{100*p['wilson95'][0]:.1f}, {100*p['wilson95'][1]:.1f}] "
              f"cluster [{100*p['cluster_ci95'][0]:.1f}, {100*p['cluster_ci95'][1]:.1f}]")
    if adj.get("run"):
        nm, rg, k = adj["naming"], adj["recognition"], adj["amendment1_kill"]
        print(f"adjudication naming: agree {nm['agree']}/{nm['items']} = {100*nm['agreement']:.1f}%  "
              f"kappa {nm['kappa']:.3f}  (L1 yes {nm['L1_yes']}, L2 yes {nm['L2_yes']}; "
              f"{nm['disagreements']} disagreements, {nm['disagreements_L1_no_L2_yes']} L1-no/L2-yes)")
        print(f"  recognition on the {rg['items']} consensus-yes items: agree {rg['agree']}/{rg['items']}"
              f"  kappa {'undefined' if rg['kappa'] is None else format(rg['kappa'], '.3f')}")
        for arm in ("T", "R"):
            e = adj["arms"][arm]
            for q in ("naming", "defect_asserting"):
                print(f"  {e['route']:8s} {q:16s} " + "  ".join(
                    f"{r} {e[q][r]['k']}" for r in ("consensus", "L1", "L2", "either")))
        print(f"  Amendment 1 kill (< {k['threshold_k']} of 110 on cross-T's registered primary, "
              f"{k['primary_k']}): {'FIRED' if k['fired'] else 'did not fire'}; "
              f"fires under every rule and question: {k['fired_under_every_rule_and_question']}")
    print(f"cost: ${out['cost']['ledger_usd_total']} over {out['cost']['ledger_calls_total']} calls")
    return 0


# ---------------------------------------------------------------------------------
# the tables, rendered from numbers.json and from nothing else
# ---------------------------------------------------------------------------------


LABELS = {"cross": "`cross` (shipped constitution, ceiling 1)",
          "cross-R": "**`cross-R` (shipped + referent rule)**",
          "cross-T": "`cross-T` (shipped, texts archived — Amendment 1)"}

#: Every generated block, in the order it is rendered. The results file must carry exactly
#: these marker pairs and no table-like content outside them (study 17's lesson, round 5).
BLOCK_NAMES = ("PREAMBLE", "TABLE1", "TABLE2", "KILL", "TABLE3", "TABLE4", "ASYMPTOTE-DIFF",
               "TABLE5", "TABLE6", "TABLE7", "TABLE8", "TABLE9", "TABLE10", "KILL-A",
               "TABLE11", "COST")

BEGIN = "<!-- BEGIN {name} (records/ceiling4/tables.md) -->"
END = "<!-- END {name} -->"


def _pc(x, places: int = 1) -> str:
    return f"{100 * x:.{places}f}"


def _iv(pair, places: int = 1) -> str:
    return f"{_pc(pair[0], places)}–{_pc(pair[1], places)}"


def _pts(pair, places: int = 1) -> str:
    return f"{pair[0]:.{places}f}, {pair[1]:.{places}f}"


def _preamble(out: dict) -> list[str]:
    return [f"Intervals: a k/n rate carries the 95% Wilson interval and the problem-cluster percentile "
            f"bootstrap ({out['bootstrap']['reps']:,} resamples, seed {out['bootstrap']['seed']}); a "
            f"subset-averaged curve point, a single-draw mean, a mixed rate and a difference of fitted "
            f"asymptotes are means, not k/n, and carry the cluster interval only "
            f"({out['bootstrap']['mixed_reps']:,} resamples for mixed). The cluster interval is the "
            f"primary one throughout. Beside each paired contrast the tables quote Tango's score "
            f"interval and a grid-unconditional interval (an exact test maximised over a 41-point "
            f"nuisance grid with no bound on the missed supremum — ceiling 1 Amendment 5's own "
            f"qualification); both ignore clustering. The cluster sign-flip sampler keeps ceiling 1's "
            f"frozen seed: {out['bootstrap']['signflip_seed']}."]


def _table1(out: dict) -> list[str]:
    lines = ["### Table 1 — union of K readings, BLOCKER rule (Wilson; problem-cluster bootstrap)", "",
             "| family | K | P union recall | Wilson | cluster | C union FP | Wilson | cluster |",
             "|---|---|---|---|---|---|---|---|"]
    for f in ("cross", "cross-R"):
        e = out["families"][f]
        p, c = e["P"]["union_at_kmax"], e["C"]["union_at_kmax"]
        lines.append(f"| {LABELS[f]} | {e['k_max']} | {p['k']}/{p['n']} = {_pc(p['rate'])}% | {_iv(p['wilson95'])} "
                     f"| {_iv(p['cluster_ci95'])} | {c['k']}/{c['n']} = {_pc(c['rate'])}% | {_iv(c['wilson95'])} "
                     f"| {_iv(c['cluster_ci95'])} |")
    ct = out["amendment1_cross_T"]
    if "P_flag_rate" in ct:
        p, c = ct["P_flag_rate"], ct["C_flag_rate"]
        lines.append(f"| {LABELS['cross-T']} | 1 | {p['k']}/{p['n']} = {_pc(p['rate'])}% | {_iv(p['wilson95'])} "
                     f"| {_iv(p['cluster_ci95'])} | {c['k']}/{c['n']} = {_pc(c['rate'])}% | {_iv(c['wilson95'])} "
                     f"| {_iv(c['cluster_ci95'])} |")
    return lines


def _table2(out: dict) -> list[str]:
    lines = ["### Table 2 — the preregistered contrasts (§2): union at K on the same instances, paired per instance", "",
             "| hypothesis | stratum | K | A − B (points) | cluster 95% | Tango 95% | grid-unconditional 95% "
             "| A only | B only | McNemar exact p | cluster sign-flip p |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, label, stratum in (("primary_H20a_crossR_minus_cross_P", "**H20a (primary)** `cross-R` − `cross`", "P"),
                                ("H20c_C_false_positives", "H20c `cross-R` − `cross`", "C")):
        h = out[key]
        lines.append(f"| {label} | {stratum} | {h['k']} | {h['difference_points']:+.1f} "
                     f"| {_pts(h['cluster_ci95_points'])} | {_pts(h['tango_ci95_points'])} "
                     f"| {_pts(h['exact_unconditional_ci95_points'])} | {h['a_only']} | {h['b_only']} "
                     f"| {h['mcnemar_exact_p']:.2e} | {h['signflip']['p']:.2e} ({h['signflip']['method']}) |")
    return lines


def _kill(out: dict) -> list[str]:
    k = out["H20a_kill"]
    return [f"**The preregistered kill** (§2): *{k['rule']}*. H20a's cluster interval includes zero: "
            f"**{'yes' if k['cluster_ci95_includes_zero'] else 'no'}**. `cross-R`'s eight-reading union "
            f"{k['crossR_union_at_kmax_points']:.1f}% lies inside "
            f"[{k['cross_k8_cluster_ci95_points_preregistered'][0]:.1f}, "
            f"{k['cross_k8_cluster_ci95_points_preregistered'][1]:.1f}]: "
            f"**{'yes' if k['crossR_union_inside_cross_interval'] else 'no'}**. "
            f"The kill **{'FIRED' if k['fired'] else 'did not fire'}**. "
            f"(The same `cross` interval recomputed at this study's seed is "
            f"[{k['cross_k8_cluster_ci95_points_recomputed_at_seed_20260913'][0]:.1f}, "
            f"{k['cross_k8_cluster_ci95_points_recomputed_at_seed_20260913'][1]:.1f}]; the kill is "
            f"evaluated against the registered one.)"]


def _table3(out: dict) -> list[str]:
    k = out["k_max"]
    lines = ["### Table 3 — the curves: union rate at each K with its problem-cluster interval (P; then C)", "",
             "| family | stratum | " + " | ".join(f"K={i}" for i in range(1, k + 1)) + " |",
             "|---|---|" + "---|" * k]
    for f in ("cross", "cross-R"):
        e = out["families"][f]
        for st in ("P", "C"):
            cells = [f"{_pc(v)} [{_iv(ci)}]" for v, ci in zip(e[st]["curve"], e[st]["curve_cluster_ci95"])]
            lines.append(f"| {LABELS[f]} | {st} | " + " | ".join(cells) + " |")
    return lines


def _table4(out: dict) -> list[str]:
    k = out["k_max"]
    lines = ["### Table 4 — H20b: the fitted asymptote (ceiling 1 §1.2, constrained), the registered flattening bar, "
             "and the exchange rate", "",
             "| family | A (P) | A cluster 95% | τ | R² | max abs residual (points) "
             "| ZIBB π, ceiling 1 §1.2's secondary [cluster, 1,000 resamples] "
             f"| K={k - 1}→K={k} gain (points) [cluster] | flattened by ceiling 1's bar (gain ≤ 1.0) "
             "| asymptote is an extrapolation | raw union at K_max (the sturdier number) "
             "| Δrecall/ΔFP K=1→K_max [cluster] (EXPLORATORY) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in ("cross", "cross-R"):
        e = out["families"][f]
        fit = e["P"]["fit"]
        fl = out["H20b_flattening"][f]
        x = e["exchange_rate_cluster_ci95_EXPLORATORY"]
        u = fl["raw_union_at_kmax"]
        z = e["P"]["zibb"]
        lines.append(f"| {LABELS[f]} | {_pc(fit['A'])}% | {_iv(fit['A_ci95_cluster'])} | {fit['tau']:.2f} "
                     f"| {fit['r2']:.4f} | {100 * e['P']['fit_max_resid']:.2f} "
                     f"| {_pc(z['pi'])}% [{_iv(z['pi_cluster_ci95'])}; {z['all_zero_resamples']} all-zero] "
                     f"| {fl['gain_last_step_points']:.2f} [{_pts(fl['gain_cluster_ci95_points'], 2)}] "
                     f"| {'yes' if fl['flattened'] else 'no'} | {'yes' if fl['asymptote_is_extrapolation'] else 'no'} "
                     f"| {u['k']}/{u['n']} = {_pc(u['rate'])}% [{_iv(u['cluster_ci95'])}] "
                     f"| {e['exchange_rate_recall_per_fp_EXPLORATORY']:.2f} [{x[0]:.2f}–{x[1]:.2f}]"
                     + (f" ({x[2]} discarded)" if x[2] else "") + " |")
    return lines


def _asymptote_diff(out: dict) -> list[str]:
    hb = out["H20b_asymptote_difference_P"]
    return [f"A(`cross-R`) − A(`cross`) on P, the constrained fit refitted inside every one of the "
            f"{hb['reps']:,} problem-cluster resamples: **{hb['difference_points']:+.1f} points, cluster "
            f"[{_pts(hb['cluster_ci95_points'])}]** ({hb['resamples_fitted']:,} resamples fitted). "
            f"Method: {hb['note']}."]


def _table5(out: dict) -> list[str]:
    s = out["H20c_single_draw_fp"]
    lines = [f"### Table 5 — H20c: the single-draw false-positive rate on C against the product bar "
             f"({100 * s['bar']:.1f}%)", "",
             "| family | mean over the K draws [cluster] | per-draw flagged instances (of 150) "
             "| draws at or below the bar |", "|---|---|---|---|"]
    for f in ("cross", "cross-R"):
        e = s[f]
        m = e["mean_over_draws"]
        per = ", ".join(str(d["k"]) for d in e["per_draw"])
        lines.append(f"| {LABELS[f]} | {_pc(m['rate'])}% [{_iv(m['cluster_ci95'])}] | {per} "
                     f"| {e['draws_at_or_below_bar']} of {e['k_max']} |")
    return lines


def _table6(out: dict) -> list[str]:
    lines = ["### Table 6 — the any-finding rule (§3, preregistered secondary): a flag rate, not a defect-naming rate", "",
             "| family | K | P union | Wilson | cluster | single-draw P [cluster] | C union | Wilson | cluster "
             "| single-draw C [cluster] |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for f in ("cross", "cross-R", "cross-T"):
        e = out["secondary_any_finding_rule"]["families"].get(f)
        if not e:
            continue
        p, c = e["P"]["union_at_kmax"], e["C"]["union_at_kmax"]
        lines.append(f"| {LABELS[f]} | {e['k_max']} | {p['k']}/{p['n']} = {_pc(p['rate'])}% | {_iv(p['wilson95'])} "
                     f"| {_iv(p['cluster_ci95'])} | {_pc(e['P']['single_draw_mean'])} [{_iv(e['P']['curve_cluster_ci95'][0])}] "
                     f"| {c['k']}/{c['n']} = {_pc(c['rate'])}% | {_iv(c['wilson95'])} | {_iv(c['cluster_ci95'])} "
                     f"| {_pc(e['C']['single_draw_mean'])} [{_iv(e['C']['curve_cluster_ci95'][0])}] |")
    return lines


def _table7(out: dict) -> list[str]:
    lines = ["### Table 7 — `mixed` (K/2 `cross` + K/2 `cross-R`) against each family alone at the same total", "",
             "| stratum | total K | mixed | cluster 95% | `cross` alone [cluster] | `cross-R` alone [cluster] |",
             "|---|---|---|---|---|---|"]
    for st, key in (("P", "secondary_mixed_cross_crossR_P"), ("C", "secondary_mixed_cross_crossR_C")):
        m = out[key]
        for total in (2, 4, 6, 8):
            v = m["totals"].get(f"K={total}")
            if not v:
                continue
            a, b = out["families"]["cross"][st], out["families"]["cross-R"][st]
            lines.append(f"| {st} | {total} | {_pc(v['mixed_union'])}% | {_iv(v['cluster_ci95'])} "
                         f"| {_pc(a['curve'][total - 1])}% [{_iv(a['curve_cluster_ci95'][total - 1])}] "
                         f"| {_pc(b['curve'][total - 1])}% [{_iv(b['curve_cluster_ci95'][total - 1])}] |")
    return lines


def _table8(out: dict) -> list[str]:
    r = out["H20d_residual"]
    lines = [f"### Table 8 — H20d: the residual across {len(r['families'])} families ({r['total_draws']} draws), "
             "by ceiling 1 §1.5's category", "",
             "| category | after study 18 (5 families) | with `cross-R` added | left the residual |",
             "|---|---|---|---|"]
    for cat in sorted(set(r["study18_by_category"]) | set(r["by_category"])):
        lines.append(f"| {cat} | {r['study18_by_category'].get(cat, 0)} | {r['by_category'].get(cat, 0)} "
                     f"| {r['left_the_residual_by_category'].get(cat, 0)} |")
    lines.append(f"| **total** | **{r['study18_residual_n']}** | **{r['n']}** "
                 f"| **{len(r['left_the_residual_when_cross_R_was_added'])}** |")
    res = r["residual"]
    lines += ["", f"Residual rate with `cross-R` added: {res['k']}/{res['n']} = {_pc(res['rate'])}% "
              f"(Wilson {_iv(res['wilson95'])}; cluster {_iv(res['cluster_ci95'])}). "
              f"New to the residual: {len(r['new_to_the_residual'])}."]
    return lines


def _table11(out: dict) -> list[str]:
    lines = ["### Table 11 — reply format, provider denials and ledger cost, per draw", "",
             "| draw | readings | prompt digest = study 2's base | malformed after repair "
             "| repair re-asks (ledger calls − readings) | replies > 300 output tokens "
             "| denied attempts retried (rows / distinct instances) | ledger $ |",
             "|---|---|---|---|---|---|---|---|"]
    fmt = out["secondary_reply_format_and_cost"]
    for name in sorted(fmt, key=lambda s: (s.split("-d")[0], int(s.split("-d")[1]))):
        v = fmt[name]
        lines.append(f"| `{name}` | {v['rows']} | {v['prompt_digest_equals_study2_base']} "
                     f"| {v['invalid_reason_nonempty']} "
                     f"| {'n/a' if v['ledger_calls_minus_readings'] is None else v['ledger_calls_minus_readings']} "
                     f"| {'n/a' if v['replies_over_300_output_tokens'] is None else v['replies_over_300_output_tokens']} "
                     f"| {v['provider_denial_rows_before_completion']} / "
                     f"{v['provider_denial_instances_before_completion']} "
                     f"| {'n/a' if v['ledger_usd'] is None else format(v['ledger_usd'], '.4f')} |")
    return lines


def _adj(out: dict) -> dict:
    return out["amendment1_adjudication"]


def _table9(out: dict) -> list[str]:
    """Table 9 — the two raters against each other, before any rate built on them."""
    a = _adj(out)
    if not a.get("run"):
        return ["### Table 9 — Amendment 1's adjudication", "",
                "The adjudication has not been answered; there is nothing to tabulate."]
    nm, rg = a["naming"], a["recognition"]
    k = "undefined" if rg["kappa"] is None else f"{rg['kappa']:.3f}"
    return ["### Table 9 — Amendment 1's adjudication: the two raters against each other, over "
            f"{nm['items']} blind sheet items", "",
            "| question | scope | both yes | L1 only | L2 only | both no | agreement | Cohen κ |",
            "|---|---|---|---|---|---|---|---|",
            f"| naming (study 19's registered question) | all {nm['items']} items | {nm['both_yes']} "
            f"| {nm['L1_only']} | {nm['L2_only']} | {nm['both_no']} "
            f"| {nm['agree']}/{nm['items']} = {_pc(nm['agreement'])}% | **{nm['kappa']:.3f}** |",
            f"| recognition, \"defect\" (registered HERE by Amendment 1) | the {rg['items']} "
            f"consensus naming-yes items | {rg['both_defect']} | {rg['L1_only']} | {rg['L2_only']} "
            f"| {rg['neither']} | {rg['agree']}/{rg['items']} = {_pc(rg['agreement'])}% | {k} |",
            "",
            f"L1 answered yes on {nm['L1_yes']} items, L2 on {nm['L2_yes']}; of the "
            f"{nm['disagreements']} disagreements {nm['disagreements_L1_no_L2_yes']} are "
            f"L1-no/L2-yes and {nm['disagreements_L1_yes_L2_no']} are L1-yes/L2-no, so "
            f"{nm['more_inclusive_rater']} is the more inclusive rater. {rg['kappa_note']}"]


def _table10(out: dict) -> list[str]:
    """Table 10 — the rates, under every reader rule, because κ on naming is low."""
    a = _adj(out)
    if not a.get("run"):
        return ["### Table 10 — Amendment 1's rates", "", "Not answered."]
    lines = ["### Table 10 — P instances named, and P instances with a defect-asserting finding, "
             "under each reader rule (rate over all 110 P instances; Wilson; problem-cluster bootstrap)", "",
             "| route | question | rule | instances | rate | Wilson | cluster |",
             "|---|---|---|---|---|---|---|"]
    labels = {"naming": "names the failing class", "defect_asserting": "**asserts it is a defect**"}
    for arm in ("T", "R"):
        e = a["arms"][arm]
        for question in ("naming", "defect_asserting"):
            for rule in ("consensus", "L1", "L2", "either"):
                v = e[question][rule]
                star = " **(registered primary)**" if (arm == "T" and question == "defect_asserting"
                                                       and rule == "consensus") else ""
                lines.append(f"| `{e['route']}` | {labels[question]} | {rule}{star} | {v['k']} of {v['n']} "
                             f"| {_pc(v['rate'])}% | {_iv(v['wilson95'])} | {_iv(v['cluster_ci95'])} |")
    t, r = a["arms"]["T"], a["arms"]["R"]
    lines += ["", f"Denominators: `cross-T`'s one reading returned a finding on "
              f"{t['P_instances_with_a_finding']} of the 110 P instances ({t['items']} findings) and "
              f"`cross-R`'s draw 1 on {r['P_instances_with_a_finding']} ({r['items']} findings); the "
              f"rates above are over all 110 either way. The consensus rule counts a disputed item as "
              f"NOT named, which is the preregistered direction."]
    return lines


def _kill_a(out: dict) -> list[str]:
    a = _adj(out)
    if not a.get("run"):
        return ["**Amendment 1's kill** is not evaluated: the adjudication has not been answered."]
    k = a["amendment1_kill"]
    t = a["arms"]["T"]
    span = sorted({t[q][r]["k"] for q in ("naming", "defect_asserting")
                   for r in ("consensus", "L1", "L2", "either")})
    every = ("and it fires under every one of the eight ways of reading that rate "
             "(two questions by four reader rules): the count runs from "
             f"{span[0]} to {span[-1]} of 110, every one below {k['threshold_k']}"
             if k["fired_under_every_rule_and_question"] else
             "but NOT under every reader rule; the rules that do not fire it are in Table 10")
    return [f"**Amendment 1's kill.** {k['rule']}. `cross-T`'s registered primary is "
            f"{k['primary_k']} of {k['primary_n']}, below {k['threshold_k']}, so the kill "
            f"**{'FIRED' if k['fired'] else 'did not fire'}** — {every}. The verdict therefore does "
            f"not rest on the raters' disagreement, even though the point estimate does."]


def _cost(out: dict) -> list[str]:
    cost = out["cost"]
    if cost["ledger_usd_total"] is None:
        return ["Ledger cost not read: the analysis was run without `--run`."]
    return [f"Total from the {len(out['secondary_reply_format_and_cost'])} project ledgers: "
            f"**${cost['ledger_usd_total']:.2f}** over {cost['ledger_calls_total']:,} calls for "
            f"{cost['readings_total']:,} readings, against the ${cost['budget_cap_usd']:.0f} cap. "
            f"Note: {cost['note']}."]


RENDERERS = {"PREAMBLE": _preamble, "TABLE1": _table1, "TABLE2": _table2, "KILL": _kill,
             "TABLE3": _table3, "TABLE4": _table4, "ASYMPTOTE-DIFF": _asymptote_diff,
             "TABLE5": _table5, "TABLE6": _table6, "TABLE7": _table7, "TABLE8": _table8,
             "TABLE9": _table9, "TABLE10": _table10, "KILL-A": _kill_a,
             "TABLE11": _table11, "COST": _cost}


def render_tables(out: dict) -> str:
    """The blocks RESULTS-CEILING4.md embeds verbatim. Every cell comes from ``out``.

    ``out`` is ``records/ceiling4/numbers.json`` and nothing else: no record file is read
    here, so the tables are reproducible from the committed numbers alone. Each block is
    wrapped in its own BEGIN/END marker pair and ``ceiling4/splice_tables.py`` copies the
    bytes between a pair into the pair of the same name in the results file.
    """
    parts = ["<!-- generated by report_ceiling4.py; do not edit -->"]
    for name in BLOCK_NAMES:
        body = "\n".join(RENDERERS[name](out))
        parts.append(f"{BEGIN.format(name=name)}\n{body}\n{END.format(name=name)}")
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
