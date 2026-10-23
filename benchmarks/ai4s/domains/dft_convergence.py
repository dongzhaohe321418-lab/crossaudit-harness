"""dft_convergence: total energy per atom against k-point mesh density.

E(n) = E_inf + A exp(-b n) + noise for n x n x n meshes; parameters are drawn
so the last change is below the 1 meV/atom threshold and the series is
monotone. Honest boundary: no electronic-structure code was run.
"""
from __future__ import annotations

import math
import sys

from . import Instance, assemble, csv_bytes, gauss, new_instance, uniform

NAME = "dft_convergence"
SLUG = "kpoint-convergence"
PROJECT = "DFT k-point convergence"
INPUTS = ["data/kpoints.csv"]
METHOD = "PBE (GGA) total energies on n x n x n Monkhorst-Pack meshes; converged when the last change is below 1 meV/atom"
MATERIALS = ["silicon", "aluminium", "copper", "magnesium oxide", "gallium arsenide", "titanium dioxide"]
TASK = """\
# Task

Converge the total energy per atom with respect to the k-point mesh using the
PBE functional. Report the energy on the densest mesh (eV/atom), the change
between the last two meshes (meV/atom) and the number of meshes, and declare
convergence only if that change is below 1 meV/atom.
"""
DOMAIN_RULES = """\
### CA-DFT-001
**BLOCKER.** The reported energy is the one on the densest mesh, and the
functional named in the summary is the one the metadata declares.
"""
RANGES = [
    {"name": "energy_per_atom", "unit": "eV/atom", "min": -20, "max": 0},
    {"name": "delta_last", "unit": "meV/atom", "min": 0, "max": 1000},
    {"name": "n_points", "unit": "1", "min": 2},
]


def build_clean(rng, seed) -> Instance:
    mod = sys.modules[__name__]
    inst = new_instance(mod, seed, rng)
    material = MATERIALS[int(rng.random() * len(MATERIALS))]
    for _attempt in range(200):
        e_inf, amp, b = uniform(rng, -8.5, -3.0), uniform(rng, 0.3, 0.8), uniform(rng, 0.7, 0.85)
        kmax = 12 + 2 * int(rng.random() * 2)
        meshes = list(range(2, kmax + 1, 2))
        es = [round(e_inf + amp * math.exp(-b * k) + gauss(rng, 0, 1.5e-5), 6) for k in meshes]
        delta = abs(es[-1] - es[-2]) * 1000.0
        monotone = all(x > y for x, y in zip(es, es[1:]))
        if monotone and 0.05 < delta < 0.8:
            break
    else:
        raise RuntimeError("no converged dft series")
    inst.params = {"material": material, "kmax": kmax}
    return assemble(mod, inst, {"data/kpoints.csv": csv_bytes(["kmesh", "energy_ev_per_atom"],
                                                               [[k, "%.6f" % e] for k, e in zip(meshes, es)])})


def regenerate(inst, variant, rng):
    return None


def summary(p, inst: Instance) -> str:
    m, k = inst.params["material"], inst.params["kmax"]
    return (
        f"# k-point convergence of the total energy of {m}\n\n"
        f"Total energies of {m} were computed with the PBE functional on {p.n('n_points')} "
        f"Monkhorst-Pack meshes from 2x2x2 to {k}x{k}x{k}. The total energy decreases "
        "monotonically as the mesh is refined; between the last two meshes it changes by "
        f"{p.n('delta_last')}, below the 1 meV/atom threshold, so the run is converged. "
        f"The energy on the densest mesh is {p.n('energy_per_atom')}.\n")


SPEC = {
    "d03": ("energy_per_atom", "kJ/mol"),
    "d07": None,
    "d08": {"above_max": ("energy_per_atom", 23.0), "below_min": ("energy_per_atom", -230.0)},
    "d10_targets": ["energy_per_atom"],
    "wrong_rows": None,
    "n_quantity": "n_points",
    "direction": ("The total energy decreases", "The total energy increases"),
    "method": ("with the PBE functional", "with the PBEsol functional"),
    "d13": [],
    "has_split": False,
}
