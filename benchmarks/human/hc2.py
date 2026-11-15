"""Second-rater agreement for the human admissibility check (PREREGISTRATION-H1.md, Amendment 2). Reads both raters'
exported labels, the items and the key; reports agreement, the second rater's admissible share, and E6's estimands
on the units both raters accept (E9's subset function, E6's frozen analysis).

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/human/hc2.py labels_test.json labels_rater2_test.json [--out]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import h1                                          # noqa: E402  (wilson, kappa, paths)


def decode(path: str, items: dict, key: dict) -> dict:
    raw = json.loads(Path(path).read_text())
    raw = raw["labels"] if isinstance(raw, dict) and "labels" in raw else raw
    labels = {int(r["item"]): r for r in raw if r.get("r1") and r.get("r2")}
    missing = sorted(set(items) - set(labels))
    if missing:
        raise SystemExit(f"{path}: labels missing for items {missing}")
    out = {}
    for i, x in items.items():
        lab, pid = labels[i], x["problem_id"]
        ra, rb = (lab["r1"], lab["r2"]) if key[pid]["rule_1_is"] == "a" else (lab["r2"], lab["r1"])
        out[pid] = {"rule_a": ra, "rule_b": rb, "admissible": ra == "yes" and rb == "yes"}
    return out


def analyse(path1: str, path2: str, write: bool) -> dict:
    items = {x["item"]: x for x in json.loads((HERE / "admissibility_items_test.json").read_text())}
    key = json.loads((HERE / "admissibility_key_test.json").read_text())
    r1, r2 = decode(path1, items, key), decode(path2, items, key)
    pids = sorted(r1)
    a1, a2 = [int(r1[p]["admissible"]) for p in pids], [int(r2[p]["admissible"]) for p in pids]
    n, k2 = len(pids), sum(a2)
    no1 = {(p, r) for p in pids for r in ("rule_a", "rule_b") if r1[p][r] == "no"}
    no2 = {(p, r) for p in pids for r in ("rule_a", "rule_b") if r2[p][r] == "no"}
    res = {"n_units": n,
           "agreement": {"units_agree": sum(x == y for x, y in zip(a1, a2)), "kappa": h1.kappa(a1, a2),
                         "both_admissible": sum(x and y for x, y in zip(a1, a2)),
                         "rejections_rater1": len(no1), "rejections_rater2": len(no2), "rejections_shared": len(no1 & no2)},
           "rater2_admissible": {"k": k2, "share": 100 * k2 / n, "wilson95": h1.wilson(k2, n)},
           "rater2_rule_no": {"benchmark_rule": sum(r2[p]["rule_b"] == "no" for p in pids),
                              "alternative_rule": sum(r2[p]["rule_a"] == "no" for p in pids)}}
    sys.path[:0] = [str(HERE.parent / "e9"), str(HERE.parent / "code" / "icml")]
    import e9
    both = {p for p in pids if r1[p]["admissible"] and r2[p]["admissible"]}
    res["E6_on_units_both_accept"] = e9.subset_e6("test", both)
    res["per_unit"] = {p: {"rater1": r1[p], "rater2": r2[p]} for p in pids}
    if write:
        (HERE / "hc2_results_test.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    out = analyse(sys.argv[1], sys.argv[2], write="--out" in sys.argv)
    out.pop("per_unit")
    print(json.dumps(out, indent=1, default=str))
