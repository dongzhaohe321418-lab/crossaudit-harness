"""E10: does stating the requirement add more than pointing at the behaviour? (PREREGISTRATION-E10.md)

On E6's frozen open units (open and open2) and programs, with E6's audit prompt, auditor configurations at the low
budget (E6's sentence configurations), witness scoring and analysis code, four arms are run afresh and interleaved:
none (the task alone), pointer (the task plus a note naming the input class the rules concern, with no rule),
sentence-a and sentence-b (one rule stated as an ordinary requirement, E6's sentence arms). Records are E10's own;
E6's records are read-only. E6's modules are reused by pointing them at E10's record files and arms.

    python benchmarks/e10/e10.py freeze|run|analyse <split> [--limit N]   (--limit: development pilot only)
"""
from __future__ import annotations

import argparse
import hashlib
import re
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "code"), str(HERE.parent / "code" / "icml")]
import e1  # noqa: E402
import e6  # noqa: E402

REC = HERE / "records"
PROTOCOL = "e10-v1"
ARMS = ("none", "pointer", "sentence-a", "sentence-b")
POINTER = "\n\nAdditional note: pay particular attention to how the function handles the following kind of input: {cls}"
WORKERS = 4
LIMIT: int | None = None

_set_kind, _arm_text, _registered = e6.set_kind, e6.arm_text, e6.registered_units
ORIGINAL = (e6.set_kind, e6.arm_text, e6.registered_units, e6.configs_for, e6.PROTOCOL)


def set_kind(kind: str) -> None:
    """E6's set_kind, then E10's record files, arms, protocol and configurations."""
    _set_kind(kind)
    pre = {"open": "open", "open2": "open2"}.get(kind)
    if pre:
        e6.AUD, e6.AUD_RAW = REC / f"{pre}_audits.jsonl", REC / f"{pre}_audits_raw.jsonl"
        e6.WIT = REC / f"{pre}_witnesses.jsonl"
        e6.ARMS = ARMS


CLAUSE = re.compile(r",?\s+(?=(?:for which|whose|requiring|but)\b)")
UNCERTAIN = re.compile(r"(?i)unspecified|ambiguous|\bmay\b|\beither\b|convention|\bdiffers?\b|requiring")


def neutral_class(cls: str) -> str:
    """The input class only: the constructor's description cut before its first clause (introduced by "for which",
    "whose", "requiring" or "but") that says what is unspecified or names alternatives; clauses that only define the
    class are kept."""
    text = cls.strip().rstrip(" .")
    cuts = [m.start() for m in CLAUSE.finditer(text)] + [len(text)]
    for i, start in enumerate(cuts[:-1]):
        if UNCERTAIN.search(text[start:cuts[i + 1]]):
            return text[:start].rstrip(" ,")
    return text if not UNCERTAIN.search(text) else text


def arm_text(u: dict, arm: str) -> str:
    if arm == "pointer":
        return POINTER.format(cls=neutral_class(u["class"]))
    return _arm_text(u, arm)


def registered_units(split: str) -> list:
    return _registered(split)        # a development pilot's --limit acts on analyse_e6.population, used by both


def sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def state(split: str) -> dict:
    out = {"split": split, "protocol": PROTOCOL, "arms": list(ARMS), "pointer": sha(POINTER),
           "configs": list(e6.SENTENCE_CONFIGS), "routes": {c: list(e1.ROUTES[c][1]) for c in e6.SENTENCE_CONFIGS},
           "code": {f: sha((HERE / f).read_text()) for f in ("e10.py", "PREREGISTRATION-E10.md")},
           "e6_code": {f: sha((HERE.parent / "code" / "icml" / f).read_text())
                       for f in ("e6.py", "e1.py", "analyse_e6.py")}, "units": {}, "n_required_readings": 0}
    prev = e6.KIND                         # called from inside E6's stages (via freeze.verify): restore the kind
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        us = e6.units(split)
        for pid in e6.registered_units(split):
            out["units"][f"{kind}|{pid}"] = sha(json.dumps([us[pid]["program"], us[pid]["oracle"], us[pid]["class"],
                                                            [arm_text(us[pid], a) for a in ARMS]]))
        out["n_required_readings"] += len(e6.schedule(split))
    e6.set_kind(prev)
    return out


def manifest(split: str) -> Path:
    return REC / f"FREEZE10_{split}.json"


ADDED = re.compile(r"^(e9|e10)/|^code/icml/e6_exception_sensitivity\.py$")   # files added after E6's freeze


def verify_e6_frozen() -> None:
    """E6's frozen bundle, computed under E6's own configuration (E10's patches are lifted while it is built): every
    field except the repository commit; dependency files must all match, and the benchmark tree may differ from the
    frozen one only by the files added since (E9, E10, the exception sensitivity)."""
    import freeze
    prev = e6.KIND
    import analyse_e6
    saved = (e6.set_kind, e6.arm_text, e6.registered_units, e6.configs_for, e6.PROTOCOL)
    saved_pop = analyse_e6.population
    e6.set_kind, e6.arm_text, e6.registered_units, e6.configs_for, e6.PROTOCOL = ORIGINAL
    analyse_e6.population = ORIGINAL_POPULATION
    try:
        old, now = json.loads(freeze.MANIFEST.read_text()), _freeze_build()
    finally:
        e6.set_kind, e6.arm_text, e6.registered_units, e6.configs_for, e6.PROTOCOL = saved
        analyse_e6.population = saved_pop
        e6.set_kind(prev)
    diffs = [k for k in freeze.REQUIRED if k not in ("git_commit", "dependencies") and old.get(k) != now.get(k)]
    od, nd = old["dependencies"], now["dependencies"]
    for k in od:
        if k == "benchmarks_code":
            extra = {f for f in nd[k] if f not in od[k]}
            if any(nd[k].get(f) != h for f, h in od[k].items()) or any(not ADDED.search(f) for f in extra):
                diffs.append("dependencies.benchmarks_code")
        elif od[k] != nd[k]:
            diffs.append(f"dependencies.{k}")
    if diffs:
        raise SystemExit(f"E6 freeze verification failed: {diffs}")


def canonical(x) -> str:
    return json.dumps(x, sort_keys=True)


def verify_e10() -> None:
    verify_e6_frozen()
    m = manifest("test")
    if not m.exists() or canonical(json.loads(m.read_text())) != canonical(_state_test()):
        raise SystemExit("E10 freeze verification failed")


def install() -> None:
    """Point E6's stages at E10 (module globals are looked up at call time)."""
    import freeze
    global _freeze_build, _state_test
    _freeze_build = freeze.build
    _state_test = lambda: state("test")
    e6.set_kind, e6.arm_text, e6.registered_units = set_kind, arm_text, registered_units
    e6.configs_for = lambda arm: e6.SENTENCE_CONFIGS
    e6.PROTOCOL = PROTOCOL
    freeze.verify = verify_e10
    import analyse_e6
    global ORIGINAL_POPULATION
    ORIGINAL_POPULATION = analyse_e6.population
    analyse_e6.population = lambda split: (ORIGINAL_POPULATION(split)[:LIMIT] if (LIMIT and split != "test")
                                           else ORIGINAL_POPULATION(split))


def run(split: str) -> None:
    REC.mkdir(exist_ok=True)
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        if not e6.registered_units(split):
            continue
        e6.stage_audit(split, WORKERS)
        e6.stage_witness(split, WORKERS)
    e6.set_kind("open")


EXCEPTION_UNITS = ("Mbpp/93", "Mbpp/623")    # rule A requires an exception: no contract-A credit (E6 appendix)


def located(split: str) -> dict:
    """Descriptive: share of flagging readings, per arm, whose witnesses include a call that is valid, in the class and
    in the interface, whether or not the stated expected value is right (scorer output, no rescoring)."""
    out = {}
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        wit = {}
        for w in e1.load(e6.WIT):
            if not w.get("infra"):
                wit.setdefault(tuple(w["key"]), []).append(w)
        for r in e1.load(e6.AUD):
            if r.get("ok") and r["split"] == split and r.get("protocol") == PROTOCOL and r.get("flagged"):
                hit = any(x.get("valid") and x.get("in_class") and x.get("in_interface")
                          for w in wit.get(tuple(r["key"]), []) for x in w["results"])
                out.setdefault(r["key"][2], []).append(hit)
    e6.set_kind("open")
    return {arm: {"n_flagging": len(v), "located": 100 * sum(v) / len(v)} for arm, v in sorted(out.items()) if v}


def analyse(split: str) -> dict:
    import analyse_e6 as A
    if split == "test":
        verify_e10()
    cells, units, status, beh = A.merged_open(split, allow_incomplete=False)
    S, t = e6.SENTENCE_CONFIGS, 1
    res = {"split": split, "protocol": PROTOCOL, "n_units": len(units), "completeness": status}
    lv, uv = {}, {}
    for g in ("none", "pointer", "sentence"):
        lv[g], uv[g] = A.level(cells, units, g, S, t)
    res["levels"] = {g: {m: lv[g][m] for m in ("tpr", "fpr", "cov")} for g in lv}
    res["E10_1_sentence_minus_pointer"] = A.contrast(cells, units, "sentence", "pointer", S, S, "cov", t)
    res["E10_2_pointer_minus_none"] = A.contrast(cells, units, "pointer", "none", S, S, "cov", t)
    res["sentence_minus_none"] = A.contrast(cells, units, "sentence", "none", S, S, "cov", t)
    res["flag_rate_pointer_minus_none"] = A.contrast(cells, units, "pointer", "none", S, S, "tpr", t)
    for name, f in (("flag_pref", lambda v: v["flag_a"] - v["flag_b"]),
                    ("convention_advantage", lambda v: (v["r_b"] - v["r_a"]) / 2)):
        res[name] = {}
        for g in ("none", "pointer"):
            vals = {k: f(v) for k, v in uv[g].items()}
            res[name][g] = A.with_bounds(A.boot(vals), vals, len(units) - len(vals), lo=-1.0 if name == "flag_pref"
                                         else -0.5, hi=1.0 if name == "flag_pref" else 0.5)
    res["per_config"] = {c: {"E10_1": A.contrast(cells, units, "sentence", "pointer", (c,), (c,), "cov", t),
                             "E10_2": A.contrast(cells, units, "pointer", "none", (c,), (c,), "cov", t)} for c in S}
    keep = [u for u in units if u not in EXCEPTION_UNITS]
    res["sensitivity_without_exception_units"] = {
        "n_units": len(keep),
        "E10_1": A.contrast(cells, keep, "sentence", "pointer", S, S, "cov", t),
        "E10_2": A.contrast(cells, keep, "pointer", "none", S, S, "cov", t)}
    res["located"] = located(split)
    e1_, e2_ = res["E10_1_sentence_minus_pointer"], res["E10_2_pointer_minus_none"]
    est = lambda d, f: d.get(f) is not None
    res["verdicts"] = {
        "E10_1": (bool(e1_["lo"] > 0 and e1_["bound_low"] > 0) if est(e1_, "lo") and est(e1_, "bound_low")
                  else "not estimable"),
        # registered interpretation margins (PREREGISTRATION-E10.md): 20 points
        "pointer_adds_little": bool(est(e2_, "hi") and e2_["hi"] < 20),
        "sentence_close_to_pointer": bool(est(e1_, "hi") and e1_["hi"] < 20)}
    if split == "test":
        (REC / f"e10_results_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["freeze", "run", "analyse"])
    ap.add_argument("split")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.split == "test" and a.limit:
        raise SystemExit("--limit is for the development pilot only")
    LIMIT = a.limit
    install()
    if a.action == "freeze":
        REC.mkdir(exist_ok=True)
        if a.split == "test" and (REC / "open_audits.jsonl").exists() and any(
                r.get("split") == "test" for r in e1.load(REC / "open_audits.jsonl")):
            raise SystemExit("held-out E10 records exist: the freeze cannot be rewritten")
        manifest(a.split).write_text(json.dumps(state(a.split), indent=1, sort_keys=True))
        print("E10 frozen:", manifest(a.split))
    elif a.action == "run":
        run(a.split)
    else:
        print(json.dumps(analyse(a.split), indent=1, default=str))
