"""Feasibility gate for E7 (no model calls): per task, the reference passes its whole suite, the extracted call
arguments evaluate (test prologue in scope), and the reference is deterministic on them under the comparator."""
from __future__ import annotations

import base64
import json
import pickle
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import corpus7

EXEC = sys.argv[1]
RUNNER = r'''
import sys, json, pickle, base64, signal, copy
spec = json.load(open(sys.argv[1]))
ns = {}
exec(spec["prologue"], ns)
inputs, bad = [], 0
for src in spec["calls"]:
    try:
        inputs.append(eval(src, dict(ns)))
    except Exception:
        bad += 1
exec(spec["comparator"], ns)
ref = {}
exec(spec["reference"], ref)
fn = ref[spec["entry"]]
def run(x):
    signal.alarm(10)
    try:
        v = fn(*copy.deepcopy(x)); signal.alarm(0); return "ok", v
    except Exception as e:
        signal.alarm(0); return "exc:" + type(e).__name__, None
ok = det = 0
for x in inputs:
    a, b = run(x), run(x)
    if a[0] == "ok":
        ok += 1
        try:
            ns["assertion"](a[1], b[1], 1e-9); det += 1
        except Exception:
            pass
json.dump({"n_calls": len(spec["calls"]), "unevaluable": bad, "ref_ok": ok, "deterministic": det,
           "pickles": sum(1 for x in inputs if _try(x))}, open(spec["out"], "w"))
'''
RUNNER = RUNNER.replace('"pickles": sum(1 for x in inputs if _try(x))', '"pickles": sum(1 for x in inputs if _p(x))')
RUNNER = "def _p(x):\n    import pickle\n    try:\n        pickle.dumps(x); return True\n    except Exception:\n        return False\n" + RUNNER


def one(t):
    with tempfile.TemporaryDirectory() as tmp:
        suite = subprocess.run([EXEC, "-c", t.hidden_program(t.canonical_solution)[0]], capture_output=True,
                               text=True, timeout=300, cwd=tmp)
        spec = {"prologue": t.prologue(), "calls": t.call_args(), "comparator": corpus7.COMPARATOR,
                "reference": t.canonical_solution, "entry": t.entry_point, "out": str(Path(tmp) / "o.json")}
        Path(tmp, "s.json").write_text(json.dumps(spec))
        Path(tmp, "r.py").write_text(RUNNER)
        try:
            subprocess.run([EXEC, str(Path(tmp, "r.py")), str(Path(tmp, "s.json"))], capture_output=True, text=True,
                           timeout=300, cwd=tmp)
            res = json.loads(Path(tmp, "o.json").read_text())
        except Exception as e:  # noqa: BLE001
            res = {"error": type(e).__name__}
    return {"task_id": t.problem_id, "split": corpus7.split_of(t.problem_id), "suite_passes": suite.returncode == 0,
            **res}


if __name__ == "__main__":
    tasks = corpus7.load_tasks()
    with ThreadPoolExecutor(3) as ex:
        rows = list(ex.map(one, tasks))
    Path("feasibility.json").write_text(json.dumps(rows, indent=1))
    good = [r for r in rows if r.get("suite_passes") and r.get("deterministic", 0) >= 3
            and r.get("pickles", 0) >= 3]
    print("tasks", len(rows), "reference passes suite", sum(r.get("suite_passes", False) for r in rows),
          "usable (suite passes, >=3 deterministic picklable inputs)", len(good),
          "dev", sum(r["split"] == "dev" for r in good), "test", sum(r["split"] == "test" for r in good))
