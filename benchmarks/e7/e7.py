"""E7: the randomised-contract experiment (E6, protocol e6-v4.3) on deterministic BigCodeBench tasks.

E6's stages run unchanged; this module points them at the BigCodeBench corpus and its own record directory, and
supplies what BigCodeBench lacks: recorded hidden inputs, a pandas/numpy comparator, and arguments written as
pandas/numpy constructor expressions (checked against a whitelist, then evaluated in the executor, never in this
process). The frozen E1/E6 code is not modified.

    python benchmarks/e7/e7.py <stage> --split dev|test --kind open|det --workers N

Environment: harness interpreter audit/.venv7 (pandas installed, so recorded inputs unpickle), executor
audit/.exec7, PYTHONPATH=crossaudit-harness/src.
"""
from __future__ import annotations

import ast
import base64
import json
import os
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parents[2]
os.environ.setdefault("CROSSAUDIT_BENCH_EXECUTOR", str(AUDIT / ".exec7" / "bin" / "python"))
sys.path[:0] = [str(HERE), str(HERE.parent / "code"), str(HERE.parent / "code" / "icml")]

import corpus7  # noqa: E402
import e1  # noqa: E402
import e6  # noqa: E402
from e1 import execute  # noqa: E402

REC7 = HERE / "records"
REC7.mkdir(exist_ok=True)
HIDDEN = {r["task_id"]: r["hidden_inputs_b64"] for r in json.loads((HERE / "hidden_inputs.json").read_text())}
TASKS = {t.problem_id: t for t in corpus7.load_tasks() if len(HIDDEN.get(t.problem_id, [])) >= 3}

# ---------------------------------------------------------------------------------------------
# arguments as constructor expressions: whitelist, then evaluation in the executor
# ---------------------------------------------------------------------------------------------
ROOTS = {"pd", "np", "pandas", "numpy", "datetime", "nan", "inf", "math"}
NODES = (ast.Expression, ast.Tuple, ast.List, ast.Dict, ast.Set, ast.Constant, ast.UnaryOp, ast.USub, ast.UAdd,
         ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Name, ast.Attribute, ast.Call, ast.keyword, ast.Load)
PRELUDE = "import pandas as pd, numpy as np, pandas, numpy, datetime, math\nfrom math import nan, inf\n"
_cache: dict = {}
_original_literal = e1.literal


def allowed(src: str) -> bool:
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return False
    for n in ast.walk(tree):
        if not isinstance(n, NODES):
            return False
        if isinstance(n, ast.Name) and n.id not in ROOTS:
            return False
        if isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            return False
        if isinstance(n, ast.Call):            # only calls of pd./np./datetime. names, e.g. pd.DataFrame(...)
            f = n.func
            while isinstance(f, ast.Attribute):
                f = f.value
            if not (isinstance(f, ast.Name) and f.id in ROOTS):
                return False
    return True


def materialise(src: str):
    """Evaluate a whitelisted expression in the executor (time and memory capped) and return the object."""
    if src in _cache:
        return _cache[src]
    prog = (PRELUDE + "import sys, pickle, base64\n"
            f"v = eval({src!r})\nsys.stdout.write(base64.b64encode(pickle.dumps(v)).decode())\n")
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "m.py").write_text(prog)
        done, why = e6.run_watched([execute.EXECUTOR, str(Path(tmp, "m.py"))], tmp, timeout=30, mem_mb=1024)
    if why or done is None or done.returncode != 0:
        raise ValueError(f"unevaluable: {why or (done.stderr or '')[-200:]}")
    _cache[src] = pickle.loads(base64.b64decode(done.stdout))
    return _cache[src]


def literal7(src):
    """e1.literal, extended: an expression that is not a literal is accepted if it passes the whitelist."""
    try:
        return _original_literal(src)
    except (ValueError, SyntaxError, TypeError):
        text = src if isinstance(src, str) else ast.unparse(src)
        if not allowed(text):
            raise ValueError("not a literal and not a whitelisted constructor expression")
        return materialise(text)


# ---------------------------------------------------------------------------------------------
# the corpus in E6's interface
# ---------------------------------------------------------------------------------------------
def problems(split: str) -> list:
    return [t for t in TASKS.values() if corpus7.split_of(t.problem_id) == split]


def hidden_inputs(p):
    return [pickle.loads(base64.b64decode(x)) for x in HIDDEN.get(p.problem_id, [])] or None


def suite_assertion(p) -> tuple:
    return corpus7.COMPARATOR, "1e-9"


def imports_of(p) -> str:
    return ""


WORDING = (("each a Python literal tuple of the", "each a Python tuple expression (literals, or pandas `pd.` / numpy "
            "`np.` constructor calls where the task's arguments need them) of the"),
           ("each a Python literal tuple of positional arguments", "each a Python tuple expression of positional "
            "arguments (literals, or pandas `pd.` / numpy `np.` constructor calls where needed)"),
           ("each call a Python literal\ntuple of positional arguments", "each call a Python tuple expression of "
            "positional arguments (literals, or pandas `pd.` / numpy `np.` constructor calls where needed)"))
WITNESS_RULE7 = e1.WITNESS_RULE.replace(
    "written as a Python call with literal arguments", "written as a Python call whose arguments are literals or "
    "pandas (pd) / numpy (np) constructor expressions").replace(
    "written as a Python literal.", "written as a Python literal or such an expression.")


def install() -> None:
    """Point E6 and E1 at the BigCodeBench corpus and E7's records."""
    e1.literal = literal7
    e1.hidden_inputs, e1.suite_assertion, e1.imports_of = hidden_inputs, suite_assertion, imports_of
    e1.WITNESS_RULE = WITNESS_RULE7
    e6.problems, e6.suite_assertion, e6.imports_of = problems, suite_assertion, imports_of
    for name in ("PROPOSE_PROMPT", "PROPOSE_DET_PROMPT", "PROBE_PROMPT", "REDTEAM_PROMPT"):
        text = getattr(e6, name)
        for old, new in WORDING:
            text = text.replace(old, new)
        setattr(e6, name, text)
    e6.REC = REC7
    sys.modules["freeze"] = __import__("freeze7")     # E7's own pre-test freeze


if __name__ == "__main__":
    import argparse
    install()
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["propose", "implement", "validate", "probe", "classpred", "validate4", "redteam",
                                      "judge", "audit", "witness"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--kind", choices=["open", "det"], default="open")
    a = ap.parse_args()
    e6.set_kind(a.kind)
    getattr(e6, "stage_" + a.stage)(a.split, a.workers)
