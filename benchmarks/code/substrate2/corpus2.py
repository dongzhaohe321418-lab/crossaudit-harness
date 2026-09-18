"""Study 23 — BigCodeBench as a second substrate, in ceiling 1's Problem interface.

BigCodeBench ships one unittest class per task, so the visible/hidden split ceiling 1 needs
does not exist upstream and is made here, mechanically and by seed (§1 of the preregistration):
two test methods, chosen by ``random.Random(SPLIT_SEED)`` from the sorted method names, are the
**visible** suite; **all** methods are the hidden suite, so hidden ⊇ visible exactly as
EvalPlus's plus-suite contains its base suite.

Selection is by unittest's own test-name argument rather than by editing the test class: the
class is run unmodified and told which methods to execute, so a task's suite is never rewritten
by this harness.

The corpus itself is not committed. ``freeze_frame.py`` writes the frame — ids, hashes, the
split, and every drop with its reason — and that record is what the study binds to.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

SPLIT_SEED = 20260917
N_VISIBLE = 2
MIN_METHODS = 3
DATA = Path(__file__).resolve().parent.parent / "data" / "bigcodebench.jsonl"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_methods(test_code: str) -> list[str]:
    """The task's test method names, sorted. Empty if the suite does not parse."""
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
                _base_name(b).endswith("TestCase") for b in node.bases):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith("test"):
                    names.append(f"{node.name}.{child.name}")
    return sorted(names)


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def visible_methods(task_id: str, methods: list[str]) -> list[str]:
    """The seeded visible subset. A function of the task id and the method NAMES only.

    ``random.sample`` reads its population in order, so the names are sorted first: without
    that, the split would depend on the order the test class happened to be walked in, which
    a refactor of the parser could silently change.
    """
    rng = random.Random(f"{SPLIT_SEED}:{task_id}")
    return sorted(rng.sample(sorted(methods), N_VISIBLE))


@dataclass(frozen=True)
class Task:
    """ceiling 1's ``Problem`` interface over a BigCodeBench row."""

    problem_id: str
    benchmark: str
    entry_point: str
    spec: str
    canonical_solution: str
    _test: str
    _methods: tuple[str, ...]
    _visible: tuple[str, ...]

    @property
    def visible_instrumented(self) -> bool:
        return False               # unittest gives a whole-suite verdict, not a per-input vector

    def _program(self, solution: str, which: tuple[str, ...]) -> str:
        argv = ", ".join(repr(m) for m in which)
        return (f"{solution}\n\n{self._test}\n\n"
                f"import unittest\nunittest.main(argv=['x', {argv}], verbosity=0, exit=True)\n")

    def visible_program(self, solution: str) -> str:
        return self._program(solution, self._visible)

    def hidden_program(self, solution: str) -> tuple[str, bool]:
        return self._program(solution, self._methods), False

    def test_imports(self) -> list[str]:
        return []

    def visible_tests_text(self) -> str:
        """The visible suite as the developer sees it: a module that PARSES.

        The auditor and the generator are shown these and only these. Until
        Amendment 7 this sliced the selected methods' source out of the class and
        returned it verbatim, so the text began at an indented ``def`` and was not
        valid Python -- 300 of 300 tasks failed ``ast.parse``, while scoring
        executed the intact class. It now emits the module's own prologue, the
        class header, the class's non-test members (``setUp``, ``tearDown`` and any
        helper the selected methods call) and the selected test methods. No test
        method outside ``_visible`` appears, so the hidden suite is still hidden.
        """
        tree = ast.parse(self._test)
        lines = self._test.splitlines()
        wanted = {m.split(".", 1)[1] for m in self._visible}
        hidden = {m.split(".", 1)[1] for m in self._methods}

        def src(node) -> list[str]:
            first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            return lines[first - 1:node.end_lineno]

        target = next((n for n in tree.body
                       if isinstance(n, ast.ClassDef)
                       and any(isinstance(c, ast.FunctionDef) and c.name in wanted
                               for c in n.body)), None)
        if target is None:
            return ""

        out: list[str] = []
        for node in tree.body:                      # prologue: imports and module-level code,
            if not isinstance(node, ast.ClassDef):  # never another test class
                out.extend(src(node))
        if out:
            out.append("")

        # The class header is the `class` statement and its own decorators ONLY. Slicing to
        # the first member's line (Amendment 5) kept that member's decorators inside the
        # "header", so a hidden method's @patch stack was re-attached to whichever visible
        # method came first -- 26 tasks, verified. The displayed test then took extra mock
        # arguments and raised TypeError at run time while still parsing cleanly, so the
        # parse gate could not see it. End the header at the class statement's own last line.
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
            else:                                   # class-level constants the tests read
                out.extend(src(child))
        return "\n".join(out).rstrip() + "\n"


def load_rows() -> list[dict]:
    if not DATA.exists():
        raise SystemExit(f"{DATA} is missing; run benchmarks/code/substrate2/fetch2.py")
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def declared_libs(row: dict) -> list[str]:
    value = row.get("libs")
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except Exception:  # noqa: BLE001
            return []
    return list(value or [])


def task_from_row(row: dict) -> Task | None:
    methods = test_methods(row["test"])
    if len(methods) < MIN_METHODS:
        return None
    return Task(
        problem_id=row["task_id"], benchmark="bigcodebench", entry_point=row["entry_point"],
        spec=row["complete_prompt"],
        canonical_solution=row["complete_prompt"] + row["canonical_solution"],
        _test=row["test"], _methods=tuple(methods),
        _visible=tuple(visible_methods(row["task_id"], methods)))


def load_frame(frame_path: Path) -> list[Task]:
    """The frozen frame's tasks, in the order the frame records them."""
    frame = json.loads(frame_path.read_text(encoding="utf-8"))
    rows = {r["task_id"]: r for r in load_rows()}
    tasks = []
    for entry in frame["frame"]:
        row = rows[entry["task_id"]]
        assert sha(json.dumps(row, sort_keys=True)) == entry["row_sha256"], entry["task_id"]
        task = task_from_row(row)
        assert task is not None and list(task._visible) == entry["visible_methods"]
        tasks.append(task)
    return tasks
