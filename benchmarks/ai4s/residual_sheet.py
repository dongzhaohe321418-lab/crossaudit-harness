#!/usr/bin/env python3
"""A4S-1 residual characterisation: the blind sheet, and the L2 rater (`gpt-5.6-luna`).

Registered in `PREREGISTRATION-CODE.md` ("Residual characterisation"). The residual is every
defective instance that no reading of either family flagged at K = 8. The sheet shows, per item,
the prose (main description, step description, background, function header), the candidate, each
test case's inputs and the expected values, and nothing about status, family, instance id or
hypothesis. Items are shuffled at seed 20260928 and named S001...; the key (id -> instance) is kept
beside the sheet. The sheet quotes SciCode (Apache-2.0) and stays in the run archive.

    python benchmarks/ai4s/residual_sheet.py build     # sheet + key
    python benchmarks/ai4s/residual_sheet.py rate-l2   # luna's labels -> records/ai4s/residual_L2.csv
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))
import scicode_exec as sx  # noqa: E402

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
AUDIT = AI4S / "runs/audit"
GEN = AI4S / "runs/generation"
DIR = AI4S / "runs/residual"
SHEET, KEY = DIR / "sheet.md", DIR / "key.jsonl"
STRATA = REPO / "benchmarks/code/records/ai4s/strata.json"
L2_OUT = REPO / "benchmarks/code/records/ai4s/residual_L2.csv"
SEED = 20260928
K = 8
MAX_SHOWN = 24          # array elements shown per expected value; the shape is always stated
MODEL, KEY_ENV, BATCH = "gpt-5.6-luna", "CROSSAUDIT_OPENAI_KEY", 4

RUBRIC = """For each item you are asked one thing only:

> Do the step's prose and background determine the value the test expects at the tested
> input, including the tolerance, units, conventions and numerical method it depends on?

Not whether the code is correct. Not whether the tests are reasonable. Only whether this text
pins the expected value down.

  determined    — the text says. A careful scientist could derive the expected value from it.
  undetermined  — the text does not say. Several values fit this text (a different convention,
                  unit, normalisation, method or tolerance), and the test picked one of them.
  cannot-tell   — you cannot tell (the text is too short, the tested behaviour is unclear, or
                  you are unsure).

`cannot-tell` is a legitimate answer. Do not force a choice to make the sheet look tidy.

Answer with one line per item, exactly `<id>,<label>`, and nothing else."""

TARGETS = r'''
import json, sys, numpy as np
from scicode.parse.parse import process_hdf5_to_tuple
t = process_hdf5_to_tuple(sys.argv[1], int(sys.argv[2]), sys.argv[3])
def show(x):
    try:
        a = np.asarray(x)
        if a.dtype.kind in "iufcb" and a.ndim > 0:
            flat = a.ravel()
            body = ", ".join(repr(v.item()) for v in flat[:%d])
            more = "" if flat.size <= %d else f", ... ({flat.size} elements)"
            return f"array of shape {a.shape}: [{body}{more}]"
    except Exception:
        pass
    s = repr(x)
    return s if len(s) < 2000 else s[:2000] + " ..."
print(json.dumps([show(x) for x in t]))
''' % (MAX_SHOWN, MAX_SHOWN)


def residual() -> list[str]:
    strata = json.loads(STRATA.read_text())
    flagged: dict[str, bool] = {i: False for i in strata["defective"]}
    counts: dict[str, int] = {i: 0 for i in strata["defective"]}
    for fam in ("cross", "self"):
        for d in range(1, K + 1):
            for line in (AUDIT / f"{fam}.d{d}.jsonl").read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if r.get("ok") and r["instance_id"] in flagged:
                        counts[r["instance_id"]] += 1
                        flagged[r["instance_id"]] |= bool(r["flagged"])
    short = [i for i, n in counts.items() if n != 2 * K]
    if short:
        raise SystemExit(f"{len(short)} defective instances lack 16 readings, e.g. {short[:3]}")
    return sorted(i for i, f in flagged.items() if not f)


def build() -> int:
    probs = {p["problem_id"]: p for split in ("dev", "test") for p in sx.load(split)}
    gen = {}
    for f in GEN.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                gen[(r["problem_id"], r["sample"], r["step"])] = r
    res = residual()
    order = res[:]
    random.Random(SEED).shuffle(order)
    DIR.mkdir(parents=True, exist_ok=True)
    parts, key = ["# Rating sheet\n"], []
    for n, iid in enumerate(order, 1):
        rid = f"S{n:03d}"
        pid, step1, s = iid.rsplit(".", 2)
        k, smp = int(step1) - 1, int(s[1:])
        p, st = probs[pid], probs[pid]["sub_steps"][k]
        cp = subprocess.run([str(sx.PY), "-c", TARGETS, st["step_number"],
                             str(len(st["test_cases"])), str(sx.H5)],
                            capture_output=True, text=True, env={"PYTHONPATH": str(sx.SRC),
                                                                 "PATH": "/usr/bin:/bin"})
        targets = json.loads(cp.stdout.strip().splitlines()[-1])
        cases = []
        for i, tc in enumerate(st["test_cases"]):
            inputs = "\n".join(l for l in tc.splitlines() if not l.lstrip().startswith("assert"))
            check = "\n".join(l for l in tc.splitlines() if l.lstrip().startswith("assert"))
            cases.append(f"Test {i + 1} inputs:\n```python\n{inputs}\n```\n"
                         f"Test {i + 1} check: `{check.strip()}`\n"
                         f"Test {i + 1} expected value (`target`): {targets[i]}\n")
        parts.append(
            f"## {rid}\n\n### Problem\n{p['problem_description_main']}\n\n"
            f"### Step\n{st['step_description_prompt']}\n\n### Background\n{st['step_background']}\n\n"
            f"### Function header\n```python\n{st['function_header']}\n{st['return_line']}\n```\n\n"
            f"### Candidate\n```python\n{gen[(pid, smp, k)]['function']}\n```\n\n"
            f"### Tests\n" + "\n".join(cases) + "\n")
        key.append({"id": rid, "instance": iid})
    SHEET.write_text("\n".join(parts), encoding="utf-8")
    KEY.write_text("".join(json.dumps(r) + "\n" for r in key), encoding="utf-8")
    print(f"residual {len(res)} instances; sheet {SHEET} ({SHEET.stat().st_size} bytes)")
    return 0


def rate_l2() -> int:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k_, v_ = line.split("=", 1)
            os.environ.setdefault(k_.strip(), v_.strip().strip('"').strip("'"))
    from crossaudit.providers import openai_compat
    text = SHEET.read_text(encoding="utf-8")
    parts = re.split(r"^## (S\d+)$", text, flags=re.M)[1:]
    rows = list(zip(parts[0::2], (b.strip() for b in parts[1::2])))
    labels: dict[str, str] = {}
    spend = []
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        prompt = "\n\n".join(f"## {rid}\n{body}" for rid, body in chunk)
        out = ""
        for attempt in range(1, 4):
            try:
                reply = openai_compat.complete(model=MODEL, key_env=KEY_ENV, system=RUBRIC,
                                               prompt=prompt, max_tokens=4000, timeout=300.0)
                out = getattr(reply, "text", "") or ""
                spend.append(getattr(reply, "cost_usd", None))
                if out.strip():
                    break
            except Exception as exc:                                   # noqa: BLE001
                print(f"  {chunk[0][0]}: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            time.sleep(5 * attempt)
        for m in re.finditer(r"(S\d+)\s*,\s*(determined|undetermined|cannot-tell)", out):
            labels[m.group(1)] = m.group(2)
        print(f"  {chunk[0][0]}-{chunk[-1][0]}: {len(labels)} labelled", flush=True)
    L2_OUT.write_text("id,label\n" + "".join(f"{rid},{labels.get(rid, '')}\n" for rid, _ in rows),
                      encoding="utf-8")
    known = [c for c in spend if isinstance(c, (int, float))]
    print(f"wrote {L2_OUT}: {len(labels)} of {len(rows)}; spend ${sum(known):.4f}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit(build() if cmd == "build" else rate_l2() if cmd == "rate-l2" else print(__doc__))
