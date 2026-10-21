"""nmr_shift_calibration: linear calibration of predicted vs experimental 13C shifts.

Experimental shifts are drawn uniformly over 12-205 ppm; predictions are the
experimental value pushed through a known slope/intercept plus Gaussian noise.
Honest boundary: no molecule or prediction method stands behind the numbers.
"""
from __future__ import annotations

import sys

from . import Instance, assemble, csv_bytes, gauss, new_instance, qvalue, rerun_analysis, uniform

NAME = "nmr_shift_calibration"
SLUG = "c13-calibration"
PROJECT = "13C shift prediction calibration"
INPUTS = ["data/shifts.csv"]
METHOD = "ordinary least squares of experimental_ppm on predicted_ppm"
TASK = """\
# Task

Calibrate the 13C chemical shifts predicted by our model against the
experimental shifts in data/shifts.csv with a straight-line fit. Report the
slope, the intercept (ppm), the root-mean-square deviation of the calibrated
predictions from experiment (ppm) and the number of carbons, and say whether
the predictor is unbiased in scale (slope within 0.9 to 1.1).
"""
DOMAIN_RULES = """\
### CA-NMR-001
**BLOCKER.** The calibration is fitted on every carbon in the committed data;
no point is dropped without being reported.
"""
RANGES = [
    {"name": "slope", "unit": "1", "min": 0, "max": 2},
    {"name": "intercept", "unit": "ppm", "min": -50, "max": 50},
    {"name": "rmse", "unit": "ppm", "min": 0, "max": 50},
    {"name": "n", "unit": "1", "min": 1},
]
HEADER = ["id", "predicted_ppm", "experimental_ppm"]


def _data(rng, n, a, b, sigma, exps=None):
    exps = exps or [round(uniform(rng, 12.0, 205.0), 2) for _ in range(n)]
    rows = [["C%02d" % (i + 1), round((e - b) / a + gauss(rng, 0, sigma), 2), e]
            for i, e in enumerate(exps)]
    return csv_bytes(HEADER, rows), exps


def build_clean(rng, seed) -> Instance:
    mod = sys.modules[__name__]
    inst = new_instance(mod, seed, rng)
    n = 30 + int(rng.random() * 16)
    a, b, sigma = uniform(rng, 0.97, 1.03), uniform(rng, -2.5, 2.5), uniform(rng, 1.2, 2.2)
    for _attempt in range(50):
        data, exps = _data(rng, n, a, b, sigma)
        inst.params = {"n": n, "a": a, "b": b, "sigma": sigma, "exps": exps}
        assemble(mod, inst, {"data/shifts.csv": data})
        if 0.9 <= qvalue(inst.results(), "slope") <= 1.1:
            return inst
    raise RuntimeError("no clean nmr instance")


def regenerate(inst: Instance, variant: str, rng) -> Instance | None:
    """improvement_claim_false (nmr reading: the declared calibration-quality
    claim is false): the predictions are redrawn from the same experimental
    shifts under a scale error of 1.2-1.3, everything is recomputed, and the
    'slope within 0.9 to 1.1' claim is left in place."""
    if variant != "improvement_claim_false":
        return None
    prm = inst.params
    for _attempt in range(200):
        new = inst.copy()
        data, _ = _data(rng, prm["n"], uniform(rng, 1.2, 1.3), prm["b"], prm["sigma"], prm["exps"])
        new.files[new.path("data/shifts.csv")] = data
        rerun_analysis(new)
        if qvalue(new.results(), "slope") > 1.1:
            return new
    raise RuntimeError("could not make the nmr claim false")


def summary(p, inst: Instance) -> str:
    unc = p.unc("slope")
    return (
        "# 13C shift calibration\n\n"
        f"Predicted 13C chemical shifts for {p.n('n')} carbons were calibrated against "
        "experiment by ordinary least squares. The experimental shifts increase linearly with "
        f"the predicted shifts: the fitted slope is {p.n('slope')} (bootstrap standard error "
        f"{unc}) and the intercept is {p.n('intercept')}. After calibration the "
        f"root-mean-square deviation from experiment is {p.n('rmse')}.\n\n"
        "The slope lies inside the 0.9 to 1.1 window, so the predictor is unbiased in scale.\n")


SPEC = {
    "d03": ("intercept", "Hz"),
    "d07": None,
    "d08": {"above_max": ("intercept", 480.0), "below_min": ("intercept", -480.0)},
    "d10_targets": ["slope", "rmse", "intercept"],
    "wrong_rows": None,
    "n_quantity": "n",
    "direction": ("experimental shifts increase linearly", "experimental shifts decrease linearly"),
    "method": ("by ordinary least squares", "by Theil-Sen robust regression"),
    "d13": ["improvement_claim_false"],
    "has_split": False,
}
