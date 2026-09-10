"""Study 17 — recognising a wrong generated test without the canonical solution.

Preregistered in ``testgen/PREREGISTRATION-VAL.md`` (with Amendment 1) before any model
call and before this module existed. Study 16 found that every false positive of the
test-generating auditor was a WRONG test — one that also fails on the canonical solution
— and that with those removed by the oracle the union with the reading auditor moved the
front by seven P instances. The product has no canonical solution. This study asks
whether further independent draws of the generator recognise a wrong test.

    draw 1      study 16's suite per problem, FROZEN: its tests, its per-candidate
                outcomes (``records/testgen/rows.jsonl``) and its wrong/right gold are
                read, never re-executed
    draw 2, 3   two further generations per problem, same prompt (the per-problem
                prompt hash must equal draw 1's), same model; executed against every
                candidate of the problem and — for scoring only — the canonical solution

The rules (§3 of the preregistration) decide, for each draw-1 test that FAILS on a
candidate, whether to keep or drop it, from the other draws' outcomes on that candidate
and nothing else:

    A       keep iff draw 2 AND draw 3 each have at least one failing test on the candidate
    B       keep iff draw 2 OR draw 3 has at least one failing test on the candidate
    Cprime  keep iff at least one OTHER draw-1 test fails on the candidate (zero-cost comparator)

Primary (§4): the wrong-test rate among kept failing applications, and how many of the
seven ``validated-only`` instances keep a correct failing test. Kill: > 2% wrong among
kept, or fewer than 5 of 7. The canonical solution scores the rules; it enters none.

The information boundary is ``architectures.py``'s, unchanged: the generator receives
``problem.spec`` and ``problem.visible_tests_text()`` as plain strings. ``execute.py``
and ``src/`` are untouched. Generated test text lives in the run directory (the archive),
never under ``records/``.

    python benchmarks/code/testgen_val.py run --run <dir> --scratch <dir> --budget-usd 5
    python benchmarks/code/testgen_val.py report
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

import architectures as arch  # noqa: E402
import explore  # noqa: E402
import testgen  # noqa: E402
from corpus import load_problems  # noqa: E402
from report_ceiling import cluster_bootstrap_ci  # noqa: E402
from testgen import MODEL_SPEC, HC_KEY, run_generated, sha256_text  # noqa: E402

RECORDS = HERE / "records" / "testgen-val"
ROWS = RECORDS / "rows.jsonl"
NUMBERS = RECORDS / "numbers.json"
LEDGER = RECORDS / "ledger.json"
DRAWS = (2, 3)
RULES = ("A", "B", "Cprime")
#: Preregistration §4.
BOOTSTRAP_SEED = 20260915
BOOTSTRAP_REPS = 10_000
KILL_WRONG_RATE = 0.02
KILL_RETENTION = 5
#: §2: draw 2's responses byte-identical to draw 1's beyond this fraction stop the study.
DEGENERACY_FRACTION = 0.5


def suites_path(k: int) -> Path:
    return RECORDS / f"suites-d{k}.json"


def cache_name(k: int) -> str:
    return f"generated_tests-d{k}.json"


# ---------------------------------------------------------------------------------
# the rules — pure
# ---------------------------------------------------------------------------------

def keep(rule: str, f1: set[int], f2: set[int], f3: set[int]) -> set[int]:
    """The draw-1 failing indices a rule KEEPS on one candidate (§3).

    ``f1``, ``f2``, ``f3`` are the sets of draw-1, draw-2 and draw-3 tests that fail on
    the candidate. A passing draw-1 test is not in ``f1`` and is not decided on. An empty
    draw has no failing test and matches nothing.
    """
    f1 = set(f1)
    if rule == "A":
        ok = bool(f2) and bool(f3)
    elif rule == "B":
        ok = bool(f2) or bool(f3)
    elif rule == "Cprime":
        ok = len(f1) >= 2
    else:
        raise ValueError(rule)
    return f1 if ok else set()


def flag(kept: set[int], candidate_timed_out: bool) -> bool:
    """The arm a rule implies (§5): a kept failing test, or a draw-1 timeout (Amendment 1)."""
    return bool(kept) or bool(candidate_timed_out)


def is_artefact(row: dict) -> bool:
    """A draw-1 run in which no test was evaluated: a timeout or a pre-collector death."""
    return bool(row["candidate_timed_out"]) or bool(row["candidate_error"])


def select_best(per_rule: dict[str, dict]) -> tuple[str, bool]:
    """§4's selection order; returns (rule, holds).

    Among rules retaining ≥ 5 of 7, the lowest wrong-rate point estimate; ties by higher
    retention, then A before B before Cprime. If none retains 5, the highest retention
    and H17 is killed.
    """
    order = {r: i for i, r in enumerate(RULES)}
    eligible = [r for r in RULES if per_rule[r]["retained"] >= KILL_RETENTION]
    if eligible:
        best = min(eligible, key=lambda r: (per_rule[r]["rate"] if per_rule[r]["rate"] is not None else 1.0,
                                            -per_rule[r]["retained"], order[r]))
        return best, not per_rule[best]["killed"]
    best = max(RULES, key=lambda r: (per_rule[r]["retained"], -order[r]))
    return best, False


def verdict(rate: float | None, retained: int) -> dict:
    killed_rate = rate is not None and rate > KILL_WRONG_RATE
    killed_ret = retained < KILL_RETENTION
    return {"killed": bool(killed_rate or killed_ret),
            "killed_by_wrong_rate": bool(killed_rate), "killed_by_retention": bool(killed_ret)}


def normalised(src: str) -> str:
    """A test's source as its AST dump, so that whitespace and quoting do not separate draws."""
    try:
        return ast.dump(ast.parse(src))
    except (SyntaxError, ValueError):
        return src.strip()


# ---------------------------------------------------------------------------------
# generation — a draw is one call per problem, cached with its text in the run dir
# ---------------------------------------------------------------------------------

def generate_draw(client, problems: dict, pids: list[str], cache_path: Path, *,
                  budget_usd: float, spend: dict, workers: int, max_passes: int,
                  failed_log: Path) -> dict:
    """Fill ``cache_path`` with one suite per problem in ``pids``; returns the cache.

    The same prompt builder, parser and compile filter as study 16; the prompt hash is
    recorded per problem so the report can check it equals draw 1's. Spend is tallied
    into ``spend["usd"]`` across draws and halts every worker at the cap.
    """
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    lock = threading.Lock()
    halted = threading.Event()

    def one(pid: str) -> str | None:
        if halted.is_set():
            return None
        try:
            with lock:
                if pid in cache:
                    return pid
            system, user = arch.testgen_prompt(problems[pid].spec, problems[pid].visible_tests_text())
            started = time.monotonic()
            completion = client.complete(model=MODEL_SPEC, system=system, user=user)
            parsed = arch.parse_tests(completion.text)
            tests, dropped = arch.compilable(parsed)
            with lock:
                cache[pid] = {"tests": tests, "n_parsed": len(parsed), "n_uncompilable": dropped,
                              "prompt_sha256": sha256_text(system + "\n" + user),
                              "response_sha256": sha256_text(completion.text),
                              "cost_usd": float(completion.cost_usd),
                              "input_tokens": int(completion.input_tokens),
                              "output_tokens": int(completion.output_tokens),
                              "model": completion.model,
                              "wall_s": round(time.monotonic() - started, 3)}
                cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")
                spend["usd"] += float(completion.cost_usd)
                if budget_usd and spend["usd"] >= budget_usd:
                    print(f"    STOP: spend ${spend['usd']:.3f} reached the ${budget_usd:.2f} cap",
                          flush=True)
                    halted.set()
        except Exception as exc:  # noqa: BLE001
            with lock:
                with failed_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"problem_id": pid, "cache": cache_path.name,
                                             "error": f"{type(exc).__name__}: {exc}"[:300]}) + "\n")
            return None
        return pid

    for attempt in range(1, max_passes + 1):
        pending = [pid for pid in pids if pid not in cache]
        if not pending or halted.is_set():
            break
        if attempt > 1:
            print(f"    pass {attempt}: {len(pending)} problems still without a suite; "
                  f"waiting 75s for the breaker to close", flush=True)
            time.sleep(75)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for done, _ in enumerate(pool.map(one, pending), start=1):
                if done % 20 == 0 or done == len(pending):
                    print(f"    {cache_path.name}: generated {done}/{len(pending)}  "
                          f"${spend['usd']:.3f}", flush=True)
    return cache


def shapes_of(cache: dict) -> dict:
    return {pid: {k: v for k, v in entry.items() if k != "tests"} | {"n_tests": len(entry["tests"])}
            for pid, entry in cache.items()}


def ledger_totals(ledger: Path, run_ids: tuple[str, ...]) -> dict:
    """Spend per run_id from the product's own usage ledger — counts and USD, nothing else."""
    from crossaudit import usage
    out = {rid: {"usd": 0.0, "calls": 0, "input": 0, "output": 0} for rid in run_ids}
    if not ledger.exists():
        return out
    events, _ = usage.read_events(ledger)
    for event in events:
        rid = event.get("run_id")
        if rid in out:
            out[rid]["usd"] += float(event.get("api_value_usd") or 0.0)
            out[rid]["calls"] += 1
            out[rid]["input"] += int(event.get("input", 0) or 0)
            out[rid]["output"] += int(event.get("output", 0) or 0)
    for rid in out:
        out[rid]["usd"] = round(out[rid]["usd"], 6)
    return out


# ---------------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------------

def run(args) -> int:
    from run import load_credentials
    from provider import CrossAuditClient
    from crossaudit.config import load
    import audit as study1

    run_dir = Path(args.run)
    d1_rows = testgen.load_rows()                       # frozen draw 1, study 16's records
    if not d1_rows:
        print("study 16's rows are the frozen draw 1; none found")
        return 1
    problems = {p.problem_id: p for p in load_problems()}
    pids = sorted({r["problem_id"] for r in d1_rows.values()})
    d1_cache = json.loads((run_dir / "inputs" / "generated_tests.json").read_text(encoding="utf-8"))
    missing = [pid for pid in pids if pid not in d1_cache]
    if missing:
        print(f"draw-1 text missing for {len(missing)} problems in {run_dir / 'inputs'}")
        return 1
    solutions: dict[str, dict] = {}
    for batch in sorted({r["batch"] for r in d1_rows.values()}):
        for line in (run_dir / "inputs" / f"solutions-{batch}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                solutions[f"{batch}:{row['problem_id']}"] = row
    caches = {k: (json.loads((run_dir / cache_name(k)).read_text(encoding="utf-8"))
                  if (run_dir / cache_name(k)).exists() else {}) for k in DRAWS}
    print(f"{len(d1_rows)} frozen draw-1 rows over {len(pids)} problems; "
          + ", ".join(f"draw {k}: {len(caches[k])} suites cached" for k in DRAWS), flush=True)
    if args.dry_run:
        return 0

    RECORDS.mkdir(parents=True, exist_ok=True)
    load_credentials()
    study1.register_visible_tests_check()
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    project = explore.build_project(scratch, HC_KEY, study1.shipped_constitution())
    cfg = load(project / "crossaudit.yml")
    spend = {"usd": 0.0}
    degenerate = None
    for k in DRAWS:
        if len(caches[k]) < len(pids) and not (k == 3 and degenerate):
            client = CrossAuditClient(cfg=cfg, phase="testgen-val", run_id=f"testgen-val-d{k}")
            caches[k] = generate_draw(client, problems, pids, run_dir / cache_name(k),
                                      budget_usd=args.budget_usd, spend=spend, workers=args.workers,
                                      max_passes=args.max_passes,
                                      failed_log=RECORDS / "generation.failed.jsonl")
        if k == 2:
            # §2's degeneracy stop: identical responses are not independent draws.
            same = sum(1 for pid, e in caches[2].items()
                       if e["response_sha256"] == d1_cache[pid]["response_sha256"])
            degenerate = len(caches[2]) > 0 and same > DEGENERACY_FRACTION * len(caches[2])
            print(f"draw 2: {same}/{len(caches[2])} responses byte-identical to draw 1"
                  + ("  — DEGENERATE, draw 3 not generated" if degenerate else ""), flush=True)
    print(f"generation spend this invocation: ${spend['usd']:.4f}", flush=True)
    for k in DRAWS:
        suites_path(k).write_text(json.dumps(shapes_of(caches[k]), indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
    from crossaudit import usage
    ledger = Path(cfg.root) / cfg.state_dir / usage.LEDGER_NAME
    LEDGER.write_text(json.dumps({"ledger": str(ledger), "read_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                  "by_run_id": ledger_totals(ledger, tuple(f"testgen-val-d{k}" for k in DRAWS))},
                                 indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Execution — no model, no spend. Draws 2 and 3 against every candidate and, for
    # scoring only, the canonical solution; draw 1 is read from the frozen rows.
    have = load_rows()
    executed = 0
    with ROWS.open("a", encoding="utf-8") as handle:
        for iid in sorted(d1_rows):
            if iid in have:
                continue
            r1 = d1_rows[iid]
            pid = r1["problem_id"]
            if any(pid not in caches[k] for k in DRAWS):
                continue
            problem = problems[pid]
            imports = problem.test_imports()
            started = time.monotonic()
            row = {"instance_id": iid, "problem_id": pid, "batch": r1["batch"],
                   "stratum": r1["stratum"], "half": r1["half"], "hc_flagged": r1["hc_flagged"],
                   "d1": {"n_tests": r1["n_tests"], "failed_candidate": r1["failed_candidate"],
                          "failed_canonical": r1["failed_canonical"],
                          "candidate_timed_out": r1["candidate_timed_out"],
                          "candidate_died": bool(r1["candidate_error"]) and not r1["candidate_timed_out"],
                          "canonical_timed_out": r1["canonical_timed_out"],
                          "suite_response_sha256": r1["suite_response_sha256"]},
                   "artefact": is_artefact(r1), "classifiable": not r1["canonical_unusable"]}
            for k in DRAWS:
                tests = caches[k][pid]["tests"]
                cand = run_generated(solutions[iid]["solution"], imports, tests)
                canon = run_generated(problem.canonical_solution, imports, tests)
                row[f"d{k}"] = {"n_tests": len(tests), "failed_candidate": cand["failed"],
                                "failed_canonical": canon["failed"],
                                "candidate_timed_out": cand["timed_out"],
                                "candidate_died": bool(cand["error"]) and not cand["timed_out"],
                                "canonical_timed_out": canon["timed_out"],
                                "suite_response_sha256": caches[k][pid]["response_sha256"],
                                "prompt_matches_d1": caches[k][pid]["prompt_sha256"] == d1_cache[pid]["prompt_sha256"]}
            f1, f2, f3 = (set(row[f"d{k}"]["failed_candidate"]) for k in (1, 2, 3))
            row["kept"] = {rule: sorted(keep(rule, f1, f2, f3)) for rule in RULES}
            row["flagged"] = {rule: flag(set(row["kept"][rule]), r1["candidate_timed_out"]) for rule in RULES}
            row["wall_s"] = round(time.monotonic() - started, 3)
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            executed += 1
    print(f"executed {executed} instances", flush=True)

    write_identity(d1_cache, caches)
    return 0


def identity_of(d1_cache: dict, caches: dict) -> dict:
    """Draw-to-draw identity (a §5 secondary), from the text: per-problem counts, no text."""
    identity = {}
    for k in DRAWS:
        per_problem = {}
        for pid, e in caches[k].items():
            d1_norm = {normalised(t) for t in d1_cache[pid]["tests"]}
            per_problem[pid] = {"n_tests": len(e["tests"]),
                                "identical_to_a_draw1_test": sum(1 for t in e["tests"] if normalised(t) in d1_norm)}
        identity[f"d{k}"] = {"tests_identical_to_a_draw1_test": sum(v["identical_to_a_draw1_test"] for v in per_problem.values()),
                             "responses_identical_to_draw1": sum(
                                 1 for pid, e in caches[k].items()
                                 if e["response_sha256"] == d1_cache[pid]["response_sha256"]),
                             "per_problem": per_problem}
    return identity


def write_identity(d1_cache: dict, caches: dict) -> None:
    (RECORDS / "identity.json").write_text(json.dumps(identity_of(d1_cache, caches), indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")


def identity(args) -> int:
    """Recompute identity.json from the archive's text (the run dir); records keep counts only."""
    run_dir = Path(args.run)
    d1_cache = json.loads((run_dir / "inputs" / "generated_tests.json").read_text(encoding="utf-8"))
    caches = {k: json.loads((run_dir / cache_name(k)).read_text(encoding="utf-8")) for k in DRAWS}
    write_identity(d1_cache, caches)
    return 0


def load_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if ROWS.exists():
        for line in ROWS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["instance_id"]] = row
    return rows


# ---------------------------------------------------------------------------------
# the report — the preregistered outcomes, applied and nothing else
# ---------------------------------------------------------------------------------

def validated_only(d1_rows: dict[str, dict]) -> list[str]:
    """§0's seven: confirm-half P, flagged by the oracle-validated arm, not by hc."""
    return sorted(i for i, r in d1_rows.items()
                  if r["half"] == "confirm" and r["stratum"] == "P"
                  and r["flagged_validated"] and r["hc_flagged"] is False)


def rate_block(values_by_cluster: dict[str, list[float]]) -> dict:
    k = int(sum(sum(v) for v in values_by_cluster.values()))
    n = sum(len(v) for v in values_by_cluster.values())
    lo, hi = explore.wilson(k, n) if n else (None, None)
    blo, bhi = cluster_bootstrap_ci(values_by_cluster, BOOTSTRAP_REPS, BOOTSTRAP_SEED)
    return {"k": k, "n": n, "rate": (k / n if n else None), "wilson": [lo, hi],
            "bootstrap_problem_cluster": [blo, bhi]}


def primary_for(rule: str, rows: list[dict], seven: list[str]) -> dict:
    """§4 (i) and (ii) for one rule, on the clean, classifiable rows with all three draws."""
    wrong_kept: dict[str, list[float]] = {}
    right_kept: dict[str, list[float]] = {}   # per right failing application: 1 if kept
    wrong_removed: dict[str, list[float]] = {}  # per wrong failing application: 1 if dropped
    retained: list[str] = []
    for r in rows:
        if r["artefact"] or not r["classifiable"]:
            continue
        pid = r["problem_id"]
        f1 = set(r["d1"]["failed_candidate"])
        wrong = set(r["d1"]["failed_canonical"])
        kept = set(r["kept"][rule])
        for t in f1:
            if t in kept:
                wrong_kept.setdefault(pid, []).append(1.0 if t in wrong else 0.0)
            if t in wrong:
                wrong_removed.setdefault(pid, []).append(0.0 if t in kept else 1.0)
            else:
                right_kept.setdefault(pid, []).append(1.0 if t in kept else 0.0)
        if r["instance_id"] in seven and (kept - wrong):
            retained.append(r["instance_id"])
    block = rate_block(wrong_kept)
    out = {"wrong_among_kept": block, "rate": block["rate"],
           "right_failing_retained": rate_block(right_kept),
           "wrong_failing_removed": rate_block(wrong_removed),
           "retained": len(retained), "retained_of": len(seven), "retained_ids": retained}
    out.update(verdict(block["rate"], len(retained)))
    return out


def unique_level(rule: str, rows: list[dict]) -> dict:
    """§5: the brief's unique-test quantity, and the exposed-test level, per rule."""
    by_problem: dict[str, list[dict]] = {}
    for r in rows:
        if r["classifiable"]:
            by_problem.setdefault(r["problem_id"], []).append(r)
    all_tests: dict[str, list[float]] = {}          # wrong among kept, over every classifiable test
    exposed: dict[str, list[float]] = {}             # wrong among kept, over tests failing somewhere
    right_retained: dict[str, list[float]] = {}      # per right exposed test: 1 if kept somewhere
    wrong_removed: dict[str, list[float]] = {}       # per wrong exposed test: 1 if kept nowhere
    n_all = n_kept_all = n_exposed = 0
    for pid, prs in by_problem.items():
        n1 = prs[0]["d1"]["n_tests"]
        wrong = set()
        for r in prs:
            wrong.update(r["d1"]["failed_canonical"])
        clean = [r for r in prs if not r["artefact"]]
        for t in range(n1):
            n_all += 1
            fails_on = [r for r in clean if t in r["d1"]["failed_candidate"]]
            kept_somewhere = any(t in r["kept"][rule] for r in fails_on)
            kept = kept_somewhere or not fails_on         # passes everywhere: no decision
            if kept:
                n_kept_all += 1
                all_tests.setdefault(pid, []).append(1.0 if t in wrong else 0.0)
            if fails_on:
                n_exposed += 1
                if kept_somewhere:
                    exposed.setdefault(pid, []).append(1.0 if t in wrong else 0.0)
                if t in wrong:
                    wrong_removed.setdefault(pid, []).append(0.0 if kept_somewhere else 1.0)
                else:
                    right_retained.setdefault(pid, []).append(1.0 if kept_somewhere else 0.0)
    return {"all_classifiable_tests": n_all, "kept": n_kept_all,
            "wrong_among_kept_all": rate_block(all_tests),
            "exposed_tests": n_exposed, "wrong_among_kept_exposed": rate_block(exposed),
            "exposed_right_retained": rate_block(right_retained),
            "exposed_wrong_removed": rate_block(wrong_removed)}


def arm_rates(rule: str, rows: list[dict], half: str) -> dict:
    out = {}
    for stratum in ("P", "C", "F"):
        sub = [r for r in rows if r["half"] == half and r["stratum"] == stratum]
        own = {}
        for r in sub:
            own.setdefault(r["problem_id"], []).append(1.0 if r["flagged"][rule] else 0.0)
        union = {}
        for r in sub:
            if r["hc_flagged"] is not None:
                union.setdefault(r["problem_id"], []).append(1.0 if (r["flagged"][rule] or r["hc_flagged"]) else 0.0)
        out[stratum] = {"rule": rate_block(own), "hc_union_rule": rate_block(union)}
    return out


def draw_wrongness(rows: list[dict], k: int) -> dict:
    """Draw k scored against the canonical solution, as study 16 scored draw 1."""
    wrong_by_problem: dict[str, set] = {}
    n_by_problem: dict[str, int] = {}
    unusable = set()
    for r in rows:
        d = r[f"d{k}"]
        if d["canonical_timed_out"]:
            unusable.add(r["problem_id"])
            continue
        wrong_by_problem.setdefault(r["problem_id"], set()).update(d["failed_canonical"])
        n_by_problem[r["problem_id"]] = d["n_tests"]
    values = {pid: [1.0 if i in wrong_by_problem.get(pid, set()) else 0.0 for i in range(n)]
              for pid, n in n_by_problem.items() if pid not in unusable and n}
    block = rate_block(values)
    return {"unique_wrong": block["k"], "unique_classifiable": block["n"], "rate": block["rate"],
            "wilson": block["wilson"], "bootstrap_problem_cluster": block["bootstrap_problem_cluster"],
            "problems_canonical_timed_out": len(unusable),
            "problems_with_a_wrong_test": sum(1 for v in wrong_by_problem.values() if v),
            "wrong_by_problem": {pid: sorted(v) for pid, v in wrong_by_problem.items() if v}}


def report(args) -> int:
    rows = list(load_rows().values())
    if not rows:
        print("no rows; run first")
        return 1
    d1_rows = testgen.load_rows()
    seven = validated_only(d1_rows)
    complete = [r for r in rows if all(f"d{k}" in r for k in DRAWS)]
    out: dict = {"n_rows": len(rows), "n_rows_with_all_draws": len(complete),
                 "n_problems": len({r["problem_id"] for r in complete}),
                 "validated_only_ids": seven,
                 "bootstrap": {"seed": BOOTSTRAP_SEED, "reps": BOOTSTRAP_REPS, "unit": "problem"},
                 "kill": {"wrong_rate_gt": KILL_WRONG_RATE, "retention_lt": KILL_RETENTION},
                 "prompt_mismatches": sum(1 for r in complete for k in DRAWS if not r[f"d{k}"]["prompt_matches_d1"]),
                 "rules": {}}
    clean = [r for r in complete if not r["artefact"] and r["classifiable"]]
    fail_apps = sum(len(r["d1"]["failed_candidate"]) for r in clean)
    fail_wrong = sum(len(set(r["d1"]["failed_candidate"]) & set(r["d1"]["failed_canonical"])) for r in clean)
    out["failing_applications"] = {"n": fail_apps, "wrong": fail_wrong, "right": fail_apps - fail_wrong,
                                   "rows_clean_classifiable": len(clean),
                                   "artefact_rows": sum(1 for r in complete if r["artefact"]),
                                   "unclassifiable_rows": sum(1 for r in complete if not r["classifiable"])}
    for rule in RULES:
        entry = {"primary": primary_for(rule, complete, seven), "unique_level": unique_level(rule, complete),
                 "arm": {half: arm_rates(rule, complete, half) for half in ("confirm", "explore")}}
        out["rules"][rule] = entry
    per_rule = {rule: {"rate": out["rules"][rule]["primary"]["rate"],
                       "retained": out["rules"][rule]["primary"]["retained"],
                       "killed": out["rules"][rule]["primary"]["killed"]} for rule in RULES}
    best, holds = select_best(per_rule)
    out["decision"] = {"best_rule": best, "H17": "HOLDS" if holds else "KILL",
                       "per_rule": {rule: ("KILL" if per_rule[rule]["killed"] else "PASS") for rule in RULES}}

    # Secondaries.
    for k in DRAWS:
        out[f"draw{k}"] = draw_wrongness(complete, k)
        suites = json.loads(suites_path(k).read_text(encoding="utf-8")) if suites_path(k).exists() else {}
        n_tests = [s["n_tests"] for s in suites.values()]
        out[f"draw{k}"].update({
            "problems_with_suite": len(suites), "tests_total": sum(n_tests),
            "tests_per_problem": {"mean": (sum(n_tests) / len(n_tests) if n_tests else None),
                                  "min": min(n_tests, default=None), "max": max(n_tests, default=None),
                                  "zero": sum(1 for x in n_tests if x == 0)},
            "uncompilable_total": sum(s["n_uncompilable"] for s in suites.values()),
            "cost_usd_adapter_sum": round(sum(float(s.get("cost_usd", 0.0)) for s in suites.values()), 6),
            "candidate_timeouts": sum(1 for r in complete if r[f"d{k}"]["candidate_timed_out"]),
            "candidate_died_before_collector": sum(1 for r in complete if r[f"d{k}"]["candidate_died"]),
            "canonical_timeouts": sum(1 for r in complete if r[f"d{k}"]["canonical_timed_out"])})
    d1_wrong_problems = {r["problem_id"] for r in complete if r["classifiable"] and r["d1"]["failed_canonical"]}
    out["wrong_test_correlation"] = {
        "problems_with_a_wrong_draw1_test": len(d1_wrong_problems),
        **{f"of_which_also_wrong_in_draw{k}": len(d1_wrong_problems & set(out[f"draw{k}"]["wrong_by_problem"]))
           for k in DRAWS},
        "of_which_wrong_in_draw2_or_draw3": len(d1_wrong_problems & (set(out["draw2"]["wrong_by_problem"]) | set(out["draw3"]["wrong_by_problem"]))),
        "problems_with_a_wrong_test_in_any_draw": len(d1_wrong_problems | set(out["draw2"]["wrong_by_problem"]) | set(out["draw3"]["wrong_by_problem"]))}
    for k in DRAWS:
        out[f"draw{k}"].pop("wrong_by_problem")
    if (RECORDS / "identity.json").exists():
        ident = json.loads((RECORDS / "identity.json").read_text(encoding="utf-8"))
        for k in DRAWS:
            per = ident[f"d{k}"].pop("per_problem", {})
            if per:
                ident[f"d{k}"]["tests_identical_rate"] = rate_block(
                    {pid: [1.0] * v["identical_to_a_draw1_test"] + [0.0] * (v["n_tests"] - v["identical_to_a_draw1_test"])
                     for pid, v in per.items() if v["n_tests"]})
        out["identity"] = ident
    if LEDGER.exists():
        out["ledger"] = json.loads(LEDGER.read_text(encoding="utf-8"))
    NUMBERS.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for rule in RULES:
        p = out["rules"][rule]["primary"]
        b = p["wrong_among_kept"]
        print(f"{rule:7s} wrong among kept {b['k']:3d}/{b['n']:3d} ({_pct(b)})   "
              f"retained {p['retained']}/{p['retained_of']}   "
              f"{'KILL' if p['killed'] else 'PASS'}")
    print(f"\nH17: {out['decision']['H17']}   best rule {best}")
    for k in DRAWS:
        d = out[f"draw{k}"]
        print(f"draw {k}: wrong {d['unique_wrong']}/{d['unique_classifiable']} "
              f"({100 * d['rate']:.1f}%), ${d['cost_usd_adapter_sum']:.3f} adapter sum")
    return 0


def _pct(block: dict) -> str:
    if block["rate"] is None:
        return "n/a"
    lo, hi = block["wilson"]
    blo, bhi = block["bootstrap_problem_cluster"]
    return (f"{100 * block['rate']:.1f}% W {100 * lo:.1f}–{100 * hi:.1f}"
            + (f" B {100 * blo:.1f}–{100 * bhi:.1f}" if blo is not None else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--run", required=True, help="run dir: inputs/{solutions-*.jsonl, generated_tests.json}; draws cached here")
    r.add_argument("--scratch", default="/tmp/testgen-val")
    r.add_argument("--budget-usd", type=float, default=5.0)
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--max-passes", type=int, default=4)
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("report")
    i = sub.add_parser("identity")
    i.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    return {"run": run, "report": report, "identity": identity}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
