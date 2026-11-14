"""E11: the randomised-contract experiment on BigCodeBench, with programs built as localised edits of the reference.

E7 (same corpus) stopped at construction: implementations written from scratch disagreed with the reference outside
the open class. E11 changes one stage. Each of E6's two implementing vendors edits the reference solution (docstring
removed) minimally, making the handling of the open class an explicit branch that follows the rule, and leaving every
other line unchanged; this is done for both rules. Everything else is E7's set-up (corpus, recorded hidden inputs,
comparator, constructor-expression arguments) and E6's frozen stages (validation, probes, class predicates, v4.3
admission, red team, judges, audits, witnesses). E11 starts from E7's frozen rule proposals and keeps its own records.

    python benchmarks/e11/e11.py <stage> --split dev|test [--kind open|det] [--workers N]
    stages: implement (E11's edit stage), validate, probe, classpred, validate4, redteam, judge, construct (all of them)

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
    REC.mkdir(exist_ok=True)
    for f in ("e6_proposals.jsonl", "e6det_proposals.jsonl"):     # E7's frozen proposals are E11's starting point
        if not (REC / f).exists() and (E7REC / f).exists():
            shutil.copy2(E7REC / f, REC / f)
    e6.stage_implement = stage_implement


if __name__ == "__main__":
    import argparse
    install()
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("implement",) + STAGES + ("construct",))
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--kind", choices=["open", "det"], default="open")
    a = ap.parse_args()
    e6.set_kind(a.kind)
    for stage in (("implement",) + STAGES if a.stage == "construct" else (a.stage,)):
        print(f"== {stage}", flush=True)
        getattr(e6, "stage_" + stage)(a.split, a.workers)
