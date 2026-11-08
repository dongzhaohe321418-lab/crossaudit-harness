"""Exploratory pilot (development units only, Claude routes only): can an auditor find the behaviour a task leaves
open, when asked to list unspecified behaviours instead of being told the contract?

For each registered development unit (open, and positive controls as a control), the auditor model is shown the
task, the visible tests and one of the two programs, and asked for up to six unspecified behaviours as questions to
the task author. A judge, shown both rules in a random order and not told which is the benchmark's, decides whether
any question targets the behaviour on which the rules differ. Records: benchmarks/e8/records/discover_dev.jsonl.

    PYTHONPATH=crossaudit-harness/src audit/.venv/bin/python benchmarks/e8/pilot_discover.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "code"), str(HERE.parent / "code" / "icml")]
import e1  # noqa: E402
import e6  # noqa: E402

OUT = HERE / "records" / "discover_dev.jsonl"
AUDITOR, JUDGE = "aud-claude-sonnet-low", "adj-claude-opus"

ELICIT = """You are reviewing a Python function written for the task below. Before judging correctness, list the
behaviours that the task description and the visible tests leave unspecified and on which a correct implementation's
output could reasonably differ (for example, how ties, duplicates, empty inputs, types or unusual characters are
handled). Ignore style and performance. Give at most six, most important first, each as one short question to the
task author.

TASK:
{spec}

VISIBLE TESTS:
{visible}

PROGRAM:
{program}

Reply with exactly one JSON object: {{"questions": ["...", "..."]}}
"""

MATCH = """A task author was asked questions about a programming task. Two candidate rules, which a task author
might add, differ on one kind of input. Decide whether any of the questions asks about the behaviour on which the two
rules differ (it need not use the same words, but it must be about that behaviour, not merely the same input).

TASK:
{spec}

RULE 1: {r1}
RULE 2: {r2}

QUESTIONS:
{questions}

Reply with exactly one JSON object: {{"match": true or false, "question_index": <1-based index or null>}}
"""


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    done = {(r["kind"], r["problem_id"], r["program"]) for r in e1.load(OUT)}
    jobs = []
    for kind in ("open", "open2", "det"):
        e6.set_kind(kind)
        units = e6.units("dev")
        probs = {p.problem_id: p for p in e6.problems("dev")}
        for pid in e6.registered_units("dev"):
            for prog in "ab":
                if (kind, pid, prog) not in done:
                    jobs.append((kind, pid, prog, units[pid], probs[pid]))

    def one(job):
        kind, pid, prog, u, p = job
        res = e1.call(AUDITOR, ELICIT.format(spec=p.spec.rstrip(), visible=p.visible_tests_text(),
                                             program=u["program"][prog]))
        obj = e1.parse_json(res["text"]) if res.get("text") else None
        qs = [str(q) for q in (obj or {}).get("questions", [])][:6] if isinstance(obj, dict) else []
        a_first = int(e6.sha("discover-order|" + pid), 16) % 2 == 0
        r1, r2 = (u["rule_a"], u["rule_b"]) if a_first else (u["rule_b"], u["rule_a"])
        match = None
        if qs:
            j = e1.call(JUDGE, MATCH.format(spec=p.spec.rstrip(), r1=r1, r2=r2,
                                            questions="\n".join(f"{i + 1}. {q}" for i, q in enumerate(qs))))
            jo = e1.parse_json(j["text"]) if j.get("text") else None
            match = bool(jo.get("match")) if isinstance(jo, dict) and "match" in jo else None
        e1.append(OUT, {"kind": kind, "problem_id": pid, "program": prog, "ok": res.get("ok", False),
                        "questions": qs, "match": match})
    e1.run_pool(jobs, one, 3, "e8 discover dev")
    rows = e1.load(OUT)
    for kind in ("open", "open2", "det"):
        rs = [r for r in rows if r["kind"] == kind and r["match"] is not None]
        print(kind, "readings", len(rs), "behaviour found", sum(r["match"] for r in rs))


if __name__ == "__main__":
    main()
