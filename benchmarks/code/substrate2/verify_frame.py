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
REGISTERED_DIGEST = "2c47fb410167fc6e2054d6fad0b62e42e0716d62c5225807a16344b895bba128"


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
    got, unparsable = digest_and_check()
    if unparsable:
        print(f"HALT: {len(unparsable)} tasks' visible text does not parse: {unparsable[:5]}")
        return 1
    if got != REGISTERED_DIGEST:
        print(f"HALT: visible-text digest {got}\n      does not match the registered "
              f"{REGISTERED_DIGEST}")
        return 1
    print(f"visible text verified: 300 tasks parse, digest {got[:16]}... matches Amendment 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
