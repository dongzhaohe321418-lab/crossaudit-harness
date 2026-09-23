#!/usr/bin/env python3
"""A4S-2 re-execution auditor, and the re-execution half of the gate.

For every item: run `work/solution.py` then `work/inputs.py` from the item's own files, evaluate
the registered call, and compare the output with the report's stated values (the
`crossaudit-numbers` rows' `v`) under `np.allclose` defaults (Amendment 1). Flag = not allclose, or
the run did not produce a comparable output. Writes `records/ai4s/results_reexec.json`. No model.

    python benchmarks/ai4s/reexec_results.py
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from build_results_items import OUT, execute  # noqa: E402

MANIFEST = REPO / "benchmarks/code/records/ai4s/results_items.json"
RECORD = REPO / "benchmarks/code/records/ai4s/results_reexec.json"
_FENCE = re.compile(r"```crossaudit-numbers[^\n]*\n(.*?)\n```", re.S)


def main() -> int:
    import numpy as np
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    jobs = [(inst, e) for inst in man["instances"] for e in inst["items"]]

    def one(job):
        inst, e = job
        d = OUT / e["item"] / "work"
        code = (d / "solution.py").read_text(encoding="utf-8")
        inputs = (d / "inputs.py").read_text(encoding="utf-8")
        rows = json.loads(_FENCE.search((d / "report.md").read_text(encoding="utf-8")).group(1))
        stated = [float(r["v"]) for r in rows]
        got = execute(code, inputs, inst["call"])
        if got is None or len(got[0]) != len(stated):
            return {"item": e["item"], "kind": e["kind"], "fault": e["fault"], "flagged": True,
                    "why": "no comparable output"}
        ok = bool(np.allclose(got[0], stated))
        return {"item": e["item"], "kind": e["kind"], "fault": e["fault"], "flagged": not ok}

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(one, jobs))
    RECORD.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    clean_bad = [r["item"] for r in rows if r["kind"] == "clean" and r["flagged"]]
    print(f"{len(rows)} items re-executed; gate (re-execution half): clean items flagged "
          f"{len(clean_bad)} {clean_bad[:5]}")
    return 0 if not clean_bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
