"""Total-energy convergence against k-point density.

Reads data/kpoints.csv (kmesh = n for an n x n x n Monkhorst-Pack mesh,
energy_ev_per_atom), reports the energy on the densest mesh, the absolute
change between the last two meshes (meV/atom) and the number of meshes, and
declares the run converged when that change is below the 1 meV/atom threshold.
The uncertainty on the energy is that last change, in eV/atom. Deterministic:
--seed is accepted for a uniform command line and not used.
Writes results.json and results.txt beside scripts/ and prints results.json.
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

DATA = "data/kpoints.csv"
THRESHOLD_MEV = 1.0


def run(read, seed):
    cv = read_code_version(read("metadata.yml").decode("utf-8"))
    src = "%s@%s" % (DATA, cv)
    rows = read_csv(read(DATA).decode("utf-8"))
    energies = column(rows, "energy_ev_per_atom")
    delta_ev = abs(energies[-1] - energies[-2])
    unc = round_uncertainty(delta_ev)
    d = decimals_for(unc)
    delta_mev = rounded(delta_ev * 1000.0, 3)
    qs = [
        quantity("energy_per_atom", rounded(energies[-1], d), "eV/atom", src, unc),
        quantity("delta_last", delta_mev, "meV/atom", src),
        quantity("n_points", len(energies), "1", src),
    ]
    ders = [
        derivation("energy_per_atom", "last", {"file": DATA, "y": "energy_ev_per_atom"}, d),
        derivation("n_points", "count", {"file": DATA, "x": "kmesh"}, 0),
    ]
    conv = {"converged": delta_mev < THRESHOLD_MEV, "achieved": delta_mev,
            "threshold": THRESHOLD_MEV, "criterion": "abs change in energy_per_atom between the last two meshes, meV/atom"}
    doc = {"quantities": qs, "convergence": conv, "derivations": ders}
    return emit(doc)


if __name__ == "__main__":
    main(run)
