#!/usr/bin/env python3
"""Execute SciCode subproblems against the scientists' tests, with targets from test_data.h5.

Mirrors SciCode's own eval/inspect_ai/scicode.py test assembly: the program for step k is the code
of steps 1..k (the caller supplies it), then `targets = process_hdf5_to_tuple(step_id, n)`, then each
test case with `target = targets[i]` bound before it. Run in a subprocess with a timeout.

    python harness/scicode_exec.py --gate     # gold code on the dev split: every step must pass
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

AI4S = Path(__file__).resolve().parents[1]
H5 = AI4S / "gdrive/test_data.h5"
SRC = AI4S / "SciCode/src"
PY = AI4S / ".venv/bin/python"
SKIP = {("13", 5), ("62", 0), ("76", 2)}   # the official harness skips these three steps


def load(split: str) -> list[dict]:
    return [json.loads(l) for l in (AI4S / f"data/problems_{split}.jsonl").read_text().splitlines() if l.strip()]


def program(code: str, step: dict) -> str:
    head = ("\nfrom scicode.parse.parse import process_hdf5_to_tuple\n"
            f"targets = process_hdf5_to_tuple('{step['step_number']}', {len(step['test_cases'])}, '{H5}')\n")
    body = "".join(f"target = targets[{i}]\n\n{t}\n" for i, t in enumerate(step["test_cases"]))
    return code + "\n" + head + body


def run(prog: str, timeout: float = 600.0) -> tuple[str, str]:
    """('pass'|'fail'|'timeout', last stderr line)."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "t.py"
        f.write_text(prog, encoding="utf-8")
        env = {"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"}
        try:
            cp = subprocess.run([str(PY), str(f)], cwd=d, capture_output=True, text=True,
                                timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return "timeout", ""
        last = (cp.stderr.strip().splitlines() or [""])[-1][:160]
        return ("pass" if cp.returncode == 0 else "fail"), last


def gold_code(prob: dict, upto: int) -> str:
    parts = []
    for i, s in enumerate(prob["sub_steps"][: upto + 1]):
        parts.append(s.get("ground_truth_code") or "")
    return "\n\n".join(parts)


def gate() -> int:
    rows = load("dev")
    res = {"pass": 0, "fail": 0, "timeout": 0}
    bad = []
    for p in rows:
        for k, s in enumerate(p["sub_steps"]):
            if (p["problem_id"], k) in SKIP:
                continue
            code = "\n".join(p.get("required_dependencies", "").splitlines()) + "\n\n" + gold_code(p, k)
            st, err = run(program(code, s))
            res[st] += 1
            if st != "pass":
                bad.append((s["step_number"], st, err))
    print(res)
    for b in bad[:10]:
        print("  ", b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if "--gate" in sys.argv:
        raise SystemExit(gate())
    print(__doc__)
