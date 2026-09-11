"""Amendment 1: build the blind adjudication sheet for `cross-T` d1 and `cross-R` d1. No model call.

    python benchmarks/code/ceiling4/adjudication_sheet.py \
        --run ~/Documents/Crossaudit/study-data/wt-ceiling4-runs \
        --out ~/Documents/Crossaudit/study-data/wt-ceiling4-adjudication

Study 19's ``ceiling3b/adjudication_sheet.py``, re-pointed at this study's two archived
draws. Sheet items: every finding (any severity) on a stratum-P instance in draw 1 of
`cross-T` (the shipped constitution, Amendment 1's subject) and of `cross-R` (adjudicated
beside it whether or not H20a is positive, Amendment 1). Each item shows an opaque id, the
specification, the candidate solution, the hidden failure (the first failing hidden inputs
with expected and actual values, recovered model-free by re-running the hidden suite in
``execute.py``'s subprocess sandbox) and the finding text — no arm, no severity, no
stratum. The question per item is study 19's: does the finding name the input class, or the
behaviour, on which the hidden test fails? yes / no / cannot tell.

**This script prepares the inputs and stops.** It runs no adjudicator, asks no model and
touches no network; L1 and L2 are not invoked here.

The sheet quotes model output and the benchmark's specifications and solutions, so it is
written to ``--out``, which must be outside the repository (the script refuses otherwise).
Only the key — id to instance, arm, finding index, severity, rule — is written into the
repository, and the manifest of counts and digests beside it. Order is shuffled with seed
20260913, the preregistration's seed.
"""
from __future__ import annotations

import argparse
import hashlib
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

REPO = HERE.parent.parent.parent
SEED = 20260913
ARMS = {"cross-T": "T", "cross-R": "R"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, type=Path, help="the read-only run archive")
    ap.add_argument("--out", required=True, type=Path, help="where the sheet goes; must be outside the repo")
    args = ap.parse_args(argv)
    run, out = args.run.expanduser().resolve(), args.out.expanduser().resolve()
    if REPO in out.parents or out == REPO:
        raise SystemExit(f"--out {out} is inside the repository; the sheet carries finding and "
                         f"specification text and is never committed")
    out.mkdir(parents=True, exist_ok=True)

    instances = explore.load_instances()
    problems = {p.problem_id: p for p in load_problems()}
    solutions: dict[str, str] = {}
    for batch in ("b1", "b2"):
        for line in (run / f"study2-inputs/solutions-{batch}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row["solution"]

    items: list[dict] = []
    for route, arm in ARMS.items():
        path = run / f"findings-{route}-d1.jsonl"
        if not path.exists():
            print(f"missing {path.name}; the sheet is incomplete without it")
            continue
        seen: set[str] = set()
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
        sid = f"K{n:04d}"
        p = problems[instances[it["instance"]]["problem_id"]]
        sheet.append({"id": sid, "specification": p.spec, "solution": solutions[it["instance"]],
                      "hidden_failure": witnesses[it["instance"]], "finding": it["text"]})
        key.append({"id": sid, "instance": it["instance"], "arm": it["arm"], "k": it["k"],
                    "severity": it["severity"], "rule": it["rule"]})
    sheet_path = out / "sheet-amendment1.jsonl"
    sheet_path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sheet), encoding="utf-8")
    key_path = HERE / "key-amendment1.jsonl"
    key_path.write_text("".join(json.dumps(x) + "\n" for x in key), encoding="utf-8")

    by_arm = {a: sum(1 for x in key if x["arm"] == a) for a in ARMS.values()}
    instances_by_arm = {a: len({x["instance"] for x in key if x["arm"] == a}) for a in ARMS.values()}
    witness_kinds: dict[str, int] = {}
    for w in witnesses.values():
        witness_kinds[w.get("kind", "vector")] = witness_kinds.get(w.get("kind", "vector"), 0) + 1
    manifest = {
        "prepared": "Amendment 1's adjudication inputs; PREPARED ONLY — no adjudicator was run, "
                    "no model was called, no network was used",
        "questions": "study 19's: (L1 naming) does the finding name the input class, or the "
                     "behaviour, on which the hidden test fails? then the recognition question; "
                     "L1 the author, L2 a different vendor's model, both blind to metadata",
        "sheet_path_outside_repo": str(sheet_path),
        "sheet_sha256": sha256_file(sheet_path),
        "key_path_in_repo": str(key_path.relative_to(REPO)),
        "key_sha256": sha256_file(key_path),
        "shuffle_seed": SEED,
        "items": len(sheet), "items_by_arm": by_arm,
        "P_instances_with_a_finding_by_arm": instances_by_arm,
        "hidden_failure_witness_kinds": dict(sorted(witness_kinds.items())),
        "note": "the sheet carries specification, solution and finding text and is never committed; "
                "the key carries ids, severities and rule codes only"}
    (out / "manifest-amendment1.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                                  encoding="utf-8")
    (HERE / "adjudication-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                                     encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
