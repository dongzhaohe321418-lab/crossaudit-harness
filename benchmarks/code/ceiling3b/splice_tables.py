"""Splice records/ceiling3b/tables.md into RESULTS-CEILING3B.md between its markers, verbatim.

    python benchmarks/code/ceiling3/splice_tables.py
"""
from __future__ import annotations

from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
BEGIN, END = "<!-- BEGIN TABLES (records/ceiling3b/tables.md) -->", "<!-- END TABLES -->"


def main() -> int:
    tables = (CODE / "records" / "ceiling3b" / "tables.md").read_text(encoding="utf-8")
    path = CODE / "RESULTS-CEILING3B.md"
    text = path.read_text(encoding="utf-8")
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    path.write_text(text[:a] + "\n" + tables + text[b:], encoding="utf-8")
    print("spliced", len(tables.splitlines()), "table lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
