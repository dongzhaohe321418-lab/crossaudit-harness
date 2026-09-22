#!/usr/bin/env python3
"""P3 Amendment 1 — a third rater on the blinded 121-item sheet.

Registered at `plan/P3-PREREGISTRATION.md` Amendment 1 before this ran. The premise P3 rests on
comes from study 21's consensus of L1 -- "the author" -- and L2, `gpt-6-astra`, on sheets that
Amendment 2 of that study found were not blind to instance identity. **And the record does not
establish who produced L1's labels**: the rerate study has no cost ledger, so nothing distinguishes
a human rater from a model one there. The third rater is therefore chosen to be independent of
both possibilities -- not `gpt-6-astra`, and not an Anthropic model, since the labels may have been
produced by one.

`gpt-5.6-luna` is the least entangled route available. It is not clean: it served as `cheap-cross`
in the explore study and as one of study 22's probe alternatives. It is not `gpt-5.6-terra`, whose
misses define the residual being judged, which is the entanglement that would matter most.

The rater is given the booklet's own rubric verbatim and nothing else. This file adds no
instruction, no example and no hint of the hypothesis.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
from crossaudit.providers import openai_compat  # noqa: E402

SHEET = Path.home() / "Desktop" / "CrossAudit-审计天花板" / "人类评分任务"
MODEL = "gpt-5.6-luna"
KEY_ENV = "CROSSAUDIT_AUDITOR_KEY"
BATCH = 6
OUT = Path("benchmarks/code/records/rate3/L3.csv")

#: The booklet's own instruction, copied from 评分册.md, translated to English for the rater and
#: otherwise unchanged. The three labels are the booklet's.
RUBRIC = """For each item you are asked one thing only:

> Does the specification's prose determine what should be returned on the failing input class?

Not whether the code is correct. Not whether the tests are reasonable. Only whether this piece
of text pins the answer down.

  determined    — the specification says. A careful reader can derive what should be returned.
  undetermined  — the specification does not say. Several answers fit this text, and the hidden
                  suite picked one of them.
  cannot-tell   — you cannot tell (the specification is too short, the failing class is unclear,
                  or you are unsure).

`cannot-tell` is a legitimate answer. Do not force a choice to make the sheet look tidy.

Answer with one line per item, exactly `<id>,<label>`, and nothing else."""


def items() -> list[tuple[str, str]]:
    """(id, the item as the booklet shows it) for all 121, from the booklet itself."""
    text = (SHEET / "评分册.md").read_text(encoding="utf-8")
    parts = re.split(r"^## (H\d+)$", text, flags=re.M)[1:]
    out = []
    for rid, body in zip(parts[0::2], parts[1::2]):
        body = re.sub(r"\*\*H\d+ 你的判断：\*\*.*$", "", body, flags=re.S).strip()
        out.append((rid, body))
    return out


def main() -> int:
    # The key file is a shell fragment: its lines start with `export`. Stripping that is the
    # whole of the difference between this running and a ConfigDenial.
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    rows = items()
    assert len(rows) == 121, len(rows)
    labels: dict[str, str] = {}
    spend_note = []
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        prompt = "\n\n".join(f"## {rid}\n{body}" for rid, body in chunk)
        text = ""
        for attempt in range(1, 4):
            try:
                reply = openai_compat.complete(
                    model=MODEL, key_env=KEY_ENV, system=RUBRIC, prompt=prompt,
                    max_tokens=3000, timeout=240.0)
                text = getattr(reply, "text", "") or ""
                spend_note.append(getattr(reply, "cost_usd", None))
                if text.strip():
                    break
                print(f"  {chunk[0][0]}-{chunk[-1][0]}: empty completion, attempt {attempt}/3",
                      flush=True)
            except Exception as exc:                                   # noqa: BLE001
                # A batch that never returns is a hole in the sheet, not a reason to lose the
                # batches that did. It is reported at the end and left unlabelled.
                print(f"  {chunk[0][0]}-{chunk[-1][0]}: {type(exc).__name__}, attempt {attempt}/3",
                      flush=True)
            time.sleep(5 * attempt)
        for m in re.finditer(r"(H\d+)\s*,\s*(determined|undetermined|cannot-tell)", text):
            labels[m.group(1)] = m.group(2)
        print(f"  {chunk[0][0]}-{chunk[-1][0]}: {len(labels)} labelled so far", flush=True)

    missing = [rid for rid, _ in rows if rid not in labels]
    if missing:
        print(f"  !! {len(missing)} items returned no parsable label: {missing[:8]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("rate_id,label\n" + "".join(
        f"{rid},{labels.get(rid, '')}\n" for rid, _ in rows), encoding="utf-8")
    known = [c for c in spend_note if isinstance(c, (int, float))]
    print(f"\nwrote {OUT}: {len(labels)} of {len(rows)} labelled"
          + (f", spend ${sum(known):.4f}" if known else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
