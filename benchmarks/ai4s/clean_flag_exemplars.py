#!/usr/bin/env python3
"""A4S-3, post hoc: the `self`-flagged clean items, sorted by what their findings claim.

Item-level only; review rounds 2-4 showed that text-level totals and a single "false statement"
bucket were not supportable. Every flagged clean item falls in exactly one group:

  refuted    at least one unwithdrawn BLOCKER text states a row count, a field count, a named missing
             column or target, or a truncation that the item's own CSV contradicts. One exemplar per
             item is named and checked against the file here. This count is a lower bound.
  dispute    the findings contest that the CSV was delivered as a file (the harness passes named file
             contents in memory and writes nothing to disk, so this is a protocol dispute, not a
             refuted fact); no refutable exemplar was found.
  withdrawn  the one refutable allegation is withdrawn in the same text (in `concrete.clean.24` only in
             part: its surviving claim that the columns do not match the card is not checked here).
  documentation  only documentation or requirement judgements (one also a plausibility judgement).

The agent that ran the study read every exemplar. A negative control shows each file check can fail.
Output: records/ai4s/data_clean_flag_exemplars.json.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AI4S = Path.home() / "Documents/Crossaudit/ai4s"
RUNS, ITEMS = AI4S / "runs/data_audit", AI4S / "runs/data_items"
OUT = REPO / "benchmarks/code/records/ai4s/data_clean_flag_exemplars.json"
TARGET = "Concrete compressive strength(MPa, megapascals)"
AGE = "Age (day)"

#: refuted: item -> (exemplar key, kind). Each was read in full.
REFUTED = {
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
    "concrete.clean.9": ("concrete.clean.9|d2|b0", "F:rowcount"),
    "supercond.clean.1": ("supercond.clean.1|d1|b0", "F:rowcount"),
    "supercond.clean.11": ("supercond.clean.11|d1|b0", "F:rowcount"),
    "supercond.clean.12": ("supercond.clean.12|d1|b0", "F:rowcount"),
    "supercond.clean.13": ("supercond.clean.13|d1|b0", "F:rowcount"),
    "supercond.clean.14": ("supercond.clean.14|d4|b0", "F:rowcount"),
    "supercond.clean.16": ("supercond.clean.16|d1|b0", "F:rowcount"),
    "supercond.clean.17": ("supercond.clean.17|d1|b0", "F:rowcount"),
    "supercond.clean.18": ("supercond.clean.18|d3|b1", "F:rowcount"),
    "supercond.clean.19": ("supercond.clean.19|d2|b0", "F:rowcount"),
    "supercond.clean.24": ("supercond.clean.24|d3|b0", "F:rowcount"),
    "supercond.clean.25": ("supercond.clean.25|d1|b0", "F:rowcount"),
    "supercond.clean.26": ("supercond.clean.26|d1|b0", "F:rowcount"),
    "supercond.clean.28": ("supercond.clean.28|d2|b0", "F:rowcount"),
    "supercond.clean.29": ("supercond.clean.29|d3|b0", "F:rowcount"),
    "supercond.clean.3": ("supercond.clean.3|d3|b0", "F:rowcount"),
    "supercond.clean.30": ("supercond.clean.30|d2|b0", "F:rowcount"),
    "supercond.clean.31": ("supercond.clean.31|d4|b0", "F:rowcount"),
    "supercond.clean.33": ("supercond.clean.33|d4|b0", "F:rowcount"),
    "supercond.clean.4": ("supercond.clean.4|d4|b0", "F:rowcount"),
    "supercond.clean.5": ("supercond.clean.5|d2|b1", "F:rowcount"),
    "supercond.clean.6": ("supercond.clean.6|d3|b0", "F:rowcount"),
    "supercond.clean.8": ("supercond.clean.8|d4|b0", "F:rowcount"),
}
DISPUTE = ["supercond.clean.0", "supercond.clean.10", "supercond.clean.15", "supercond.clean.2", "supercond.clean.20", "supercond.clean.21", "supercond.clean.22", "supercond.clean.23", "supercond.clean.27", "supercond.clean.32", "supercond.clean.34", "supercond.clean.7"]
WITHDRAWN = ["concrete.clean.8", "concrete.clean.24"]
DOCUMENTATION = ["concrete.clean.5", "concrete.clean.7", "concrete.clean.18", "concrete.clean.28",
                 "concrete.clean.30"]


def check(kind: str, text: str, raw: str) -> dict:
    """The file fact that contradicts the exemplar; raises AssertionError if the file does not."""
    parsed = list(csv.reader(io.StringIO(raw)))
    header, rows = parsed[0], parsed[1:]
    flat = " ".join(text.split())
    if kind == "F:rowcount":
        claimed = [int(m.group(1)) for m in re.finditer(
            r"(?<![\d,.])(\d{1,3})\s+(?:\w+\s+)?(?:rows|records|observations|entries|samples)\b", flat)]
        wrong = [c for c in claimed if c not in (9, 11, 12, 120)]
        assert wrong and len(rows) == 120, (claimed, len(rows))
        return {"claimed": wrong, "actual_data_rows": len(rows)}
    if kind == "F:fields":
        assert re.search(r"\b(8|eight)\s+(columns|fields|values|comma)", flat)
        assert all(len(r) == 9 for r in parsed), "a row does not have 9 fields"
        return {"claimed_fields": 8, "actual_fields": 9}
    if kind == "F:column":
        named = []
        if re.search(r"Age", flat):
            named.append(AGE)
        if re.search(r"(compressive|target)", flat, re.I):
            named.append(TARGET)
        assert named, "no column named"
        for col in named:
            assert col in header, f"{col} not in header"
            j = header.index(col)
            assert all(r[j] != "" for r in rows), f"{col} has an empty value"
        if re.search(r"closing (double-)?quote", flat):
            assert header[-1] == TARGET and raw.splitlines()[0].endswith('"')
        return {"named": named, "present_and_populated": True}
    if kind == "F:truncated":
        assert raw.endswith("\n") and all(len(r) == len(header) for r in parsed) and len(rows) == 120
        return {"final_newline": True, "complete_rows": 120}
    raise ValueError(kind)


def negative_control() -> None:
    """Each check must fail on a file that does what the exemplar says."""
    raw = (ITEMS / "concrete.clean.13" / "data.csv").read_text(encoding="utf-8")
    broken = {
        "F:column": (raw.replace(AGE, "UNRELATED_COLUMN", 1), "the CSV is missing the 'Age (day)' column"),
        "F:rowcount": ("\n".join(raw.splitlines()[:101]) + "\n", "only 100 rows of data"),
        "F:fields": (raw.replace(",28.0,", ",", 1), "only 8 values per row"),
        "F:truncated": (raw.rstrip("\n"), "ends abruptly"),
    }
    for kind, (bad, text) in broken.items():
        try:
            check(kind, text, bad)
        except AssertionError:
            continue
        raise SystemExit(f"negative control failed: the {kind} check passed a file that matches the claim")


def main() -> int:
    negative_control()
    out = {}
    for item, (key, kind) in REFUTED.items():
        _, d, b = key.split("|")
        rows = [json.loads(l) for l in (RUNS / f"self.{d}.jsonl").read_text().splitlines()]
        text = next(r for r in rows if r["instance_id"] == item)["blocker_texts"][int(b[1:])]
        raw = (ITEMS / item / "data.csv").read_text(encoding="utf-8")
        out[item] = {"exemplar": key, "kind": kind, "text": " ".join(text.split()),
                     "file_fact": check(kind, text, raw)}
    groups = {"refuted": sorted(out), "dispute": DISPUTE, "withdrawn": WITHDRAWN,
               "documentation": DOCUMENTATION}
    allitems = [i for g in groups.values() for i in g]
    assert len(allitems) == len(set(allitems)) == 67, len(allitems)
    OUT.write_text(json.dumps({"counts": {k: len(v) for k, v in groups.items()}, "groups": groups,
                               "refuted": out}, indent=1) + "\n", encoding="utf-8")
    print({k: len(v) for k, v in groups.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
