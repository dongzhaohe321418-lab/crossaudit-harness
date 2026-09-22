#!/usr/bin/env python3
"""Rebuild the 121-item rating sheet on mechanical evidence, for both arms.

P3 Amendment 1 found the control arm unanswerable. `failing_input_class` lives in
`records/ceiling/residual_classification.json`, which by construction covers only the residual,
so 42 of the 53 caught items carried none -- and all 42 were rated `cannot-tell`, one to one.
The sheet could not compare the groups, and a human rater would have met the same wall.

`residual_dump.py` already recovers a **witness** for any stratum-P instance by re-executing its
failing hidden inputs. That evidence exists for both arms, passes through no hand step, and is
what both arms are rebuilt on here: 61 of 68 missed and 49 of 53 caught carry concrete failing
cases. The remainder is **not all timeouts**, as this docstring said until the first review of
`RESULTS-RATE3.md` checked it: the missed arm's seven are five timeouts and two whose inputs the
harness could not recover, and the caught arm's four are timeouts. Each is shown as what it is.

**The witness carries the expected value and this sheet does not show it.** The question is
whether the specification determines what should be returned on the failing input. Showing the expected value would
change the question being asked. Without a target, a rater judges whether the prose determines
what to return; with one, it judges whether the prose entails that particular value -- which is
what the six-category comparator asked, explicitly, and is a different question rather than a
weaker one. Whether a shown value would also anchor the rater is **not measured here**. Two
earlier versions of this docstring asserted more than that: first that a shown value makes a
rater judge the prose determines it, then that it reduces the question to consistency. Only the failing input is shown, recovered mechanically instead of written by
the author. This is **not** the same information content as the prose classes it replaces, as
this docstring claimed until the second review of `RESULTS-RATE3.md` checked it: some of those
classes stated oracle behaviour outright, which this deliberately withholds. The replacement is
comparable across arms and mechanically derived; it is not equivalent to what it replaced.

The rate_id to instance mapping is preserved exactly, so a partially completed sheet still maps.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SHEET = Path.home() / "Desktop" / "CrossAudit-审计天花板" / "人类评分任务"
DUMPS = Path.home() / "Documents" / "Crossaudit" / "study-data" / "wt-ceiling-runs"


def witnesses() -> dict[str, dict]:
    out = {}
    for name in ("residual", "caught"):
        for row in json.loads((DUMPS / name / "index.json").read_text(encoding="utf-8")):
            out[row["instance_id"]] = row
    return out


def failing_block(row: dict) -> str:
    """What the rater is shown about where the hidden suite fails. Inputs only."""
    w = row.get("witness") or {}
    kind = w.get("kind")
    if kind == "timeout" or row.get("hidden_timed_out"):
        return "> the hidden suite did not terminate inside the harness timeout"
    cases = w.get("cases") or []
    if not cases:
        n = row.get("hidden_failed_n")
        return (f"> the hidden suite fails on {n} of its {row.get('hidden_total')} cases; the "
                "harness could not recover the inputs")
    shown = cases[:3]
    lines = [f"> the hidden suite fails on {row.get('hidden_failed_n')} of its "
             f"{row.get('hidden_total')} cases. The first "
             f"{'few' if len(shown) > 1 else 'one'} failing input"
             f"{'s' if len(shown) > 1 else ''}:", ">"]
    for c in shown:
        lines.append(f"> - `{str(c.get('input'))[:300]}`")
    if len(cases) > len(shown):
        lines.append(f">\n> …and {len(cases) - len(shown)} more.")
    return "\n".join(lines)


def main() -> int:
    items = {i["rate_id"]: i for i in json.loads((SHEET / "_items.json").read_text("utf-8"))}
    wit = witnesses()
    book = (SHEET / "评分册.md").read_text(encoding="utf-8")
    head, body = book.split("## H001", 1)
    body = "## H001" + body

    parts = re.split(r"^## (H\d+)$", body, flags=re.M)[1:]
    rebuilt, missing = [], []
    for rid, chunk in zip(parts[0::2], parts[1::2]):
        inst = items[rid]["instance"]
        row = wit.get(inst)
        if row is None:
            missing.append(rid)
            rebuilt.append(f"## {rid}{chunk}")
            continue
        new_block = ("**隐藏测试在这里失败**\n\n" + failing_block(row) + "\n")
        replaced, n = re.subn(
            r"\*\*失败输入类\*\*（隐藏测试在这里挂掉）\n\n>.*?(?=\n\*\*H\d+ 你的判断)",
            new_block, chunk, flags=re.S)
        if n != 1:
            replaced, n = re.subn(
                r"\*\*失败输入类\*\*.*?(?=\n\*\*H\d+ 你的判断)", new_block, chunk, flags=re.S)
        if n != 1:
            missing.append(rid)
        rebuilt.append(f"## {rid}{replaced}")

    head = head.replace(
        "* **不要**去查这些实例之前被标成什么。编号已打乱、已盲化。",
        "* **不要**去查这些实例之前被标成什么。编号已打乱、已盲化。\n"
        "* 失败位置现在由机器重跑隐藏测试得出，两组的呈现方式完全相同。"
        "**只给失败的输入，不给期望值**——期望值等于答案，给了就没法问这个问题了。")
    (SHEET / "评分册.md").write_text(head + "".join(rebuilt), encoding="utf-8")
    print(f"rebuilt {len(rebuilt)} items; {len(missing)} could not be rebuilt: {missing[:8]}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
