"""E8 analysis (PREREGISTRATION-E8.md): discovery on open units, on positive controls, and their difference.

    python benchmarks/e8/analyse_e8.py dev|test   -> records/e8_results_<split>.json
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED, B = 20261113, 10000


def unit_means(rows: list, kinds: tuple) -> dict:
    by: dict = {}
    for r in rows:
        if r["kind"] in kinds and r.get("match") is not None:
            by.setdefault(r["problem_id"], []).append(1.0 if r["match"] else 0.0)
    return {k: statistics.mean(v) for k, v in by.items()}


def boot(vals: list, rng: random.Random) -> list:
    return [statistics.mean(rng.choice(vals) for _ in vals) for _ in range(B)]


def main(split: str) -> None:
    rows = [json.loads(l) for l in (HERE / "records" / f"discover_{split}.jsonl").read_text().splitlines() if l.strip()]
    op = list(unit_means(rows, ("open", "open2")).values())
    ct = list(unit_means(rows, ("det",)).values())
    rng = random.Random(SEED)
    bo, bc = boot(op, rng), boot(ct, rng)
    q = lambda xs: (100 * sorted(xs)[int(0.025 * B)], 100 * sorted(xs)[int(0.975 * B)])
    diff = [a - b for a, b in zip(bo, bc)]
    res = {"split": split, "n_open_units": len(op), "n_control_units": len(ct),
           "D_open": {"est": 100 * statistics.mean(op), "ci": q(bo)},
           "D_control": {"est": 100 * statistics.mean(ct), "ci": q(bc)},
           "S": {"est": 100 * (statistics.mean(op) - statistics.mean(ct)), "ci": q(diff)},
           "missing_readings": sum(1 for r in rows if r.get("match") is None)}
    res["verdicts"] = {"E8_1": res["D_open"]["ci"][0] > 50,
                       "S_excludes_0": res["S"]["ci"][0] > 0, "S_excludes_20": res["S"]["ci"][1] < 20}
    (HERE / "records" / f"e8_results_{split}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
