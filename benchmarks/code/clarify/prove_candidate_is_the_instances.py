#!/usr/bin/env python3
"""Check that each condition's candidate is THIS INSTANCE'S candidate.

Amendment 13. Every other check this study built asks whether something is *consistent* across
the arms or *distinct* between them. A wrong program that is wrong in all three arms passes all
of them, and that is exactly what happened: 384 readings against `canonical_solution`, which is
per problem, for instances that are per (batch, problem).

Two checks, and the second is the one with teeth:

1. The candidate equals the frozen generation batch's solution for that instance.
2. **The candidate reproduces the witness's recorded `actual` value on the witness's own failing
   inputs.**

**The first version of this docstring said a different program cannot reproduce another's
outputs. That is false**, and the second review of `RESULTS-CLARIFY.md` said so: agreement on a
finite set of witness cases establishes **consistency**, not identity. Identity is established
by check 1, the comparison against the frozen batch source. Check 2 executes the condition
file's candidate on the first three witness cases and is what caught the canonical-solution
defect in practice -- but on its own it proves the weaker thing.

**What this script does NOT check** (third review): it never reads the recorded audit prompts,
so it cannot show the candidate reached the auditor untransformed. It is not an end-to-end
transit check. For the archived run, that gap was closed by the third review's separate
reconstruction of all 96 condition prompts, which reproduced every successful reading's saved
prompt hash -- an external check, not this script.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

COND = HERE.parent / "records/clarify/conditions.json"
DUMP = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs/residual/index.json"
BATCH = Path.home() / "Documents/Crossaudit/study-data/wt-testgen-runs/inputs"
ARMS = ("original", "clarified", "placebo")


def frozen() -> dict[str, str]:
    out = {}
    for b in ("b1", "b2"):
        for line in (BATCH / f"solutions-{b}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if isinstance(r.get("solution"), str):
                    out[f"{b}:{r['problem_id']}"] = r["solution"]
    return out


def call(candidate: str, entry_hint: str, args: list):
    ns: dict = {}
    exec(compile(candidate, "<candidate>", "exec"), ns)      # noqa: S102
    fns = [v for k, v in ns.items() if callable(v) and not k.startswith("__")]
    fn = next((v for v in fns if getattr(v, "__name__", "") == entry_hint), None) or (
        fns[0] if fns else None)
    if fn is None:
        raise RuntimeError("no callable in candidate")
    return fn(*args)


def main() -> int:
    conds = json.loads(COND.read_text(encoding="utf-8"))["conditions"]
    batch = frozen()
    wit = {r["instance_id"]: r for r in json.loads(DUMP.read_text(encoding="utf-8"))}

    wrong_source, no_witness, mismatched, checked = [], [], [], 0
    for iid, c in conds.items():
        cand = c["original"]["candidate"]
        if any(c[a]["candidate"] != cand for a in ARMS):
            wrong_source.append(f"{iid}: the three arms do not share one candidate")
            continue
        if iid not in batch or batch[iid].strip() != cand.strip():
            wrong_source.append(f"{iid}: candidate is not the frozen batch solution")
            continue
        cases = ((wit.get(iid) or {}).get("witness") or {}).get("cases") or []
        if not cases:
            no_witness.append(iid)
            continue
        entry = iid.split("/")[-1]
        for case in cases[:3]:
            expected_actual = str(case.get("actual"))
            # The witness records an exception as `<raised IndexError: ...>`, so a candidate
            # that raises is REPRODUCING it, not failing to run. The first version treated every
            # exception as a failure and reported four instances as not auditing their own
            # candidate when all four matched the witness exactly.
            try:
                args = ast.literal_eval(str(case.get("input")))
                got = call(cand, entry, args)
                observed, alt = repr(got), str(got)
            except Exception as exc:                                   # noqa: BLE001
                observed = alt = f"<raised {type(exc).__name__}: {exc}>"
            if observed != expected_actual and alt != expected_actual.strip("'\""):
                mismatched.append(f"{iid}: candidate gave {observed} where the witness "
                                  f"recorded {expected_actual}")
                break
        else:
            checked += 1

    for group, label in ((wrong_source, "wrong source"), (mismatched, "witness mismatch")):
        for m in group[:8]:
            print(f"  [FAIL] {m}")
    if no_witness:
        print(f"  [note] {len(no_witness)} instance(s) carry no witness cases "
              f"(timeouts and unrecovered inputs); the second check cannot run on them")
    print(f"  [ok ] {checked} instance(s) reproduce the witness's own recorded outputs")
    if wrong_source or mismatched:
        print(f"\n{len(wrong_source) + len(mismatched)} instance(s) are not auditing their own "
              "candidate")
        return 1
    print("\nevery condition audits this instance's own candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
