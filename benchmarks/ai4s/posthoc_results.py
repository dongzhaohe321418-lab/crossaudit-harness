#!/usr/bin/env python3
"""A4S-2 post hoc analyses, added after reading every LLM flag on a clean item. None is registered.

1. Clean-item flags, read one by one (labels below, one per flagged clean item).
2. Construction defects found by that reading: (a) instances whose test case passes its inputs as
   literals in the call, so `work/inputs.py` is empty and the report's sentence "on the inputs in
   work/inputs.py" is false; (b) instances whose true output is so near zero that `np.allclose`'s
   default absolute tolerance (1e-8) absorbs the injected fault, contrary to the registration's
   premise that a 5% error lies beyond those defaults.
3. Sensitivity: the registered outcomes recomputed without the instances in 2(a), 2(b), and both.
4. Exact McNemar p values to full precision (the registered script rounds to 4 places).
Input: the registered analysis output. Output: records/ai4s/results_posthoc.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "benchmarks/code"))
import report_ceiling as rc  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
ITEMS = AI4S / "runs/results_items"
RUNS = AI4S / "runs/results_audit"
MANIFEST = REPO / "benchmarks/code/records/ai4s/results_items.json"
REEXEC = REPO / "benchmarks/code/records/ai4s/results_reexec.json"
OUT = REPO / "benchmarks/code/records/ai4s/results_posthoc.json"
FAULTS = ["R1", "R2", "R3", "R4", "R5", "F1", "F4"]

#: Every clean item with an LLM flag, labelled after reading all its BLOCKER texts.
CLEAN_FLAG_LABELS = {
    "27.1.s2.clean": "correct: provenance (inputs are call literals; inputs.py empty)",
    "34.1.s2.clean": "correct: provenance (inputs are call literals; inputs.py empty)",
    "35.1.s1.clean": "correct: provenance, and unit (solution documents nm, report says dimensionless)",
    "42.2.s1.clean": "correct: provenance (inputs are call literals; inputs.py empty)",
    "42.2.s3.clean": "correct: provenance (inputs are call literals; inputs.py empty)",
    "57.4.s1.clean": "correct: provenance (inputs are call literals; inputs.py empty)",
    "57.4.s2.clean": "correct: provenance (inputs are call literals; inputs.py empty)",
    "77.8.s3.clean": "correct: unit (solution documents zeptojoules, report says dimensionless)",
    "25.1.s2.clean": "wrong: hand-computed value (0.018) disagrees with the executed output",
    "32.1.s1.clean": "wrong: hand-computed value off by 10^12 from the executed output",
    "61.2.s1.clean": "wrong: claims the output ignores p_s; the executed output is the report's",
    "72.7.s1.clean": "wrong: claims a syntax error in a line whose trailing text is a comment",
}


def main() -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["instances"]
    empty = sorted(i["instance"] for i in man
                   if not (ITEMS / f"{i['instance']}.clean/work/inputs.py").read_text().strip())
    rx = {r["item"]: r["flagged"] for r in json.loads(REEXEC.read_text(encoding="utf-8"))}
    rx_missed = sorted(k.rsplit(".", 1)[0] for k, v in rx.items() if k.endswith(".faulty") and not v)
    llm: dict[str, bool] = {}
    for d in range(1, 5):
        for line in (RUNS / f"cross.d{d}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            llm[r["instance_id"]] = llm.get(r["instance_id"], False) or r["flagged"]
    fault = {i["instance"]: i["fault"] for i in man}

    def outcomes(exclude: set[str]) -> dict:
        keep = [i["instance"] for i in man if i["instance"] not in exclude]
        res = {"instances": len(keep)}
        for name, v in (("llm_k4", llm), ("reexec", rx)):
            res[name] = {
                "recall": f"{sum(v[f'{i}.faulty'] for i in keep)}/{len(keep)}",
                "clean_fp": f"{sum(v[f'{i}.clean'] for i in keep)}/{len(keep)}",
                "by_fault": {f: f"{sum(v[f'{i}.faulty'] for i in keep if fault[i] == f)}/"
                                f"{sum(1 for i in keep if fault[i] == f)}" for f in FAULTS}}
        return res

    pairs = {}
    for a, b, va, vb in (("llm_k4", "dcl", llm, None), ("llm_k4", "reexec", llm, rx)):
        if vb is None:
            dcl = {}
            for d in range(1, 2):
                for line in (RUNS / f"cross.d{d}.jsonl").read_text(encoding="utf-8").splitlines():
                    r = json.loads(line)
                    dcl[r["instance_id"]] = r["dcl_hard_failures"] > 0
            vb = dcl
        only_a = sum(1 for i in man if va[f"{i['instance']}.faulty"] and not vb[f"{i['instance']}.faulty"])
        only_b = sum(1 for i in man if vb[f"{i['instance']}.faulty"] and not va[f"{i['instance']}.faulty"])
        pairs[f"{a}_vs_{b}"] = {"only_first": only_a, "only_second": only_b,
                                "p_exact": rc.mcnemar_exact(only_a, only_b)}
    within = {}
    for name, v in (("llm_k4", llm), ("reexec", rx)):
        b_ = sum(1 for i in man if v[f"{i['instance']}.faulty"] and not v[f"{i['instance']}.clean"])
        c_ = sum(1 for i in man if v[f"{i['instance']}.clean"] and not v[f"{i['instance']}.faulty"])
        within[name] = {"faulty_only": b_, "clean_only": c_, "p_exact": rc.mcnemar_exact(b_, c_)}
    labelled = sorted(CLEAN_FLAG_LABELS)
    flagged_clean = sorted(k for k, v in llm.items() if k.endswith(".clean") and v)
    assert labelled == flagged_clean, (labelled, flagged_clean)
    out = {"clean_flag_labels": CLEAN_FLAG_LABELS,
           "clean_flags_correct": sum(v.startswith("correct") for v in CLEAN_FLAG_LABELS.values()),
           "clean_flags_wrong": sum(v.startswith("wrong") for v in CLEAN_FLAG_LABELS.values()),
           "empty_inputs_instances": empty,
           "reexec_missed_faulty_instances": rx_missed,
           "reexec_missed_true_values": {i: next(m["true_values"] for m in man if m["instance"] == i)
                                         for i in rx_missed},
           "sensitivity": {"registered": outcomes(set()),
                           "without_empty_inputs": outcomes(set(empty)),
                           "without_reexec_tolerance_cases": outcomes(set(rx_missed)),
                           "without_both": outcomes(set(empty) | set(rx_missed))},
           "mcnemar_exact_full_precision": pairs, "within_instance_full_precision": within}
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "clean_flag_labels"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
