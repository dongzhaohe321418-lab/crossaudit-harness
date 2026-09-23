#!/usr/bin/env python3
"""A4S-1 execution: every generated (sample, step) against the scientists' tests; the strata.

Registered in `PREREGISTRATION-CODE.md`. The program for step k of sample s is the dependencies,
sample s's extracted functions for steps 1..k (the benchmark's own code for its three skipped
steps), then the step's tests with targets from `test_data.h5`. Writes the per-instance outcome
and the strata to `records/ai4s/strata.json` (ids, outcomes and hashes only).

    python benchmarks/ai4s/execute.py
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scicode_exec as sx  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
GEN = AI4S / "runs/generation"
EXEC = AI4S / "runs/execution.jsonl"
OUT = HERE.parents[1] / "benchmarks/code/records/ai4s/strata.json"
SEED = 20260925
CAP = 150
GATE_EXCLUDED = {"78.3", "70.8"}     # gold fails in this environment (GATE-RESULT.md)


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def chains() -> dict[tuple[str, int], dict[int, dict]]:
    out: dict = defaultdict(dict)
    for f in GEN.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[(r["problem_id"], r["sample"])][r["step"]] = r
    return out


def main() -> int:
    probs = {p["problem_id"]: p for split in ("dev", "test") for p in sx.load(split)}
    ch = chains()
    done = {}
    if EXEC.exists():
        for line in EXEC.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r["problem_id"], r["sample"], r["step"])] = r
    jobs = []
    for (pid, smp), steps in sorted(ch.items()):
        p = probs[pid]
        for k, s in enumerate(p["sub_steps"]):
            if (pid, k) in sx.SKIP or s["step_number"] in GATE_EXCLUDED:
                continue
            if (pid, smp, k) in done or k not in steps:
                continue
            funcs = []
            ok = True
            for i in range(k + 1):
                if (pid, i) in sx.SKIP:
                    funcs.append((AI4S / f"SciCode/eval/data/{pid}.{i + 1}.txt").read_text(encoding="utf-8"))
                    continue
                r = steps.get(i)
                if not r or not r.get("function"):
                    ok = ok if i < k else False
                    if i == k:
                        break
                    funcs.append("")
                    continue
                funcs.append(r["function"])
            jobs.append((pid, smp, k, s, p, funcs, ok and bool(steps[k].get("function"))))

    def one(job):
        pid, smp, k, s, p, funcs, has_func = job
        if not has_func:
            return {"problem_id": pid, "sample": smp, "step": k, "step_number": s["step_number"],
                    "outcome": "no-function"}
        code = p["required_dependencies"] + "\n\n" + "\n\n".join(funcs)
        status, err = sx.run(sx.program(code, s))
        return {"problem_id": pid, "sample": smp, "step": k, "step_number": s["step_number"],
                "outcome": status, "error": err, "program_sha256": sha(code)}

    with EXEC.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=6) as pool:
        for n, r in enumerate(pool.map(one, jobs), 1):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
            fh.flush()
            if n % 50 == 0:
                print(f"  {n}/{len(jobs)} executed", flush=True)

    rows = [json.loads(l) for l in EXEC.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_step: dict = defaultdict(list)
    for r in rows:
        by_step[r["step_number"]].append(r)
    passable = {st for st, rs in by_step.items() if any(r["outcome"] == "pass" for r in rs)}
    correct = [r for r in rows if r["outcome"] == "pass"]
    defective = [r for r in rows if r["outcome"] in ("fail", "timeout") and r["step_number"] in passable]
    iid = lambda r: f"{r['problem_id']}.{r['step'] + 1}.s{r['sample']}"
    rng = random.Random(SEED)
    pick = lambda xs: sorted(rng.sample(xs, CAP), key=iid) if len(xs) > CAP else sorted(xs, key=iid)
    rec = {
        "readings_executed": len(rows),
        "outcomes": dict(Counter(r["outcome"] for r in rows)),
        "steps_total": len(by_step), "steps_passable": len(passable),
        "correct_pool": len(correct), "defective_pool": len(defective),
        "defective_excluded_unpassable": sum(1 for r in rows if r["outcome"] in ("fail", "timeout")
                                             and r["step_number"] not in passable),
        "seed": SEED, "cap": CAP,
        "correct": [iid(r) for r in pick(correct)],
        "defective": [iid(r) for r in pick(defective)],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in rec.items() if k not in ("correct", "defective")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
