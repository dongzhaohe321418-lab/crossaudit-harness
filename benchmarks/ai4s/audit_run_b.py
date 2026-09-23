#!/usr/bin/env python3
"""A4S-1b: A4S-1's instances and program bytes, with the step's function as the deliverable.

Registered in `PREREGISTRATION-CODE-B.md`. Everything is A4S-1's runner (`audit_run.py`) except
three module-level values, replaced before `main()` runs: the task text (`instance`), the output
directory, and the halt. The program returned by `instance` is A4S-1's, byte for byte; the check
below asserts that for every instance before any call is made.

    python benchmarks/ai4s/audit_run_b.py --plan
    python benchmarks/ai4s/audit_run_b.py --family cross --workers 6
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_run as a  # noqa: E402

_a1_instance = a.instance


def instance_b(iid: str, probs: dict, gen: dict) -> tuple[str, str]:
    _task_a1, program = _a1_instance(iid, probs, gen)
    pid, step1, _s = iid.rsplit(".", 2)
    p = probs[pid]
    st = p["sub_steps"][int(step1) - 1]
    task = (f"Deliver the function for step {st['step_number']} of a multi-step scientific "
            f"programming problem.\n\n"
            f"Step {st['step_number']}: {st['step_description_prompt']}\n\n"
            f"Background:\n{st['step_background']}\n\n"
            f"Function to implement:\n{st['function_header']}\n{st['return_line']}\n\n"
            f"Allowed dependencies:\n{p['required_dependencies']}\n\n"
            f"The file also contains the functions written for the earlier steps of this problem, "
            f"which this step may call; they are given, not part of this step's deliverable. The "
            f"overall problem, for context only (later steps will complete it):\n"
            f"{p['problem_description_main']}\n")
    return task, program


a.instance = instance_b
a.OUT = a.AI4S / "runs/audit_b"
a.HALT_USD = 40.0

if __name__ == "__main__":
    raise SystemExit(a.main())
