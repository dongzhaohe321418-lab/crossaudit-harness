"""Score an AI4S run directory into ``numbers.json`` — every quantity the report quotes.

    PYTHONPATH=../../src python score.py records/run-2026-10-21
    PYTHONPATH=../../src python score.py --check-coverage     # rewrites coverage_check.json

Reads ``rows.jsonl`` and ``run.json`` written by ``run_checks.py`` and computes,
in pure Python (no numpy), the analysis of ``DESIGN.md`` §5:

* per-class and per-(class, variant) recall per profile, planted instances only
  (caught decided per instance by run_checks.classify from its expected.severity),
  each with its n and a 95% Wilson score interval (z = 1.959963984540054);
* class-averaged recall per profile: the unweighted mean over the classes
  present in the run (17 on the full corpus);
* the primary contrast, extended minus shipped class-averaged recall, with a
  percentile interval from a **cluster bootstrap over pair_id** (templates
  resampled with replacement, both class averages recomputed on the resampled
  instances, 2,000 resamples, seed 20261021);
* false-block rate per profile on clean instances (Wilson) with per-check and
  per-rule attribution of every false block;
* any-blocker recall, attribution accuracy (among any-block instances, the
  fraction where an expected rule fired), advisory-only detection, the rules
  that fired per class, wall time, and the H1/H2 decisions against DESIGN §1.

The bootstrap interval's coverage is not assumed. ``simulate_coverage`` measures
it on a corpus-shaped design (EXPERIMENT_RECORD §10); ``--check-coverage``
records the measurement in ``coverage_check.json`` and ``score`` copies it into
``numbers.json`` as ``primary.coverage_checked``. A missing record, or a measured
coverage outside 0.93–0.97, makes the interval "uncalibrated" in the report.

Honest boundary: this is arithmetic over recorded rows. It cannot tell whether a
row's ``caught`` is right (``run_checks.classify`` decides that, and its tests
check it), and the class average weights a 10-instance class the same as a
200-instance one by design (§5), which is a choice, not a fact about science.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COVERAGE_RECORD = HERE / "coverage_check.json"

Z95 = 1.959963984540054
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261021
PERCENTILES = (2.5, 97.5)
SHIPPED, EXTENDED = "science", "science-ai4s"

#: DESIGN §1 thresholds, decided before the run.
H1_THRESHOLD = 0.50              # shipped class-averaged recall below this
H2_DELTA = 0.30                  # extended - shipped at least this
H2_FALSE_BLOCK_UPPER = 0.025     # extended false-block Wilson upper bound at most this

#: EXPERIMENT_RECORD §10 coverage band and the simulation that checks it.
COVERAGE_BAND = (0.93, 0.97)
COVERAGE_SIMS = 300
COVERAGE_RESAMPLES = 400
COVERAGE_SEED = 20261021
COVERAGE_SIGMA = 1.0             # template random effect, logit scale


# ------------------------------------------------------------------ statistics

def wilson(k: int, n: int, z: float = Z95) -> tuple[float | None, float | None]:
    """95% Wilson score interval for k successes in n; (None, None) when n == 0."""
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cell(k: int, n: int) -> dict:
    low, high = wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else None,
            "wilson_low": low, "wilson_high": high}


def percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile (Hyndman–Fan type 7) of a sorted list, q in [0, 100]."""
    if not sorted_values:
        raise ValueError("percentile of an empty list")
    h = (len(sorted_values) - 1) * q / 100.0
    lo = math.floor(h)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (h - lo) * (sorted_values[hi] - sorted_values[lo])


class PackedClusters:
    """Per-cluster (k_shipped, k_extended, n) for every class, packed into one int.

    A resample is then a sum of m Python ints (C speed) plus one unpack, which is
    what makes 2,000 resamples here and 240,000 in the coverage test cheap with
    no numpy. All fields are non-negative counts, so packed addition is exact as
    long as no field overflows its width, which the width is chosen to prevent.
    """

    def __init__(self, table: list[dict[str, tuple[int, int, int]]], classes: list[str]):
        self.classes = list(classes)
        biggest = max([max(v) for row in table for v in row.values()] + [1])
        self.width = (biggest * max(len(table), 1)).bit_length() + 1
        self.mask = (1 << self.width) - 1
        self.packed = []
        for row in table:
            value = 0
            for i, c in enumerate(self.classes):
                ks, ke, n = row.get(c, (0, 0, 0))
                base = 3 * i * self.width
                value |= (ks << base) | (ke << (base + self.width)) | (n << (base + 2 * self.width))
            self.packed.append(value)

    def delta(self, total: int) -> float | None:
        """Extended minus shipped class-averaged recall over classes with n > 0."""
        w, m = self.width, self.mask
        rs = re = 0.0
        present = 0
        for i in range(len(self.classes)):
            base = 3 * i * w
            n = (total >> (base + 2 * w)) & m
            if n:
                rs += ((total >> base) & m) / n
                re += ((total >> (base + w)) & m) / n
                present += 1
        return (re - rs) / present if present else None

    def bootstrap(self, resamples: int, seed: int) -> list[float]:
        rng = random.Random(seed)
        k = len(self.packed)
        out = []
        for _ in range(resamples):
            d = self.delta(sum(rng.choices(self.packed, k=k)))
            if d is not None:
                out.append(d)
        out.sort()
        return out


def cluster_bootstrap(table: list[dict[str, tuple[int, int, int]]], classes: list[str],
                      resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED
                      ) -> dict:
    """Point delta and percentile interval from resampling clusters with replacement."""
    pc = PackedClusters(table, classes)
    point = pc.delta(sum(pc.packed))
    dist = pc.bootstrap(resamples, seed)
    return {"delta": point,
            "ci_low": percentile(dist, PERCENTILES[0]) if dist else None,
            "ci_high": percentile(dist, PERCENTILES[1]) if dist else None,
            "resamples": resamples, "resamples_used": len(dist)}


# ------------------------------------------------------------------ coverage

def _expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def _marginal(p: float, sigma: float) -> float:
    """E[expit(logit(p) + u)], u ~ N(0, sigma^2), by trapezoid quadrature on ±8 sigma."""
    if sigma == 0:
        return p
    a, steps = _logit(p), 4000
    lo, hi = -8 * sigma, 8 * sigma
    h = (hi - lo) / steps
    total = 0.0
    for i in range(steps + 1):
        u = lo + i * h
        w = math.exp(-0.5 * (u / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))
        total += (0.5 if i in (0, steps) else 1.0) * w * _expit(a + u)
    return total * h


def coverage_design(scenario: str) -> dict:
    """The corpus-shaped design: taxonomy classes, domains, variants and catch rates.

    ``null``: every class has the same catch probability under both profiles
    (a spread of 0.05 / 0.5 / 0.95 across classes); draws are independent per
    profile, since with the superset coupling the real profiles have a null
    delta would be identically zero and the interval degenerate.
    ``effect``: shipped catches existing-tier classes at 0.9 and others at 0.05;
    extended adds the new-tier classes at 0.60, giving a class-averaged delta
    near 0.30; draws share one uniform per instance, so extended catches
    whatever shipped catches (the superset structure of science-ai4s).
    """
    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    domains = tax["domains"]
    seeds = int(tax.get("seeds_per_domain", 10))
    classes = []
    for i, c in enumerate(tax["classes"]):
        doms = domains if c["domains"] == "all" else list(c["domains"])
        tier = c["tier"]
        if scenario == "null":
            ps = pe = (0.05, 0.5, 0.95)[i % 3]
        elif scenario == "effect":
            ps = 0.9 if tier == "deterministic_existing" else 0.05
            pe = 0.60 if tier == "deterministic_new" else ps
        else:
            raise ValueError(scenario)
        classes.append({"id": c["id"], "domains": doms, "m": len(c["variants"]),
                        "ps": ps, "pe": pe})
    truth = sum(_marginal(c["pe"], COVERAGE_SIGMA) - _marginal(c["ps"], COVERAGE_SIGMA)
                for c in classes) / len(classes)
    return {"scenario": scenario, "domains": domains, "seeds": seeds,
            "classes": classes, "coupled": scenario == "effect",
            "sigma": COVERAGE_SIGMA, "true_delta": truth}


def simulate_corpus(design: dict, rng: random.Random) -> list[dict[str, tuple[int, int, int]]]:
    """One simulated corpus: per template, per class, (k_shipped, k_extended, n)."""
    table = []
    for d in design["domains"]:
        for _ in range(design["seeds"]):
            u = rng.gauss(0.0, design["sigma"])
            row = {}
            for c in design["classes"]:
                if d not in c["domains"]:
                    continue
                ps = _expit(_logit(c["ps"]) + u)
                pe = _expit(_logit(c["pe"]) + u)
                ks = ke = 0
                for _ in range(c["m"]):
                    if design["coupled"]:
                        x = rng.random()
                        ks += x < ps
                        ke += x < pe
                    else:
                        ks += rng.random() < ps
                        ke += rng.random() < pe
                row[c["id"]] = (ks, ke, c["m"])
            table.append(row)
    return table


def simulate_coverage(scenario: str, sims: int = COVERAGE_SIMS,
                      resamples: int = COVERAGE_RESAMPLES, seed: int = COVERAGE_SEED) -> dict:
    """Empirical coverage of the cluster-bootstrap percentile interval for the true delta."""
    design = coverage_design(scenario)
    ids = [c["id"] for c in design["classes"]]
    rng = random.Random(f"{seed}-{scenario}")
    hits, widths = 0, []
    for s in range(sims):
        table = simulate_corpus(design, rng)
        pc = PackedClusters(table, ids)
        dist = pc.bootstrap(resamples, rng.randrange(2**31))
        lo, hi = percentile(dist, PERCENTILES[0]), percentile(dist, PERCENTILES[1])
        hits += lo <= design["true_delta"] <= hi
        widths.append(hi - lo)
    return {"scenario": scenario, "sims": sims, "resamples": resamples, "seed": seed,
            "templates": len(design["domains"]) * design["seeds"],
            "classes": len(ids), "sigma": design["sigma"],
            "true_delta": design["true_delta"], "coverage": hits / sims,
            "mean_width": sum(widths) / len(widths)}


def coverage_record() -> dict:
    runs = [simulate_coverage("null"), simulate_coverage("effect")]
    passed = all(COVERAGE_BAND[0] <= r["coverage"] <= COVERAGE_BAND[1] for r in runs)
    return {"band": list(COVERAGE_BAND), "runs": runs, "passed": passed,
            "method": "cluster bootstrap over templates, percentile interval "
                      f"{PERCENTILES[0]}/{PERCENTILES[1]}"}


def load_coverage(path: Path = COVERAGE_RECORD) -> dict:
    if not path.is_file():
        return {"coverage_checked": False, "coverage": None,
                "coverage_note": "no coverage_check.json; run score.py --check-coverage"}
    rec = json.loads(path.read_text(encoding="utf-8"))
    runs = {r["scenario"]: r for r in rec.get("runs", [])}
    return {"coverage_checked": bool(rec.get("passed")),
            "coverage": {k: {"coverage": v["coverage"], "true_delta": v["true_delta"],
                             "sims": v["sims"], "resamples": v["resamples"],
                             "templates": v["templates"], "classes": v["classes"]}
                         for k, v in runs.items()},
            "coverage_band": rec.get("band")}


# ------------------------------------------------------------------ scoring

def read_rows(run_dir: Path) -> list[dict]:
    return [json.loads(line) for line in
            (run_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def _taxonomy() -> dict:
    return json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))


def _class_order(c: str) -> tuple:
    return (len(c), c)


def score(run_dir: Path | str, coverage_path: Path = COVERAGE_RECORD) -> dict:
    run_dir = Path(run_dir)
    rows = read_rows(run_dir)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    tax = _taxonomy()
    tax_classes = {c["id"]: c for c in tax["classes"]}
    profiles = list(run.get("profiles", {}).keys())
    shipped = SHIPPED if SHIPPED in profiles else None
    extended = EXTENDED if EXTENDED in profiles else None

    planted = [r for r in rows if not r["clean"]]
    clean = [r for r in rows if r["clean"]]
    present = sorted({r["defect_class"] for r in planted}, key=_class_order)

    numbers: dict = {
        "schema": 1,
        "confidence": 0.95,
        "z": Z95,
        "profiles": {"shipped": SHIPPED, "extended": EXTENDED, "run": profiles,
                     "unknown": run.get("unknown_profiles", [])},
        "classes": {c: {"name": tax_classes.get(c, {}).get("name"),
                        "tier": tax_classes.get(c, {}).get("tier"),
                        "rules": tax_classes.get(c, {}).get("rules", []),
                        "checks": tax_classes.get(c, {}).get("checks", []),
                        "severity": tax_classes.get(c, {}).get("severity"),
                        "variant_tiers": tax_classes.get(c, {}).get("variant_tiers", {})}
                    for c in present},
        "counts": {**run.get("counts", {}), "rows": len(rows),
                   "rows_by_profile": {p: sum(1 for r in rows if r["profile"] == p)
                                       for p in profiles}},
    }

    recall_c, recall_cv, anyb_c, attr_c, fired = {}, {}, {}, {}, {}
    for c in present:
        recall_c[c], anyb_c[c], attr_c[c], fired[c], recall_cv[c] = {}, {}, {}, {}, {}
        crow = [r for r in planted if r["defect_class"] == c]
        variants = sorted({r["variant"] for r in crow})
        for p in profiles:
            pr = [r for r in crow if r["profile"] == p]
            recall_c[c][p] = cell(sum(1 for r in pr if r["caught"]), len(pr))
            anyb_c[c][p] = cell(sum(1 for r in pr if r["any_block"]), len(pr))
            blocked = [r for r in pr if r["any_block"]]
            attr_c[c][p] = cell(sum(1 for r in blocked if r["attributed"]), len(blocked))
            codes: dict[str, int] = {}
            for r in pr:
                # instances per rule; an advisory is labelled so it never reads as a block
                for code in sorted({(f["implementation_code"] or f["rule"])
                                    + ("" if f["severity"] == "BLOCKER" else ":ADVISORY")
                                    for f in r["findings"]}):
                    codes[code] = codes.get(code, 0) + 1
            fired[c][p] = dict(sorted(codes.items()))
        for v in variants:
            recall_cv[c][v] = {}
            for p in profiles:
                pr = [r for r in crow if r["profile"] == p and r["variant"] == v]
                recall_cv[c][v][p] = cell(sum(1 for r in pr if r["caught"]), len(pr))

    class_avg = {}
    for p in profiles:
        rates = [recall_c[c][p]["rate"] for c in present if recall_c[c][p]["n"]]
        class_avg[p] = {"value": (sum(rates) / len(rates)) if rates else None,
                        "n_classes": len(rates), "classes": present}

    overall, anyb_overall, attr_overall, adv_only = {}, {}, {}, {}
    for p in profiles:
        pr = [r for r in planted if r["profile"] == p]
        overall[p] = cell(sum(1 for r in pr if r["caught"]), len(pr))
        anyb_overall[p] = cell(sum(1 for r in pr if r["any_block"]), len(pr))
        blocked = [r for r in pr if r["any_block"]]
        attr_overall[p] = cell(sum(1 for r in blocked if r["attributed"]), len(blocked))
        adv_only[p] = cell(sum(1 for r in pr if r["findings"] and all(
            f["severity"] == "ADVISORY" for f in r["findings"])), len(pr))

    numbers["recall"] = {"by_class": recall_c, "by_class_variant": recall_cv,
                         "class_avg": class_avg, "overall": overall}
    numbers["any_block"] = {"by_class": anyb_c, "overall": anyb_overall}
    numbers["attribution"] = {"by_class": attr_c, "overall": attr_overall,
                              "definition": "among any-block planted instances, the "
                                            "fraction where an expected rule or check fired"}
    numbers["advisory_only"] = adv_only
    numbers["fired"] = {"by_class": fired}

    false_block = {}
    for p in profiles:
        pr = [r for r in clean if r["profile"] == p]
        blocked = [r for r in pr if r["any_block"]]
        by_check: dict[str, int] = {}
        by_code: dict[str, int] = {}
        for r in blocked:
            for chk in sorted({f["check"] or "?" for f in r["findings"] if f["severity"] == "BLOCKER"}):
                by_check[chk] = by_check.get(chk, 0) + 1
            for code in sorted({f["implementation_code"] or f["rule"]
                                for f in r["findings"] if f["severity"] == "BLOCKER"}):
                by_code[code] = by_code.get(code, 0) + 1
        c_ = cell(len(blocked), len(pr))
        false_block[p] = {"count": c_["k"], "n": c_["n"], "rate": c_["rate"],
                          "wilson_low": c_["wilson_low"], "wilson_high": c_["wilson_high"],
                          "by_check": dict(sorted(by_check.items())),
                          "by_code": dict(sorted(by_code.items())),
                          "instances": sorted(r["instance_id"] for r in blocked)}
    numbers["false_block"] = false_block

    cov = load_coverage(coverage_path)
    if shipped and extended:
        by_pair: dict[str, dict[str, list[int]]] = {}
        for r in planted:
            if r["profile"] not in (shipped, extended):
                continue
            slot = by_pair.setdefault(r["pair_id"], {}).setdefault(r["defect_class"], [0, 0, 0])
            if r["profile"] == shipped:
                slot[0] += bool(r["caught"])
                slot[2] += 1
            else:
                slot[1] += bool(r["caught"])
        table = [{c: tuple(v) for c, v in by_pair[k].items()} for k in sorted(by_pair)]
        boot = cluster_bootstrap(table, present)
        numbers["primary"] = {
            **boot, "seed": BOOTSTRAP_SEED, "clusters": len(table),
            "percentiles": list(PERCENTILES),
            "method": "cluster bootstrap over pair_id, percentile interval",
            "available": True, **cov}
    else:
        numbers["primary"] = {"available": False, "delta": None, "ci_low": None,
                              "ci_high": None, "resamples": BOOTSTRAP_RESAMPLES,
                              "seed": BOOTSTRAP_SEED, "clusters": 0,
                              "percentiles": list(PERCENTILES),
                              "reason": "both the shipped and the extended profile must be "
                                        "in the run", **cov}

    h1_value = class_avg.get(shipped, {}).get("value") if shipped else None
    h2_fb = false_block.get(extended, {}).get("wilson_high") if extended else None
    delta = numbers["primary"]["delta"]
    numbers["claims"] = {
        "H1": {"threshold": H1_THRESHOLD, "value": h1_value,
               "decidable": h1_value is not None,
               "holds": (h1_value < H1_THRESHOLD) if h1_value is not None else None},
        "H2": {"delta_threshold": H2_DELTA, "false_block_upper_threshold": H2_FALSE_BLOCK_UPPER,
               "delta": delta, "false_block_upper": h2_fb,
               # stated secondary condition, NOT part of the preregistered rule
               "ci_low": numbers["primary"]["ci_low"],
               "ci_low_above_zero": (numbers["primary"]["ci_low"] > 0)
               if numbers["primary"]["ci_low"] is not None else None,
               "decidable": delta is not None and h2_fb is not None,
               "holds": (delta >= H2_DELTA and h2_fb <= H2_FALSE_BLOCK_UPPER)
               if delta is not None and h2_fb is not None else None},
    }

    wall = {}
    for p in profiles:
        ws = [r["wall_ms"] for r in rows if r["profile"] == p]
        wall[p] = {"mean": (sum(ws) / len(ws)) if ws else None,
                   "max": max(ws) if ws else None, "n": len(ws)}
    numbers["wall_ms"] = wall
    numbers["errors"] = {"by_profile": {p: sum(1 for r in rows if r["profile"] == p
                                               and r.get("error")) for p in profiles},
                         "run": run.get("errors", [])}
    numbers["replicate_identical"] = run.get("replicate_identical")
    numbers["environment"] = {
        **run.get("environment", {}),
        "generation_seed": (run.get("generation_seed") or {}).get("value"),
        "generation_seed_source": (run.get("generation_seed") or {}).get("source"),
        "corpus_manifest_sha256": run.get("corpus_manifest_sha256"),
        "taxonomy_sha256": run.get("taxonomy_sha256"),
        "checks_contracts_sha256": run.get("checks_contracts_sha256"),
        "rows_sha256": hashlib.sha256((run_dir / "rows.jsonl").read_bytes()).hexdigest(),
        "utc_start": run.get("utc_start"), "utc_end": run.get("utc_end"),
    }
    return numbers


def write_numbers(run_dir: Path | str, numbers: dict) -> Path:
    path = Path(run_dir) / "numbers.json"
    path.write_text(json.dumps(numbers, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", nargs="?", type=Path)
    ap.add_argument("--check-coverage", action="store_true",
                    help="run the coverage simulation and rewrite coverage_check.json")
    args = ap.parse_args(argv)
    if args.check_coverage:
        rec = coverage_record()
        COVERAGE_RECORD.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n",
                                   encoding="utf-8")
        print(json.dumps({r["scenario"]: round(r["coverage"], 4) for r in rec["runs"]}
                         | {"passed": rec["passed"]}))
    if args.run_dir:
        path = write_numbers(args.run_dir, score(args.run_dir))
        print(path)
    if not args.check_coverage and not args.run_dir:
        ap.error("give a run directory, --check-coverage, or both")
    return 0


if __name__ == "__main__":
    sys.exit(main())
