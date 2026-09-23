#!/usr/bin/env python3
"""A4S-1b analysis, as registered in `PREREGISTRATION-CODE-B.md`; committed before this arm completed.

1. This arm's outcomes: `analyze_code.py` rerun on `runs/audit_b` with this arm's seed (20260930).
2. The paired change from A4S-1 to A4S-1b per family and stratum: per instance, flagged at K = 8 in
   one arm and not the other; exact McNemar, cluster sign-flip, and the cluster-bootstrap interval
   on the difference (B minus A), through the ceiling study's reviewed `paired_difference`.
3. B1: supported if the `cross` correct-stratum difference's interval lies below zero; killed if it
   lies above zero; otherwise inconclusive.

    python benchmarks/ai4s/analyze_code_b.py --out benchmarks/code/records/ai4s/code_results_b.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_code as ac  # noqa: E402

SEED_B = 20260930


def flagged_any(audit_dir: Path, fam: str) -> dict[str, bool]:
    out: dict[str, bool] = {}
    n: dict[str, int] = defaultdict(int)
    for d in range(1, ac.K + 1):
        for line in (audit_dir / f"{fam}.d{d}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("ok"):
                out[r["instance_id"]] = out.get(r["instance_id"], False) or bool(r["flagged"])
                n[r["instance_id"]] += 1
    return {i: v for i, v in out.items() if n[i] == ac.K}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    a_dir, b_dir = ac.AUDIT, ac.AI4S / "runs/audit_b"
    ac.AUDIT, ac.SEED = b_dir, SEED_B
    tmp = Path(args.out).with_suffix(".arm.json") if args.out else None
    sys.argv = ["analyze_code.py"] + (["--out", str(tmp)] if tmp else [])
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ac.main()
    arm_b = json.loads(buf.getvalue())
    if tmp:
        tmp.unlink()
    strata = json.loads(ac.STRATA.read_text(encoding="utf-8"))
    change = {}
    for fam in ("cross", "self"):
        fa, fb = flagged_any(a_dir, fam), flagged_any(b_dir, fam)
        for name in ("defective", "correct"):
            ids = [i for i in strata[name] if i in fa and i in fb]
            signed = defaultdict(list)
            for i in ids:
                signed[ac.problem(i)].append(int(fb[i]) - int(fa[i]))
            pdiff = ac.rc.paired_difference(dict(signed), reps=ac.REPS, seed=SEED_B)
            change[f"{fam}/{name}"] = {
                "n": len(ids), "A": sum(fa[i] for i in ids), "B": sum(fb[i] for i in ids),
                "delta_points_B_minus_A": round(100 * pdiff["delta"], 1),
                "ci": [round(100 * x, 1) for x in pdiff["ci95"]],
                "tango_ci": [round(100 * x, 1) for x in pdiff["tango_ci95"]] if pdiff["tango_ci95"] else None,
                "one_signed_discordance": pdiff["one_signed_discordance"],
                "b_flag_only_in_B": pdiff["b"], "c_flag_only_in_A": pdiff["c"],
                "p_exact_mcnemar": pdiff["p_exact"], "p_signflip_cluster": pdiff["p_signflip_cluster"]}
    lo, hi = change["cross/correct"]["ci"]
    b1 = "supported" if hi < 0 else "killed" if lo > 0 else "inconclusive"
    out = {"arm_b": arm_b, "paired_change_A_to_B": change, "B1": b1}
    text = json.dumps(out, indent=1, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
