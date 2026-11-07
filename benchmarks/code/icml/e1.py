"""ICML study E1/E2 — does what the specification determines move the auditor's ceiling?

Preregistration: ``icml/PREREGISTRATION-E1.md`` (committed before the first audit call).

Stages, each resumable and cached as JSONL under ``records/icml/``:

    generate   two generators x every HumanEval+/MBPP+ problem x 3 samples
    oracle     validate every hidden and visible suite: the reference passes, two wrong implementations fail
    execute    visible and hidden suites per sample; first failing hidden input with both outputs
    select     freeze one defective and one test-passing sample per (problem, generator); frozen split
    construct  a missing requirement (clause) with typed behavioural cases, a pointer and a placebo, written
               without seeing the defective candidate and validated by execution (amendment 2)
    adjudicate two vendors, blind to the candidates, check correspondence, novelty, non-contradiction,
               leakage, pointer non-resolution and placebo neutrality; both must admit (amendment 2)
    audit      arms {orig, clause, placebo, pointer} x auditors x readings, one persisted randomised schedule
    witness    execute auditor witnesses against the reference
    analyse    unions, H1-H4, E2 curves

Isolation. Codex routes run with their own CODEX_HOME holding only the login, with user config, rules and
session persistence disabled, from an empty working directory, and with --json so that any tool call is
visible; a reading that used a tool is discarded and retried once. Claude routes run with every tool
disabled and no session persistence. Neither CLI exposes a temperature.

Ground truth (amendment 2). Hidden suites run with their own assertion call, including any task-specific
tolerance; construction cases and witnesses are compared with the suite's own ``assertion`` function in one
executor process per call, with PYTHONHASHSEED fixed and arguments deserialised afresh for each program.
"""
from __future__ import annotations

import argparse
import ast
import math
import base64
import hashlib
import itertools
import json
import os
import pickle
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE.parent / "expertlongbench"))

import execute  # noqa: E402
import generate as gen_mod  # noqa: E402  (the original study's generation prompts, unchanged)
from corpus import Problem, load_problems  # noqa: E402

PROTOCOL = "e1-v3"
REC = CODE / "records" / "icml"
REC.mkdir(parents=True, exist_ok=True)
ISO_ROOT = CODE.parents[2] / ".codex_iso"          # outside the repository
EMPTY = Path(tempfile.gettempdir()) / "icml_e1_empty"
EMPTY.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------------------------
CLAUDE = ["claude", "-p", "--tools", "", "--setting-sources", "", "--strict-mcp-config",
          "--disable-slash-commands", "--no-session-persistence",
          "--system-prompt", "Answer the user's request."]


def codex(model: str, effort: str) -> list[str]:
    return ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--json",
            "-m", model, "-c", f'model_reasoning_effort="{effort}"', "--sandbox", "read-only",
            "--skip-git-repo-check", "-C", str(EMPTY), "-"]


ROUTES = {
    "gen-claude-haiku45": ("claude", CLAUDE + ["--model", "claude-haiku-4-5"]),
    "gen-gpt-terra": ("codex", codex("gpt-5.6-terra", "low")),
    "con-gpt-astra": ("codex", codex("gpt-6-astra", "high")),
    "adj-claude-opus": ("claude", CLAUDE + ["--model", "claude-opus-5-5"]),
    "adj-gpt-sol": ("codex", codex("gpt-6.1-sol", "high")),
    "aud-gpt-terra": ("codex", codex("gpt-5.6-terra", "medium")),
    "aud-claude-sonnet": ("claude", CLAUDE + ["--model", "claude-sonnet-5-5"]),
    "aud-gpt-sol": ("codex", codex("gpt-6.1-sol", "medium")),
    "aud-claude-opus": ("claude", CLAUDE + ["--model", "claude-opus-5-5"]),
}
GENERATORS = ["gen-claude-haiku45", "gen-gpt-terra"]
PRIMARY_AUDITORS = ["aud-gpt-terra", "aud-claude-sonnet"]
ADJUDICATORS = ["adj-claude-opus", "adj-gpt-sol"]
NON_MESSAGE_ITEMS = {"command_execution", "mcp_tool_call", "web_search", "file_change", "patch_apply",
                     "tool_call", "function_call"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iso_home(route: str) -> str:
    home = ISO_ROOT / route
    if not (home / "auth.json").exists():
        home.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path.home() / ".codex" / "auth.json", home / "auth.json")
    return str(home)


def call(route: str, payload: str, timeout: float = 900.0) -> dict:
    kind, argv = ROUTES[route]
    env = dict(os.environ)
    if kind == "codex":
        env["CODEX_HOME"] = iso_home(route)
    started = time.monotonic()
    try:
        done = subprocess.run(argv, input=payload, cwd=str(EMPTY), capture_output=True, text=True,
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "wall_s": round(time.monotonic() - started, 1),
                "text": "", "raw": "", "tool_used": False}
    wall = round(time.monotonic() - started, 1)
    raw = done.stdout or ""
    text, tool_used, usage = raw, False, None
    if kind == "codex":
        messages = []
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") or {}
            if item.get("type") in NON_MESSAGE_ITEMS:
                tool_used = True
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
        text = messages[-1] if messages else ""
    ok = done.returncode == 0 and bool(text.strip()) and not tool_used
    out = {"ok": ok, "wall_s": wall, "text": text, "raw": raw, "tool_used": tool_used, "usage": usage}
    if not ok:
        out["error"] = ("tool used" if tool_used else
                        f"exit {done.returncode}: {(done.stderr or '')[-200:]}")
    return out


_lock = threading.Lock()


def append(path: Path, row: dict) -> None:
    with _lock, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def run_pool(jobs, fn, workers: int, label: str) -> None:
    total, done = len(jobs), 0
    if not total:
        print(f"{label}: nothing to do", flush=True)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn, job) for job in jobs]
        for future in as_completed(futures):
            done += 1
            future.result()
            if done % 25 == 0 or done == total:
                print(f"{label}: {done}/{total}", flush=True)


def imports_of(p: Problem) -> str:
    return "\n".join(p._test_imports) if p.benchmark == "mbpp" else ""


# ---------------------------------------------------------------------------------------------
# sandboxed calls on materialised arguments, judged with the suite's own assertion
# ---------------------------------------------------------------------------------------------
EXEC_ENV = {**os.environ, "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1"}
JUDGE = r'''
import pickle, sys, base64, signal, json
sys.setrecursionlimit(10000)
spec = json.loads(open(sys.argv[1]).read())
blob = base64.b64decode(spec["blob"].encode())

class _Late(BaseException):
    pass

def _alarm(*_):
    raise _Late()

signal.signal(signal.SIGALRM, _alarm)
helpers = {}
exec(compile(spec["helpers"], "suite_helpers", "exec"), helpers)

def run(src):
    ns = {}
    try:
        exec(compile(src, "solution", "exec"), ns)
        fn = ns[spec["entry"]]
    except BaseException as e:
        return "load", None, type(e).__name__
    args, kwargs = pickle.loads(blob)
    signal.alarm(spec["limit"])
    try:
        value = fn(*args, **kwargs)
        signal.alarm(0)
        return "ok", value, repr(value)[:2000]
    except _Late:
        return "timeout", None, "timeout"
    except BaseException as e:
        signal.alarm(0)
        return "exc", None, type(e).__name__

def agrees(out, exp):
    """The suite's own assertion, bounded in time. Any exception is a rejection, as in the suite; the kind is kept."""
    signal.alarm(spec["limit"])
    try:
        helpers["assertion"](out, exp, spec["atol"])
        signal.alarm(0)
        return True, None
    except _Late:
        return False, "comparator_timeout"
    except AssertionError:
        signal.alarm(0)
        return False, None
    except BaseException as e:
        signal.alarm(0)
        return False, type(e).__name__

res = {}
rs, rv, rr = run(spec["reference"])
res["reference"] = {"status": rs, "repr": rr}
if rs == "ok":
    # a comparator that cannot accept the reference against itself cannot score this call (judge-v3.2)
    self_ok, self_err = agrees(pickle.loads(pickle.dumps(rv)), rv)
    res["comparator_ok"] = self_ok
    res["comparator_error"] = self_err
if spec.get("candidate") is not None:
    cs, cv, cr = run(spec["candidate"])
    res["candidate"] = {"status": cs, "repr": cr}
    if rs == "ok" and cs == "ok":
        res["agree"], res["agree_error"] = agrees(cv, rv)
if spec.get("has_expected") and rs == "ok":
    res["expected_correct"], res["expected_error"] = agrees(pickle.loads(base64.b64decode(spec["expected"].encode())), rv)
with open(spec["out"], "w") as fh:          # framed by a file, not by a marker in stdout (judge-v3.2)
    fh.write(json.dumps(res))
'''
_ASSERT_CALL = re.compile(r"^\s*assertion\((?P<body>.*)\)\s*$", re.M)


def suite_assertion(p: Problem) -> tuple[str, str]:
    """(helpers source, tolerance source) of the problem's own hidden suite."""
    code = p._hidden_test
    cut = code.find("def check(candidate):") if p.benchmark == "humaneval" else code.find("inputs =")
    helpers = ("import math\n" + imports_of(p) + "\n" + code[:cut]) if cut > 0 else ""
    calls = _ASSERT_CALL.findall(code)
    atol = calls[-1].rsplit(",", 1)[1].strip() if calls else "0"
    return helpers, atol


def judge_call(p: Problem, args: tuple, kwargs: dict, candidate: str | None = None,
               expected=None, limit: int = 10, has_expected: bool = False) -> dict:
    """Run the reference (and a candidate) on freshly unpickled copies of the same arguments in one executor
    process, and compare outputs with the suite's own assertion and tolerance."""
    helpers, atol = suite_assertion(p)
    spec = {"helpers": helpers, "atol": float(ast.literal_eval(atol)), "entry": p.entry_point, "limit": limit,
            "blob": base64.b64encode(pickle.dumps((tuple(args), dict(kwargs)))).decode(),
            "reference": imports_of(p) + "\n" + p.canonical_solution,
            "candidate": None if candidate is None else imports_of(p) + "\n" + candidate,
            "has_expected": has_expected,   # an expected value of None is a legitimate value, not "absent"
            "expected": base64.b64encode(pickle.dumps(expected)).decode() if has_expected else None}
    with tempfile.TemporaryDirectory() as tmp:
        spec["out"] = str(Path(tmp) / "result.json")
        (Path(tmp) / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        (Path(tmp) / "judge.py").write_text(JUDGE, encoding="utf-8")
        try:
            done = subprocess.run([execute.EXECUTOR, str(Path(tmp) / "judge.py"), str(Path(tmp) / "spec.json")],
                                  capture_output=True, text=True, timeout=6 * limit + 30, cwd=tmp, env=EXEC_ENV)
        except subprocess.TimeoutExpired:
            return {"infra": "timeout"}
        try:
            return json.loads((Path(tmp) / "result.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"infra": (done.stderr or "")[-300:] or "no result"}


def hidden_program_v3(p: Problem, solution: str) -> tuple[str, bool]:
    """The hidden suite with its own assertion call (task-specific tolerance kept), collecting every failure."""
    calls = _ASSERT_CALL.findall(p._hidden_test)
    if not calls:
        return p.hidden_program(solution)
    call_src = "assertion(" + calls[-1].strip() + ")"
    body, inst = execute.instrument_plus_suite(p._hidden_test, call_src)
    if p.benchmark == "humaneval":
        return f"{solution}\n\n{body}\n\ncheck({p.entry_point})\n", inst
    return f"{solution}\n\n{body}\n", inst


class _NonFinite(ast.NodeTransformer):
    """float('inf'), float('-inf'), float('nan'), math.inf, math.nan, inf and nan become constants."""
    NAMES = {"inf": math.inf, "nan": math.nan}

    def visit_Call(self, node):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Name) and node.func.id == "float" and len(node.args) == 1 and not node.keywords
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            v = node.args[0].value.strip().lower()
            if v in ("inf", "+inf", "-inf", "infinity", "-infinity", "nan"):
                return ast.copy_location(ast.Constant(float(v)), node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "math" and node.attr in self.NAMES:
            return ast.copy_location(ast.Constant(self.NAMES[node.attr]), node)
        return node

    def visit_Name(self, node):
        return ast.copy_location(ast.Constant(self.NAMES[node.id]), node) if node.id in self.NAMES else node


def literal(src):
    """ast.literal_eval extended with non-finite floats (scorer judge-v3.1)."""
    node = ast.parse(src, mode="eval") if isinstance(src, str) else ast.Expression(body=src)
    node = ast.fix_missing_locations(_NonFinite().visit(node))
    return ast.literal_eval(node.body)


def parse_call(src: str, entry: str) -> tuple[tuple, dict] | None:
    """A witness call must be entry(<literals>, name=<literal>); anything else is unparseable."""
    try:
        node = ast.parse(src.strip(), mode="eval").body
    except SyntaxError:
        return None
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == entry):
        return None
    try:
        args = tuple(literal(a) for a in node.args)
        kwargs = {k.arg: literal(k.value) for k in node.keywords if k.arg}
    except (ValueError, SyntaxError, TypeError):
        return None
    if any(k.arg is None for k in node.keywords):
        return None
    return args, kwargs


# ---------------------------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------------------------
SAMPLES = 6                          # amendment 1: six samples per problem and generator (was three)
GEN_PATH = REC / "generations.jsonl"


def stage_generate(workers: int, attempts: int = 2) -> None:
    problems = load_problems()
    rows = load(GEN_PATH)
    have = {(r["generator"], r["problem_id"], r["sample"]) for r in rows if r.get("ok")}
    tries: dict = {}
    for r in rows:
        k = (r["generator"], r["problem_id"], r["sample"])
        tries[k] = tries.get(k, 0) + 1
    jobs = [(g, p, s) for g in GENERATORS for p in problems for s in range(SAMPLES)
            if (g, p.problem_id, s) not in have and tries.get((g, p.problem_id, s), 0) < attempts]
    random.Random(1).shuffle(jobs)

    def one(job):
        g, p, s = job
        payload = gen_mod.SYSTEM + "\n\n" + gen_mod.user_prompt(p)
        res = call(g, payload, timeout=300)
        row = {"generator": g, "problem_id": p.problem_id, "sample": s, "ok": res["ok"],
               "wall_s": res["wall_s"], "prompt_sha256": sha(payload), "tool_used": res["tool_used"],
               "protocol": PROTOCOL}
        if res["ok"]:
            row["solution"] = gen_mod.extract_code(res["text"])
        else:
            row["error"] = res.get("error", "")
        append(GEN_PATH, row)
    run_pool(jobs, one, workers, "generate")


# ---------------------------------------------------------------------------------------------
# oracle validation
# ---------------------------------------------------------------------------------------------
ORACLE_PATH = REC / "oracles_v3.json"
WRONG = {"returns_none": "def {e}(*args, **kwargs):\n    return None\n",
         "raises": "def {e}(*args, **kwargs):\n    raise ValueError('wrong')\n"}


def stage_oracle(workers: int) -> None:
    problems = load_problems()
    result: dict = {}

    def one(p: Problem):
        vis = execute.run_suite(p.visible_program(p.canonical_solution), instrumented=p.visible_instrumented)
        hid_prog, inst = hidden_program_v3(p, p.canonical_solution)
        hid = execute.run_suite(hid_prog, instrumented=inst)
        wrong = {}
        for name, tmpl in WRONG.items():
            sol = imports_of(p) + "\n" + tmpl.format(e=p.entry_point)
            prog, inst2 = hidden_program_v3(p, sol)
            wrong[name] = execute.run_suite(prog, instrumented=inst2).passed
        valid = vis.passed and hid.passed and not any(wrong.values())
        with _lock:
            result[p.problem_id] = {"valid": valid, "reference_visible": vis.passed,
                                    "reference_hidden": hid.passed, "wrong_passes_hidden": wrong,
                                    "hidden_mode": hid.mode}
    run_pool(problems, one, workers, "oracle")
    ORACLE_PATH.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    bad = sorted(k for k, v in result.items() if not v["valid"])
    print(f"oracles: {len(result) - len(bad)} valid, {len(bad)} invalid: {bad[:20]}")


# ---------------------------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------------------------
EXEC_PATH = REC / "executions_v3.jsonl"


def hidden_inputs(problem: Problem):
    code = problem._hidden_test
    cut = code.find("for i, (inp, exp) in enumerate(zip(inputs, results)):")
    if cut < 0:
        return None
    preamble = code[:cut]
    if problem.benchmark == "humaneval":
        preamble = preamble.replace("def check(candidate):", "if True:")
    prog = ("import math\n" + imports_of(problem) + "\n" + preamble +
            "\nimport pickle,sys,base64\nsys.stdout.write(base64.b64encode(pickle.dumps(inputs)).decode())\n")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "inp.py"
        path.write_text(prog, encoding="utf-8")
        done = subprocess.run([execute.EXECUTOR, str(path)], capture_output=True, text=True, timeout=120, env=EXEC_ENV)
    if done.returncode != 0:
        return None
    return pickle.loads(base64.b64decode(done.stdout))


def stage_execute(workers: int) -> None:
    problems = {p.problem_id: p for p in load_problems()}
    have = {(r["generator"], r["problem_id"], r["sample"], r["solution_sha256"]) for r in load(EXEC_PATH)}
    gens = [r for r in load(GEN_PATH) if r.get("ok")]
    jobs = [r for r in gens if (r["generator"], r["problem_id"], r["sample"], sha(r["solution"])) not in have]
    inp_cache: dict = {}

    def one(r):
        p = problems[r["problem_id"]]
        sol = r["solution"]
        vr = execute.run_suite(p.visible_program(sol), instrumented=p.visible_instrumented)
        prog, inst = hidden_program_v3(p, sol)
        hr = execute.run_suite(prog, instrumented=inst)
        row = {"generator": r["generator"], "problem_id": r["problem_id"], "sample": r["sample"],
               "solution_sha256": sha(sol), "visible_passed": vr.passed, "hidden_passed": hr.passed,
               "hidden_mode": hr.mode, "hidden_failed": hr.failed_indices[:5], "hidden_total": hr.total}
        if vr.passed and not hr.passed and hr.failed_indices:
            with _lock:
                if p.problem_id not in inp_cache:
                    inp_cache[p.problem_id] = hidden_inputs(p)
            inputs = inp_cache[p.problem_id]
            if inputs is not None:
                idx = hr.failed_indices[0]
                args = tuple(inputs[idx])
                j = judge_call(p, args, {}, candidate=sol)
                row["first_fail"] = {"index": idx, "args_repr": repr(args)[:4000],
                                     "args_b64": base64.b64encode(pickle.dumps(args)).decode(),
                                     "reference": j.get("reference", {"status": "infra"}),
                                     "candidate": j.get("candidate", {"status": "infra"}),
                                     "agree": j.get("agree")}
        append(EXEC_PATH, row)
    run_pool(jobs, one, workers, "execute")


# ---------------------------------------------------------------------------------------------
# select (frozen)
# ---------------------------------------------------------------------------------------------
SPLIT_PATH = REC / "split.json"
ITEMS_PATH = REC / "items_v3.json"
SPLIT_SEED = 20261109
DEV_FRACTION = 0.25


def frozen_split() -> dict:
    if SPLIT_PATH.exists():
        return json.loads(SPLIT_PATH.read_text())
    ids = sorted(p.problem_id for p in load_problems())
    rng = random.Random(SPLIT_SEED)
    dev = set(rng.sample(ids, round(DEV_FRACTION * len(ids))))
    split = {pid: ("dev" if pid in dev else "test") for pid in ids}
    SPLIT_PATH.write_text(json.dumps(split, indent=1, sort_keys=True), encoding="utf-8")
    return split


def stage_select(force: bool = False) -> None:
    if ITEMS_PATH.exists() and not force:
        raise SystemExit("items.json is frozen; refusing to reselect (use --force before any audit)")
    split = frozen_split()
    oracles = json.loads(ORACLE_PATH.read_text())
    gens = {(r["generator"], r["problem_id"], r["sample"]): r for r in load(GEN_PATH) if r.get("ok")}
    attempted = {}
    for r in load(GEN_PATH):
        attempted.setdefault((r["generator"], r["problem_id"], r["sample"]), []).append(r.get("ok"))
    incomplete = [k for k in itertools.product(GENERATORS, split, range(SAMPLES))
                  if k not in gens and len(attempted.get(k, [])) < 2]
    if incomplete:
        raise SystemExit(f"generation incomplete: {len(incomplete)} samples neither generated nor exhausted")
    execs = {(e["generator"], e["problem_id"], e["sample"]): e for e in load(EXEC_PATH)}
    problems_by_id = {p.problem_id: p for p in load_problems()}
    funnel = {"pairs": 0, "invalid_oracle": 0, "no_defect": 0, "no_correct": 0, "items": 0}
    items = []
    for g in GENERATORS:
        for pid in sorted(split):
            funnel["pairs"] += 1
            if not oracles.get(pid, {}).get("valid"):
                funnel["invalid_oracle"] += 1
                continue
            rows = [execs[(g, pid, s)] for s in range(SAMPLES) if (g, pid, s) in execs]
            defect = next((e for e in rows if e["visible_passed"] and not e["hidden_passed"]
                           and e.get("first_fail", {}).get("reference", {}).get("status") == "ok"
                           and e["first_fail"].get("agree") is not True), None)
            if not defect:
                funnel["no_defect"] += 1
                continue
            # amendment 1: the test-passing control is the same generator's first passing sample, else the
            # other generator's, else the reference solution (recorded, and excluded in a sensitivity analysis)
            other = [x for x in GENERATORS if x != g][0]
            correct, source = next((e for e in rows if e["visible_passed"] and e["hidden_passed"]), None), "same"
            if correct is None:
                orows = [execs[(other, pid, s)] for s in range(SAMPLES) if (other, pid, s) in execs]
                correct, source = next((e for e in orows if e["visible_passed"] and e["hidden_passed"]), None), "other"
            if correct is None:
                source = "reference"
                funnel["no_correct"] += 1
            funnel["items"] += 1
            if source == "reference":
                ctrl_sol = problems_by_id[pid].canonical_solution
            else:
                ctrl_sol = gens[(correct["generator"], pid, correct["sample"])]["solution"]
            items.append({"item_id": f"{g}|{pid}", "generator": g, "problem_id": pid, "split": split[pid],
                          "defective_sample": defect["sample"], "control_source": source,
                          "correct_sample": None if correct is None else [correct["generator"], correct["sample"]],
                          "first_fail": defect["first_fail"],
                          "defective_solution": gens[(g, pid, defect["sample"])]["solution"],
                          "correct_solution": ctrl_sol})
    ITEMS_PATH.write_text(json.dumps(items, indent=1), encoding="utf-8")
    (REC / "funnel_select_v3.json").write_text(json.dumps(funnel, indent=1))
    print(json.dumps(funnel), {s: sum(i["split"] == s for i in items) for s in ("dev", "test")})


# ---------------------------------------------------------------------------------------------
# construct
# ---------------------------------------------------------------------------------------------
CON_PATH = REC / "constructions_v3.jsonl"
CON_PROMPT = """You are helping build a controlled experiment on code review.

Below is a programming task as given to a programmer, its visible tests, a REFERENCE solution that is
correct, and one input on which a plausible solution that passes the visible tests returned something other
than the reference's output. You are not shown that solution.

Decide first whether the task's own words leave the reference's behaviour on inputs like this one open, so
that a careful reader could reasonably implement either the reference's behaviour or a different one. If the
task's words already determine the behaviour, or if the reference's behaviour on such inputs contradicts the
task's words or looks like an arbitrary implementation quirk that no task author would intend, reply with
{{"skip": "one sentence"}} and nothing else.

Otherwise write:

1. CLAUSE: one sentence, at most 40 words, stating the general requirement that the task leaves open and
   that the reference satisfies. It must read like an ordinary line a task author could have written, be
   consistent with every word of the task and the visible tests, state required behaviour (not an
   implementation technique), and must NOT mention any specific input or output value, tests or solutions.
2. POINTER: one sentence of about the same length that draws attention to the same kind of input as the
   CLAUSE (for example "Inputs may contain ...") but does not state or imply what the correct output is for
   such inputs, so that adding it does not change which outputs are correct.
3. PLACEBO: one sentence of about the same length that reads like an ordinary line of a task description,
   does not change which outputs are correct for any input (for example, restating a property every
   solution already has), and says nothing related to the kind of input the CLAUSE concerns.
4. CASES: between 4 and 8 calls of the function that exercise the CLAUSE, each written as a Python literal
   tuple of the positional arguments, with the exact argument types the task uses (a tuple where the task
   passes a tuple; a one-argument call is written "(x,)"). Use valid inputs for the task. Include calls on
   which the CLAUSE leads to different outputs (both sides of any condition it states). Do not reuse the
   input shown below. The expected outputs will be computed from the reference, so do not give them.

Reply with exactly one JSON object:
{{"clause": "...", "pointer": "...", "placebo": "...", "cases": ["(...)", "(...)", ...]}}

TASK:
{spec}

VISIBLE TESTS:
{visible}

REFERENCE:
```python
{reference}
```

INPUT (positional arguments): {args}
REFERENCE OUTPUT ON IT: {ref_out}
"""


def parse_json(text: str) -> dict | None:
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    for chunk in blocks[::-1] + [text]:
        s, e = chunk.find("{"), chunk.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(chunk[s:e + 1])
            except json.JSONDecodeError:
                continue
    return None


def literal_tokens(item: dict) -> list[str]:
    ff = item["first_fail"]
    toks = []
    for text in (ff["reference"].get("repr", ""), ff["candidate"].get("repr", ""), ff["args_repr"]):
        toks += re.findall(r"-?\d+(?:\.\d+)?|'[^']{2,}'|\"[^\"]{2,}\"", text)
    out = []
    for t in toks:
        t = t.strip("'\"")
        if len(t) >= 2 and t not in ("10", "00"):
            out.append(t)
    return out


def leaks(sentence: str, item: dict) -> bool:
    low = sentence.lower()
    return any(re.search(r"(?<![\w.])" + re.escape(t.lower()) + r"(?![\w.])", low) for t in literal_tokens(item))


def type_sig(x, depth: int = 2):
    t = type(x).__name__
    t = "num" if t in ("int", "float") else t
    if depth and isinstance(x, (list, tuple, set, frozenset)) and x:
        return (t, type_sig(next(iter(x)), depth - 1))
    if depth and isinstance(x, dict) and x:
        k, v = next(iter(x.items()))
        return (t, type_sig(k, depth - 1), type_sig(v, depth - 1))
    return (t,)


_domain_cache: dict = {}


def domain_of(p: Problem):
    """Per-arity, per-position type signatures of the hidden suite's inputs (None if not recoverable)."""
    with _lock:
        if p.problem_id in _domain_cache:
            return _domain_cache[p.problem_id]
    inputs = hidden_inputs(p)
    dom = None
    if inputs:
        dom = {}
        for inp in inputs:
            inp = tuple(inp)
            for i, x in enumerate(inp):
                dom.setdefault(len(inp), [set() for _ in inp])[i].add(type_sig(x))
    with _lock:
        _domain_cache[p.problem_id] = dom
    return dom


def in_domain(args: tuple, dom) -> bool:
    if dom is None:
        return True
    if len(args) not in dom:
        return False
    for x, allowed in zip(args, dom[len(args)]):
        sg = type_sig(x)
        if sg not in allowed and not (len(sg) == 1 and any(a[0] == sg[0] for a in allowed)):
            return False
    return True


def validate_cases(cases, p: Problem, item: dict) -> tuple[list, list[str]]:
    """Typed cases: parsed as Python literals, inside the suite's input types, run on the reference, the
    test-passing control and the defective candidate, compared with the suite's own assertion."""
    reasons, evaluated = [], []
    if not isinstance(cases, list) or not 4 <= len(cases) <= 8:
        return [], ["cases: need 4-8"]
    failing = pickle.loads(base64.b64decode(item["first_fail"]["args_b64"]))
    dom = domain_of(p)
    separates, outcomes = False, set()
    for c in cases:
        try:
            args = ast.literal_eval(c) if isinstance(c, str) else None
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            args = None
        if not isinstance(args, tuple):
            reasons.append("case is not a Python literal tuple")
            continue
        if repr(args) == repr(tuple(failing)):
            reasons.append("case reuses the failing input")
            continue
        if not in_domain(args, dom):
            reasons.append("case outside the suite's input types")
            continue
        cor = judge_call(p, args, {}, candidate=item["correct_solution"])
        dfc = judge_call(p, args, {}, candidate=item["defective_solution"])
        if "infra" in cor or "infra" in dfc:
            reasons.append("infrastructure failure on a case")
            continue
        if cor["reference"]["status"] != "ok":
            reasons.append(f"reference does not run on a case ({cor['reference']['status']})")
            continue
        if cor.get("agree") is not True:
            reasons.append("test-passing control disagrees with the reference on a case")
        if dfc.get("agree") is not True:
            separates = True
        outcomes.add(cor["reference"]["repr"])
        evaluated.append({"args_repr": repr(args)[:1000], "reference_repr": cor["reference"]["repr"][:500],
                          "defective_repr": dfc["candidate"]["repr"][:500], "defective_agrees": dfc.get("agree")})
    if not separates:
        reasons.append("no case separates the defective candidate from the reference")
    if len(outcomes) < 2:
        reasons.append("cases do not show two different reference outputs")
    return evaluated, reasons


def stage_construct(workers: int, attempts: int = 3) -> None:
    problems = {p.problem_id: p for p in load_problems()}
    items = json.loads(ITEMS_PATH.read_text())
    done = {r["item_id"] for r in load(CON_PATH) if r.get("admitted_by_execution") or r.get("final")}
    jobs = [i for i in items if i["item_id"] not in done]

    def one(item):
        p = problems[item["problem_id"]]
        ff = item["first_fail"]
        payload = CON_PROMPT.format(spec=p.spec.rstrip(), visible=p.visible_tests_text(),
                                    reference=p.canonical_solution, args=ff["args_repr"][:1500],
                                    ref_out=ff["reference"]["repr"][:800])
        log = []
        for attempt in range(attempts):
            res = call("con-gpt-astra", payload, timeout=900)
            obj = parse_json(res["text"]) if res["ok"] else None
            if obj and "skip" in obj and "clause" not in obj:
                append(CON_PATH, {"item_id": item["item_id"], "final": True, "admitted_by_execution": False,
                                  "skipped": str(obj["skip"])[:500], "attempt": attempt,
                                  "prompt_sha256": sha(payload), "protocol": PROTOCOL})
                return
            if not obj or not all(k in obj for k in ("clause", "pointer", "placebo", "cases")):
                log.append({"attempt": attempt, "reasons": ["unparseable or call failed"],
                            "error": res.get("error", "")})
                continue
            evaluated, reasons = validate_cases(obj["cases"], p, item)
            wc = len(obj["clause"].split())
            wr, wp = len(obj["pointer"].split()), len(obj["placebo"].split())
            if wc > 40:
                reasons.append("clause too long")
            if not (0.6 * wc <= wp <= 1.5 * wc):
                reasons.append("placebo length unmatched")
            if not (0.6 * wc <= wr <= 1.5 * wc):
                reasons.append("pointer length unmatched")
            for name in ("clause", "pointer", "placebo"):
                if leaks(obj[name], item):
                    reasons.append(f"{name} contains a failing-case literal")
            row = {"item_id": item["item_id"], "attempt": attempt, "clause": obj["clause"],
                   "pointer": obj["pointer"], "placebo": obj["placebo"], "cases": evaluated,
                   "clause_words": wc, "pointer_words": wr, "placebo_words": wp, "reasons": reasons,
                   "admitted_by_execution": not reasons, "prompt_sha256": sha(payload),
                   "raw": res["text"][:6000], "protocol": PROTOCOL}
            append(CON_PATH, row)
            if not reasons:
                return
            log.append({"attempt": attempt, "reasons": reasons})
        append(CON_PATH, {"item_id": item["item_id"], "final": True, "admitted_by_execution": False,
                          "log": log, "protocol": PROTOCOL})
    run_pool(jobs, one, workers, "construct")


# ---------------------------------------------------------------------------------------------
# adjudicate (second vendor, blind to which solution is which)
# ---------------------------------------------------------------------------------------------
ADJ_PATH = REC / "adjudications_v3.jsonl"
ADJ_PROMPT = """You are checking materials for a controlled experiment. Answer strictly; when in doubt, answer
in the direction that rejects the materials.

TASK (as given to a programmer):
{spec}

VISIBLE TESTS:
{visible}

PROPOSED ADDITIONAL REQUIREMENT (A): {clause}

CALLS ILLUSTRATING (A), with the outputs a correct solution returns:
{cases}

PROPOSED POINTER SENTENCE (R): {pointer}

PROPOSED NEUTRAL SENTENCE (B): {placebo}

Answer each question true or false:
q1: Does (A) correctly describe what the illustrated outputs show, so that a solution satisfying (A) and
    the task would return exactly these outputs?
q2: Is the behaviour (A) requires already determined by the TASK's words and the VISIBLE TESTS, so that a
    careful reader would implement it without (A)? (Agreement with the visible tests is not enough to answer
    false: answer false only if the task's words genuinely permit a different behaviour.)
q3: Does (A) contradict any word of the TASK or any VISIBLE TEST, or change what the task asks for?
q4: Does (A) reveal a specific test input or output value, or prescribe an implementation technique rather
    than behaviour?
q5: Could a reasonable author of this task have intended (A), rather than (A) codifying an arbitrary quirk
    with no basis in the task's words?
q6: Would adding (B) to the task change which outputs are correct for any valid input?
q7: Does (B) relate to the behaviour that (A) describes, or hint at it?
q8: Does (R) concern the same kind of input as (A)?
q9: Does (R) state or imply which output is correct for those inputs, or otherwise narrow which behaviour is
    correct?

Reply with exactly one JSON object: {{"q1": true|false, "q2": ..., "q3": ..., "q4": ..., "q5": ..., "q6": ...,
"q7": ..., "q8": ..., "q9": ..., "permits_both": "one sentence: which two behaviours the TASK's words permit
on such inputs, or why it does not", "note": "one sentence"}}
"""
ADJ_PASS = {"q1": True, "q2": False, "q3": False, "q4": False, "q5": True, "q6": False, "q7": False,
            "q8": True, "q9": False}


def stage_adjudicate(workers: int) -> None:
    """Two vendors, each blind to the candidates and to every audit; an item is admitted only if both admit."""
    problems = {p.problem_id: p for p in load_problems()}
    items = {i["item_id"]: i for i in json.loads(ITEMS_PATH.read_text())}
    cons = {r["item_id"]: r for r in load(CON_PATH) if r.get("admitted_by_execution")}
    have = {(r["item_id"], r["adjudicator"]) for r in load(ADJ_PATH) if r.get("ok")}
    jobs = [(c, a) for iid, c in cons.items() for a in ADJUDICATORS if (iid, a) not in have]

    def one(job):
        con, adj = job
        item = items[con["item_id"]]
        p = problems[item["problem_id"]]
        cases = "\n".join(f"  {p.entry_point}(*{c['args_repr']}) -> {c['reference_repr']}" for c in con["cases"])
        payload = ADJ_PROMPT.format(spec=p.spec.rstrip(), visible=p.visible_tests_text(), clause=con["clause"],
                                    cases=cases, pointer=con["pointer"], placebo=con["placebo"])
        for attempt in range(2):
            res = call(adj, payload, timeout=900)
            obj = parse_json(res["text"]) if res["ok"] else None
            if obj and all(k in obj for k in ADJ_PASS):
                admitted = all(obj[k] is v for k, v in ADJ_PASS.items())
                append(ADJ_PATH, {"item_id": con["item_id"], "adjudicator": adj, "ok": True, "answers": obj,
                                  "admitted": admitted, "prompt_sha256": sha(payload), "protocol": PROTOCOL})
                return
        append(ADJ_PATH, {"item_id": con["item_id"], "adjudicator": adj, "ok": False, "admitted": False,
                          "protocol": PROTOCOL})
    run_pool(jobs, one, workers, "adjudicate")


def admitted_constructions() -> dict:
    cons = {r["item_id"]: r for r in load(CON_PATH) if r.get("admitted_by_execution")}
    votes: dict = {}
    for r in load(ADJ_PATH):
        if r.get("ok"):
            votes.setdefault(r["item_id"], {})[r["adjudicator"]] = r["admitted"]
    return {iid: c for iid, c in cons.items()
            if all(votes.get(iid, {}).get(a) is True for a in ADJUDICATORS)}


# ---------------------------------------------------------------------------------------------
# taxonomy (amendment 3): what the task's words say about the first failing input, for every selected item
# ---------------------------------------------------------------------------------------------
TAX_PATH = REC / "taxonomy_v3.jsonl"
TAX_PROMPT = """You are classifying items for a study of code review. Answer strictly from the task's words.

TASK (as given to a programmer):
{spec}

VISIBLE TESTS:
{visible}

On the input below, the benchmark's reference solution and a submitted program return different values.

INPUT (positional arguments): {args}
REFERENCE OUTPUT: {ref_out}
SUBMITTED PROGRAM'S OUTPUT: {cand_out}

Classify the item as exactly one of:
DETERMINED   the task's words and visible tests require the reference's output on this input, and the
             submitted program's output violates them;
OPEN         the task's words and visible tests are consistent with both outputs (the task leaves this
             behaviour open);
AT_ODDS      the reference's output is inconsistent with the task's words, or is an arbitrary artefact of
             its implementation (for example floating-point noise or a loop's fall-through value) that the
             task's author would not intend.

Reply with exactly one JSON object: {{"class": "DETERMINED" | "OPEN" | "AT_ODDS", "reason": "one sentence"}}
"""
TAX_CLASSES = ("DETERMINED", "OPEN", "AT_ODDS")


def stage_taxonomy(workers: int) -> None:
    """Both adjudicator routes classify every selected item, blind to every audit and to the program text."""
    problems = {p.problem_id: p for p in load_problems()}
    items = json.loads(ITEMS_PATH.read_text())
    have = {(r["item_id"], r["adjudicator"]) for r in load(TAX_PATH) if r.get("ok")}
    jobs = [(i, a) for i in items for a in ADJUDICATORS if (i["item_id"], a) not in have]

    def one(job):
        item, adj = job
        p = problems[item["problem_id"]]
        ff = item["first_fail"]
        payload = TAX_PROMPT.format(spec=p.spec.rstrip(), visible=p.visible_tests_text(),
                                    args=ff["args_repr"][:1500], ref_out=ff["reference"]["repr"][:800],
                                    cand_out=(ff["candidate"].get("repr") or ff["candidate"].get("status", ""))[:800])
        for attempt in range(2):
            res = call(adj, payload, timeout=900)
            obj = parse_json(res["text"]) if res["ok"] else None
            if obj and obj.get("class") in TAX_CLASSES:
                append(TAX_PATH, {"item_id": item["item_id"], "adjudicator": adj, "ok": True, "class": obj["class"],
                                  "reason": str(obj.get("reason", ""))[:500], "prompt_sha256": sha(payload),
                                  "protocol": PROTOCOL})
                return
        append(TAX_PATH, {"item_id": item["item_id"], "adjudicator": adj, "ok": False, "protocol": PROTOCOL})
    run_pool(jobs, one, workers, "taxonomy")


def taxonomy() -> dict:
    """Item class: the class both adjudicators gave, else DISPUTED."""
    votes: dict = {}
    for r in load(TAX_PATH):
        if r.get("ok"):
            votes.setdefault(r["item_id"], {})[r["adjudicator"]] = r["class"]
    return {iid: (v[ADJUDICATORS[0]] if len(v) == 2 and len(set(v.values())) == 1 else "DISPUTED")
            for iid, v in votes.items()}


# ---------------------------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------------------------
AUD_PATH = REC / "audits_v3.jsonl"
RAW_PATH = REC / "audits_raw_v3.jsonl"
WITNESS_RULE = (
    "\n\n## Evidence for behavioural findings\n\n"
    "When you grade a finding about the program's behaviour as BLOCKER, end its observation with one "
    "line of the form `WITNESS: <call> -> <expected value>`, giving a concrete call of the function, "
    "written as a Python call with literal arguments, on which you believe the program returns the wrong "
    "value, and the value it should return, written as a Python literal.\n")
ARMS = ("orig", "clause", "placebo", "pointer")
READINGS = {"orig": 4, "clause": 2, "placebo": 2, "pointer": 2}
MAX_ATTEMPTS = 2


def task_text(spec: str, arm: str, con: dict) -> str:
    if arm == "orig":
        return spec
    sentence = con[arm]
    return spec.rstrip() + "\n\nAdditional requirement: " + sentence.strip() + "\n"


_cfg: dict = {}


def audit_prompt(problem: Problem, solution: str, task: str) -> str:
    import audit as study1
    from crossaudit.auditor import prompt as prompt_mod
    from crossaudit.config import load as load_cfg
    from crossaudit.dcl import run_checks
    with _lock:
        if "cfg" not in _cfg:
            constitution = study1.shipped_constitution() + WITNESS_RULE
            proj = study1.build_project(REC / "project", "cross", "openai:gpt-5.6-terra",
                                        "anthropic:claude-haiku-4-5", constitution)
            _cfg["cfg"], _cfg["constitution"] = load_cfg(proj / "crossaudit.yml"), constitution
    files = study1.increment_files(problem, solution)
    dcl = run_checks(files, _cfg["cfg"].checks, [], _cfg["cfg"].plugins).as_dict()
    text, _bounded, _digest = prompt_mod.build(_cfg["constitution"], "frozen", dcl, files, task=task)
    return prompt_mod.SYSTEM + "\n\n" + text


_WIT = re.compile(r"WITNESS:\s*`?(.+?)`?\s*->\s*`?(.+?)`?\s*$", re.M)


def schedule(split: str, auditors: list[str], orig_rest: bool = False) -> list[list]:
    """The persisted schedule: every arm for admitted items, or (amendment 3, `orig_rest`) the original arm
    for every selected item that was not admitted."""
    path = REC / (f"schedule_v3_orig_{split}.json" if orig_rest else f"schedule_v3_{split}.json")
    if path.exists():
        return json.loads(path.read_text())
    items = [i for i in json.loads(ITEMS_PATH.read_text()) if i["split"] == split]
    cons = admitted_constructions()
    if orig_rest:
        jobs = [[i["item_id"], kind, "orig", a, k] for i in items if i["item_id"] not in cons
                for kind in ("defective", "correct") for a in auditors for k in range(READINGS["orig"])]
    else:
        jobs = [[i["item_id"], kind, arm, a, k] for i in items if i["item_id"] in cons
                for kind in ("defective", "correct") for arm in ARMS for a in auditors
                for k in range(READINGS[arm])]
    random.Random(7).shuffle(jobs)
    path.write_text(json.dumps(jobs))
    return jobs


def stage_audit(split: str, workers: int, auditors: list[str], orig_rest: bool = False) -> None:
    from crossaudit.auditor.validate import known_rules, parse_reply, validate_reply
    problems = {p.problem_id: p for p in load_problems()}
    items = {i["item_id"]: i for i in json.loads(ITEMS_PATH.read_text())}
    cons = admitted_constructions()
    rows = load(AUD_PATH)
    ok_keys = {(r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"]) for r in rows if r.get("ok")}
    attempts: dict = {}
    for r in rows:
        k = (r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"])
        attempts[k] = attempts.get(k, 0) + 1
    jobs = [tuple(j) for j in schedule(split, auditors, orig_rest)
            if tuple(j) not in ok_keys and attempts.get(tuple(j), 0) < MAX_ATTEMPTS]

    def one(job):
        iid, kind, arm, auditor, k = job
        item = items[iid]
        p = problems[item["problem_id"]]
        payload = audit_prompt(p, item[f"{kind}_solution"], task_text(p.spec, arm, cons.get(iid)))
        res = call(auditor, payload, timeout=900)
        row = {"item_id": iid, "kind": kind, "arm": arm, "auditor": auditor, "reading": k, "split": split,
               "prompt_sha256": sha(payload), "wall_s": res["wall_s"], "tool_used": res["tool_used"],
               "usage": res.get("usage"), "attempt": attempts.get(job, 0) + 1, "protocol": PROTOCOL}
        append(RAW_PATH, {k2: row[k2] for k2 in ("item_id", "kind", "arm", "auditor", "reading", "attempt")}
               | {"text": res["text"], "raw": res.get("raw", ""), "error": res.get("error", "")})
        if not res["ok"]:
            row.update({"ok": False, "error": res.get("error", "")[:200]})
            append(AUD_PATH, row)
            return
        import ceiling
        text, _ = ceiling.astra_extract(res["text"])
        reply, err = parse_reply(text)
        invalid = validate_reply(reply, known_rules(_cfg["constitution"])) if reply is not None else "unparsed"
        if reply is None or invalid:
            row.update({"ok": False, "error": f"invalid reply: {err or invalid}"[:200]})
            append(AUD_PATH, row)
            return
        findings = reply.get("findings") or []
        blockers = [f for f in findings if f.get("severity") == "BLOCKER"]
        witnesses = [{"call": c.strip(), "expected": e.strip()}
                     for f in blockers for c, e in _WIT.findall(f.get("observation", ""))]
        row.update({"ok": True, "flagged": bool(blockers), "any_finding": bool(findings),
                    "n_findings": len(findings), "n_blockers": len(blockers), "witnesses": witnesses[:6],
                    "verdict": reply.get("verdict", "")})
        append(AUD_PATH, row)
    run_pool(jobs, one, workers, f"audit {split}")


# ---------------------------------------------------------------------------------------------
# witnesses
# ---------------------------------------------------------------------------------------------
WIT_PATH = REC / "witnesses_v3.jsonl"
SCORER = "judge-v3.2"   # v3.1: expected None scored, non-finite literals; v3.2: file-framed result, bounded comparator,
                        # comparator self-check, exception kinds kept


def judge_witness(p: Problem, solution: str, call_src: str, expected_src: str) -> dict:
    parsed = parse_call(call_src, p.entry_point)
    if parsed is None:
        return {"status": "unparseable"}
    args, kwargs = parsed
    try:
        expected = literal(expected_src.strip().rstrip("."))
        has_expected = True
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        expected, has_expected = None, False
    j = judge_call(p, args, kwargs, candidate=solution, expected=expected, has_expected=has_expected)
    if "infra" in j:
        return {"status": "infra", "detail": str(j["infra"])[:200]}
    ref, cand = j["reference"], j["candidate"]
    if ref["status"] == "timeout":
        return {"status": "infra", "detail": "reference timeout"}
    if ref["status"] != "ok":
        return {"status": "outside_domain", "reference": ref["status"]}
    if not j.get("comparator_ok", True):
        return {"status": "infra", "detail": f"comparator rejects reference: {j.get('comparator_error')}"}
    if cand["status"] == "timeout":
        return {"status": "candidate_timeout", "expected_parsed": has_expected}
    if j.get("agree_error") == "comparator_timeout" or j.get("expected_error") == "comparator_timeout":
        return {"status": "infra", "detail": "comparator timeout"}
    disagrees = cand["status"] != "ok" or j.get("agree") is False
    expected_ok = bool(j.get("expected_correct")) if has_expected else False
    return {"status": "disagrees" if disagrees else "agrees", "expected_parsed": has_expected,
            "expected_correct": expected_ok, "verified_diagnosis": disagrees and expected_ok,
            "agree_error": j.get("agree_error"), "expected_error": j.get("expected_error")}


def witness_key(r: dict, item: dict, p: Problem) -> str:
    """Binds the scorer version and implementation, the suite's comparator and tolerance, both programs and the
    witness text."""
    return sha(json.dumps([SCORER, sha(JUDGE), sha(json.dumps(suite_assertion(p))), sha(_NonFinite.__doc__ or ""),
                           sha(item[f"{r['kind']}_solution"]), sha(p.canonical_solution), r["witnesses"]],
                          sort_keys=True))


def stage_witness(workers: int) -> None:
    problems = {p.problem_id: p for p in load_problems()}
    items = {i["item_id"]: i for i in json.loads(ITEMS_PATH.read_text())}
    have = {r["input_sha256"] for r in load(WIT_PATH) if not r.get("infra")}
    jobs = []
    for r in load(AUD_PATH):
        if r.get("ok") and r.get("witnesses"):
            item = items[r["item_id"]]
            if witness_key(r, item, problems[item["problem_id"]]) not in have:
                jobs.append(r)

    def one(r):
        item = items[r["item_id"]]
        p = problems[item["problem_id"]]
        res = [judge_witness(p, item[f"{r['kind']}_solution"], w["call"], w["expected"]) for w in r["witnesses"]]
        append(WIT_PATH, {"item_id": r["item_id"], "kind": r["kind"], "arm": r["arm"], "auditor": r["auditor"],
                          "reading": r["reading"], "input_sha256": witness_key(r, item, p), "scorer": SCORER,
                          "results": res, "infra": any(x["status"] == "infra" for x in res),
                          "disagreement": any(x.get("status") == "disagrees" for x in res),
                          "verified_diagnosis": any(x.get("verified_diagnosis") for x in res)})
    run_pool(jobs, one, workers, "witness")


def expected_universe(split: str, auditors: list[str] = PRIMARY_AUDITORS) -> list[tuple]:
    """Every reading the registered analysis needs, rebuilt from the frozen items and admissions rather than from
    whatever schedule files exist (A4 B5): all arms for admitted items, the original arm for the rest."""
    items = [i["item_id"] for i in json.loads(ITEMS_PATH.read_text()) if i["split"] == split]
    cons = admitted_constructions()
    out = []
    for iid in items:
        arms = ARMS if iid in cons else ("orig",)
        out += [(iid, kind, arm, a, k) for kind in ("defective", "correct") for arm in arms for a in auditors
                for k in range(READINGS[arm])]
    return out


def completeness(split: str) -> dict:
    """Every scheduled key is either valid or exhausted, and every valid reading with witnesses has a current,
    infrastructure-free witness record. Raises if work is unfinished."""
    problems = {p.problem_id: p for p in load_problems()}
    items = {i["item_id"]: i for i in json.loads(ITEMS_PATH.read_text())}
    rows = [r for r in load(AUD_PATH) if r.get("split") == split]
    ok = {(r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"]): r for r in rows if r.get("ok")}
    tries: dict = {}
    for r in rows:
        k = (r["item_id"], r["kind"], r["arm"], r["auditor"], r["reading"])
        tries[k] = tries.get(k, 0) + 1
    sched = expected_universe(split)
    for name in (f"schedule_v3_{split}.json", f"schedule_v3_orig_{split}.json"):
        if (REC / name).exists():
            extra = {tuple(j) for j in json.loads((REC / name).read_text())} - set(sched)
            if extra:
                raise SystemExit(f"{name} holds {len(extra)} keys outside the required universe")
    unexpected = [k for k in tries if k not in set(sched)]
    if unexpected:
        raise SystemExit(f"{len(unexpected)} audit keys outside the required universe, e.g. {unexpected[0]}")
    unfinished = [k for k in sched if k not in ok and tries.get(k, 0) < MAX_ATTEMPTS]
    missing = [k for k in sched if k not in ok and tries.get(k, 0) >= MAX_ATTEMPTS]
    wits = {r["input_sha256"]: r for r in load(WIT_PATH) if not r.get("infra")}
    unscored = [k for k, r in ok.items() if r.get("witnesses") and
                witness_key(r, items[r["item_id"]], problems[items[r["item_id"]]["problem_id"]]) not in wits]
    if unfinished or unscored:
        raise SystemExit(f"incomplete: {len(unfinished)} unfinished readings, {len(unscored)} unscored witnesses")
    return {"scheduled": len(sched), "valid": len(ok), "missing": [list(k) for k in missing]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["generate", "oracle", "execute", "select", "construct", "adjudicate",
                                      "taxonomy", "audit", "witness"])
    ap.add_argument("--orig-rest", action="store_true", help="original arm for the non-admitted items")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--auditors", default=",".join(PRIMARY_AUDITORS))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    {"generate": lambda: stage_generate(a.workers), "oracle": lambda: stage_oracle(a.workers),
     "execute": lambda: stage_execute(a.workers), "select": lambda: stage_select(a.force),
     "construct": lambda: stage_construct(a.workers), "adjudicate": lambda: stage_adjudicate(a.workers),
     "taxonomy": lambda: stage_taxonomy(a.workers),
     "audit": lambda: stage_audit(a.split, a.workers, a.auditors.split(","), a.orig_rest),
     "witness": lambda: stage_witness(a.workers)}[a.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
