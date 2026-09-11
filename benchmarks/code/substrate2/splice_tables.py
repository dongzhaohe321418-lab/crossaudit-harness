"""Splice records/substrate2/tables.md's blocks into RESULTS-SUBSTRATE2.md, verbatim.

    python benchmarks/code/substrate2/splice_tables.py

Each table has its own marker pair. The body between a pair in the results document is
replaced by the body between the same pair in ``tables.md``, byte for byte; nothing else
in the document is touched, and no markdown is parsed.
"""
from __future__ import annotations

import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE))

from report_substrate2 import TABLE_KEYS, begin, end  # noqa: E402

TABLES = CODE / "records" / "substrate2" / "tables.md"
RESULTS = CODE / "RESULTS-SUBSTRATE2.md"


def body(text: str, key: str) -> str:
    a = text.index(begin(key)) + len(begin(key))
    b = text.index(end(key))
    return text[a:b]


def main() -> int:
    tables = TABLES.read_text(encoding="utf-8")
    text = RESULTS.read_text(encoding="utf-8")
    for key in TABLE_KEYS:
        a = text.index(begin(key)) + len(begin(key))
        b = text.index(end(key))
        text = text[:a] + body(tables, key) + text[b:]
    RESULTS.write_text(text, encoding="utf-8")
    print(f"spliced {len(TABLE_KEYS)} table blocks into {RESULTS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
