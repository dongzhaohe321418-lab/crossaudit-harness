#!/usr/bin/env python3
"""A4S-3 post hoc analyses added after the first cross-vendor review. None is registered.

1. Fault-relevant flags (`cross`): an item counts only if at least one flagging BLOCKER is not the
   airfoil card-description complaint (the one documentation-only BLOCKER `cross` raised).
2. Validator sensitivity: the concrete source README states Age 1~365 days, which the frozen spec
   omitted; the validator is rerun with that one range added.
3. Floating-point tails: cells with 14 or more decimals, by dataset and fault.
Output: records/ai4s/data_posthoc.json.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import data_spec  # noqa: E402
from data_validator import validate  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
RUNS, ITEMS = AI4S / "runs/data_audit", AI4S / "runs/data_items"
MANIFEST = REPO / "benchmarks/code/records/ai4s/data_items.json"
OUT = REPO / "benchmarks/code/records/ai4s/data_posthoc.json"
DOC = re.compile(r"(card (supplies|lists|provides) column (identifiers|names)|no (definitions|descriptions)"
                 r"|does not define|identifiers and units only)", re.I)
FAULTS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]


def main() -> int:
    man = {m["item"]: m for m in json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]}
    texts = collections.defaultdict(list)
    for d in range(1, 5):
        for line in (RUNS / f"cross.d{d}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["flagged"]:
                texts[r["instance_id"]] += r["blocker_texts"]
    flagged = set(texts)
    relevant = {i for i, t in texts.items() if not all(DOC.search(x) for x in t)}
    doc_only = sorted(flagged - relevant)
    val = {i: m["validator"]["flagged"] for i, m in man.items()}
    data_spec.DATASETS["concrete"]["ranges"] = {data_spec.CONC[7]: (1, 365)}
    val_age = {i: validate(m["dataset"], (ITEMS / i / "data.csv").read_text(encoding="utf-8"))["flagged"]
               for i, m in man.items()}
    faulty = [i for i, m in man.items() if m["fault"]]
    clean = [i for i, m in man.items() if not m["fault"]]

    def tab(s: set | dict) -> dict:
        f = (lambda i: bool(s.get(i))) if isinstance(s, dict) else (lambda i: i in s)
        return {"faulty": sum(f(i) for i in faulty), "clean": sum(f(i) for i in clean),
                "by_fault": {x: sum(f(i) for i in faulty if man[i]["fault"] == x) for x in FAULTS}}

    llm_only_rel = sorted(i for i in faulty if i in relevant and not val[i])
    llm_only_rel_age = sorted(i for i in faulty if i in relevant and not val_age[i])
    union_rel = {i for i in man if i in relevant or val[i]}
    tails = collections.Counter()
    for i, m in man.items():
        n = len(re.findall(r"\d+\.\d{14,}", (ITEMS / i / "data.csv").read_text(encoding="utf-8")))
        tails[f"{m['dataset']}:{m['fault'] or 'clean'}"] += bool(n)
    out = {"cross_doc_only_items": doc_only,
           "cross_fault_relevant": tab(relevant),
           "cross_fault_relevant_union_with_validator": tab(union_rel),
           "llm_only_fault_relevant": llm_only_rel,
           "validator_with_age_range": tab(val_age),
           "validator_with_age_range_new_catches": sorted(i for i in man if val_age[i] and not val[i]),
           "llm_only_fault_relevant_vs_age_validator": llm_only_rel_age,
           "items_with_14plus_decimal_cells": dict(sorted(tails.items()))}
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "items_with_14plus_decimal_cells"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
