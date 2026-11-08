"""Pre-test freeze bundle for E1 (Amendment 4) and E6 (e6-v4.3).

`write` records, with SHA-256 checksums: every input record file, the frozen populations, the required reading
universes, the hash of every rendered test audit prompt, the code, the registrations, the model routes, the CLI and
interpreter versions and the git commit. `verify` recomputes all of it and refuses on any difference; the audit
stages are run only after `verify` passes.

    python benchmarks/code/icml/freeze.py write
    python benchmarks/code/icml/freeze.py verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import e1
import e6

HERE = Path(__file__).resolve().parent
MANIFEST = e1.REC / "FREEZE_test.json"
RECORDS = ["split.json", "items_v3.json", "oracles_v3.json", "executions_v3.jsonl", "constructions_v3.jsonl",
           "adjudications_v3.jsonl", "taxonomy_v3.jsonl", "taxonomy_v4.jsonl", "controls_v4.jsonl",
           "generations.jsonl",
           "e6_proposals.jsonl", "e6_impls.jsonl", "e6_units.jsonl", "e6_probes.jsonl", "e6_units4.jsonl",
           "e6_judgements2.jsonl", "e6_behaviour4.jsonl",
           "e6det_proposals.jsonl", "e6det_impls.jsonl", "e6det_units.jsonl", "e6det_probes.jsonl",
           "e6det_units4.jsonl", "e6det_judgements2.jsonl",
           "e6b_proposals.jsonl", "e6b_impls.jsonl", "e6b_units.jsonl", "e6b_probes.jsonl", "e6b_units4.jsonl",
           "e6b_judgements2.jsonl", "e6b_behaviour4.jsonl", "e6det_behaviour4.jsonl", "e1_behaviour_v4.json",
           "e6_redteam.jsonl", "e6b_redteam.jsonl", "e6det_redteam.jsonl", "bridge_v4.jsonl"]
CODE = ["e1.py", "e6.py", "analyse_e1.py", "analyse_e6.py", "isolate.py", "freeze.py",
        "PREREGISTRATION-E1.md", "PREREGISTRATION-E6.md"]
BENCH = HERE.parent                                   # benchmarks/code: corpus, execution, prompts, data
SRC = HERE.parents[2] / "src" / "crossaudit"         # auditor prompt, parser, validator, rulebook, checks
REQUIRED = ("records", "code", "dependencies", "routes", "versions", "git_commit", "e1", "e6_open", "e6_open2",
            "e6_det")


def tree_sha(root: Path, patterns: tuple) -> dict:
    return {str(f.relative_to(root)): fsha(f) for pat in patterns for f in sorted(root.rglob(pat))
            if f.is_file() and "__pycache__" not in f.parts}


DEV_ONLY = {"bridge_v4.jsonl"}       # grows during the held-out run: only its development rows are pre-test inputs


def dev_rows_sha(path: Path) -> str:
    if not path.exists():
        return "missing"
    split = {i["item_id"]: i["split"] for i in json.loads(e1.ITEMS_PATH.read_text())}
    rows = sorted(l for l in path.read_text(encoding="utf-8").splitlines()
                  if l.strip() and split.get(json.loads(l).get("item_id")) == "dev")
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def fsha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def version(cmd: list) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()[:200]
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def e6_state(kind: str) -> dict:
    import analyse_e6
    previous = e6.KIND                    # P6: verification must not change the caller's selected kind
    e6.set_kind(kind)
    units = e6.units("test")
    pop = analyse_e6.population("test")
    probs = {p.problem_id: p for p in e6.problems("test")}
    sched = e6.schedule("test")
    prompts, cache = {}, {}
    for pid, prog, arm, _cfg, _k in sched:
        if (pid, prog, arm) not in cache:
            cache[(pid, prog, arm)] = e6.expected_prompt_sha(units[pid], probs[pid], prog, arm, {})
    prompts = {"|".join(k): v for k, v in sorted(cache.items())}
    out = {"admitted_units": sorted(units), "population": pop, "registered_units": e6.registered_units("test"),
           "n_required_readings": len(sched),
           "schedule_sha256": hashlib.sha256(json.dumps(sched).encode()).hexdigest(),
           "prompt_sha256": prompts,
           "shown_vendor": {pid: u["shown_route"] for pid, u in units.items()},
           "menu_first_a": {pid: u["first_a"] for pid, u in units.items()},
           "redteam_sha256": fsha(e6.REDTEAM)}
    e6.set_kind(previous)
    return out


def e1_state() -> dict:
    cons = e1.admitted_constructions()
    uni = e1.expected_universe("test")
    items = {i["item_id"]: i for i in json.loads(e1.ITEMS_PATH.read_text())}
    problems = {p.problem_id: p for p in e1.load_problems()}
    prompts = {}
    for iid, kind, arm, _a, _k in uni:
        key = f"{iid}|{kind}|{arm}"
        if key not in prompts:
            p = problems[items[iid]["problem_id"]]
            prompts[key] = e1.sha(e1.audit_prompt(p, items[iid][f"{kind}_solution"],
                                                  e1.task_text(p.spec, arm, cons.get(iid))))
    beh = e1.REC / "e1_behaviour_v4.json"
    # P6: the persisted test schedules are what stage_audit runs; bind them and require that together they are
    # exactly the required universe (they are created here, deterministically, if absent)
    main = e1.schedule("test", e1.PRIMARY_AUDITORS)
    rest = e1.schedule("test", e1.PRIMARY_AUDITORS, orig_rest=True)
    if sorted(map(tuple, main + rest)) != sorted(map(tuple, uni)) or len(main + rest) != len(uni):
        raise SystemExit("E1 test schedules do not equal the required universe")
    sched = {f: fsha(e1.REC / f) for f in ("schedule_v3_test.json", "schedule_v3_orig_test.json")}
    return {"retained_admissions": sorted(cons), "taxonomy_v4": e1.taxonomy2(), "schedule_sha256": sched,
            "n_required_readings": len(uni),
            "universe_sha256": hashlib.sha256(json.dumps(sorted(map(list, uni))).encode()).hexdigest(),
            "prompt_sha256": prompts, "behaviour_sha256": fsha(beh)}


def build() -> dict:
    git = version(["git", "-C", str(HERE), "rev-parse", "HEAD"])
    dirty = version(["git", "-C", str(HERE), "status", "--porcelain", "--", str(HERE)])
    return {
        "records": {f: (dev_rows_sha if f in DEV_ONLY else fsha)(e1.REC / f) for f in RECORDS},
        "code": {f: fsha(HERE / f) for f in CODE},
        "dependencies": {"benchmarks_code": tree_sha(BENCH, ("*.py",)), "corpus_data": tree_sha(BENCH / "data", ("*",)),
                         "crossaudit_src": tree_sha(SRC, ("*.py", "*.md", "*.yml", "*.yaml", "*.json")),
                         "audit_project": tree_sha(e1.REC / "project", ("*",))},
        "routes": {k: v[1] for k, v in e1.ROUTES.items()},
        "versions": {"python": sys.version, "platform": platform.platform(),
                     "executor": version([str(e1.execute.EXECUTOR), "--version"]),
                     "codex": version(["codex", "--version"]), "claude": version(["claude", "--version"]),
                     "venv_packages": subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True,
                                                     text=True).stdout,
                     "executor_packages": subprocess.run([str(e1.execute.EXECUTOR), "-m", "pip", "freeze"],
                                                         capture_output=True, text=True).stdout},
        "git_commit": git, "git_dirty_icml": dirty,
        "e1": e1_state(), "e6_open": e6_state("open"), "e6_open2": e6_state("open2"), "e6_det": e6_state("det"),
    }


def check_schema(state: dict) -> None:
    missing_keys = [k for k in REQUIRED if k not in state]
    missing_files = [f for f, h in state["records"].items() if h == "missing"] + \
                    [f for f, h in state["code"].items() if h == "missing"]
    if missing_keys or missing_files:
        raise SystemExit(f"freeze schema: missing keys {missing_keys}, missing files {missing_files}")


def verify() -> None:
    """Refuse unless the current state, versions included, equals the frozen manifest (called before any test
    audit)."""
    if not MANIFEST.exists():
        raise SystemExit("no freeze manifest: run freeze.py write after the final review")
    old, state = json.loads(MANIFEST.read_text()), build()
    check_schema(old)
    diffs = [k for k in REQUIRED if old.get(k) != state.get(k)]
    if diffs:
        raise SystemExit(f"freeze verification failed: {diffs}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["write", "verify"])
    a = ap.parse_args()
    state = build()
    if a.action == "write":
        check_schema(state)
        if state["git_dirty_icml"]:
            raise SystemExit("commit the icml code and registrations before freezing:\n" + state["git_dirty_icml"])
        MANIFEST.write_text(json.dumps(state, indent=1, sort_keys=True))
        print("frozen:", MANIFEST, "e1 readings", state["e1"]["n_required_readings"],
              "e6 open", len(state["e6_open"]["population"]), "units /", state["e6_open"]["n_required_readings"],
              "readings; e6 det", len(state["e6_det"]["population"]), "units")
    else:
        verify()
        print("freeze verified")
