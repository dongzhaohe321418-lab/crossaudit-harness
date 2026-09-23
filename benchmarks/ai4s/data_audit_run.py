#!/usr/bin/env python3
"""A4S-3 auditing: the product's run_audit on the data items, cross and self, K = 4.

Registered in `PREREGISTRATION-DATA.md` (Amendments 1 and 2). Each item's CSV and data card are
committed at `work/data/data.csv` and `work/data/CARD.md` inside the audited scope (Amendment 2);
the task is the registered delivery sentence followed by the card. The `self` family's calls go
through the Claude Code CLI (A4S-1 Amendment 1); `cross` goes to OpenAI as shipped. Every
reading's BLOCKER texts are archived; the halt reads every ledger this study wrote, the voided
and pilot runs included, and fails closed.

    python benchmarks/ai4s/data_audit_run.py --plan
    python benchmarks/ai4s/data_audit_run.py --family cross --workers 6
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "benchmarks/code"))
sys.path.insert(0, str(REPO / "benchmarks/expertlongbench"))
sys.path.insert(0, str(HERE))

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
GEN = AI4S / "runs/generation"
OUT = AI4S / "runs/data_audit"
VOID = AI4S / "runs/data_audit_void_scope"      # Amendment 2: counted, never analysed
PILOT = AI4S / "runs/data_audit_pilot"          # Amendment 1: counted, never analysed
ITEMS = AI4S / "runs/data_items"
MANIFEST = REPO / "benchmarks/code/records/ai4s/data_items.json"
STRATA = REPO / "benchmarks/code/records/ai4s/strata.json"
K = 4
HALT_USD = 60.0                          # Amendment 3
SPECS = {"cross": "openai:gpt-5.6-terra", "self": "anthropic:claude-haiku-4-5-20251001"}
GENERATOR = "anthropic:claude-haiku-4-5-20251001"
SKIP = {("13", 5), ("62", 0), ("76", 2)}


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def problems() -> dict[str, dict]:
    out = {}
    for split in ("dev", "test"):
        for line in (AI4S / f"data/problems_{split}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                p = json.loads(line)
                out[p["problem_id"]] = p
    return out


def generated() -> dict[tuple[str, int, int], dict]:
    out = {}
    for f in GEN.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("ok"):
                    out[(r["problem_id"], r["sample"], r["step"])] = r
    return out


def instance(iid: str, probs: dict, gen: dict) -> tuple[str, str]:
    """(task, candidate program) for instance id '<pid>.<step1>.s<sample>'."""
    pid, step1, s = iid.rsplit(".", 2)
    k, smp = int(step1) - 1, int(s[1:])
    p = probs[pid]
    funcs = []
    for i in range(k + 1):
        if (pid, i) in SKIP:
            funcs.append((AI4S / f"SciCode/eval/data/{pid}.{i + 1}.txt").read_text(encoding="utf-8"))
        else:
            funcs.append(gen[(pid, smp, i)]["function"] or "")
    program = p["required_dependencies"] + "\n\n" + "\n\n".join(funcs) + "\n"
    st = p["sub_steps"][k]
    task = (f"{p['problem_description_main']}\n\n"
            f"Step {st['step_number']}: {st['step_description_prompt']}\n\n"
            f"Background:\n{st['step_background']}\n\n"
            f"Function to implement:\n{st['function_header']}\n{st['return_line']}\n\n"
            f"Allowed dependencies:\n{p['required_dependencies']}\n")
    return task, program


def spent() -> tuple[float, int]:
    from crossaudit import usage
    total, n, priced = 0.0, 0, 0
    ledgers = [*OUT.glob("projects/*/.crossaudit/usage.jsonl"),
               *VOID.glob("projects/*/.crossaudit/usage.jsonl"),
               *PILOT.glob("**/.crossaudit/usage.jsonl")]
    for ledger in ledgers:
        events, _ = usage.read_events(ledger)
        for e in events:
            n += 1
            v = e.get("api_value_usd")
            if v is not None:
                total += float(v)
                priced += 1
    if n and not priced:
        raise SystemExit(f"HALT: {n} ledger events and no cost on any; the guard cannot see money")
    return total, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(SPECS))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="first N instances of draw 1 only")
    args = ap.parse_args()

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    ids = [m["item"] for m in man]
    stratum = {m["item"]: ("P" if m["fault"] else "C") for m in man}
    OUT.mkdir(parents=True, exist_ok=True)
    if args.plan or not args.family:
        for fam in SPECS:
            for d in range(1, K + 1):
                f = OUT / f"{fam}.d{d}.jsonl"
                have = {json.loads(l)["instance_id"] for l in f.read_text().splitlines() if l.strip()} if f.exists() else set()
                print(f"{fam} d{d}: {len(have)}/{len(ids)}")
        print("spent", spent())
        return 0

    import os
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k_, v_ = line.split("=", 1)
            os.environ.setdefault(k_.strip(), v_.strip().strip('"').strip("'"))
    from crossaudit import app_keys
    for vendor, role_env in app_keys.ROLE_FALLBACKS.items():
        venv = app_keys.env_for_vendor(vendor)
        if not os.environ.get(venv) and os.environ.get(role_env):
            os.environ[venv] = os.environ[role_env]
    if args.family == "self":
        import cli_transport                  # Amendment 1
        cli_transport.install()

    import audit as study1
    from crossaudit.auditor.run import run_audit
    from crossaudit.config import load
    from crossaudit.scaffold import read as read_template
    constitution = read_template("GENERAL_AUDIT_RULES.md").replace("<PROJECT>", "scientific-data-study")
    project = study1.build_project(OUT / "projects", args.family, SPECS[args.family], GENERATOR,
                                   constitution)
    cfg = load(project / "crossaudit.yml")
    TASK = ("Deliver a dataset ready for use in a scientific analysis: work/data/data.csv, "
            "documented by the data card work/data/CARD.md, which states what each column is "
            "and its unit.")                   # Amendment 2: inside the audited scope
    lock = threading.Lock()

    def one(iid: str, draw: int) -> dict:
        csv_text = (ITEMS / iid / "data.csv").read_text(encoding="utf-8")
        card_text = (ITEMS / iid / "CARD.md").read_text(encoding="utf-8")
        task, program = TASK + "\n\n" + card_text, csv_text
        run_id = f"a4s3-{args.family}-d{draw}-{iid}"[:64]
        row = {"instance_id": iid, "stratum": stratum[iid], "family": args.family, "draw": draw,
               "run_id": run_id, "task_sha256": sha(task), "program_sha256": sha(program)}
        def on_event(*_a, **_k):
            return None
        on_event.run_id = run_id
        on_event.heartbeat = lambda: None
        for attempt in range(1, 8):
            try:
                out = run_audit(cfg=cfg, sha="0" * 40, round_=1,
                                files={"work/data/data.csv": program.encode("utf-8"),
                                       "work/data/CARD.md": card_text.encode("utf-8")}, notes=[],
                                constitution=constitution, constitution_commit="frozen",
                                task=task, on_event=on_event,
                                usage_context={"run_id": run_id, "arm": args.family,
                                               "problem_id": iid})
                findings = (out.model_reply or {}).get("findings") or []
                blockers = [f for f in findings if f.get("severity") == "BLOCKER"]
                row.update({"ok": True, "verdict": out.verdict, "flagged": bool(blockers),
                            "model_findings": len(findings), "model_blockers": len(blockers),
                            "blocker_texts": [f.get("observation", "") for f in blockers]})
                return row
            except Exception as exc:                                    # noqa: BLE001
                row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]})
                time.sleep(min(20 * attempt, 120))
        return row

    for draw in range(1, K + 1):
        f = OUT / f"{args.family}.d{draw}.jsonl"
        have = set()
        if f.exists():
            have = {json.loads(l)["instance_id"] for l in f.read_text().splitlines()
                    if l.strip() and json.loads(l).get("ok")}
        todo = [i for i in ids if i not in have]
        if args.limit:
            if draw > 1:
                break
            todo = todo[: args.limit]
        if not todo:
            continue
        total, _ = spent()
        if total >= HALT_USD:
            print(f"HALT: ${total:.2f} at or over ${HALT_USD}")
            return 2
        print(f"{args.family} d{draw}: {len(todo)} to run (spent ${total:.2f})", flush=True)
        with f.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(args.workers) as pool:
            for n, row in enumerate(pool.map(lambda i: one(i, draw), todo), 1):
                with lock:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")
                    fh.flush()
                if n % 25 == 0:
                    tot, _ = spent()
                    print(f"  d{draw} {n}/{len(todo)}  ${tot:.2f}", flush=True)
                    if tot >= HALT_USD:
                        print("HALT"); return 2
    missing = 0
    for draw in range(1, K + 1):
        f = OUT / f"{args.family}.d{draw}.jsonl"
        have = {json.loads(l)["instance_id"] for l in f.read_text().splitlines()
                if l.strip() and json.loads(l).get("ok")} if f.exists() else set()
        missing += len([i for i in ids if i not in have])
    print(f"spent ${spent()[0]:.2f}; missing readings: {missing}")
    return 4 if missing and not args.limit else 0


if __name__ == "__main__":
    raise SystemExit(main())
