"""test -> the production lines it actually executed, from coverage contexts.

This is what separates the three outcomes the boss asked to be kept apart:
  * a guard whose OWN covered lines were mutated and stayed green  -> cannot fire
  * a guard none of whose covered lines were mutated               -> mutation missed
  * a guard that executes no production lines at all               -> structural
"""
import json, sqlite3, sys, collections
from pathlib import Path

db = Path(sys.argv[1])            # .coverage
out = Path(sys.argv[2])
con = sqlite3.connect(db)
files = {r[0]: r[1] for r in con.execute("select id, path from file")}
ctxs = {r[0]: r[1] for r in con.execute("select id, context from context")}
per_test = collections.defaultdict(set)
per_line = collections.defaultdict(set)
for fid, cid, numbits in con.execute("select file_id, context_id, numbits from line_bits"):
    ctx = ctxs.get(cid, "")
    if not ctx:
        continue
    path = files[fid]
    # numbits -> line numbers
    lines = []
    for i, byte in enumerate(numbits):
        for b in range(8):
            if byte & (1 << b):
                lines.append(i * 8 + b)
    for ln in lines:
        per_test[ctx].add((path, ln))
        per_line[(path, ln)].add(ctx)
con.close()
json.dump({"per_test": {k: sorted(f"{p}:{l}" for p, l in v) for k, v in per_test.items()},
           "line_test_counts": {f"{p}:{l}": len(v) for (p, l), v in per_line.items()}},
          open(out, "w"))
print(f"tests with a context : {len(per_test)}")
print(f"production lines hit  : {len(per_line)}")
zero = [t for t, v in per_test.items() if not v]
print(f"contexts with ZERO production lines: {len(zero)}")
