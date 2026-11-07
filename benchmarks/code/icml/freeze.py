"""Pre-test freeze bundle for E1 (Amendment 4) and E6 (e6-v4.1).

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
           "e6det_units4.jsonl", "e6det_judgements2.jsonl"]
CODE = ["e1.py", "e6.py", "analyse_e1.py", "analyse_e6.py", "isolate.py", "freeze.py",
        "PREREGISTRATION-E1.md", "PREREGISTRATION-E6.md"]


def fsha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def version(cmd: list) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()[:200]
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def e6_state(kind: str) -> dict:
    import analyse_e6
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
    out = {"admitted_units": sorted(units), "population": pop, "n_required_readings": len(sched),
           "schedule_sha256": hashlib.sha256(json.dumps(sched).encode()).hexdigest(),
           "prompt_sha256": prompts,
           "shown_vendor": {pid: u["shown_route"] for pid, u in units.items()},
           "menu_first_a": {pid: u["first_a"] for pid, u in units.items()}}
    e6.set_kind("open")
    return out


def e1_state() -> dict:
    cons = e1.admitted_constructions()
    uni = e1.expected_universe("test")
    return {"retained_admissions": sorted(cons), "taxonomy_v4": e1.taxonomy2(),
            "n_required_readings": len(uni),
            "universe_sha256": hashlib.sha256(json.dumps(sorted(map(list, uni))).encode()).hexdigest()}


def build() -> dict:
    git = version(["git", "-C", str(HERE), "rev-parse", "HEAD"])
    dirty = version(["git", "-C", str(HERE), "status", "--porcelain", "--", str(HERE)])
    return {
        "records": {f: fsha(e1.REC / f) for f in RECORDS},
        "code": {f: fsha(HERE / f) for f in CODE},
        "routes": {k: v[1] for k, v in e1.ROUTES.items()},
        "versions": {"python": sys.version, "platform": platform.platform(),
                     "executor": version([str(e1.execute.EXECUTOR), "--version"]),
                     "codex": version(["codex", "--version"]), "claude": version(["claude", "--version"])},
        "git_commit": git, "git_dirty_icml": dirty,
        "e1": e1_state(), "e6_open": e6_state("open"), "e6_det": e6_state("det"),
    }


def verify() -> None:
    """Refuse unless the current state equals the frozen manifest (called before any test audit)."""
    if not MANIFEST.exists():
        raise SystemExit("no freeze manifest: run freeze.py write after the final review")
    old, state = json.loads(MANIFEST.read_text()), build()
    diffs = [k for k in old if k != "versions" and old[k] != state.get(k)]
    if diffs:
        raise SystemExit(f"freeze verification failed: {diffs}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["write", "verify"])
    a = ap.parse_args()
    state = build()
    if a.action == "write":
        if state["git_dirty_icml"]:
            raise SystemExit("commit the icml code and registrations before freezing:\n" + state["git_dirty_icml"])
        MANIFEST.write_text(json.dumps(state, indent=1, sort_keys=True))
        print("frozen:", MANIFEST, "e1 readings", state["e1"]["n_required_readings"],
              "e6 open", len(state["e6_open"]["population"]), "units /", state["e6_open"]["n_required_readings"],
              "readings; e6 det", len(state["e6_det"]["population"]), "units")
    else:
        verify()
        print("freeze verified")
