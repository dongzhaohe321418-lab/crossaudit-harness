"""Linear calibration of predicted against experimental 13C chemical shifts.

Reads data/shifts.csv, fits experimental_ppm = slope * predicted_ppm +
intercept by ordinary least squares, writes the calibrated predictions to
calibrated.csv, and reports slope, intercept, the RMSE of the calibrated
predictions and n. The uncertainty on the slope is a bootstrap standard error
(400 resamples over carbons, seeded by --seed). Writes results.json and
results.txt beside scripts/ and prints results.json. Standard library only.

Usage: python3 scripts/analyse.py --seed <int>
"""
import csv
import io
import json
import math
import random
import sys

#@HELPERS

DATA = "data/shifts.csv"


def run(read, seed):
    cv = read_code_version(read("metadata.yml").decode("utf-8"))
    src = "%s@%s" % (DATA, cv)
    rows = read_csv(read(DATA).decode("utf-8"))
    x = column(rows, "predicted_ppm")
    y = column(rows, "experimental_ppm")
    slope, intercept = linfit(x, y)
    cal = [slope * v + intercept for v in x]
    lines = ["id,experimental_ppm,calibrated_ppm"]
    for r, c in zip(rows, cal):
        lines.append("%s,%s,%r" % (r["id"], r["experimental_ppm"], c))
    rng = random.Random(seed)
    unc = round_uncertainty(bootstrap_se(
        rng, len(x), lambda idx: linfit([x[i] for i in idx], [y[i] for i in idx])[0]
        if len(set(x[i] for i in idx)) > 2 else None))
    d = decimals_for(unc)
    qs = [
        quantity("slope", rounded(slope, d), "1", src, unc),
        quantity("intercept", rounded(intercept, 3), "ppm", src),
        quantity("rmse", rounded(rmse(y, cal), 3), "ppm", src),
        quantity("n", len(x), "1", src),
    ]
    ders = [
        derivation("slope", "linfit_slope", {"file": DATA, "x": "predicted_ppm", "y": "experimental_ppm"}, d),
        derivation("intercept", "linfit_intercept", {"file": DATA, "x": "predicted_ppm", "y": "experimental_ppm"}, 3),
        derivation("rmse", "rmse", {"file": "calibrated.csv", "truth": "experimental_ppm", "pred": "calibrated_ppm"}, 3),
        derivation("n", "count", {"file": DATA, "x": "id"}, 0),
    ]
    claims = [{"text": "the predictor is unbiased in scale: the calibration slope lies within 0.9 to 1.1",
               "test": "within", "quantity": "slope", "low": 0.9, "high": 1.1}]
    doc = {"quantities": qs, "stochastic": True, "derivations": ders, "claims": claims}
    return emit(doc, {"calibrated.csv": ("\n".join(lines) + "\n").encode("utf-8")})


if __name__ == "__main__":
    main(run)
