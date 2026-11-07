"""E6: contract-randomised information release (CEILING_PROGRAM.md v2, section 3). Construction stages.

A discrepancy unit comes from an E1 item: the task, the reference R, the defective program D and the first hidden
input x0 on which they differ. The minimal pair C_A is R rewritten to behave like D on inputs of x0's kind and like
R elsewhere. It is admitted only if, on every hidden input, either C_A agrees with R, or C_A agrees with D (and the
set of such inputs contains x0); and C_A passes the visible tests. Comparisons use the suite's own assertion.

    python benchmarks/code/icml/e6.py pairs --split dev --workers 4
    python benchmarks/code/icml/e6.py validate --workers 6
"""
from __future__ import annotations

import argparse
import base64
import json
import pickle
import subprocess
import tempfile
from pathlib import Path

import e1
from e1 import REC, execute, imports_of, load, append, sha, suite_assertion

PAIRS = REC / "e6_pairs.jsonl"
VALID = REC / "e6_validation.jsonl"
PAIR_ROUTE = "con-gpt-astra"

PAIR_PROMPT = """Below are a programming task, a reference implementation, and a second implementation that behaves
differently on one input. Rewrite the REFERENCE so that it behaves like the second implementation on this input and on
other inputs of the same kind (the same edge case or convention), and exactly like the reference on every other input.
Make the smallest change that does this. Keep the reference's function name, signature and imports. Write the change as
ordinary code: no comments or names that mention a reference, another implementation, tests, edge cases or this
instruction.

Reply with exactly one JSON object: {{"code": "<the complete rewritten function, with any imports it needs>",
"kind": "<one sentence describing the kind of input on which the behaviour changes>"}}

TASK:
{spec}

REFERENCE:
```python
{reference}
```

SECOND IMPLEMENTATION:
```python
{defective}
```

INPUT (positional arguments): {args}
REFERENCE OUTPUT: {ref_out}
SECOND IMPLEMENTATION OUTPUT: {def_out}
"""

BATCH = r'''
import pickle, sys, base64, signal, json
sys.setrecursionlimit(10000)
spec = json.loads(open(sys.argv[1]).read())
inputs = pickle.loads(base64.b64decode(spec["inputs"].encode()))

class _Late(BaseException):
    pass

def _alarm(*_):
    raise _Late()

signal.signal(signal.SIGALRM, _alarm)
helpers = {}
exec(compile(spec["helpers"], "suite_helpers", "exec"), helpers)

def load_fn(src):
    ns = {}
    exec(compile(src, "solution", "exec"), ns)
    return ns[spec["entry"]]

fns = {k: load_fn(spec[k]) for k in ("reference", "candidate", "defective")}

def run(fn, inp):
    args = pickle.loads(pickle.dumps(inp))
    signal.alarm(spec["limit"])
    try:
        value = fn(*args)
        signal.alarm(0)
        return "ok", value
    except _Late:
        return "timeout", None
    except BaseException as e:
        signal.alarm(0)
        return "exc:" + type(e).__name__, None

def agrees(a, b):
    sa, va = a
    sb, vb = b
    if sa != "ok" or sb != "ok":
        return sa == sb
    try:
        helpers["assertion"](va, vb, spec["atol"])
        return True
    except BaseException:
        return False

rows = []
for i, inp in enumerate(inputs):
    r, c, d = (run(fns[k], inp) for k in ("reference", "candidate", "defective"))
    rows.append([i, agrees(c, r), agrees(c, d), agrees(d, r), r[0], c[0]])
sys.stdout.write("BATCH " + json.dumps(rows))
'''


def batch_compare(p, reference: str, candidate: str, defective: str, inputs: list, limit: int = 5) -> dict:
    helpers, atol = suite_assertion(p)
    pre = imports_of(p) + "\n"
    spec = {"helpers": helpers, "atol": float(e1.literal(atol)), "entry": p.entry_point, "limit": limit,
            "inputs": base64.b64encode(pickle.dumps(inputs)).decode(),
            "reference": pre + p.canonical_solution, "candidate": pre + candidate, "defective": pre + defective}
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        (Path(tmp) / "batch.py").write_text(BATCH, encoding="utf-8")
        try:
            done = subprocess.run([execute.EXECUTOR, str(Path(tmp) / "batch.py"), str(Path(tmp) / "spec.json")],
                                  capture_output=True, text=True, timeout=limit * len(inputs) * 3 + 120, cwd=tmp,
                                  env=e1.EXEC_ENV)
        except subprocess.TimeoutExpired:
            return {"infra": "timeout"}
    if "BATCH " not in done.stdout:
        return {"infra": (done.stderr or "")[-300:]}
    return {"rows": json.loads(done.stdout[done.stdout.rfind("BATCH ") + 6:])}


def problems() -> dict:
    return {p.problem_id: p for p in e1.load_problems()}


def stage_pairs(split: str, workers: int) -> None:
    items = [i for i in json.loads((REC / "items_v3.json").read_text()) if i["split"] == split]
    probs = problems()
    have = {r["item_id"] for r in load(PAIRS) if r.get("ok")}
    jobs = [i for i in items if i["item_id"] not in have]

    def one(it):
        p, ff = probs[it["problem_id"]], it["first_fail"]
        payload = PAIR_PROMPT.format(spec=p.spec, reference=p.canonical_solution, defective=it["defective_solution"],
                                     args=ff["args_repr"], ref_out=ff["reference"]["repr"],
                                     def_out=ff["candidate"]["repr"])
        res = e1.call(PAIR_ROUTE, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        ok = isinstance(obj, dict) and isinstance(obj.get("code"), str) and obj["code"].strip() != ""
        append(PAIRS, {"item_id": it["item_id"], "split": split, "route": PAIR_ROUTE, "ok": ok,
                       "prompt_sha256": sha(payload), "code": obj.get("code") if ok else None,
                       "kind": obj.get("kind") if ok else None, "error": res.get("error", "" if ok else "parse")})
    e1.run_pool(jobs, one, workers, f"e6 pairs {split}")


def stage_validate(workers: int) -> None:
    items = {i["item_id"]: i for i in json.loads((REC / "items_v3.json").read_text())}
    probs = problems()
    pairs = {r["item_id"]: r for r in load(PAIRS) if r.get("ok")}
    have = {r["pair_sha256"] for r in load(VALID)}
    jobs = [r for r in pairs.values() if sha(r["code"]) not in have]
    inp_cache: dict = {}

    def one(pr):
        it = items[pr["item_id"]]
        p = probs[it["problem_id"]]
        if p.problem_id not in inp_cache:
            inp_cache[p.problem_id] = e1.hidden_inputs(p)
        inputs = inp_cache[p.problem_id]
        x0 = it["first_fail"]["index"]
        vis = execute.run_suite(p.visible_program(pr["code"]),
                                instrumented=p.visible_instrumented)
        row = {"item_id": pr["item_id"], "pair_sha256": sha(pr["code"]), "visible_passed": vis.passed}
        if inputs is None:
            append(VALID, {**row, "admitted": False, "reason": "no hidden inputs"})
            return
        b = batch_compare(p, p.canonical_solution, pr["code"], it["defective_solution"], inputs)
        if "infra" in b:
            append(VALID, {**row, "admitted": False, "reason": "infra", "infra": b["infra"]})
            return
        changed = [r[0] for r in b["rows"] if not r[1]]                 # C_A differs from R
        new_defect = [r[0] for r in b["rows"] if not r[1] and not r[2]]  # ... and from D: not D's behaviour
        d_only = [r[0] for r in b["rows"] if not r[3] and r[1]]          # D differs, C_A kept R
        admitted = vis.passed and bool(changed) and not new_defect and x0 in changed
        reason = ("ok" if admitted else "visible" if not vis.passed else "no change" if not changed
                  else "new defect" if new_defect else "x0 unchanged")
        append(VALID, {**row, "admitted": admitted, "reason": reason, "n_inputs": len(inputs),
                       "changed": changed[:500], "n_changed": len(changed), "n_new_defect": len(new_defect),
                       "n_d_only": len(d_only), "x0": x0})
    e1.run_pool(jobs, one, workers, "e6 validate")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pairs", "validate"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.stage == "pairs":
        stage_pairs(a.split, a.workers)
    else:
        stage_validate(a.workers)
