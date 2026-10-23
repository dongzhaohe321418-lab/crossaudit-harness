"""Builds tests/fixtures/mini_corpus, the hand-built fixture the runner tests read.

Run from the repository root: python benchmarks/ai4s/tests/fixtures/build_mini_corpus.py \
    benchmarks/ai4s/tests/fixtures/mini_corpus
The output is committed; this script is kept so the fixture can be regenerated and
reviewed. Honest boundary: the fixture only exercises the shipped `science` profile
(D01, D02, D04, D05 caught; D08 and the ADVISORY-tier D16 missed), not the pack.
"""
import hashlib, json, math, shutil, sys
from pathlib import Path

OUT = Path(sys.argv[1])
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

RULES_BASE = """# Audit rules

### CA-META-001
BLOCKER. Every increment declares metadata.yml and results.json.

### CA-DATA-001
BLOCKER. Every quantity carries a unit and a source.

### CA-DATA-002
BLOCKER. Prose agrees with the data and the declared method.

### CA-DATA-003
BLOCKER. Every source is a declared, committed input.

### CA-METH-002
BLOCKER. Unconverged numbers are not results.

### CA-NUM-002
BLOCKER. An annotated number resolves to the line that holds it.

### CA-PHYS-001
BLOCKER. Quantities obey the declared physical ranges.

### CA-REPRO-001
ADVISORY. Stochastic work declares command, environment and seed.

```crossaudit-ranges
%s
```
"""

def q_line(q):
    return "    " + json.dumps(q, separators=(", ", ": "))

def results_json(quantities, extra):
    lines = ["{", '  "quantities": [']
    lines.append(",\n".join(q_line(q) for q in quantities))
    lines.append("  ]" + ("," if extra else ""))
    items = list(extra.items())
    for i, (k, v) in enumerate(items):
        lines.append(f'  "{k}": {json.dumps(v)}' + ("," if i < len(items) - 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"

def summary(title, sentences, rows):
    body = f"# {title}\n\n" + "\n".join(sentences) + "\n\n```crossaudit-numbers\n"
    body += json.dumps(rows, indent=1) + "\n```\n"
    return body

# ---------------------------------------------------------------- arrhenius
R = 8.314462618
T = [300, 320, 340, 360, 380, 400]
Ea, lnA = 84.21e3, 30.0
k = [math.exp(lnA - Ea / (R * t)) for t in T]
EXP_A = "experiments/2026-10-21-arrhenius"

def arrhenius_files(seed_in_meta=True):
    rates = "T_K,k_per_s\n" + "".join(f"{t},{kk:.6e}\n" for t, kk in zip(T, k))
    src = "data/rates.csv@v1"
    qs = [
        {"name": "activation_energy", "value": 84.21, "unit": "kJ/mol", "source": src, "display": "84.21 kJ/mol"},
        {"name": "ln_prefactor", "value": 30.0, "unit": "1", "source": src},
        {"name": "n", "value": 6, "unit": "1", "source": src},
    ]
    meta = ("code_version: v1\ninputs:\n  - data/rates.csv@v1\n"
            "command: python scripts/analyse.py\nenvironment: python3.11 stdlib\n")
    if seed_in_meta:
        meta += "seed: 1\n"
    ranges = json.dumps([{"name": "activation_energy", "unit": "kJ/mol", "min": 0, "max": 500},
                         {"name": "n", "unit": "1", "min": 1}])
    return {
        "TASK.md": "Fit an Arrhenius model to the measured rate constants and report Ea.\n",
        "AUDIT_RULES.md": RULES_BASE % ranges,
        f"{EXP_A}/metadata.yml": meta,
        f"{EXP_A}/data/rates.csv": rates,
        f"{EXP_A}/scripts/analyse.py": "# stdlib-only re-run of the Arrhenius fit\nprint('fit')\n",
        f"{EXP_A}/results.json": results_json(qs, {"stochastic": True}),
        f"{EXP_A}/SUMMARY.md": summary(
            "Arrhenius fit",
            ["The fitted activation energy is 84.21 kJ/mol over 6 temperatures."],
            [{"v": "84.21", "u": "kJ/mol",
              "src": {"file": f"{EXP_A}/results.json",
                      "quote": '"display": "84.21 kJ/mol"'}}]),
    }

# ---------------------------------------------------------------- dft
EXP_D = "experiments/2026-10-21-dft"

def dft_files():
    kp = "kmesh,energy_ev_per_atom\n4,-5.4012\n6,-5.4101\n8,-5.4110\n10,-5.4112\n"
    src = "data/kpoints.csv@v1"
    qs = [
        {"name": "energy_per_atom", "value": -5.4112, "unit": "eV/atom", "source": src, "display": "-5.4112 eV/atom"},
        {"name": "delta_last", "value": 0.2, "unit": "meV/atom", "source": src},
        {"name": "n_points", "value": 4, "unit": "1", "source": src},
    ]
    meta = ("code_version: v1\ninputs:\n  - data/kpoints.csv@v1\n"
            "command: python scripts/analyse.py\nenvironment: python3.11 stdlib\n")
    ranges = json.dumps([{"name": "n_points", "unit": "1", "min": 2}])
    return {
        "TASK.md": "Converge the total energy per atom against k-point density.\n",
        "AUDIT_RULES.md": RULES_BASE % ranges,
        f"{EXP_D}/metadata.yml": meta,
        f"{EXP_D}/data/kpoints.csv": kp,
        f"{EXP_D}/scripts/analyse.py": "# stdlib-only convergence table\nprint('conv')\n",
        f"{EXP_D}/results.json": results_json(
            qs, {"convergence": {"converged": True, "achieved": 0.2, "threshold": 1.0}}),
        f"{EXP_D}/SUMMARY.md": summary(
            "k-point convergence",
            ["The energy converged to -5.4112 eV/atom."],
            [{"v": "-5.4112", "u": "eV/atom",
              "src": {"file": f"{EXP_D}/results.json",
                      "quote": '"display": "-5.4112 eV/atom"'}}]),
    }

TAX = {"D01": ("deterministic_existing", ["CA-META-001"], ["schema"], "BLOCKER"),
       "D02": ("deterministic_existing", ["CA-DATA-001"], ["units"], "BLOCKER"),
       "D04": ("deterministic_existing", ["CA-DATA-003"], ["provenance"], "BLOCKER"),
       "D05": ("deterministic_existing", ["CA-METH-002"], ["convergence"], "BLOCKER"),
       "D08": ("deterministic_new", ["CA-PHYS-001"], ["range_rules"], "BLOCKER"),
       "D16": ("deterministic_new", ["CA-REPRO-001"], ["repro_declared"], "ADVISORY")}

rows = []

def emit(domain, seed, files, cls=None, variant=None, planted=None):
    pair = f"{domain}-s{seed}"
    iid = f"{pair}-clean" if cls is None else f"{pair}-{cls}-{variant}"
    root = OUT / iid
    shas = {}
    for rel in sorted(files):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        data = files[rel].encode("utf-8")
        p.write_bytes(data)
        shas[rel] = hashlib.sha256(data).hexdigest()
    exp = None
    if cls:
        tier, rules, checks, sev = TAX[cls]
        exp = {"tier": tier, "rules": rules, "checks": checks, "severity": sev}
    rows.append({"instance_id": iid, "pair_id": pair, "domain": domain, "seed": seed,
                 "clean": cls is None, "defect_class": cls, "variant": variant,
                 "planted": planted, "expected": exp, "files_sha256": shas})

A = "arrhenius_kinetics"
emit(A, 1, arrhenius_files())
emit("dft_convergence", 1, dft_files())

f = arrhenius_files()
f[f"{EXP_A}/metadata.yml"] = f[f"{EXP_A}/metadata.yml"].replace("code_version: v1\n", "")
emit(A, 1, f, "D01", "no_code_version",
     {"file": f"{EXP_A}/metadata.yml", "locator": "code_version", "before": "v1", "after": None})

f = arrhenius_files()
f[f"{EXP_A}/results.json"] = f[f"{EXP_A}/results.json"].replace('"unit": "1", "source": "data/rates.csv@v1"}', '"unit": "", "source": "data/rates.csv@v1"}', 1)
emit(A, 1, f, "D02", "empty_unit",
     {"file": f"{EXP_A}/results.json", "locator": "quantities[1].unit", "before": "1", "after": ""})

f = arrhenius_files()
del f[f"{EXP_A}/data/rates.csv"]
emit(A, 1, f, "D04", "input_file_missing",
     {"file": f"{EXP_A}/data/rates.csv", "locator": "file", "before": "present", "after": "absent"})

f = arrhenius_files()
f[f"{EXP_A}/results.json"] = f[f"{EXP_A}/results.json"].replace("84.21", "8421.0")
f[f"{EXP_A}/SUMMARY.md"] = f[f"{EXP_A}/SUMMARY.md"].replace("84.21", "8421.0")
emit(A, 1, f, "D08", "above_max",
     {"file": f"{EXP_A}/results.json", "locator": "quantities[0].value", "before": 84.21, "after": 8421.0})

f = arrhenius_files(seed_in_meta=False)
emit(A, 1, f, "D16", "no_seed",
     {"file": f"{EXP_A}/metadata.yml", "locator": "seed", "before": 1, "after": None})

g = dft_files()
g[f"{EXP_D}/results.json"] = g[f"{EXP_D}/results.json"].replace('"converged": true', '"converged": false')
emit("dft_convergence", 1, g, "D05", "converged_false",
     {"file": f"{EXP_D}/results.json", "locator": "convergence.converged", "before": True, "after": False})

with open(OUT / "manifest.jsonl", "w", encoding="utf-8", newline="\n") as fh:
    for r in rows:
        fh.write(json.dumps(r, sort_keys=True) + "\n")
print(len(rows), "instances")
