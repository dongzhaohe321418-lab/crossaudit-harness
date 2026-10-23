"""Cubic lattice parameter from indexed powder diffraction peaks (Cu K-alpha).

Reads data/peaks.csv (two_theta_deg, h, k, l), converts each peak to a
d-spacing with Bragg's law (wavelength 1.5406 angstrom), estimates
a = d * sqrt(h^2 + k^2 + l^2) per peak and reports the mean over all indexed
peaks, the (111) spacing implied by that a (a / sqrt 3), the number of
peaks, and the median and population standard deviation (n divisor: every
indexed peak, not a sample of peaks) of the per-peak estimates. The
uncertainty on a is a bootstrap standard error (400 resamples over peaks,
seeded by --seed). Writes per_peak.csv (the per-peak estimates), results.json
and results.txt beside scripts/ and prints results.json. Standard library only.

Usage: python3 scripts/analyse.py --seed <int>
"""
import csv
import io
import json
import math
import random
import sys

#@HELPERS

DATA = "data/peaks.csv"
WAVELENGTH = 1.5406


def run(read, seed):
    cv = read_code_version(read("metadata.yml").decode("utf-8"))
    src = "%s@%s" % (DATA, cv)
    rows = read_csv(read(DATA).decode("utf-8"))
    per_peak = []
    lines = ["two_theta_deg,h,k,l,a_angstrom"]
    for r in rows:
        theta = math.radians(float(r["two_theta_deg"]) / 2.0)
        dspace = WAVELENGTH / (2.0 * math.sin(theta))
        per_peak.append(dspace * math.sqrt(float(r["h"]) ** 2 + float(r["k"]) ** 2 + float(r["l"]) ** 2))
        lines.append("%s,%s,%s,%s,%r" % (r["two_theta_deg"], r["h"], r["k"], r["l"], per_peak[-1]))
    a = mean(per_peak)
    rng = random.Random(seed)
    unc = round_uncertainty(bootstrap_se(rng, len(per_peak), lambda idx: mean([per_peak[i] for i in idx])))
    d = decimals_for(unc)
    a_rep = rounded(a, d)
    factor = 1.0 / math.sqrt(3.0)
    qs = [
        quantity("lattice_a", a_rep, "Å", src, unc),
        quantity("d_111", rounded(a_rep * factor, 4), "Å", src),
        quantity("n_peaks", len(per_peak), "1", src),
    ]
    spread = sd_population(per_peak)
    d_spread = sig_decimals(spread, 3)
    qs += [
        quantity("a_median", rounded(median(per_peak), d), "Å", src),
        quantity("a_spread", rounded(spread, d_spread), "Å", src),
    ]
    ders = [
        derivation("lattice_a", "bragg_cubic_a", {"file": DATA, "two_theta_deg": "two_theta_deg",
                                                  "h": "h", "k": "k", "l": "l", "wavelength": WAVELENGTH}, d),
        derivation("d_111", "scale", {"x": "lattice_a", "factor": factor}, 4),
        derivation("n_peaks", "count", {"file": DATA, "x": "h"}, 0),
        derivation("a_median", "median", {"file": "per_peak.csv", "x": "a_angstrom"}, d),
        derivation("a_spread", "sd_population", {"file": "per_peak.csv", "x": "a_angstrom"}, d_spread),
    ]
    doc = {"quantities": qs, "stochastic": True, "derivations": ders}
    return emit(doc, {"per_peak.csv": ("\n".join(lines) + "\n").encode("utf-8")})


if __name__ == "__main__":
    main(run)
