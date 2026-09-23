#!/usr/bin/env python3
"""A4S-1 generation: SciCode steps written by the frozen generator, three samples per step.

Registered in `PREREGISTRATION-CODE.md` (1f8aa4d). SciCode's with-background template verbatim,
one step at a time, earlier steps from this sample's own extracted functions; the benchmark's own
code for its three skipped steps. Every reply, prompt hash and cost is archived under
`~/Documents/Crossaudit/ai4s/runs/generation/`; the halt reads the priced replies and fails closed.

    python benchmarks/ai4s/generate.py --limit 1   # one problem, one sample: proves the pipeline
    python benchmarks/ai4s/generate.py             # all 80 problems x 3 samples, resumable
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

AI4S = Path.home() / "Documents/Crossaudit/ai4s"
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(AI4S / "SciCode/src"))

from scicode.parse.parse import extract_function_name, get_function_from_code  # noqa: E402

OUT = AI4S / "runs/generation"
MODEL = "claude-haiku-4-5-20251001"
KEY_ENV = "CROSSAUDIT_GENERATOR_KEY"
SAMPLES = 3
HALT_USD = 15.0
SKIP = {("13", 5), ("62", 0), ("76", 2)}
TEMPLATE = (AI4S / "SciCode/eval/data/background_comment_template.txt").read_text(encoding="utf-8")


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_keys() -> None:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def problems() -> list[dict]:
    rows = []
    for split in ("dev", "test"):
        for line in (AI4S / f"data/problems_{split}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["_split"] = split
                rows.append(r)
    return rows


def extract_python_script(response: str) -> str:
    """SciCode's own extractor, restated because importing its module pulls in `inspect_ai`."""
    if "```" in response:
        python_script = (response.split("```python")[1].split("```")[0]
                         if "```python" in response else response.split("```")[1].split("```")[0])
    else:
        python_script = response
    return "\n".join(l for l in python_script.splitlines()
                     if not l.lstrip().startswith(("from ", "import ")))


def prompt_for(p: dict, k: int, prev_funcs: list[str]) -> str:
    lines = []
    for i in range(k):
        s = p["sub_steps"][i]
        lines.append(s["step_description_prompt"] + "\n" + s["step_background"])
        lines.append(prev_funcs[i])
        lines.append("------")
    s = p["sub_steps"][k]
    nxt = "\n\n".join([s["step_description_prompt"] + "\n" + s["step_background"],
                       f"{s['function_header']}\n\n{s['return_line']}"])
    return TEMPLATE.format(problem_steps_str="\n\n".join(lines[:-1]), next_step_str=nxt,
                           dependencies=p["required_dependencies"])


def spent() -> float:
    total, n = 0.0, 0
    for f in OUT.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("cost_usd") is None and r.get("ok"):
                    raise SystemExit("HALT: a successful reply without a cost; the guard cannot see money")
                total += r.get("cost_usd") or 0.0
                n += 1
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="0/1", help="i/n: this process takes problems i, i+n, ...")
    args = ap.parse_args()
    load_keys()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cli_transport                     # Amendment 1: Anthropic calls go through the CLI
    cli_transport.install()
    from crossaudit.providers import anthropic
    OUT.mkdir(parents=True, exist_ok=True)
    rows = problems()
    samples = range(1, SAMPLES + 1)
    if args.limit:
        rows, samples = rows[: args.limit], range(1, 2)
    i, n = (int(x) for x in args.shard.split("/"))
    rows = rows[i::n]
    for p in rows:
        pid = p["problem_id"]
        for smp in samples:
            path = OUT / f"{pid}.s{smp}.jsonl"
            done = {}
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        r = json.loads(line)
                        if r.get("ok"):
                            done[r["step"]] = r
            prev: list[str] = []
            with path.open("a", encoding="utf-8") as fh:
                for k, s in enumerate(p["sub_steps"]):
                    fname = extract_function_name(s["function_header"])
                    if (pid, k) in SKIP:
                        code = (AI4S / f"SciCode/eval/data/{pid}.{k + 1}.txt").read_text(encoding="utf-8")
                        prev.append(get_function_from_code(code, fname) or code)
                        continue
                    if k in done:
                        prev.append(done[k]["function"] or "")
                        continue
                    if spent() >= HALT_USD:
                        print(f"HALT: generation spend at or over ${HALT_USD}")
                        return 2
                    prompt = prompt_for(p, k, prev)
                    text, cost, err = "", None, ""
                    for attempt in range(1, 6):
                        try:
                            rep = anthropic.complete(model=MODEL, system="", prompt=prompt,
                                                     key_env=KEY_ENV, max_tokens=4096, timeout=300.0)
                            text = rep.text or ""
                            cost = rep.cost_usd
                            err = ""
                            break
                        except Exception as exc:                        # noqa: BLE001
                            err = f"{type(exc).__name__}: {exc}"[:300]
                            time.sleep(15 * attempt)
                    script = extract_python_script(text) if text else ""
                    func = get_function_from_code(script, fname) if script else None
                    fh.write(json.dumps({"problem_id": pid, "split": p["_split"], "sample": smp,
                                         "step": k, "step_number": s["step_number"],
                                         "ok": bool(text), "error": err,
                                         "prompt_sha256": sha(prompt), "response": text,
                                         "script": script, "function": func,
                                         "cost_usd": cost}, sort_keys=True) + "\n")
                    fh.flush()
                    prev.append(func or "")
            print(f"{pid} s{smp}: done  (${spent():.3f})", flush=True)
    print(f"generation complete; ${spent():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
