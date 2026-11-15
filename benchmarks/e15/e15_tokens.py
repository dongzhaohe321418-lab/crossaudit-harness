"""Corrected body token counts for E15's held-out pairs (review M6: `e15.body_tokens` could count an earlier, unchanged
branch). Selects the `if` whose masked body makes the two programs' trees identical, as the confinement check does.
Reporting only; e15.py stays frozen.

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/e15/e15_tokens.py
"""
import ast
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import e15                                         # noqa: E402


def differing_body_tokens(pa: str, pb: str):
    ta, tb = ast.parse(pa), ast.parse(pb)
    nodes_b = dict(e15._ifs(tb))
    for path, na in e15._ifs(ta):
        nb = nodes_b.get(path)
        if nb is None or ast.dump(na.test) != ast.dump(nb.test):
            continue
        ma, mb = ast.parse(pa), ast.parse(pb)
        dict(e15._ifs(ma))[path].body = [ast.Pass()]
        dict(e15._ifs(mb))[path].body = [ast.Pass()]
        if ast.dump(ma) == ast.dump(mb):
            return e15._tokens(na.body, pa.splitlines()), e15._tokens(nb.body, pb.splitlines())
    return None


if __name__ == "__main__":
    pairs = {f"{k}|{p}": differing_body_tokens(v["m"], v["n"]) for (k, p), v in sorted(e15.passed("test").items())}
    vals = [v for v in pairs.values() if v]
    out = {"n": len(vals), "equal": sum(a == b for a, b in vals), "m_a_longer": sum(a > b for a, b in vals),
           "per_pair": pairs}
    (e15.REC / "e15_body_tokens_test.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "per_pair"})
