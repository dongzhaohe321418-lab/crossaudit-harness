"""E11: the randomised-contract experiment on BigCodeBench, with programs built as localised edits of the reference.

E7 (same corpus) stopped at construction: implementations written from scratch disagreed with the reference outside
the open class. E11 changes one stage. Each of E6's two implementing vendors edits the reference solution (docstring
removed) minimally, making the handling of the open class an explicit branch that follows the rule, and leaving every
other line unchanged; this is done for both rules. Everything else is E7's set-up (corpus, recorded hidden inputs,
comparator, constructor-expression arguments) and E6's frozen stages (validation, probes, class predicates, v4.3
admission, red team, judges, audits, witnesses). E11 starts from E7's frozen rule proposals and keeps its own records.

    python benchmarks/e11/e11.py <stage> --split dev|test [--kind open|det] [--workers N]
    stages: propose, implement (E11's edit stage), validate, probe, classpred, validate4, redteam, judge,
            construct (all of them; the first attempt starts from E7's frozen proposals, so it skips propose)
    kinds: open (first attempt), open2 (second, independent attempt on problems without a first-attempt primary unit,
           as in E6), det (positive controls)

Environment: as E7 (interpreter audit/.venv7, executor audit/.exec7, PYTHONPATH=crossaudit-harness/src).
"""
from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "e7")]
import e7  # noqa: E402   (sets the executor and import paths)
import e1  # noqa: E402
import e6  # noqa: E402

REC = HERE / "records"
E7REC = HERE.parent / "e7" / "records"

EDIT_PROMPT = """Below are a programming task and a working reference solution. Edit the solution minimally so that it
follows the additional requirement on the inputs the requirement concerns, and behaves exactly as before on every
other input. Make the handling of those inputs an explicit branch (for example an `if` statement guarding that case),
even if the solution already follows the requirement; leave every other line unchanged. Keep the solution's imports
and libraries. Write ordinary code: no comments about the requirement, the tests or these instructions.

TASK:
{spec}

REFERENCE SOLUTION:
{reference}

ADDITIONAL REQUIREMENT: {rule}

Reply with exactly one JSON object: {{"code": "<the complete edited solution, with its imports>"}}
"""

STAGES = ("validate", "probe", "classpred", "validate4", "redteam", "judge")


def strip_docstring(src: str, entry: str) -> str:
    """The reference without the entry function's docstring (the task text is shown separately)."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str) and len(node.body) > 1):
                lines = src.splitlines(keepends=True)
                return "".join(lines[:first.lineno - 1] + lines[first.end_lineno:])
    return src


def stage_implement(split: str, workers: int) -> None:
    if split == "test":
        verify_protocol()
    props = e6.proposals(split)
    probs = {p.problem_id: p for p in e6.problems(split)}
    have = {(r["problem_id"], r["contract"], r["route"]) for r in e1.load(e6.IMPLS)}   # one attempt each
    jobs = [(pid, c, rt) for pid in props if pid in probs for c in ("a", "b") for rt in e6.IMPL_ROUTES
            if (pid, c, rt) not in have]

    def one(job):
        pid, c, rt = job
        p, pr = probs[pid], props[pid]
        payload = EDIT_PROMPT.format(spec=p.spec.rstrip(), reference=strip_docstring(p.canonical_solution,
                                                                                      p.entry_point).rstrip(),
                                     rule=pr[f"rule_{c}"])
        res = e1.call(rt, payload)
        obj = e1.parse_json(res["text"]) if res["ok"] else None
        ok = isinstance(obj, dict) and isinstance(obj.get("code"), str) and p.entry_point in obj["code"]
        e1.append(e6.IMPLS, {"problem_id": pid, "contract": c, "route": rt, "ok": ok, "prompt_sha256": e6.sha(payload),
                             "code": obj["code"] if ok else None, "error": "" if ok else res.get("error", "parse"),
                             "reached": e1.reached_model(res)})
    e1.run_pool(jobs, one, workers, f"e11 implement {split}")


def install() -> None:
    e7.install()
    e6.REC = REC                                   # set_kind builds every record path from e6.REC
    e1.REC = REC                                   # audit_prompt builds its rulebook project under e1.REC: keep it out
                                                   # of E6's frozen records (review P13)
    REC.mkdir(exist_ok=True)
    for f in ("e6_proposals.jsonl", "e6det_proposals.jsonl"):     # E7's frozen proposals are E11's starting point
        if not (REC / f).exists() and (E7REC / f).exists():
            shutil.copy2(E7REC / f, REC / f)
    e6.stage_implement = stage_implement


# ---------------------------------------------------------------------------------------------------------------
# audits and analysis (PREREGISTRATION-E11.md): E10's arms on E11's units, E6's frozen stages and analysis
# ---------------------------------------------------------------------------------------------------------------
import hashlib  # noqa: E402
import json  # noqa: E402
import types  # noqa: E402

sys.path[:0] = [str(HERE.parent / "e10")]
from e10 import POINTER, UNCERTAIN, neutral_class  # noqa: E402   (E10's frozen pointer wording and class rule)
import re  # noqa: E402

DELIM = re.compile(r",\s|;\s|\s(?:where|that|which|and|or|but|so)\s")


def neutral_class11(cls: str) -> str:
    """E10's rule, then, if an uncertainty word survives (E10's rule only cuts introduced clauses), the text is cut at
    the last delimiter before that word. A rendered pointer that still contains one is refused at the freeze."""
    text = neutral_class(cls)
    m = UNCERTAIN.search(text)
    if m:
        cuts = [d.start() for d in DELIM.finditer(text) if d.start() < m.start()]
        text = text[:cuts[-1]].rstrip(" ,;") if cuts else ""
    return text

PROTOCOL = "e11-v1"
ARMS = ("none", "pointer", "sentence-a", "sentence-b")
GATE = 12                       # E7's registered go/no-go: held-out open units after both judges
_set_kind, _arm_text = e6.set_kind, e6.arm_text


def _sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def set_kind(kind: str) -> None:
    _set_kind(kind)
    if kind in ("open", "open2"):
        e6.AUD, e6.AUD_RAW = REC / f"{kind}_audits.jsonl", REC / f"{kind}_audits_raw.jsonl"
        e6.WIT = REC / f"{kind}_witnesses.jsonl"
        e6.ARMS = ARMS


def arm_text(u: dict, arm: str) -> str:
    return POINTER.format(cls=neutral_class11(u["class"])) if arm == "pointer" else _arm_text(u, arm)


def population(split: str) -> dict:
    out = {}
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        out[kind] = e6.registered_units(split)
    e6.set_kind("open")
    return out


def files_sha() -> dict:
    e7dir, icml, code = HERE.parent / "e7", HERE.parent / "code" / "icml", HERE.parent / "code"
    fs = [HERE / "e11.py", HERE / "PREREGISTRATION-E11.md", HERE.parent / "e10" / "e10.py",
          e7dir / "e7.py", e7dir / "corpus7.py", e7dir / "freeze7.py", e7dir / "hidden_inputs.json",
          e7dir / "data" / "bigcodebench.jsonl", icml / "e6.py", icml / "e1.py", icml / "analyse_e6.py",
          code / "audit.py", code / "execute.py", code / "ceiling.py"]
    return {str(f.relative_to(HERE.parent)): _sha(f.read_text()) for f in fs if f.exists()}


def environment() -> dict:
    """The product source the audit prompt, parser, validator, checks and rulebook come from, and both environments."""
    import subprocess
    from e1 import execute
    src = HERE.parents[1] / "src"
    tree = {str(f.relative_to(src)): _sha(f.read_text(errors="replace")) for pat in ("*.py", "*.md", "*.yml", "*.json")
            for f in sorted(src.rglob(pat)) if f.is_file() and "__pycache__" not in f.parts}
    pf = lambda py: subprocess.run([str(py), "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    return {"crossaudit_src": _sha(json.dumps(tree, sort_keys=True)), "python": sys.version,
            "venv_packages": _sha(pf(sys.executable)), "executor_packages": _sha(pf(execute.EXECUTOR)),
            "codex": subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip(),
            "claude": subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()}


def protocol_state() -> dict:
    """Phase 1, before any held-out construction: code, prompts, corpus and environment."""
    return {"protocol": PROTOCOL, "files": files_sha(), "environment": environment(),
            "prompts": {"edit": _sha(EDIT_PROMPT), "pointer": _sha(POINTER),
                        **{n: _sha(getattr(e6, n)) for n in ("PROPOSE_PROMPT", "PROBE_PROMPT", "CLASSPRED_PROMPT",
                                                            "REDTEAM_PROMPT", "JUDGE_PROMPT")}},
            "routes": {r: list(e1.ROUTES[r][1]) for r in sorted(set(e6.IMPL_ROUTES) | set(e6.JUDGE_ROUTES)
                                                            | set(e6.SENTENCE_CONFIGS) | {e6.PROPOSE_ROUTE})}}


def construction_complete(split: str) -> list:
    """Problems of each attempt whose construction is unfinished (registered: both attempts run to completion)."""
    gaps = []
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        props = e6.proposals(split)
        impls = {(r["problem_id"], r["contract"], r["route"]) for r in e1.load(e6.IMPLS)}
        pre = {r["problem_id"] for r in e1.load(e6.PREUNITS) if r.get("split") == split}
        gaps += [f"{kind}:{pid}:impl" for pid in props
                 if any((pid, c, rt) not in impls for c in "ab" for rt in e6.IMPL_ROUTES)]
        gaps += [f"{kind}:{pid}:validate" for pid in props if pid not in pre]
        adm4 = {r["problem_id"] for r in e1.load(e6.UNITS) if r.get("split") == split and r.get("admitted")}
        rt = {r["problem_id"] for r in e1.load(e6.REDTEAM) if r.get("passed") is not None}
        gaps += [f"{kind}:{pid}:redteam" for pid in adm4 if pid not in rt]
        judged = {(r["problem_id"], r["judge"]) for r in e1.load(e6.JUDGE) if r.get("ok")}
        gaps += [f"{kind}:{pid}:judge" for pid in e6.units(split) if any((pid, j) not in judged for j in e6.JUDGE_ROUTES)]
    e6.set_kind("open")
    return gaps


def state(split: str) -> dict:
    """Phase 2, after both construction attempts: the protocol state plus the population, the gate, every unit's
    programs, oracles, predicates and rendered arms, every required reading and its prompt hash."""
    prev = e6.KIND
    out = {"split": split, **protocol_state(), "arms": list(ARMS), "configs": list(e6.SENTENCE_CONFIGS),
           "units": {}, "readings": {}, "gate": gate(split),
           "construction_records": {f.name: _sha(f.read_text()) for f in sorted(REC.glob("*.jsonl"))
                                    if "audits" not in f.name and "witnesses" not in f.name and "e9" not in f.name}}
    cache: dict = {}
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        us, probs = e6.units(split), {p.problem_id: p for p in e6.problems(split)}
        for pid in e6.registered_units(split):
            out["units"][f"{kind}|{pid}"] = _sha(json.dumps([us[pid]["program"], us[pid]["oracle"], us[pid]["valid"],
                                                             us[pid]["in_class"], [arm_text(us[pid], a) for a in ARMS]]))
        for key in e6.schedule(split):
            out["readings"]["|".join(map(str, key))] = e6.expected_prompt_sha(us[key[0]], probs[key[0]], key[1],
                                                                              key[2], cache)
    e6.set_kind(prev)
    return out


def manifest(split: str) -> Path:
    return REC / f"FREEZE11_{split}.json"


PROTOCOL_MANIFEST = REC / "FREEZE11_protocol.json"


def same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def verify_protocol() -> None:
    if not PROTOCOL_MANIFEST.exists() or not same(json.loads(PROTOCOL_MANIFEST.read_text()), protocol_state()):
        raise SystemExit("E11 protocol freeze verification failed")


def verify() -> None:
    m = manifest("test")
    if not m.exists():
        raise SystemExit("no E11 population freeze for test")
    old = json.loads(m.read_text())
    if not old["gate"]["go"]:
        raise SystemExit("E11 gate was not met at the freeze: no audits")
    if not same(old, state("test")):
        raise SystemExit("E11 freeze verification failed")


def heldout_audits_exist() -> bool:
    """Any audit row, valid or raw, of either attempt, on a held-out problem."""
    test = {p.problem_id for p in e6.problems("test")}
    return any((r.get("key") or [None])[0] in test
               for k in ("open", "open2") for f in (REC / f"{k}_audits.jsonl", REC / f"{k}_audits_raw.jsonl")
               for r in e1.load(f))


def pointer_problems(split: str) -> list:
    bad = []
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        us = e6.units(split)
        for pid in e6.registered_units(split):
            text = arm_text(us[pid], "pointer")
            if UNCERTAIN.search(text) or len(neutral_class11(us[pid]["class"]).split()) < 2:
                bad.append(f"{kind}|{pid}: {text.strip()[:160]}")
    e6.set_kind("open")
    return bad


def install_audit() -> None:
    """E11's arms, records, protocol and freeze in E6's stages (module globals are looked up at call time)."""
    e6.set_kind, e6.arm_text = set_kind, arm_text
    e6.configs_for = lambda arm: e6.SENTENCE_CONFIGS
    e6.PROTOCOL = PROTOCOL
    sys.modules["freeze"] = types.SimpleNamespace(verify=verify)


def gate(split: str) -> dict:
    pop = population(split)
    n = sum(len(v) for v in pop.values())
    return {"n_units": n, "by_attempt": {k: len(v) for k, v in pop.items()}, "go": n >= GATE}


def run_audits(split: str, workers: int) -> None:
    if split == "test":
        g = gate(split)
        if not g["go"]:
            raise SystemExit(f"E11 gate not met: {g}")
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        if e6.registered_units(split):
            e6.stage_audit(split, workers)
            e6.stage_witness(split, workers)
    e6.set_kind("open")


def analyse(split: str) -> dict:
    import analyse_e6 as A
    if split == "test":
        verify()
    cells, units, status, beh = A.merged_open(split, allow_incomplete=False)
    S, t = e6.SENTENCE_CONFIGS, 1
    res = {"split": split, "protocol": PROTOCOL, "n_units": len(units), "units": units, "completeness": status}
    lv, uv = {}, {}
    for g in ("none", "pointer", "sentence"):
        lv[g], uv[g] = A.level(cells, units, g, S, t)
    res["levels"] = {g: {m: lv[g][m] for m in ("tpr", "fpr", "cov")} for g in lv}
    res["fpr_sentence_betting_upper95"] = lv["sentence"]["fpr_betting_upper95_worst_missing"]
    res["E11_1_sentence_minus_none"] = A.contrast(cells, units, "sentence", "none", S, S, "cov", t)
    res["E11_2_sentence_minus_pointer"] = A.contrast(cells, units, "sentence", "pointer", S, S, "cov", t)
    res["pointer_minus_none"] = A.contrast(cells, units, "pointer", "none", S, S, "cov", t)
    for name, f, lo, hi in (("flag_pref", lambda v: v["flag_a"] - v["flag_b"], -1.0, 1.0),
                            ("convention_advantage", lambda v: (v["r_b"] - v["r_a"]) / 2, -0.5, 0.5)):
        res[name] = {}
        for g in ("none", "pointer"):
            vals = {k: f(v) for k, v in uv[g].items()}
            res[name][g] = A.with_bounds(A.boot(vals), vals, len(units) - len(vals), lo=lo, hi=hi)
    res["per_config"] = {c: {"E11_1": A.contrast(cells, units, "sentence", "none", (c,), (c,), "cov", t),
                             "E11_2": A.contrast(cells, units, "sentence", "pointer", (c,), (c,), "cov", t)}
                         for c in S}

    def holds(d):
        if d.get("lo") is None or d.get("bound_low") is None:
            return "not estimable"
        return bool(d["lo"] > 0 and d["bound_low"] > 0)

    v1, v2 = holds(res["E11_1_sentence_minus_none"]), holds(res["E11_2_sentence_minus_pointer"])
    res["verdicts"] = {"E11_1": v1, "E11_2": v2, "E11_2_claimed": v1 is True and v2 is True}
    if split == "test":
        (REC / f"e11_results_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    import argparse
    install()
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("propose", "implement") + STAGES + ("construct", "protocol-freeze", "gate",
                                                                         "freeze", "audit", "analyse",
                                                                         "admissibility", "admissibility-analyse"))
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--kind", choices=["open", "open2", "det"], default="open")
    a = ap.parse_args()
    if a.stage == "protocol-freeze":
        test = {p.problem_id for p in e6.problems("test")}
        if any(r.get("problem_id") in test for f in ("e6_impls.jsonl", "e6b_impls.jsonl", "e6b_proposals.jsonl")
               for r in e1.load(REC / f)):
            raise SystemExit("held-out E11 construction has begun: the protocol freeze cannot be rewritten")
        PROTOCOL_MANIFEST.write_text(json.dumps(protocol_state(), indent=1, sort_keys=True))
        print("E11 protocol frozen:", PROTOCOL_MANIFEST)
        sys.exit(0)
    if a.stage in ("admissibility", "admissibility-analyse"):
        install_audit()                            # E9's judges and items on E11's units (descriptive, E11-3)
        sys.path[:0] = [str(HERE.parent / "e9")]
        import e9
        e9.REC = REC / "e9"
        e9.REC.mkdir(exist_ok=True)
        e9.verify = lambda split: verify() if split == "test" else None
        if a.stage == "admissibility":
            e9.run(a.split)
        else:
            print(json.dumps(e9.analyse(a.split, with_e6=(a.split == "test")), indent=1, default=str))
        sys.exit(0)
    if a.stage in ("gate", "freeze", "audit", "analyse"):
        install_audit()
        if a.stage == "gate":
            print(json.dumps(gate(a.split)))
        elif a.stage == "freeze":
            if a.split == "test":
                if heldout_audits_exist():
                    raise SystemExit("held-out E11 audit records exist: the freeze cannot be rewritten")
                verify_protocol()
            gaps = construction_complete(a.split)
            if gaps:
                raise SystemExit(f"construction unfinished ({len(gaps)}): {gaps[:10]}")
            bad = pointer_problems(a.split)
            if bad:
                raise SystemExit("pointer text not neutral:\n" + "\n".join(bad))
            manifest(a.split).write_text(json.dumps(state(a.split), indent=1, sort_keys=True))
            print("E11 frozen:", manifest(a.split), json.dumps(gate(a.split)))
        elif a.stage == "audit":
            run_audits(a.split, a.workers)
        else:
            print(json.dumps(analyse(a.split), indent=1, default=str))
        sys.exit(0)
    e6.set_kind(a.kind)
    first = ("propose",) if a.kind == "open2" else ()
    for stage in (first + ("implement",) + STAGES if a.stage == "construct" else (a.stage,)):
        print(f"== {stage}", flush=True)
        getattr(e6, "stage_" + stage)(a.split, a.workers)
