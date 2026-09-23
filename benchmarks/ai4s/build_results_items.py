#!/usr/bin/env python3
"""A4S-2 items: one clean and one faulty results increment per qualifying correct instance.

Exactly as registered in `PREREGISTRATION-RESULTS.md` with Amendment 1. Items are written to
`~/Documents/Crossaudit/ai4s/runs/results_items/<instance>.<clean|fault>/work/...`; the manifest
(instance, test case, true output, fault, substitutions, hashes, and the shipped `science` profile's
verdict on every item) goes to `records/ai4s/results_items.json`. No model is called.

    python benchmarks/ai4s/build_results_items.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import random
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))
import scicode_exec as sx  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
GEN = AI4S / "runs/generation"
OUT = AI4S / "runs/results_items"
STRATA = REPO / "benchmarks/code/records/ai4s/strata.json"
MANIFEST = REPO / "benchmarks/code/records/ai4s/results_items.json"
SEED = 20260927
UNIT = "dimensionless"
FAULTS = ["R1", "R2", "R3", "R4", "R5", "F1", "F4"]
MAX_ELEMS = 10

RUNNER = r'''
import json, math
import numpy as _np
{inputs}
__out = ({call})
def __flat(x):
    if isinstance(x, (bool, _np.bool_)):
        return None
    if isinstance(x, (int, float, _np.integer, _np.floating)):
        return [float(x), "shape"]
    try:
        a = _np.asarray(x)
    except Exception:
        return None
    if a.dtype.kind not in "iuf" or a.size == 0 or a.size > {maxe}:
        return None
    return [float(v) for v in a.ravel()] + ["shape"] + [int(s) for s in a.shape]
print("__A4S2__" + json.dumps(__flat(__out)))
'''


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fmt(x: float) -> str:
    return format(x, ".8g")


def call_of(test_case: str) -> tuple[str, str] | None:
    """(input lines, the expression compared with `target`) or None."""
    try:
        tree = ast.parse(test_case)
    except SyntaxError:
        return None
    asserts = [n for n in tree.body if isinstance(n, ast.Assert)]
    if len(asserts) != 1 or tree.body[-1] is not asserts[0]:
        return None
    t = asserts[0].test

    def is_target(n):
        return isinstance(n, ast.Name) and n.id == "target"

    expr = None
    if isinstance(t, ast.Call) and len(t.args) >= 2:
        if is_target(t.args[1]):
            expr = t.args[0]
        elif is_target(t.args[0]):
            expr = t.args[1]
    elif isinstance(t, ast.Compare) and len(t.comparators) == 1 and isinstance(t.ops[0], ast.Eq):
        if is_target(t.comparators[0]):
            expr = t.left
        elif is_target(t.left):
            expr = t.comparators[0]
    if expr is None:
        return None
    lines = test_case.splitlines()
    inputs = "\n".join(lines[: asserts[0].lineno - 1])
    return inputs, ast.unparse(expr)


def execute(code: str, inputs: str, call: str) -> tuple[list[float], list[int]] | None:
    prog = code + "\n" + RUNNER.format(inputs=inputs, call=call, maxe=MAX_ELEMS)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "t.py"
        f.write_text(prog, encoding="utf-8")
        try:
            cp = subprocess.run([str(sx.PY), str(f)], cwd=d, capture_output=True, text=True,
                                timeout=600, env={"PYTHONPATH": str(sx.SRC), "PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired:
            return None
    for line in cp.stdout.splitlines():
        if line.startswith("__A4S2__"):
            v = json.loads(line[len("__A4S2__"):])
            if v is None:
                return None
            i = v.index("shape")
            vals, shape = v[:i], v[i + 1:]
            if not all(math.isfinite(x) for x in vals):
                return None
            return vals, shape
    return None


def transpose_digits(s: str) -> str | None:
    """Swap the first pair of adjacent distinct digits in the mantissa."""
    mant = s.split("e")[0]
    for i in range(len(mant) - 1):
        a, b = mant[i], mant[i + 1]
        if a.isdigit() and b.isdigit() and a != b:
            return s[:i] + b + a + s[i + 2:]
    return None


def files_for(inst: str, code: str, inputs: str, log_vals: list[str], res_vals: list[str],
              rep_vals: list[str], rev: str) -> dict[str, bytes]:
    log = "".join(f"{v} {UNIT}\n" for v in log_vals)
    q = [{"name": f"output[{i}]", "value": v, "unit": UNIT,
          "source": f"work/outputs/run.log@{rev}#L{i + 1}", "text": f"{v} {UNIT}"}
         for i, v in enumerate(res_vals)]
    res = "{\n \"quantities\": [\n" + ",\n".join("  " + json.dumps(x) for x in q) + "\n ]\n}\n"
    meta = (f"code_version: {rev}\ninputs:\n  - work/outputs/run.log@{rev}\n"
            f"  - work/solution.py@{rev}\n  - work/inputs.py@{rev}\n")
    rows = [{"v": rv, "u": UNIT,
             "src": {"file": "work/results/results.json", "quote": f"\"text\": \"{qv} {UNIT}\""}}
            for rv, qv in zip(rep_vals, res_vals)]
    stated = ", ".join(f"{v} {UNIT}" for v in rep_vals)
    what = "value is" if len(rep_vals) == 1 else f"{len(rep_vals)} values are, in order,"
    rep = (f"# Result\n\nRunning `work/solution.py` on the inputs in `work/inputs.py` produces the "
           f"step's output; its {what} {stated}. The run log is `work/outputs/run.log` and the "
           f"values are recorded in `work/results/results.json`.\n\n"
           "```crossaudit-numbers\n" + json.dumps(rows) + "\n```\n")
    return {"work/solution.py": code.encode(), "work/inputs.py": (inputs + "\n").encode(),
            "work/outputs/run.log": log.encode(), "work/results/results.json": res.encode(),
            "work/results/metadata.yml": meta.encode(), "work/report.md": rep.encode()}


def main() -> int:
    from crossaudit.dcl import run_checks
    from crossaudit.dcl.profiles import PROFILES

    probs = {p["problem_id"]: p for split in ("dev", "test") for p in sx.load(split)}
    gen = {}
    for f in GEN.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                gen[(r["problem_id"], r["sample"], r["step"])] = r
    correct = sorted(json.loads(STRATA.read_text())["correct"])

    def program(iid: str) -> tuple[str, dict]:
        pid, step1, s = iid.rsplit(".", 2)
        k, smp = int(step1) - 1, int(s[1:])
        p = probs[pid]
        funcs = []
        for i in range(k + 1):
            if (pid, i) in sx.SKIP:
                funcs.append((AI4S / f"SciCode/eval/data/{pid}.{i + 1}.txt").read_text(encoding="utf-8"))
            else:
                funcs.append(gen[(pid, smp, i)]["function"] or "")
        return p["required_dependencies"] + "\n\n" + "\n\n".join(funcs) + "\n", p["sub_steps"][k]

    def prepare(iid: str) -> dict:
        rng = random.Random(f"{SEED}:{iid}")
        code, step = program(iid)
        cases = step["test_cases"]
        ci = rng.randrange(len(cases))
        parsed = call_of(cases[ci])
        row = {"instance": iid, "case": ci, "n_cases": len(cases)}
        if parsed is None:
            return row | {"qualifies": False, "why": "call not readable from the assertion"}
        inputs, call = parsed
        got = execute(code, inputs, call)
        if got is None:
            return row | {"qualifies": False, "why": "output not a finite real scalar/array <= 10"}
        vals, shape = got
        if not any(v != 0 for v in vals):
            return row | {"qualifies": False, "why": "all-zero output"}
        others = []
        for cj, tc in enumerate(cases):
            if cj == ci:
                continue
            pj = call_of(tc)
            if pj is None:
                continue
            gj = execute(code, *pj)
            if gj is None or gj[1] != shape:
                continue
            import numpy as np
            if np.allclose(gj[0], vals):
                continue
            others.append((cj, gj[0]))
        return row | {"qualifies": True, "inputs": inputs, "call": call, "values": vals,
                      "shape": shape, "code": code, "others": others}

    with ThreadPoolExecutor(max_workers=6) as pool:
        prepared = list(pool.map(prepare, correct))
    qual = [r for r in prepared if r["qualifies"]]
    cycle = FAULTS[:]
    random.Random(SEED).shuffle(cycle)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, subs = [], []
    for n, r in enumerate(qual):
        iid = r["instance"]
        rng = random.Random(f"{SEED}:fault:{iid}")
        true = [fmt(v) for v in r["values"]]
        assigned = cycle[n % len(cycle)]
        fault, tries = assigned, 0
        while True:
            if fault == "R3" and not r["others"]:
                pass
            elif fault == "R5" and not any(transpose_digits(v) for v in true):
                pass
            else:
                break
            fault = cycle[(cycle.index(fault) + 1) % len(cycle)]
            tries += 1
        if fault != assigned:
            subs.append({"instance": iid, "assigned": assigned, "used": fault})
        rev = "a4s2-" + sha(iid.encode())[:10]
        log, res, rep = true, true, true
        detail: dict = {}
        if fault in ("R1", "F1"):
            bad = [fmt(v * 1000) for v in r["values"]]
        elif fault == "R2":
            bad = [fmt(-v) for v in r["values"]]
        elif fault in ("R4", "F4"):
            bad = [fmt(v * 1.05) for v in r["values"]]
        elif fault == "R3":
            cj, ov = r["others"][rng.randrange(len(r["others"]))]
            bad = [fmt(v) for v in ov]
            detail["other_case"] = cj
        if fault in ("R1", "R2", "R3", "R4"):
            res, rep = bad, bad
        elif fault in ("F1", "F4"):
            log, res, rep = bad, bad, bad
        elif fault == "R5":
            i = next(i for i, v in enumerate(true) if transpose_digits(v))
            rep = true[:]
            rep[i] = transpose_digits(true[i])
            detail["element"] = i
        entries = []
        for kind, (lv, rv, pv) in (("clean", (true, true, true)), (fault, (log, res, rep))):
            files = files_for(iid, r["code"], r["inputs"], lv, rv, pv, rev)
            d = OUT / f"{iid}.{'clean' if kind == 'clean' else 'faulty'}"
            for path, data in files.items():
                (d / path).parent.mkdir(parents=True, exist_ok=True)
                (d / path).write_bytes(data)
            dcl = run_checks(files, PROFILES["science"], [], []).as_dict()
            entries.append({"item": d.name, "kind": "clean" if kind == "clean" else "faulty",
                            "fault": None if kind == "clean" else fault,
                            "dcl_hard_failures": dcl["total_hard_failures"],
                            "dcl_rules": sorted({f["rule"] for f in dcl["findings"]
                                                 if f["severity"] == "BLOCKER"}),
                            "report_values": pv,
                            "files_sha256": {p: sha(b) for p, b in files.items()}})
        manifest.append({"instance": iid, "case": r["case"], "call": r["call"],
                         "true_values": true, "shape": r["shape"], "fault": fault,
                         "fault_detail": detail, "items": entries})
    dropped = [{k: r[k] for k in ("instance", "case", "why")} for r in prepared if not r["qualifies"]]
    MANIFEST.write_text(json.dumps({"seed": SEED, "cycle": cycle, "n_correct": len(correct),
                                    "n_qualifying": len(qual), "dropped": dropped,
                                    "substitutions": subs, "instances": manifest}, indent=1) + "\n",
                        encoding="utf-8")
    clean_fail = [e["item"] for m in manifest for e in m["items"]
                  if e["kind"] == "clean" and e["dcl_hard_failures"]]
    print(f"{len(qual)} of {len(correct)} qualify; dropped {len(dropped)}; substitutions {len(subs)}")
    print(f"cycle {cycle}")
    print(f"gate (DCL half): clean items with a science-profile BLOCKER: {len(clean_fail)} {clean_fail[:5]}")
    from collections import Counter
    print("faults", Counter(m["fault"] for m in manifest))
    return 0 if not clean_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
