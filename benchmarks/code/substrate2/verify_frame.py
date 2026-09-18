"""Amendment 2's registered gate: the corrected visible text must reproduce its digest.

    python benchmarks/code/substrate2/verify_frame.py

Exit 0 if every frame task's visible text parses and the digest over all 300 matches the value
frozen in `PREREGISTRATION.md` Amendment 2. Exit 1 otherwise, having spent nothing. The re-run's
generation and audit both call this first; a mismatch halts the run and is reported rather than
absorbed, because it would mean the models are about to be shown something other than what the
study says they are shown -- which is exactly how the original run was voided.
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from substrate2 import corpus2  # noqa: E402

FRAME = HERE.parent / "records" / "substrate2" / "frame.json"
#: Frozen by Amendment 2 on 2026-09-16, before the re-run's first model call.
#: Re-frozen by Amendment 6 on 2026-09-18, after the decorator leak was removed. The
#: Amendment 2 value 2c47fb41... froze the defective extraction faithfully, which is
#: exactly what a digest does and why a digest alone is not a correctness gate.
REGISTERED_DIGEST = "5c21539e7c3a4bcb03a92284ed06c0a52a609d75dad9bfe8d7c0257b2dcd89f2"


def semantic_check() -> list[str]:
    """Amendment 6: the displayed methods must be the SAME OBJECTS the scored suite runs.

    Parsing was not enough. Amendment 5's header slice re-attached a hidden method's
    decorators to the first visible method on 26 tasks; every one of those files parsed, no
    hidden test name appeared, and the displayed test still raised TypeError at run time
    because it had acquired mock arguments the scored one did not have. A gate that only
    asks "does it parse" cannot see a semantic divergence, so this one compares each shown
    method's AST against the same method in the intact class.
    """
    bad: list[str] = []
    for task in corpus2.load_frame(FRAME):
        try:
            shown = ast.parse(task.visible_tests_text())
        except SyntaxError:
            bad.append(f"{task.problem_id}: does not parse")
            continue
        intact = ast.parse(task._test)
        orig = {c.name: c for n in ast.walk(intact) if isinstance(n, ast.ClassDef)
                for c in n.body if isinstance(c, ast.FunctionDef)}
        for node in ast.walk(shown):
            if not isinstance(node, ast.ClassDef):
                continue
            for child in node.body:
                if not isinstance(child, ast.FunctionDef):
                    continue
                source = orig.get(child.name)
                if source is None:
                    bad.append(f"{task.problem_id}.{child.name}: not in the intact class")
                elif ast.dump(child) != ast.dump(source):
                    bad.append(f"{task.problem_id}.{child.name}: differs from the scored method")
    return bad


def digest_and_check() -> tuple[str, list[str]]:
    tasks = corpus2.load_frame(FRAME)
    unparsable: list[str] = []
    h = hashlib.sha256()
    for task in tasks:
        text = task.visible_tests_text()
        h.update(task.problem_id.encode("utf-8"))
        h.update(b"\0")
        h.update(text.encode("utf-8"))
        try:
            ast.parse(text)
        except SyntaxError:
            unparsable.append(task.problem_id)
    return h.hexdigest(), unparsable


def main() -> int:
    divergent = semantic_check()
    if divergent:
        print(f"HALT: {len(divergent)} displayed methods differ from the scored suite: "
              f"{divergent[:5]}")
        return 1
    got, unparsable = digest_and_check()
    if unparsable:
        print(f"HALT: {len(unparsable)} tasks' visible text does not parse: {unparsable[:5]}")
        return 1
    if got != REGISTERED_DIGEST:
        print(f"HALT: visible-text digest {got}\n      does not match the registered "
              f"{REGISTERED_DIGEST}")
        return 1
    print(f"visible text verified: 300 tasks parse, every displayed method is AST-identical "
          f"to the scored one, digest {got[:16]}... (Amendment 6 re-froze it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
