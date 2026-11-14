"""E9: do judges outside the construction accept both rules of an open unit? (PREREGISTRATION-E9.md)

Items: every registered E6 unit of the split (open, open2: the open units; det: positive controls, rule A a misreading)
and, for each open unit, a resolved item: the same task with one rule appended as an ordinary requirement (the rule
chosen by a hash of the problem id), so that the other rule should be excluded. Each item is read by two judges
(Claude Sonnet 5.5 and GPT-5.6-terra, high budget; neither took part in the construction) in both rule orders. The
judges are not told which rule is the benchmark's nor what kind of item they read. Each reading judges whether the
inputs the rules concern are valid, and each rule compatible / incompatible / unresolved, quoting the words that
exclude a rule. Quotes are matched verbatim against the text shown, by program. Each reading may make at most two
calls that reached the model (e1.reached_model) and six in all; a reply is accepted only from a call that succeeded
without tool use and has every field; exhausted readings are terminal failures.

    python benchmarks/e9/e9.py freeze|run|analyse <split>
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "code"), str(HERE.parent / "code" / "icml")]
import e1  # noqa: E402
import e6  # noqa: E402

REC = HERE / "records"
SEED, B, MAX_MODEL, MAX_CALLS = 20261114, 10000, 2, 6
JUDGES = ("aud-claude-sonnet-high", "aud-gpt-terra-high")
VALS = ("compatible", "incompatible", "unresolved")
DOMS = ("valid", "invalid", "unresolved")
KINDS = ("open", "open2", "det", "resolved")

PROMPT = """You are checking material for a study of code review. Answer strictly from the task's words and visible
tests, as a careful programmer would read them; do not run code.

TASK (as given to a programmer):
{spec}

VISIBLE TESTS:
{visible}

Below are two rules that a task author might add to make the task more precise. First decide whether the inputs the
rules concern are valid inputs for the task as stated (types, ranges, preconditions). Then, for EACH rule separately,
decide whether a function that follows it is compatible with the task as written:
- "compatible": nothing in the task's words, their ordinary meaning or the visible tests rules it out;
- "incompatible": the words, their ordinary meaning (for example a mathematical fact) or a visible test rules it out;
- "unresolved": you cannot decide.
The absence of an example is not by itself permission or prohibition. For every "incompatible" verdict, quote the
exact words of the task or visible tests that rule the rule out (copy them verbatim), or write "ordinary meaning" if
it is ruled out by a fact the words imply rather than by particular words; for other verdicts give an empty string.
RULE 1: {r1}
RULE 2: {r2}

Reply with exactly one JSON object:
{{"domain": "valid" | "invalid" | "unresolved",
  "rule1": "compatible" | "incompatible" | "unresolved", "rule1_quote": "verbatim words, ordinary meaning, or empty",
  "rule2": "compatible" | "incompatible" | "unresolved", "rule2_quote": "verbatim words, ordinary meaning, or empty",
  "reason": "one or two sentences"}}
"""


def sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def resolved_rule(pid: str) -> str:
    """The rule a resolved item appends: fixed by a hash of the problem id, independent of the readings."""
    return "a" if int(sha("e9-resolve|" + pid), 16) % 2 == 0 else "b"


def items(split: str) -> list:
    out = []
    for kind in ("open", "open2", "det"):
        e6.set_kind(kind)
        out += [(kind, pid) for pid in e6.registered_units(split)]
    e6.set_kind("open")
    return out + [("resolved", pid) for k, pid in list(out) if k in ("open", "open2")]


def universe(split: str) -> list:
    return [(k, pid, j, o) for k, pid in items(split) for j in JUDGES for o in ("ab", "ba")]


def context(split: str) -> dict:
    ctx = {}
    for kind in ("open", "open2", "det"):
        e6.set_kind(kind)
        us, ps = e6.units(split), {p.problem_id: p for p in e6.problems(split)}
        for pid in e6.registered_units(split):
            ctx[(kind, pid)] = (us[pid], ps[pid], ps[pid].spec.rstrip())
            if kind != "det":
                ctx[("resolved", pid)] = (us[pid], ps[pid], ps[pid].spec.rstrip() + e6.arm_text(
                    us[pid], "sentence-" + resolved_rule(pid)))
    e6.set_kind("open")
    return ctx


def payload(ctx: dict, kind: str, pid: str, order: str) -> str:
    u, p, spec = ctx[(kind, pid)]
    r1, r2 = (u["rule_a"], u["rule_b"]) if order == "ab" else (u["rule_b"], u["rule_a"])
    return PROMPT.format(spec=spec, visible=p.visible_tests_text(), r1=r1, r2=r2)


def state(split: str) -> dict:
    ctx = context(split)
    return {"split": split, "n_readings": len(universe(split)), "prompt": sha(PROMPT),
            "items": {f"{k}|{pid}": sha(payload(ctx, k, pid, "ab")) for k, pid in items(split)},
            "routes": {r: e1.ROUTES[r][1] for r in JUDGES},
            "code": {f: sha((HERE / f).read_text()) for f in ("e9.py", "PREREGISTRATION-E9.md")}}


def manifest(split: str) -> Path:
    return REC / f"FREEZE9_{split}.json"


def records(split: str) -> Path:
    return REC / f"e9_{split}.jsonl"


def verify(split: str) -> None:
    if split == "test":
        import freeze
        freeze.verify()                   # E6's frozen bundle must be intact
    m = manifest(split)
    if not m.exists():
        raise SystemExit(f"no E9 freeze for {split}")
    if json.loads(m.read_text()) != state(split):
        raise SystemExit("E9 freeze verification failed")


def norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().strip("\"'").strip().lower()


def validate(text: str):
    obj = e1.parse_json(text) if text else None
    if not (isinstance(obj, dict) and obj.get("domain") in DOMS and obj.get("rule1") in VALS
            and obj.get("rule2") in VALS and all(isinstance(obj.get(f), str)
                                                 for f in ("rule1_quote", "rule2_quote", "reason"))):
        return None
    return obj


def quote_match(quote: str, shown: str) -> str:
    """'found': the quote (at least two words and eight characters) occurs verbatim in the text shown, whitespace,
    quotes and case folded; 'meaning': the judge appealed to ordinary meaning; 'not_found': neither. Occurrence is a
    textual check only: whether the words establish incompatibility is not judged."""
    q = norm(quote)
    if q == "ordinary meaning":
        return "meaning"
    return "found" if len(q) >= 8 and len(q.split()) >= 2 and q in norm(shown) else "not_found"


def step(route: str, text: str):
    attempts = []
    while len(attempts) < MAX_CALLS and sum(a["reached"] for a in attempts) < MAX_MODEL:
        res = e1.call(route, text)
        val = validate(res.get("text", "")) if res.get("ok") else None      # never from a failed or tool-using call
        attempts.append({"ok": bool(res.get("ok")), "usage": res.get("usage"), "error": str(res.get("error", ""))[:200],
                         "reached": e1.reached_model(res), "valid": val is not None})
        if val is not None:
            return val, res["text"], attempts
    return None, None, attempts


def run(split: str, workers: int = 4) -> None:
    if split == "test":
        verify(split)
    out = records(split)
    done = {(r["kind"], r["problem_id"], r["judge"], r["order"]) for r in e1.load(out)}
    jobs = [j for j in universe(split) if j not in done]
    ctx = context(split)

    def one(job):
        kind, pid, judge, order = job
        text = payload(ctx, kind, pid, order)
        obj, reply, att = step(judge, text)
        row = {"kind": kind, "problem_id": pid, "judge": judge, "order": order, "prompt_sha256": sha(text),
               "attempts": att, "terminal": obj is None, "reply": reply}
        if obj is not None:
            ka, kb = ("rule1", "rule2") if order == "ab" else ("rule2", "rule1")
            shown = text.split("RULE 1:")[0]
            row.update(domain=obj["domain"], a=obj[ka], b=obj[kb], a_quote=obj[ka + "_quote"],
                       b_quote=obj[kb + "_quote"], reason=obj["reason"],
                       a_ground=quote_match(obj[ka + "_quote"], shown) if obj[ka] == "incompatible" else None,
                       b_ground=quote_match(obj[kb + "_quote"], shown) if obj[kb] == "incompatible" else None)
        e1.append(out, row)
    e1.run_pool(jobs, one, workers, f"e9 {split}")


# ---------------------------------------------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------------------------------------------
def mean(xs):
    return statistics.mean(xs) if xs else None


def pct(x):
    return None if x is None else 100 * x


def boot(per_problem: dict, f) -> list | None:
    """Problem bootstrap of f(values by group); per_problem maps pid -> {group: unit value}, so groups that share a
    problem are resampled together. None when f is not estimable on the data."""
    if f(per_problem) is None:
        return None
    problems = sorted(per_problem)
    rng = random.Random(SEED)
    draws = []
    for _ in range(B):
        pick = [per_problem[rng.choice(problems)] for _ in problems]
        x = f(dict(enumerate(pick)))
        if x is not None:
            draws.append(x)
    draws.sort()
    return [pct(draws[int(0.025 * len(draws))]), pct(draws[int(0.975 * len(draws)) - 1])]


def group_mean(g):
    return lambda pp: mean([v[g] for v in pp.values() if g in v])


def diff(g1, g2, paired=False):
    def f(pp):
        if paired:
            ds = [v[g1] - v[g2] for v in pp.values() if g1 in v and g2 in v]
            return mean(ds)
        a, b = group_mean(g1)(pp), group_mean(g2)(pp)
        return None if a is None or b is None else a - b
    return f


def subset_e6(split: str, keep: set) -> dict:
    """E9-3: the E6 estimands on a subset of the open units, by the frozen E6 analysis code (no rescoring)."""
    if not keep:
        return {"n_units": 0, "estimable": False}
    import analyse_e6
    original = analyse_e6.merged_open

    def patched(split_, allow_incomplete):
        cells, units, status, beh = original(split_, allow_incomplete)
        units = [u for u in units if u in keep]
        return {k: v for k, v in cells.items() if k[0] in units}, units, status, beh

    analyse_e6.merged_open = patched
    try:
        res = analyse_e6.analyse(split, allow_incomplete=False)
    finally:
        analyse_e6.merged_open = original
    pick = ("E6_1_abs_resolve_cov", "E6_1_cov_resolve_minus_menu", "E6_2_convention_advantage_none",
            "E6_5_cov_sentence_minus_none", "flag_pref_a_minus_b_none")
    out = {"n_units": res["n_units"], "estimable": True}
    for k in pick:
        out[k] = {f: res[k].get(f) for f in ("est", "lo", "hi", "n", "missing", "bound_low", "bound_high")
                  if f in res[k]}
    out["registered_criteria"] = {"E6_1": res["verdicts"]["E6_1"], "E6_2": res["verdicts"]["E6_2"],
                                  "E6_5": res["verdicts"]["E6_5"],
                                  "flag_pref_above_0": bool((out["flag_pref_a_minus_b_none"].get("lo") or -1) > 0)}
    out["per_vendor"] = {v: {"E6_1": {f: res["per_vendor"][v]["E6_1"].get(f) for f in ("est", "lo", "hi")},
                             "E6_2": {f: res["per_vendor"][v]["E6_2"].get(f) for f in ("est", "lo", "hi")}}
                         for v in res["per_vendor"]}
    return out


def analyse(split: str, with_e6: bool = True) -> dict:
    if split == "test":
        verify(split)
    ctx = context(split)
    uni = set(universe(split))
    rows = {}
    for r in e1.load(records(split)):
        k = (r["kind"], r["problem_id"], r["judge"], r["order"])
        if k in rows:
            raise SystemExit(f"duplicate reading {k}")
        if k not in uni:
            raise SystemExit(f"unexpected reading {k}")
        if r["prompt_sha256"] != sha(payload(ctx, *k[:2], k[3])):
            raise SystemExit(f"prompt hash mismatch {k}")
        rows[k] = r
    if len(rows) < len(uni):
        raise SystemExit(f"incomplete: {len(uni) - len(rows)} of {len(uni)} readings not run")

    group = {"open": "open", "open2": "open", "det": "control", "resolved": "resolved"}
    per = {}                                      # (group, pid) -> readings (None = terminal failure)
    for k in sorted(uni):
        per.setdefault((group[k[0]], k[1]), []).append(None if rows[k]["terminal"] else rows[k])

    accept = lambda r: r["domain"] == "valid" and r["a"] == "compatible" and r["b"] == "compatible"
    excl = lambda c, grounded=False: (lambda r: r[c] == "incompatible"
                                      and (not grounded or r[f"{c}_ground"] in ("found", "meaning")))
    opp = {pid: ("b" if resolved_rule(pid) == "a" else "a") for g, pid in per if g == "resolved"}

    def unit_values(metric, fill=None, resolved_metric=None):
        pp = {}
        for (g, pid), rs in per.items():
            m = resolved_metric(pid) if (g == "resolved" and resolved_metric) else metric
            if fill is None and any(r is None for r in rs):
                continue
            pp.setdefault(pid, {})[g] = mean([fill if r is None else float(m(r)) for r in rs])
        return pp

    res = {"split": split, "n_readings": len(uni),
           "terminal_failures": sum(r is None for v in per.values() for r in v),
           "n_units": {g: sum(1 for (gg, _) in per if gg == g) for g in ("open", "control", "resolved")}}

    def report(name, pp, f):
        res[name] = {"est": pct(f(pp)), "ci": boot(pp, f)}

    acc, a_ex = unit_values(accept), unit_values(excl("a"))
    report("Adm_open", acc, group_mean("open"))
    report("Adm_control", acc, group_mean("control"))
    report("Excl_A_open", a_ex, group_mean("open"))
    report("Excl_A_control", a_ex, group_mean("control"))
    report("Excl_B_open", unit_values(excl("b")), group_mean("open"))
    report("Disc", a_ex, diff("control", "open"))
    # resolved items: the opposite of the appended rule should be excluded; compared, within problem, with how
    # often the same rule is excluded on the open item
    opp_ex = {}
    for (g, pid), rs in per.items():
        if g in ("open", "resolved") and all(r is not None for r in rs):
            opp_ex.setdefault(pid, {})[g] = mean([float(excl(opp[pid])(r)) for r in rs])
    report("Excl_opp_resolved", opp_ex, group_mean("resolved"))
    report("Disc_resolved", opp_ex, diff("resolved", "open", paired=True))
    # sensitivity: exclusions count only when grounded (quote found or ordinary meaning)
    report("Disc_grounded", unit_values(excl("a", True)), diff("control", "open"))

    # identification bounds over terminal failures (worst case for each hypothesis)
    res["Adm_open_worst"] = pct(group_mean("open")(unit_values(accept, 0.0)))
    lo_c, hi_o = group_mean("control")(unit_values(excl("a"), 0.0)), group_mean("open")(unit_values(excl("a"), 1.0))
    res["Disc_worst"] = None if lo_c is None or hi_o is None else pct(lo_c - hi_o)

    # descriptive
    done = [r for v in per.values() for r in v if r is not None]
    res["per_judge"] = {}
    for j in JUDGES:
        mine = [r for r in done if r["judge"] == j]
        res["per_judge"][j] = {
            "accept_open": pct(mean([accept(r) for r in mine if group[r["kind"]] == "open"])),
            "excl_A_open": pct(mean([excl("a")(r) for r in mine if group[r["kind"]] == "open"])),
            "excl_A_control": pct(mean([excl("a")(r) for r in mine if group[r["kind"]] == "control"])),
            "excl_opp_resolved": pct(mean([excl(opp[r["problem_id"]])(r) for r in mine if r["kind"] == "resolved"])),
            "domain_valid_open": pct(mean([r["domain"] == "valid" for r in mine if group[r["kind"]] == "open"]))}
    pair = {}
    for r in done:
        pair.setdefault((group[r["kind"]], r["problem_id"], r["judge"]), {})[r["order"]] = (r["domain"], r["a"], r["b"])
    res["order_stability"] = {g: pct(mean([v["ab"] == v["ba"] for (gg, _, _), v in pair.items()
                                            if gg == g and len(v) == 2])) for g in ("open", "control", "resolved")}
    cross = {}
    for r in done:
        if group[r["kind"]] == "open":
            cross.setdefault((r["problem_id"], r["order"]), {})[r["judge"]] = accept(r)
    res["cross_judge_agreement_open"] = pct(mean([len(set(v.values())) == 1 for v in cross.values() if len(v) == 2]))
    gr = [r[f"{c}_ground"] for r in done for c in "ab" if r.get(f"{c}_ground")]
    res["exclusion_grounding"] = {g: gr.count(g) for g in ("found", "meaning", "not_found")}

    # open units by acceptance; E9-3 subsets; selection by one judge, outcomes of the other vendor's auditors
    n_acc = {pid: sum(1 for r in rs if r is not None and accept(r)) for (g, pid), rs in per.items() if g == "open"}
    by_judge = {}
    for j in JUDGES:
        ok: dict = {}
        for (k, pid, jj, o), r in rows.items():
            if group[k] == "open" and jj == j:
                ok.setdefault(pid, []).append(not r["terminal"] and accept(r))
        by_judge[j] = {pid for pid, v in ok.items() if len(v) == 2 and all(v)}
    res["open_unit_acceptance"] = dict(sorted(n_acc.items()))
    res["units_accepted_by_majority"] = sum(n >= 3 for n in n_acc.values())
    res["subsets"] = {"majority": sorted(p for p, n in n_acc.items() if n >= 3),
                      "strict": sorted(p for p, n in n_acc.items() if n == 4),
                      **{f"by_{j}": sorted(s) for j, s in by_judge.items()}}
    if with_e6:
        res["E9_3"] = {name: subset_e6(split, set(ps)) for name, ps in res["subsets"].items()}

    def clears(name, worst, threshold):
        ci = res[name]["ci"]
        return bool(ci is not None and ci[0] > threshold and worst is not None and worst > threshold)

    res["verdicts"] = {"E9_1": clears("Adm_open", res["Adm_open_worst"], 50),
                       "E9_2": clears("Disc", res["Disc_worst"], 30),
                       "E9_2b": bool(res["Disc_resolved"]["ci"] and res["Disc_resolved"]["ci"][0] > 30)}
    if with_e6:
        res["verdicts"]["E9_3_majority_registered_criteria"] = res["E9_3"]["majority"].get("registered_criteria")
    (REC / f"e9_results_{split}.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    action, split = sys.argv[1], sys.argv[2]
    if action == "freeze":
        REC.mkdir(exist_ok=True)
        if records(split).exists() and split == "test":
            raise SystemExit("held-out E9 records exist: the freeze cannot be rewritten")
        manifest(split).write_text(json.dumps(state(split), indent=1, sort_keys=True))
        print("E9 frozen:", manifest(split))
    elif action == "run":
        REC.mkdir(exist_ok=True)
        run(split)
    else:
        print(json.dumps(analyse(split, with_e6=(split == "test")), indent=1))
