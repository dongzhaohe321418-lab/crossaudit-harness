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
import re
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
    ap.add_argument("--study18-run", type=Path, default=None, help="study 18 archive: arm S's reused draws 1-4")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()
    run = args.run
    prereg = CODE / "ceiling3b" / "PREREGISTRATION.md"
    commits = [line.split(" ", 1) for line in git("log", "--format=%H %cI %s", "--", str(prereg.relative_to(REPO))).splitlines()]
    status = git("status", "--porcelain")
    if status and not args.allow_dirty:
        raise SystemExit("the tree is not clean; commit first, then run this at the frozen commit:\n" + status)
    study_files = sorted(p for p in [*(CODE / "ceiling3b").glob("*"), CODE / "ceiling3b.py", CODE / "report_ceiling3b.py",
                                      CODE / "RESULTS-CEILING3B.md", CODE / "tests" / "test_ceiling3b_report.py",
                                      *(CODE / "records" / "ceiling3b").rglob("*")]
                         if p.is_file() and p.name != "manifest.json")
    study_files += sorted(p for p in (REPO / "benchmarks" / "reviews").glob("*ceiling3b*") if p.is_file())
    code = {"preregistration_and_amendment_commits": [{"sha": c[0], "when_and_subject": c[1]} for c in reversed(commits)],
            "amendment_headings": [l.strip() for l in prereg.read_text(encoding="utf-8").splitlines() if l.startswith("## Amendment")],
            "frozen_commit": git("rev-parse", "HEAD"),
            "frozen_commit_subject": git("log", "-1", "--format=%s"),
            "working_tree_status_at_freeze": status,
            "clean_at_freeze": status == "",
            "note": "manifest.json is committed in the commit after frozen_commit; every other file the study added is listed here",
            "files_this_study_added": {str(p.relative_to(REPO)): sha(p) for p in study_files}}
    data_dir = CODE / "data"
    fetch_src = (CODE / "fetch.py").read_text(encoding="utf-8") if (CODE / "fetch.py").exists() else ""
    sources = sorted(set(re.findall(r"https?://[^\s\"']+", fetch_src)))
    def rows(p: Path) -> int:
        return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    data = {"corpus": {p.name: {"sha256": sha(p), "bytes": p.stat().st_size, "rows": rows(p)} for p in sorted(data_dir.glob("*.jsonl"))} if data_dir.exists() else "data/ not present",
            "dataset": "EvalPlus HumanEval+ and MBPP+, as fetched by benchmarks/code/fetch.py; the revision is the per-file digest above",
            "fetch_sources": sources,
            "licence": "EvalPlus HumanEval+ / MBPP+ (Apache-2.0); solutions are study 2's, frozen",
            "audit_set_sha256": sha(CODE / "records" / "study2" / "audit_set.json"),
            "instances_sha256": sha(CODE / "records" / "study2" / "instances.jsonl"),
            "instances_rows": rows(CODE / "records" / "study2" / "instances.jsonl"),
            "solutions": {p.name: {"sha256": sha(p), "rows": rows(p)} for p in sorted((run / "study2-inputs").glob("solutions-*.jsonl"))}}
    import datetime as _dt
    def iso(t):
        t = float(t); t = t / 1000 if t > 1e11 else t      # the ledger stamps epoch milliseconds
        return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).isoformat()
    models = {}
    times = {}
    for proj in sorted((run / "projects").glob("project-holistic__*")):
        arm = proj.name.split("project-holistic__")[1]
        cfg = (proj / "crossaudit.yml").read_text(encoding="utf-8") if (proj / "crossaudit.yml").exists() else ""
        ledger = proj / ".crossaudit" / "usage.jsonl"
        ev = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
        ts = sorted(iso(e.get("t")) for e in ev if e.get("t"))
        models[arm] = {"config_sha256": hashlib.sha256(cfg.encode()).hexdigest(),
                       "auditor": {"vendor": "anthropic", "model": "claude-sonnet-4-6", "provider": "anthropic",
                                   "base_url": "vendor default", "reasoning_effort": "unset (product default)",
                                   "temperature": "adapter default for the model's capability card (0 for Sonnet 4.6)"},
                       "generator": "unset — the same-vendor bypass of ceiling 1's self family, confined to the harness",
                       "constitution_sha256": sha(proj / "AUDIT_RULES.md") if (proj / "AUDIT_RULES.md").exists() else None,
                       "ledger_calls": len(ev), "ledger_usd": round(sum(float(e.get("api_value_usd") or 0) for e in ev), 6)}
        times[arm] = {"first_call_utc": ts[0] if ts else None, "last_call_utc": ts[-1] if ts else None}
    if args.study18_run is not None:
        for d in (1, 2, 3, 4):
            proj = args.study18_run / "projects" / f"project-holistic__self-strong__d{d}"
            ledger = proj / ".crossaudit" / "usage.jsonl"
            ev = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
            ts = sorted(iso(e.get("t")) for e in ev if e.get("t"))
            cfg = (proj / "crossaudit.yml").read_text(encoding="utf-8") if (proj / "crossaudit.yml").exists() else ""
            models[f"S (study 18 self-strong d{d}, reused)"] = {
                "config_sha256": hashlib.sha256(cfg.encode()).hexdigest(),
                "auditor": {"role": "auditor (arm S: the shipped constitution; the comparator of every S contrast)",
                            "vendor": "anthropic", "model": "claude-sonnet-4-6", "provider": "anthropic",
                            "base_url": "vendor default", "reasoning_effort": "unset (product default)",
                            "temperature": "adapter default for the model's capability card (0 for Sonnet 4.6)"},
                "generator": "unset — the same-vendor bypass of ceiling 1's self family, confined to the harness",
                "constitution_sha256": sha(proj / "AUDIT_RULES.md") if (proj / "AUDIT_RULES.md").exists() else None,
                "ledger_calls": len(ev), "ledger_usd": round(sum(float(e.get("api_value_usd") or 0) for e in ev), 6),
                "provenance": "study 18's archive (records/ceiling3/manifest and its MANIFEST.sha256); not re-run here"}
            times[f"S (study 18 self-strong d{d}, reused)"] = {"first_call_utc": ts[0] if ts else None, "last_call_utc": ts[-1] if ts else None}
    models["adjudicators"] = {
        "_blinding": "METADATA-BLIND, NOT ALLOCATION-BLIND. The sheet withholds the instance id, "
                     "the arm and the stratum, but five of the 190 finding texts (and three of "
                     "the 72 strict ones) name the added rule's id, CA-COVER-001 or "
                     "CA-GRADE-001, so a reader of those items can infer the arm. RESULTS "
                     "§4 says the same; this field exists so the machine-readable record "
                     "cannot say otherwise.",
        "L1": {"role": "adjudicator, naming and (post hoc) recognition questions",
               "who": "the author of this study and of the paper (human)",
               "withheld_by_the_sheet": "instance id, arm, stratum",
               "not_blind_to": "the finding text, which names the rule id in five items; "
                               "and, being the author, the study's design and its other results"},
        "L2": {"role": "adjudicator, same questions", "model": "gpt-6-astra",
               "provider": "OpenAI via the Codex CLI (not the product's provider layer)",
               # EXPERIMENT_RECORD §2 requires a base URL for every model. This one is
               # MISSING, and the record says so in the field itself rather than putting an
               # excuse where a URL belongs: `base_url` is null, and the next two fields say
               # what is known and why the value cannot be recovered. A test asserts the null
               # and the declaration together, so prose can never satisfy this again.
               "base_url": None,
               "base_url_status": "MISSING — required by EXPERIMENT_RECORD §2 and not recorded",
               "base_url_why": "the adjudicator ran through the Codex CLI (codex-cli 0.153.4), "
                               "which writes no endpoint to any local record this study may "
                               "read; ~/.codex/config.toml sets neither base_url nor "
                               "model_provider, so the CLI's built-in default for the "
                               "account's authentication mode applied, and ~/.codex/auth.json "
                               "is out of bounds under this project's rules. The call cannot "
                               "be reconstructed from this record alone.",
               "settings": "codex exec --sandbox read-only, model_reasoning_effort=high, "
                           "default sampling",
               "withheld_by_the_sheet": "instance id, arm, stratum",
               "not_blind_to": "the finding text, which names the rule id in five items"}}
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
