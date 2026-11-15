"""H1: the human admissibility check (PREREGISTRATION-H1.md). Reads the rater's labels (exported from the labelling
page's `labels` collection), the item file and the key, and reports the registered quantities. E6's estimands on the
human-admissible subset come from E9's subset function (E6's frozen analysis on a subset).

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/human/h1.py labels_test.json [--out]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "e9"), str(HERE.parent / "code" / "icml")]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (100 * (centre - half), 100 * (centre + half))


def kappa(a: list, b: list) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def analyse(labels_path: str, write: bool) -> dict:
    items = {x["item"]: x for x in json.loads((HERE / "admissibility_items_test.json").read_text())}
    key = json.loads((HERE / "admissibility_key_test.json").read_text())
    raw = json.loads(Path(labels_path).read_text())
    if isinstance(raw, dict) and "labels" in raw:              # the review pack's export format
        raw = raw["labels"]
    labels = {int(r["item"]): r for r in (raw if isinstance(raw, list) else raw.values())
              if r.get("r1") and r.get("r2")}
    missing = sorted(set(items) - set(labels))
    if missing:
        raise SystemExit(f"labels missing for items {missing}")
    per_unit, bench_no, alt_no = {}, 0, 0
    for i, x in items.items():
        lab, pid = labels[i], x["problem_id"]
        first_is_a = key[pid]["rule_1_is"] == "a"
        ra, rb = (lab["r1"], lab["r2"]) if first_is_a else (lab["r2"], lab["r1"])
        per_unit[pid] = {"rule_a": ra, "rule_b": rb, "admissible": ra == "yes" and rb == "yes",
                         "reason": lab.get("reason", "")}
        bench_no += rb == "no"
        alt_no += ra == "no"
    n = len(per_unit)
    k = sum(v["admissible"] for v in per_unit.values())
    res = {"n_units": n, "H1_1_admissible": {"k": k, "share": 100 * k / n, "wilson95": wilson(k, n)},
           "rule_no": {"benchmark_rule": bench_no, "alternative_rule": alt_no},
           "answers": {r: {v: sum(u[r] == v for u in per_unit.values()) for v in ("yes", "no", "unsure")}
                       for r in ("rule_a", "rule_b")}}
    e9 = json.loads((HERE.parent / "e9" / "records" / "e9_results_test.json").read_text())
    acc = e9["open_unit_acceptance"]
    pids = sorted(per_unit)
    human = [int(per_unit[p]["admissible"]) for p in pids]
    judges = [int(acc.get(p, 0) >= 3) for p in pids]
    res["agreement_with_E9_majority"] = {"agree": sum(h == j for h, j in zip(human, judges)), "n": n,
                                         "kappa": kappa(human, judges)}
    import e9
    subset = {p for p in pids if per_unit[p]["admissible"]}
    res["H1_2_E6_on_admissible_subset"] = e9.subset_e6("test", subset)
    sub = res["H1_2_E6_on_admissible_subset"]
    if sub.get("estimable"):
        lo = lambda name: (sub.get(name) or {}).get("lo")
        res["verdicts"] = {"E6_5_holds": bool((lo("E6_5_cov_sentence_minus_none") or -1) > 0),
                           "E6_2_holds": bool((lo("E6_2_convention_advantage_none") or -1) > 0)}
    res["per_unit"] = per_unit
    if write:
        (HERE / "h1_results_test.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    r = analyse(sys.argv[1], write="--out" in sys.argv)
    r.pop("per_unit")
    print(json.dumps(r, indent=1, default=str))
