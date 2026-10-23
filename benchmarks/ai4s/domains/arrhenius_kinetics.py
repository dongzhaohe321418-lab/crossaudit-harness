"""arrhenius_kinetics: Arrhenius fit of rate constants at 6-8 temperatures.

ln k = ln A - Ea/(RT) with known Ea and ln A plus Gaussian noise on ln k.
Honest boundary: one synthetic first-order reaction, no real kinetics.
"""
from __future__ import annotations

import math
import sys

from . import Instance, assemble, csv_bytes, gauss, new_instance, uniform

NAME = "arrhenius_kinetics"
SLUG = "arrhenius"
PROJECT = "Kinetics of ester hydrolysis"
INPUTS = ["data/rates.csv"]
METHOD = "unweighted linear least squares of ln k on 1/T (Arrhenius)"
TASK = """\
# Task

Determine the Arrhenius parameters of the hydrolysis from the first-order rate
constants in data/rates.csv. Report the activation energy (kJ/mol), ln A
(k in 1/s), the r2 of the fit and the number of temperatures.
"""
DOMAIN_RULES = """\
### CA-KIN-001
**BLOCKER.** The activation energy is obtained from the temperature dependence
of the committed rate constants, with R = 8.314462618 J/(mol K).
"""
RANGES = [
    {"name": "activation_energy", "unit": "kJ/mol", "min": 0, "max": 500},
    {"name": "ln_prefactor", "unit": "1", "min": -50, "max": 80},
    {"name": "r2", "unit": "1", "min": -1, "max": 1},
    {"name": "n", "unit": "1", "min": 1},
]
R = 8.314462618


def build_clean(rng, seed) -> Instance:
    mod = sys.modules[__name__]
    inst = new_instance(mod, seed, rng)
    ea, lna = uniform(rng, 45.0, 115.0), uniform(rng, 22.0, 30.0)
    n = 6 + int(rng.random() * 3)
    rows = []
    for i in range(n):
        t = round(298.15 + 12.5 * i + gauss(rng, 0, 0.2), 2)
        lnk = lna - ea * 1000.0 / (R * t) + gauss(rng, 0, 0.04)
        rows.append([t, "%.5e" % math.exp(lnk)])
    inst.params = {"ea": ea, "lna": lna}
    return assemble(mod, inst, {"data/rates.csv": csv_bytes(["T_K", "k_per_s"], rows)})


def regenerate(inst, variant, rng):
    return None


def summary(p, inst: Instance) -> str:
    import csv
    import io
    temps = [r["T_K"] for r in csv.DictReader(io.StringIO(inst.text("data/rates.csv")))]
    unc = p.unc("activation_energy")
    return (
        "# Arrhenius analysis of the hydrolysis\n\n"
        f"Rate constants were measured at {p.n('n')} temperatures between {temps[0]} K and "
        f"{temps[-1]} K, and the rate constant increases with temperature. Using an unweighted "
        "linear least-squares fit of ln k against 1/T, the activation energy is "
        f"{p.n('activation_energy')} (bootstrap standard error {unc} kJ/mol) and "
        f"ln A = {p.n('ln_prefactor')} for k in 1/s, with r2 = {p.n('r2')}.\n")


SPEC = {
    "d03": ("activation_energy", "eV"),
    "d07": "activation_energy",
    "d08": {"above_max": ("activation_energy", 4800.0), "below_min": ("r2", -3.0)},
    "d10_targets": ["activation_energy", "ln_prefactor"],
    "wrong_rows": None,
    "n_quantity": "n",
    "direction": ("the rate constant increases with temperature",
                  "the rate constant decreases with temperature"),
    "method": ("an unweighted linear least-squares fit of ln k against 1/T",
               "a weighted nonlinear least-squares fit of k against T"),
    "d13": [],
    "has_split": False,
}
