"""Synthetic run directories for the scorer and report tests.

Writes ``rows.jsonl`` and ``run.json`` shaped exactly like ``run_checks.py``'s
output, for designs the fixture corpus cannot produce (both profiles present,
false blocks, many templates). Honest boundary: these rows are invented to
exercise arithmetic; they say nothing about what any check does.
"""
from __future__ import annotations

import json
import random
from pathlib import Path


def _row(iid, pair, cls, variant, profile, caught, blocked, attributed, findings, clean):
    return {"instance_id": iid, "pair_id": pair, "domain": pair.rsplit("-s", 1)[0],
            "clean": clean, "defect_class": cls, "variant": variant, "profile": profile,
            "verdict": "BLOCKED" if blocked else "PASS",
            "hard_failures": sum(1 for f in findings if f["severity"] == "BLOCKER"),
            "scope_started": True, "findings": findings,
            "caught": None if clean else caught, "any_block": blocked,
            "attributed": None if clean else attributed,
            "wall_ms": 1.5, "dcl_version": 3, "corpus_sha256": "0" * 64}


def _f(code, check, severity="BLOCKER"):
    return {"severity": severity, "rule": f"DCL:{check}", "implementation_code": code,
            "check": check, "artifact": "experiments/x/results.json", "observation": "o"}


def write_two_profile_run(run_dir: Path, templates: int = 12, seed: int = 3) -> Path:
    """Two profiles, three classes, clean controls with one false block on the extended profile.

    Class A (D01): both profiles catch every instance.
    Class B (D08): shipped never; extended catches a template-dependent fraction.
    Class C (D16, ADVISORY tier): shipped never; extended catches via an advisory.
    """
    rng = random.Random(seed)
    rows = []
    for t in range(templates):
        pair = f"arrhenius_kinetics-s{t}"
        good = rng.random() < 0.7
        for profile in ("science", "science-ai4s"):
            ext = profile == "science-ai4s"
            fb = ext and t == 0
            rows.append(_row(f"{pair}-clean", pair, None, None, profile, None, fb, None,
                             [_f("CA-PHYS-001", "range_rules")] if fb else [], True))
            rows.append(_row(f"{pair}-D01-no_code_version", pair, "D01", "no_code_version",
                             profile, True, True, True, [_f("CA-META-001", "schema")], False))
            for v in ("above_max", "below_min"):
                hit = ext and (good or v == "above_max")
                rows.append(_row(f"{pair}-D08-{v}", pair, "D08", v, profile, hit, hit, hit,
                                 [_f("CA-PHYS-001", "range_rules")] if hit else [], False))
            rows.append(_row(f"{pair}-D16-no_seed", pair, "D16", "no_seed", profile, ext,
                             False, ext,
                             [_f("CA-REPRO-001", "repro_declared", "ADVISORY")] if ext else [],
                             False))
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "rows.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    run = {"profiles": {"science": ["schema"], "science-ai4s": ["schema", "range_rules"]},
           "unknown_profiles": [], "errors": [], "replicate_identical": True,
           "counts": {"instances": templates * 5, "clean": templates,
                      "planted": templates * 4, "templates": templates},
           "generation_seed": {"value": 20261021, "source": "synthetic"},
           "corpus_manifest_sha256": "1" * 64, "taxonomy_sha256": "2" * 64,
           "checks_contracts_sha256": "3" * 64,
           "environment": {"python": "3.x", "platform": "synthetic",
                           "git": {"sha": "f" * 40, "dirty": False}},
           "utc_start": "2026-10-21T00:00:00+00:00", "utc_end": "2026-10-21T00:00:01+00:00"}
    (run_dir / "run.json").write_text(json.dumps(run, indent=1, sort_keys=True) + "\n",
                                      encoding="utf-8")
    return run_dir
