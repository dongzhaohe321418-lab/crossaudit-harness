#!/usr/bin/env python3
"""L1/L2 agreement on the P3 adjudication sheet, written to a record.

`RESULTS-CLARIFY.md` quoted 84/91 and kappa = 0.852 from an ad hoc computation that no script
or record reproduced; two reviews recomputed it independently, but a number that enters the
paper has to be regenerable from the record. This is that script. Agreement is not accuracy,
and `L1` is the author.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHEET = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs/sheet"
OUT = HERE.parent / "records/clarify/agreement.json"


def load(name: str) -> dict[str, str]:
    with open(SHEET / name, newline="", encoding="utf-8") as f:
        return {r["id"]: r["label"].strip() for r in csv.DictReader(f)}


def main() -> int:
    l1, l2 = load("L1.csv"), load("L2.csv")
    if set(l1) != set(l2):
        print("item sets differ", sorted(set(l1) ^ set(l2)), file=sys.stderr)
        return 2
    ids = sorted(l1)
    n = len(ids)
    agree = sum(l1[i] == l2[i] for i in ids)
    c1, c2 = Counter(l1.values()), Counter(l2.values())
    pe = sum(c1[k] * c2[k] for k in set(c1) | set(c2)) / (n * n)
    po = agree / n
    kappa = (po - pe) / (1 - pe)
    rec = {
        "n_items": n,
        "n_agree": agree,
        "observed": po,
        "expected": pe,
        "cohen_kappa": kappa,
        "L1_counts": dict(c1),
        "L2_counts": dict(c2),
        "joint": {f"{a}|{b}": v for (a, b), v in sorted(Counter((l1[i], l2[i]) for i in ids).items())},
        "note": "agreement between the author (L1) and gpt-6-astra (L2); not accuracy",
    }
    OUT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{agree}/{n}  kappa={kappa:.8f}  -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
