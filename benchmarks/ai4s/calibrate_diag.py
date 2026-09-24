"""A4S-4 step 0: the diagnosis rule applied to A4S-3's archived readings (development set).

No model call. Reports, by fault, how many faulty items each family and the validator diagnose
under the rule, beside A4S-3's post hoc fault-relevant counts, so the rule can be frozen with its
behaviour on data it was not tuned on stated in the registration.
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from diag_match import reading_diagnoses, validator_texts  # noqa: E402
RUNS = Path.home() / "Documents/Crossaudit/ai4s/runs/data_audit"
MAN = json.loads((HERE.parents[1] / "benchmarks/code/records/ai4s/data_items.json").read_text())
items = {i["item"]: i for i in MAN["items"]}
out = {}
for fam in ("cross", "self"):
    diag = defaultdict(bool); flag = defaultdict(bool)
    for d in range(1, 5):
        for line in (RUNS / f"{fam}.d{d}.jsonl").read_text().splitlines():
            r = json.loads(line); it = items[r["instance_id"]]
            flag[r["instance_id"]] |= bool(r["flagged"])
            if it["fault"]:
                diag[r["instance_id"]] |= reading_diagnoses(it["dataset"], it["fault"], it["params"], r["blocker_texts"])
    by = Counter(items[i]["fault"] for i, v in diag.items() if v)
    out[fam] = {"diagnosed": sum(diag.values()), "by_fault": dict(sorted(by.items())),
                "flagged_faulty": sum(v for i, v in flag.items() if items[i]["fault"]),
                "items": sorted(i for i, v in diag.items() if v)}
vd = {i: reading_diagnoses(it["dataset"], it["fault"], it["params"], validator_texts(it["validator"]["checks"]))
      for i, it in items.items() if it["fault"]}
out["validator"] = {"diagnosed": sum(vd.values()),
                    "by_fault": dict(sorted(Counter(items[i]["fault"] for i, v in vd.items() if v).items())),
                    "flagged_faulty": sum(items[i]["validator"]["flagged"] for i in vd)}
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "items"} for k, v in out.items()}, indent=1))
json.dump(out, open(sys.argv[1], "w"), indent=1) if len(sys.argv) > 1 else None
