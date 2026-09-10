"""Build the blind adjudication sheet for H19d from the archived draw-1 findings.

    python benchmarks/code/ceiling3b/adjudication_sheet.py --run <archive dir> --out <archive dir>/sheet

Sheet items: every finding (any severity) on a stratum-P instance in draw 1 of arms R, B and
the S-text reading. Each item shows an opaque id, the specification, the candidate
solution, the hidden failure (the first failing hidden inputs with expected and actual
values — the thing the finding is judged against) and the finding text — no arm, no
severity. The question per item: does the finding name the input class, or the behaviour,
on which the hidden test fails? yes / no / cannot tell. The key
(id -> instance, arm, severity, rule) is written beside the sheet and committed later;
the sheet itself stays in the archive (it quotes model output and the benchmark's
specifications). Order is shuffled with seed 20260912.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import execute  # noqa: E402
import explore  # noqa: E402
import residual_dump  # noqa: E402
from corpus import load_problems  # noqa: E402

SEED = 20260912
ARMS = {"self-strong-R": "R", "self-strong-B": "B", "self-strong-S": "S"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    instances = explore.load_instances()
    problems = {p.problem_id: p for p in load_problems()}
    solutions = {}
    for batch in ("b1", "b2"):
        for line in (args.run / f"study2-inputs/solutions-{batch}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row["solution"]
    items = []
    for route, arm in ARMS.items():
        path = args.run / f"findings-{route}-d1.jsonl"
        if not path.exists():
            print(f"missing {path.name}; the sheet is incomplete without it")
            continue
        seen = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            iid = rec["instance_id"]
            if iid in seen or instances[iid]["stratum"] != "P":
                continue
            seen.add(iid)
            for k, f in enumerate(rec["findings"]):
                items.append({"instance": iid, "arm": arm, "k": k, "severity": f.get("severity"),
                              "rule": f.get("rule"), "text": f.get("observation", "")})
    # The hidden failure each finding is judged against (H19d): the first failing hidden
    # inputs with expected and actual values, recovered model-free by re-running the
    # hidden suite in execute.py's sandbox (residual_dump.witness_for). Cached per instance.
    witnesses: dict[str, dict] = {}
    for it in items:
        iid = it["instance"]
        if iid in witnesses:
            continue
        problem = problems[instances[iid]["problem_id"]]
        program, instrumented = problem.hidden_program(solutions[iid])
        hidden = execute.run_suite(program, instrumented=instrumented).as_dict()
        witnesses[iid] = residual_dump.witness_for(problem, solutions[iid], hidden)
    rng = random.Random(SEED)
    rng.shuffle(items)
    sheet, key = [], []
    for n, it in enumerate(items, 1):
        sid = f"J{n:04d}"
        p = problems[instances[it["instance"]]["problem_id"]]
        sheet.append({"id": sid, "specification": p.spec, "solution": solutions[it["instance"]],
                      "hidden_failure": witnesses[it["instance"]], "finding": it["text"]})
        key.append({"id": sid, "instance": it["instance"], "arm": it["arm"], "k": it["k"],
                    "severity": it["severity"], "rule": it["rule"]})
    (args.out / "sheet-h19d.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sheet), encoding="utf-8")
    (HERE / "key-h19d.jsonl").write_text("".join(json.dumps(x) + "\n" for x in key), encoding="utf-8")
    print(f"sheet items {len(sheet)} (P instances with a finding, by arm: "
          + ", ".join(f"{a} {sum(1 for x in key if x['arm'] == a)}" for a in ("S", "R", "B")) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
