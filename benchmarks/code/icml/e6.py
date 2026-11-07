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
    global KIND, PROPOSALS, IMPLS, UNITS, JUDGE, BEHAV, AUD, AUD_RAW, WIT, ARMS
    KIND = kind
    pre = "e6_" if kind == "open" else "e6det_"
    PROPOSALS, IMPLS, UNITS = REC / f"{pre}proposals.jsonl", REC / f"{pre}impls.jsonl", REC / f"{pre}units.jsonl"
    JUDGE, BEHAV = REC / f"{pre}judgements.jsonl", REC / f"{pre}behaviour.jsonl"
    AUD, AUD_RAW, WIT = REC / f"{pre}audits.jsonl", REC / f"{pre}audits_raw.jsonl", REC / f"{pre}witnesses.jsonl"
    ARMS = ("none", "menu", "resolve-a", "resolve-b") if kind == "open" else ("none",)
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
                 "agree": {f"{a}~{b}": agrees(out[a], out[b]) for a, b in spec["pairs"]}})
with open(spec["out"], "w") as fh:
    fh.write(json.dumps(rows))
'''


def multi_compare(p, programs: dict, pairs: list, inputs: list, limit: int = 5) -> dict:
    """Run every program on every input in one executor process; compare the given pairs with the suite's own
    assertion. Results come back through a file."""
    helpers, atol = suite_assertion(p)
    pre = imports_of(p) + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        spec = {"helpers": helpers, "atol": float(e1.literal(atol)), "entry": p.entry_point, "limit": limit,
                "inputs": base64.b64encode(pickle.dumps(inputs)).decode(), "pairs": pairs,
                "programs": {k: pre + v for k, v in programs.items()}, "out": str(Path(tmp) / "out.json")}
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
    done_ids = {r["problem_id"] for r in load(UNITS)}
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
            append(UNITS, {**row, "admitted": False, "reason": "no hidden inputs"})
            return
        cls = [literal_tuple(x) for x in pr["class_inputs"]]
        oth = [literal_tuple(x) for x in pr["other_inputs"]]
        inputs = list(hidden) + cls + oth
        pairs = [["ref", "b1"], ["ref", "b2"], ["a1", "a2"], ["a1", "b1"], ["a2", "b2"], ["ref", "a1"]]
        res = multi_compare(p, progs, pairs, inputs)
        if "infra" in res:
            append(UNITS, {**row, "admitted": False, "reason": "infra", "infra": res["infra"]})
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
        append(UNITS, {**row, "admitted": admitted, "checks": checks, "visible": vis, "n_hidden": nh,
                       "n_class_differ": class_diff, "n_hidden_changed": len(hidden_changed),
                       "hidden_changed": hidden_changed[:200],
                       "reason": "ok" if admitted else ",".join(k for k, v in checks.items() if not v)})
    e1.run_pool(jobs, one, workers, f"e6 validate {split}")


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

Consider inputs of this kind: {cls}
Below are two rules for such inputs. For EACH rule separately, decide whether a careful programmer reading only the
task and the visible tests could accept a function that follows it, given that the task says nothing more.
RULE 1: {r1}
RULE 2: {r2}

For each rule answer "compatible" (the task's words and visible tests allow it), "incompatible" (they rule it out;
cite the words) or "unresolved". Reply with exactly one JSON object:
{{"rule1": "compatible" | "incompatible" | "unresolved", "rule2": "...", "reason": "one or two sentences"}}
"""


def stage_judge(split: str, workers: int) -> None:
    props = {pid: pr for pid, pr in proposals(split).items()
             if any(u["problem_id"] == pid and u.get("admitted") for u in load(UNITS))}
    probs = {p.problem_id: p for p in problems(split)}
    have = {(r["problem_id"], r["judge"]) for r in load(JUDGE) if r.get("ok")}
    jobs = [(pid, j) for pid in props for j in JUDGE_ROUTES if (pid, j) not in have]

    def one(job):
        pid, j = job
        pr = props[pid]
        a_first = int(sha("judge-order|" + pid), 16) % 2 == 0
        r1, r2 = (pr["rule_a"], pr["rule_b"]) if a_first else (pr["rule_b"], pr["rule_a"])
        payload = JUDGE_PROMPT.format(spec=probs[pid].spec.rstrip(), cls=pr["class"], r1=r1, r2=r2)
        res = e1.call(j, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        vals = ("compatible", "incompatible", "unresolved")
        ok = isinstance(obj, dict) and obj.get("rule1") in vals and obj.get("rule2") in vals
        row = {"problem_id": pid, "judge": j, "ok": ok, "prompt_sha256": sha(payload),
               "error": "" if ok else res.get("error", "parse")}
        if ok:
            row.update({"a": obj["rule1"] if a_first else obj["rule2"], "b": obj["rule2"] if a_first else obj["rule1"],
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
ARMS = ("none", "menu", "resolve-a", "resolve-b")
CONFIGS = ("aud-gpt-terra-low", "aud-gpt-terra-high", "aud-claude-sonnet-low", "aud-claude-sonnet-high")
READINGS = 2
MAX_ATTEMPTS = 3


def units(split: str) -> dict:
    """Admitted units with their audited and oracle implementations. The audited vendor alternates by a hash of the
    problem id; the oracle for each contract is the other vendor's implementation of it."""
    props = proposals(split)
    impls = {(r["problem_id"], r["contract"], r["route"]): r["code"] for r in load(IMPLS) if r.get("ok")}
    out = {}
    for u in load(UNITS):
        if not (u.get("admitted") and u["split"] == split):
            continue
        pid = u["problem_id"]
        shown = IMPL_ROUTES[int(sha(pid), 16) % 2]
        other = IMPL_ROUTES[1 - IMPL_ROUTES.index(shown)]
        first_a = int(sha("menu-order|" + pid), 16) % 2 == 0          # menu order, fixed per unit
        out[pid] = {**props[pid], "shown_route": shown, "first_a": first_a,
                    "program": {c: impls[(pid, c, shown)] for c in "ab"},
                    "oracle": {c: impls[(pid, c, other)] for c in "ab"}}
    return out


def arm_text(u: dict, arm: str) -> str:
    """Text appended to the task. The menu bytes are identical in every arm that shows them and do not depend on
    the contract; a resolving arm adds one selection sentence of equal form for either contract."""
    if arm == "none":
        return ""
    first, second = ("a", "b") if u["first_a"] else ("b", "a")
    menu = ("\n\nAdditional requirement. " + u["class"].strip().rstrip(".") + ": the function must follow exactly one "
            "of these two rules, and the task author has fixed which.\n"
            f"(1) {u['rule_' + first].strip()}\n(2) {u['rule_' + second].strip()}")
    if arm == "menu":
        return menu + "\nThe task does not say which of the two rules applies."
    chosen = arm.split("-")[1]
    return menu + f"\nThe function must follow rule ({1 if chosen == first else 2})."


def schedule(split: str) -> list[tuple]:
    return [(pid, prog, arm, cfg, k) for pid in sorted(units(split)) for prog in "ab" for arm in ARMS
            for cfg in CONFIGS for k in range(READINGS)]


def stage_audit(split: str, workers: int) -> None:
    from crossaudit.auditor.validate import known_rules, parse_reply, validate_reply
    import ceiling
    us = units(split)
    probs = {p.problem_id: p for p in problems(split)}
    rows = load(AUD)
    ok_keys = {tuple(r["key"]) for r in rows if r.get("ok")}
    tries: dict = {}
    for r in rows:
        tries[tuple(r["key"])] = tries.get(tuple(r["key"]), 0) + 1
    jobs = [j for j in schedule(split) if j not in ok_keys and tries.get(j, 0) < MAX_ATTEMPTS]
    __import__("random").Random(17).shuffle(jobs)

    def one(job):
        pid, prog, arm, cfg, k = job
        p, u = probs[pid], us[pid]
        payload = e1.audit_prompt(p, u["program"][prog], p.spec + arm_text(u, arm))
        res = e1.call(cfg, payload, timeout=900)
        row = {"key": list(job), "split": split, "prompt_sha256": sha(payload), "wall_s": res["wall_s"],
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
                     "n_blockers": len(blockers), "witnesses": witnesses[:6], "verdict": reply.get("verdict", ""),
                     "blocker_text": [str(f.get("observation", ""))[:600] for f in blockers][:6]})
    e1.run_pool(jobs, one, workers, f"e6 audit {split}")


def stage_witness(split: str, workers: int) -> None:
    """Score each reading's witnesses under BOTH contracts (the oracle implementations): under contract X the shown
    program is defective iff it implements the other contract."""
    us = units(split)
    probs = {p.problem_id: p for p in problems(split)}
    have = {(tuple(r["key"]), r["contract"]) for r in load(WIT) if not r.get("infra")}
    jobs = [(r, c) for r in load(AUD) if r.get("ok") and r.get("witnesses") and r["split"] == split
            for c in "ab" if (tuple(r["key"]), c) not in have]

    def one(job):
        r, c = job
        pid, prog = r["key"][0], r["key"][1]
        p, u = probs[pid], us[pid]
        res = [e1.judge_witness(p, u["program"][prog], w["call"], w["expected"], oracle=u["oracle"][c])
               for w in r["witnesses"]]
        append(WIT, {"key": r["key"], "contract": c, "scorer": e1.SCORER, "results": res,
                     "infra": any(x["status"] == "infra" for x in res),
                     "verified_diagnosis": any(x.get("verified_diagnosis") for x in res)})
    e1.run_pool(jobs, one, workers, f"e6 witness {split}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["propose", "implement", "validate", "judge", "behaviour", "audit", "witness"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--kind", choices=["open", "det"], default="open")
    a = ap.parse_args()
    set_kind(a.kind)
    {"propose": stage_propose, "implement": stage_implement, "validate": stage_validate, "judge": stage_judge,
     "behaviour": stage_behaviour, "audit": stage_audit,
     "witness": stage_witness}[a.stage](a.split, a.workers)
