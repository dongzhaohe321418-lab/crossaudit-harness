"""Study 8 — assemble the reading material for the residual classification (§1.5).

The residual is every stratum-P instance that **no draw of any family ever flagged**.
Classifying it is the one hand step in this study, and the categories were fixed in the
preregistration before the first residual instance was read.

This script only assembles evidence; it decides nothing. For each residual instance it
writes the specification, the visible suite, the candidate solution, the dataset's own
canonical solution, and which hidden inputs failed and with what values — and, so the
classification is checkable rather than merely asserted, it re-runs the failing hidden
inputs through ``execute.py``'s sandbox to recover the expected and actual values.

Output goes to the run directory, not the repository: it contains corpus text and full
candidate solutions. The **classification** that comes out of reading it — instance id,
category, one phrase — is what gets committed, in
``records/ceiling/residual_classification.json``.

    python benchmarks/code/residual_dump.py --run <run-dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import execute  # noqa: E402
import report_ceiling as rc  # noqa: E402
from corpus import load_problems  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--population", default="three_families_all_P")
    # P3 Amendment 1 found the rating sheet's control arm unanswerable: `failing_input_class`
    # lives in the residual classification, which by construction covers only the residual, so
    # 42 of 53 caught instances carried none and every one of them was rated `cannot-tell`.
    # The witness this script recovers is mechanical and exists for ANY stratum-P instance, so
    # the same evidence can be dumped for the caught arm and the two made comparable.
    parser.add_argument("--ids-file", default="",
                        help="dump these instance ids instead of a named residual population")
    parser.add_argument("--out", default="residual", help="subdirectory of --run to write into")
    args = parser.parse_args(argv)

    numbers_path = rc.CEILING / "numbers.json"
    if not numbers_path.exists():
        raise SystemExit("run report_ceiling.py first")
    numbers = json.loads(numbers_path.read_text(encoding="utf-8"))
    if args.ids_file:
        ids = [x.strip() for x in Path(args.ids_file).read_text(encoding="utf-8").splitlines()
               if x.strip()]
        print(f"{len(ids)} instances from {args.ids_file}")
    else:
        residual = numbers["ceiling1"]["residual"].get(args.population)
        if not residual:
            raise SystemExit(f"no residual population named {args.population!r}")
        ids = residual["instance_ids"]
        print(f"{len(ids)} residual instances "
              f"({', '.join(residual['families'])}, {residual['total_draws']} draws)")

    run_dir = Path(args.run)
    problems = {p.problem_id: p for p in load_problems()}
    solutions: dict[str, dict] = {}
    scored: dict[str, dict] = {}
    for batch in ("b1", "b2"):
        for line in (run_dir / f"study2-inputs/solutions-{batch}.jsonl").read_text(
                encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row
        for line in (run_dir / f"study2-inputs/scored-{batch}.jsonl").read_text(
                encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                scored[f"{batch}:{row['problem_id']}"] = row

    out_dir = run_dir / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for iid in ids:
        batch, problem_id = iid.split(":", 1)
        problem = problems[problem_id]
        solution = solutions[iid]["solution"]
        hidden = scored[iid]["hidden"]
        # Recover the failing inputs and the values, so the category rests on evidence.
        witness = witness_for(problem, solution, hidden)
        record = {
            "instance_id": iid, "benchmark": problem.benchmark,
            "hidden_total": hidden.get("total"), "hidden_mode": hidden.get("mode"),
            "hidden_timed_out": hidden.get("timed_out"),
            "hidden_error": hidden.get("error", "")[:400],
            "hidden_failed_n": len(hidden.get("failed_indices") or []),
            "hidden_failed_indices": (hidden.get("failed_indices") or [])[:20],
            "witness": witness,
        }
        index.append(record)
        (out_dir / f"{iid.replace('/', '_').replace(':', '_')}.txt").write_text(
            "\n\n".join([
                f"=== {iid}  ({problem.benchmark}) ===",
                f"--- hidden outcome ---\n{json.dumps(record, indent=2)[:4000]}",
                f"--- specification ---\n{problem.spec}",
                f"--- visible suite ---\n{problem.visible_tests_text()}",
                f"--- candidate solution ---\n{solution}",
                f"--- dataset canonical solution ---\n{problem.canonical_solution}",
            ]), encoding="utf-8")
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(index)} files to {out_dir}")
    return 0


def witness_for(problem, solution: str, hidden: dict) -> dict:
    """The first failing hidden inputs, with the expected and the actual value.

    Built by re-instrumenting the suite through ``execute.instrument_plus_suite`` with a
    collector that records values instead of only indices. Instrumenting *inside* the
    suite matters: HumanEval+ wraps its vectors in ``check(candidate)``, so ``inputs`` and
    ``results`` are locals and code appended at module level cannot see them.

    Runs in ``execute.py``'s subprocess sandbox — candidate code is untrusted and is never
    imported into this interpreter. Where the suite is not the instrumented EvalPlus shape
    there is no per-input vector to recover and the witness says so rather than inventing
    one.
    """
    if hidden.get("timed_out"):
        return {"kind": "timeout", "detail": "the hidden suite did not terminate"}
    if hidden.get("mode") != "vector" or not (hidden.get("failed_indices") or []):
        return {"kind": "no_vector",
                "detail": f"mode={hidden.get('mode')}, "
                          f"error={(hidden.get('error') or '')[:200]}"}

    witness_collector = """
{indent}__w = []
{indent}for i, (inp, exp) in enumerate(zip(inputs, results)):
{indent}    try:
{indent}        {call}
{indent}    except BaseException:
{indent}        try:
{indent}            __act = repr(CANDIDATE_EXPR)
{indent}        except BaseException as __e:
{indent}            __act = "<raised " + type(__e).__name__ + ": " + str(__e) + ">"
{indent}        if len(__w) < 5:
{indent}            __w.append({{"index": i, "input": repr(inp)[:400],
{indent}                         "expected": repr(exp)[:400], "actual": __act[:400]}})
{indent}import json as __json, sys as __sys
{indent}__sys.stderr.write("__CROSSAUDIT_WITNESS__" + __json.dumps(__w) + "\\n")
"""
    call = ("assertion(candidate(*inp), exp, 0)" if problem.benchmark == "humaneval"
            else f"assertion({problem.entry_point}(*inp), exp, 0)")
    expr = call[len("assertion("):call.rindex(", exp, 0)")]
    original = execute._COLLECTOR
    try:
        execute._COLLECTOR = witness_collector.replace("CANDIDATE_EXPR", expr)
        program, instrumented = problem.hidden_program(solution)
    finally:
        execute._COLLECTOR = original
    if not instrumented:
        return {"kind": "no_vector", "detail": "suite is not the instrumented shape"}

    _code, _out, err, timed = execute._run(program, execute.DEFAULT_TIMEOUT)
    if timed:
        return {"kind": "timeout", "detail": "witness probe timed out"}
    for line in err.splitlines():
        if line.startswith("__CROSSAUDIT_WITNESS__"):
            try:
                return {"kind": "vector",
                        "cases": json.loads(line[len("__CROSSAUDIT_WITNESS__"):])}
            except json.JSONDecodeError:
                break
    return {"kind": "probe_failed", "detail": err[-400:]}


if __name__ == "__main__":
    raise SystemExit(main())
