#!/usr/bin/env python3
"""Prove the condition's specification reaches the auditor, and that nothing else differs.

If it does not, P3 buys three samples of one condition, the contrast is zero by construction,
and the report says "no effect" about an experiment that never ran. Nothing downstream would
notice: every gate would pass, every count would be plausible, and the null would look like a
finding. So it is checked here, against the real prompt, before anything is bought.

No model call is made: the provider is replaced with one that captures the prompt and returns an
empty finding list.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, "src")
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import audit as study1  # noqa: E402
from corpus import load_problems  # noqa: E402

COND = HERE.parent / "records/clarify/conditions.json"


def main() -> int:
    data = json.loads(COND.read_text(encoding="utf-8"))
    iid = sorted(data["conditions"])[0]
    conds = data["conditions"][iid]
    base = {p.problem_id: p for p in load_problems()}[iid.split(":", 1)[1]]

    seen: dict[str, dict] = {}
    import crossaudit.auditor.run as runmod

    def fake_run_audit(**kw):
        seen[kw["usage_context"]["arm"]] = {
            "task": kw["task"],
            "files": {k: v.decode("utf-8", "replace") for k, v in kw["files"].items()},
            "constitution": kw["constitution"],
        }
        class O:
            verdict = "PASS"; dcl = {"findings": [], "verdict": "PASS"}
            model_reply = {"findings": []}; invalid_reason = ""; prompt_sha256 = "x"
        return O()

    real, runmod.run_audit = runmod.run_audit, fake_run_audit
    try:
        for arm in ("original", "clarified", "placebo"):
            c = conds[arm]
            problem = dataclasses.replace(base, spec=c["spec"])
            study1.audit_one(None, problem, c["candidate"], {}, "RULES",
                             run_id=f"t-{arm}", arm=arm)
    finally:
        runmod.run_audit = real

    failures = []
    if set(seen) != {"original", "clarified", "placebo"}:
        failures.append(f"not every arm reached the auditor: {sorted(seen)}")
    for arm in seen:
        if seen[arm]["task"] != conds[arm]["spec"]:
            failures.append(f"{arm}: the auditor's task is not that condition's specification")
    tasks = {a: seen[a]["task"] for a in seen}
    if len(set(tasks.values())) != 3:
        failures.append("two conditions sent the auditor the SAME task -- the manipulation "
                        "does not reach it, and the study would return a null by construction")
    # and nothing else may differ
    for key in ("files", "constitution"):
        vals = {json.dumps(seen[a][key], sort_keys=True) for a in seen}
        if len(vals) != 1:
            failures.append(f"{key} differs across conditions; only the specification may")

    # the negative direction: without the swap, all three tasks are identical
    seen.clear()
    real, runmod.run_audit = runmod.run_audit, fake_run_audit
    try:
        for arm in ("original", "clarified", "placebo"):
            study1.audit_one(None, base, conds[arm]["candidate"], {}, "RULES",
                             run_id=f"u-{arm}", arm=arm)
    finally:
        runmod.run_audit = real
    if len({seen[a]["task"] for a in seen}) != 1:
        failures.append("the control case did not reproduce the bug this check exists for")

    for f in failures:
        print(f"  [FAIL] {f}")
    if failures:
        return 1
    print("  [ok ] each condition's own specification reaches the auditor as its task")
    print("  [ok ] the three tasks are distinct")
    print("  [ok ] files and constitution are identical across the three")
    print("  [ok ] without the swap all three tasks collapse to one -- the bug is reproducible")
    print("\nthe manipulation reaches the auditor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
