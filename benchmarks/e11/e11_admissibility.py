"""E11-3 (descriptive): E9's admissibility analysis on E11's units, with E11-1 and E11-2 in place of E6's estimands on
the accepted subsets (E9's `subset_e6` reads E6's own results and does not apply to E11). Reads frozen records only."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "e9")]
import e11                                        # noqa: E402


def subset_e11(split: str, keep: set) -> dict:
    import analyse_e6 as A
    if not keep:
        return {"n_units": 0, "estimable": False}
    cells, units, _, _ = A.merged_open(split, allow_incomplete=False)
    units = [u for u in units if u in keep]
    S, t = e11.e6.SENTENCE_CONFIGS, 1
    out = {"n_units": len(units), "estimable": True}
    for name, other in (("E11_1_sentence_minus_none", "none"), ("E11_2_sentence_minus_pointer", "pointer")):
        d = A.contrast(cells, units, "sentence", other, S, S, "cov", t)
        out[name] = {f: d.get(f) for f in ("est", "lo", "hi", "n", "bound_low", "bound_high")}
    return out


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "dev"
    e11.install()
    e11.install_audit()
    import e9
    e9.REC = e11.REC / "e9"
    e9.verify = lambda s: e11.verify() if s == "test" else None
    e9.subset_e6 = subset_e11
    res = e9.analyse(split, with_e6=True)
    if split == "test":
        (e11.REC / "e9" / f"e11_admissibility_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))
