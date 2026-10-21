"""Arrhenius fit of rate constants measured at several temperatures.

Reads data/rates.csv (T_K, k_per_s), fits ln k = ln A - Ea / (R T) by ordinary
least squares on 1/T, and reports the activation energy (kJ/mol), ln A (k in
1/s), the r2 of the linear fit and n. The uncertainty on the activation energy
is a bootstrap standard error (400 resamples over temperatures, a resample with
fewer than three distinct temperatures redrawn, seeded by --seed). Writes
results.json and results.txt beside scripts/ and prints results.json.
Standard library only.

Usage: python3 scripts/analyse.py --seed <int>
"""
import csv
import io
import json
import math
import random
import sys

#@HELPERS

DATA = "data/rates.csv"


def run(read, seed):
    cv = read_code_version(read("metadata.yml").decode("utf-8"))
    src = "%s@%s" % (DATA, cv)
    rows = read_csv(read(DATA).decode("utf-8"))
    temps = column(rows, "T_K")
    ks = column(rows, "k_per_s")
    x = [1.0 / t for t in temps]
    y = [math.log(k) for k in ks]
    slope, intercept = linfit(x, y)
    ea = -slope * R_GAS / 1000.0
    fit = [slope * v + intercept for v in x]
    rng = random.Random(seed)
    unc = round_uncertainty(bootstrap_se(
        rng, len(x), lambda idx: -linfit([x[i] for i in idx], [y[i] for i in idx])[0] * R_GAS / 1000.0
        if len(set(idx)) >= 3 else None))
    d = decimals_for(unc)
    qs = [
        quantity("activation_energy", rounded(ea, d), "kJ/mol", src, unc),
        quantity("ln_prefactor", rounded(intercept, 3), "1", src),
        quantity("r2", rounded(r2(y, fit), 4), "1", src),
        quantity("n", len(x), "1", src),
    ]
    ders = [
        derivation("activation_energy", "arrhenius_ea_kj_per_mol", {"file": DATA, "T_K": "T_K", "k": "k_per_s"}, d),
        derivation("ln_prefactor", "arrhenius_ln_a", {"file": DATA, "T_K": "T_K", "k": "k_per_s"}, 3),
        derivation("n", "count", {"file": DATA, "x": "T_K"}, 0),
    ]
    doc = {"quantities": qs, "stochastic": True, "derivations": ders}
    return emit(doc)


if __name__ == "__main__":
    main(run)
