#!/usr/bin/env python3
"""P4 readings: ceiling 1's correct stratum, re-read through ceiling 1's own code path.

Registered in `fpadj/PREREGISTRATION.md` (37ae487) before any call. The path is
`explore.run_detector` with key ("holistic", "cross", d), exactly as `ceiling.py` ran it; two
things differ and nothing else:

* caches go to `records/fpadj/cache/`, so ceiling 1's cache is never written;
* `audit2.holistic_one` is wrapped so each BLOCKER observation text -- which that path computes
  and then pops before caching -- is appended to the study-data archive first.

    python fpadj/audit.py --plan        # identity check and counts, no calls
    python fpadj/audit.py               # the run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE.parent / "expertlongbench"))

import audit as study1  # noqa: E402
import audit2  # noqa: E402
import explore  # noqa: E402
from corpus import load_problems  # noqa: E402

RECORDS = CODE / "records"
FP = RECORDS / "fpadj"
CEILING_CACHE = RECORDS / "ceiling" / "cache"
CEILING_RUN = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs"
OUT = Path.home() / "Documents/Crossaudit/study-data/wt-fpadj-runs"
K = 8
HALT_USD = 12.0            # registered audit halt


class FailClosedSpend(explore.Spend):
    """`explore.Spend` sums `api_value_usd` and reads a missing field as free. This programme's
    budget guard has been blind three times; this one halts if the ledger shows readings of this
    study and no cost on any of them."""

    def total(self) -> float:
        from crossaudit import usage
        n_events = 0
        for ledger in list(self.ledgers):
            if ledger.exists():
                events, _ = usage.read_events(ledger)
                n_events += sum(1 for e in events
                                if str(e.get("run_id") or "").startswith(self.prefix))
        total = super().total()
        if n_events and total == 0.0:
            raise SystemExit(f"HALT: {n_events} ledger events for {self.prefix} and no cost on "
                             "any; refusing to spend against a guard that cannot see money")
        return total


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_solutions() -> dict[str, dict]:
    out = {}
    for batch in ("b1", "b2"):
        for line in (CEILING_RUN / f"study2-inputs/solutions-{batch}.jsonl").read_text(
                encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out[f"{batch}:{row['problem_id']}"] = row
    return out


def ceiling_digests() -> dict[str, set[str]]:
    """solution_sha256 of every instance ceiling 1's cross route audited, over all its draws."""
    seen: dict[str, set[str]] = {}
    for path in sorted(CEILING_CACHE.glob("holistic__cross__d*.jsonl")):
        if ".failed." in path.name:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                seen.setdefault(r["instance_id"], set()).add(r["solution_sha256"])
    return seen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0,
                    help="run only the first N of draw 1 -- real readings of the registered\n"
                         "design, used once to prove the text capture before buying the rest")
    args = ap.parse_args(argv)

    explore.EXPLORE = FP
    (FP / "cache").mkdir(parents=True, exist_ok=True)
    instances = explore.load_instances()
    audit_set = explore.load_audit_set()
    scope = [i for i in audit_set if instances[i]["stratum"] == "C"]
    if len(scope) != 150:
        raise SystemExit(f"HALT: correct stratum has {len(scope)} instances, registered 150")

    solutions = load_solutions()
    digests = ceiling_digests()
    bad = [i for i in scope
           if digests.get(i) != {sha(solutions[i]["solution"])}]
    print(f"identity: {len(scope) - len(bad)} of {len(scope)} candidates byte-identical to "
          f"what ceiling 1's cross route audited", flush=True)
    if bad:
        raise SystemExit(f"HALT: {len(bad)} candidates differ from ceiling 1's, e.g. {bad[:3]}")

    have = {d: {json.loads(l)["instance_id"]
                for l in (FP / "cache" / f"holistic__cross__d{d}.jsonl").read_text(
                    encoding="utf-8").splitlines() if l.strip()}
            if (FP / "cache" / f"holistic__cross__d{d}.jsonl").exists() else set()
            for d in range(1, K + 1)}
    todo = {d: [i for i in scope if i not in have[d]] for d in range(1, K + 1)}
    if args.limit:
        todo = {d: (v[:args.limit] if d == 1 else []) for d, v in todo.items()}
    print("to run: " + ", ".join(f"d{d} {len(v)}" for d, v in todo.items()), flush=True)
    if args.plan:
        return 0

    from run import load_credentials
    load_credentials()
    study1.register_visible_tests_check()
    constitution = study1.shipped_constitution()
    problems = {p.problem_id: p for p in load_problems()}

    OUT.mkdir(parents=True, exist_ok=True)
    texts_path = OUT / "blocker_texts.jsonl"
    lock = threading.Lock()
    real = audit2.holistic_one

    def capturing(cfg, problem, solution, inst, constitution_, run_id, arm):
        row = real(cfg, problem, solution, inst, constitution_, run_id, arm)
        if row.get("ok"):
            with lock, texts_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"instance_id": inst["instance_id"], "run_id": run_id,
                                     "detector": arm, "flagged": row.get("flagged"),
                                     "blocker_texts": row.get("blocker_texts") or []},
                                    sort_keys=True) + "\n")
        return row

    audit2.holistic_one = capturing
    spend = FailClosedSpend(f"fpadj-{time.strftime('%m%d%H%M%S', time.gmtime())}-")
    scratch = OUT / "projects"
    scratch.mkdir(parents=True, exist_ok=True)
    cfg_cache: dict = {}
    for d in range(1, K + 1):
        if not todo[d]:
            continue
        if spend.total() >= HALT_USD:
            print(f"HALT: ${spend.total():.2f} at or over the registered ${HALT_USD}")
            return 2
        print(f"\ncross d{d}: {len(todo[d])} instances  (spend ${spend.total():.3f})", flush=True)
        explore.run_detector(("holistic", "cross", d), todo[d], instances=instances,
                             problems=problems, solutions=solutions, constitution=constitution,
                             cfg_cache=cfg_cache, scratch=scratch, spend=spend,
                             budget_usd=HALT_USD, workers=args.workers,
                             property_cache_path=CEILING_RUN / "study2-inputs/properties.json")

    missing = []
    for d in range(1, K + 1):
        p = FP / "cache" / f"holistic__cross__d{d}.jsonl"
        got = {json.loads(l)["instance_id"] for l in p.read_text(encoding="utf-8").splitlines()
               if l.strip()} if p.exists() else set()
        missing += [(i, d) for i in scope if i not in got]
    print(f"\nspend this invocation ${spend.total():.3f}")
    if missing:
        print(f"INCOMPLETE: {len(missing)} of {150 * K} readings missing, e.g. {missing[:4]}. "
              "Re-run; the analysis must not be computed over this state.")
        return 4
    print(f"complete: 150 x K={K} readings present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
