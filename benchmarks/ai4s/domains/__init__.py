"""Domain templates for the AI4S audit corpus (DESIGN.md §2.1).

Each domain module exposes ``build_clean(rng, seed) -> Instance`` and a
``SPEC`` dict the planters read (which quantity a unit swap targets, which
sentence carries the direction word, ...). This package holds what every
domain shares: the ``Instance`` record, the splice that turns
``analysis/<domain>.py`` + ``analysis/_helpers.py`` into the committed
``scripts/analyse.py``, and ``assemble``, which RUNS that exact script text
in-process to produce ``results.json``/``results.txt`` so a clean instance is
reproducible from its own files.

**Annotation quote target (decided by testing the shipped matcher).** The
``crossaudit-numbers`` rows quote ``results.txt``, one ``name = value unit``
line per quantity, and not ``results.json``: ``numbers.contains_pair`` does not
accept JSON punctuation between a value and its unit (``84.2, "unit":
"kJ/mol"`` holds no ``84.2 kJ/mol`` pair), so a results.json line can never
satisfy a row with a unit. Dimensionless quantities are written without a
unit in results.txt and annotated with ``u: ""``.

Honest boundary: the templates are synthetic and well-formed by construction;
nothing here models how a real generator lays out an increment.
"""
from __future__ import annotations

import hashlib
import json
import types
from dataclasses import dataclass, field, replace
from pathlib import Path

DATE = "2026-10-21"
CODE_VERSION = "a1b2c3d4e5f6"
OLD_REVISION = "0f9e8d7c6b5a"
ENVIRONMENT = "CPython 3.10 or later, standard library only"

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
AUDIT_RULES_TEMPLATE = REPO / "src" / "crossaudit" / "scaffold" / "templates" / "AUDIT_RULES.md"

DOMAIN_NAMES = ["crystal_bandgap_ml", "nmr_shift_calibration", "arrhenius_kinetics",
                "dft_convergence", "xrd_bragg", "biostat_two_group"]


@dataclass
class Instance:
    """One audited scope: files keyed by path relative to the instance root.

    ``params`` are the data-generation parameters (kept so a planter can
    regenerate a dataset under a different effect); ``analysis_seed`` is the
    ``--seed`` the committed command line passes to scripts/analyse.py.
    """
    domain: str
    seed: int
    slug: str
    exp: str
    files: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    analysis_seed: int = 0

    def copy(self) -> "Instance":
        return replace(self, files=dict(self.files), params=json.loads(json.dumps(self.params)))

    def path(self, rel: str) -> str:
        """Instance-root path of a file named relative to the experiment dir."""
        return f"{self.exp}/{rel}"

    def text(self, rel: str) -> str:
        return self.files[self.path(rel)].decode("utf-8")

    def results(self) -> dict:
        return json.loads(self.files[self.path("results.json")])


_ANALYSIS_CACHE: dict = {}


def analysis_source(domain: str) -> str:
    """The committed scripts/analyse.py text for a domain."""
    body = (HERE / "analysis" / f"{domain}.py").read_text(encoding="utf-8")
    helpers = (HERE / "analysis" / "_helpers.py").read_text(encoding="utf-8")
    assert body.count("#@HELPERS\n") == 1, domain
    return body.replace("#@HELPERS\n", helpers)


def analysis_module(domain: str):
    """Execute the exact committed script text as a module (not its __main__)."""
    if domain not in _ANALYSIS_CACHE:
        src = analysis_source(domain)
        mod = types.ModuleType(f"ai4s_analysis_{domain}")
        exec(compile(src, f"<{domain}:scripts/analyse.py>", "exec"), mod.__dict__)
        _ANALYSIS_CACHE[domain] = (src, mod)
    return _ANALYSIS_CACHE[domain]


def get(domain: str):
    """The domain module by name."""
    import importlib
    return importlib.import_module(f"{__name__}.{domain}")


def instance_seed(generation_seed: int, domain: str, index: int) -> int:
    """A per-instance integer seed: sha256 of the generation seed, domain and index."""
    digest = hashlib.sha256(f"{generation_seed}:{domain}:{index}".encode()).hexdigest()
    return int(digest[:16], 16)


def gauss(rng, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Box-Muller normal deviate from rng.random() only, so the stream does not
    depend on the CPython version's gauss implementation."""
    import math
    u1 = rng.random()
    while u1 <= 1e-300:
        u1 = rng.random()
    u2 = rng.random()
    return mu + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def metadata_yml(mod, inst: Instance) -> str:
    inputs = [f"{rel}@{CODE_VERSION}" for rel in mod.INPUTS] + [f"scripts/analyse.py@{CODE_VERSION}"]
    lines = [f"code_version: {CODE_VERSION}", "inputs:"]
    lines += [f"  - {item}" for item in inputs]
    lines += [f"command: {_yaml_str(f'python3 scripts/analyse.py --seed {inst.analysis_seed}')}",
              f"environment: {_yaml_str(ENVIRONMENT)}",
              f"seed: {inst.analysis_seed}",
              f"method: {_yaml_str(mod.METHOD)}"]
    return "\n".join(lines) + "\n"


def ranges_block(ranges: list) -> str:
    body = ",\n ".join(json.dumps(r, ensure_ascii=False) for r in ranges)
    return "```crossaudit-ranges\n[" + body + "]\n```\n"


PACK_RULES = """\
### CA-PHYS-001
**BLOCKER.** Every reported quantity named in the ranges block below carries
exactly the declared unit and lies inside the declared physical range.

### CA-NUM-005
**BLOCKER.** Every reported value is a finite number.

### CA-DERIV-001
**BLOCKER.** A quantity with a declared derivation equals that derivation,
recomputed from the committed data, within the declared tolerance.

### CA-STAT-004
**BLOCKER.** A declared statistical or comparative claim is true of the
reported quantities.

### CA-PREC-001
**ADVISORY.** A value is not written to more decimal places than its stated
uncertainty supports (one place beyond the uncertainty's first significant
digit).
"""


def audit_rules(mod) -> str:
    text = AUDIT_RULES_TEMPLATE.read_text(encoding="utf-8").replace("<PROJECT>", mod.PROJECT)
    extra = PACK_RULES + "\n" + mod.DOMAIN_RULES.rstrip("\n") + "\n"
    if getattr(mod, "SPLIT_RULE", False):
        extra += ("\n### CA-ML-001\n**BLOCKER.** Train and test sets are disjoint by id and by\n"
                  "group, every id exists in the data, and no id repeats within a set.\n")
    extra += ("\n## Declared physical ranges\n\nThe deterministic layer reads this block "
              "(name, unit, inclusive bounds).\n\n" + ranges_block(mod.RANGES))
    return text.rstrip("\n") + "\n\n" + extra


class Prose:
    """Collects annotated numbers while a SUMMARY is written: ``n(name)``
    returns the value as results.txt writes it (plus the unit, if any) and
    records the crossaudit-numbers row that quotes results.txt for it."""

    def __init__(self, inst: Instance, results: dict):
        self.inst = inst
        self.q = {q["name"]: q for q in results["quantities"]}
        self.rows: list = []

    def v(self, name: str) -> str:
        return json.dumps(self.q[name]["value"])

    def u(self, name: str) -> str:
        unit = self.q[name]["unit"]
        return "" if unit == "1" else unit

    def unc(self, name: str) -> str:
        """The quantity's uncertainty as prose: fixed-point, two significant figures."""
        u = self.q[name]["uncertainty"]
        import math
        d = max(0, -int(math.floor(math.log10(abs(u)))) + 1)
        return "%.*f" % (d, u)

    def n(self, name: str) -> str:
        v, u = self.v(name), self.u(name)
        line = f"{name} = {v}" + (f" {u}" if u else "")
        self.rows.append({"v": v, "u": u, "src": {"file": self.inst.path("results.txt"), "quote": line}})
        return f"{v} {u}" if u else v


def numbers_block(rows: list) -> str:
    body = ",\n ".join(json.dumps(r, ensure_ascii=False) for r in rows)
    return "```crossaudit-numbers\n[" + body + "]\n```\n"


def render_summary(mod, inst: Instance) -> str:
    prose = Prose(inst, inst.results())
    text = mod.summary(prose, inst)
    return text.rstrip("\n") + "\n\n" + numbers_block(prose.rows)


def assemble(mod, inst: Instance, inputs: dict) -> Instance:
    """Write every file of a clean instance from its input files.

    Runs the committed analysis text in-process on exactly the bytes being
    committed, so results.json is what ``python3 scripts/analyse.py`` prints.
    """
    src, analysis = analysis_module(mod.NAME)
    files = {
        "TASK.md": mod.TASK.encode("utf-8"),
        "AUDIT_RULES.md": audit_rules(mod).encode("utf-8"),
        inst.path("metadata.yml"): metadata_yml(mod, inst).encode("utf-8"),
        inst.path("scripts/analyse.py"): src.encode("utf-8"),
    }
    for rel, data in inputs.items():
        files[inst.path(rel)] = data
    inst.files = files
    rerun_analysis(inst)
    return inst


def rerun_analysis(inst: Instance, summary: bool = True) -> Instance:
    """Re-run the committed analysis over the instance's current inputs and
    rewrite its outputs (and, by default, its SUMMARY)."""
    mod = get(inst.domain)
    _src, analysis = analysis_module(inst.domain)
    outputs = analysis.run(lambda rel: inst.files[inst.path(rel)], inst.analysis_seed)
    for rel, data in outputs.items():
        inst.files[inst.path(rel)] = data
    if summary:
        inst.files[inst.path("SUMMARY.md")] = render_summary(mod, inst).encode("utf-8")
    return inst


def new_instance(mod, seed: int, rng) -> Instance:
    return Instance(domain=mod.NAME, seed=seed, slug=mod.SLUG,
                    exp=f"experiments/{DATE}-{mod.SLUG}",
                    analysis_seed=int(rng.random() * 90000) + 10000)


def csv_bytes(header: list, rows: list) -> bytes:
    lines = [",".join(header)] + [",".join(str(c) for c in r) for r in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def shuffled(rng, seq: list) -> list:
    """Fisher-Yates over rng.random() only (version-stable)."""
    out = list(seq)
    for i in range(len(out) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        out[i], out[j] = out[j], out[i]
    return out


def uniform(rng, lo: float, hi: float) -> float:
    return lo + (hi - lo) * rng.random()


def qvalue(results: dict, name: str):
    for q in results["quantities"]:
        if q["name"] == name:
            return q["value"]
    raise KeyError(name)
