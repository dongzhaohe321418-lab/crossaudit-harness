#!/usr/bin/env python3
"""A4S-3, post hoc: observation-level labels for every BLOCKER text on a clean item.

Written after the first cross-vendor review found the earlier item-level classification unreliable.
Every text gets one primary label, by precedence F > A > P > D > R:

  F  states a checkably false fact about the delivered files: the CSV absent, only inline, or not a
     file; a column, header quote or target values missing; a row or field count other than the
     file's (120 data rows, 9/5/6/12 fields); truncation or a missing final newline; values outside
     ranges the card does not state or that the data do not violate.
  A  a true observation of an anomaly in the data or the card's source-given values.
  P  a plausibility judgement about genuine source values (e.g. calling a low but real value
     implausible).
  D  a documentation or requirement judgement about the card or the deliverable's scope (empty range
     cells, missing descriptions or provenance, a sample rather than the full table, not committed).
  R  a text that names no defect or withdraws the one it raised.

Detectors propose F; the agent that ran the study (L1) read every text and the OVERRIDES below
record where reading changed a detector's answer. Output: records/ai4s/data_clean_flag_labels.json.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = Path.home() / "Documents/Crossaudit/ai4s/runs/data_audit"
MANIFEST = REPO / "benchmarks/code/records/ai4s/data_items.json"
OUT = REPO / "benchmarks/code/records/ai4s/data_clean_flag_labels.json"

DET = [
    ("F:column", r"missing (the )?('?Age|'?Concrete compressive|the target|its closing)|target (column|variable) is missing|(missing|lacks) (the )?target|missing the target|no value for the required target|every data row is missing"),
    ("F:absent", r"((data\.csv|CSV file|the file|CSV)[^.]{0,120}(not (present|included|shown|confirmed|materiali[sz]ed|established|exist)|absent|inline|as (plain |raw )?text|not as a|does not exist|embedded)|(no|without) (the )?(actual |corresponding |accompanying )?(data\.csv|CSV file)|(does not|doesn't) (include|show|contain) (this file|data\.csv|the (CSV|data) file)|(inline|as (plain |raw )?text)[^.]{0,80}(CSV|data\.csv)|no evidence[^.]{0,60}(file|data\.csv)|(filesystem|file system|directory structure|path structure)|missing from the increment|not present in the increment|file is missing)"),
    ("F:fields", r"\b(8|eight)\s+(columns|fields|values|comma|data columns|numeric)"),
    ("F:rowcount", r"(?<![\d,.])(?!(?:9|11|12|120|121)\b)(\d{1,3})\s+(\w+\s+)?(rows|records|observations|entries|samples)\b"),
    ("F:truncated", r"(truncat|abrupt|mid-record|newline|trailing comma|partial final row|last data row .{0,60}(incomplete|no value))"),
    ("F:range", r"(contains values outside|values? (fall|falls|lie|lies) (outside|below)|below the stated range minimum|outside these ranges)"),
    ("A:slag", r"\b0\.02\b"),
]
#: Where reading the whole text changed the detectors' answer. Key: item|draw|blocker-index.
OVERRIDES = {
    "concrete.clean.34|d3|b0": "F:rowcount",   # "121 data rows (rows 2-122 after the header)"
    "supercond.clean.8|d4|b0": "F:rowcount",   # "121 rows of data (plus header)"
    "supercond.clean.31|d4|b0": "F:rowcount",  # "121 data rows (plus header)"
    "supercond.clean.2|d3|b1": "F:range",      # deviation from stated ranges the card does not give
    "supercond.clean.7|d4|b1": "F:absent",     # the card "not presented as a separate file"
    "ccpp.clean.2|d1|b1": "A:card",            # the source's RH bound 100.16% exceeds 100%: true
    "concrete.clean.18|d4|b1": "P",            # genuine low strengths called implausible
    "supercond.clean.8|d1|b0": "R",            # "the CSV file is present ... confirms the file exists"
    "concrete.clean.5|d3|b0": "R",             # "No defect is found"
    "supercond.clean.2|d1|b0": "R",            # raises a path mismatch, then "appears correct"
    "supercond.clean.18|d2|b1": "R",           # empty ranges "consistent with the task"
    "ccpp.clean.34|d3|b1": "D",                # true: the sample's ranges differ from the source's
    "supercond.clean.5|d2|b1": "D",            # not committed to git: true
}


def main() -> int:
    man = {m["item"]: m for m in json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]}
    rows = []
    for d in range(1, 5):
        for line in (RUNS / f"self.d{d}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if man[r["instance_id"]]["fault"] is None and r["flagged"]:
                for j, t in enumerate(r["blocker_texts"]):
                    key = f"{r['instance_id']}|d{d}|b{j}"
                    tt = " ".join(t.split())
                    if key in OVERRIDES:
                        lab, how = OVERRIDES[key], "read"
                    else:
                        hit = next((name for name, p in DET if re.search(p, tt, re.I)), None)
                        lab, how = (hit or "D"), ("detector" if hit else "read")
                    rows.append({"key": key, "item": r["instance_id"], "label": lab, "how": how})
    order = {"F": 0, "A": 1, "P": 2, "D": 3, "R": 4}
    per_item: dict[str, set] = collections.defaultdict(set)
    for x in rows:
        per_item[x["item"]].add(x["label"].split(":")[0])
    item_cls = {i: min(s, key=order.get) for i, s in per_item.items()}
    out = {"texts": len(rows), "text_labels": collections.Counter(x["label"] for x in rows),
           "items": len(per_item), "item_primary": collections.Counter(item_cls.values()),
           "items_by_primary": {k: sorted(i for i, c in item_cls.items() if c == k) for k in order},
           "rows": rows}
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("texts", "text_labels", "items", "item_primary")}, indent=1))
    print("non-F items:", {k: v for k, v in out["items_by_primary"].items() if k != "F"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
