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
    out = r3.paired_union_difference(a, b, len(a), ids, instances)
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
        out["H19d"] = h
    C3B.mkdir(parents=True, exist_ok=True)
    (C3B / "numbers.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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


if __name__ == "__main__":
    raise SystemExit(main())
