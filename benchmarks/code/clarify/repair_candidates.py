#!/usr/bin/env python3
"""Amendment 13's repair: swap in each instance's own candidate, re-run the gates, keep the specs.

Amendment 9 registered run 3 as the final generation run, so this does NOT regenerate
specifications -- it buys nothing. It replaces the candidate and the visible suite, re-runs
every gate against them, and records any instance the gates now reject.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import gates  # noqa: E402
from corpus import load_problems  # noqa: E402

# `benchmarks/code/generate.py` also exists and wins on sys.path, so a plain `import generate`
# silently binds the wrong module -- the same disease as Amendment 13 itself, at a smaller
# scale: a name that looks right and is a different thing. Loaded by explicit path instead.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("clarify_generate", HERE / "generate.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)
assert hasattr(gen, "batch_candidates"), "loaded the wrong generate module"

COND = HERE.parent / "records/clarify/conditions.json"
DUMP = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs/residual/index.json"


def main() -> int:
    data = json.loads(COND.read_text(encoding="utf-8"))
    conds = data["conditions"]
    batch = gen.batch_candidates()
    problems = {p.problem_id: p for p in load_problems()}
    witnesses = {r["instance_id"]: r for r in json.loads(DUMP.read_text(encoding="utf-8"))}

    missing = [i for i in conds if i not in batch]
    if missing:
        raise SystemExit(f"ERR: no frozen candidate for {missing}")

    kept, newly_dropped = {}, []
    for iid, c in conds.items():
        problem = problems[iid.split(":", 1)[1]]
        for arm in ("original", "clarified", "placebo"):
            c[arm]["candidate"] = batch[iid]
            c[arm]["visible_tests"] = problem.visible_tests_text()
        hidden_text = problem.hidden_program(batch[iid])[0]
        problems_found = gates.run_all(iid, c, (witnesses.get(iid) or {}).get("witness") or {},
                                       hidden_text, gen.SCAFFOLD)
        if problems_found:
            newly_dropped.append({"instance_id": iid, "reasons": problems_found})
            print(f"  {iid}: DROPPED on the real candidate -- {problems_found[0][:90]}")
            continue
        kept[iid] = c

    data["conditions"] = kept
    data["amendment_13_repair"] = {
        "candidate_source": "study-data/wt-testgen-runs/inputs/solutions-{b1,b2}.jsonl",
        "specs_unchanged": True,
        "n_before": len(conds), "n_after": len(kept),
        "dropped_on_real_candidate": newly_dropped,
        "note": "specifications were NOT regenerated; Amendment 9 registered run 3 as final. "
                "Only the candidate and visible suite changed, and every gate was re-run "
                "against them.",
    }
    data["n_kept"] = len(kept)
    COND.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n{len(conds)} -> {len(kept)} instances; {len(newly_dropped)} dropped on the "
          f"real candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
