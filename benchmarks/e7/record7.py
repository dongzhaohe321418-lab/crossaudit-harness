"""Record the entry point's actual arguments while the reference runs its own whole suite (E7 hidden inputs)."""
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
WRAP = r'''
import copy as _copy, pickle as _pickle, atexit as _atexit, base64 as _b64
_orig_entry = {entry}
_recorded = []
def {entry}(*args, **kwargs):
    if not kwargs:
        try:
            _recorded.append(_pickle.dumps(_copy.deepcopy(args)))
        except Exception:
            pass
    return _orig_entry(*args, **kwargs)
def _dump():
    with open({out!r}, "w") as fh:
        fh.write("\n".join(_b64.b64encode(x).decode() for x in _recorded))
_atexit.register(_dump)
'''
DET = r'''
import sys, json, pickle, base64, signal, copy
spec = json.load(open(sys.argv[1]))
ns = {}
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
keep = []
for line in open(spec["calls"]).read().split():
    x = pickle.loads(base64.b64decode(line))
    a, b = run(x), run(x)
    if a[0] == "ok":
        try:
            ns["assertion"](a[1], b[1], 1e-9); keep.append(line)
        except Exception:
            pass
open(spec["out"], "w").write("\n".join(keep))
'''


def one(t):
    with tempfile.TemporaryDirectory() as tmp:
        rec = str(Path(tmp) / "calls.txt")
        prog = t.canonical_solution + "\n" + WRAP.format(entry=t.entry_point, out=rec) + "\n" + t._test + (
            "\nimport unittest\nunittest.main(argv=['x'], verbosity=0, exit=False)\n")
        subprocess.run([EXEC, "-c", prog], capture_output=True, text=True, timeout=300, cwd=tmp)
        n = len(Path(rec).read_text().split()) if Path(rec).exists() else 0
        keep = []
        if n:
            spec = {"comparator": corpus7.COMPARATOR, "reference": t.canonical_solution, "entry": t.entry_point,
                    "calls": rec, "out": str(Path(tmp) / "keep.txt")}
            Path(tmp, "s.json").write_text(json.dumps(spec))
            Path(tmp, "d.py").write_text(DET)
            subprocess.run([EXEC, str(Path(tmp, "d.py")), str(Path(tmp, "s.json"))], capture_output=True, text=True,
                           timeout=300, cwd=tmp)
            if Path(tmp, "keep.txt").exists():
                keep = [x for x in Path(tmp, "keep.txt").read_text().split() if x]
    return {"task_id": t.problem_id, "split": corpus7.split_of(t.problem_id), "n_recorded": n,
            "hidden_inputs_b64": sorted(set(keep))}


if __name__ == "__main__":
    feas = {r["task_id"]: r for r in json.loads(Path("feasibility.json").read_text())}
    tasks = [t for t in corpus7.load_tasks() if feas[t.problem_id].get("suite_passes")]
    with ThreadPoolExecutor(3) as ex:
        rows = list(ex.map(one, tasks))
    Path("hidden_inputs.json").write_text(json.dumps(rows))
    good = [r for r in rows if len(r["hidden_inputs_b64"]) >= 3]
    print("suite-passing tasks", len(rows), "with >=3 distinct deterministic recorded inputs", len(good),
          "dev", sum(r["split"] == "dev" for r in good), "test", sum(r["split"] == "test" for r in good))
