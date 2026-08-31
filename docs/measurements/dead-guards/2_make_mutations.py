"""Generate semantically meaningful mutations on lines the suite actually runs.

Only lines with coverage are mutated: a mutation on dead production code tells
you nothing about a guard, and would inflate "cannot fire" with sites no test
was ever supposed to reach.

Operators are chosen to change BEHAVIOUR, not to break syntax -- a SyntaxError
reddens everything and proves nothing.
"""
import ast, json, random, sys
from pathlib import Path

cov = json.load(open(sys.argv[1]))
root = Path(sys.argv[2])
out = Path(sys.argv[3])
covered = {}
for line, n in cov["line_test_counts"].items():
    path, ln = line.rsplit(":", 1)
    covered.setdefault(path, {})[int(ln)] = n

OPS = [
    ("cmp_eq_ne",   "==", "!="),
    ("cmp_ne_eq",   "!=", "=="),
    ("cmp_lt_le",   " < ", " <= "),
    ("cmp_ge_gt",   " >= ", " > "),
    ("bool_true",   "True", "False"),
    ("bool_false",  "False", "True"),
    ("and_or",      " and ", " or "),
    ("not_drop",    "not ", ""),
]
muts = []
for path, lines in sorted(covered.items()):
    p = Path(path)
    if not p.is_file() or "/crossaudit/" not in str(p):
        continue
    try:
        src = p.read_text().splitlines()
    except OSError:
        continue
    for ln, ntests in sorted(lines.items(), key=lambda kv: -kv[1]):
        if ln <= 0 or ln > len(src):
            continue
        text = src[ln - 1]
        stripped = text.strip()
        if (not stripped or stripped.startswith("#") or stripped.startswith('"')
                or stripped.startswith("'") or stripped.startswith("def ")
                or stripped.startswith("class ") or stripped.startswith("import ")
                or stripped.startswith("from ")):
            continue
        for name, a, b in OPS:
            if a in text:
                muts.append({"file": str(p), "line": ln, "op": name,
                             "before": text, "after": text.replace(a, b, 1),
                             "tests_covering": ntests})
                break
random.Random(20260831).shuffle(muts)
# spread across files: at most N per file, so one big module cannot dominate
per_file, chosen = {}, []
CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 6
for m in muts:
    k = m["file"]
    if per_file.get(k, 0) >= CAP:
        continue
    per_file[k] = per_file.get(k, 0) + 1
    chosen.append(m)
json.dump(chosen, open(out, "w"), indent=1)
print(f"candidate sites : {len(muts)}")
print(f"selected        : {len(chosen)} across {len(per_file)} files (cap {CAP}/file)")
