"""Study 19, ceiling 3b — Sonnet 4.6 under two changed constitutions, finding texts archived.

Preregistered in ``ceiling3b/PREREGISTRATION.md`` before the first model call. A driver over
``explore.run_detector`` exactly as ``ceiling3.py``; the two arms are routes that alias the
same model (``self-strong-R``, ``self-strong-B``) so their caches are separate, each run with
its own constitution. The reading function is ``audit2.holistic_one`` wrapped so that EVERY
finding (severity, rule, observation) is appended to a jsonl in the run directory — the
archive, never the repository — and the cache row stays as before (hashes and counts only).

    python benchmarks/code/ceiling3b.py --plan
    python benchmarks/code/ceiling3b.py --run <run-dir> --budget-usd 30
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

import audit as study1  # noqa: E402
import audit2  # noqa: E402
import explore  # noqa: E402
import loop  # noqa: E402
from corpus import load_problems  # noqa: E402

RECORDS = HERE / "records"
CEILING3B = RECORDS / "ceiling3b"
CACHES_BEFORE = (RECORDS / "explore", RECORDS / "ceiling", RECORDS / "ceiling3")

MODEL = "anthropic:claude-sonnet-4-6"
ROUTES = {"self-strong-R": MODEL, "self-strong-B": MODEL, "self-strong-S": MODEL}   # S: Amendment 1, texts archived
explore.ROUTES.update(ROUTES)
explore.ROUTES.setdefault("self-strong", MODEL)

GRADE_RULE = """

### CA-GRADE-001
**BLOCKER.** A finding that names a specific input on which the implementation
returns a value the specification does not allow is a BLOCKER, whatever else it
is; grade it BLOCKER. A finding that names no such input is ADVISORY.
"""

#: (route, draw): the preregistered ladder, set by budget alone (§4).
LADDER = ([("self-strong-R", d) for d in range(1, 5)] + [("self-strong-B", d) for d in range(1, 5)]
          + [("self-strong-S", 1)])   # Amendment 1: one S reading with its texts archived, for H19d only


def constitution_for(route: str, base: str) -> str:
    if route == "self-strong-R":
        return base + loop.REFERENT_RULE
    if route == "self-strong-B":
        return base + GRADE_RULE
    return base


def in_scope(instances: dict, audit_set: list[str]) -> list[str]:
    return [i for i in audit_set if instances[i]["stratum"] in ("P", "C")]


def load_everywhere(key, scope: set[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for directory in (*CACHES_BEFORE, CEILING3B):
        explore.EXPLORE = directory
        found.update(explore.load_detector(key, scope))
    explore.EXPLORE = CEILING3B
    return found


def install_findings_archive(path: Path) -> None:
    """Wrap ``audit2.holistic_one`` so every finding's text lands in ``path`` (the archive)."""
    original = audit2.holistic_one
    lock = threading.Lock()

    def holistic_one_all(cfg, problem, solution, inst, constitution, run_id, arm):
        from crossaudit.auditor.run import run_audit
        files = study1.increment_files(problem, solution)
        study1._VISIBLE_RESULT = {}
        started = time.monotonic()

        def on_event(*_args, **_kwargs):
            return None
        on_event.run_id = run_id
        on_event.heartbeat = lambda: None
        row = audit2.blank_row(arm, inst)
        try:
            outcome = run_audit(cfg=cfg, sha="0" * 40, round_=1, files=files, notes=[],
                                constitution=constitution, constitution_commit="frozen",
                                task=problem.spec, on_event=on_event,
                                usage_context={"run_id": run_id, "arm": arm, "problem_id": problem.problem_id})
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}", "wall_s": time.monotonic() - started})
            return row
        model_findings = ((outcome.model_reply or {}).get("findings") or [])
        dcl_findings = outcome.dcl.get("findings", [])
        blockers = [f for f in model_findings if f.get("severity") == "BLOCKER"]
        dcl_blockers = [f for f in dcl_findings if f.get("severity") == "BLOCKER"]
        row.update({
            "ok": True, "error": "", "verdict": outcome.verdict, "dcl_verdict": outcome.dcl.get("verdict"),
            "dcl_hard_failures": outcome.dcl.get("total_hard_failures", 0),
            "model_findings": len(model_findings), "model_blockers": len(blockers), "dcl_blockers": len(dcl_blockers),
            "model_advisories": sum(1 for f in model_findings if f.get("severity") == "ADVISORY"),
            "flagged": bool(blockers or dcl_blockers), "flagged_by_model": bool(blockers), "flagged_by_checks": bool(dcl_blockers),
            "rules": sorted({f.get("rule", "") for f in blockers}), "dcl_rules": sorted({f.get("rule", "") for f in dcl_blockers}),
            "finding_sha256": [audit2.sha256_text(f.get("observation", "")) for f in blockers],
            "finding_chars": [len(f.get("observation", "")) for f in blockers],
            "blocker_texts": [f.get("observation", "") for f in blockers],
            "invalid_reason": outcome.invalid_reason or "", "prompt_sha256": outcome.prompt_sha256,
            "wall_s": time.monotonic() - started,
        })
        with lock, path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"instance_id": inst["instance_id"], "arm": arm, "run_id": run_id,
                                     "prompt_sha256": outcome.prompt_sha256,
                                     "findings": [{"severity": f.get("severity"), "rule": f.get("rule"),
                                                   "artifact": f.get("artifact"), "observation": f.get("observation", "")}
                                                  for f in model_findings]}, ensure_ascii=False) + "\n")
        return row

    audit2.holistic_one = holistic_one_all
    holistic_one_all.original = original  # type: ignore[attr-defined]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run")
    parser.add_argument("--budget-usd", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max-passes", type=int, default=8)
    args = parser.parse_args(argv)

    explore.EXPLORE = CEILING3B
    (CEILING3B / "cache").mkdir(parents=True, exist_ok=True)
    instances = explore.load_instances()
    audit_set = explore.load_audit_set()
    scope = in_scope(instances, audit_set)
    scope_set = set(scope)
    have = {("holistic", r, d): load_everywhere(("holistic", r, d), scope_set) for r, d in LADDER}
    for r, d in LADDER:
        print(f"  {r} draw {d}: {len(have[('holistic', r, d)]):3d} of {len(scope)}")
    if args.plan:
        return 0
    if not args.run:
        parser.error("--run is required unless --plan")
    run_dir = Path(args.run)

    from run import load_credentials
    load_credentials()
    study1.register_visible_tests_check()
    base = study1.shipped_constitution()
    problems = {p.problem_id: p for p in load_problems()}
    solutions: dict[str, dict] = {}
    for batch in ("b1", "b2"):
        for line in (run_dir / f"study2-inputs/solutions-{batch}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row
    scratch = run_dir / "projects"
    scratch.mkdir(parents=True, exist_ok=True)
    spend = explore.Spend(f"ceiling3b-{time.strftime('%m%d%H%M%S', time.gmtime())}-")

    for route, draw in LADDER:
        key = ("holistic", route, draw)
        missing = [i for i in scope if i not in have[key]]
        if not missing:
            print(f"ladder {route} d{draw}: already complete")
            continue
        total = spend.total()
        if args.budget_usd and total >= args.budget_usd:
            print(f"\nSTOP: spend ${total:.3f} reached the ${args.budget_usd:.2f} cap; {route} d{draw} not run")
            break
        print(f"\nladder {route} d{draw}: {len(missing)} instances (spend so far ${total:.3f})", flush=True)
        install_findings_archive(run_dir / f"findings-{route}-d{draw}.jsonl")
        explore.run_detector(key, missing, instances=instances, problems=problems, solutions=solutions,
                             constitution=constitution_for(route, base), cfg_cache={}, scratch=scratch,
                             spend=spend, budget_usd=args.budget_usd, workers=args.workers,
                             property_cache_path=run_dir / "study2-inputs/properties.json",
                             max_passes=args.max_passes)
        have[key] = load_everywhere(key, scope_set)
        print(f"  {route} d{draw}: {len(have[key])} of {len(scope)}; spend ${spend.total():.3f}", flush=True)
    print(f"\nceiling-3b spend this invocation: ${spend.total():.4f}", flush=True)
    manifest = {"study": "study19 / ceiling 3b", "preregistration": "benchmarks/code/ceiling3b/PREREGISTRATION.md",
                "routes": ROUTES, "ladder": LADDER, "scope_n": len(scope),
                "referent_rule_sha256": audit2.sha256_text(loop.REFERENT_RULE), "grade_rule_sha256": audit2.sha256_text(GRADE_RULE),
                "draws_complete": {f"{r}-d{d}": len(have[("holistic", r, d)]) for r, d in LADDER},
                "spend_usd_this_invocation": round(spend.total(), 6),
                "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (CEILING3B / f"manifest-{manifest['written_utc'].replace(':', '')}.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
