#!/usr/bin/env python3
"""P1's third rating, analysed exactly as `plan/P1-ANALYSIS-REGISTRATION.md` fixed it.

Three contrasts: the primary with `cannot-tell` in the denominator, a secondary excluding it,
and an exploratory reading of what the broken sheet cost. All reported whatever they show.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, "benchmarks/code")
sys.path.insert(0, "benchmarks/expertlongbench")
import report_ceiling as rc  # noqa: E402

KEY = Path.home() / "Desktop/CrossAudit-审计天花板/人类评分任务/_items.json"
REC = Path("benchmarks/code/records/rate3")
SEED = 20260922
N_BOOT = 10000


def labels(path: Path) -> dict[str, str]:
    return {r["rate_id"]: r["label"] for r in csv.DictReader(path.open(encoding="utf-8"))}


def contrast(items: list[dict], lab: dict[str, str], drop_cannot: bool) -> dict:
    rows = []
    for it in items:
        l = lab.get(it["rate_id"])
        if l is None or (drop_cannot and l == "cannot-tell"):
            continue
        rows.append((it["problem_id"], it["arm"], 1 if l == "undetermined" else 0))
    if not rows:
        return {"n": 0}

    def rate(sub, arm):
        vals = [v for _, a, v in sub if a == arm]
        return (100 * sum(vals) / len(vals), sum(vals), len(vals)) if vals else (None, 0, 0)

    m, mk, mn = rate(rows, "missed")
    c, ck, cn = rate(rows, "caught")

    by_problem: dict[str, list] = {}
    for pid, arm, v in rows:
        by_problem.setdefault(pid, []).append((arm, v))
    keys = sorted(by_problem)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(N_BOOT):
        mm = mmn = cc = ccn = 0
        for _ in range(len(keys)):
            for arm, v in by_problem[keys[rng.randrange(len(keys))]]:
                if arm == "missed":
                    mm += v; mmn += 1
                else:
                    cc += v; ccn += 1
        if mmn and ccn:
            diffs.append(100 * (mm / mmn - cc / ccn))
    diffs.sort()
    return {"missed_pct": m, "missed": [mk, mn], "caught_pct": c, "caught": [ck, cn],
            "diff_points": (m - c) if (m is not None and c is not None) else None,
            "cluster_ci95": [rc.percentile(diffs, 0.025), rc.percentile(diffs, 0.975)],
            "n_problems": len(keys), "n_boot_ok": len(diffs)}


def main() -> int:
    items = json.loads(KEY.read_text(encoding="utf-8"))
    rebuilt = labels(REC / "L3.csv")
    broken = labels(REC / "L3-broken-sheet.csv")

    primary = contrast(items, rebuilt, drop_cannot=False)
    secondary = contrast(items, rebuilt, drop_cannot=True)
    explor = contrast(items, broken, drop_cannot=False)

    moved = sum(1 for it in items
                if broken.get(it["rate_id"]) != rebuilt.get(it["rate_id"]))
    ct = {"broken": sum(1 for v in broken.values() if v == "cannot-tell"),
          "rebuilt": sum(1 for v in rebuilt.values() if v == "cannot-tell")}

    out = {
        "rater": "gpt-6-astra (L3) -- a third MODEL, not the outside human P1 asks for",
        "seed": SEED, "n_boot": N_BOOT,
        "primary_cannot_tell_in_denominator": primary,
        "secondary_cannot_tell_excluded": secondary,
        "exploratory_broken_sheet": explor,
        "labels_changed_between_sheets": moved,
        "cannot_tell_counts": ct,
        "six_category_comparator": {
            "note": "a DIFFERENT instrument: ambiguous-oracle among six options, not a "
                    "three-option determinacy rubric. Reported beside, not as a replication.",
            "missed": [46, 68], "caught": [24, 53], "diff_points": 100 * (46 / 68 - 24 / 53)},
    }
    (REC / "analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                                       encoding="utf-8")

    def show(name, d):
        if not d.get("n_problems"):
            print(f"{name}: no rows"); return
        lo, hi = d["cluster_ci95"]
        print(f"{name}")
        print(f"  missed  {d['missed'][0]:>3}/{d['missed'][1]:<3} = {d['missed_pct']:5.1f}%")
        print(f"  caught  {d['caught'][0]:>3}/{d['caught'][1]:<3} = {d['caught_pct']:5.1f}%")
        print(f"  difference {d['diff_points']:+.1f} points, cluster [{lo:+.1f}, {hi:+.1f}], "
              f"{d['n_problems']} problems")

    show("PRIMARY   (cannot-tell in the denominator)", primary)
    print()
    show("SECONDARY (cannot-tell excluded)", secondary)
    print()
    show("EXPLORATORY (the broken sheet -- evidence about SHEETS, not specifications)", explor)
    print(f"\ncannot-tell: {ct['broken']} on the broken sheet, {ct['rebuilt']} on the rebuilt one")
    print(f"{moved} of {len(items)} labels changed between the two sheets")
    print(f"\nsix-category comparator (a DIFFERENT instrument): missed 46/68, caught 24/53, "
          f"{out['six_category_comparator']['diff_points']:+.1f} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
