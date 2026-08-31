"""Turn the raw runs into the three outcomes, kept apart deliberately.

  cannot_fire      a guard whose OWN covered lines were mutated, and which
                   stayed green for every such mutation
  mutation_missed  a guard none of whose covered lines this campaign touched;
                   says nothing about the guard, only about the campaign
  undetermined     a guard whose behaviour this instrument cannot see at all
                   (node subprocess, Swift source, threading) -- NOT dead
"""
import json, sys, collections

ctx = json.load(open(sys.argv[1]))["per_test"]
res = json.load(open(sys.argv[2]))
noprod = json.load(open(sys.argv[3]))

mutated_lines = {f"{r['file']}:{r['line']}" for r in res if "reddened" in r}
reddened_by = collections.defaultdict(list)
for r in res:
    for t in r.get("failed_tests", []):
        reddened_by[t].append(f"{r['file'].split('/crossaudit/')[-1]}:{r['line']}:{r['op']}")

def tid(c):
    parts = c.split("."); return f"{'/'.join(parts[:-1])}.py::{parts[-1]}"

cannot, missed, fired = [], [], []
for test, lines in ctx.items():
    own = set(lines) & mutated_lines
    if not own:
        missed.append(test); continue
    if tid(test) in reddened_by or any(tid(test) == k for k in reddened_by):
        fired.append(test)
    else:
        cannot.append({"test": test, "mutated_own_lines": sorted(own)[:6],
                       "n_mutated": len(own)})
out = {"fired": sorted(fired), "cannot_fire": cannot,
       "mutation_missed": sorted(missed), "undetermined_no_python_path": noprod}
json.dump(out, open(sys.argv[4], "w"), indent=1)
print(f"mutations with a result : {len(mutated_lines)}")
print(f"guards that FIRED       : {len(fired)}")
print(f"guards that CANNOT FIRE : {len(cannot)}   (own covered lines mutated, stayed green)")
print(f"MUTATION MISSED         : {len(missed)}   (campaign never touched their lines)")
print(f"UNDETERMINED            : {len(noprod)}   (no python execution path to observe)")
