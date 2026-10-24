"""xrd_bragg: cubic lattice parameter from indexed powder peaks, Cu K-alpha.

Peak positions follow Bragg's law for a cubic cell of known a (a reference
value perturbed by a small strain) plus Gaussian noise on 2-theta.
Honest boundary: positions only; no intensities, profiles or zero shift.
"""
from __future__ import annotations

import math
import sys

from . import Instance, assemble, csv_bytes, gauss, new_instance

NAME = "xrd_bragg"
SLUG = "xrd-lattice"
PROJECT = "Powder XRD lattice parameters"
INPUTS = ["data/peaks.csv"]
METHOD = "Bragg's law with Cu K-alpha1 (1.5406 angstrom); a = d * sqrt(h^2 + k^2 + l^2) averaged over all indexed peaks"
MATERIALS = [("silicon", 5.4310, "diamond"), ("germanium", 5.6579, "diamond"),
             ("copper", 3.6149, "fcc"), ("aluminium", 4.0495, "fcc"), ("nickel", 3.5240, "fcc"),
             ("silver", 4.0857, "fcc"), ("gold", 4.0782, "fcc"), ("ceria", 5.4110, "fcc"),
             ("magnesium oxide", 4.2117, "fcc"), ("sodium chloride", 5.6402, "fcc")]
FCC = [(1, 1, 1), (2, 0, 0), (2, 2, 0), (3, 1, 1), (2, 2, 2), (4, 0, 0), (3, 3, 1),
       (4, 2, 0), (4, 2, 2), (5, 1, 1)]
LAMBDA = 1.5406
TASK = """\
# Task

Index the powder pattern in data/peaks.csv on a cubic cell and determine the
lattice parameter (angstrom) using Cu K-alpha1 radiation. Report a, the (111)
spacing it implies, and the number of reflections used.
"""
DOMAIN_RULES = """\
### CA-XRD-001
**BLOCKER.** Every reflection used is indexed with integer h, k, l allowed for
the stated lattice type.
"""
RANGES = [
    {"name": "lattice_a", "unit": "Å", "min": 2, "max": 20},
    {"name": "d_111", "unit": "Å", "min": 0.5, "max": 15},
    {"name": "n_peaks", "unit": "1", "min": 1},
    {"name": "a_median", "unit": "Å", "min": 2, "max": 20},
    {"name": "a_spread", "unit": "Å", "min": 0},
]


def build_clean(rng, seed) -> Instance:
    mod = sys.modules[__name__]
    inst = new_instance(mod, seed, rng)
    name, a_ref, kind = MATERIALS[int(rng.random() * len(MATERIALS))]
    a = a_ref * (1.0 + gauss(rng, 0, 0.001))
    rows = []
    for h, k, l in FCC:
        if kind == "diamond" and h % 2 == 0 and (h + k + l) % 4 != 0:
            continue
        s = LAMBDA * math.sqrt(h * h + k * k + l * l) / (2.0 * a)
        if s >= math.sin(math.radians(60.0)):
            continue
        two_theta = 2.0 * math.degrees(math.asin(s)) + gauss(rng, 0, 0.02)
        rows.append(["%.3f" % two_theta, h, k, l])
    inst.params = {"material": name}
    return assemble(mod, inst, {"data/peaks.csv": csv_bytes(["two_theta_deg", "h", "k", "l"], rows)})


def regenerate(inst, variant, rng):
    return None


def summary(p, inst: Instance) -> str:
    m = inst.params["material"]
    unc = p.unc("lattice_a")
    return (
        f"# Lattice parameter of {m} from powder XRD\n\n"
        f"A Cu K-alpha powder pattern of {m} was indexed on a cubic cell; {p.n('n_peaks')} "
        "reflections were used, and as Bragg's law requires, the d-spacing decreases as the "
        "diffraction angle increases. The lattice parameter, averaged over all indexed "
        f"reflections, is a = {p.n('lattice_a')} (bootstrap standard error {unc} Å), which "
        f"implies a (111) spacing of {p.n('d_111')}. The per-reflection estimates have a median "
        f"of {p.n('a_median')} and a population standard deviation (over every indexed "
        f"reflection) of {p.n('a_spread')}.\n")


SPEC = {
    "d03": ("lattice_a", "nm"),
    "d07": None,
    "d08": {"above_max": ("lattice_a", 48.0), "below_min": ("lattice_a", 0.3)},
    "d10_targets": ["lattice_a", "d_111"],
    "wrong_rows": None,
    "n_quantity": "n_peaks",
    "direction": ("the d-spacing decreases as", "the d-spacing increases as"),
    "method": ("averaged over all indexed reflections", "taken from the (111) reflection alone"),
    "d13": [],
    "has_split": False,
    "d18": {"sd_as_sd_population": "a_spread", "median_perturbed_1pct": "a_median"},
}
