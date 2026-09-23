#!/usr/bin/env python3
"""A4S-3 items: 140 clean and 140 faulty 120-row samples, exactly as registered.

Items are written to `~/Documents/Crossaudit/ai4s/runs/data_items/<item>/` (data.csv, CARD.md);
the manifest, with every fault's column, rows and parameters and each file's hash, goes to
`records/ai4s/data_items.json`. Seed 20260926, derived per item so any item rebuilds alone.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from data_spec import DATASETS, FAULTS, card  # noqa: E402
from data_validator import validate  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
OUT = AI4S / "runs/data_items"
MANIFEST = HERE.parents[1] / "benchmarks/code/records/ai4s/data_items.json"
SEED = 20260926
N_ROWS = 120
CLEAN_PER = 35
SEEDS_PER_FAULT = 5


def pool(name: str) -> pd.DataFrame:
    raw = pd.read_csv(AI4S / f"data/uci/{name}.csv")
    raw.columns = [c.strip() for c in raw.columns]   # Amendment 1: one name in CSV and card
    d = raw[DATASETS[name]["columns"]]
    d = d.drop_duplicates()
    # Every column as float for every item, clean and faulty alike: casting only a faulted column
    # would print it as 800.0 where clean items print 800, a formatting tell that leaks the fault.
    d = d.astype(float)
    if name == "ccpp":
        d = d[d["RH"] <= 100]
    return d.reset_index(drop=True)


def inject(name: str, df: pd.DataFrame, fault: str, rng: random.Random) -> dict:
    spec = DATASETS[name]
    n = len(df)
    if fault == "F1":
        col, fac, off, to = rng.choice(spec["unit_mix"])
        rows = sorted(rng.sample(range(n), int(0.2 * n)))
        df.loc[rows, col] = df.loc[rows, col] * fac + off
        return {"column": col, "rows": rows, "to_unit": to, "factor": fac, "offset": off}
    if fault == "F2":
        col = rng.choice(spec["nonneg"])
        cand = [i for i in range(n) if df.at[i, col] > 0]
        rows = sorted(rng.sample(cand, 3))
        df.loc[rows, col] = -df.loc[rows, col]
        return {"column": col, "rows": rows}
    if fault == "F3":
        dst = sorted(rng.sample(range(n), int(0.1 * n)))
        src_pool = [i for i in range(n) if i not in dst]
        src = [rng.choice(src_pool) for _ in dst]
        for d_, s_ in zip(dst, src):
            df.loc[d_] = df.loc[s_]
        return {"rows": dst, "copied_from": src}
    if fault == "F4":
        col = spec["target"]
        rows = sorted(rng.sample(range(n), int(0.3 * n)))
        vals = df.loc[rows, col].tolist()
        perm = vals[:]
        while perm == vals:
            rng.shuffle(perm)
        df.loc[rows, col] = perm
        return {"column": col, "rows": rows}
    if fault == "F5":
        num = spec["columns"]
        pairs = [(a, b) for i, a in enumerate(num) for b in num[i + 1:]
                 if df[a].max() < df[b].min() or df[b].max() < df[a].min()]
        a, b = rng.choice(pairs)
        df[[a, b]] = df[[b, a]].values
        return {"columns": [a, b]}
    if fault == "F6":
        col = rng.choice(spec["columns"])
        rows = sorted(rng.sample(range(n), int(0.05 * n)))
        df.loc[rows, col] = -999
        return {"column": col, "rows": rows}
    if fault == "F7":
        col = rng.choice(spec["continuous"])
        df[col] = df[col].round(0)
        return {"column": col}
    raise ValueError(fault)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for name in DATASETS:
        base = pool(name)
        jobs = [("clean", i) for i in range(CLEAN_PER)] + \
               [(f, s) for f in FAULTS for s in range(SEEDS_PER_FAULT)]
        for kind, s in jobs:
            iid = f"{name}.{kind}.{s}"
            rng = random.Random(f"{SEED}:{iid}")
            df = base.sample(n=N_ROWS, random_state=rng.randrange(2**31)).reset_index(drop=True)
            params = {} if kind == "clean" else inject(name, df, kind, rng)
            csv_text = df.to_csv(index=False)
            d = OUT / iid
            d.mkdir(parents=True, exist_ok=True)
            (d / "data.csv").write_text(csv_text, encoding="utf-8")
            (d / "CARD.md").write_text(card(name), encoding="utf-8")
            items.append({"item": iid, "dataset": name, "fault": kind if kind != "clean" else None,
                          "params": params,
                          "csv_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
                          "validator": validate(name, csv_text)})
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"seed": SEED, "n_rows": N_ROWS, "items": items}, indent=1,
                                   default=str) + "\n", encoding="utf-8")
    clean = [i for i in items if i["fault"] is None]
    print(f"{len(items)} items; validator flags {sum(i['validator']['flagged'] for i in clean)} of "
          f"{len(clean)} clean")
    for f in FAULTS:
        fi = [i for i in items if i["fault"] == f]
        print(f"  {f}: validator {sum(i['validator']['flagged'] for i in fi)}/{len(fi)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
