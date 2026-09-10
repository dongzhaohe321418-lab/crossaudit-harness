"""Study 23 §2 — the audit ladder on substrate 2.

    python benchmarks/code/substrate2/audit2_sub.py --plan  <run-dir>
    python benchmarks/code/substrate2/audit2_sub.py --run   <run-dir> --budget-usd 60

Ceiling 1's protocol unchanged, over substrate 2's instances: the shipped cross-vendor auditor
holistically, K = 8, then the same-vendor family at K = 8 if budget remains. The audit set —
every stratum-P instance up to 200, drawn by seed where there are more, plus a C sample of 150 —
is frozen to `records/substrate2/audit_set.json` before the first audit call and never redrawn.
Every reading is cached by (kind, route, draw, instance) and never bought twice. `src/` is
untouched; no corpus text and no finding text is committed.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE.parent / "expertlongbench"))

import audit as study1  # noqa: E402
import explore  # noqa: E402
from corpus2 import load_frame  # noqa: E402

RECORDS = CODE / "records" / "substrate2"
SEED = 20260917
MAX_P, N_C = 200, 150
LADDER = [("cross", d) for d in range(1, 9)] + [("self", d) for d in range(1, 9)]


def load_instances() -> dict[str, dict]:
    rows = {}
    for line in (RECORDS / "instances.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["instance_id"]] = row
    return rows


def freeze_audit_set(instances: dict[str, dict]) -> dict:
    """§2's scope, drawn once by seed and committed before the first audit call."""
    path = RECORDS / "audit_set.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    by_stratum: dict[str, list[str]] = {}
    for iid, row in instances.items():
        by_stratum.setdefault(row["stratum"], []).append(iid)
    chosen: dict[str, list[str]] = {}
    for stratum, cap in (("P", MAX_P), ("C", N_C)):
        ids = sorted(by_stratum.get(stratum, []))
        chosen[stratum] = sorted(rng.sample(ids, cap)) if len(ids) > cap else ids
    out = {"seed": SEED, "caps": {"P": MAX_P, "C": N_C},
           "population": {s: len(v) for s, v in sorted(by_stratum.items())},
           "audited": {s: len(v) for s, v in chosen.items()},
           "instance_ids": sorted(chosen["P"] + chosen["C"]),
           "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--budget-usd", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--max-passes", type=int, default=6)
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    explore.EXPLORE = RECORDS
    (RECORDS / "cache").mkdir(parents=True, exist_ok=True)
    instances = load_instances()
    audit_set = freeze_audit_set(instances)
    scope = audit_set["instance_ids"]
    scope_set = set(scope)
    print(f"population {audit_set['population']}; audited {audit_set['audited']}", flush=True)

    have = {("holistic", f, d): explore.load_detector(("holistic", f, d), scope_set)
            for f, d in LADDER}
    if args.plan:
        for f, d in LADDER:
            print(f"ladder {f} d{d}: {len(scope) - len(have[('holistic', f, d)])} to run")
        return 0

    from run import load_credentials
    load_credentials()
    study1.register_visible_tests_check()
    constitution = study1.shipped_constitution()
    problems = {t.problem_id: t for t in load_frame(RECORDS / "frame.json")}
    solutions: dict[str, dict] = {}
    for batch in sorted({instances[i]["batch"] for i in scope}):
        path = run_dir / "solutions" / f"solutions-{batch}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row

    scratch = run_dir / "projects"
    scratch.mkdir(parents=True, exist_ok=True)
    spend = explore.Spend(f"sub2-{time.strftime('%m%d%H%M%S', time.gmtime())}-")
    for family, draw in LADDER:
        key = ("holistic", family, draw)
        missing = [i for i in scope if i not in have[key]]
        if not missing:
            print(f"ladder {family} d{draw}: already complete")
            continue
        total = spend.total()
        if args.budget_usd and total >= args.budget_usd:
            print(f"\nSTOP: spend ${total:.3f} reached the ${args.budget_usd:.2f} cap; "
                  f"{family} d{draw} not run")
            break
        print(f"\nladder {family} d{draw}: {len(missing)} instances (spend ${total:.3f})",
              flush=True)
        explore.run_detector(key, missing, instances=instances, problems=problems,
                             solutions=solutions, constitution=constitution, cfg_cache={},
                             scratch=scratch, spend=spend, budget_usd=args.budget_usd,
                             workers=args.workers,
                             property_cache_path=run_dir / "properties.json",
                             max_passes=args.max_passes)
        have[key] = explore.load_detector(key, scope_set)
        print(f"  {family} d{draw}: {len(have[key])} of {len(scope)}; "
              f"spend ${spend.total():.3f}", flush=True)
    print(f"\nstudy-23 spend this invocation: ${spend.total():.4f}", flush=True)
    manifest = {"study": "study23 / substrate 2", "ladder": LADDER, "scope_n": len(scope),
                "draws_complete": {f"{f}-d{d}": len(have[("holistic", f, d)]) for f, d in LADDER},
                "spend_usd_this_invocation": round(spend.total(), 6),
                "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (RECORDS / f"manifest-{manifest['written_utc'].replace(':', '')}.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
