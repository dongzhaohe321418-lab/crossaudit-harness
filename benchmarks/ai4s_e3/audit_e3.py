"""E3 model audits (PREREGISTRATION-E3.md): tool-using and reading-only auditors on the E3 data items.

  agentic   the auditor runs in a fresh temporary copy of the item (data.csv, CARD.md only) and may inspect
            the files with the shell and Python; Codex (read-only sandbox, isolated CODEX_HOME, --json, web
            search disabled) or Claude Code (Bash and Read only, inside Claude Code's sandbox with no network,
            stream-json transcript). One reading per item and auditor. Amendment 2: every command is kept, and
            a reading whose commands reach the network or anything outside its own copy is discarded.
  reading   the same instructions with both files inlined and every tool disabled; 120-row items only; two
            readings per item and auditor. Codex runs with its shell tools disabled (amendment 1); a reading
            that invokes a tool is still discarded.

Every reply is JSON with typed findings, scored by code against the injection manifest (score_e3.py).

    python benchmarks/ai4s_e3/audit_e3.py --mode agentic --split dev --workers 6
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code" / "icml"))
sys.path.insert(0, str(HERE.parent / "code"))
import e1  # noqa: E402  (routes, isolation, JSON helpers)
from build_e3 import ITEM_ROOT, REC  # noqa: E402
from spec_e3 import FAULT_NAMES  # noqa: E402

OUT = REC / "audits.jsonl"
RAW = REC / "audits_raw.jsonl"
ROUTE_VERSION = "isolated-v2"     # amendment 2: every route, both modes; earlier rows are archived


def current(r: dict) -> bool:
    """Rows made with the route version the study now uses."""
    return r.get("route", "") == ROUTE_VERSION


SANDBOX = json.dumps({"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True,
                                  "allowUnsandboxedCommands": False, "network": {"allowedDomains": []}}})
_OUT_OF_SCOPE = re.compile(r"(\.\./|~/|/tmp/|/Users/|/private/|/var/|/home/|e3items|crossaudit|benchmarks|"
                           r"items\.json|manifest|https?:|\bcurl\b|\bwget\b|urllib|import requests|socket|"
                           r"http\.client|find\s+/|ls\s+/(?!usr|bin)|\blocate\s)", re.I)


def scope_violations(commands: list[str], workdir: str) -> list[str]:
    """Commands that reach the network or a path outside the auditor's own copy of the item."""
    out = []
    for c in commands:
        for w in (os.path.realpath(workdir), workdir):
            c = c.replace(w, "")
        if _OUT_OF_SCOPE.search(c):
            out.append(c[:300])
    return out
TYPES = sorted(set(FAULT_NAMES.values())) + ["other"]
PROMPT = """You are auditing a dataset delivered for a scientific analysis before anyone uses it. {where}

Decide whether the data can be used as delivered. Check it against its card (columns, units, stated ranges,
what each row is) and for internal problems. Report every problem you find. Grade a finding BLOCKER if the
data should not be used until it is fixed, ADVISORY otherwise. Do not report problems with the card's
wording unless they make the data unusable.

Reply with exactly one JSON object and nothing else:
{{"verdict": "accept" | "reject",
  "findings": [{{"severity": "BLOCKER" | "ADVISORY",
                "fault_type": one of {types},
                "columns": [column names involved, if any],
                "rows": [up to 10 zero-based row indices that show the problem, if any],
                "evidence": "one or two sentences"}}]}}
"""
AGENTIC_WHERE = ("The current directory contains data.csv and CARD.md. You may inspect them with the shell "
                 "and Python (standard library; numpy or pandas only if importable). Do not modify any file.")


def route_cmd(auditor: str, mode: str, item_dir: Path) -> tuple[str, list[str]]:
    if auditor == "aud-gpt-terra":
        notools = ["--disable", "shell_tool", "--disable", "unified_exec"] if mode == "reading" else []
        argv = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--json", *notools,
                "-c", 'web_search="disabled"',
                "-m", "gpt-5.6-terra", "-c", 'model_reasoning_effort="medium"', "--sandbox", "read-only",
                "--skip-git-repo-check", "-C", str(item_dir if mode == "agentic" else e1.EMPTY), "-"]
        return "codex", argv
    tools = ["--allowedTools", "Bash,Read", "--disallowedTools", "Write,Edit,NotebookEdit,WebFetch,WebSearch",
             "--settings", SANDBOX, "--output-format", "stream-json", "--verbose"] \
        if mode == "agentic" else ["--tools", ""]
    argv = ["claude", "-p", "--model", "claude-sonnet-5-5", *tools, "--setting-sources", "",
            "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
            "--system-prompt", "Answer the user's request."]
    return "claude", argv


def run(auditor: str, mode: str, item: dict, timeout: float = 1500.0) -> dict:
    src = ITEM_ROOT / item["item"]
    work = Path(tempfile.mkdtemp(prefix="audit_"))
    for name in ("data.csv", "CARD.md"):
        shutil.copy2(src / name, work / name)
    try:
        return _run(auditor, mode, work, timeout)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run(auditor: str, mode: str, work: Path, timeout: float) -> dict:
    if mode == "agentic":
        payload = PROMPT.format(where=AGENTIC_WHERE, types=TYPES)
    else:
        where = ("The card and the data follow.\n\nCARD.md:\n" + (work / "CARD.md").read_text() +
                 "\n\ndata.csv:\n" + (work / "data.csv").read_text())
        payload = PROMPT.format(where=where, types=TYPES)
    kind, argv = route_cmd(auditor, mode, work)
    env = dict(e1.os.environ)
    if kind == "codex":
        env["CODEX_HOME"] = e1.iso_home(f"{auditor}-e3")
    cwd = str(work if mode == "agentic" else e1.EMPTY)
    started = time.monotonic()
    try:
        done = subprocess.run(argv, input=payload, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "wall_s": round(time.monotonic() - started, 1), "raw": ""}
    wall = round(time.monotonic() - started, 1)
    raw, text, tools_used, commands, other_tools = done.stdout or "", done.stdout or "", 0, [], []
    if kind == "codex":
        msgs = []
        for line in raw.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            it = ev.get("item") or {}
            if ev.get("type") == "item.completed" and it.get("type") in e1.NON_MESSAGE_ITEMS:
                tools_used += 1
                if it.get("type") == "command_execution":
                    commands.append(str(it.get("command", "")))
                else:
                    other_tools.append(it.get("type"))
            if ev.get("type") == "item.completed" and it.get("type") == "agent_message":
                msgs.append(it.get("text", ""))
        text = msgs[-1] if msgs else ""
    elif mode == "agentic":
        text = ""
        for line in raw.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                for c in ev.get("message", {}).get("content", []):
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        tools_used += 1
                        inp = c.get("input") or {}
                        if c.get("name") == "Bash":
                            commands.append(str(inp.get("command", "")))
                        elif c.get("name") == "Read":
                            commands.append("Read " + str(inp.get("file_path", "")))
                        else:
                            other_tools.append(c.get("name"))
            if ev.get("type") == "result":
                text = str(ev.get("result") or "")
    obj = e1.parse_json(text)
    violations = scope_violations(commands, str(work)) if mode == "agentic" else []
    ok = done.returncode == 0 and isinstance(obj, dict) and isinstance(obj.get("findings"), list)
    error = ""
    if mode == "reading" and tools_used:
        ok, error = False, f"tools {tools_used}"
    if other_tools:
        ok, error = False, f"non-shell tools {other_tools[:5]}"
    if violations:
        ok, error = False, "out-of-scope access"
    if not ok and not error:
        error = f"exit {done.returncode}; {(done.stderr or '')[-200:]}"
    return {"ok": ok, "wall_s": wall, "tools_used": tools_used, "commands": commands[:200],
            "violations": violations[:20], "reply": obj if ok else None, "text": text[:20000],
            "error": error, "raw": raw}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["agentic", "reading"], required=True)
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--auditors", default="aud-gpt-terra,aud-claude-sonnet")
    a = ap.parse_args()
    items = [i for i in json.loads((REC / "items.json").read_text())["items"] if i["split"] == a.split]
    if a.mode == "reading":
        items = [i for i in items if i["size"] == 120]
    readings = 1 if a.mode == "agentic" else 2
    rows = [r for r in e1.load(OUT) if current(r)]
    done_keys = {(r["item"], r["mode"], r["auditor"], r["reading"]) for r in rows if r.get("ok")}
    tries: dict = {}
    for r in rows:
        k = (r["item"], r["mode"], r["auditor"], r["reading"])
        tries[k] = tries.get(k, 0) + 1
    jobs = [(i, au, k) for i in items for au in a.auditors.split(",") for k in range(readings)
            if (i["item"], a.mode, au, k) not in done_keys and tries.get((i["item"], a.mode, au, k), 0) < 2]
    random.Random(11).shuffle(jobs)

    def one(job):
        item, au, k = job
        res = run(au, a.mode, item)
        raw = res.pop("raw", "")
        e1.append(RAW, {"item": item["item"], "mode": a.mode, "auditor": au, "reading": k, "route": ROUTE_VERSION,
                        "raw": raw})
        e1.append(OUT, {"item": item["item"], "mode": a.mode, "auditor": au, "reading": k, "split": a.split,
                        "route": ROUTE_VERSION, **res})
    e1.run_pool(jobs, one, a.workers, f"e3 {a.mode} {a.split}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
