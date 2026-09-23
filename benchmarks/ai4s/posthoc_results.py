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
5. Fabrication rationale (added after review round 1): of the fabricated items the LLM flags, those
   whose every flagging finding rests on an incorrect calculation of the output, read one by one.
6. The unit defect: instances whose solution documents a unit for the output, which every report
   labels `dimensionless`, and whether the LLM flagged the clean item.
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


#: Fabricated items flagged only by findings whose own calculation of the output is wrong.
FABRICATION_UNSOUND = {
    "32.1.s3": "claims the output should be about -1.36e6; the executed output is -1.36e-6",
    "70.5.s1": "claims the tensor terms cancel to zero; they sum to -1.616e-7",
}
#: Solutions whose docstring gives the output a unit (read one by one).
UNIT_DOCUMENTED = {"35.1.s1": "nm", "61.2.s1": "inverse angstrom", "77.8.s2": "zeptojoules",
                   "77.8.s3": "zeptojoules"}


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

    pairs, clustered = {}, {}
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
        signed: dict[str, list[int]] = {}
        for i in man:
            k = f"{i['instance']}.faulty"
            signed.setdefault(i["instance"].split(".")[0], []).append(int(bool(va[k])) - int(bool(vb[k])))
        clustered[f"{a}_vs_{b}"] = rc.signflip_p(signed)
    within = {}
    for name, v in (("llm_k4", llm), ("reexec", rx)):
        b_ = sum(1 for i in man if v[f"{i['instance']}.faulty"] and not v[f"{i['instance']}.clean"])
        c_ = sum(1 for i in man if v[f"{i['instance']}.clean"] and not v[f"{i['instance']}.faulty"])
        within[name] = {"faulty_only": b_, "clean_only": c_, "p_exact": rc.mcnemar_exact(b_, c_)}
    labelled = sorted(CLEAN_FLAG_LABELS)
    flagged_clean = sorted(k for k, v in llm.items() if k.endswith(".clean") and v)
    assert labelled == flagged_clean, (labelled, flagged_clean)
    fab = [i["instance"] for i in man if i["fault"] in ("F1", "F4")]
    fab_flagged = [i for i in fab if llm[f"{i}.faulty"]]
    fab_sound = [i for i in fab_flagged if i not in FABRICATION_UNSOUND]
    assert set(FABRICATION_UNSOUND) <= set(fab_flagged)
    union_sound = sum(1 for i in man if (llm[f"{i['instance']}.faulty"] and i["instance"] not in FABRICATION_UNSOUND)
                      or rx[f"{i['instance']}.faulty"])
    out = {"fabrication": {"items": len(fab), "flagged_any_blocker": len(fab_flagged),
                           "flagged_with_sound_rationale": len(fab_sound),
                           "unsound": FABRICATION_UNSOUND},
           "llm_or_reexec_with_sound_llm_rationale": f"{union_sound}/{len(man)}",
           "unit_documented": {i: {"unit": u, "clean_flagged": llm[f"{i}.clean"]}
                               for i, u in UNIT_DOCUMENTED.items()},
           "clean_flag_labels": CLEAN_FLAG_LABELS,
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
           "mcnemar_exact_full_precision": pairs,
           "signflip_by_problem_sensitivity": clustered, "within_instance_full_precision": within}
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "clean_flag_labels"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
