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
import hashlib
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


def generation_digest(instances: dict[str, dict]) -> str:
    """Which generation of candidates this scope and these readings belong to.

    Amendment 3's guard. `audit_set.json` and `cache/` live in `records/`, which is committed for
    provenance, while the thing that invalidates them -- a new generation -- is selected by
    `--run`, which points at the run directory. So changing the run directory correctly
    invalidated the solutions and did nothing to the audit set or the cache, and both were reused
    across generations by existence alone. The re-run of 2026-09-16 audited a scope frozen from
    the voided generation: of its 250 ids, 92 were still P under the new candidates, 152 were C
    and 6 were F, which fail their own visible suite and must never be audited.

    The digest covers exactly what a reading depends on: which instance, which stratum it is in,
    and which solution text the auditor is shown.
    """
    payload = "\n".join(
        f"{iid}\t{row['stratum']}\t{row.get('solution_sha256', '')}"
        for iid, row in sorted(instances.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_audit_set(instances: dict[str, dict]) -> dict:
    """§2's scope, drawn once by seed and committed before the first audit call.

    Amendment 3: the frozen file records the generation it was drawn from, and a scope drawn
    from a different generation is refused rather than reused.
    """
    path = RECORDS / "audit_set.json"
    current = generation_digest(instances)
    if path.exists():
        frozen = json.loads(path.read_text(encoding="utf-8"))
        was = frozen.get("generation_sha256")
        if was is None:
            raise SystemExit(
                f"HALT: {path} predates Amendment 3 and records no generation digest, so it "
                f"cannot be shown to belong to these candidates. Move it aside deliberately "
                f"(see records/substrate2/cache-void-2026-09-11/README.md) and let it redraw.")
        if was != current:
            raise SystemExit(
                f"HALT: {path} was frozen from a different generation of candidates.\n"
                f"  frozen from: {was}\n"
                f"  present now: {current}\n"
                f"Re-using it would audit a scope whose strata no longer hold. Move it aside and "
                f"let it redraw, and move `cache/` with it -- the readings in it belong to the "
                f"same superseded generation.")
        return frozen
    rng = random.Random(SEED)
    by_stratum: dict[str, list[str]] = {}
    for iid, row in instances.items():
        by_stratum.setdefault(row["stratum"], []).append(iid)
    chosen: dict[str, list[str]] = {}
    for stratum, cap in (("P", MAX_P), ("C", N_C)):
        ids = sorted(by_stratum.get(stratum, []))
        chosen[stratum] = sorted(rng.sample(ids, cap)) if len(ids) > cap else ids
    out = {"seed": SEED, "caps": {"P": MAX_P, "C": N_C},
           "generation_sha256": current,          # Amendment 3
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

    # Amendment 3, the cache half of the same guard. A cached reading records the
    # solution_sha256 it was taken against; a reading of a superseded candidate must not be
    # counted as a reading of this one. This is checked rather than assumed because the readings
    # of 2026-09-16 DID match their candidates -- the auditor read the right code -- while the
    # scope around them did not, so matching solutions are not evidence that a resume is sound.
    stale = [f"{f} d{d}: {iid}"
             for (kind, f, d), rows in have.items()
             for iid, row in rows.items()
             if row.get("solution_sha256")
             and row["solution_sha256"] != instances.get(iid, {}).get("solution_sha256")]
    if stale:
        raise SystemExit(
            f"HALT: {len(stale)} cached readings were taken against a different candidate than "
            f"the one now in instances.jsonl, e.g. {stale[:3]}. Move `cache/` aside; those "
            f"readings belong to a superseded generation.")
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
