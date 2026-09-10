"""Study 19 — the manifest EXPERIMENT_RECORD §2 requires, from recorded evidence, after the run.

    python benchmarks/code/ceiling3b/finalise_manifest.py --run <archive dir>

code: the preregistration commit and the commits at each amendment, with the working tree's
status at each (from git); data: the corpus files' digests and licence, the frozen audit set's
digest; models: every role, provider, base URL, sampling and reasoning settings (from the
projects' crossaudit.yml and the ledgers); seed: the bootstrap seed and the sheet's shuffle seed
(instance selection is study 2's frozen audit set, not seeded here); time: UTC start and end of
every arm's draws from the ledgers; environment: Python, OS, package versions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
REPO = CODE.parent.parent
sys.path.insert(0, str(REPO / "src"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(REPO), capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    args = ap.parse_args()
    run = args.run
    prereg = CODE / "ceiling3b" / "PREREGISTRATION.md"
    commits = [line.split(" ", 1) for line in git("log", "--format=%H %cI %s", "--", str(prereg.relative_to(REPO))).splitlines()]
    code = {"preregistration_and_amendment_commits": [{"sha": c[0], "when_and_subject": c[1]} for c in reversed(commits)],
            "working_tree_status_now": git("status", "--porcelain"),
            "head_now": git("rev-parse", "HEAD"),
            "files_this_study_added": {str(p.relative_to(REPO)): sha(p) for p in sorted((CODE / "ceiling3b").glob("*")) if p.is_file()}
            | {str(p.relative_to(REPO)): sha(p) for p in (CODE / "ceiling3b.py", CODE / "report_ceiling3b.py")}}
    data_dir = CODE / "data"
    data = {"corpus": {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(data_dir.glob("*.jsonl"))} if data_dir.exists() else "data/ not present",
            "licence": "EvalPlus HumanEval+ / MBPP+ (Apache-2.0); solutions are study 2's, frozen",
            "audit_set_sha256": sha(CODE / "records" / "study2" / "audit_set.json"),
            "instances_sha256": sha(CODE / "records" / "study2" / "instances.jsonl"),
            "solutions": {p.name: sha(p) for p in sorted((run / "study2-inputs").glob("solutions-*.jsonl"))}}
    models = {}
    times = {}
    for proj in sorted((run / "projects").glob("project-holistic__*")):
        arm = proj.name.split("project-holistic__")[1]
        cfg = (proj / "crossaudit.yml").read_text(encoding="utf-8") if (proj / "crossaudit.yml").exists() else ""
        ledger = proj / ".crossaudit" / "usage.jsonl"
        ev = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
        import datetime as _dt
        def iso(t):
            t = float(t); t = t / 1000 if t > 1e11 else t      # the ledger stamps epoch milliseconds
            return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).isoformat()
        ts = sorted(iso(e.get("t")) for e in ev if e.get("t"))
        models[arm] = {"config_sha256": hashlib.sha256(cfg.encode()).hexdigest(),
                       "auditor": {"vendor": "anthropic", "model": "claude-sonnet-4-6", "provider": "anthropic",
                                   "base_url": "vendor default", "reasoning_effort": "unset (product default)",
                                   "temperature": "adapter default for the model's capability card (0 for Sonnet 4.6)"},
                       "generator": "unset — the same-vendor bypass of ceiling 1's self family, confined to the harness",
                       "constitution_sha256": sha(proj / "AUDIT_RULES.md") if (proj / "AUDIT_RULES.md").exists() else None,
                       "ledger_calls": len(ev), "ledger_usd": round(sum(float(e.get("api_value_usd") or 0) for e in ev), 6)}
        times[arm] = {"first_call_utc": ts[0] if ts else None, "last_call_utc": ts[-1] if ts else None}
    seeds = {"bootstrap_seed": 20260912, "bootstrap_reps": 10000, "sheet_shuffle_seed": 20260912,
             "instance_selection": "study 2's frozen audit set (records/study2/audit_set.json); no selection seeded here"}
    env = {"python": sys.version.split()[0], "platform": platform.platform()}
    try:
        from importlib.metadata import version
        env["packages"] = {p: version(p) for p in ("crossaudit", "pytest") if True}
    except Exception:  # noqa: BLE001
        pass
    out = {"study": "study19 / ceiling 3b", "preregistration": str(prereg.relative_to(REPO)),
           "code": code, "data": data, "models": models, "seeds": seeds, "time": times, "environment": env}
    (CODE / "records" / "ceiling3b" / "manifest.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("manifest written:", list(times))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
