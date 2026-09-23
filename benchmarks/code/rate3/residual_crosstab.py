#!/usr/bin/env python3
"""The ceiling-1 residual re-rated by a model that audited nothing: L3 against study 21's pair.

R1-M3 (pre-submission): study 21's labels on the residual came from the author and
`gpt-6-astra`, and astra is one of the three families whose misses define the residual. P1's
L3 (`gpt-5.6-luna`, no audit role anywhere in the programme) rated all 121 sheet entries; its
disjoint missed group is exactly the residual (asserted below). This script cross-tabulates the
two, per instance. POST HOC, registered nowhere, and not reviewed: the instruments differ (a
three-option determinacy rubric showing at most three failing inputs, against study 21's
six-category rubric), so agreement here is between instruments as much as between raters.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "records"
OUT = R / "rate3/residual_crosstab.json"


def main() -> int:
    items = json.loads((R / "rate3/items.json").read_text(encoding="utf-8"))
    l3 = {r["rate_id"]: r["label"] for r in csv.DictReader((R / "rate3/L3.csv").open(encoding="utf-8"))}
    res = set(json.loads((R / "ceiling/numbers.json").read_text())["ceiling1"]["residual"]["all_families"]["instance_ids"])
    seen: dict[str, set] = {}
    for it in items:
        seen.setdefault(it["instance"], set()).add(it["arm"])
    both = {i for i, a in seen.items() if len(a) > 1}
    missed = {it["instance"]: l3[it["rate_id"]] for it in items
              if it["arm"] == "missed" and it["instance"] not in both}
    assert set(missed) == res, "L3's disjoint missed group is not the ceiling-1 residual"
    key = {}
    for f in ("key.jsonl", "key-flagged.jsonl"):
        for line in (R / "rerate" / f).read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            key[d["id"]] = d.get("instance") or d.get("instance_id")

    def lab(*fs):
        out = {}
        for f in fs:
            out.update({r["id"]: r["label"] for r in csv.DictReader((R / "rerate" / f).open(encoding="utf-8"))})
        return out
    a, b = lab("L1.csv", "L1-flagged.csv"), lab("L2.csv", "L2-flagged.csv")
    pair = {}
    for i, inst in key.items():
        if inst in res and i in a and i in b:
            pair[inst] = "ambiguous-oracle" if a[i] == b[i] == "ambiguous-oracle" else (
                "disputed" if a[i] != b[i] else a[i])
    assert set(pair) == res
    tab = Counter((pair[i], missed[i]) for i in sorted(res))
    rec = {
        "n": len(res),
        "L3_marginal": dict(Counter(missed.values())),
        "study21_pair_marginal": dict(Counter(pair.values())),
        "crosstab": {f"{p}|{q}": n for (p, q), n in sorted(tab.items())},
        "pair_undetermined_L3_agrees": tab[("ambiguous-oracle", "undetermined")],
        "pair_undetermined_total": sum(n for (p, _), n in tab.items() if p == "ambiguous-oracle"),
        "label": "POST HOC; not reviewed; different instruments",
    }
    OUT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(rec, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
