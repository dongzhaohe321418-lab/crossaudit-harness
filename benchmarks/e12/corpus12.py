"""E12 corpus: BigCodeBench tasks that no earlier study constructed or audited, in E7's Task interface.

Unused means: outside E7's deterministic pool (which E7 and E11 drew from) and outside the standard-library half of
BigCodeBench, which an earlier unreported substrate study audited (every task whose declared libraries are all
standard-library is excluded). Kept: mock-free tests with at least three test methods, at least one third-party
library, and no file, network, plotting, clock or subprocess code in the reference. Seeded randomness is allowed;
determinism is established by execution (E7's recorder keeps only inputs on which two runs agree)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "e7")]
import corpus7                                     # noqa: E402

DEV_SEED = "e12-dev-split"
DEV_SHARE = 0.25
STDLIB = set(sys.stdlib_module_names)
IO_SRC = ("plt.", "matplotlib", "open(", "os.", "requests", "urllib", "socket", "subprocess", "time.sleep", "sns.",
          "tempfile", "shutil", "glob", "sqlite", "datetime.now", "date.today", "smtplib", "ftplib", "psutil",
          "Path(", "cv2", "PIL", "wordcloud", "flask", "django", "time.time", "getpass", "input(")


def e7_pool(row: dict) -> bool:
    return corpus7.deterministic(row) and len(corpus7.test_methods(row["test"])) >= corpus7.MIN_METHODS


def eligible(row: dict) -> bool:
    libs = corpus7.declared_libs(row)
    return (not e7_pool(row) and bool(libs - STDLIB) and "mock" not in row["test"] and "patch(" not in row["test"]
            and not any(b in row["canonical_solution"] for b in IO_SRC)
            and len(corpus7.test_methods(row["test"])) >= corpus7.MIN_METHODS)


def split_of(task_id: str) -> str:
    h = int(hashlib.sha256(f"{DEV_SEED}|{task_id}".encode()).hexdigest(), 16) % 10_000
    return "dev" if h < DEV_SHARE * 10_000 else "test"


def load_tasks() -> list:
    rows = [json.loads(l) for l in corpus7.DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        if not eligible(r):
            continue
        methods = corpus7.test_methods(r["test"])
        out.append(corpus7.Task(r["task_id"], "bigcodebench", r["entry_point"], r["complete_prompt"],
                                r["complete_prompt"] + r["canonical_solution"], r["test"], tuple(methods),
                                tuple(corpus7.visible_methods(r["task_id"], methods))))
    return out


def install() -> None:
    """Point E7's corpus functions (used by its feasibility check and input recorder) at E12's corpus."""
    corpus7.load_tasks, corpus7.split_of = load_tasks, split_of


if __name__ == "__main__":
    ts = load_tasks()
    import collections
    print(len(ts), collections.Counter(split_of(t.problem_id) for t in ts))
