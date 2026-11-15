"""E13's prespecified secondary estimates (PREREGISTRATION-E13.md, Hypotheses) that `e13.py`'s analysis omitted:
per-vendor E13-1 and E13-2, the difference between the code-shape strata, and conditionals and lines added. Written
after the held-out run (review M4); `e13.py` is unchanged so the freeze still verifies. Writes
records/e13_secondary_<split>.json.

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/e13/e13_secondary.py test
"""
import difflib
import json
import random
import statistics
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import e13                                         # noqa: E402
import e6                                          # noqa: E402


def lines_added(b: str, bp: str) -> int:
    norm = lambda s: [l.strip() for l in s.splitlines() if l.strip()]
    return sum(1 for d in difflib.ndiff(norm(b), norm(bp)) if d.startswith("+ "))


def diff_boot(x: dict, y: dict, b: int = 10_000, seed: str = "e13-strata") -> dict:
    """Difference of stratum means with a problem-level bootstrap within each stratum (points)."""
    xs, ys = list(x.values()), list(y.values())
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choice(xs) for _ in xs) - statistics.mean(rng.choice(ys) for _ in ys)
                   for _ in range(b))
    return {"est": 100 * (statistics.mean(xs) - statistics.mean(ys)), "lo": 100 * draws[int(0.025 * b)],
            "hi": 100 * draws[int(0.975 * b) - 1], "n": [len(xs), len(ys)]}


def main(split: str) -> dict:
    import analyse_e6 as A
    if split == "test":
        e13.verify()
    reg = e13.registered(split)
    population = [p for (_, p) in reg]
    strata = e13.shape_strata(split)
    bp = e13.passed_edits(split)
    e13.install_audit()
    cells = {}
    for kind in e13.KINDS:
        e6.set_kind(kind)
        e6.completeness(split)
        c, _ = A.table(split)
        cells.update(c)
    e6.set_kind("open")
    paired = lambda prog: {(pid, "b" if pr == prog else pr, arm, cfg): v for (pid, pr, arm, cfg), v in cells.items()
                           if pr in ("a", prog)}
    with_b, with_c = paired("b"), paired("c")

    def contrasts(cfgs):
        d1, d2 = {}, {}
        for pid in population:
            vb, vc = A.unit_value(with_b, pid, "none", cfgs, 1), A.unit_value(with_c, pid, "none", cfgs, 1)
            if vb is not None and vc is not None:
                d1[pid], d2[pid] = vc["flag_b"] - vb["flag_b"], vc["flag_a"] - vc["flag_b"]
        return d1, d2
    out = {"split": split, "per_vendor": {}}
    for vendor in ("gpt", "claude"):
        cfgs = tuple(c for c in e6.CONFIGS if vendor in c)
        d1, d2 = contrasts(cfgs)
        out["per_vendor"][vendor] = {"configs": cfgs, "E13_1": A.boot(d1), "E13_2": A.boot(d2)}
    d1, d2 = contrasts(e6.CONFIGS)
    more, rest = strata["a_more_conditionals"], strata["a_not_more"]
    pick = lambda d, m: {p: d[p] for p in m if p in d}
    out["strata_difference"] = {"E13_1": diff_boot(pick(d1, more), pick(d1, rest)),
                                "E13_2": diff_boot(pick(d2, more), pick(d2, rest))}
    added = {f"{k}|{p}": {"conditionals": e13.conditionals(code) - e13.conditionals(reg[(k, p)]["program"]["b"]),
                          "lines": lines_added(reg[(k, p)]["program"]["b"], code)} for (k, p), code in bp.items()}
    out["added"] = {"per_unit": added,
                    "conditionals_median": statistics.median(v["conditionals"] for v in added.values()),
                    "lines_median": statistics.median(v["lines"] for v in added.values()),
                    "lines_max": max(v["lines"] for v in added.values())}
    if split == "test":
        (e13.REC / f"e13_secondary_{split}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    r = main(sys.argv[1] if len(sys.argv) > 1 else "dev")
    r["added"].pop("per_unit")
    print(json.dumps(r, indent=1, default=str))
