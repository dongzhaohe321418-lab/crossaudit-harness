#!/usr/bin/env python3
"""A4S-3, post hoc: one verified false statement per `self`-flagged clean item.

Replaces an earlier text-level labelling that review round 2 found inconsistent with its own
rubric. The claim this supports is item-level only: for each item below, one BLOCKER text (named by
item|draw|blocker-index) states something about the delivered files that the item refutes. The
agent that ran the study read every exemplar; the refuting fact for each kind is checked against
the item's own CSV here. Items flagged by `self` and absent from this list carry no such exemplar.
Output: records/ai4s/data_clean_flag_exemplars.json.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AI4S = Path.home() / "Documents/Crossaudit/ai4s"
RUNS, ITEMS = AI4S / "runs/data_audit", AI4S / "runs/data_items"
OUT = REPO / "benchmarks/code/records/ai4s/data_clean_flag_exemplars.json"

REFUTES = {
    "F:absent": "both files were supplied to the auditor as named files of the increment in every reading",
    "F:rowcount": "the file has 120 data rows and a header",
    "F:column": "every row has every column, the target included, and the quoted header parses",
    "F:fields": "every row parses to the header's field count",
    "F:truncated": "the file has 120 complete rows and ends with a newline",
}
#: item -> (exemplar key, kind). Each was read in full.
EXEMPLARS = {
    "ccpp.clean.15": ("ccpp.clean.15|d4|b0", "F:rowcount"),
    "ccpp.clean.16": ("ccpp.clean.16|d1|b0", "F:rowcount"),
    "ccpp.clean.18": ("ccpp.clean.18|d2|b0", "F:rowcount"),
    "ccpp.clean.2": ("ccpp.clean.2|d1|b0", "F:rowcount"),
    "ccpp.clean.26": ("ccpp.clean.26|d1|b0", "F:rowcount"),
    "ccpp.clean.33": ("ccpp.clean.33|d3|b0", "F:rowcount"),
    "ccpp.clean.34": ("ccpp.clean.34|d1|b0", "F:rowcount"),
    "concrete.clean.13": ("concrete.clean.13|d2|b0", "F:column"),
    "concrete.clean.14": ("concrete.clean.14|d4|b0", "F:column"),
    "concrete.clean.16": ("concrete.clean.16|d1|b0", "F:rowcount"),
    "concrete.clean.19": ("concrete.clean.19|d4|b0", "F:rowcount"),
    "concrete.clean.2": ("concrete.clean.2|d3|b0", "F:fields"),
    "concrete.clean.21": ("concrete.clean.21|d2|b1", "F:column"),
    "concrete.clean.22": ("concrete.clean.22|d3|b0", "F:rowcount"),
    "concrete.clean.23": ("concrete.clean.23|d3|b0", "F:column"),
    "concrete.clean.24": ("concrete.clean.24|d1|b0", "F:column"),
    "concrete.clean.25": ("concrete.clean.25|d2|b0", "F:column"),
    "concrete.clean.26": ("concrete.clean.26|d4|b0", "F:column"),
    "concrete.clean.27": ("concrete.clean.27|d2|b0", "F:column"),
    "concrete.clean.29": ("concrete.clean.29|d3|b0", "F:truncated"),
    "concrete.clean.31": ("concrete.clean.31|d1|b0", "F:rowcount"),
    "concrete.clean.32": ("concrete.clean.32|d2|b0", "F:rowcount"),
    "concrete.clean.33": ("concrete.clean.33|d3|b1", "F:rowcount"),
    "concrete.clean.34": ("concrete.clean.34|d2|b0", "F:rowcount"),
    "concrete.clean.4": ("concrete.clean.4|d1|b0", "F:fields"),
    "concrete.clean.6": ("concrete.clean.6|d4|b0", "F:rowcount"),
    "concrete.clean.8": ("concrete.clean.8|d3|b0", "F:column"),
    "concrete.clean.9": ("concrete.clean.9|d2|b0", "F:rowcount"),
    "supercond.clean.0": ("supercond.clean.0|d2|b0", "F:absent"),
    "supercond.clean.1": ("supercond.clean.1|d1|b0", "F:rowcount"),
    "supercond.clean.10": ("supercond.clean.10|d2|b0", "F:absent"),
    "supercond.clean.11": ("supercond.clean.11|d3|b0", "F:absent"),
    "supercond.clean.12": ("supercond.clean.12|d3|b0", "F:absent"),
    "supercond.clean.13": ("supercond.clean.13|d3|b0", "F:absent"),
    "supercond.clean.14": ("supercond.clean.14|d2|b0", "F:absent"),
    "supercond.clean.15": ("supercond.clean.15|d1|b0", "F:absent"),
    "supercond.clean.16": ("supercond.clean.16|d3|b0", "F:absent"),
    "supercond.clean.17": ("supercond.clean.17|d2|b0", "F:absent"),
    "supercond.clean.18": ("supercond.clean.18|d3|b0", "F:absent"),
    "supercond.clean.19": ("supercond.clean.19|d3|b0", "F:absent"),
    "supercond.clean.2": ("supercond.clean.2|d2|b0", "F:absent"),
    "supercond.clean.20": ("supercond.clean.20|d1|b0", "F:absent"),
    "supercond.clean.21": ("supercond.clean.21|d1|b0", "F:absent"),
    "supercond.clean.22": ("supercond.clean.22|d4|b0", "F:absent"),
    "supercond.clean.23": ("supercond.clean.23|d1|b0", "F:absent"),
    "supercond.clean.24": ("supercond.clean.24|d1|b0", "F:absent"),
    "supercond.clean.25": ("supercond.clean.25|d3|b0", "F:absent"),
    "supercond.clean.26": ("supercond.clean.26|d4|b0", "F:absent"),
    "supercond.clean.27": ("supercond.clean.27|d2|b0", "F:absent"),
    "supercond.clean.28": ("supercond.clean.28|d2|b0", "F:rowcount"),
    "supercond.clean.29": ("supercond.clean.29|d3|b0", "F:rowcount"),
    "supercond.clean.3": ("supercond.clean.3|d1|b0", "F:absent"),
    "supercond.clean.30": ("supercond.clean.30|d1|b0", "F:absent"),
    "supercond.clean.31": ("supercond.clean.31|d1|b0", "F:absent"),
    "supercond.clean.32": ("supercond.clean.32|d1|b0", "F:absent"),
    "supercond.clean.33": ("supercond.clean.33|d4|b0", "F:rowcount"),
    "supercond.clean.34": ("supercond.clean.34|d4|b0", "F:absent"),
    "supercond.clean.4": ("supercond.clean.4|d1|b0", "F:absent"),
    "supercond.clean.5": ("supercond.clean.5|d2|b0", "F:absent"),
    "supercond.clean.6": ("supercond.clean.6|d1|b0", "F:absent"),
    "supercond.clean.7": ("supercond.clean.7|d4|b0", "F:absent"),
    "supercond.clean.8": ("supercond.clean.8|d4|b0", "F:rowcount"),
}


def main() -> int:
    out = {}
    for item, (key, kind) in EXEMPLARS.items():
        _, d, b = key.split("|")
        rows = [json.loads(l) for l in (RUNS / f"self.{d}.jsonl").read_text().splitlines()]
        text = next(r for r in rows if r["instance_id"] == item)["blocker_texts"][int(b[1:])]
        raw = (ITEMS / item / "data.csv").read_text(encoding="utf-8")
        parsed = list(csv.reader(io.StringIO(raw)))
        width = len(parsed[0])
        check = {"data_rows": len(parsed) - 1, "all_rows_full": all(len(r) == width for r in parsed),
                 "final_newline": raw.endswith("\n")}
        assert check == {"data_rows": 120, "all_rows_full": True, "final_newline": True}, (item, check)
        out[item] = {"exemplar": key, "kind": kind, "text": " ".join(text.split()),
                     "refuted_by": REFUTES[kind], "file_check": check}
    OUT.write_text(json.dumps({"n_items": len(out), "items": out}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} items with a verified false statement about the files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
