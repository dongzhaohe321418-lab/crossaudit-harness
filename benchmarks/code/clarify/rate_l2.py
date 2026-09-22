#!/usr/bin/env python3
"""L2's pass over P3's blind adjudication sheet.

`gpt-6-astra`, which did study 19's H19d adjudication and is neither the auditor
(`gpt-5.6-terra`) nor the clarifier (`gpt-5.6-luna`). `gpt-5.6-sol` is excluded by Amendment 12:
it rated all three arms' specifications for the manipulation check and knows which text belongs
to which condition.

The rater is given the sheet's own question verbatim and the items as the sheet shows them --
no arm, no instance id, no severity. One line per item, `<id>,<label>`.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

SHEET = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs/sheet"
MODEL = "gpt-6-astra"
KEY_ENV = "CROSSAUDIT_AUDITOR_KEY"
BATCH = 5

RUBRIC = """You are adjudicating audit findings. For each item you are asked one thing only:

> Does this finding state the behaviour the hidden suite expects at an input the hidden suite
> exercises, well enough that a reader could fix the code without seeing the test?

  yes          — it does. The behaviour is stated, and it is the behaviour the suite expects.
  no           — it does not. It may be true, or about something else, or too vague to act on.
  cannot tell  — you cannot tell.

`cannot tell` is a legitimate answer. Do not force a choice to make the sheet look tidy.

A finding that merely reports that something is wrong, or that the tests fail, without saying
what the code should do instead, is `no`.

Answer with one line per item, exactly `<id>,<label>`, and nothing else."""


def load_keys() -> None:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip().removeprefix("export ")
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def items() -> list[tuple[str, str]]:
    text = (SHEET / "sheet.md").read_text(encoding="utf-8")
    parts = re.split(r"^## (P\d+)$", text, flags=re.M)[1:]
    return list(zip(parts[0::2], parts[1::2]))


def main() -> int:
    load_keys()
    from crossaudit.providers import openai_compat as provider
    its = items()
    out_path = SHEET / "L2.csv"
    done: dict[str, str] = {}
    if out_path.exists():
        import csv
        done = {r["id"]: r["label"] for r in csv.DictReader(out_path.open(encoding="utf-8"))}
        print(f"resuming: {len(done)} already labelled", flush=True)

    todo = [(i, c) for i, c in its if i not in done]
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        prompt = "\n\n".join(f"## {i}{c}" for i, c in chunk)
        text = ""
        for attempt in range(4):
            try:
                reply = provider.complete(model=MODEL, key_env=KEY_ENV, system=RUBRIC,
                                          prompt=prompt, max_tokens=2000, timeout=240.0)
                text = (getattr(reply, "text", "") or "")
                if text.strip():
                    break
            except Exception as exc:                                   # noqa: BLE001
                print(f"    {chunk[0][0]}: {type(exc).__name__} {attempt + 1}/4", flush=True)
            time.sleep(20 * (attempt + 1))
        for m in re.finditer(r"(P\d+)\s*,\s*(yes|no|cannot tell)", text):
            done[m.group(1)] = m.group(2)
        lines = ["id,label"] + [f"{i},{done[i]}" for i, _ in its if i in done]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  {chunk[0][0]}-{chunk[-1][0]}: {len(done)}/{len(its)}", flush=True)

    missing = [i for i, _ in its if i not in done]
    if missing:
        print(f"\n{len(missing)} items unlabelled: {missing[:10]}")
        return 1
    print(f"\nwrote {out_path}: {len(done)} of {len(its)} labelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
