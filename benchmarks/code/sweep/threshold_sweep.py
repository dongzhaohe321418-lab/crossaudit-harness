"""P2 — severity-threshold sweep. No model calls: re-grades archived findings only."""
import json, glob, os, random, sys
from pathlib import Path
sys.path.insert(0,"benchmarks/code"); sys.path.insert(0,"benchmarks/expertlongbench")
import report_ceiling as rc

BOOT, SEED = 10_000, 20260915
COMMON_K = 4          # the largest depth every family reaches (round 1 of the review)

# Round 1 of the cross-vendor review found this loader silently changed both the readings and
# the population, which invalidated every cross-family figure in the first version of the
# report:
#
#   * it globbed ONE cache directory and renumbered what it found with `enumerate(fs, 1)`.
#     `records/ceiling/cache` holds only draws 4-8 of `cross`, so "cross at K = 5" was draws
#     4 to 8 read as 1 to 5. Draws 1-3 are committed, in `records/explore/cache`, and
#     `report_ceiling3.load_draws` has always known to look there.
#   * it took the population from `draws[min(draws)]` -- whichever file sorted first. For
#     `self` that is a partial draw of 172 rows, so its denominators were 54 P and 118 C
#     against 110 and 150 everywhere else in this programme.
#
# The report's sentence "each family at its own K, because that is what the archive holds"
# was therefore false: the archive holds 8, 8, 4, 8, 4. This now uses the same multi-location
# loading and the same frozen scope as every other report here.
CACHES = ("explore", "ceiling", "ceiling3")


def load(base, fam, scope):
    """draw -> instance -> RAW row, over every source this programme writes, at the true draw number.

    `explore.load_detector` is the canonical multi-location reader, and it cannot be used here:
    it returns `{flagged, cost_usd, source, cost_reconstructed}` and drops `model_blockers` and
    `model_findings`, which are the two fields a severity sweep re-grades. So this repeats its
    source order -- the committed inherited arm first, then each cache directory -- while keeping
    the whole row. The inherited arms were checked to carry both counts before this was written;
    if one ever does not, the instance is dropped loudly below rather than silently.
    """
    import explore
    draws = {}
    for draw in range(1, 9):
        key = ("holistic", fam, draw)
        found = {}
        src = explore.FREE_SOURCES.get(key)
        if src:
            path, mode, _label = src
            for line in (explore.RECORDS / path).read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                iid = row["instance_id"] if mode == "instance" else f"b1:{row['problem_id']}"
                if iid in scope and row.get("ok", True):
                    found[iid] = row
        for directory in CACHES:
            cache = Path(f"benchmarks/code/records/{directory}/cache/holistic__{fam}__d{draw}.jsonl")
            if not cache.exists():
                continue
            for line in cache.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("instance_id") in scope and row.get("ok", True):
                    found[row["instance_id"]] = row
        ungradeable = [i for i, r in found.items()
                       if "model_blockers" not in r or "model_findings" not in r]
        if ungradeable:
            print(f"  !! {fam} d{draw}: {len(ungradeable)} rows carry no severity counts and "
                  f"cannot be re-graded; first: {ungradeable[0]}")
            for i in ungradeable:
                found.pop(i)
        if found:
            draws[draw] = found
    return draws

RULES = {
    "blocker>=1 (shipped)": lambda r: (r.get("model_blockers") or 0) >= 1,
    "blocker>=2":           lambda r: (r.get("model_blockers") or 0) >= 2,
    "any finding>=1":       lambda r: (r.get("model_findings") or 0) >= 1,
    "any finding>=2":       lambda r: (r.get("model_findings") or 0) >= 2,
}

def union_rate(draws, ids, rule, K):
    ks=sorted(draws)[:K]
    hit=[i for i in ids if any(rule(draws[k][i]) for k in ks if i in draws[k])]
    return len(hit), len(ids), {i: (i in set(hit)) for i in ids}

def cluster_ci(flags, probs):
    by={}
    for i,f in flags.items(): by.setdefault(probs[i],[]).append(int(f))
    keys=sorted(by); rng=random.Random(SEED); out=[]
    for _ in range(BOOT):
        a=c=0
        for _ in range(len(keys)):
            v=by[keys[rng.randrange(len(keys))]]; a+=sum(v); c+=len(v)
        if c: out.append(100*a/c)
    out.sort(); return rc.percentile(out,0.025), rc.percentile(out,0.975)

FAMS=[("ceiling","cross"),("ceiling","self"),("ceiling","astra"),
      ("ceiling3","self-strong"),("ceiling3","self-frontier")]
print(f"{'family':<14}{'rule':<22}{'K':>2}  {'recall P':>22}  {'FP on C':>22}")
print("-"*90)
# The scope is the study's frozen audit set, not whatever the first file happened to hold.
instances = rc.load_instances()
audit_set = rc.load_audit_set()
SCOPE = [i for i in audit_set if instances[i]["stratum"] in ("P", "C")]
P_ALL = [i for i in SCOPE if instances[i]["stratum"] == "P"]
C_ALL = [i for i in SCOPE if instances[i]["stratum"] == "C"]
PROBS = {i: instances[i].get("problem_id") or i for i in SCOPE}
print(f"scope: {len(P_ALL)} P, {len(C_ALL)} C\n")

rows=[]
K_USED={}
for base,fam in FAMS:
    draws=load(base,fam,set(SCOPE))
    if not draws: continue
    # A draw counts only where it covers the whole scope; a partial draw is reported, not used.
    complete=[d for d in sorted(draws) if len(draws[d])==len(SCOPE)]
    partial=[d for d in sorted(draws) if d not in complete]
    if partial:
        print(f"  {fam}: partial draws ignored: "
              + ", ".join(f"d{d}={len(draws[d])}/{len(SCOPE)}" for d in partial))
    draws={d: draws[d] for d in complete}
    if not draws: continue
    P, C, probs = P_ALL, C_ALL, PROBS
    K=max(draws)
    K_USED[fam]=K
    for name,rule in RULES.items():
        kp,np_,fp_=union_rate(draws,P,rule,K); lo1,hi1=cluster_ci(fp_,probs)
        kc,nc,fc=union_rate(draws,C,rule,K);   lo2,hi2=cluster_ci(fc,probs)
        rows.append((fam,name,K,100*kp/np_,lo1,hi1,100*kc/nc,lo2,hi2))
        print(f"{fam:<14}{name:<22}{K:>2}  {100*kp/np_:>6.1f}% [{lo1:>5.1f},{hi1:>5.1f}]  {100*kc/nc:>6.1f}% [{lo2:>5.1f},{hi2:>5.1f}]")
# Round 1 required a COMMON-K table beside the complete-ladder one: families read at their own
# K (8, 8, 4, 8, 4) cannot isolate auditor identity, because a family read four times is not
# being asked the same question as one read eight times. K = 4 is the largest depth every
# family reaches. The rate is averaged EXACTLY over all C(K_max, 4) four-draw subsets, so a
# family with eight draws is not advantaged by a lucky choice of which four to use.
print(f"\n{'family':<14}{'rule':<22}{'K':>2}  {'recall P @ common K=4':>24}  {'FP on C @ K=4':>22}")
print("-"*90)
common = []
for base, fam in FAMS:
    draws = load(base, fam, set(SCOPE))
    draws = {d: r for d, r in draws.items() if len(r) == len(SCOPE)}
    if len(draws) < COMMON_K:
        print(f"{fam:<14}{'--':<22}{len(draws):>2}  fewer than {COMMON_K} complete draws")
        continue
    for name, rule in RULES.items():
        vals = []
        for ids in (P_ALL, C_ALL):
            ks = [sum(1 for d in sorted(draws) if rule(draws[d][i])) for i in ids]
            vals.append(100 * rc.union_curve(ks, len(draws))[COMMON_K - 1])
        common.append((fam, name, COMMON_K, vals[0], vals[1]))
        print(f"{fam:<14}{name:<22}{COMMON_K:>2}  {vals[0]:>23.1f}%  {vals[1]:>21.1f}%")

# Round 1: this wrote to /tmp and the committed record was copied across by hand, so the
# record and the code that made it could drift without anything noticing. It writes to the
# record now, with the scope and the per-family K it actually used, so a reader can see both.
out = {"scope": {"n_P": len(P_ALL), "n_C": len(C_ALL)},
       "bootstrap": {"seed": SEED, "reps": BOOT},
       "k_by_family": K_USED,
       "rules": list(RULES),
       "rows": rows,
       "common_k_subset_averaged": {"k": COMMON_K, "rows": common}}
Path("benchmarks/code/records/threshold_sweep.json").write_text(
    json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"\nwrote records/threshold_sweep.json: {len(rows)} rows, "
      f"K by family {K_USED}")
