"""E6: contract-randomised information release (CEILING_PROGRAM.md v3). Construction stages.

Contracts first (GPT review P2): for each problem, a proposer names an input class on which the task text and the
visible tests leave the behaviour open, and states two behavioural rules of equal specificity: B, the one the
benchmark reference follows, and A, an alternative. Each rule is then implemented independently, from the task
plus the rule alone, by two different vendors with the same prompt; neither implementation sees the reference.
A unit is admitted only if all four implementations pass the visible tests, both B implementations pass the full
hidden suite, the two A implementations agree with each other on every validation input, A and B differ on at
least two class inputs, and they agree on every non-class input. The audited programs are one A and one B
implementation from the same vendor, so the two programs share provenance and style.

    python benchmarks/code/icml/e6.py propose --split dev --workers 6
    python benchmarks/code/icml/e6.py implement --split dev --workers 6
    python benchmarks/code/icml/e6.py validate --split dev --workers 6
    python benchmarks/code/icml/e6.py audit --split dev --workers 8
    python benchmarks/code/icml/e6.py witness --split dev --workers 6

The pilot of the earlier minimal-pair design (CEILING_PROGRAM v2) is kept in e6_pairs.jsonl / e6_validation.jsonl.
"""
from __future__ import annotations

import argparse
import ast
import random
import base64
import json
import pickle
import subprocess
import tempfile
from pathlib import Path

import e1
from e1 import REC, execute, imports_of, load, append, sha, suite_assertion

PROPOSALS = REC / "e6_proposals.jsonl"
IMPLS = REC / "e6_impls.jsonl"
UNITS = REC / "e6_units.jsonl"
KIND = "open"            # "det": positive controls, where the task's words decide and RULE_A is a misreading


def set_kind(kind: str) -> None:
    """Point every stage at the record files of one unit kind."""
    global KIND, PROPOSALS, IMPLS, PREUNITS, PROBES, UNITS, JUDGE, BEHAV, AUD, AUD_RAW, WIT, ARMS
    KIND = kind
    pre = "e6_" if kind == "open" else "e6det_"
    PROPOSALS, IMPLS = REC / f"{pre}proposals.jsonl", REC / f"{pre}impls.jsonl"
    PREUNITS = REC / f"{pre}units.jsonl"          # pre-admission (stage_validate): decides who receives probes
    PROBES, UNITS = REC / f"{pre}probes.jsonl", REC / f"{pre}units4.jsonl"
    JUDGE, BEHAV = REC / f"{pre}judgements2.jsonl", REC / f"{pre}behaviour4.jsonl"
    AUD, AUD_RAW = REC / f"{pre}audits_v4.jsonl", REC / f"{pre}audits_raw_v4.jsonl"
    WIT = REC / f"{pre}witnesses_v4.jsonl"
    ARMS = OPEN_ARMS if kind == "open" else ("none",)
PROPOSE_ROUTE = "con-gpt-astra"
IMPL_ROUTES = ("adj-gpt-sol", "adj-claude-opus")     # two vendors, same prompt

PROPOSE_PROMPT = """You are preparing material for a study of code review. Below are a programming task as a
programmer receives it (description and visible tests) and the benchmark's reference implementation.

Find ONE kind of valid input on which the task's words and the visible tests genuinely leave the correct behaviour
open: two different behaviours would each be accepted by a careful programmer reading only the task and the visible
tests. Typical cases are unstated tie-breaking, ordering, duplicates, empty or boundary inputs that the task's stated
domain allows, rounding, case, or which of two natural readings of a phrase applies. Do not use inputs the task's
domain excludes, behaviour that a careful reading of the words already decides, or quirks of the reference that no
reading of the words supports.

State two behavioural rules for that kind of input, each one sentence, equally specific, written as requirements a
task author could add (for example "If several words are equally long, return the first of them."):
- RULE_B: the behaviour the reference implementation follows;
- RULE_A: a different behaviour that is equally compatible with the task's words and visible tests.
Neither rule may mention the reference, tests, or this study. Then give inputs, each a Python literal tuple of the
positional arguments with the exact argument types the task uses (a one-argument call is written "(x,)"):
- CLASS_INPUTS: 4 to 8 inputs of that kind, including inputs on which RULE_A and RULE_B give different outputs;
- OTHER_INPUTS: 3 to 5 valid inputs of other kinds, on which both rules agree.

If no such genuinely open behaviour exists, reply {{"skip": "<one sentence why>"}}. Otherwise reply with exactly one
JSON object:
{{"class": "<one sentence describing the kind of input>", "rule_a": "...", "rule_b": "...",
  "class_inputs": ["(...)", ...], "other_inputs": ["(...)", ...]}}

TASK:
{spec}

REFERENCE:
```python
{reference}
```
"""

PROPOSE_DET_PROMPT = """You are preparing material for a study of code review. Below are a programming task as a
programmer receives it (description and visible tests) and the benchmark's reference implementation.

Find ONE kind of valid input on which the task's words DO decide the correct behaviour, but where a hurried programmer
could plausibly get it wrong while still passing every visible test (a plausible misreading of the words). State two
behavioural rules for that kind of input, each one sentence, equally specific, written as requirements:
- RULE_B: the behaviour the task's words require (the reference follows it);
- RULE_A: the plausible misreading, which passes the visible tests but which a careful reading of the words rules out.
Neither rule may mention the reference, tests, or this study. Then give inputs, each a Python literal tuple of the
positional arguments with the exact argument types the task uses (a one-argument call is written "(x,)"):
- CLASS_INPUTS: 4 to 8 inputs of that kind, including inputs on which RULE_A and RULE_B give different outputs;
- OTHER_INPUTS: 3 to 5 valid inputs of other kinds, on which both rules agree.

If no such behaviour exists, reply {{"skip": "<one sentence why>"}}. Otherwise reply with exactly one JSON object:
{{"class": "<one sentence describing the kind of input>", "rule_a": "...", "rule_b": "...",
  "class_inputs": ["(...)", ...], "other_inputs": ["(...)", ...]}}

TASK:
{spec}

REFERENCE:
```python
{reference}
```
"""

IMPL_PROMPT = """Write a Python function for the task below. It must pass the visible tests and must also follow the
additional requirement exactly. Use only the standard library. Write ordinary, clean code: no comments about the
requirement, the tests or these instructions.

TASK:
{spec}

ADDITIONAL REQUIREMENT: {rule}

Reply with exactly one JSON object: {{"code": "<the complete function definition, with any imports it needs>"}}
"""

MULTI = r'''
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
    try:
        exec(compile(src, "solution", "exec"), ns)
        return ns[spec["entry"]]
    except BaseException:
        return None

fns = {k: load_fn(v) for k, v in spec["programs"].items()}

def run(fn, inp):
    if fn is None:
        return "load", None
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
    signal.alarm(spec["limit"])
    try:
        helpers["assertion"](va, vb, spec["atol"])
        signal.alarm(0)
        return True
    except _Late:
        return None
    except BaseException:
        signal.alarm(0)
        return False

rows = []
for inp in inputs:
    out = {k: run(f, inp) for k, f in fns.items()}
    rows.append({"status": {k: v[0] for k, v in out.items()},
                 "agree": {f"{a}~{b}": agrees(out[a], out[b]) for a, b in spec["pairs"]},
                 "value": {k: out[k][1] for k in spec.get("capture", []) if isinstance(out[k][1], bool)}})
with open(spec["out"], "w") as fh:
    fh.write(json.dumps(rows))
'''


def multi_compare(p, programs: dict, pairs: list, inputs: list, limit: int = 5, capture: list = ()) -> dict:
    """Run every program on every input in one executor process; compare the given pairs with the suite's own
    assertion. Results come back through a file."""
    helpers, atol = suite_assertion(p)
    pre = imports_of(p) + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        spec = {"helpers": helpers, "atol": float(e1.literal(atol)), "entry": p.entry_point, "limit": limit,
                "inputs": base64.b64encode(pickle.dumps(inputs)).decode(), "pairs": pairs,
                "programs": {k: pre + v for k, v in programs.items()}, "out": str(Path(tmp) / "out.json"),
                "capture": list(capture)}
        (Path(tmp) / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        (Path(tmp) / "multi.py").write_text(MULTI, encoding="utf-8")
        try:
            done = subprocess.run([execute.EXECUTOR, str(Path(tmp) / "multi.py"), str(Path(tmp) / "spec.json")],
                                  capture_output=True, text=True, timeout=limit * 3 * len(inputs) * len(programs) + 120,
                                  cwd=tmp, env=e1.EXEC_ENV)
        except subprocess.TimeoutExpired:
            return {"infra": "timeout"}
        try:
            return {"rows": json.loads((Path(tmp) / "out.json").read_text())}
        except (OSError, json.JSONDecodeError):
            return {"infra": (done.stderr or "")[-300:] or "no result"}


def problems(split: str) -> list:
    split_of = e1.frozen_split()
    return [p for p in e1.load_problems() if split_of[p.problem_id] == split]


def literal_tuple(src: str):
    try:
        v = e1.literal(src.strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    return v if isinstance(v, tuple) else None


def stage_propose(split: str, workers: int) -> None:
    have = {r["problem_id"] for r in load(PROPOSALS) if r.get("ok")}
    jobs = [p for p in problems(split) if p.problem_id not in have]

    def one(p):
        payload = (PROPOSE_PROMPT if KIND == "open" else PROPOSE_DET_PROMPT).format(spec=p.spec,
                                                                                  reference=p.canonical_solution)
        res = e1.call(PROPOSE_ROUTE, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        row = {"problem_id": p.problem_id, "split": split, "route": PROPOSE_ROUTE, "prompt_sha256": sha(payload)}
        if isinstance(obj, dict) and "skip" in obj:
            append(PROPOSALS, {**row, "ok": True, "skip": str(obj["skip"])[:500]})
            return
        keys = ("class", "rule_a", "rule_b", "class_inputs", "other_inputs")
        ok = isinstance(obj, dict) and all(k in obj for k in keys)
        if ok:
            ci = [literal_tuple(x) for x in obj["class_inputs"]] if isinstance(obj["class_inputs"], list) else []
            oi = [literal_tuple(x) for x in obj["other_inputs"]] if isinstance(obj["other_inputs"], list) else []
            ok = len(ci) >= 4 and len(oi) >= 3 and None not in ci and None not in oi
        append(PROPOSALS, {**row, "ok": ok, **({k: obj[k] for k in keys} if ok else {}),
                           "error": "" if ok else res.get("error", "parse")})
    e1.run_pool(jobs, one, workers, f"e6 propose {split}")


def proposals(split: str) -> dict:
    return {r["problem_id"]: r for r in load(PROPOSALS) if r.get("ok") and not r.get("skip") and r["split"] == split}


def stage_implement(split: str, workers: int) -> None:
    props = proposals(split)
    probs = {p.problem_id: p for p in problems(split)}
    have = {(r["problem_id"], r["contract"], r["route"]) for r in load(IMPLS) if r.get("ok")}
    jobs = [(pid, c, rt) for pid in props for c in ("a", "b") for rt in IMPL_ROUTES if (pid, c, rt) not in have]

    def one(job):
        pid, c, rt = job
        p, pr = probs[pid], props[pid]
        payload = IMPL_PROMPT.format(spec=p.spec, rule=pr[f"rule_{c}"])
        res = e1.call(rt, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        ok = isinstance(obj, dict) and isinstance(obj.get("code"), str) and p.entry_point in obj["code"]
        append(IMPLS, {"problem_id": pid, "contract": c, "route": rt, "ok": ok, "prompt_sha256": sha(payload),
                       "code": obj["code"] if ok else None, "error": "" if ok else res.get("error", "parse")})
    e1.run_pool(jobs, one, workers, f"e6 implement {split}")


def stage_validate(split: str, workers: int) -> None:
    props = proposals(split)
    probs = {p.problem_id: p for p in problems(split)}
    impls: dict = {}
    for r in load(IMPLS):
        if r.get("ok"):
            impls[(r["problem_id"], r["contract"], r["route"])] = r["code"]
    done_ids = {r["problem_id"] for r in load(PREUNITS)}
    jobs = [pid for pid in props if pid not in done_ids
            and all((pid, c, rt) in impls for c in ("a", "b") for rt in IMPL_ROUTES)]

    def one(pid):
        p, pr = probs[pid], props[pid]
        g, c = IMPL_ROUTES
        progs = {"ref": p.canonical_solution, "a1": impls[(pid, "a", g)], "a2": impls[(pid, "a", c)],
                 "b1": impls[(pid, "b", g)], "b2": impls[(pid, "b", c)]}
        row = {"problem_id": pid, "split": split, "impl_sha256": {k: sha(v) for k, v in progs.items()}}
        vis = {k: execute.run_suite(p.visible_program(v), instrumented=p.visible_instrumented).passed
               for k, v in progs.items() if k != "ref"}
        hidden = e1.hidden_inputs(p)
        if hidden is None:
            append(PREUNITS, {**row, "admitted": False, "reason": "no hidden inputs"})
            return
        cls = [literal_tuple(x) for x in pr["class_inputs"]]
        oth = [literal_tuple(x) for x in pr["other_inputs"]]
        inputs = list(hidden) + cls + oth
        pairs = [["ref", "b1"], ["ref", "b2"], ["a1", "a2"], ["a1", "b1"], ["a2", "b2"], ["ref", "a1"]]
        res = multi_compare(p, progs, pairs, inputs)
        if "infra" in res:
            append(PREUNITS, {**row, "admitted": False, "reason": "infra", "infra": res["infra"]})
            return
        rows = res["rows"]
        nh, nc = len(hidden), len(cls)
        H, C, O = rows[:nh], rows[nh:nh + nc], rows[nh + nc:]
        ref_valid = [r["status"]["ref"] == "ok" for r in rows]
        b_full = all(r["agree"]["ref~b1"] and r["agree"]["ref~b2"] for r in H)
        a_same = all(r["agree"]["a1~a2"] for r in rows)
        class_diff = sum(1 for r in C if r["agree"]["a1~b1"] is False and r["agree"]["a2~b2"] is False)
        other_same = all(r["agree"]["a1~b1"] and r["agree"]["a2~b2"] for r in O)
        hidden_changed = [i for i, r in enumerate(H) if r["agree"]["a1~b1"] is False]
        checks = {"visible": all(vis.values()), "b_pass_hidden": b_full, "a_impls_agree": a_same,
                  "class_differs_2": class_diff >= 2, "other_agree": other_same,
                  "class_inputs_valid": all(ref_valid[nh:nh + nc]), "other_inputs_valid": all(ref_valid[nh + nc:])}
        admitted = all(checks.values())
        append(PREUNITS, {**row, "admitted": admitted, "checks": checks, "visible": vis, "n_hidden": nh,
                       "n_class_differ": class_diff, "n_hidden_changed": len(hidden_changed),
                       "hidden_changed": hidden_changed[:200],
                       "reason": "ok" if admitted else ",".join(k for k, v in checks.items() if not v)})
    e1.run_pool(jobs, one, workers, f"e6 validate {split}")


# ---------------------------------------------------------------------------------------------
# independent probes and executable predicates (GPT review P3, blocker 1); admission v4
# ---------------------------------------------------------------------------------------------
PROBE_ROUTE = "adj-claude-opus"      # did not propose the rules
PROBE_PROMPT = """You are writing test material for a study of code review. Below is a programming task (description and
visible tests) and two rules that a task author might add for some inputs. Do not decide which rule is right.

TASK:
{spec}

VISIBLE TESTS:
{visible}

RULE 1: {r1}
RULE 2: {r2}

Write, in Python with the standard library only:
- a predicate `valid(*args)` that returns True exactly when the positional arguments are valid inputs for the task as
  stated (types, ranges, preconditions such as "sorted", "positive", "same length", "1 to 12"), and False otherwise;
- a predicate `in_class(*args)` that returns True exactly when the arguments are inputs to which the two rules apply
  and on which they can lead to different results, and False otherwise;
- 16 to 24 probe calls, each a Python literal tuple of positional arguments with the exact types the task uses
  (one-argument calls written "(x,)"): at least 6 valid inputs inside the class including boundary cases, at least 6
  valid inputs outside the class including near-boundary cases, and up to 4 invalid inputs.
Both predicates must never raise. Reply with exactly one JSON object:
{{"valid": "def valid(*args):\n    ...", "in_class": "def in_class(*args):\n    ...", "probes": ["(...)", ...]}}
"""


def stage_probe(split: str, workers: int) -> None:
    props = proposals(split)
    probs = {p.problem_id: p for p in problems(split)}
    ok_ids = {u["problem_id"] for u in load(PREUNITS) if u.get("admitted")}
    have = {r["problem_id"] for r in load(PROBES) if r.get("ok")}
    jobs = [pid for pid in props if pid in ok_ids and pid not in have]

    def one(pid):
        p, pr = probs[pid], props[pid]
        a_first = int(sha("probe-order|" + pid), 16) % 2 == 0
        r1, r2 = (pr["rule_a"], pr["rule_b"]) if a_first else (pr["rule_b"], pr["rule_a"])
        payload = PROBE_PROMPT.format(spec=p.spec.rstrip(), visible=p.visible_tests_text(), r1=r1, r2=r2)
        res = e1.call(PROBE_ROUTE, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        ok = (isinstance(obj, dict) and isinstance(obj.get("valid"), str) and isinstance(obj.get("in_class"), str)
              and "def valid" in obj["valid"] and "def in_class" in obj["in_class"]
              and isinstance(obj.get("probes"), list))
        probes = [literal_tuple(x) for x in obj["probes"]] if ok else []
        ok = ok and len([x for x in probes if x is not None]) >= 12
        append(PROBES, {"problem_id": pid, "split": split, "route": PROBE_ROUTE, "ok": ok, "prompt_sha256": sha(payload),
                        **({"valid": obj["valid"], "in_class": obj["in_class"],
                            "probes": [x for x in obj["probes"] if literal_tuple(x) is not None]} if ok else {}),
                        "error": "" if ok else res.get("error", "parse")})
    e1.run_pool(jobs, one, workers, f"e6 probe {split}")


CLASSPRED_PROMPT = """Earlier you described a kind of input for the task below. Write a Python predicate
`in_class(*args)` (standard library only, never raising) that returns True exactly when the positional arguments are
an input of that kind, whether or not the two rules happen to give different results on that particular input, and
False for every other input. It must return True on each CLASS input and False on each OTHER input listed.

TASK:
{spec}

KIND OF INPUT: {cls}
RULE 1: {r1}
RULE 2: {r2}
CLASS INPUTS: {ci}
OTHER INPUTS: {oi}

Reply with exactly one JSON object: {{"in_class": "def in_class(*args):\n    ..."}}
"""


def stage_classpred(split: str, workers: int) -> None:
    """The class predicate comes from the proposer, which defined the class; `valid` and the probes stay independent."""
    props = proposals(split)
    probs = {p.problem_id: p for p in problems(split)}
    rows = [r for r in load(PROBES) if r.get("ok")]
    jobs = [r for r in rows if "in_class_proposer" not in r and r["problem_id"] in props]
    have = {r["problem_id"] for r in load(PROBES) if r.get("in_class_proposer")}
    jobs = [r for r in jobs if r["problem_id"] not in have]

    def one(r):
        pid = r["problem_id"]
        pr = props[pid]
        payload = CLASSPRED_PROMPT.format(spec=probs[pid].spec.rstrip(), cls=pr["class"], r1=pr["rule_a"],
                                          r2=pr["rule_b"], ci=pr["class_inputs"], oi=pr["other_inputs"])
        res = e1.call(PROPOSE_ROUTE, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        if isinstance(obj, dict) and isinstance(obj.get("in_class"), str) and "def in_class" in obj["in_class"]:
            append(PROBES, {**r, "in_class_proposer": obj["in_class"], "classpred_sha256": sha(payload)})
    e1.run_pool(jobs, one, workers, f"e6 classpred {split}")


_STR_MUT = ["", " ", "\v", "\f", "\u00a0", "\u2003", "\t\n", "è", "É", "ß", "Σ", "ΟΣ", "Ο\u0301Σ", "İ", "ǅ",
            "\u0301", "😀", "a" * 300]
_NUM_MUT = [0, -1, 1, 10 ** 16, -(10 ** 16), 2 ** 63, 0.5, -0.0, 1e308, -1e308, 1e-308, 3.5]


def _mutants(x, rng, depth=0):
    """Type-guided stress values for one argument: unicode and whitespace for strings, extremes and int/float
    widening for numbers, empty/singleton/duplicated/mixed containers."""
    out = []
    if isinstance(x, bool):
        return [not x]
    if isinstance(x, str):
        out += [m for m in _STR_MUT] + [x + m for m in _STR_MUT[1:8]] + [m + x for m in ("\u00a0", "Σ", "è")]
        out += [x.upper(), x.lower(), x * 3]
    elif isinstance(x, int):
        out += _NUM_MUT + [x + 0.5, float(x), -x, x * 10 ** 12]
    elif isinstance(x, float):
        out += _NUM_MUT + [round(x), -x, x * 1e300]
    elif isinstance(x, (list, tuple)) and depth < 2:
        t = type(x)
        out += [t(), t(x[:1]), t(list(x) + list(x[:1])), t(list(x)[::-1])]
        if x and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in x):
            out += [t([-1e308, 1e308]), t([1e308, 1e308]), t([10 ** 16, 1, -(10 ** 16)]), t([0.1, 0.2, 0.3]),
                    t([-0.0, 0.0]), t([v + 0.5 for v in x])]
        if x and all(isinstance(v, str) for v in x):
            out += [t(["Σ", "σ"]), t(["è", "e"]), t(["\u00a0", " "]), t(["", ""])]
        if x:
            for m in _mutants(x[0], rng, depth + 1)[:12]:
                out.append(t([m] + list(x[1:])))
                if len(x) > 1:
                    out.append(t(list(x[:-1]) + [m]))
    elif isinstance(x, dict) and depth < 2:
        out += [{}, {**x, "": None}, {**x, "Σ": 0}]
    return out


def stress_inputs(hidden: list, n: int = 120, seed: str = "") -> list:
    """Deterministic stress inputs: each argument of a few hidden inputs replaced by its mutants (P4 blocker 1)."""
    rng = random.Random(int(sha("stress|" + seed), 16))
    base = [h for h in hidden if isinstance(h, (list, tuple))][:6]
    out = []
    for h in base:
        for i, arg in enumerate(h):
            for m in _mutants(arg, rng):
                out.append(tuple(list(h[:i]) + [m] + list(h[i + 1:])))
    rng.shuffle(out)
    seen, uniq = set(), []
    for x in out:
        k = repr(x)
        if k not in seen and len(k) < 5000:
            seen.add(k)
            uniq.append(x)
    return uniq[:n]


def predicate_src(src: str, name: str, entry: str) -> str:
    return src + f"\n\n{entry} = {name}\n"


def stage_validate4(split: str, workers: int) -> None:
    """Admission v4: on every valid input (by the executable `valid` predicate) among the hidden inputs, the proposer's
    inputs and the independent probes, both B implementations agree with the reference; outside the class (by
    `in_class`) all four implementations agree with the reference; inside it the two A implementations agree; A and B
    differ on at least two valid class inputs; the proposer's class inputs are valid and in class and its other inputs
    valid and out of class; the predicates never raise; all implementations pass the visible tests."""
    props = proposals(split)
    probs = {p.problem_id: p for p in problems(split)}
    pr_rows = {r["problem_id"]: r for r in load(PROBES) if r.get("ok") and r.get("in_class_proposer")}
    impls = {(r["problem_id"], r["contract"], r["route"]): r["code"] for r in load(IMPLS) if r.get("ok")}
    done_ids = {r["problem_id"] for r in load(UNITS)}
    jobs = [pid for pid in pr_rows if pid in props and pid not in done_ids]

    def one(pid):
        p, pr, pb = probs[pid], props[pid], pr_rows[pid]
        g, c = IMPL_ROUTES
        progs = {"ref": p.canonical_solution, "a1": impls[(pid, "a", g)], "a2": impls[(pid, "a", c)],
                 "b1": impls[(pid, "b", g)], "b2": impls[(pid, "b", c)],
                 "valid": predicate_src(pb["valid"], "valid", p.entry_point),
                 "in_class": predicate_src(pb["in_class_proposer"], "in_class", p.entry_point)}
        row = {"problem_id": pid, "split": split, "impl_sha256": {k: sha(v) for k, v in progs.items()},
               "probe_sha256": sha(json.dumps(pb, sort_keys=True))}
        vis = {k: execute.run_suite(p.visible_program(progs[k]), instrumented=p.visible_instrumented).passed
               for k in ("a1", "a2", "b1", "b2")}
        hidden = e1.hidden_inputs(p) or []
        cls = [literal_tuple(x) for x in pr["class_inputs"]]
        oth = [literal_tuple(x) for x in pr["other_inputs"]]
        prb = [literal_tuple(x) for x in pb["probes"]]
        stress = stress_inputs(list(hidden) + cls + oth, seed=pid)
        inputs = list(hidden) + cls + oth + prb + stress
        pairs = [["ref", "b1"], ["ref", "b2"], ["a1", "a2"], ["ref", "a1"], ["ref", "a2"], ["a1", "b1"], ["a2", "b2"]]
        res = multi_compare(p, progs, pairs, inputs, capture=["valid", "in_class"])
        if "infra" in res:
            append(UNITS, {**row, "admitted": False, "reason": "infra", "infra": res["infra"]})
            return
        rows = res["rows"]
        pred_ok = all(r["status"]["valid"] == "ok" and r["status"]["in_class"] == "ok"
                      and "valid" in r["value"] and "in_class" in r["value"] for r in rows)
        bad = {"b_vs_ref": [], "outside_class": [], "a_disagree": []}
        n_sep = 0
        for i, r in enumerate(rows):
            if not (r["value"].get("valid") and r["status"]["ref"] == "ok"):
                continue
            ag = r["agree"]
            if not (ag["ref~b1"] and ag["ref~b2"]):
                bad["b_vs_ref"].append(i)
            if r["value"].get("in_class"):
                if not ag["a1~a2"]:
                    bad["a_disagree"].append(i)
                if ag["a1~b1"] is False and ag["a2~b2"] is False:
                    n_sep += 1
            elif not (ag["ref~a1"] and ag["ref~a2"]):
                bad["outside_class"].append(i)
        nh, nc, no = len(hidden), len(cls), len(oth)
        cls_rows, oth_rows = rows[nh:nh + nc], rows[nh + nc:nh + nc + no]
        consistent = (all(r["value"].get("valid") and r["value"].get("in_class") for r in cls_rows)
                      and all(r["value"].get("valid") and not r["value"].get("in_class") for r in oth_rows))
        checks = {"visible": all(vis.values()), "predicates_total": pred_ok, "b_agree_ref": not bad["b_vs_ref"],
                  "outside_class_agree": not bad["outside_class"], "a_impls_agree": not bad["a_disagree"],
                  "separates_2": n_sep >= 2, "predicates_match_proposer": consistent}
        admitted = all(checks.values())
        append(UNITS, {**row, "admitted": admitted, "checks": checks, "n_inputs": len(inputs), "n_stress": len(stress),
                       "n_separating": n_sep,
                       "n_valid": sum(1 for r in rows if r["value"].get("valid")),
                       "n_in_class": sum(1 for r in rows if r["value"].get("valid") and r["value"].get("in_class")),
                       "bad": {k: v[:20] for k, v in bad.items()},
                       "reason": "ok" if admitted else ",".join(k for k, v in checks.items() if not v)})
    e1.run_pool(jobs, one, workers, f"e6 validate4 {split}")


# ---------------------------------------------------------------------------------------------
# validation without human raters: a blind two-vendor judge panel and behavioural evidence
# ---------------------------------------------------------------------------------------------
JUDGE = REC / "e6_judgements.jsonl"
BEHAV = REC / "e6_behaviour.jsonl"
JUDGE_ROUTES = ("adj-claude-opus", "adj-gpt-sol")    # neither proposed the rules nor audits

JUDGE_PROMPT = """You are checking material for a study of code review. Answer strictly from the task's words and
visible tests; do not run code.

TASK (as given to a programmer):
{spec}

VISIBLE TESTS:
{visible}

Below are two rules a task author might add. First decide whether the inputs the rules concern are valid inputs for
the task as stated (types, ranges, preconditions). Then, for EACH rule separately, decide whether the task's words and
visible tests allow a function that follows it. The absence of an example is not by itself permission: a rule is
"incompatible" if the words, ordinary meaning (for example mathematical facts) or the visible tests rule it out.
RULE 1: {r1}
RULE 2: {r2}

Reply with exactly one JSON object:
{{"domain": "valid" | "invalid" | "unresolved", "rule1": "compatible" | "incompatible" | "unresolved",
  "rule2": "compatible" | "incompatible" | "unresolved", "reason": "one or two sentences citing the words"}}
"""


def stage_judge(split: str, workers: int) -> None:
    adm = {u["problem_id"] for u in load(UNITS) if u.get("admitted")}
    props = {pid: pr for pid, pr in proposals(split).items() if pid in adm}
    probs = {p.problem_id: p for p in problems(split)}
    have = {(r["problem_id"], r["judge"]) for r in load(JUDGE) if r.get("ok")}
    jobs = [(pid, j) for pid in props for j in JUDGE_ROUTES if (pid, j) not in have]

    def one(job):
        pid, j = job
        pr = props[pid]
        a_first = int(sha("judge-order|" + pid), 16) % 2 == 0
        r1, r2 = (pr["rule_a"], pr["rule_b"]) if a_first else (pr["rule_b"], pr["rule_a"])
        payload = JUDGE_PROMPT.format(spec=probs[pid].spec.rstrip(), visible=probs[pid].visible_tests_text(), r1=r1, r2=r2)
        res = e1.call(j, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        vals = ("compatible", "incompatible", "unresolved")
        ok = (isinstance(obj, dict) and obj.get("rule1") in vals and obj.get("rule2") in vals
              and obj.get("domain") in ("valid", "invalid", "unresolved"))
        row = {"problem_id": pid, "judge": j, "ok": ok, "prompt_sha256": sha(payload),
               "error": "" if ok else res.get("error", "parse")}
        if ok:
            row.update({"domain": obj["domain"],
                        "a": obj["rule1"] if a_first else obj["rule2"], "b": obj["rule2"] if a_first else obj["rule1"],
                        "reason": str(obj.get("reason", ""))[:600]})
        append(JUDGE, row)
    e1.run_pool(jobs, one, workers, f"e6 judge {split}")


def stage_behaviour(split: str, workers: int) -> None:
    """Which rule do independent solutions written from the task alone follow? Every E1 generation (two vendors,
    six samples each) that passes the visible tests is run on the unit's class inputs where A and B differ."""
    us = {u["problem_id"]: u for u in load(UNITS) if u.get("admitted") and u["split"] == split}
    props = proposals(split)
    probs = {p.problem_id: p for p in problems(split)}
    impls = {(r["problem_id"], r["contract"], r["route"]): r["code"] for r in load(IMPLS) if r.get("ok")}
    gens: dict = {}
    for r in load(e1.GEN_PATH):
        if r.get("ok") and r.get("solution") and r["problem_id"] in us:
            gens.setdefault(r["problem_id"], []).append(r)
    done = {r["problem_id"] for r in load(BEHAV)}
    jobs = [pid for pid in us if pid not in done]

    def one(pid):
        p, pr = probs[pid], props[pid]
        cls = [literal_tuple(x) for x in pr["class_inputs"]]
        progs = {"A": impls[(pid, "a", IMPL_ROUTES[0])], "B": impls[(pid, "b", IMPL_ROUTES[0])]}
        sols = []
        for g in gens.get(pid, []):
            if execute.run_suite(p.visible_program(g["solution"]), instrumented=p.visible_instrumented).passed:
                key = f"g{len(sols)}"
                progs[key] = g["solution"]
                sols.append((key, g["generator"], g["sample"]))
        pairs = [["A", "B"]] + [[k, x] for k, _, _ in sols for x in ("A", "B")]
        res = multi_compare(p, progs, pairs, cls)
        if "infra" in res:
            append(BEHAV, {"problem_id": pid, "infra": res["infra"]})
            return
        diff = [i for i, r in enumerate(res["rows"]) if r["agree"]["A~B"] is False]
        follows = []
        for k, gen, smp in sols:
            fa = all(res["rows"][i]["agree"][f"{k}~A"] for i in diff)
            fb = all(res["rows"][i]["agree"][f"{k}~B"] for i in diff)
            follows.append({"generator": gen, "sample": smp, "rule": "A" if fa else "B" if fb else "other"})
        n = lambda x: sum(1 for f in follows if f["rule"] == x)
        append(BEHAV, {"problem_id": pid, "n_visible_passing": len(sols), "n_diff_inputs": len(diff),
                       "n_A": n("A"), "n_B": n("B"), "n_other": n("other"), "follows": follows})
    e1.run_pool(jobs, one, workers, f"e6 behaviour {split}")


# ---------------------------------------------------------------------------------------------
# audits
# ---------------------------------------------------------------------------------------------
AUD = REC / "e6_audits.jsonl"
AUD_RAW = REC / "e6_audits_raw.jsonl"
WIT = REC / "e6_witnesses.jsonl"
OPEN_ARMS = ("none", "menu", "resolve-a", "resolve-b", "sentence-a", "sentence-b")
ARMS = OPEN_ARMS
CONFIGS = ("aud-gpt-terra-low", "aud-gpt-terra-high", "aud-claude-sonnet-low", "aud-claude-sonnet-high")
SENTENCE_CONFIGS = ("aud-gpt-terra-low", "aud-claude-sonnet-low")   # ordinary-language reveal: one budget per vendor
READINGS = 2
PROTOCOL = "e6-v4"
MAX_ATTEMPTS = 3


def units(split: str) -> dict:
    """Admitted units with their audited and oracle implementations. The audited vendor alternates by a hash of the
    problem id; the oracle for each contract is the other vendor's implementation of it."""
    props = proposals(split)
    impls = {(r["problem_id"], r["contract"], r["route"]): r["code"] for r in load(IMPLS) if r.get("ok")}
    probes = {r["problem_id"]: r for r in load(PROBES) if r.get("ok") and r.get("in_class_proposer")}
    pmap = {p.problem_id: p for p in problems(split)}
    refs = {pid: p.canonical_solution for pid, p in pmap.items()}
    out = {}
    for u in load(UNITS):
        if not (u.get("admitted") and u["split"] == split):
            continue
        pid = u["problem_id"]
        shown = IMPL_ROUTES[int(sha(pid), 16) % 2]
        other = IMPL_ROUTES[1 - IMPL_ROUTES.index(shown)]
        first_a = int(sha("menu-order|" + pid), 16) % 2 == 0          # menu order, fixed per unit
        # v4 oracles: contract B is the benchmark reference itself; contract A is the other vendor's A implementation
        # (admission requires both A implementations to agree in class and to equal the reference outside it)
        out[pid] = {**props[pid], "shown_route": shown, "first_a": first_a,
                    "program": {c: impls[(pid, c, shown)] for c in "ab"},
                    "oracle": {"a": impls[(pid, "a", other)], "b": refs[pid]},
                    "valid": probes[pid]["valid"], "in_class": probes[pid]["in_class_proposer"],
                    "comparator_sha": sha(json.dumps(suite_assertion(pmap[pid])))}
    return out


def arm_text(u: dict, arm: str) -> str:
    """Text appended to the task. v4: no class description (rules carry their own condition). The menu bytes are
    identical in every arm that shows them and do not depend on the contract; a resolving arm adds one selection
    sentence of equal form; a sentence arm states one rule as an ordinary requirement, with no menu."""
    if arm == "none":
        return ""
    if arm.startswith("sentence-"):
        return "\n\nAdditional requirement: " + u["rule_" + arm.split("-")[1]].strip()
    first, second = ("a", "b") if u["first_a"] else ("b", "a")
    menu = ("\n\nAdditional requirement: the function must follow exactly one of these two rules, and the task "
            f"author has fixed which.\n(1) {u['rule_' + first].strip()}\n(2) {u['rule_' + second].strip()}")
    if arm == "menu":
        return menu + "\nThe task does not say which of the two rules applies."
    chosen = arm.split("-")[1]
    return menu + f"\nThe function must follow rule ({1 if chosen == first else 2})."


def configs_for(arm: str) -> tuple:
    return SENTENCE_CONFIGS if arm.startswith("sentence-") else CONFIGS


def schedule(split: str) -> list[tuple]:
    """The required reading universe: every (unit, program, arm, configuration, reading)."""
    return [(pid, prog, arm, cfg, k) for pid in sorted(units(split)) for prog in "ab" for arm in ARMS
            for cfg in configs_for(arm) for k in range(READINGS)]


def stage_audit(split: str, workers: int) -> None:
    from crossaudit.auditor.validate import known_rules, parse_reply, validate_reply
    import ceiling
    us = units(split)
    probs = {p.problem_id: p for p in problems(split)}
    rows = load(AUD)
    ok_keys = {tuple(r["key"]) for r in rows if r.get("ok")}
    tries: dict = {}
    for r in rows:
        if counts_as_attempt(r):
            tries[tuple(r["key"])] = tries.get(tuple(r["key"]), 0) + 1
    jobs = [j for j in schedule(split) if j not in ok_keys and tries.get(j, 0) < MAX_ATTEMPTS]
    __import__("random").Random(17).shuffle(jobs)

    def one(job):
        pid, prog, arm, cfg, k = job
        p, u = probs[pid], us[pid]
        payload = e1.audit_prompt(p, u["program"][prog], p.spec + arm_text(u, arm))
        res = e1.call(cfg, payload, timeout=900)
        row = {"key": list(job), "split": split, "protocol": PROTOCOL, "prompt_sha256": sha(payload), "wall_s": res["wall_s"],
               "usage": res.get("usage"), "attempt": tries.get(job, 0) + 1}
        append(AUD_RAW, {"key": list(job), "attempt": row["attempt"], "text": res["text"], "raw": res.get("raw", ""),
                         "error": res.get("error", "")})
        if not res["ok"]:
            append(AUD, {**row, "ok": False, "error": res.get("error", "")[:200]})
            return
        text, _ = ceiling.astra_extract(res["text"])
        reply, err = parse_reply(text)
        invalid = validate_reply(reply, known_rules(e1._cfg["constitution"])) if reply is not None else "unparsed"
        if reply is None or invalid:
            append(AUD, {**row, "ok": False, "error": f"invalid reply: {err or invalid}"[:200]})
            return
        findings = reply.get("findings") or []
        blockers = [f for f in findings if f.get("severity") == "BLOCKER"]
        witnesses = [{"call": c.strip(), "expected": e.strip()}
                     for f in blockers for c, e in e1._WIT.findall(f.get("observation", ""))]
        append(AUD, {**row, "ok": True, "flagged": bool(blockers), "n_findings": len(findings),
                     "escalated": str(reply.get("verdict", "")).upper().startswith("ESCALATE"),
                     "n_blockers": len(blockers), "witnesses": witnesses[:6], "verdict": reply.get("verdict", ""),
                     "blocker_text": [str(f.get("observation", ""))[:600] for f in blockers][:6]})
    e1.run_pool(jobs, one, workers, f"e6 audit {split}")


def witness_key(r: dict, u: dict, contract: str, p=None) -> str:
    """Binds scorer version and source, the suite comparator and tolerance, program, both oracles, predicates,
    contract and witness text."""
    prog = r["key"][1]
    comp = sha(json.dumps(suite_assertion(p))) if p is not None else u.get("comparator_sha", "")
    return sha(json.dumps([e1.SCORER, sha(e1.JUDGE), sha(MULTI), comp, u["program"][prog], u["oracle"]["a"],
                           u["oracle"]["b"], u["valid"], u["in_class"], contract, r["witnesses"]], sort_keys=True))


def stage_witness(split: str, workers: int) -> None:
    """Score each reading's witnesses under BOTH contracts. A witness counts only on a valid input (the executable
    `valid` predicate); it is a target-discrepancy witness if the input is in the class (`in_class`)."""
    us = units(split)
    probs = {p.problem_id: p for p in problems(split)}
    have = {r["input_sha256"] for r in load(WIT) if not r.get("infra")}
    jobs = [(r, c) for r in load(AUD) if r.get("ok") and r.get("witnesses") and r["split"] == split
            and r.get("protocol") == PROTOCOL for c in "ab"
            if r["key"][0] in us and witness_key(r, us[r["key"][0]], c, probs[r["key"][0]]) not in have]

    def one(job):
        r, c = job
        pid, prog = r["key"][0], r["key"][1]
        p, u = probs[pid], us[pid]
        out = []
        for w in r["witnesses"]:
            parsed = e1.parse_call(w["call"], p.entry_point)
            if parsed is None or parsed[1]:
                out.append({"status": "unparseable"})
                continue
            pr = multi_compare(p, {"valid": predicate_src(u["valid"], "valid", p.entry_point),
                                   "in_class": predicate_src(u["in_class"], "in_class", p.entry_point),
                                   "oa": u["oracle"]["a"], "ob": u["oracle"]["b"]},
                               [["oa", "ob"]], [parsed[0]], capture=["valid", "in_class"])
            if "infra" in pr:
                out.append({"status": "infra", "detail": pr["infra"][:200]})
                continue
            row = pr["rows"][0]
            res = e1.judge_witness(p, u["program"][prog], w["call"], w["expected"], oracle=u["oracle"][c])
            out.append({**res, "valid": bool(row["value"].get("valid")), "in_class": bool(row["value"].get("in_class")),
                        "oracles_differ": row["agree"]["oa~ob"] is False})
        target = lambda x: (x.get("verified_diagnosis") and x.get("valid") and x.get("in_class")
                            and x.get("oracles_differ"))
        append(WIT, {"key": r["key"], "contract": c, "input_sha256": witness_key(r, u, c, p), "scorer": e1.SCORER,
                     "results": out, "infra": any(x["status"] == "infra" for x in out),
                     "verified_diagnosis": any(target(x) for x in out),
                     # sensitivity: the benchmark reference's own domain (it runs) instead of the `valid` predicate
                     "verified_refdomain": any(x.get("verified_diagnosis") and x.get("in_class")
                                               and x.get("oracles_differ") for x in out),
                     "verified_offclass": any(x.get("verified_diagnosis") and x.get("valid")
                                              and not x.get("in_class") for x in out)})
    e1.run_pool(jobs, one, workers, f"e6 witness {split}")


PRE_MODEL_INFRA = ("refresh token", "auth.openai.com", "Not logged in", "Please run /login", "ECONNREFUSED")


def counts_as_attempt(r: dict) -> bool:
    """A failure that never reached the model (login refresh, connection refused) does not consume an attempt."""
    return r.get("ok") or not any(m in str(r.get("error", "")) for m in PRE_MODEL_INFRA)


def expected_prompt_sha(u: dict, p, prog: str, arm: str, cache: dict) -> str:
    k = (p.problem_id, prog, arm)
    if k not in cache:
        cache[k] = sha(e1.audit_prompt(p, u["program"][prog], p.spec + arm_text(u, arm)))
    return cache[k]


def completeness(split: str, check_prompts: bool = True) -> dict:
    """Every required reading valid or exhausted (pre-model infrastructure failures excluded); no duplicate valid
    reading; every valid reading's prompt hash equals the prompt rebuilt from the frozen unit; every flagged valid
    reading with witnesses has exactly one, infrastructure-free score under each contract. Readings of units outside
    the current population (superseded by a later admission) are counted, not used. Raises otherwise."""
    us = units(split)
    probs = {p.problem_id: p for p in problems(split)}
    rows = [r for r in load(AUD) if r["split"] == split and r.get("protocol") == PROTOCOL]
    need = set(schedule(split))
    ok, tries, superseded, cache = {}, {}, 0, {}
    for r in rows:
        k = tuple(r["key"])
        if k[0] not in us:
            superseded += 1
            continue
        if k not in need:
            raise SystemExit(f"reading outside the required universe: {k}")
        if counts_as_attempt(r):
            tries[k] = tries.get(k, 0) + 1
        if r.get("ok"):
            if k in ok:
                raise SystemExit(f"duplicate valid reading: {k}")
            if check_prompts and r["prompt_sha256"] != expected_prompt_sha(us[k[0]], probs[k[0]], k[1], k[2], cache):
                raise SystemExit(f"prompt hash mismatch: {k}")
            ok[k] = r
    unfinished = [k for k in need if k not in ok and tries.get(k, 0) < MAX_ATTEMPTS]
    scores: dict = {}
    for w in load(WIT):
        if not w.get("infra"):
            prev = scores.get(w["input_sha256"])
            if prev is not None and prev != w["verified_diagnosis"]:
                raise SystemExit(f"conflicting witness scores under one key: {w['key']}")
            scores[w["input_sha256"]] = w["verified_diagnosis"]
    unscored = [k for k, r in ok.items() if r.get("witnesses")
                and any(witness_key(r, us[k[0]], c, probs[k[0]]) not in scores for c in "ab")]
    if unfinished or unscored:
        raise SystemExit(f"incomplete: {len(unfinished)} unfinished readings, {len(unscored)} unscored witness sets")
    return {"required": len(need), "valid": len(ok), "superseded_readings": superseded,
            "exhausted": sorted(set(need) - set(ok))}


set_kind("open")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["propose", "implement", "validate", "probe", "classpred", "validate4", "judge", "behaviour",
                                      "audit", "witness"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--kind", choices=["open", "det"], default="open")
    a = ap.parse_args()
    set_kind(a.kind)
    {"propose": stage_propose, "implement": stage_implement, "validate": stage_validate, "probe": stage_probe,
     "classpred": stage_classpred, "validate4": stage_validate4, "judge": stage_judge,
     "behaviour": stage_behaviour, "audit": stage_audit,
     "witness": stage_witness}[a.stage](a.split, a.workers)
