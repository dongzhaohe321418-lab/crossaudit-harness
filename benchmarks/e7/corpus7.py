"""E7 corpus: deterministic BigCodeBench tasks in E6's Problem interface.

The Task class (visible/hidden split by seeded test-method names, a visible suite that parses) is study 23's
(benchmarks/code/substrate2/corpus2.py, branch study/substrate2), copied here so that E7 does not touch the frozen
E1/E6 code. Added for E6: hidden inputs (literal-evaluable or import-evaluable arguments of the entry point's calls
in the test methods), a comparator for pandas/numpy values, and the deterministic-task filter.
"""
from __future__ import annotations

import ast
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "bigcodebench.jsonl"
SPLIT_SEED = 20260917            # study 23's visible-method seed
DEV_SEED = "e7-dev-split"
N_VISIBLE, MIN_METHODS = 2, 3
OK_LIBS = {"numpy", "pandas", "scipy", "math", "collections", "itertools", "re", "string", "json", "datetime",
           "statistics", "functools", "operator", "heapq", "bisect", "decimal", "fractions", "textwrap",
           "unicodedata", "copy", "sklearn"}
BAD_SRC = ("random", "plt.", "matplotlib", "open(", "os.", "requests", "urllib", "socket", "subprocess",
           "time.sleep", "np.random", "uuid", "sns.", "tempfile", "shutil", "glob", "sqlite", "Faker",
           "datetime.now", "date.today")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _base_name(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""


def test_methods(test_code: str) -> list[str]:
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(_base_name(b).endswith("TestCase") for b in node.bases):
            names += [f"{node.name}.{c.name}" for c in node.body
                      if isinstance(c, ast.FunctionDef) and c.name.startswith("test")]
    return sorted(names)


def visible_methods(task_id: str, methods: list[str]) -> list[str]:
    rng = random.Random(f"{SPLIT_SEED}:{task_id}")
    return sorted(rng.sample(sorted(methods), N_VISIBLE))


@dataclass(frozen=True)
class Task:
    problem_id: str
    benchmark: str
    entry_point: str
    spec: str
    canonical_solution: str
    _test: str
    _methods: tuple
    _visible: tuple

    @property
    def visible_instrumented(self) -> bool:
        return False

    def _program(self, solution: str, which: tuple) -> str:
        argv = ", ".join(repr(m) for m in which)
        return (f"{solution}\n\n{self._test}\n\n"
                f"import unittest\nunittest.main(argv=['x', {argv}], verbosity=0, exit=True)\n")

    def visible_program(self, solution: str) -> str:
        return self._program(solution, self._visible)

    def hidden_program(self, solution: str) -> tuple:
        return self._program(solution, self._methods), False

    def prologue(self) -> str:
        """Module-level statements of the test file (imports, constants), never a test class."""
        tree = ast.parse(self._test)
        lines = self._test.splitlines()
        return "\n".join("\n".join(lines[n.lineno - 1:n.end_lineno]) for n in tree.body
                         if not isinstance(n, ast.ClassDef))

    def call_args(self) -> list[str]:
        """Source of the argument tuples of every call to the entry point in the test methods that does not use
        `self` or keyword-only machinery the harness cannot rebuild (positional and keyword args kept as source)."""
        out = []
        for node in ast.walk(ast.parse(self._test)):
            if isinstance(node, ast.Call) and _base_name(node.func) == self.entry_point:
                if any(isinstance(n, ast.Name) and n.id == "self" for a in node.args + [k.value for k in node.keywords]
                       for n in ast.walk(a)) or node.keywords:
                    continue
                out.append("(" + "".join(ast.unparse(a) + ", " for a in node.args) + ")")
        return out

    def visible_tests_text(self) -> str:
        tree = ast.parse(self._test)
        lines = self._test.splitlines()
        wanted = {m.split(".", 1)[1] for m in self._visible}
        hidden = {m.split(".", 1)[1] for m in self._methods}

        def src(node) -> list:
            first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            return lines[first - 1:node.end_lineno]

        target = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                       and any(isinstance(c, ast.FunctionDef) and c.name in wanted for c in n.body)), None)
        if target is None:
            return ""
        out = []
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                out.extend(src(node))
        if out:
            out.append("")
        head = min([target.lineno] + [d.lineno for d in target.decorator_list]) - 1
        header_end = target.body[0].lineno - 1
        for child in target.body:
            first = min([child.lineno] + [d.lineno for d in getattr(child, "decorator_list", [])])
            header_end = min(header_end, first - 1)
        out.extend(lines[head:header_end])
        for child in target.body:
            if isinstance(child, ast.FunctionDef):
                if child.name in wanted or child.name not in hidden:
                    out.extend(src(child))
                    out.append("")
            else:
                out.extend(src(child))
        return "\n".join(out).rstrip() + "\n"


def declared_libs(row: dict) -> set:
    v = row.get("libs")
    if isinstance(v, str):
        try:
            v = ast.literal_eval(v)
        except Exception:  # noqa: BLE001
            return set()
    return set(v or [])


def deterministic(row: dict) -> bool:
    return (declared_libs(row) <= OK_LIBS and "mock" not in row["test"] and "patch(" not in row["test"]
            and not any(b in row["canonical_solution"] for b in BAD_SRC))


def load_tasks() -> list:
    rows = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    tasks = []
    for r in rows:
        methods = test_methods(r["test"])
        if not deterministic(r) or len(methods) < MIN_METHODS:
            continue
        tasks.append(Task(r["task_id"], "bigcodebench", r["entry_point"], r["complete_prompt"],
                          r["complete_prompt"] + r["canonical_solution"], r["test"], tuple(methods),
                          tuple(visible_methods(r["task_id"], methods))))
    return tasks


def split_of(task_id: str) -> str:
    """About a quarter of the tasks for development, by a seeded hash of the id."""
    return "dev" if int(sha(f"{DEV_SEED}:{task_id}"), 16) % 4 == 0 else "test"


COMPARATOR = r'''
import math
def assertion(a, b, atol):
    """Equality for pandas/numpy/builtin results with a relative tolerance on floats."""
    import numpy as np
    try:
        import pandas as pd
    except Exception:
        pd = None
    if pd is not None and isinstance(a, (pd.DataFrame, pd.Series, pd.Index)):
        assert type(a) is type(b)
        if isinstance(a, pd.DataFrame):
            pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=False, rtol=1e-6, atol=atol)
        elif isinstance(a, pd.Series):
            pd.testing.assert_series_equal(a, b, check_dtype=False, check_exact=False, rtol=1e-6, atol=atol)
        else:
            pd.testing.assert_index_equal(a, b, exact=False)
        return
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a2, b2 = np.asarray(a), np.asarray(b)
        assert a2.shape == b2.shape
        if a2.dtype.kind in "fc" or b2.dtype.kind in "fc":
            assert np.allclose(a2, b2, rtol=1e-6, atol=atol, equal_nan=True)
        else:
            assert (a2 == b2).all()
        return
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, (int, float)) and isinstance(b, (int, float))
        assert (math.isnan(a) and math.isnan(b)) or math.isclose(a, b, rel_tol=1e-6, abs_tol=atol)
        return
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        assert type(a) is type(b) and len(a) == len(b)
        for x, y in zip(a, b):
            assertion(x, y, atol)
        return
    if isinstance(a, dict) and isinstance(b, dict):
        assert a.keys() == b.keys()
        for k in a:
            assertion(a[k], b[k], atol)
        return
    assert a == b
'''
