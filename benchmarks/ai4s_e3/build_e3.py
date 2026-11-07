"""E3 items and deterministic baselines (PREREGISTRATION-E3.md). No model calls.

For every dataset: a clean pool (source columns renamed to the card's names, numeric, rows with missing
values or the source's missing-value marker removed, exact duplicates removed), split once into a
*reference* sample (30%, at most 3,000 rows; what a data steward would profile) and an *item* pool. Items are
drawn from the item pool at each size the pool allows (size <= 70% of it): clean items and one faulty item
per fault type and seed. Item directories have opaque names and hold only data.csv and CARD.md.

Two deterministic baselines, both frozen here before any audit:
  card validator     the A4S-3 rules generalised: card ranges, non-negativity from units, sentinels,
                     exact duplicate rows, integer-valued columns that are non-integer in the reference.
  profile validator  the card validator plus profile checks against the reference sample, in the manner of
                     TFDV/Deequ: per-column out-of-profile mass, per-column median shift, and target-feature
                     correlation shift, each against a null band from 400 same-size resamples of the
                     reference (Bonferroni over columns, family-wise 1% per statistic).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from spec_e3 import DATASETS, FAULTS, SENTINELS, SIZES, card, columns, nonneg  # noqa: E402

SOURCE = HERE.parents[2] / "e3data" / "uci"                 # audit/e3data/uci (not in the repository)
ITEM_ROOT = Path("/tmp/e3items")                            # opaque item directories, outside the repo
REC = HERE.parent / "code" / "records" / "icml_e3"
SEED = 20261111
SEEDS_PER_FAULT = {"dev": 2, "test": 2}


def pool(name: str) -> pd.DataFrame:
    d = DATASETS[name]
    raw = pd.read_csv(SOURCE / f"{name}.csv", low_memory=False)
    df = raw[list(d["rename"])].rename(columns=d["rename"])
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if "missing_marker" in d:
        df = df[~(df == d["missing_marker"]).any(axis=1)]
    df = df.drop_duplicates().astype(float)
    return df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def split_pool(df: pd.DataFrame):
    n_ref = min(3000, int(0.3 * len(df)))
    return df.iloc[:n_ref].reset_index(drop=True), df.iloc[n_ref:].reset_index(drop=True)


def inject(name: str, df: pd.DataFrame, fault: str, rng: random.Random, ref: pd.DataFrame) -> dict:
    d, n, cols = DATASETS[name], len(df), columns(name)
    if fault == "F1":
        col, fac, off, to = rng.choice(d["unit_mix"])
        rows = sorted(rng.sample(range(n), int(0.2 * n)))
        df.loc[rows, col] = df.loc[rows, col] * fac + off
        return {"column": col, "n_rows": len(rows), "to_unit": to}
    if fault == "F2":
        cands = [c for c in nonneg(name) if (df[c] > 0).sum() >= 3]
        col = rng.choice(cands)
        pos = [i for i in range(n) if df.at[i, col] > 0]
        rows = sorted(rng.sample(pos, max(3, int(0.01 * n))))
        df.loc[rows, col] = -df.loc[rows, col]
        return {"column": col, "n_rows": len(rows)}
    if fault == "F3":
        dst = sorted(rng.sample(range(n), int(0.1 * n)))
        keep = sorted(set(range(n)) - set(dst))
        for i in dst:
            df.loc[i] = df.loc[rng.choice(keep)]
        return {"n_rows": len(dst)}
    if fault == "F4":
        col = d["target"]
        rows = sorted(rng.sample(range(n), int(0.3 * n)))
        vals = df.loc[rows, col].tolist()
        perm = vals[:]
        while perm == vals:
            rng.shuffle(perm)
        df.loc[rows, col] = perm
        return {"column": col, "n_rows": len(rows)}
    if fault == "F5":
        med = {c: float(ref[c].median()) for c in cols}
        pairs = [(a, b) for i, a in enumerate(cols) for b in cols[i + 1:]
                 if ref[a].max() < ref[b].min() or ref[b].max() < ref[a].min()]
        if not pairs:
            pairs = sorted(((a, b) for i, a in enumerate(cols) for b in cols[i + 1:]),
                           key=lambda ab: -abs(med[ab[0]] - med[ab[1]]))[:3]
        a, b = rng.choice(pairs)
        df[[a, b]] = df[[b, a]].values
        return {"columns": [a, b]}
    if fault == "F6":
        col = rng.choice(cols)
        rows = sorted(rng.sample(range(n), max(1, int(0.05 * n))))
        df.loc[rows, col] = -999.0
        return {"column": col, "n_rows": len(rows)}
    if fault == "F7":
        cont = [c for c in cols if not np.all(np.mod(ref[c], 1) == 0)]
        col = rng.choice(cont)
        df[col] = df[col].round(0)
        return {"column": col}
    raise ValueError(fault)


# ------------------------------------------------------------------ validators
def card_validator(name: str, df: pd.DataFrame, ref: pd.DataFrame) -> list[str]:
    d, fired = DATASETS[name], []
    for c in columns(name):
        v = df[c].to_numpy()
        if np.isin(v, list(SENTINELS)).any():
            fired.append(f"sentinel:{c}")
        if c in nonneg(name) and (v < 0).any():
            fired.append(f"negative:{c}")
        r = d["ranges"].get(c)
        if r and ((v < r[0]) | (v > r[1])).any():
            fired.append(f"range:{c}")
        p_nonint = float(np.mean(np.mod(ref[c], 1) != 0))
        if p_nonint > 0 and (1 - p_nonint) ** len(v) < 1e-4 and np.all(np.mod(v, 1) == 0):
            fired.append(f"integer:{c}")
    if df.duplicated().any():
        fired.append("duplicates")
    return fired


def halves(ref: pd.DataFrame):
    """Profile half (quantiles) and null half (resampled for the null bands): disjoint."""
    h = len(ref) // 2
    return ref.iloc[:h].reset_index(drop=True), ref.iloc[h:].reset_index(drop=True)


def _stats(name: str, df: pd.DataFrame, ref: pd.DataFrame) -> dict:
    cols, tgt = columns(name), DATASETS[name]["target"]
    ref = halves(ref)[0]
    out = {}
    for c in cols:
        lo, hi = np.quantile(ref[c], [0.001, 0.999])
        width = hi - lo if hi > lo else 1.0
        v = df[c].to_numpy()
        out[f"oop:{c}"] = float(np.mean((v < lo - 0.1 * width) | (v > hi + 0.1 * width)))
        out[f"med:{c}"] = float(np.median(v))
    for c in cols:
        if c == tgt or df[c].std() == 0 or df[tgt].std() == 0:
            continue
        out[f"corr:{c}"] = float(np.corrcoef(df[c], df[tgt])[0, 1])
    return out


_null_cache: dict = {}


def null_bands(name: str, ref: pd.DataFrame, size: int) -> dict:
    key = (name, size)
    if key in _null_cache:
        return _null_cache[key]
    rng = np.random.default_rng(SEED)
    null_half = halves(ref)[1]
    draws = [_stats(name, null_half.sample(n=size, replace=True,
                                           random_state=int(rng.integers(2**31))).reset_index(drop=True), ref)
             for _ in range(400)]
    keys = draws[0].keys()
    groups = {"oop": [k for k in keys if k.startswith("oop:")], "med": [k for k in keys if k.startswith("med:")],
              "corr": [k for k in keys if k.startswith("corr:")]}
    bands = {}
    for g, ks in groups.items():
        alpha = 0.01 / max(1, len(ks))
        for k in ks:
            vals = np.array([dr.get(k, np.nan) for dr in draws])
            vals = vals[~np.isnan(vals)]
            if g == "oop":
                bands[k] = (None, float(np.quantile(vals, 1 - alpha)) + 1e-9)
            else:
                bands[k] = (float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2)))
    _null_cache[key] = bands
    return bands


PROFILE = {"oop_frac": 0.02, "oop_widen": 0.10, "median_iqr": 0.5, "corr_z": 4.5, "corr_abs": 0.2}


def profile_validator(name: str, df: pd.DataFrame, ref: pd.DataFrame) -> list[str]:
    """Card validator plus fixed-threshold profile checks against the reference (TFDV/Deequ style).
    Thresholds are set on the development datasets' clean items only and frozen before test items are read."""
    fired = card_validator(name, df, ref)
    cols, tgt = columns(name), DATASETS[name]["target"]
    for c in cols:
        lo, hi = np.quantile(ref[c], [0.001, 0.999])
        w = (hi - lo) if hi > lo else max(abs(hi), 1.0)
        v = df[c].to_numpy()
        if np.mean((v < lo - PROFILE["oop_widen"] * w) | (v > hi + PROFILE["oop_widen"] * w)) > PROFILE["oop_frac"]:
            fired.append(f"profile:oop:{c}")
        q1, q3 = np.quantile(ref[c], [0.25, 0.75])
        iqr = (q3 - q1) if q3 > q1 else w
        if abs(np.median(v) - np.median(ref[c])) > PROFILE["median_iqr"] * iqr:
            fired.append(f"profile:med:{c}")
    n_i, n_r = len(df), len(ref)
    for c in cols:
        if c == tgt or df[c].std() == 0 or ref[c].std() == 0 or df[tgt].std() == 0:
            continue
        ri = float(np.clip(np.corrcoef(df[c], df[tgt])[0, 1], -0.999, 0.999))
        rr = float(np.clip(np.corrcoef(ref[c], ref[tgt])[0, 1], -0.999, 0.999))
        z = abs(np.arctanh(ri) - np.arctanh(rr)) / np.sqrt(1 / (n_i - 3) + 1 / (n_r - 3))
        if z > PROFILE["corr_z"] and abs(ri - rr) > PROFILE["corr_abs"]:
            fired.append(f"profile:corr:{c}")
    return fired


def main() -> int:
    REC.mkdir(parents=True, exist_ok=True)
    if (REC / "items.json").exists():
        raise SystemExit("items.json exists; E3 items are frozen")
    ITEM_ROOT.mkdir(parents=True, exist_ok=True)
    items, refs = [], {}
    dropped_ranges = {}
    for name, d in DATASETS.items():
        full = pool(name)
        bad = [c for c, (lo, hi) in d["ranges"].items() if ((full[c] < lo) | (full[c] > hi)).any()]
        for c in bad:                                  # a stated range the source itself violates is not stated
            dropped_ranges.setdefault(name, []).append([c, list(d["ranges"].pop(c))])
        ref, rest = split_pool(full)
        refs[name] = {"n_reference": len(ref), "n_item_pool": len(rest)}
        ref.to_csv(REC / f"reference_{name}.csv", index=False)
        for size in SIZES:
            if size > 0.7 * len(rest):
                continue
            n_seeds = SEEDS_PER_FAULT[d["split"]]
            jobs = [("clean", s) for s in range(n_seeds * len(FAULTS))] + \
                   [(f, s) for f in FAULTS for s in range(n_seeds)]
            for kind, s in jobs:
                label = f"{name}|{size}|{kind}|{s}"
                rng = random.Random(f"{SEED}:{label}")
                df = rest.sample(n=size, random_state=rng.randrange(2**31)).reset_index(drop=True)
                params = {} if kind == "clean" else inject(name, df, kind, rng, ref)
                csv_text = df.to_csv(index=False)
                opaque = hashlib.sha256(f"{SEED}:{label}".encode()).hexdigest()[:16]
                item_dir = ITEM_ROOT / opaque
                item_dir.mkdir(parents=True, exist_ok=True)
                (item_dir / "data.csv").write_text(csv_text, encoding="utf-8")
                (item_dir / "CARD.md").write_text(card(name), encoding="utf-8")
                items.append({"item": opaque, "dataset": name, "split": d["split"], "size": size,
                              "fault": None if kind == "clean" else kind, "seed": s, "params": params,
                              "csv_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
                              "card_validator": card_validator(name, df, ref),
                              "profile_validator": profile_validator(name, df, ref)})
            print(name, size, "done", flush=True)
    (REC / "items.json").write_text(json.dumps({"seed": SEED, "references": refs, "dropped_ranges": dropped_ranges, "items": items}, indent=1))
    for split in ("dev", "test"):
        it = [i for i in items if i["split"] == split]
        clean = [i for i in it if i["fault"] is None]
        print(split, len(it), "items;", "clean flags card", sum(bool(i["card_validator"]) for i in clean),
              "profile", sum(bool(i["profile_validator"]) for i in clean), "of", len(clean))
        for f in FAULTS:
            fi = [i for i in it if i["fault"] == f]
            print("  ", f, "card", sum(bool(i["card_validator"]) for i in fi), "profile",
                  sum(bool(i["profile_validator"]) for i in fi), "of", len(fi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
