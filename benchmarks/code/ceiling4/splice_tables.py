"""Splice records/ceiling4/tables.md into RESULTS-CEILING4.md between its markers, verbatim.

Each table in ``tables.md`` is delimited there by its own BEGIN/END marker pair, and every
pair is spliced into the results file at the matching pair. Nothing is reformatted: the
bytes between a pair in the results file are the bytes between that pair in ``tables.md``.

    python benchmarks/code/ceiling4/splice_tables.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
TABLES = CODE / "records" / "ceiling4" / "tables.md"
RESULTS = CODE / "RESULTS-CEILING4.md"

BEGIN = "<!-- BEGIN {name} (records/ceiling4/tables.md) -->"
END = "<!-- END {name} -->"
_BLOCK = re.compile(r"<!-- BEGIN (?P<name>[A-Z0-9-]+) \(records/ceiling4/tables\.md\) -->"
                    r"(?P<body>.*?)<!-- END (?P=name) -->", re.DOTALL)


def blocks(text: str) -> dict[str, str]:
    """name -> the bytes between that name's BEGIN and END markers, markers excluded."""
    out: dict[str, str] = {}
    for m in _BLOCK.finditer(text):
        if m.group("name") in out:
            raise SystemExit(f"duplicate block marker {m.group('name')}")
        out[m.group("name")] = m.group("body")
    return out


def splice(results_text: str, tables_text: str) -> str:
    source = blocks(tables_text)
    target = blocks(results_text)
    missing = sorted(set(source) - set(target))
    extra = sorted(set(target) - set(source))
    if missing or extra:
        raise SystemExit(f"marker mismatch; missing in results {missing}; not in tables.md {extra}")
    out = results_text
    for name, body in source.items():
        begin, end = BEGIN.format(name=name), END.format(name=name)
        a = out.index(begin) + len(begin)
        b = out.index(end, a)
        out = out[:a] + body + out[b:]
    return out


def main() -> int:
    tables = TABLES.read_text(encoding="utf-8")
    text = RESULTS.read_text(encoding="utf-8")
    spliced = splice(text, tables)
    RESULTS.write_text(spliced, encoding="utf-8")
    print(f"spliced {len(blocks(tables))} table blocks, {len(tables.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
