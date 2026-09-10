"""Study 19 — ceiling 3b's preregistered outcomes over the records, and nothing else.

Arms: S = study 18's self-strong draws 1–4 (records/ceiling3), R and B = records/ceiling3b.
Both flag rules (BLOCKER; any finding). Contrasts B − S and R − S at K = 4 on P and C, paired
per instance, with the problem-cluster bootstrap (seed 20260912), Tango and the
grid-unconditional interval (ceiling 1 Amendment 5's qualification), McNemar and the cluster
sign-flip. H19d's adjudication is read from records/ceiling3b/L1-h19d.csv, L2-h19d.csv when
they exist.

    python benchmarks/code/report_ceiling3b.py --run <archive dir>
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore  # noqa: E402
import report_ceiling as rc  # noqa: E402
import report_ceiling3 as r3  # noqa: E402

RECORDS = HERE / "records"
C3B = RECORDS / "ceiling3b"
BOOT_SEED, BOOTSTRAP = 20260912, 10_000
ARMS = {"S": ("self-strong", RECORDS / "ceiling3"), "R": ("self-strong-R", C3B), "B": ("self-strong-B", C3B)}
explore.ROUTES.update({"self-strong": "anthropic:claude-sonnet-4-6", "self-strong-R": "anthropic:claude-sonnet-4-6",
                       "self-strong-B": "anthropic:claude-sonnet-4-6", "self-strong-S": "anthropic:claude-sonnet-4-6"})


def load_arm(route: str, directory: Path, scope: set[str], k: int = 4) -> tuple[dict, dict]:
    """draw -> instance -> flagged (BLOCKER rule), and the same under any finding."""
    blk, anyf = {}, {}
    for d in range(1, k + 1):
        cache = directory / "cache" / f"holistic__{route}__d{d}.jsonl"
        rows = [json.loads(l) for l in cache.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows = [r for r in rows if r.get("ok") and r["instance_id"] in scope]
        if len(rows) != len(scope):
            raise SystemExit(f"{route} d{d}: {len(rows)} of {len(scope)} readings")
        blk[d] = {r["instance_id"]: bool(r["flagged"]) for r in rows}
        anyf[d] = {r["instance_id"]: int(r.get("model_findings", 0) or 0) > 0 for r in rows}
    return blk, anyf


def block(draws: dict, ids: list[str], instances: dict) -> dict:
    k_max = len(draws)
    ks = rc.counts_per_instance(draws, ids)
    curve = rc.union_curve(ks, k_max)
    by_problem: dict[str, list[int]] = {}
    for i, kk in zip(ids, ks):
        by_problem.setdefault(instances[i]["problem_id"], []).append(kk)
    union = {i: any(draws[d].get(i) for d in draws) for i in ids}
    return {"k_max": k_max, "curve": curve,
            "curve_cluster_ci95": r3.curve_cluster_cis(by_problem, k_max, BOOTSTRAP, BOOT_SEED),
            "union_at_kmax": rc.clustered_rate(union, ids, instances, BOOTSTRAP, BOOT_SEED),
            "single_draw_mean": curve[0]}


def contrast(a: dict, b: dict, ids: list[str], instances: dict) -> dict:
    """Union-at-K recall of A minus B on the same instances, paired per instance, with THIS
    study's registered seed (20260912). Round 1 of the review found the delegation to
    study 18's helper used that module's seed (20260910); the computation is restated
    here so the seed is the preregistration's and is visible."""
    k = len(a)
    da = sorted(a); db = sorted(b)
    by_problem: dict[str, list[float]] = {}
    ka = kb = 0
    for i in ids:
        fa = any(a[d].get(i) for d in da); fb = any(b[d].get(i) for d in db)
        ka += fa; kb += fb
        by_problem.setdefault(instances[i]["problem_id"], []).append(float(fa) - float(fb))
    lo, hi = rc.cluster_bootstrap_ci(by_problem, BOOTSTRAP, BOOT_SEED)
    b_only = sum(1 for i in ids if any(a[d].get(i) for d in da) and not any(b[d].get(i) for d in db))
    c_only = sum(1 for i in ids if not any(a[d].get(i) for d in da) and any(b[d].get(i) for d in db))
    n = len(ids)
    return {"k": k, "n": n, "a_union": ka / n, "b_union": kb / n,
            "difference_points": 100 * (ka - kb) / n,
            "cluster_ci95_points": [100 * lo, 100 * hi], "cluster_seed": BOOT_SEED,
            "tango_ci95_points": [100 * x for x in rc.tango_score_interval(b_only, c_only, n)],
            "exact_unconditional_ci95_points": [100 * x for x in rc.exact_unconditional_interval(b_only, c_only, n)],
            "one_signed_discordance": (b_only == 0) != (c_only == 0) and (b_only + c_only) > 0,
            "a_only": b_only, "b_only": c_only, "mcnemar_exact_p": rc.mcnemar_exact(b_only, c_only),
            "signflip": rc.signflip_p(by_problem)}


def secondaries(run_dir: Path, arms: dict, P: list[str], instances: dict) -> dict:
    """Reply format and cost from the archive's ledgers; BLOCKER share among findings; the
    residual across ALL measured families when R or B is added; exchange rates."""
    out: dict = {"per_draw": {}}
    for arm, route in (("R", "self-strong-R"), ("B", "self-strong-B"), ("S-text", "self-strong-S")):
        for d in range(1, 5 if arm != "S-text" else 2):
            cache = C3B / "cache" / f"holistic__{route}__d{d}.jsonl"
            if not cache.exists():
                continue
            rows = [json.loads(l) for l in cache.read_text().splitlines() if l.strip()]
            ledger = run_dir / "projects" / f"project-holistic__{route}__d{d}" / ".crossaudit" / "usage.jsonl"
            ev = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
            findings = sum(int(r.get("model_findings", 0) or 0) for r in rows)
            blockers = sum(int(r.get("model_blockers", 0) or 0) for r in rows)
            out["per_draw"][f"{arm}-d{d}"] = {
                "rows": len(rows), "invalid_reason_nonempty": sum(1 for r in rows if r.get("invalid_reason")),
                "ledger_calls": len(ev), "ledger_usd": round(sum(float(e.get("api_value_usd") or 0) for e in ev), 4),
                "extra_calls": len(ev) - len(rows),
                "replies_over_300_output_tokens": sum(1 for e in ev if int(e.get("output", 0) or 0) > 300),
                "findings_total": findings, "blockers_total": blockers,
                "blocker_share_of_findings": (blockers / findings) if findings else None}
    out["ledger_usd_total"] = round(sum(v["ledger_usd"] for v in out["per_draw"].values()), 4)
    out["ledger_calls_total"] = sum(v["ledger_calls"] for v in out["per_draw"].values())
    # the residual across all measured families (ceiling 1's five, at their K_max) plus R, plus B
    c3 = json.loads((RECORDS / "ceiling3" / "numbers.json").read_text(encoding="utf-8"))
    base_never = set(c3["never_flagged_by_any_family"]["instance_ids"])
    rcls = json.loads((RECORDS / "ceiling" / "residual_classification.json").read_text(encoding="utf-8"))["classification"]
    res = {"ceiling3_residual_n": len(base_never)}
    for arm in ("R", "B"):
        blk = arms[arm]["blocker"]
        still = sorted(i for i in base_never if not any(blk[d].get(i) for d in blk))
        left = sorted(i for i in base_never if i not in still)
        cats: dict[str, int] = {}
        for i in left:
            c = rcls.get(i, {}).get("category", "unclassified"); cats[c] = cats.get(c, 0) + 1
        res[f"with_{arm}"] = {"n": len(still), "left_by_category": dict(sorted(cats.items())),
                             "rate": rc.clustered_rate({i: (i in still) for i in P}, P, instances, BOOTSTRAP, BOOT_SEED)}
    out["residual"] = res
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="")
    args = ap.parse_args()
    instances = rc.load_instances(); audit_set = rc.load_audit_set()
    scope = [i for i in audit_set if instances[i]["stratum"] in ("P", "C")]
    P = [i for i in scope if instances[i]["stratum"] == "P"]; C = [i for i in scope if instances[i]["stratum"] == "C"]
    arms = {}
    for arm, (route, directory) in ARMS.items():
        blk, anyf = load_arm(route, directory, set(scope))
        arms[arm] = {"route": route, "blocker": blk, "any": anyf}
    out = {"study": "study19 / ceiling 3b", "bootstrap": {"seed": BOOT_SEED, "reps": BOOTSTRAP, "unit": "problem"},
           "n_P": len(P), "n_C": len(C), "arms": {}, "contrasts": {}}
    for arm in ARMS:
        out["arms"][arm] = {rule: {"P": block(arms[arm][rule], P, instances), "C": block(arms[arm][rule], C, instances)}
                            for rule in ("blocker", "any")}
    for name, (x, y) in {"B_minus_S": ("B", "S"), "R_minus_S": ("R", "S"), "B_minus_R": ("B", "R")}.items():
        out["contrasts"][name] = {rule: {st: contrast(arms[x][rule], arms[y][rule], ids, instances)
                                         for st, ids in (("P", P), ("C", C))} for rule in ("blocker", "any")}
    for arm in ARMS:
        for rule in ("blocker", "any"):
            e = out["arms"][arm][rule]; rec, fp = e["P"]["curve"], e["C"]["curve"]
            e["exchange_rate_recall_per_fp"] = ((rec[-1] - rec[0]) / (fp[-1] - fp[0])) if fp[-1] != fp[0] else None
    if args.run:
        out["secondaries"] = secondaries(Path(args.run), arms, P, instances)
    prim = out["contrasts"]["B_minus_S"]["blocker"]["P"]
    out["H19a"] = {"difference_points": prim["difference_points"], "cluster_ci95_points": prim["cluster_ci95_points"],
                   "holds": prim["cluster_ci95_points"][0] > 0,
                   "kill_for_the_severity_inference": not (prim["cluster_ci95_points"][0] > 0)}
    # H19d: adjudication
    key = {r["id"]: r for r in (json.loads(l) for l in (HERE / "ceiling3b" / "key-h19d.jsonl").read_text().splitlines() if l.strip())}
    labels = {}
    for who in ("L1", "L2"):
        path = C3B / f"{who}-h19d.csv"
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                labels[who] = {row["id"]: row["label"].strip().lower() for row in csv.DictReader(fh)}
    if labels:
        h = {"n_items": len(key), "by_arm": {}}
        gold = {}
        if "L1" in labels and "L2" in labels:
            agree = sum(1 for i in key if labels["L1"].get(i) == labels["L2"].get(i))
            cats = ("yes", "no", "cannot tell")
            po = agree / len(key)
            pe = sum((sum(1 for i in key if labels["L1"].get(i) == c) / len(key)) * (sum(1 for i in key if labels["L2"].get(i) == c) / len(key)) for c in cats)
            h["kappa"] = (po - pe) / (1 - pe) if pe < 1 else 1.0
            h["agreement"] = [agree, len(key)]
            h["disagreements"] = sorted(i for i in key if labels["L1"].get(i) != labels["L2"].get(i))
            gold = {i: (labels["L1"][i] if labels["L1"].get(i) == labels["L2"].get(i) else "disputed") for i in key}
        elif "L1" in labels:
            gold = dict(labels["L1"]); h["note"] = "L1 only; no kappa"
        for arm in ("S", "R", "B"):
            items = [i for i in key if key[i]["arm"] == arm]
            inst = {}
            for i in items:
                inst.setdefault(key[i]["instance"], []).append(gold.get(i))
            names_P = {ins: any(v == "yes" for v in vals) for ins, vals in inst.items()}
            ids = sorted(names_P)
            h["by_arm"][arm] = {"findings": len(items),
                                "findings_yes": sum(1 for i in items if gold.get(i) == "yes"),
                                "findings_no": sum(1 for i in items if gold.get(i) == "no"),
                                "findings_cannot_tell": sum(1 for i in items if gold.get(i) == "cannot tell"),
                                "findings_disputed": sum(1 for i in items if gold.get(i) == "disputed"),
                                "P_instances_with_a_finding": len(ids),
                                "P_instances_named_by_some_finding": rc.clustered_rate(names_P, ids, instances, BOOTSTRAP, BOOT_SEED) if ids else None,
                                "names_rate_over_all_P": rc.clustered_rate(names_P, P, instances, BOOTSTRAP, BOOT_SEED)}
        # The second question (review round 1; post hoc, labelled so): among consensus-"yes"
        # findings, does the finding assert the code is WRONG on that class ("defect") or say it
        # is handled correctly / only untested ("correct")? Recognition, not mention.
        strict = {}
        for who in ("L1", "L2"):
            path = C3B / f"{who}-h19d-strict.csv"
            if path.exists():
                with path.open(encoding="utf-8") as fh:
                    strict[who] = {row["id"]: row["label"].strip().lower() for row in csv.DictReader(fh)}
        if strict:
            items = sorted(set.intersection(*(set(v) for v in strict.values())))
            st = {"n_items": len(items), "note": "post hoc (review round 1): the 'yes' items re-labelled for whether the finding asserts a defect on that class"}
            if len(strict) == 2:
                agree = sum(1 for i in items if strict["L1"][i] == strict["L2"][i])
                cats = ("defect", "correct", "cannot tell")
                po = agree / len(items) if items else 0
                pe = sum((sum(1 for i in items if strict["L1"][i] == c) / len(items)) * (sum(1 for i in items if strict["L2"][i] == c) / len(items)) for c in cats) if items else 1
                st["agreement"] = [agree, len(items)]; st["kappa"] = (po - pe) / (1 - pe) if pe < 1 else 1.0
                st["disagreements"] = sorted(i for i in items if strict["L1"][i] != strict["L2"][i])
                sgold = {i: (strict["L1"][i] if strict["L1"][i] == strict["L2"][i] else "disputed") for i in items}
            else:
                sgold = dict(strict["L1"]); st["note"] += "; L1 only"
            st["by_arm"] = {}
            for arm in ("S", "R", "B"):
                inst: dict[str, list] = {}
                for i in items:
                    if key[i]["arm"] == arm:
                        inst.setdefault(key[i]["instance"], []).append(sgold.get(i))
                rec = {ins: any(v == "defect" for v in vals) for ins, vals in inst.items()}
                st["by_arm"][arm] = {"yes_findings": sum(1 for i in items if key[i]["arm"] == arm),
                                     "defect": sum(1 for i in items if key[i]["arm"] == arm and sgold.get(i) == "defect"),
                                     "correct": sum(1 for i in items if key[i]["arm"] == arm and sgold.get(i) == "correct"),
                                     "cannot_tell": sum(1 for i in items if key[i]["arm"] == arm and sgold.get(i) == "cannot tell"),
                                     "disputed": sum(1 for i in items if key[i]["arm"] == arm and sgold.get(i) == "disputed"),
                                     "recognised_rate_over_all_P": rc.clustered_rate(rec, P, instances, BOOTSTRAP, BOOT_SEED)}
            h["strict_recognition_POST_HOC"] = st
        out["H19d"] = h
    C3B.mkdir(parents=True, exist_ok=True)
    (C3B / "numbers.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (C3B / "tables.md").write_text(render_tables(out), encoding="utf-8")
    for arm in ARMS:
        for rule in ("blocker", "any"):
            e = out["arms"][arm][rule]
            print(f"{arm} {rule:8s} P union {100*e['P']['union_at_kmax']['rate']:5.1f}% [{100*e['P']['union_at_kmax']['cluster_ci95'][0]:.1f}, {100*e['P']['union_at_kmax']['cluster_ci95'][1]:.1f}]  single {100*e['P']['single_draw_mean']:.1f}%   C union {100*e['C']['union_at_kmax']['rate']:.1f}%  single {100*e['C']['single_draw_mean']:.1f}%")
    for name, v in out["contrasts"].items():
        for rule in ("blocker", "any"):
            p = v[rule]["P"]; c = v[rule]["C"]
            print(f"{name} {rule:8s} P {p['difference_points']:+.1f} [{p['cluster_ci95_points'][0]:+.1f}, {p['cluster_ci95_points'][1]:+.1f}] ({p['a_only']} vs {p['b_only']})   C {c['difference_points']:+.1f} [{c['cluster_ci95_points'][0]:+.1f}, {c['cluster_ci95_points'][1]:+.1f}]")
    print("H19a:", out["H19a"])
    if "H19d" in out:
        print("H19d:", json.dumps({k: v for k, v in out["H19d"].items() if k != "by_arm"}), {a: (v["findings_yes"], v["findings"]) for a, v in out["H19d"]["by_arm"].items()})
    return 0


LABEL = {"S": "S — shipped constitution (study 18's draws 1–4)", "R": "R — + referent rule (CA-COVER-001)", "B": "B — + grading rule (CA-GRADE-001)"}


def _pc(x) -> str:
    return f"{100 * x:.1f}"


def _iv(p) -> str:
    return f"{_pc(p[0])}–{_pc(p[1])}"


def _ivp(p) -> str:
    return f"[{p[0]:+.1f}, {p[1]:+.1f}]"


def render_tables(out: dict) -> str:
    L = ["<!-- generated by report_ceiling3b.py; do not edit -->", "",
         "Intervals: a k/n rate carries the 95% Wilson interval and the problem-cluster percentile bootstrap "
         "(10,000 resamples, seed 20260912); curve points and single-draw means are subset-averaged means and carry "
         "the cluster interval only; paired contrasts carry the cluster interval (primary), Tango's score interval and "
         "the grid-unconditional interval (an exact test maximised over a 41-point nuisance grid, no bound on the "
         "missed supremum — ceiling 1 Amendment 5), the latter two ignoring clustering. Where every discordant pair "
         "points one way, the grid-unconditional interval is the one to quote (ceiling 1's rule).", ""]
    for rule, title in (("blocker", "BLOCKER rule (preregistered primary flag)"), ("any", "any-finding rule (preregistered secondary)")):
        L += [f"### Table {'1' if rule == 'blocker' else '2'} — union of K = 4 readings, {title}", "",
              "| arm | P union recall | Wilson | cluster | single-draw P [cluster] | C union FP | Wilson | cluster | single-draw C [cluster] | Δrecall/ΔFP |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for arm in ("S", "R", "B"):
            e = out["arms"][arm][rule]; p, c = e["P"]["union_at_kmax"], e["C"]["union_at_kmax"]
            x = e.get("exchange_rate_recall_per_fp")
            L.append(f"| {LABEL[arm]} | {p['k']}/{p['n']} = {_pc(p['rate'])}% | {_iv(p['wilson95'])} | {_iv(p['cluster_ci95'])} "
                     f"| {_pc(e['P']['single_draw_mean'])} [{_iv(e['P']['curve_cluster_ci95'][0])}] "
                     f"| {c['k']}/{c['n']} = {_pc(c['rate'])}% | {_iv(c['wilson95'])} | {_iv(c['cluster_ci95'])} "
                     f"| {_pc(e['C']['single_draw_mean'])} [{_iv(e['C']['curve_cluster_ci95'][0])}] | {('%.2f' % x) if x is not None else 'n/a'} |")
        L.append("")
    L += ["### Table 3 — the curves at K = 1…4 with cluster intervals (P; then C), both rules", "",
          "| arm | rule | stratum | K=1 | K=2 | K=3 | K=4 |", "|---|---|---|---|---|---|---|"]
    for arm in ("S", "R", "B"):
        for rule in ("blocker", "any"):
            for st in ("P", "C"):
                e = out["arms"][arm][rule][st]
                L.append(f"| {arm} | {rule} | {st} | " + " | ".join(f"{_pc(v)} [{_iv(ci)}]" for v, ci in zip(e["curve"], e["curve_cluster_ci95"])) + " |")
    L += ["", "### Table 4 — paired contrasts at K = 4 (points; a-only / b-only discordant counts)", "",
          "| contrast | rule | stratum | difference | cluster 95% | Tango | grid-unconditional | one-signed | a-only / b-only | McNemar p | sign-flip p |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in ("B_minus_S", "R_minus_S", "B_minus_R"):
        for rule in ("blocker", "any"):
            for st in ("P", "C"):
                v = out["contrasts"][name][rule][st]
                L.append(f"| {name.replace('_minus_', ' − ')} | {rule} | {st} | {v['difference_points']:+.1f} | {_ivp(v['cluster_ci95_points'])} "
                         f"| {_ivp(v['tango_ci95_points'])} | {_ivp(v['exact_unconditional_ci95_points'])} | {'yes' if v['one_signed_discordance'] else 'no'} "
                         f"| {v['a_only']} / {v['b_only']} | {v['mcnemar_exact_p']:.2e} | {v['signflip']['p']:.2e} |")
    if "H19d" in out and "by_arm" in out["H19d"]:
        h = out["H19d"]
        if "strict_recognition_POST_HOC" in h:
            st = h["strict_recognition_POST_HOC"]
            L += ["", f"### Table 5b — POST HOC (review round 1): of the consensus-'yes' findings, does the finding assert the code is wrong on that class? ({st['n_items']} items"
                  + (f"; agreement {st['agreement'][0]}/{st['agreement'][1]}, κ = {st['kappa']:.3f}" if 'kappa' in st else "; L1 only") + "; disputed excluded from 'defect')", "",
                  "| arm | 'yes' findings | defect | correct / untested | cannot tell | disputed | P instances with a defect-asserting finding / all 110 | Wilson | cluster |",
                  "|---|---|---|---|---|---|---|---|---|"]
            T5 = dict(LABEL, S="S-text — shipped constitution, a fifth reading (Amendment 1)")
            for arm in ("S", "R", "B"):
                v = st["by_arm"][arm]; r = v["recognised_rate_over_all_P"]
                L.append(f"| {T5[arm]} | {v['yes_findings']} | {v['defect']} | {v['correct']} | {v['cannot_tell']} | {v['disputed']} | {r['k']}/{r['n']} = {_pc(r['rate'])}% | {_iv(r['wilson95'])} | {_iv(r['cluster_ci95'])} |")
        L += ["", f"### Table 5 — H19d, blinded adjudication of draw-1 findings on P instances: does the finding name the input class or behaviour on which the hidden test fails? "
              f"({h['n_items']} items; L1 the author, L2 gpt-6-astra; agreement {h['agreement'][0]}/{h['agreement'][1]}, κ = {h['kappa']:.3f}; disputed items excluded from 'yes')", "",
              "| arm | findings | yes | no | cannot tell | disputed | P instances with a finding | of which named by some finding | named / all 110 P | Wilson | cluster |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        T5 = dict(LABEL, S="S-text — shipped constitution, a fifth reading (Amendment 1)")
        for arm in ("S", "R", "B"):
            v = h["by_arm"][arm]; r = v["names_rate_over_all_P"]
            L.append(f"| {T5[arm]} | {v['findings']} | {v['findings_yes']} | {v['findings_no']} | {v['findings_cannot_tell']} | {v['findings_disputed']} "
                     f"| {v['P_instances_with_a_finding']} | {v['P_instances_named_by_some_finding']['k'] if v['P_instances_named_by_some_finding'] else 0} "
                     f"| {r['k']}/{r['n']} = {_pc(r['rate'])}% | {_iv(r['wilson95'])} | {_iv(r['cluster_ci95'])} |")
    sec = out.get("secondaries")
    if sec:
        L += ["", "### Table 6 — reply format and cost per draw, from the caches and the ledgers", "",
              "| draw | readings | malformed | ledger calls | extra calls | replies > 300 output tokens | findings | BLOCKER findings | BLOCKER share | ledger USD |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in sec["per_draw"].items():
            L.append(f"| {k} | {v['rows']} | {v['invalid_reason_nonempty']} | {v['ledger_calls']} | {v['extra_calls']} | {v['replies_over_300_output_tokens']} "
                     f"| {v['findings_total']} | {v['blockers_total']} | {(_pc(v['blocker_share_of_findings']) + '%') if v['blocker_share_of_findings'] is not None else 'n/a'} | ${v['ledger_usd']:.2f} |")
        L.append(f"| **total** | | | {sec['ledger_calls_total']} | | | | | | **${sec['ledger_usd_total']:.2f}** |")
        r = sec["residual"]
        L += ["", f"### Table 7 — the residual: P instances blocked by no measured family (ceiling 3's five families: {r['ceiling3_residual_n']}) when an arm is added", "",
              "| added arm | residual n | rate | Wilson | cluster | instances that left, by ceiling 1's category |", "|---|---|---|---|---|---|"]
        for arm in ("R", "B"):
            v = r[f"with_{arm}"]; rt = v["rate"]
            L.append(f"| {arm} | {v['n']} | {rt['k']}/{rt['n']} = {_pc(rt['rate'])}% | {_iv(rt['wilson95'])} | {_iv(rt['cluster_ci95'])} | {', '.join(f'{k} {n}' for k, n in v['left_by_category'].items()) or 'none'} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
