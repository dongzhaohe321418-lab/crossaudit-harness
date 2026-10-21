"""crystal_bandgap_ml: ridge regression of a DFT-like band gap, group split.

Synthetic compounds in twelve binary chemical systems; the band gap is a known
linear function of composition features plus a per-system offset and noise.
Three systems are held out as the test set (splits.json), so the split is a
group split. Honest boundary: the features are invented, not computed from
real compositions.
"""
from __future__ import annotations

import sys

from . import (Instance, assemble, csv_bytes, gauss, new_instance, qvalue,
               rerun_analysis, shuffled, uniform)

NAME = "crystal_bandgap_ml"
SLUG = "bandgap-ridge"
PROJECT = "Band-gap regression from composition"
INPUTS = ["data/compounds.csv", "splits.json"]
METHOD = ("ridge regression (lambda 1.0, standardised features) evaluated on a "
          "group-held-out split by chemical system; baseline predicts the train mean")
SPLIT_RULE = True
TASK = """\
# Task

Train a ridge regression that predicts the DFT band gap (eV) of binary
compounds from four composition features (mean electronegativity,
electronegativity difference, mean atomic radius, ionic fraction). Hold out
whole chemical systems as the test set, so the test error measures transfer to
unseen chemistries. Report the test MAE, RMSE and r2, the test MAE of a
baseline that predicts the training-set mean, and the train and test sizes.
State whether the model beats the baseline.
"""
DOMAIN_RULES = """\
### CA-BG-001
**BLOCKER.** Test metrics are computed only on compounds whose chemical system
does not appear in training.
"""
RANGES = [
    {"name": "mae_*", "unit": "eV", "min": 0, "max": 15},
    {"name": "rmse_*", "unit": "eV", "min": 0, "max": 15},
    {"name": "r2_*", "unit": "1", "min": -1, "max": 1},
    {"name": "n_*", "unit": "1", "min": 1},
]
SYSTEMS = ["Li-F", "Na-Cl", "K-Br", "Mg-O", "Ca-S", "Zn-S", "Ga-N", "Ga-As",
           "In-P", "Cd-Te", "Al-N", "Si-C"]
HEADER = ["id", "system", "en_mean", "en_diff", "radius_mean_pm", "ionic_fraction", "bandgap_ev"]


def _features(rng):
    rows = []
    idx = 1
    for system in SYSTEMS:
        en_mean0, en_diff0, rad0 = uniform(rng, 1.6, 3.1), uniform(rng, 0.2, 2.8), uniform(rng, 70, 170)
        offset = gauss(rng, 0.0, 0.25)
        for _ in range(10):
            en_mean = en_mean0 + gauss(rng, 0, 0.2)
            en_diff = max(0.05, en_diff0 + gauss(rng, 0, 0.35))
            rad = rad0 + gauss(rng, 0, 15.0)
            ionic = 1.0 - 2.718281828459045 ** (-en_diff * en_diff / 4.0)
            rows.append({"id": "c%03d" % idx, "system": system, "en_mean": round(en_mean, 3),
                         "en_diff": round(en_diff, 3), "radius_mean_pm": round(rad, 2),
                         "ionic_fraction": round(ionic, 4), "offset": offset})
            idx += 1
    return rows


def _gap_physical(rng, r):
    g = (0.4 + 2.2 * r["en_diff"] + 0.9 * (r["en_mean"] - 2.0)
         - 0.006 * (r["radius_mean_pm"] - 100.0) + r["offset"] + gauss(rng, 0, 0.3))
    return round(max(0.05, g), 3)


def _gap_noise(rng, r):
    return round(max(0.05, 2.6 + gauss(rng, 0, 1.1)), 3)


def _write(inst: Instance, rows, gaps, test_systems):
    data = csv_bytes(HEADER, [[r["id"], r["system"], r["en_mean"], r["en_diff"], r["radius_mean_pm"],
                               r["ionic_fraction"], g] for r, g in zip(rows, gaps)])
    train = [r["id"] for r in rows if r["system"] not in test_systems]
    test = [r["id"] for r in rows if r["system"] in test_systems]
    return data, train, test


def splits_bytes(train, test) -> bytes:
    import json
    doc = {"data": "data/compounds.csv", "id_column": "id", "group_column": "system",
           "train": train, "test": test}
    return (json.dumps(doc, indent=1) + "\n").encode("utf-8")


def build_clean(rng, seed) -> Instance:
    inst = new_instance(sys.modules[__name__], seed, rng)
    for _attempt in range(50):
        rows = _features(rng)
        gaps = [_gap_physical(rng, r) for r in rows]
        test_systems = sorted(shuffled(rng, SYSTEMS)[:3])
        data, train, test = _write(inst, rows, gaps, test_systems)
        inst.params = {"test_systems": test_systems}
        assemble(sys.modules[__name__], inst,
                 {"data/compounds.csv": data, "splits.json": splits_bytes(train, test)})
        res = inst.results()
        if qvalue(res, "mae_test") < qvalue(res, "mae_baseline") and qvalue(res, "r2_test") > 0:
            return inst
    raise RuntimeError("no clean crystal instance in 50 attempts")


def regenerate(inst: Instance, variant: str, rng) -> Instance | None:
    """improvement_claim_false: the band-gap column is redrawn with NO feature
    dependence, everything is recomputed by analyse.py, and the 'beats the
    baseline' claim is left in place. Redrawn until the claim is false against
    the committed data (and r2 stays inside its declared range)."""
    if variant != "improvement_claim_false":
        return None
    import csv
    import io
    rows = list(csv.DictReader(io.StringIO(inst.text("data/compounds.csv"))))
    for _attempt in range(200):
        new = inst.copy()
        gaps = [_gap_noise(rng, r) for r in rows]
        data = csv_bytes(HEADER, [[r[h] for h in HEADER[:-1]] + [g] for r, g in zip(rows, gaps)])
        new.files[new.path("data/compounds.csv")] = data
        rerun_analysis(new)
        res = new.results()
        if qvalue(res, "mae_test") >= qvalue(res, "mae_baseline") and qvalue(res, "r2_test") >= -1:
            return new
    raise RuntimeError("could not make the improvement claim false")


def wrong_rows(inst: Instance):
    """Test metrics recomputed on the TRAIN rows (reported as test): candidates
    in preference order; the planter takes the first that differs beyond
    rounding from what was reported."""
    import csv
    import io
    import math
    rows = [r for r in csv.DictReader(io.StringIO(inst.text("predictions.csv"))) if r["split"] == "train"]
    t = [float(r["bandgap_ev"]) for r in rows]
    p = [float(r["pred_ev"]) for r in rows]
    b = [float(r["baseline_ev"]) for r in rows]
    n = len(t)
    return [("mae_test", sum(abs(x - y) for x, y in zip(t, p)) / n),
            ("rmse_test", math.sqrt(sum((x - y) ** 2 for x, y in zip(t, p)) / n)),
            ("mae_baseline", sum(abs(x - y) for x, y in zip(t, b)) / n)]


def summary(p, inst: Instance) -> str:
    unc = p.unc("mae_test")
    return (
        "# Band-gap regression with a group split\n\n"
        f"A ridge regression on four composition features was trained on {p.n('n_train')} "
        f"compounds and evaluated on {p.n('n_test')} compounds from chemical systems held out "
        "of training, using a group-held-out split by chemical system. "
        f"On the test systems the model reaches a mean absolute error of {p.n('mae_test')} "
        f"(bootstrap standard error {unc} eV) and a root-mean-square error of "
        f"{p.n('rmse_test')}, with r2 = {p.n('r2_test')}.\n\n"
        "A baseline that predicts the training-set mean band gap has a test MAE of "
        f"{p.n('mae_baseline')}, so the model's error is lower than that of the baseline.\n")


SPEC = {
    "d03": ("mae_test", "kJ/mol"),
    "d07": "mae_test",
    "d08": {"above_max": ("mae_test", 23.0), "below_min": ("r2_test", -3.0)},
    "d10_targets": ["mae_test", "rmse_test", "mae_baseline"],
    "wrong_rows": wrong_rows,
    "n_quantity": "n_test",
    "direction": ("the model's error is lower than", "the model's error is higher than"),
    "method": ("using a group-held-out split by chemical system",
               "using 5-fold random cross-validation"),
    "d13": ["improvement_claim_false"],
    "has_split": True,
}
