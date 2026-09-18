"""The gate the two previous failures both needed: RUN what the models are shown.

Study 23 has now voided two runs on the same fault — the text shown to the auditor and the
generator was not the suite the scorer executed:

  * Amendment 1: methods sliced out of their class; 300 of 300 failed to parse.
  * Amendment 6: the repair kept a hidden method's decorators in the "class header" and
    re-attached them to the first visible method; 26 of 300 gained mock arguments and raised
    TypeError at run time while parsing cleanly.

Every gate written so far inspects the displayed text — does it parse, does its digest match,
does its AST equal the intact class. Those are proxies. The property the study depends on is
that **the displayed suite behaves the same as the scored suite**, and behaviour is settled by
running it, not by reading it.

So this executes both, against the benchmark's own canonical solution, and requires the same
outcome. It costs no model calls.

    python benchmarks/code/substrate2/verify_execution.py [--limit N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import execute  # noqa: E402
from substrate2 import corpus2  # noqa: E402

FRAME = HERE.parent / "records" / "substrate2" / "frame.json"


def displayed_program(task, solution: str) -> str:
    """The same assembly the scorer uses, but over the text the MODELS were shown."""
    argv = ", ".join(repr(m) for m in task._visible)
    return (f"{solution}\n\n{task.visible_tests_text()}\n\n"
            f"import unittest\nunittest.main(argv=['x', {argv}], verbosity=0, exit=True)\n")


def check(limit: int | None = None) -> list[str]:
    tasks = corpus2.load_frame(FRAME)
    if limit:
        tasks = tasks[:limit]
    bad: list[str] = []
    for i, task in enumerate(tasks, 1):
        solution = task.canonical_solution
        scored = execute.run_suite(task.visible_program(solution), instrumented=False)
        shown = execute.run_suite(displayed_program(task, solution), instrumented=False)
        if scored.passed != shown.passed or scored.timed_out != shown.timed_out:
            first = (shown.error or "").strip().splitlines()
            bad.append(f"{task.problem_id}: scored passed={scored.passed} "
                       f"shown passed={shown.passed} :: {first[-1][:110] if first else ''}")
        if i % 50 == 0:
            print(f"  executed {i}/{len(tasks)}  ({len(bad)} divergent)", flush=True)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    bad = check(args.limit)
    if bad:
        print(f"\nHALT: {len(bad)} tasks where the displayed suite does not behave like the "
              f"scored one:")
        for line in bad[:10]:
            print(f"  {line}")
        return 1
    print("\nexecution equivalence verified: the displayed suite and the scored suite agree "
          "on the canonical solution for every frame task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
