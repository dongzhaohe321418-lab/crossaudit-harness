"""Study 23 §1 — apply S1 and S2 and freeze the frame, before any generation.

    python benchmarks/code/substrate2/freeze_frame.py

S1: every module the task declares is importable in this interpreter.
S2: the task's canonical solution passes the task's OWN full suite here, within the timeout.
Both are mechanical. Writes records/substrate2/frame.json: the surviving tasks with their row
digests and their seeded visible split, every drop with its reason, and the environment that
decided S1. No model call, no spend.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CODE))

import execute  # noqa: E402
from corpus2 import (MIN_METHODS, N_VISIBLE, SPLIT_SEED, declared_libs, load_rows,  # noqa: E402
                     sha, task_from_row, test_methods)

RECORDS = CODE / "records" / "substrate2"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    rows = load_rows()
    seen: dict[str, bool] = {}

    def importable(name: str) -> bool:
        if name not in seen:
            try:
                seen[name] = importlib.util.find_spec(name) is not None
            except Exception:  # noqa: BLE001
                seen[name] = False
        return seen[name]

    drops: list[dict] = []
    s1: list[dict] = []
    for row in rows:
        missing = [m for m in declared_libs(row) if not importable(m)]
        if missing:
            drops.append({"task_id": row["task_id"], "filter": "S1", "missing": sorted(missing)})
        else:
            s1.append(row)

    def check(row: dict) -> tuple[dict, dict | None]:
        task = task_from_row(row)
        if task is None:
            return row, {"task_id": row["task_id"], "filter": "S1b",
                         "reason": f"fewer than {MIN_METHODS} test methods",
                         "n_methods": len(test_methods(row["test"]))}
        program, instrumented = task.hidden_program(task.canonical_solution)
        result = execute.run_suite(program, timeout=args.timeout, instrumented=instrumented)
        if result.passed:
            return row, None
        return row, {"task_id": row["task_id"], "filter": "S2",
                     "timed_out": result.timed_out, "error": (result.error or "")[-200:]}

    frame: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row, drop in pool.map(check, s1):
            if drop is not None:
                drops.append(drop)
                continue
            task = task_from_row(row)
            frame.append({"task_id": row["task_id"],
                          "row_sha256": sha(json.dumps(row, sort_keys=True)),
                          "n_test_methods": len(task._methods),
                          "visible_methods": list(task._visible),
                          "spec_words": len(task.spec.split()),
                          "canonical_lines": len(task.canonical_solution.splitlines())})
    frame.sort(key=lambda e: e["task_id"])

    out = {
        "study": "study23 / substrate 2",
        "dataset": {"name": "bigcode/bigcodebench", "split": "v0.1.4", "licence": "Apache-2.0",
                    "file_sha256": sha((CODE / "data" / "bigcodebench.jsonl").read_text(encoding="utf-8")),
                    "n_rows": len(rows)},
        "split_rule": {"seed": SPLIT_SEED, "n_visible": N_VISIBLE, "min_methods": MIN_METHODS,
                       "hidden": "every test method; hidden contains visible"},
        "n_frame": len(frame), "n_dropped": len(drops),
        "drops_by_filter": {f: sum(1 for d in drops if d["filter"] == f)
                            for f in sorted({d["filter"] for d in drops})},
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "modules_checked": {k: v for k, v in sorted(seen.items())}},
        "frame": frame, "drops": drops,
        "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    RECORDS.mkdir(parents=True, exist_ok=True)
    (RECORDS / "frame.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
    print(f"frame {len(frame)} tasks; dropped {len(drops)} ({out['drops_by_filter']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
