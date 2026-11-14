"""E11's registered descriptive reports, outside the frozen analysis: edit sizes (lines differing from the reference),
problem-level effects and leave-one-problem-out estimates for E11-1 and E11-2 (PREREGISTRATION-E11.md, Power and
interpretation). Reads frozen records only; on the held-out split it verifies the population freeze first."""
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import e11                                        # noqa: E402  (installs E6's paths)


def changed_lines(a: str, b: str) -> int:
    norm = lambda s: [l.rstrip() for l in s.strip().splitlines() if l.strip()]
    return sum(1 for d in difflib.ndiff(norm(a), norm(b)) if d[:1] in "+-")


def edit_sizes(split: str) -> dict:
    out = {}
    for kind in ("open", "open2"):
        e11.e6.set_kind(kind)
        us = e11.e6.units(split)
        probs = {p.problem_id: p for p in e11.e6.problems(split)}
        for pid in e11.e6.registered_units(split):
            p = probs[pid]
            ref = e11.strip_docstring(p.canonical_solution, p.entry_point)
            out[pid] = {c: changed_lines(ref, us[pid]["program"][c]) for c in "ab"}
    e11.e6.set_kind("open")
    return out


def report(split: str) -> dict:
    import analyse_e6 as A
    if split == "test":
        e11.verify()
    cells, units, _, _ = A.merged_open(split, allow_incomplete=False)
    S, t = e11.e6.SENTENCE_CONFIGS, 1
    res = {"split": split, "n_units": len(units), "edit_lines": edit_sizes(split)}
    sizes = sorted(v for d in res["edit_lines"].values() for v in d.values())
    res["edit_lines_median"] = sizes[len(sizes) // 2] if sizes else None
    res["edit_lines_max"] = sizes[-1] if sizes else None
    for name, other in (("E11_1", "none"), ("E11_2", "pointer")):
        per = {}
        for pid in units:
            x, y = A.unit_value(cells, pid, "sentence", S, t), A.unit_value(cells, pid, other, S, t)
            per[pid] = None if x is None or y is None else 100 * (x["cov"] - y["cov"])
        loo = {pid: A.contrast(cells, [u for u in units if u != pid], "sentence", other, S, S, "cov", t)
               for pid in units}
        res[name] = {"per_problem": per,
                     "leave_one_out": {pid: {k: d.get(k) for k in ("est", "lo", "hi", "bound_low")}
                                       for pid, d in loo.items()},
                     "leave_one_out_min_lo": min((d["lo"] for d in loo.values() if d.get("lo") is not None),
                                                 default=None)}
    if split == "test":
        (e11.REC / f"e11_report_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    e11.install()
    e11.install_audit()
    print(json.dumps(report(sys.argv[1] if len(sys.argv) > 1 else "dev"), indent=1, default=str))
