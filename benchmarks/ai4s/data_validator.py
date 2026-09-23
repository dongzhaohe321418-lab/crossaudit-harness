"""A4S-3 deterministic validator, frozen with the registration before any item is built.

Written from the data card alone: declared ranges where the source states them, non-negativity for
the quantities the spec lists, exact duplicate rows, sentinel values, and integer-valued columns the
card declares continuous. It flags an item if any check fires. It knows nothing about faults.
"""
from __future__ import annotations

import csv
import io

from data_spec import DATASETS, SENTINELS


def validate(name: str, csv_text: str) -> dict:
    spec = DATASETS[name]
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    fired: list[str] = []
    cols = spec["columns"]

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for c in cols:
        vals = [num(r.get(c)) for r in rows]
        vals = [v for v in vals if v is not None]
        if not vals:
            fired.append(f"missing:{c}")
            continue
        if any(v in SENTINELS for v in vals):
            fired.append(f"sentinel:{c}")
        if c in spec["nonneg"] and any(v < 0 for v in vals):
            fired.append(f"negative:{c}")
        lo_hi = spec["ranges"].get(c)
        if lo_hi and any(v < lo_hi[0] or v > lo_hi[1] for v in vals):
            fired.append(f"range:{c}")
        if c in spec["continuous"] and all(float(v).is_integer() for v in vals):
            fired.append(f"integer:{c}")
    keys = [tuple(r.get(c) for c in cols) for r in rows]
    if len(set(keys)) < len(keys):
        fired.append("duplicates")
    return {"flagged": bool(fired), "checks": fired}
