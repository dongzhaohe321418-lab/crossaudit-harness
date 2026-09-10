"""Study 17 — EXPLORATORY, post hoc, not preregistered: where the kept wrong tests sit.

Reads ``records/testgen-val/rows.jsonl`` (indices and counts, no test text) and reports,
per rule, where the kept wrong applications sit, how many of them are corroborated only
by tests that themselves fail the canonical solution, and the rules' behaviour on the P
and C candidates alone — the strata the product meets, since an F candidate fails the
visible suite and makes corroboration trivial.

Every quantity here is post hoc and is labelled exploratory in RESULTS-TESTGEN-VAL.md.
The intervals use the study's own machinery — Wilson, and the problem-cluster percentile
bootstrap at the preregistered seed and replicate count — so an exploratory rate is
quoted with an interval like every other rate in the project (EXPERIMENT_RECORD §9).
The figures are written to ``records/testgen-val/exploratory.json`` so the results file
can be bound to them by test.

    python benchmarks/code/testgen/exploratory_val.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import testgen  # noqa: E402
import testgen_val as tv  # noqa: E402

OUT = tv.RECORDS / "exploratory.json"


def _fmt(block: dict) -> str:
    if block["rate"] is None:
        return f"{block['k']}/{block['n']}"
    lo, hi = block["wilson"]
    blo, bhi = block["bootstrap_problem_cluster"]
    return (f"{block['k']}/{block['n']} = {100 * block['rate']:.1f}% "
            f"(Wilson {100 * lo:.1f}–{100 * hi:.1f}%; bootstrap "
            + (f"{100 * blo:.1f}–{100 * bhi:.1f}%)" if blo is not None else "n/a)"))


def main() -> int:
    rows = [r for r in tv.load_rows().values() if not r["artefact"] and r["classifiable"]]
    out: dict = {"note": "post hoc, not preregistered; intervals as in the primary "
                         f"(Wilson; problem-cluster bootstrap, seed {tv.BOOTSTRAP_SEED}, "
                         f"{tv.BOOTSTRAP_REPS} resamples)",
                 "rules": {}}
    for rule in tv.RULES:
        by_stratum: dict[str, int] = {}
        instances = 0
        # per kept wrong application: 1 if every draw-2/draw-3 test failing on that
        # candidate also fails the canonical solution
        only_wrong: dict[str, list[float]] = {}
        # P and C candidates only: wrong among kept
        pc_wrong: dict[str, list[float]] = {}
        for r in rows:
            pid = r["problem_id"]
            wrong1 = set(r["d1"]["failed_canonical"])
            kept = set(r["kept"][rule])
            if r["stratum"] != "F":
                for t in kept:
                    pc_wrong.setdefault(pid, []).append(1.0 if t in wrong1 else 0.0)
            kw = kept & wrong1
            if not kw:
                continue
            instances += 1
            key = f"{r['half']}-{r['stratum']}"
            by_stratum[key] = by_stratum.get(key, 0) + len(kw)
            if rule in ("A", "B"):
                exclusively_wrong = all(
                    not (set(r[f"d{k}"]["failed_candidate"]) - set(r[f"d{k}"]["failed_canonical"]))
                    for k in tv.DRAWS)
                only_wrong.setdefault(pid, []).extend([1.0 if exclusively_wrong else 0.0] * len(kw))
        entry = {"kept_wrong_applications": sum(by_stratum.values()), "on_instances": instances,
                 "by_half_stratum": dict(sorted(by_stratum.items())),
                 "wrong_among_kept_P_and_C": tv.rate_block(pc_wrong)}
        if rule in ("A", "B"):
            entry["corroborated_only_by_wrong_tests"] = tv.rate_block(only_wrong)
        out["rules"][rule] = entry
        print(f"{rule}: kept wrong applications {entry['kept_wrong_applications']} on "
              f"{instances} instances; by half-stratum {entry['by_half_stratum']}")
        print(f"{rule}: P and C rows only — wrong among kept {_fmt(entry['wrong_among_kept_P_and_C'])}")
        if rule in ("A", "B"):
            print(f"{rule}: of the kept wrong applications, corroborated ONLY by tests that "
                  f"themselves fail the canonical solution: {_fmt(entry['corroborated_only_by_wrong_tests'])}")

    b_minus_a = {k: out["rules"]["B"]["by_half_stratum"].get(k, 0) - v
                 for k, v in ({**{k: 0 for k in out["rules"]["B"]["by_half_stratum"]},
                               **out["rules"]["A"]["by_half_stratum"]}).items()}
    out["B_minus_A_by_half_stratum"] = {k: v for k, v in sorted(b_minus_a.items()) if v}
    print(f"B over A, by half-stratum: {out['B_minus_A_by_half_stratum']}")

    fps = [r for r in rows if r["half"] == "confirm" and r["stratum"] == "C" and r["d1"]["failed_candidate"]]
    out["confirm_C_false_positives"] = {
        r["instance_id"]: {rule: bool(r["kept"][rule]) for rule in tv.RULES} for r in fps}
    for iid, kept in out["confirm_C_false_positives"].items():
        print(f"confirm-C false positive {iid}: kept under "
              + ", ".join(f"{rule}={'yes' if v else 'no'}" for rule, v in kept.items()))

    seven = tv.validated_only(testgen.load_rows())
    out["validated_only"] = {}
    for r in rows:
        if r["instance_id"] in seven:
            out["validated_only"][r["instance_id"]] = {
                "d2_failing": len(r["d2"]["failed_candidate"]), "d3_failing": len(r["d3"]["failed_candidate"]),
                **{rule: ("kept" if r["kept"][rule] else "dropped") for rule in tv.RULES}}
    for iid, v in out["validated_only"].items():
        print(f"validated-only {iid}: draw-2 failing {v['d2_failing']}, draw-3 failing {v['d3_failing']}; "
              + ", ".join(f"{rule}={v[rule]}" for rule in tv.RULES))

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
