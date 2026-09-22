#!/usr/bin/env python3
"""P1's third rating.

**Provenance, stated precisely, because two earlier versions of this header got it wrong.**
The rubric, the share taken over all items, the problem-cluster percentile bootstrap over the
union of their problems, 10,000 resamples, **seed 20260921** and Wilson beside it were all
registered in P3's Amendment 1 (`d5919b9`, 2026-09-21 20:24:05), a day before the ratings. So
was an inconclusiveness gate at one-third `cannot-tell` in either group.

`plan/P1-ANALYSIS-REGISTRATION.md`, written the next day, is **withdrawn**: it claimed no
contrast had been computed when one had been committed an hour earlier. What that withdrawal
does NOT license is the opposite overstatement -- the method above was fixed in advance.

What was **not** registered anywhere: the disjoint-population diagnostic, and the comparison
against the broken sheet. Both are post hoc and are labelled so.
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
SEED = 20260921        # the registered seed; 20260922 was used by mistake in one draft
N_BOOT = 10000


def labels(path: Path) -> dict[str, str]:
    return {r["rate_id"]: r["label"] for r in csv.DictReader(path.open(encoding="utf-8"))}


def wilson(k: int, n: int) -> list[float]:
    """Wilson, printed beside the cluster interval and marked too narrow, as everywhere here."""
    if not n:
        return [None, None]
    z, p = 1.959963984540054, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [100 * (c - h), 100 * (c + h)]


def contrast(items: list[dict], lab: dict[str, str], drop_cannot: bool,
             disjoint: bool = False) -> dict:
    # The sheet's 121 entries cover 110 unique instances: 11 appear in BOTH arms, because the
    # 68-item missed sheet is 57 residual instances plus 11 that were caught. A contrast over
    # the sheet's two groups is therefore not a contrast between missed and caught instances.
    # `disjoint` drops each such instance's missed-arm copy, leaving 57 against 53.
    if disjoint:
        seen = {}
        for it in items:
            seen.setdefault(it["instance"], set()).add(it["arm"])
        both = {i for i, a in seen.items() if len(a) > 1}
        items = [it for it in items
                 if not (it["instance"] in both and it["arm"] == "missed")]
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
            "missed_wilson": wilson(mk, mn), "caught_wilson": wilson(ck, cn),
            "diff_points": (m - c) if (m is not None and c is not None) else None,
            "cluster_ci95": [rc.percentile(diffs, 0.025), rc.percentile(diffs, 0.975)],
            "n_problems": len(keys), "n_boot_ok": len(diffs)}


def main() -> int:
    items = json.loads(KEY.read_text(encoding="utf-8"))
    rebuilt = labels(REC / "L3.csv")
    broken = labels(REC / "L3-broken-sheet.csv")

    primary = contrast(items, rebuilt, drop_cannot=False)
    disjoint = contrast(items, rebuilt, drop_cannot=False, disjoint=True)
    secondary = contrast(items, rebuilt, drop_cannot=True)
    secondary_dj = contrast(items, rebuilt, drop_cannot=True, disjoint=True)
    explor = contrast(items, broken, drop_cannot=False)
    explor_dj = contrast(items, broken, drop_cannot=False, disjoint=True)

    moved = sum(1 for it in items
                if broken.get(it["rate_id"]) != rebuilt.get(it["rate_id"]))
    moved_by_arm = {}
    rate_shift = {}
    for a in ("missed", "caught"):
        ids = [it["rate_id"] for it in items if it["arm"] == a]
        moved_by_arm[a] = sum(1 for r in ids if broken.get(r) != rebuilt.get(r))
        bu = sum(1 for r in ids if broken.get(r) == "undetermined")
        ru = sum(1 for r in ids if rebuilt.get(r) == "undetermined")
        rate_shift[a] = 100 * (ru - bu) / len(ids) if ids else None
    ct = {"broken": sum(1 for v in broken.values() if v == "cannot-tell"),
          "rebuilt": sum(1 for v in rebuilt.values() if v == "cannot-tell")}

    # The 11 instances that sit in both arms are the same specification and the same witness
    # display, rated twice in one pass. Their agreement is a within-pass consistency reading of
    # the instrument itself, and it is the strongest constraint on anything read off it.
    dup = {}
    for it in items:
        dup.setdefault(it["instance"], []).append(it)
    pairs = [(i, rows) for i, rows in dup.items() if len(rows) > 1]
    agree = [(i, [rebuilt.get(x["rate_id"]) for x in rows]) for i, rows in pairs]
    same_text = all(len({x["spec"] for x in rows}) == 1 for _, rows in pairs)
    n_agree = sum(1 for _, ls in agree if len(set(ls)) == 1)

    ct_share = {}
    for sheet, L in (("rebuilt", rebuilt), ("broken", broken)):
        for a in ("missed", "caught"):
            ids = [it["rate_id"] for it in items if it["arm"] == a]
            ct_share[f"{sheet}_{a}"] = 100 * sum(
                1 for r in ids if L.get(r) == "cannot-tell") / len(ids)

    out = {
        "within_pass_consistency": {
            "note": "the 11 instances carried in both arms: identical specification text, "
                    "identical witness display, rated twice in the same pass",
            "n_pairs": len(pairs), "n_agreeing": n_agree,
            "specification_text_identical_in_every_pair": same_text,
            "pairs": {i: ls for i, ls in agree},
        },
        "registered_inconclusive_gate": {
            "rule": "Amendment 1 (d5919b9): inconclusive if either group exceeds one third "
                    "`cannot-tell`",
            "cannot_tell_share_pct": ct_share,
            "rebuilt_passes": max(ct_share["rebuilt_missed"], ct_share["rebuilt_caught"]) <= 100 / 3,
            "broken_passes": max(ct_share["broken_missed"], ct_share["broken_caught"]) <= 100 / 3,
        },
        "rater": "gpt-5.6-luna (L3), per rate3/third_rater.py -- a MODEL, not the outside "
                 "human P1 asks for, and deliberately NOT gpt-6-astra, which was study 21's L2",
        "seed": SEED, "n_boot": N_BOOT,
        "sheet_groups_NOT_missed_vs_caught": primary,
        "disjoint_instances_57_vs_53": disjoint,
        "secondary_cannot_tell_excluded_OVERLAPPING": secondary,
        "secondary_cannot_tell_excluded_DISJOINT": secondary_dj,
        "exploratory_broken_sheet_DISJOINT": explor_dj,
        "exploratory_broken_sheet": explor,
        "labels_changed_between_sheets": moved,
        "labels_changed_by_arm": moved_by_arm,
        "undetermined_rate_shift_points_by_arm": rate_shift,
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

    show("SHEET GROUPS (NOT missed-vs-caught: 11 instances sit in both)", primary)
    print()
    show("DISJOINT INSTANCES (the 11 missed-arm copies removed)", disjoint)
    print()
    show("SECONDARY overlapping (cannot-tell excluded)", secondary)
    print()
    show("SECONDARY disjoint  (cannot-tell excluded)", secondary_dj)
    print()
    show("EXPLORATORY broken sheet, overlapping groups", explor)
    print()
    show("EXPLORATORY broken sheet, disjoint instances", explor_dj)
    print(f"\ncannot-tell: {ct['broken']} on the broken sheet, {ct['rebuilt']} on the rebuilt one")
    print(f"{moved} of {len(items)} labels changed between the two sheets "
          f"(missed {moved_by_arm['missed']}, caught {moved_by_arm['caught']}); the "
          f"undetermined RATE moved {rate_shift['missed']:+.2f} points on missed and "
          f"{rate_shift['caught']:+.2f} on caught")
    print(f"\nwithin-pass consistency: {n_agree} of {len(pairs)} duplicate pairs agree "
          f"(identical specification text in every pair: {same_text})")
    print(f"\nsix-category comparator (a DIFFERENT instrument): missed 46/68, caught 24/53, "
          f"{out['six_category_comparator']['diff_points']:+.1f} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
