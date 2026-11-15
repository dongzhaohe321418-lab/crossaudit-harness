"""E13: a shape control for E6's convention finding (PREREGISTRATION-E13.md).

For every registered E6 open unit, the vendor that wrote the audited programs rewrites program B into B' (program
"c" here): the unit's class inputs go through an explicit branch that reproduces B's behaviour, every other line of B
kept. Execution checks that B' equals B (same status, equal values) on every registered admission input. A, B and B'
are then read afresh, interleaved in a seeded random order, in E6's task-alone arm with E6's four configurations and
frozen prompt, rulebook and scoring. This module reads E6's records and writes only under benchmarks/e13/records.

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/e13/e13.py construct|freeze|audit|analyse --split dev
"""
from __future__ import annotations

import ast
import base64
import difflib
import json
import pickle
import random
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "code" / "icml")]
import e1                                          # noqa: E402
import e6                                          # noqa: E402
from e1 import execute                             # noqa: E402

REC = HERE / "records"
EDITS, CHECKS = REC / "edits.jsonl", REC / "checks.jsonl"
MANIFEST = REC / "FREEZE13_test.json"
KINDS = ("open", "open2")
PROGS = ("a", "b", "c")                           # c = B'
MAX_EDITS = 2                                     # reached-model edits per unit: one, and one more if it fails
MARGIN = 10.0                                     # equivalence margin for E13-1, points
ORDER_SEED = "e13-order"

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

_orig = {n: getattr(e6, n) for n in ("set_kind", "units", "registered_units", "schedule")}


def conditionals(src: str) -> int:
    try:
        return sum(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(ast.parse(src)))
    except SyntaxError:
        return -1


def removed_lines(b: str, bp: str) -> int:
    """Lines of B (stripped, non-blank) that B' does not keep: the edit may only insert lines."""
    norm = lambda s: [l.strip() for l in s.splitlines() if l.strip()]
    return sum(1 for d in difflib.ndiff(norm(b), norm(bp)) if d.startswith("- "))


class kind_of:
    """Run a block with E6's original stages pointed at one kind, restoring the previous kind afterwards."""
    def __init__(self, kind):
        self.kind = kind

    def __enter__(self):
        self.prev = e6.KIND
        _orig["set_kind"](self.kind)

    def __exit__(self, *exc):
        e6.set_kind(self.prev)


def registered(split: str) -> dict:
    """(kind, pid) -> E6 unit with its probes and red-team inputs, for E6's registered population of each kind."""
    out = {}
    for kind in KINDS:
        with kind_of(kind):
            us = _orig["units"](split)
            probes = {r["problem_id"]: r for r in e1.load(e6.PROBES) if r.get("ok") and r.get("in_class_proposer")}
            red = {}
            for r in e1.load(e6.REDTEAM):
                if r.get("passed") is not None:
                    red.setdefault(r["problem_id"], []).append(r)
            for pid in _orig["registered_units"](split):
                out[(kind, pid)] = {**us[pid], "_probes": probes[pid], "_redteam": red.get(pid, [])}
    return out


def latest(path: Path) -> dict:
    rows = {}
    for r in e1.load(path):
        rows.setdefault((r["kind"], r["problem_id"]), []).append(r)
    return rows


def attempts(rows: list) -> list:
    return [r for r in rows if r.get("reached", True)]          # calls that never reached the model do not count


def stage_edit(split: str, workers: int) -> None:
    probs = {p.problem_id: p for p in e6.problems(split)}
    edits, checks = latest(EDITS), latest(CHECKS)
    jobs = []
    for key, u in registered(split).items():
        done = attempts(edits.get(key, []))
        if any(c.get("passed") for c in checks.get(key, [])) or len(done) >= MAX_EDITS:
            continue
        judged = {c["edit_sha256"] for c in checks.get(key, []) if c.get("passed") is not None}
        if any(e6.sha(e["code"] or "") not in judged for e in done):
            continue                                             # an edit not yet checked (identical edits share one)
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
                          "error": "" if ok else res.get("error", "parse"),
                          "reached": bool(ok or e1.reached_model(res))})
    e1.run_pool(jobs, one, workers, f"e13 edit {split}")


def admission_inputs(p, u: dict) -> tuple:
    """E6's admission inputs for the unit (v4.3: interface inputs only). Computed without touching E6's kind."""
    hidden = e1.hidden_inputs(p) or []
    lit = lambda xs: [x for x in (e6.literal_tuple(s) for s in xs) if x is not None]
    cls, oth, prb = lit(u["class_inputs"]), lit(u["other_inputs"]), lit(u["_probes"]["probes"])
    red = []
    for r in u["_redteam"]:                          # older red-team rows keep only the repr of their inputs
        red += pickle.loads(base64.b64decode(r["inputs_b64"])) if r.get("inputs_b64") else lit(r.get("inputs", []))
    allowed = e6.interface_types(hidden)
    stress = e6.stress_inputs(list(hidden) + cls + oth, seed=u["problem_id"])
    return hidden, [x for x in list(hidden) + cls + oth + prb + stress + red if e6.conforms(x, allowed)]


def stage_check(split: str, workers: int) -> None:
    probs = {p.problem_id: p for p in e6.problems(split)}
    us = registered(split)
    edits, checks = latest(EDITS), latest(CHECKS)
    jobs = []
    for key, rows in edits.items():
        if key not in us:
            continue
        judged = {c["edit_sha256"] for c in checks.get(key, []) if c.get("passed") is not None}
        for ed in attempts(rows):
            if e6.sha(ed["code"] or "") not in judged:
                hidden, inputs = admission_inputs(probs[key[1]], us[key])       # main thread: no shared state
                jobs.append((key, ed, hidden, inputs))

    def one(job):
        (kind, pid), ed, hidden, inputs = job
        p, u = probs[pid], us[(kind, pid)]
        row = {"kind": kind, "problem_id": pid, "split": split, "edit_sha256": e6.sha(ed["code"] or ""),
               "inputs_sha256": e6.sha(repr(inputs)), "n_inputs": len(inputs)}
        if not ed["ok"]:
            e1.append(CHECKS, {**row, "passed": False, "reason": "no edit"})
            return
        if not hidden:
            e1.append(CHECKS, {**row, "passed": False, "reason": "no hidden inputs"})
            return
        b, bp = u["program"]["b"], ed["code"]
        res = e6.multi_compare(p, {"b": b, "bp": bp}, [["b", "bp"]], inputs)
        if "infra" in res:                                       # infrastructure: retried, never consumes the edit
            e1.append(CHECKS, {**row, "passed": None, "reason": "infra", "infra": res["infra"]})
            return
        rs = res["rows"]
        differ = [i for i, r in enumerate(rs) if r["status"]["b"] != r["status"]["bp"]
                  or (r["status"]["b"] == "ok" and not r["agree"]["b~bp"])]
        visible = execute.run_suite(p.visible_program(bp), instrumented=p.visible_instrumented).passed
        added, removed = conditionals(bp) - conditionals(b), removed_lines(b, bp)
        reasons = [m for m, bad in (("differs from B", differ), ("visible tests", not visible),
                                    ("no branch", added < 1), ("changed lines of B", removed > 0)) if bad]
        e1.append(CHECKS, {**row, "passed": not reasons, "reason": "; ".join(reasons) or "ok",
                           "n_differ": len(differ), "visible": visible, "conditionals_added": added,
                           "lines_removed": removed, "hard": res.get("hard", False)})
    e1.run_pool(jobs, one, workers, f"e13 check {split}")


# ---------------------------------------------------------------------------------------------------------------
# audits of A, B and B' with E6's frozen stages (module globals are looked up at call time, as in E10 and E11)
# ---------------------------------------------------------------------------------------------------------------
def passed_edits(split: str) -> dict:
    """(kind, pid) -> the B' whose check passed (the first passing edit)."""
    edits, checks, out = latest(EDITS), latest(CHECKS), {}
    for key, cs in checks.items():
        ok = [c for c in cs if c.get("passed")]
        if ok and key[0] in KINDS and cs[0]["split"] == split:
            out[key] = next(e["code"] for e in edits[key] if e6.sha(e["code"] or "") == ok[0]["edit_sha256"])
    return out


def set_kind13(kind: str) -> None:
    _orig["set_kind"](kind)
    e6.AUD, e6.AUD_RAW = REC / f"{kind}_audits.jsonl", REC / f"{kind}_audits_raw.jsonl"
    e6.WIT = REC / f"{kind}_witnesses.jsonl"
    e6.ARMS = ("none",)


def units13(split: str, ungated: bool = False) -> dict:
    us, bp = _orig["units"](split, ungated), passed_edits(split)
    return {pid: {**u, "program": {**u["program"], "c": bp[(e6.KIND, pid)]}}
            for pid, u in us.items() if (e6.KIND, pid) in bp}


def registered13(split: str) -> list:
    bp = passed_edits(split)
    return [pid for pid in _orig["registered_units"](split) if (e6.KIND, pid) in bp]


def schedule13(split: str) -> list:
    keys = [(pid, prog, "none", cfg, k) for pid in e6.registered_units(split) for prog in PROGS
            for cfg in e6.CONFIGS for k in range(e6.READINGS)]
    random.Random(f"{ORDER_SEED}|{split}|{e6.KIND}").shuffle(keys)              # A, B and B' interleaved
    return keys


def install_audit() -> None:
    e1.REC = REC                  # the audit prompt's rulebook project is built under e1.REC: keep E6's untouched
    e6.set_kind, e6.units, e6.registered_units, e6.schedule = set_kind13, units13, registered13, schedule13
    sys.modules["freeze"] = types.SimpleNamespace(verify=verify)                # E6's test stages call it


def stage_audits(split: str, workers: int) -> None:
    install_audit()
    for kind in KINDS:
        e6.set_kind(kind)
        e6.stage_audit(split, workers)           # calls freeze.verify() on test, which restores the kind
        e6.set_kind(kind)
        e6.stage_witness(split, workers)
    e6.set_kind("open")


# ---------------------------------------------------------------------------------------------------------------
# freeze (PREREGISTRATION-E13.md, Integrity)
# ---------------------------------------------------------------------------------------------------------------
def _sha_file(f: Path) -> str:
    return e6.sha(f.read_text(errors="replace")) if f.exists() else "absent"


def _version(cmd: list) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def state(split: str) -> dict:
    prev = e6.KIND
    code, src = HERE.parent / "code", HERE.parents[1] / "src"
    files = [HERE / "e13.py", HERE / "PREREGISTRATION-E13.md", code / "icml" / "e6.py", code / "icml" / "e1.py",
             code / "icml" / "analyse_e6.py", code / "audit.py", code / "execute.py", code / "ceiling.py"]
    tree = {str(f.relative_to(src)): _sha_file(f) for pat in ("*.py", "*.md", "*.yml", "*.json")
            for f in sorted(src.rglob(pat)) if f.is_file() and "__pycache__" not in f.parts}
    pf = lambda py: subprocess.run([str(py), "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    e6_records = {f.name: _sha_file(f) for f in sorted(e6.REC.glob("*.jsonl"))
                  if f.name.startswith(("e6_", "e6b_")) and "audit" not in f.name and "witness" not in f.name}
    out = {"files": {str(f.relative_to(HERE.parents[1])): _sha_file(f) for f in files},
           "src": e6.sha(json.dumps(tree, sort_keys=True)), "venv": e6.sha(pf(sys.executable)),
           "executor": e6.sha(pf(execute.EXECUTOR)), "python": sys.version,
           "versions": {"executor": _version([str(execute.EXECUTOR), "--version"]),
                        "codex": _version(["codex", "--version"]), "claude": _version(["claude", "--version"])},
           "e6_construction_records": e6_records,
           "e13_construction": {"edits": _sha_file(EDITS), "checks": _sha_file(CHECKS)},
           "population": sorted(f"{k}|{p}" for k, p in registered(split)),
           "programs": {f"{k}|{p}": e6.sha(c) for (k, p), c in sorted(passed_edits(split).items())},
           "readings": {}}
    install_audit()
    cache: dict = {}
    probs = {p.problem_id: p for p in e6.problems(split)}
    for kind in KINDS:
        set_kind13(kind)
        us = units13(split)
        for key in schedule13(split):
            out["readings"][f"{kind}|" + "|".join(map(str, key))] = e6.expected_prompt_sha(us[key[0]], probs[key[0]],
                                                                                         key[1], key[2], cache)
    e6.set_kind(prev)
    return out


def heldout_audits_exist() -> bool:
    test = {p.problem_id for p in e6.problems("test")}
    return any(r["key"][0] in test for kind in KINDS for f in (f"{kind}_audits.jsonl", f"{kind}_audits_raw.jsonl")
               for r in e1.load(REC / f) if r.get("key"))


def construction_gaps(split: str) -> list:
    edits, checks, gaps = latest(EDITS), latest(CHECKS), []
    for key in registered(split):
        if any(c.get("passed") for c in checks.get(key, [])):
            continue
        done = attempts(edits.get(key, []))
        judged = {c["edit_sha256"] for c in checks.get(key, []) if c.get("passed") is not None}
        if len(done) < MAX_EDITS or any(e6.sha(e["code"] or "") not in judged for e in done):
            gaps.append(f"{key[0]}|{key[1]}")
    return gaps


def write_freeze() -> None:
    if heldout_audits_exist():
        raise SystemExit("held-out E13 audit records exist: the freeze cannot be rewritten")
    gaps = construction_gaps("test")
    if gaps:
        raise SystemExit(f"construction unfinished ({len(gaps)}): {gaps[:5]}")
    MANIFEST.write_text(json.dumps(state("test"), indent=1, sort_keys=True))
    print("E13 frozen:", MANIFEST)


def verify() -> None:
    if not MANIFEST.exists():
        raise SystemExit("no E13 freeze")
    if json.loads(MANIFEST.read_text()) != json.loads(json.dumps(state("test"), sort_keys=True)):
        raise SystemExit("E13 freeze verification failed")


# ---------------------------------------------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------------------------------------------
def shape_strata(split: str) -> dict:
    """The exploratory split that motivated E13: units whose A has more conditionals than B, and the rest."""
    more, rest = [], []
    for (kind, pid), u in registered(split).items():
        (more if conditionals(u["program"]["a"]) > conditionals(u["program"]["b"]) else rest).append(pid)
    return {"a_more_conditionals": more, "a_not_more": rest}


def analyse(split: str) -> dict:
    """E13-1: flag(B') - flag(B); E13-2: flag(A) - flag(B'); fresh, interleaved readings in the task-alone arm, E6's
    four configurations and cell policy. Every registered E6 unit is in the denominator; units without a checked B'
    or with an incomplete schedule enter the registered missing-data bounds."""
    import analyse_e6 as A
    if split == "test":
        verify()
    population = [p for (_, p) in registered(split)]
    strata = shape_strata(split)
    install_audit()
    cells, status = {}, {}
    for kind in KINDS:
        e6.set_kind(kind)
        status[kind] = e6.completeness(split)                    # every required reading valid, prompt hashes match
        c, _ = A.table(split)
        cells.update(c)
    e6.set_kind("open")
    C, t = e6.CONFIGS, 1

    def paired(prog):                                            # A with B ("b") or A with B' ("c"), as E6's a/b
        return {(pid, "b" if pr == prog else pr, arm, cfg): v for (pid, pr, arm, cfg), v in cells.items()
                if pr in ("a", prog)}
    with_b, with_c = paired("b"), paired("c")
    d1, d2, d0 = {}, {}, {}
    for pid in population:
        vb, vc = A.unit_value(with_b, pid, "none", C, t), A.unit_value(with_c, pid, "none", C, t)
        if vb is None or vc is None:
            continue
        d1[pid], d2[pid], d0[pid] = vc["flag_b"] - vb["flag_b"], vc["flag_a"] - vc["flag_b"], vb["flag_a"] - vb["flag_b"]
    est = lambda vals: A.with_bounds(A.boot(vals), vals, len(population) - len(vals), lo=-1.0, hi=1.0)
    res = {"split": split, "completeness": status, "n_population": len(population), "n_analysed": len(d1),
           "E13_1_flag_bprime_minus_b": est(d1), "E13_2_flag_pref_bprime": est(d2), "flag_pref_b_fresh": est(d0),
           "convention_advantage_b_fresh": A.convention(with_b, population, C, t),
           "convention_advantage_bprime": A.convention(with_c, population, C, t),
           "strata": {name: {"n": len([p for p in m if p in d1]), "E13_1": A.boot({p: d1[p] for p in m if p in d1}),
                             "E13_2": A.boot({p: d2[p] for p in m if p in d1})} for name, m in strata.items()}}
    m1, m2 = res["E13_1_flag_bprime_minus_b"], res["E13_2_flag_pref_bprime"]
    inside = lambda d, f: d.get(f) is not None and -MARGIN < d[f] < MARGIN
    if m1.get("lo") is not None and m1["lo"] > 0 and m1["bound_low"] > 0:
        v1 = "shape effect"
    elif all(inside(m1, f) for f in ("lo", "hi", "bound_low", "bound_high")):
        v1 = "no shape effect detected"
    else:
        v1 = "unresolved"
    res["verdicts"] = {"E13_1": v1, "E13_2": bool(m2.get("lo") is not None and m2["lo"] > 0 and m2["bound_low"] > 0)}
    res["per_unit"] = {p: {"d_flag_b": d1[p], "pref_bprime": d2[p], "pref_b": d0[p]} for p in d1}
    if split == "test":
        (REC / f"e13_results_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("edit", "check", "construct", "freeze", "audit", "analyse"))
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    REC.mkdir(exist_ok=True)
    if a.stage == "freeze":
        write_freeze()
    elif a.stage == "audit":
        stage_audits(a.split, a.workers)
    elif a.stage == "analyse":
        r = analyse(a.split)
        print(json.dumps({k: v for k, v in r.items() if k != "per_unit"}, indent=1, default=str))
    else:
        if a.split == "test" and heldout_audits_exist():
            raise SystemExit("held-out E13 audits exist: construction is closed")
        for s in (("edit", "check", "edit", "check") if a.stage == "construct" else (a.stage,)):
            print(f"== {s}", flush=True)
            (stage_edit if s == "edit" else stage_check)(a.split, a.workers)
        ok = len(passed_edits(a.split))
        print(f"E13 {a.split}: {ok}/{len(registered(a.split))} units with a checked B'; gaps {construction_gaps(a.split)}")
