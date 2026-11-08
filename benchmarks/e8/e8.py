"""E8: can an auditor find the behaviour a task leaves open? (PREREGISTRATION-E8.md; GPT review P8 fixes.)

Universe: every registered E6 unit of the split (open, open2, positive controls) x the two programs. Per reading,
an elicitor call and, if it returns questions, a judge call. Each step may make at most two calls that reached the
model (e1.reached_model); calls that never reached it are retried, up to six times in all. Replies are validated
strictly; an empty question list is a valid reply and a defined negative outcome. Readings whose steps exhaust their
attempts are terminal failures (missing), reported with bounds.

    python benchmarks/e8/e8.py freeze|run|analyse <split>
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "code"), str(HERE.parent / "code" / "icml")]
import e1  # noqa: E402
import e6  # noqa: E402
from pilot_discover import ELICIT, MATCH, AUDITOR, JUDGE  # noqa: E402  (prompts and routes as piloted)

REC = HERE / "records"
SEED, B, MAX_MODEL, MAX_CALLS = 20261113, 10000, 2, 6


def sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def universe(split: str) -> list:
    out = []
    for kind in ("open", "open2", "det"):
        e6.set_kind(kind)
        for pid in e6.registered_units(split):
            out += [(kind, pid, prog) for prog in "ab"]
    e6.set_kind("open")
    return out


def state(split: str) -> dict:
    """What the held-out run is bound to: E6's registered units and programs, prompts, routes, code."""
    units = {}
    for kind in ("open", "open2", "det"):
        e6.set_kind(kind)
        us = e6.units(split)
        for pid in e6.registered_units(split):
            units[f"{kind}|{pid}"] = sha(json.dumps([us[pid]["program"], us[pid]["rule_a"], us[pid]["rule_b"]]))
    e6.set_kind("open")
    return {"split": split, "units": units, "n_readings": len(universe(split)), "elicit": sha(ELICIT),
            "match": sha(MATCH), "routes": {r: e1.ROUTES[r][1] for r in (AUDITOR, JUDGE)},
            "code": {f: sha((HERE / f).read_text()) for f in ("e8.py", "pilot_discover.py")}}


def manifest(split: str) -> Path:
    return REC / f"FREEZE8_{split}.json"


def verify(split: str) -> None:
    if split == "test":
        import freeze
        freeze.verify()                   # E6's frozen bundle (units, programs) must be intact
    m = manifest(split)
    if not m.exists():
        raise SystemExit(f"no E8 freeze for {split}: run `e8.py freeze {split}` after review")
    if json.loads(m.read_text()) != state(split):
        raise SystemExit("E8 freeze verification failed")


def valid_questions(text: str):
    obj = e1.parse_json(text) if text else None
    if not (isinstance(obj, dict) and isinstance(obj.get("questions"), list)
            and all(isinstance(q, str) for q in obj["questions"])):
        return None
    return [q.strip() for q in obj["questions"] if q.strip()][:6]


def valid_match(text: str, n: int):
    obj = e1.parse_json(text) if text else None
    if not (isinstance(obj, dict) and isinstance(obj.get("match"), bool)):
        return None
    qi = obj.get("question_index")
    if obj["match"] and not (isinstance(qi, int) and not isinstance(qi, bool) and 1 <= qi <= n):
        return None                       # a match must name one of the questions
    return obj["match"]


def step(route: str, payload: str, validate):
    """At most MAX_MODEL calls that reached the model, MAX_CALLS in all. Returns (value or None, attempts)."""
    attempts = []
    while len(attempts) < MAX_CALLS and sum(a["reached"] for a in attempts) < MAX_MODEL:
        res = e1.call(route, payload)
        val = validate(res.get("text", "")) if res.get("ok") or res.get("text") else None
        attempts.append({"ok": bool(res.get("ok")), "usage": res.get("usage"), "error": str(res.get("error", ""))[:200],
                         "reached": e1.reached_model(res), "valid": val is not None})
        if val is not None:
            return val, attempts
    return None, attempts


def run(split: str) -> None:
    if split == "test":
        verify(split)
    out = REC / f"e8_{split}.jsonl"
    done = {(r["kind"], r["problem_id"], r["program"]) for r in e1.load(out)}
    jobs = [j for j in universe(split) if j not in done]
    ctx = {}
    for kind in ("open", "open2", "det"):
        e6.set_kind(kind)
        us, ps = e6.units(split), {p.problem_id: p for p in e6.problems(split)}
        for pid in e6.registered_units(split):
            ctx[(kind, pid)] = (us[pid], ps[pid])
    e6.set_kind("open")

    def one(job):
        kind, pid, prog = job
        u, p = ctx[(kind, pid)]
        qs, a1 = step(AUDITOR, ELICIT.format(spec=p.spec.rstrip(), visible=p.visible_tests_text(),
                                             program=u["program"][prog]), valid_questions)
        row = {"kind": kind, "problem_id": pid, "program": prog, "elicit_attempts": a1, "questions": qs}
        if qs is None:
            row.update(outcome=None, terminal="elicitor")
        elif not qs:
            row.update(outcome=False, judge_attempts=[])           # no questions: the behaviour is not named
        else:
            a_first = int(e6.sha("discover-order|" + pid), 16) % 2 == 0
            r1, r2 = (u["rule_a"], u["rule_b"]) if a_first else (u["rule_b"], u["rule_a"])
            m, a2 = step(JUDGE, MATCH.format(spec=p.spec.rstrip(), r1=r1, r2=r2, questions="\n".join(
                f"{i + 1}. {q}" for i, q in enumerate(qs))), lambda t, n=len(qs): valid_match(t, n))
            row.update(outcome=m, judge_attempts=a2, terminal=None if m is not None else "judge")
        e1.append(out, row)
    e1.run_pool(jobs, one, 3, f"e8 {split}")


def analyse(split: str) -> dict:
    rows = {(r["kind"], r["problem_id"], r["program"]): r for r in e1.load(REC / f"e8_{split}.jsonl")}
    uni = universe(split)
    missing_rows = [k for k in uni if k not in rows]
    if missing_rows:
        raise SystemExit(f"incomplete: {len(missing_rows)} of {len(uni)} readings not run")
    by = {}                                        # (group, problem) -> list of outcomes (None = terminal failure)
    for kind, pid, prog in uni:
        g = "control" if kind == "det" else "open"
        by.setdefault((g, pid), []).append(rows[(kind, pid, prog)]["outcome"])

    def values(fill_open, fill_control):
        """Unit values; with fills None, only units whose two readings are both complete."""
        out = {}
        for (g, pid), v in by.items():
            fill = fill_open if g == "open" else fill_control
            if fill is None and any(o is None for o in v):
                continue
            out[(g, pid)] = statistics.mean([fill if o is None else float(o) for o in v])
        return out

    def summarise(vals):
        o_all = [v for (g, _), v in vals.items() if g == "open"]
        c_all = [v for (g, _), v in vals.items() if g == "control"]
        res = {"n_open_units": len(o_all), "n_control_units": len(c_all)}
        if not o_all or not c_all:               # a population without complete units: no estimate (P9)
            res.update(D_open=None, D_control=None, S=None)
            return res
        problems = sorted({p for _, p in vals})
        rng = random.Random(SEED)
        draws = []
        for _ in range(B):                       # resample problems; a shared problem carries both values
            pick = [rng.choice(problems) for _ in problems]
            o = [vals[("open", p)] for p in pick if ("open", p) in vals]
            c = [vals[("control", p)] for p in pick if ("control", p) in vals]
            if o and c:
                draws.append((statistics.mean(o), statistics.mean(c)))
        q = lambda xs: (100 * sorted(xs)[int(0.025 * len(xs))], 100 * sorted(xs)[int(0.975 * len(xs)) - 1])
        res.update(D_open={"est": 100 * statistics.mean(o_all), "ci": q([d[0] for d in draws])},
                   D_control={"est": 100 * statistics.mean(c_all), "ci": q([d[1] for d in draws])},
                   S={"est": 100 * (statistics.mean(o_all) - statistics.mean(c_all)),
                      "ci": q([d[0] - d[1] for d in draws])})
        return res

    res = {"split": split, "n_readings": len(uni),
           "terminal_failures": sum(1 for v in by.values() for o in v if o is None),
           "primary": summarise(values(None, None)),
           # bounds over the full universe: D at 0 and 1; S at its extremes (open 0 / control 1, and the reverse)
           "D_bounds": {"missing_as_0": summarise(values(0.0, 0.0)), "missing_as_1": summarise(values(1.0, 1.0))},
           "S_bounds": {"lower": summarise(values(0.0, 1.0))["S"], "upper": summarise(values(1.0, 0.0))["S"]}}
    p = res["primary"]
    s_ci = p["S"]["ci"] if p["S"] else None
    res["verdicts"] = {"E8_1": bool(p["D_open"] and p["D_open"]["ci"][0] > 50),
                       "S_above_0": bool(s_ci and s_ci[0] > 0), "S_below_0": bool(s_ci and s_ci[1] < 0),
                       "S_below_20": bool(s_ci and s_ci[1] < 20), "S_above_20": bool(s_ci and s_ci[0] > 20),
                       "estimable": bool(p["S"])}
    (REC / f"e8_results_{split}.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    action, split = sys.argv[1], sys.argv[2]
    if action == "freeze":
        REC.mkdir(exist_ok=True)
        manifest(split).write_text(json.dumps(state(split), indent=1, sort_keys=True))
        print("E8 frozen:", manifest(split))
    elif action == "run":
        run(split)
    else:
        print(json.dumps(analyse(split), indent=1))
