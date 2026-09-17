"""P2 — severity-threshold sweep. No model calls: re-grades archived findings only."""
import json, glob, os, random, sys
from pathlib import Path
sys.path.insert(0,"benchmarks/code"); sys.path.insert(0,"benchmarks/expertlongbench")
import report_ceiling as rc

BOOT, SEED = 10_000, 20260915

def load(base, fam):
    d=Path(f"benchmarks/code/records/{base}/cache")
    fs=sorted(f for f in glob.glob(str(d/f"holistic__{fam}__d*.jsonl")) if ".failed." not in f)
    draws={}
    for i,f in enumerate(fs,1):
        for l in Path(f).read_text().splitlines():
            if not l.strip(): continue
            r=json.loads(l)
            draws.setdefault(i,{})[r["instance_id"]]=r
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
rows=[]
for base,fam in FAMS:
    draws=load(base,fam)
    if not draws: continue
    ids=sorted(set().union(*[set(v) for v in draws.values()]))
    strat={i: draws[min(draws)][i]["stratum"] for i in ids if i in draws[min(draws)]}
    probs={i: draws[min(draws)][i].get("problem_id") or i for i in strat}
    P=[i for i in strat if strat[i]=="P"]; C=[i for i in strat if strat[i]=="C"]
    K=len(draws)
    for name,rule in RULES.items():
        kp,np_,fp_=union_rate(draws,P,rule,K); lo1,hi1=cluster_ci(fp_,probs)
        kc,nc,fc=union_rate(draws,C,rule,K);   lo2,hi2=cluster_ci(fc,probs)
        rows.append((fam,name,K,100*kp/np_,lo1,hi1,100*kc/nc,lo2,hi2))
        print(f"{fam:<14}{name:<22}{K:>2}  {100*kp/np_:>6.1f}% [{lo1:>5.1f},{hi1:>5.1f}]  {100*kc/nc:>6.1f}% [{lo2:>5.1f},{hi2:>5.1f}]")
json.dump(rows, open("/tmp/sweep.json","w"))
