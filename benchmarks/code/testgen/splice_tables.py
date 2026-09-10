"""Splice records/testgen-val/tables.md into RESULTS-TESTGEN-VAL.md, table by table, verbatim.

The results file holds a marker pair per table; this script replaces what lies between
each pair with that table's section from ``tables.md``, which ``testgen_val.py report``
renders from the records. The prose is written by hand, the tables never are — the test
compares both directions byte for byte, so a figure edited in the results file, or a
table added, dropped or duplicated there, fails.

    python benchmarks/code/testgen/splice_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE))

TABLES = CODE / "records" / "testgen-val" / "tables.md"
RESULTS = CODE / "RESULTS-TESTGEN-VAL.md"


def sections(tables: str) -> dict[str, str]:
    """``tables.md`` split on its ``<!-- TABLE name -->`` lines, in order."""
    out: dict[str, str] = {}
    name: str | None = None
    body: list[str] = []
    for line in tables.splitlines():
        if line.startswith("<!-- TABLE ") and line.endswith(" -->"):
            if name is not None:
                out[name] = "\n".join(body).strip("\n") + "\n"
            name = line[len("<!-- TABLE "):-len(" -->")]
            body = []
        elif name is not None:
            body.append(line)
    if name is not None:
        out[name] = "\n".join(body).strip("\n") + "\n"
    return out


def markers(name: str) -> tuple[str, str]:
    return (f"<!-- BEGIN TABLE {name} (records/testgen-val/tables.md) -->",
            f"<!-- END TABLE {name} -->")


def main() -> int:
    text = RESULTS.read_text(encoding="utf-8")
    parts = sections(TABLES.read_text(encoding="utf-8"))
    for name, body in parts.items():
        begin, end = markers(name)
        assert text.count(begin) == 1 and text.count(end) == 1, f"marker pair for {name!r} is not unique"
        a, b = text.index(begin) + len(begin), text.index(end)
        assert a < b, f"markers for {name!r} are out of order"
        text = text[:a] + "\n" + body + text[b:]
    RESULTS.write_text(text, encoding="utf-8")
    print(f"spliced {len(parts)} tables: {', '.join(parts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
