"""E13: a shape control for E6's convention finding (audit-ceiling-paper/plan/icml2027/E13_DESIGN.md).

For every registered E6 open unit, the vendor that wrote the audited programs rewrites program B into B': the unit's
class inputs go through an explicit branch that reproduces B's behaviour; nothing else changes. Execution then checks
that B' equals B on every registered input and adds a conditional. Only B' is audited later; A's and B's readings are
E6's frozen ones. This module reads E6's records and writes only under benchmarks/e13/records.

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/e13/e13.py edit|check --split dev
"""
from __future__ import annotations

import ast
import base64
import json
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "code" / "icml")]
import e1                                          # noqa: E402
import e6                                          # noqa: E402
from e1 import execute                             # noqa: E402

REC = HERE / "records"
EDITS, CHECKS = REC / "edits.jsonl", REC / "checks.jsonl"
KINDS = ("open", "open2")
MAX_EDITS = 2                                     # one edit, and one second edit if the first fails its check

EDIT_PROMPT = """Below are a programming task and a correct solution to it. Rewrite the solution so that the inputs
described under CLASS are handled by an explicit `if` branch of their own, and inside that branch the code computes
exactly what the current solution computes for those inputs. The behaviour on every input must stay exactly the same;
outside the new branch, leave every line unchanged. Do not add comments, prints or names that mention the class, this
instruction or testing. Keep the function name and signature.

TASK:
{spec}

SOLUTION:
{program}

CLASS: {cls}

Reply with JSON only: {{"code": "<the complete rewritten solution>"}}"""


def conditionals(src: str) -> int:
    try:
        return sum(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(ast.parse(src)))
    except SyntaxError:
        return -1


def units(split: str) -> dict:
    """(kind, pid) -> E6 unit, for the registered population of each kind."""
    out = {}
    for kind in KINDS:
        e6.set_kind(kind)
        us = e6.units(split)
        for pid in e6.registered_units(split):
            out[(kind, pid)] = us[pid]
    e6.set_kind("open")
    return out


def latest(path: Path) -> dict:
    rows = {}
    for r in e1.load(path):
        rows.setdefault((r["kind"], r["problem_id"]), []).append(r)
    return rows


def stage_edit(split: str, workers: int) -> None:
    probs = {p.problem_id: p for p in e6.problems(split)}
    edits, checks = latest(EDITS), latest(CHECKS)
    jobs = []
    for key, u in units(split).items():
        done = edits.get(key, [])
        passed = any(c.get("passed") for c in checks.get(key, []))
        if passed or len(done) >= MAX_EDITS or (done and len(checks.get(key, [])) < len(done)):
            continue                                # passed, out of attempts, or last edit not yet checked
        jobs.append((key, u))

    def one(job):
        (kind, pid), u = job
        p = probs[pid]
        payload = EDIT_PROMPT.format(spec=p.spec.rstrip(), program=u["program"]["b"].rstrip(), cls=u["class"].strip())
        res = e1.call(u["shown_route"], payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        ok = isinstance(obj, dict) and isinstance(obj.get("code"), str) and p.entry_point in obj["code"]
        e1.append(EDITS, {"kind": kind, "problem_id": pid, "split": split, "route": u["shown_route"], "ok": ok,
                          "prompt_sha256": e6.sha(payload), "code": obj["code"] if ok else None,
                          "error": "" if ok else res.get("error", "parse"), "reached": e1.reached_model(res)})
    e1.run_pool(jobs, one, workers, f"e13 edit {split}")


def registered_inputs(kind: str, pid: str, p, u: dict) -> list:
    """E6's admission inputs for the unit: hidden suite, proposer, probes, stress and red-team inputs (interface
    inputs only, as in v4.3)."""
    e6.set_kind(kind)
    pb = {r["problem_id"]: r for r in e1.load(e6.PROBES) if r.get("ok") and r.get("in_class_proposer")}[pid]
    rt = [r for r in e1.load(e6.REDTEAM) if r["problem_id"] == pid and r.get("passed") is not None]
    e6.set_kind("open")
    hidden = e1.hidden_inputs(p) or []
    cls = [x for x in (e6.literal_tuple(s) for s in u["class_inputs"]) if x is not None]
    oth = [x for x in (e6.literal_tuple(s) for s in u["other_inputs"]) if x is not None]
    prb = [x for x in (e6.literal_tuple(s) for s in pb["probes"]) if x is not None]
    red = []
    for r in rt:                                   # older red-team rows keep only the repr of their inputs
        if r.get("inputs_b64"):
            red += pickle.loads(base64.b64decode(r["inputs_b64"]))
        else:
            red += [x for x in (e6.literal_tuple(s) for s in r.get("inputs", [])) if x is not None]
    allowed = e6.interface_types(hidden)
    stress = e6.stress_inputs(list(hidden) + cls + oth, seed=pid)
    return [x for x in list(hidden) + cls + oth + prb + stress + red if e6.conforms(x, allowed)]


def stage_check(split: str, workers: int) -> None:
    probs = {p.problem_id: p for p in e6.problems(split)}
    us = units(split)
    edits, checks = latest(EDITS), latest(CHECKS)
    jobs = [(key, rows[-1]) for key, rows in edits.items()
            if key in us and len(checks.get(key, [])) < len(rows)]

    def one(job):
        (kind, pid), ed = job
        p, u = probs[pid], us[(kind, pid)]
        row = {"kind": kind, "problem_id": pid, "split": split, "edit_sha256": e6.sha(ed["code"] or "")}
        if not ed["ok"]:
            e1.append(CHECKS, {**row, "passed": False, "reason": "no edit"})
            return
        b, bp = u["program"]["b"], ed["code"]
        inputs = registered_inputs(kind, pid, p, u)
        res = e6.multi_compare(p, {"b": b, "bp": bp}, [["b", "bp"]], inputs)
        if "infra" in res:
            e1.append(CHECKS, {**row, "passed": None, "reason": "infra", "infra": res["infra"]})
            return
        n = len(res["rows"])
        diff = [i for i, r in enumerate(res["rows"]) if r["status"]["b"] == "ok" and not r["agree"]["b~bp"]]
        diff += [i for i, r in enumerate(res["rows"]) if r["status"]["b"] != "ok" and r["status"]["bp"] == "ok"]
        visible = execute.run_suite(p.visible_program(bp), instrumented=p.visible_instrumented).passed
        added = conditionals(bp) - conditionals(b)
        passed = not diff and visible and added >= 1
        reason = "ok" if passed else ("differs from B" if diff else ("visible tests" if not visible else "no branch"))
        e1.append(CHECKS, {**row, "passed": passed, "reason": reason, "n_inputs": n, "n_differ": len(diff),
                           "visible": visible, "conditionals_added": added})
    e1.run_pool(jobs, one, workers, f"e13 check {split}")


# ---------------------------------------------------------------------------------------------------------------
# audits of B' with E6's frozen stages (module globals are looked up at call time, as in E10 and E11)
# ---------------------------------------------------------------------------------------------------------------
_orig_set_kind, _orig_units, _orig_registered, _orig_schedule = e6.set_kind, e6.units, e6.registered_units, e6.schedule


def passed_edits(split: str) -> dict:
    """(kind, pid) -> the B' that passed its check (the last passing edit)."""
    edits, checks = latest(EDITS), latest(CHECKS)
    out = {}
    for key, cs in checks.items():
        for c in cs:
            if c.get("passed"):
                code = next(e["code"] for e in edits[key] if e6.sha(e["code"] or "") == c["edit_sha256"])
                out[key] = code
    return out


def set_kind13(kind: str) -> None:
    _orig_set_kind(kind)
    e6.AUD, e6.AUD_RAW, e6.WIT = REC / f"{kind}_audits.jsonl", REC / f"{kind}_audits_raw.jsonl", REC / f"{kind}_witnesses.jsonl"
    e6.ARMS = ("none",)


def units13(split: str, ungated: bool = False) -> dict:
    us, bp = _orig_units(split, ungated), passed_edits(split)
    return {pid: {**u, "program": {"a": u["program"]["a"], "b": bp[(e6.KIND, pid)]}}
            for pid, u in us.items() if (e6.KIND, pid) in bp}


def registered13(split: str) -> list:
    bp = passed_edits(split)
    return [pid for pid in _orig_registered(split) if (e6.KIND, pid) in bp]


def schedule13(split: str) -> list:
    return [(pid, "b", "none", cfg, k) for pid in e6.registered_units(split) for cfg in e6.CONFIGS
            for k in range(e6.READINGS)]


def install_audit() -> None:
    e1.REC = REC                  # the audit prompt's rulebook project is built under e1.REC: keep E6's untouched
    e6.set_kind, e6.units, e6.registered_units, e6.schedule = set_kind13, units13, registered13, schedule13


def stage_audits(split: str, workers: int) -> None:
    if split == "test":
        verify()
    install_audit()
    sys.modules["freeze"] = __import__("types").SimpleNamespace(verify=verify)   # E6's audit stage calls freeze.verify
    for kind in KINDS:
        e6.set_kind(kind)
        e6.stage_audit(split, workers)
        e6.stage_witness(split, workers)
    e6.set_kind("open")


def analyse(split: str) -> dict:
    """E13-1: flag(B') - flag(B); E13-2: flag(A) - flag(B') and the convention advantage with B' in place of B; all
    in the task-alone arm with E6's four configurations, from E6's frozen cells for A and B and E13's cells for B'."""
    import analyse_e6 as A
    cells6, units6, _, _ = A.merged_open(split, allow_incomplete=False)     # before any patching
    if split == "test":
        verify()
        e6.set_kind, e6.units, e6.registered_units, e6.schedule = (_orig_set_kind, _orig_units, _orig_registered,
                                                                   _orig_schedule)
    install_audit()
    cells13 = {}
    for kind in KINDS:
        e6.set_kind(kind)
        c, _ = A.table(split)
        cells13.update({k: v for k, v in c.items() if k[1] == "b" and k[2] == "none"})
    e6.set_kind("open")
    have = {k[0] for k in cells13}
    units = [u for u in units6 if u in have]
    merged = {**cells6, **cells13}
    C, t = e6.CONFIGS, 1
    d1, d2, base = {}, {}, {}
    for pid in units:
        v6, vm = A.unit_value(cells6, pid, "none", C, t), A.unit_value(merged, pid, "none", C, t)
        if v6 is None or vm is None:
            continue
        d1[pid] = vm["flag_b"] - v6["flag_b"]
        d2[pid] = vm["flag_a"] - vm["flag_b"]
        base[pid] = v6["flag_a"] - v6["flag_b"]
    missing = len(units6) - len(d1)
    res = {"split": split, "n_registered": len(units6), "n_with_bprime": len(units), "n_analysed": len(d1),
           "E13_1_flag_bprime_minus_b": A.with_bounds(A.boot(d1), d1, missing, lo=-1.0, hi=1.0),
           "E13_2_flag_pref_shape_matched": A.with_bounds(A.boot(d2), d2, missing, lo=-1.0, hi=1.0),
           "E13_2b_convention_advantage_shape_matched": A.convention(merged, units, C, t),
           "reference_flag_pref_e6_same_units": A.boot(base),
           "reference_convention_e6_same_units": A.convention(cells6, units, C, t),
           "per_unit": {pid: {"d_flag_b": d1[pid], "pref_matched": d2[pid], "pref_e6": base[pid]} for pid in d1}}
    lo = res["E13_1_flag_bprime_minus_b"].get("lo")
    hi = res["E13_1_flag_bprime_minus_b"].get("hi")
    res["verdicts"] = {"E13_1": "shape effect" if lo is not None and lo > 0 else
                       ("no shape effect detected" if lo is not None and lo > -10 and hi < 10 else "unresolved"),
                       "E13_2": (res["E13_2_flag_pref_shape_matched"].get("lo") or 0) > 0}
    if split == "test":
        (REC / f"e13_results_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


# ---------------------------------------------------------------------------------------------------------------
# freeze (PREREGISTRATION-E13.md, Integrity)
# ---------------------------------------------------------------------------------------------------------------
MANIFEST = REC / "FREEZE13_test.json"


def _sha_file(f: Path) -> str:
    return e6.sha(f.read_text(errors="replace"))


def state(split: str) -> dict:
    import subprocess
    code = HERE.parent / "code"
    src = HERE.parents[1] / "src"
    files = [HERE / "e13.py", HERE / "PREREGISTRATION-E13.md", code / "icml" / "e6.py", code / "icml" / "e1.py",
             code / "icml" / "analyse_e6.py", code / "audit.py", code / "execute.py", code / "ceiling.py"]
    tree = {str(f.relative_to(src)): _sha_file(f) for pat in ("*.py", "*.md", "*.yml", "*.json")
            for f in sorted(src.rglob(pat)) if f.is_file() and "__pycache__" not in f.parts}
    pf = lambda py: subprocess.run([str(py), "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    install_audit()
    out = {"files": {str(f.relative_to(HERE.parents[1])): _sha_file(f) for f in files},
           "src": e6.sha(json.dumps(tree, sort_keys=True)), "venv": e6.sha(pf(sys.executable)),
           "executor": e6.sha(pf(execute.EXECUTOR)), "programs": {}, "readings": {}}
    for (kind, pid), code_bp in sorted(passed_edits(split).items()):
        out["programs"][f"{kind}|{pid}"] = e6.sha(code_bp)
    cache: dict = {}
    probs = {p.problem_id: p for p in e6.problems(split)}
    for kind in KINDS:
        e6.set_kind(kind)
        us = e6.units(split)
        for key in e6.schedule(split):
            out["readings"][f"{kind}|" + "|".join(map(str, key))] = e6.expected_prompt_sha(us[key[0]], probs[key[0]],
                                                                                         key[1], key[2], cache)
    e6.set_kind("open")
    return out


def heldout_audits_exist() -> bool:
    test = {p.problem_id for p in e6.problems("test")}
    return any(r["key"][0] in test for kind in KINDS for f in (f"{kind}_audits.jsonl", f"{kind}_audits_raw.jsonl")
               for r in e1.load(REC / f) if r.get("key"))


def write_freeze() -> None:
    if heldout_audits_exist():
        raise SystemExit("held-out E13 audit records exist: the freeze cannot be rewritten")
    us = units("test")
    edits, checks = latest(EDITS), latest(CHECKS)
    unfinished = [k for k in us if not any(c.get("passed") for c in checks.get(k, []))
                  and len(edits.get(k, [])) < MAX_EDITS]
    unchecked = [k for k, rows in edits.items() if k in us and len(checks.get(k, [])) < len(rows)]
    if unfinished or unchecked:
        raise SystemExit(f"construction unfinished: {unfinished[:5]} {unchecked[:5]}")
    MANIFEST.write_text(json.dumps(state("test"), indent=1, sort_keys=True))
    print("E13 frozen:", MANIFEST)


def verify() -> None:
    if not MANIFEST.exists():
        raise SystemExit("no E13 freeze")
    if json.loads(MANIFEST.read_text()) != json.loads(json.dumps(state("test"), sort_keys=True)):
        raise SystemExit("E13 freeze verification failed")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("edit", "check", "construct", "audit", "analyse", "freeze"))
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    REC.mkdir(exist_ok=True)
    if a.stage == "freeze":
        write_freeze()
        sys.exit(0)
    if a.stage == "analyse":
        r = analyse(a.split)
        print(json.dumps({k: v for k, v in r.items() if k != "per_unit"}, indent=1, default=str))
        sys.exit(0)
    if a.stage == "audit":
        stage_audits(a.split, a.workers)
        sys.exit(0)
    stages = ("edit", "check", "edit", "check") if a.stage == "construct" else (a.stage,)
    for s in stages:
        print(f"== {s}", flush=True)
        (stage_edit if s == "edit" else stage_check)(a.split, a.workers)
    by = latest(CHECKS)
    us = units(a.split)
    ok = sum(any(c.get("passed") for c in by.get(k, [])) for k in us)
    print(f"E13 {a.split}: {ok}/{len(us)} units with a checked B'")
