#!/usr/bin/env python3
"""P4 adjudication: extraction by a model, then execution. Registered in PREREGISTRATION.md.

    python fpadj/adjudicate.py extract     # gpt-5.6-luna, blind to the reference; $3 halt
    python fpadj/adjudicate.py execute     # candidate and reference on every extracted input
    python fpadj/adjudicate.py analyse     # D / A / N, the registered interval, the record

Texts and extractions stay in the study-data archive; the committed record carries counts,
classes, hashes and the executed inputs' outcomes, not finding text.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE.parent.parent / "src"))

from corpus import load_problems  # noqa: E402

RECORDS = CODE / "records"
FP = RECORDS / "fpadj"
ARCH = Path.home() / "Documents/Crossaudit/study-data/wt-fpadj-runs"
TEXTS = ARCH / "blocker_texts.jsonl"
EXTRACT = ARCH / "extractions.jsonl"
EXEC = ARCH / "executions.jsonl"
OUT = FP / "adjudication.json"
MODEL = "gpt-5.6-luna"
KEY_ENV = "CROSSAUDIT_AUDITOR_KEY"
HALT_USD = 3.0
SEED = 20260924
N_BOOT = 10000
TIMEOUT_S = 10.0

SYSTEM = """You read one finding an automated code auditor wrote about a Python function, together
with the function's specification and its code. Your only task is to extract the concrete inputs
the finding says the code handles wrongly.

Return JSON and nothing else: {"inputs": ["<expr>", ...]}
Each <expr> is a Python literal expression that evaluates to a TUPLE of positional arguments for
the function, for example "([1, 2, 3],)" or "('abc', 2)". Give at most three. Include an input
only if the finding names it or describes it concretely enough to write down without guessing.
If the finding names no concrete input, return {"inputs": []}. Do not judge whether the finding
is right, and do not invent inputs of your own."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_keys() -> None:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def solutions() -> dict[str, str]:
    run = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs/study2-inputs"
    out = {}
    for b in ("b1", "b2"):
        for r in rows(run / f"solutions-{b}.jsonl"):
            out[f"{b}:{r['problem_id']}"] = r["solution"]
    return out


def findings() -> list[dict]:
    """One item per distinct BLOCKER text per instance, over every flagged reading."""
    seen, out = set(), []
    for r in rows(TEXTS):
        if not r.get("flagged"):
            continue
        for t in r["blocker_texts"]:
            key = (r["instance_id"], sha(t))
            if key not in seen:
                seen.add(key)
                out.append({"instance_id": r["instance_id"], "text": t, "text_sha256": sha(t)})
    return out


def leak_lines(reference: str, spec: str, candidate: str) -> list[str]:
    """Lines of the reference long enough to identify it and present in neither the spec nor
    the candidate. For HumanEval the reference contains the spec itself, which is not a leak."""
    visible = spec + "\n" + candidate
    return [l.strip() for l in reference.splitlines()
            if len(l.strip()) >= 20 and l.strip() not in visible]


def extract() -> int:
    load_keys()
    from crossaudit.providers import openai_compat
    problems = {p.problem_id: p for p in load_problems()}
    sols = solutions()
    done = {(r["instance_id"], r["text_sha256"]) for r in rows(EXTRACT)}
    items = [f for f in findings() if (f["instance_id"], f["text_sha256"]) not in done]
    spent = sum(r.get("cost_usd") or 0.0 for r in rows(EXTRACT))
    print(f"{len(items)} findings to extract; ${spent:.4f} spent so far", flush=True)
    with EXTRACT.open("a", encoding="utf-8") as fh:
        for n, f in enumerate(items, 1):
            if spent >= HALT_USD:
                print(f"HALT: ${spent:.3f} at or over the registered ${HALT_USD}")
                return 2
            p = problems[f["instance_id"].split(":", 1)[1]]
            cand = sols[f["instance_id"]]
            prompt = (f"Function name: {p.entry_point}\n\n## Specification\n{p.spec}\n\n"
                      f"## Code\n```python\n{cand}\n```\n\n## Finding\n{f['text']}\n")
            leaks = [l for l in leak_lines(p.canonical_solution, p.spec, cand) if l in prompt]
            if leaks:
                raise SystemExit(f"HALT: leak check failed on {f['instance_id']}: {leaks[:2]}")
            reply, text, cost = None, "", None
            for attempt in range(1, 4):
                try:
                    reply = openai_compat.complete(model=MODEL, key_env=KEY_ENV, system=SYSTEM,
                                                   prompt=prompt, max_tokens=800, timeout=120.0)
                    text = getattr(reply, "text", "") or ""
                    # `Reply` carries no cost; price it the way the kernel's ledger does, from
                    # the token counts and the model's capability card. Unpriced stays None and
                    # halts below.
                    from crossaudit import usage as usage_mod
                    counts = usage_mod.normalise_usage(reply.raw, system=SYSTEM, prompt=prompt,
                                                       response=text)
                    cost = usage_mod._api_value(counts, usage_mod._rates("openai", MODEL))
                    if text.strip():
                        break
                except Exception as exc:                               # noqa: BLE001
                    print(f"  {f['instance_id']}: {type(exc).__name__}, attempt {attempt}/3")
                time.sleep(5 * attempt)
            if cost is None and text:
                raise SystemExit("HALT: the reply carries no cost; refusing to spend against a "
                                 "guard that cannot see money")
            spent += cost or 0.0
            try:
                parsed = json.loads(text[text.index("{"): text.rindex("}") + 1])["inputs"]
                parsed = [str(x) for x in parsed][:3]
                parse_ok = True
            except Exception:                                          # noqa: BLE001
                parsed, parse_ok = [], False
            fh.write(json.dumps({**f, "prompt_sha256": sha(prompt), "reply": text,
                                 "inputs": parsed, "parse_ok": parse_ok, "cost_usd": cost},
                                sort_keys=True) + "\n")
            fh.flush()
            if n % 10 == 0 or n == len(items):
                print(f"  {n}/{len(items)}  ${spent:.4f}", flush=True)
    return 0


RUNNER = r'''
import ast, sys, json
src = open(sys.argv[1]).read()
args = ast.literal_eval(open(sys.argv[2]).read())
if not isinstance(args, tuple):
    args = (args,)
ns = {}
exec(compile(src, "program", "exec"), ns)
out = ns[sys.argv[3]](*args)
print("\x00RESULT\x00" + repr(out))
'''


def run_one(program: str, entry: str, expr: str) -> tuple[str, str]:
    """('ok', repr) | ('raise', type) | ('timeout', '')."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "p.py").write_text(program, encoding="utf-8")
        (Path(d) / "a.txt").write_text(expr, encoding="utf-8")
        (Path(d) / "r.py").write_text(RUNNER, encoding="utf-8")
        try:
            cp = subprocess.run([sys.executable, "r.py", "p.py", "a.txt", entry], cwd=d,
                                capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return "timeout", ""
        marker = "\x00RESULT\x00"
        if cp.returncode == 0 and marker in cp.stdout:
            return "ok", cp.stdout.split(marker, 1)[1].strip()
        last = (cp.stderr.strip().splitlines() or ["?"])[-1]
        return "raise", last.split(":", 1)[0][:80]


def same(a: str, b: str) -> bool:
    """Python equality on the reprs' values, floats within 1e-6 relative or absolute."""
    if a == b:
        return True
    try:
        x, y = ast.literal_eval(a), ast.literal_eval(b)
    except Exception:                                                  # noqa: BLE001
        return False

    def eq(u, v):
        if isinstance(u, float) or isinstance(v, float):
            try:
                return math.isclose(float(u), float(v), rel_tol=1e-6, abs_tol=1e-6)
            except (TypeError, ValueError):
                return False
        if isinstance(u, (list, tuple)) and isinstance(v, (list, tuple)):
            return type(u) is type(v) and len(u) == len(v) and all(eq(p, q) for p, q in zip(u, v))
        if isinstance(u, dict) and isinstance(v, dict):
            return u.keys() == v.keys() and all(eq(u[k], v[k]) for k in u)
        return u == v
    return eq(x, y)


def execute() -> int:
    problems = {p.problem_id: p for p in load_problems()}
    sols = solutions()
    done = {(r["instance_id"], r["text_sha256"], r["input"]) for r in rows(EXEC)}
    n = 0
    with EXEC.open("a", encoding="utf-8") as fh:
        for e in rows(EXTRACT):
            p = problems[e["instance_id"].split(":", 1)[1]]
            for expr in e["inputs"]:
                if (e["instance_id"], e["text_sha256"], expr) in done:
                    continue
                try:
                    ast.literal_eval(expr)
                    literal = True
                except Exception:                                      # noqa: BLE001
                    literal = False
                if not literal:
                    rec = {"status": "not-a-literal"}
                else:
                    ref = run_one(p.canonical_solution, p.entry_point, expr)
                    if ref[0] != "ok":
                        rec = {"status": "invalid", "reference": ref[0]}
                    else:
                        cand = run_one(sols[e["instance_id"]], p.entry_point, expr)
                        agree = cand[0] == "ok" and same(cand[1], ref[1])
                        rec = {"status": "agree" if agree else "disagree",
                               "candidate": cand[0], "reference": "ok",
                               "candidate_out_sha256": sha(cand[1]),
                               "reference_out_sha256": sha(ref[1])}
                fh.write(json.dumps({"instance_id": e["instance_id"],
                                     "text_sha256": e["text_sha256"], "input": expr, **rec},
                                    sort_keys=True) + "\n")
                n += 1
    print(f"{n} inputs executed")
    return 0


def analyse() -> int:
    ex = rows(EXEC)
    flagged = sorted({f["instance_id"] for f in findings()})
    by_inst: dict[str, list[str]] = defaultdict(list)
    for r in ex:
        by_inst[r["instance_id"]].append(r["status"])
    cls = {}
    for i in flagged:
        st = [s for s in by_inst.get(i, []) if s in ("agree", "disagree")]
        cls[i] = "D" if "disagree" in st else ("A" if st else "N")
    n = len(flagged)
    counts = Counter(cls.values())
    problem = {i: i.split(":", 1)[1] for i in flagged}
    groups: dict[str, list[int]] = defaultdict(list)
    for i in flagged:
        groups[problem[i]].append(1 if cls[i] == "D" else 0)
    keys = sorted(groups)
    rng = random.Random(SEED)
    shares = []
    for _ in range(N_BOOT):
        k = m = 0
        for _ in keys:
            g = groups[keys[rng.randrange(len(keys))]]
            k += sum(g); m += len(g)
        shares.append(100 * k / m)
    shares.sort()

    def pct(q):
        pos = q * (len(shares) - 1)
        lo, hi = math.floor(pos), math.ceil(pos)
        return shares[lo] + (shares[hi] - shares[lo]) * (pos - lo)

    z, pD = 1.959963984540054, counts["D"] / n if n else 0.0
    d = 1 + z * z / n
    c = (pD + z * z / (2 * n)) / d
    h = z * math.sqrt(pD * (1 - pD) / n + z * z / (4 * n * n)) / d
    # Secondary: union false-positive rate at K = 8 over the 150, clustered by problem.
    union: dict[str, int] = {}
    for d in range(1, 9):
        for r in rows(RECORDS / "fpadj" / "cache" / f"holistic__cross__d{d}.jsonl"):
            union[r["instance_id"]] = union.get(r["instance_id"], 0) | int(bool(r.get("flagged")))
    assert len(union) == 150, f"union over {len(union)} instances, registered 150"
    ug: dict[str, list[int]] = defaultdict(list)
    for i, f in union.items():
        ug[i.split(":", 1)[1]].append(f)
    uk = sorted(ug)
    rng2 = random.Random(SEED)
    us = []
    for _ in range(N_BOOT):
        k = m = 0
        for _ in uk:
            g = ug[uk[rng2.randrange(len(uk))]]
            k += sum(g); m += len(g)
        us.append(100 * k / m)
    us.sort()
    rec = {
        "union_fp_K8": [sum(union.values()), len(union)],
        "union_fp_K8_pct": 100 * sum(union.values()) / len(union),
        "union_fp_K8_cluster_ci95": [us[int(0.025 * (N_BOOT - 1))], us[int(0.975 * (N_BOOT - 1))]],
        "ceiling1_union_fp_K8_for_comparison": "24/150 = 16.0% [10.1, 22.3]; neither corrects the other",
        "flagged_instances": n, "problems": len(keys),
        "classes": dict(counts),
        "D_share_pct": 100 * pD, "D_cluster_ci95": [pct(0.025), pct(0.975)],
        "D_wilson_too_narrow": [100 * (c - h), 100 * (c + h)],
        "findings_extracted": len(rows(EXTRACT)),
        "extraction_parse_failures": sum(1 for r in rows(EXTRACT) if not r["parse_ok"]),
        "inputs_by_status": dict(Counter(r["status"] for r in ex)),
        "per_instance_class": cls,
        "seed": SEED, "n_boot": N_BOOT,
        "label": "P4 primary, registered 37ae487; Amendment 1 75131f6",
    }
    OUT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in rec.items() if k != "per_instance_class"}, indent=1))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit({"extract": extract, "execute": execute, "analyse": analyse}.get(
        cmd, lambda: print(__doc__) or 1)())
