"""Apply each mutation, run ONLY the tests that execute the mutated line, revert.

Running only the covering tests is what makes this affordable and is also what
makes the result honest: a test that does not execute the line cannot be
expected to notice, and counting it as "did not fire" would manufacture dead
guards out of a coarse instrument.
"""
import json, subprocess, sys, collections, time
from pathlib import Path

ctx = json.load(open(sys.argv[1]))["per_test"]
muts = json.load(open(sys.argv[2]))
tree = Path(sys.argv[3])
out = Path(sys.argv[4])
budget = int(sys.argv[5]) if len(sys.argv) > 5 else 150
PY_BIN = "/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python"

line_tests = collections.defaultdict(set)
for test, lines in ctx.items():
    for l in lines:
        line_tests[l].add(test)

def tid(ctxname):
    parts = ctxname.split(".")
    fn = parts[-1]
    mod = ".".join(parts[:-1])
    return f"{mod.replace('.', '/')}.py::{fn}"

# leverage-first: mutate lines many tests depend on, capped per file
scored = []
for m in muts:
    key = f"{m['file']}:{m['line']}"
    tests = line_tests.get(key, set())
    if tests:
        scored.append((len(tests), m, sorted(tests)))
scored.sort(key=lambda x: -x[0])
per_file, chosen = collections.Counter(), []
for n, m, tests in scored:
    if per_file[m["file"]] >= 4:
        continue
    per_file[m["file"]] += 1
    chosen.append((m, tests))
    if len(chosen) >= budget:
        break
print(f"running {len(chosen)} mutations over {len(set(t for _, ts in chosen for t in ts))} distinct tests",
      flush=True)

results = []
sink = open(str(out) + "l", "w")
for i, (m, tests) in enumerate(chosen, 1):
    p = Path(m["file"])
    src = p.read_text()
    lines = src.splitlines(keepends=True)
    orig = lines[m["line"] - 1]
    if orig.rstrip("\n") != m["before"]:
        results.append({**m, "outcome": "skipped: line drifted", "tests": tests})
        continue
    lines[m["line"] - 1] = m["after"] + ("\n" if orig.endswith("\n") else "")
    p.write_text("".join(lines))
    try:
        ids = [tid(t) for t in tests][:40]
        r = subprocess.run([PY_BIN, "-m", "pytest", "-q", "-p", "no:randomly",
                            "--no-header", "-x" if False else "--tb=no", *ids],
                           cwd=tree, capture_output=True, text=True,
                           env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin",
                                "HOME": str(Path.home())}, timeout=300)
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        failed = [ln.split()[1] for ln in r.stdout.splitlines()
                  if ln.startswith("FAILED") and len(ln.split()) > 1]
        results.append({**m, "tests": tests, "n_tests": len(ids),
                        "reddened": bool(failed) or r.returncode != 0,
                        "failed_tests": failed, "summary": tail})
    except subprocess.TimeoutExpired:
        results.append({**m, "tests": tests, "outcome": "timeout"})
    finally:
        p.write_text(src)
    sink.write(json.dumps(results[-1]) + "\n"); sink.flush()
    if i % 10 == 0:
        print(f"  {i}/{len(chosen)}", flush=True)
json.dump(results, open(out, "w"), indent=1)
red = sum(1 for r in results if r.get("reddened"))
print(f"\nmutations run: {len(results)}   reddened: {red}   survived: {len(results)-red}")
