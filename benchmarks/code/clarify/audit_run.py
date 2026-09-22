#!/usr/bin/env python3
"""P3's audit readings: the same code, three specifications, K = 4 draws each.

Registered in `plan/P3-PREREGISTRATION.md` and its Amendment 11. The auditor is the shipped
cross-vendor one, `gpt-5.6-terra`. **It is shown the specification and nothing else that differs
between conditions**: `audit.increment_files` puts the candidate and the visible suite in front
of it, and gate 1 has already checked those are byte-identical across the three arms.

**Every finding's full text is archived.** Study 18 recorded finding counts and not finding
texts, and the consequence was that its advisory numbers could never be turned into a statement
about what any finding identified -- a limitation that has now been quoted in three reports.
P3's outcome is defined over finding text, so the text is the artefact, and a run that recorded
digests instead would be unable to answer its own question.

Rows land in the durable study-data directory, not the repo: they carry the specification prose
the corpus licence covers.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, "src")
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import audit as study1  # noqa: E402
from corpus import load_problems  # noqa: E402

COND = HERE.parent / "records/clarify/conditions.json"
OUT = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs"
ARMS = ("original", "clarified", "placebo")
K = 4                      # Amendment 11, fixed before the first call
HALT_USD = 60.0            # the registration's halt, checked against rows and not estimated


def load_keys() -> None:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    # The key file carries the app's ROLE names; the audit kernel resolves a VENDOR name.
    # `src/crossaudit/app_keys.py` is where that mapping is already declared, so it is read from
    # there rather than restated here -- the smoke run failed all twelve readings on exactly
    # this gap, and a second hand-written copy of the mapping is a second thing to drift.
    from crossaudit import app_keys
    for vendor, role_env in app_keys.ROLE_FALLBACKS.items():
        vendor_env = app_keys.env_for_vendor(vendor)
        if not os.environ.get(vendor_env) and os.environ.get(role_env):
            os.environ[vendor_env] = os.environ[role_env]


def spent(ledger: Path, n_readings: int) -> float:
    """What this study has actually spent, from the kernel's own usage ledger.

    The first version summed a `cost` field off the rows `audit.audit_one` writes. **That field
    does not exist** -- the row carries verdicts, counts and digests, and nothing about money --
    so the guard returned $0.00 after twelve readings and would have returned $0.00 after twelve
    thousand. This programme has now built that same blind guard twice: the supervisor's budget
    check read a `cost.json` that was never written and reported zero forever.

    So it reads the ledger the kernel actually writes, and it **fails closed**: a missing or
    unreadable ledger after any reading has been made halts the run instead of reading as free.
    """
    if n_readings == 0:
        return 0.0
    if not ledger.exists():
        raise SystemExit(f"ERR: {n_readings} readings made and no usage ledger at {ledger}; "
                         "refusing to spend further against a guard that cannot see cost")
    total, seen_cost = 0.0, False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:                                              # noqa: BLE001
            raise SystemExit(f"ERR: unparseable entry in {ledger}; refusing to spend further")
        for field in ("api_value_usd", "cost_usd", "usd"):
            if e.get(field) is not None:
                total += float(e[field])
                seen_cost = True
                break
    if not seen_cost:
        raise SystemExit(
            f"ERR: {n_readings} readings made and the ledger at {ledger} carries no recognised "
            "cost field; refusing to spend further. This guard has now been blind three times "
            "in this programme -- a cost.json that was never written, a `cost` key `audit_one` "
            "does not write, and a `cost_usd` name the kernel spells `api_value_usd`. The "
            "property is that the guard can SEE money, and it halts when it cannot.")
    return total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auditor", default="openai:gpt-5.6-terra")
    ap.add_argument("--generator", default="anthropic:claude-sonnet-4-6")
    ap.add_argument("--limit", type=int, default=0, help="smoke runs only; writes its own file")
    args = ap.parse_args(argv)

    load_keys()
    data = json.loads(COND.read_text(encoding="utf-8"))
    conds = data["conditions"]
    ids = sorted(conds)[:args.limit] if args.limit else sorted(conds)
    OUT.mkdir(parents=True, exist_ok=True)
    rows_path = OUT / ("rows-smoke.jsonl" if args.limit else "rows.jsonl")

    # A FAILED reading is not a completed one. The first resume counted every row on disk,
    # including ten that had died in a provider cooldown, and skipped them -- so a rerun bought
    # one reading, reported success, and left ten holes that no later count would have shown as
    # holes. Only `ok` rows are done; failed rows stay on disk as evidence and are retried.
    done, failed_rows = set(), 0
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("ok"):
                done.add((r["instance_id"], r["condition"], r["draw"]))
            else:
                failed_rows += 1
        print(f"resuming: {len(done)} completed readings on disk, "
              f"{failed_rows} failed rows to retry", flush=True)

    problems = {p.problem_id: p for p in load_problems()}
    # `audit.audit_one` keeps digests and counts; P3's outcome is defined over finding TEXT, so
    # the texts are captured here rather than lost. Study 18 recorded counts without texts and
    # its advisory numbers could never be turned into a statement about what a finding
    # identified -- a limitation three later reports have had to quote.
    import crossaudit.auditor.run as runmod
    captured: dict = {}
    _real_run_audit = runmod.run_audit

    def capturing_run_audit(**kw):
        out = _real_run_audit(**kw)
        captured["findings"] = [
            {"severity": f.get("severity"), "rule": f.get("rule"),
             "artifact": f.get("artifact"), "observation": f.get("observation") or ""}
            for f in ((out.model_reply or {}).get("findings") or [])]
        captured["dcl_findings"] = [
            {"severity": f.get("severity"), "rule": f.get("rule"),
             "observation": f.get("observation") or ""}
            for f in (out.dcl.get("findings") or [])]
        return out

    runmod.run_audit = capturing_run_audit

    from crossaudit.config import load
    constitution = study1.shipped_constitution()
    scratch = OUT / "project"
    scratch.mkdir(parents=True, exist_ok=True)
    project = study1.build_project(scratch, "cross", args.auditor, args.generator, constitution)
    cfg = load(project / "crossaudit.yml")
    study1.register_visible_tests_check()

    todo = [(iid, arm, d) for iid in ids for arm in ARMS for d in range(1, K + 1)
            if (iid, arm, d) not in done]
    print(f"{len(todo)} readings to buy ({len(ids)} instances x {len(ARMS)} arms x K={K})",
          flush=True)

    ledger = project / ".crossaudit" / "usage.jsonl"
    consecutive_failures = 0
    with rows_path.open("a", encoding="utf-8") as fh:
        for n, (iid, arm, draw) in enumerate(todo, 1):
            so_far = spent(ledger, n - 1)
            if so_far >= HALT_USD:
                print(f"HALT: ${so_far:.2f} spent, at or over the registered ${HALT_USD} halt",
                      flush=True)
                return 2
            base = problems[iid.split(":", 1)[1]]
            c = conds[iid][arm]
            # `audit_one` passes `problem.spec` as the audit's task. Handing it the unmodified
            # problem would send the ORIGINAL specification under all three condition labels and
            # the manipulation would never reach the auditor -- the study would return three
            # samples of one condition and look like a null result. `Problem` is a frozen
            # dataclass, so the condition's spec is swapped in without touching shared code, and
            # `prove_spec_reaches_auditor.py` checks that it arrives.
            problem = dataclasses.replace(base, spec=c["spec"])
            started = time.monotonic()
            captured.clear()
            row = study1.audit_one(cfg, problem, c["candidate"], {}, constitution,
                                   run_id=f"p3-{iid}-{arm}-{draw}", arm="cross")
            # `audit_one` is study 1's, and it keeps digests rather than text. The outcome here
            # is defined over the text, so the text is re-read from the outcome and stored.
            if not row.get("ok"):
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    fh.write(json.dumps({**row, "instance_id": iid, "condition": arm,
                                         "draw": draw}, sort_keys=True) + "\n")
                    fh.flush()
                    print(f"HALT: {consecutive_failures} consecutive failed readings. "
                          f"Last error: {row.get('error', '')[:200]}", flush=True)
                    return 3
            else:
                consecutive_failures = 0
            row.update({"instance_id": iid, "condition": arm, "draw": draw,
                        "findings": captured.get("findings", []),
                        "dcl_findings_text": captured.get("dcl_findings", []),
                        "spec_sha256": study1.sha256_text(c["spec"]),
                        "candidate_sha256": study1.sha256_text(c["candidate"]),
                        "visible_sha256": study1.sha256_text(c["visible_tests"]),
                        "wall_s": time.monotonic() - started})
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            if n % 10 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)}  ${spent(ledger, n):.2f}", flush=True)
    ok_n = sum(1 for _ in todo)
    print(f"\nwrote {rows_path}; ${spent(ledger, ok_n):.2f} spent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
