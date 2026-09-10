"""Study 22 — the ceiling on defects the specification determines.

Preregistered in ``inject/PREREGISTRATION.md``, committed before the first model call.

    python benchmarks/code/inject.py --build <run-dir>   # injection, filters, gate
    python benchmarks/code/inject.py --plan  <run-dir>
    python benchmarks/code/inject.py --run   <run-dir> --budget-usd 35

Population I is built from ceiling 1's 150 stratum-C instances: the generator's own solutions
that pass both suites. One defect is injected into each by the generator's own model, and the
instance enters I only if six mechanical filters and a two-model gate accept it (§1). The audit
is the shipped cross auditor, K = 8, ceiling 1's protocol and cache discipline, through
``explore.run_detector`` unchanged. ``src/`` is untouched; no corpus or model text is committed.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

import audit as study1  # noqa: E402
import audit2  # noqa: E402
import execute  # noqa: E402
import explore  # noqa: E402
from corpus import Problem, load_problems  # noqa: E402

RECORDS = HERE / "records"
INJECT = RECORDS / "inject"
CEILING_CACHE = RECORDS / "ceiling"
EXPLORE_CACHE = RECORDS / "explore"

#: §1: the injector is the generator's own model; the gate is two models, neither the auditor.
INJECTOR_SPEC = "anthropic:claude-haiku-4-5-20251001"
GATE_SPECS = ("anthropic:claude-sonnet-4-6", "openai:gpt-5.6-luna")
PROBE_SPEC = "anthropic:claude-opus-4-8"
AUDITOR_FAMILY = "cross"                      # openai:gpt-5.6-terra, ceiling 1's shipped cross
LADDER = [(AUDITOR_FAMILY, d) for d in range(1, 9)]
MIN_QUOTE_WORDS = 6                           # F1
MAX_CHANGED_LINES = 4                         # F4
SEED = 20260916


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------------
# injection
# ---------------------------------------------------------------------------------

INJECTOR_SYSTEM = (
    "You introduce a single realistic defect into a working Python solution, for research on "
    "code review. Return ONLY a JSON object, no prose and no code fence around the object."
)

INJECTOR_USER = """Here is a programming task, the tests the author was given, and a solution that passes them.

--- task ---
{spec}

--- tests the author was given ---
{tests}

--- solution (passes these tests and a larger hidden suite) ---
{solution}

Introduce EXACTLY ONE semantic defect into the solution, so that:
  * the modified solution still passes every test shown above,
  * the modified solution is wrong on some other inputs,
  * the defect violates something the task statement above actually says,
  * the change is small (a few lines at most) and looks like an ordinary mistake a careful
    programmer could make - not a marker, not a comment, not obviously deliberate.

Return a JSON object with exactly these keys:
  "code":          the full modified solution, ready to run
  "quote":         a span copied WORD FOR WORD from the task statement above that the modified
                   solution now violates (at least six words, copied exactly, not paraphrased)
  "input_class":   one sentence naming the inputs on which the modified solution is now wrong
  "witness_input": one concrete argument list on which the modified solution differs from the
                   original, written as a Python literal (for example: [[1, 2, 3], 0])
"""


def parse_injection(text: str) -> dict | None:
    """The JSON object, tolerating a fence or leading prose. None if it is not there."""
    body = text.strip()
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", body, re.S)
    if fence:
        body = fence.group(1).strip()
    start = body.find("{")
    if start < 0:
        return None
    for end in range(len(body), start, -1):
        if body[end - 1] != "}":
            continue
        try:
            obj = json.loads(body[start:end])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and {"code", "quote", "input_class"} <= set(obj):
            return obj
    return None


def changed_lines(base: str, modified: str) -> int:
    diff = list(difflib.unified_diff(base.splitlines(), modified.splitlines(), n=0, lineterm=""))
    return sum(1 for line in diff
               if (line.startswith("+") and not line.startswith("+++"))
               or (line.startswith("-") and not line.startswith("---")))


def imports_of(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"<unparseable>"}
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def changed_line_is_branched(base: str, modified: str) -> bool | None:
    """§4.3, decided mechanically: is the first changed line nested under a conditional?"""
    try:
        tree = ast.parse(modified)
    except SyntaxError:
        return None
    base_lines = base.splitlines()
    for index, line in enumerate(modified.splitlines(), start=1):
        if index > len(base_lines) or base_lines[index - 1] != line:
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.Try, ast.ExceptHandler)):
                    for child in ast.walk(node):
                        if getattr(child, "lineno", None) == index and child is not node:
                            return True
            return False
    return False


def filter_one(problem: Problem, base: str, obj: dict, timeout: float) -> dict:
    """F1-F6 of §1. Every field is mechanical; nothing here is a judgement."""
    code = obj.get("code") or ""
    quote = obj.get("quote") or ""
    out: dict = {"F1_quote_in_spec": False, "F2_visible_passes": False,
                 "F3_hidden_fails": False, "F4_small_diff": False,
                 "F5_runs": False, "F6_witness": False,
                 "changed_lines": None, "quote_words": len(quote.split()),
                 "hidden": None, "visible": None, "branched": None}
    out["F1_quote_in_spec"] = (out["quote_words"] >= MIN_QUOTE_WORDS
                               and norm_ws(quote) in norm_ws(problem.spec))
    out["changed_lines"] = changed_lines(base, code)
    out["F4_small_diff"] = (0 < out["changed_lines"] <= MAX_CHANGED_LINES
                            and imports_of(code) <= imports_of(base))
    if not code.strip():
        return out
    visible = execute.run_suite(problem.visible_program(code),
                                timeout=timeout, instrumented=problem.visible_instrumented)
    out["visible"] = visible.as_dict()
    out["F2_visible_passes"] = bool(visible.passed)
    out["F5_runs"] = not visible.timed_out and "SyntaxError" not in (visible.error or "")
    program, instrumented = problem.hidden_program(code)
    hidden = execute.run_suite(program, timeout=timeout, instrumented=instrumented)
    out["hidden"] = hidden.as_dict()
    out["F3_hidden_fails"] = (not hidden.passed) and not hidden.timed_out
    out["F6_witness"] = bool(obj.get("witness_input"))
    out["branched"] = changed_line_is_branched(base, code)
    out["accepted_by_filters"] = all(out[k] for k in
                                     ("F1_quote_in_spec", "F2_visible_passes", "F3_hidden_fails",
                                      "F4_small_diff", "F5_runs", "F6_witness"))
    return out


# ---------------------------------------------------------------------------------
# the construction gate (§1)
# ---------------------------------------------------------------------------------

GATE_SYSTEM = ("You judge whether a specification, as written, settles a question about code. "
               "Answer with one word: YES or NO.")

GATE_USER = """--- specification ---
{spec}

--- version A ---
{base}

--- version B ---
{modified}

Version B differs from version A. Someone claims B is WRONG on this class of inputs:
    {input_class}
and that the specification settles it, quoting:
    "{quote}"

Question: does the specification ABOVE, as written, entail that B's behaviour on that class of
inputs is wrong? Answer YES only if you can point to words in the specification that settle it.
Answer NO if the specification is silent on those inputs, or if a reasonable reading of it
allows B's behaviour.

Answer with one word, YES or NO."""


def gate_one(client, spec_model: str, problem: Problem, base: str, obj: dict) -> dict:
    user = GATE_USER.format(spec=problem.spec, base=base, modified=obj["code"],
                            input_class=obj.get("input_class", ""), quote=obj.get("quote", ""))
    completion = client.complete(model=spec_model, system=GATE_SYSTEM, user=user)
    word = (completion.text or "").strip().upper()
    return {"model": spec_model, "yes": word.startswith("YES"),
            "raw_first_word": word.split()[0][:12] if word.split() else "",
            "cost_usd": float(completion.cost_usd)}


# ---------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------

def load_solutions(run_dir: Path) -> dict[str, dict]:
    solutions: dict[str, dict] = {}
    for batch in ("b1", "b2"):
        path = run_dir / f"study2-inputs/solutions-{batch}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row
    return solutions


def build(run_dir: Path, workers: int, timeout: float, limit: int | None) -> int:
    from crossaudit.config import load
    from provider import CrossAuditClient
    from run import load_credentials
    from concurrent.futures import ThreadPoolExecutor

    load_credentials()
    instances = explore.load_instances()
    audit_set = explore.load_audit_set()
    base_ids = [i for i in audit_set if instances[i]["stratum"] == "C"]
    if limit:
        base_ids = base_ids[:limit]
    print(f"base: {len(base_ids)} stratum-C instances", flush=True)
    problems = {p.problem_id: p for p in load_problems()}
    solutions = load_solutions(run_dir)

    scratch = run_dir / "projects"
    scratch.mkdir(parents=True, exist_ok=True)
    project = explore.build_project(scratch, ("holistic", AUDITOR_FAMILY, 1),
                                    study1.shipped_constitution())
    cfg = load(project / "crossaudit.yml")
    client = CrossAuditClient(cfg=cfg, phase="inject", run_id="inject-build")

    archive = run_dir / "injected"
    archive.mkdir(parents=True, exist_ok=True)
    cache_path = archive / "injections.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    lock = threading.Lock()

    def inject_one(iid: str) -> tuple[str, dict]:
        inst = instances[iid]
        problem = problems[inst["problem_id"]]
        base = solutions[iid]["solution"]
        with lock:
            hit = cache.get(iid)
        if hit is not None:
            return iid, hit
        user = INJECTOR_USER.format(spec=problem.spec, tests=problem.visible_tests_text(),
                                    solution=base)
        started = time.monotonic()
        try:
            completion = client.complete(model=INJECTOR_SPEC, system=INJECTOR_SYSTEM, user=user)
        except Exception as exc:  # noqa: BLE001
            return iid, {"error": f"{type(exc).__name__}: {exc}"}
        obj = parse_injection(completion.text or "")
        entry = {"parsed": obj is not None, "cost_usd": float(completion.cost_usd),
                 "wall_s": time.monotonic() - started,
                 "prompt_sha256": sha(user), "response_sha256": sha(completion.text or "")}
        if obj is not None:
            entry.update({"code": obj["code"], "quote": obj["quote"],
                          "input_class": obj.get("input_class", ""),
                          "witness_input": obj.get("witness_input", "")})
        with lock:
            cache[iid] = entry
            cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
        return iid, entry

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, _ in enumerate(pool.map(inject_one, base_ids), 1):
            if n % 25 == 0:
                print(f"  injected {n}/{len(base_ids)}", flush=True)

    # filters, then the gate on what the filters accepted
    rows: dict[str, dict] = {}
    for iid in base_ids:
        entry = cache.get(iid) or {}
        inst = instances[iid]
        problem = problems[inst["problem_id"]]
        base = solutions[iid]["solution"]
        row = {"instance_id": iid, "problem_id": inst["problem_id"], "batch": inst["batch"],
               "parsed": bool(entry.get("parsed")),
               "base_solution_sha256": sha(base)}
        if entry.get("parsed"):
            row.update(filter_one(problem, base, entry, timeout))
            row["modified_sha256"] = sha(entry["code"])
        else:
            row["accepted_by_filters"] = False
        rows[iid] = row
    passed = [i for i in base_ids if rows[i].get("accepted_by_filters")]
    print(f"filters accept {len(passed)} of {len(base_ids)}", flush=True)

    gate_path = archive / "gate.json"
    gate_cache = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {}

    def gate_all(iid: str) -> tuple[str, list[dict]]:
        with lock:
            hit = gate_cache.get(iid)
        if hit is not None:
            return iid, hit
        inst = instances[iid]
        problem = problems[inst["problem_id"]]
        base = solutions[iid]["solution"]
        verdicts = []
        for spec_model in GATE_SPECS:
            try:
                verdicts.append(gate_one(client, spec_model, problem, base, cache[iid]))
            except Exception as exc:  # noqa: BLE001
                verdicts.append({"model": spec_model, "yes": False,
                                 "error": f"{type(exc).__name__}: {exc}", "cost_usd": 0.0})
        with lock:
            gate_cache[iid] = verdicts
            gate_path.write_text(json.dumps(gate_cache, indent=1, sort_keys=True), encoding="utf-8")
        return iid, verdicts

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, _ in enumerate(pool.map(gate_all, passed), 1):
            if n % 25 == 0:
                print(f"  gated {n}/{len(passed)}", flush=True)

    for iid in passed:
        verdicts = gate_cache.get(iid) or []
        rows[iid]["gate"] = [{k: v for k, v in g.items() if k != "cost_usd"} for g in verdicts]
        rows[iid]["in_population_I"] = bool(verdicts) and all(g.get("yes") for g in verdicts)
    population = [i for i in base_ids if rows[i].get("in_population_I")]

    INJECT.mkdir(parents=True, exist_ok=True)
    spent = sum(float(v.get("cost_usd") or 0) for v in cache.values()) + sum(
        float(g.get("cost_usd") or 0) for vs in gate_cache.values() for g in vs)
    out = {"study": "study22 / injection", "seed": SEED,
           "injector": INJECTOR_SPEC, "gate": list(GATE_SPECS), "auditor_family": AUDITOR_FAMILY,
           "n_base": len(base_ids), "n_parsed": sum(1 for i in base_ids if rows[i]["parsed"]),
           "n_filters_accept": len(passed), "n_population_I": len(population),
           "filter_drop_reasons": {
               k: sum(1 for i in base_ids if rows[i].get("parsed") and not rows[i].get(k))
               for k in ("F1_quote_in_spec", "F2_visible_passes", "F3_hidden_fails",
                         "F4_small_diff", "F5_runs", "F6_witness")},
           "gate_yes_by_model": {m: sum(1 for i in passed
                                        for g in (gate_cache.get(i) or [])
                                        if g["model"] == m and g.get("yes"))
                                 for m in GATE_SPECS},
           "gate_both_yes": len(population),
           "population_instance_ids": population,
           "rows": {i: rows[i] for i in base_ids},
           "build_spend_usd": round(spent, 6),
           "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (INJECT / "population.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8")
    print(f"population I: {len(population)} instances; build spend ${spent:.3f}", flush=True)
    return 0


# ---------------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------------

def injected_id(iid: str) -> str:
    return f"inj:{iid}"


def install_findings_archive(path: Path) -> None:
    """Every finding's text into the archive (never the repository), as study 19 did."""
    lock = threading.Lock()

    def holistic_one_all(cfg, problem, solution, inst, constitution, run_id, arm):
        from crossaudit.auditor.run import run_audit
        files = study1.increment_files(problem, solution)
        study1._VISIBLE_RESULT = {}
        started = time.monotonic()

        def on_event(*_args, **_kwargs):
            return None
        on_event.run_id = run_id
        on_event.heartbeat = lambda: None
        row = audit2.blank_row(arm, inst)
        try:
            outcome = run_audit(cfg=cfg, sha="0" * 40, round_=1, files=files, notes=[],
                                constitution=constitution, constitution_commit="frozen",
                                task=problem.spec, on_event=on_event,
                                usage_context={"run_id": run_id, "arm": arm,
                                               "problem_id": problem.problem_id})
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                        "wall_s": time.monotonic() - started})
            return row
        model_findings = ((outcome.model_reply or {}).get("findings") or [])
        dcl_findings = outcome.dcl.get("findings", [])
        blockers = [f for f in model_findings if f.get("severity") == "BLOCKER"]
        with lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"instance_id": inst["instance_id"], "arm": arm,
                                     "run_id": run_id, "verdict": outcome.verdict,
                                     "findings": model_findings}, ensure_ascii=False) + "\n")
        row.update({"ok": True, "error": "", "verdict": outcome.verdict,
                    "n_findings": len(model_findings), "n_blockers": len(blockers),
                    "n_dcl_findings": len(dcl_findings), "n_dcl_blockers": len(dcl_blockers),
                    "flagged": bool(blockers or dcl_blockers),
                    "wall_s": time.monotonic() - started})
        return row

    audit2.holistic_one = holistic_one_all


def run(run_dir: Path, budget: float, workers: int, max_passes: int, plan: bool) -> int:
    explore.EXPLORE = INJECT
    (INJECT / "cache").mkdir(parents=True, exist_ok=True)
    pop_path = INJECT / "population.json"
    if not pop_path.exists():
        raise SystemExit("run --build first")
    population = json.loads(pop_path.read_text(encoding="utf-8"))
    base_ids = population["population_instance_ids"]
    scope = [injected_id(i) for i in base_ids]
    scope_set = set(scope)
    print(f"scope: {len(scope)} injected instances", flush=True)

    have = {("holistic", f, d): explore.load_detector(("holistic", f, d), scope_set)
            for f, d in LADDER}
    if plan:
        for f, d in LADDER:
            print(f"ladder {f} d{d}: {len(scope) - len(have[('holistic', f, d)])} to run")
        return 0

    from run import load_credentials
    load_credentials()
    study1.register_visible_tests_check()
    constitution = study1.shipped_constitution()
    base_instances = explore.load_instances()
    problems = {p.problem_id: p for p in load_problems()}
    base_solutions = load_solutions(run_dir)
    injections = json.loads((run_dir / "injected" / "injections.json").read_text(encoding="utf-8"))

    instances = {}
    solutions = {}
    for iid in base_ids:
        new_id = injected_id(iid)
        code = injections[iid]["code"]
        instances[new_id] = {**base_instances[iid], "instance_id": new_id, "stratum": "P",
                             "solution_sha256": sha(code)}
        solutions[new_id] = {"solution": code}

    scratch = run_dir / "projects"
    scratch.mkdir(parents=True, exist_ok=True)
    spend = explore.Spend(f"inject-{time.strftime('%m%d%H%M%S', time.gmtime())}-")
    for family, draw in LADDER:
        key = ("holistic", family, draw)
        missing = [i for i in scope if i not in have[key]]
        if not missing:
            print(f"ladder {family} d{draw}: already complete")
            continue
        total = spend.total()
        if budget and total >= budget:
            print(f"\nSTOP: spend ${total:.3f} reached the ${budget:.2f} cap; {family} d{draw} not run")
            break
        print(f"\nladder {family} d{draw}: {len(missing)} instances (spend so far ${total:.3f})",
              flush=True)
        install_findings_archive(run_dir / f"findings-{family}-d{draw}.jsonl")
        explore.run_detector(key, missing, instances=instances, problems=problems,
                             solutions=solutions, constitution=constitution, cfg_cache={},
                             scratch=scratch, spend=spend, budget_usd=budget, workers=workers,
                             property_cache_path=run_dir / "study2-inputs/properties.json",
                             max_passes=max_passes)
        have[key] = explore.load_detector(key, scope_set)
        print(f"  {family} d{draw}: {len(have[key])} of {len(scope)}; spend ${spend.total():.3f}",
              flush=True)
    print(f"\nstudy-22 spend this invocation: ${spend.total():.4f}", flush=True)
    manifest = {"study": "study22 / injection", "ladder": LADDER, "scope_n": len(scope),
                "draws_complete": {f"{f}-d{d}": len(have[("holistic", f, d)]) for f, d in LADDER},
                "spend_usd_this_invocation": round(spend.total(), 6),
                "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (INJECT / f"manifest-{manifest['written_utc'].replace(':', '')}.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("run_dir")
    ap.add_argument("--budget-usd", type=float, default=35.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-passes", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=execute.DEFAULT_TIMEOUT)
    ap.add_argument("--limit", type=int, default=None, help="build only the first N (a probe)")
    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir)
    if args.build:
        return build(run_dir, args.workers, args.timeout, args.limit)
    return run(run_dir, args.budget_usd, args.workers, args.max_passes, args.plan)


if __name__ == "__main__":
    raise SystemExit(main())
