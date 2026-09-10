"""Study 23 §2 — generate candidates on substrate 2 and score them into strata.

    python benchmarks/code/substrate2/generate2.py --run <run-dir> --batches g1 g2

Study 2's prompt shape (the specification and the visible tests, nothing else), study 2's
generator, and ceiling 1's stratum definitions. Solutions live in the run archive; what is
committed is `records/substrate2/instances.jsonl` — ids, hashes, strata and suite outcomes,
never code.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE.parent / "expertlongbench"))

import audit as study1  # noqa: E402
import execute  # noqa: E402
import explore  # noqa: E402
from corpus2 import load_frame, sha  # noqa: E402

RECORDS = CODE / "records" / "substrate2"
GENERATOR = "anthropic:claude-haiku-4-5-20251001"

SYSTEM = (
    "You are an expert Python programmer. You write correct, complete, self-contained "
    "solutions.\n\n"
    "Reply with exactly one fenced Python code block and no other text. The block must "
    "contain the complete solution — every import it needs and the full function "
    "definition — so that it runs as written."
)
USER = ("Complete this Python function. Reproduce the signature and the docstring exactly, "
        "then write the body.\n\n```python\n{spec}\n```\n\n"
        "Your code must satisfy these tests:\n\n```python\n{tests}\n```")

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def extract_code(text: str) -> str:
    blocks = _FENCE.findall(text or "")
    return (blocks[0] if blocks else (text or "")).strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--batches", nargs="+", default=["g1", "g2"])
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--budget-usd", type=float, default=60.0)
    args = ap.parse_args(argv)

    from crossaudit.config import load
    from provider import CrossAuditClient
    from run import load_credentials

    load_credentials()
    tasks = load_frame(RECORDS / "frame.json")
    print(f"frame {len(tasks)} tasks x {len(args.batches)} batches", flush=True)
    run_dir = Path(args.run)
    (run_dir / "solutions").mkdir(parents=True, exist_ok=True)
    scratch = run_dir / "projects"
    scratch.mkdir(parents=True, exist_ok=True)
    explore.ROUTES["substrate2-gen"] = GENERATOR
    project = explore.build_project(scratch, ("holistic", "substrate2-gen", 0),
                                    study1.shipped_constitution())
    cfg = load(project / "crossaudit.yml")
    client = CrossAuditClient(cfg=cfg, phase="substrate2-gen", run_id="substrate2-gen",
                              allow_custom=True)

    instances: list[dict] = []
    for batch in args.batches:
        path = run_dir / "solutions" / f"solutions-{batch}.jsonl"
        done = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    done[row["problem_id"]] = row
        todo = [t for t in tasks if t.problem_id not in done]
        print(f"batch {batch}: {len(todo)} to generate", flush=True)

        def one(task):
            user = USER.format(spec=task.spec.rstrip(), tests=task.visible_tests_text().rstrip())
            started = time.monotonic()
            row = {"problem_id": task.problem_id, "benchmark": task.benchmark,
                   "model": GENERATOR, "prompt_sha256": sha(SYSTEM + "\n" + user)}
            try:
                completion = client.complete(model=GENERATOR, system=SYSTEM, user=user)
            except Exception as exc:  # noqa: BLE001
                row.update({"solution": "", "error": f"{type(exc).__name__}: {exc}",
                            "wall_s": time.monotonic() - started})
                return row
            code = extract_code(completion.text)
            row.update({"solution": code, "solution_sha256": sha(code),
                        "response_sha256": sha(completion.text or ""), "error": "",
                        "wall_s": time.monotonic() - started,
                        "cost_usd": float(completion.cost_usd),
                        "input_tokens": int(completion.input_tokens),
                        "output_tokens": int(completion.output_tokens)})
            return row

        with ThreadPoolExecutor(max_workers=args.workers) as pool, \
                open(path, "a", encoding="utf-8") as fh:
            for n, row in enumerate(pool.map(one, todo), 1):
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
                done[row["problem_id"]] = row
                if n % 25 == 0:
                    print(f"  {n}/{len(todo)}", flush=True)

        def score(task):
            row = done.get(task.problem_id) or {}
            solution = row.get("solution") or ""
            if not solution:
                return {"instance_id": f"{batch}:{task.problem_id}", "batch": batch,
                        "problem_id": task.problem_id, "stratum": "F",
                        "solution_sha256": row.get("solution_sha256", ""),
                        "note": "generation failed", "visible": None, "hidden": None}
            visible = execute.run_suite(task.visible_program(solution), timeout=args.timeout,
                                        instrumented=False)
            program, instrumented = task.hidden_program(solution)
            hidden = execute.run_suite(program, timeout=args.timeout, instrumented=instrumented)
            stratum = "F" if not visible.passed else ("C" if hidden.passed else "P")
            return {"instance_id": f"{batch}:{task.problem_id}", "batch": batch,
                    "problem_id": task.problem_id, "stratum": stratum,
                    "solution_sha256": row.get("solution_sha256", ""),
                    "visible": visible.as_dict(), "hidden": hidden.as_dict()}

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for n, row in enumerate(pool.map(score, tasks), 1):
                instances.append(row)
                if n % 50 == 0:
                    print(f"  scored {n}/{len(tasks)}", flush=True)

    instances.sort(key=lambda r: r["instance_id"])
    RECORDS.mkdir(parents=True, exist_ok=True)
    (RECORDS / "instances.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in instances), encoding="utf-8")
    counts: dict[str, int] = {}
    for row in instances:
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
    spend = sum(float((r.get("cost_usd") or 0)) for b in args.batches
                for r in map(json.loads, (run_dir / "solutions" / f"solutions-{b}.jsonl")
                             .read_text(encoding="utf-8").splitlines()) if r)
    print(f"\nstrata {counts}; generation spend ${spend:.3f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
