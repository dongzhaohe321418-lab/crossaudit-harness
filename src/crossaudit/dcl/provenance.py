"""A4 (C.2): the deterministic citation-provenance check — opt-in, non-overridable.

When a project turns on the ``source_provenance`` check, a report may only claim
sources it actually retrieved through the governed research tools. The report
declares its cited sources in a fenced code block:

    ```crossaudit-sources
    ["<64-hex source_id>", "<64-hex source_id>"]
    ```

and this check confirms, mechanically, that every declared id is a member of the
set of per-source provenance ids the run recorded in the evidence ledger (via
``web_fetch`` / ``paper_search``). Any declared id with no governed-tool evidence
is a BLOCKER — verdict-in-code, which the model audit cannot waive.

Honest boundary (never overclaim): this enforces that DECLARED cited sources were
governed-fetched, and it is internally consistent. It does not force a report to
declare every prose citation, it does not judge whether a cited claim is true, and
it says nothing about the remote server's honesty. A report that declares no
sources passes — there is nothing to contradict.
"""
from __future__ import annotations

import json
import re
from typing import Mapping

from .framework import BLOCKER, CheckContext, Finding, register

#: A fenced ```crossaudit-sources block; its body is a JSON array of source ids.
_FENCE = re.compile(r"```crossaudit-sources[^\n]*\n(.*?)\n```", re.S)
_TEXT_SUFFIXES = (".md", ".txt", ".rst", ".tex", ".json")


def _text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def check_source_provenance(files: Mapping[str, bytes],
                            context: CheckContext) -> list[Finding]:
    governed = context.governed_source_ids
    out: list[Finding] = []
    for path, data in sorted(files.items()):
        if not path.endswith(_TEXT_SUFFIXES):
            continue
        text = _text(data)
        if text is None:
            continue
        for body in _FENCE.findall(text):
            try:
                declared = json.loads(body)
            except json.JSONDecodeError as exc:
                out.append(Finding(
                    BLOCKER, "CA-SOURCE-001", path,
                    f"a crossaudit-sources declaration does not parse as JSON: {exc}"))
                continue
            if not isinstance(declared, list) or not all(
                    isinstance(item, str) for item in declared):
                out.append(Finding(
                    BLOCKER, "CA-SOURCE-001", path,
                    "a crossaudit-sources declaration must be a JSON array of "
                    "source-id strings"))
                continue
            for sid in declared:
                if sid not in governed:
                    out.append(Finding(
                        BLOCKER, "CA-SOURCE-001", path,
                        f"cited source {sid[:16]}… was not retrieved through a "
                        "governed tool (no matching evidence-ledger record); a "
                        "report may only cite sources it fetched under approval"))
    return out


register("source_provenance", check_source_provenance,
         "Opt-in: every source id a report declares in a ```crossaudit-sources "
         "block must be one the run retrieved through a governed research tool "
         "(web_fetch / paper_search) and recorded in the evidence ledger; an "
         "undeclared or ungoverned citation is a blocker. It does not judge the "
         "truth of a claim, only that a declared cited source was governed-fetched.",
         wants_context=True)
