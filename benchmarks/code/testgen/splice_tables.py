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

#: The skeleton: which table goes where, in order — its name in ``tables.md``, the section
#: heading it belongs under, and the last non-blank line of prose before its BEGIN marker.
#: The tests hold the results file to this, so a block cannot be moved to another section,
#: reordered, duplicated or dropped without failing. They do NOT make what renders a function
#: of the records: round 9 found nine document mutations that leave all five generated blocks
#: byte-identical and still change the rendered document, one of which leaves it entirely
#: inside a code fence and renders zero tables. That guarantee is withdrawn (Results section 5);
#: the records are authoritative and this Markdown is a convenience.
REGISTRY = (
    ("primary", "## 1. The preregistered decision",
     "also fails on the canonical solution), 89 right."),
    ("arm", "## 2. Secondaries, as preregistered",
     "  draw-1 timeout), reported and not decided on:"),
    ("where", "## 3. Exploratory, post hoc, not preregistered (`testgen/exploratory_val.py`)",
     "also fails the canonical solution):"),
    ("pc", "## 3. Exploratory, post hoc, not preregistered (`testgen/exploratory_val.py`)",
     "fails the visible suite, corroboration is trivial: broken code fails correct tests too."),
    ("corroboration", "## 3. Exploratory, post hoc, not preregistered (`testgen/exploratory_val.py`)",
     "applications:"),
)

#: Every heading the results file may carry, in order. A heading is any line matching
#: ``^#{1,6}\s`` — a tab counts, so a heading cannot be smuggled past the check by writing
#: ``##\ttitle``, and a sub-heading cannot be inserted to put a table under a caption the
#: registry does not know. Round 7.
HEADINGS = (
    "# Study 17 — recognising a wrong generated test without the canonical solution: results",
    "## 1. The preregistered decision",
    "## 2. Secondaries, as preregistered",
    "## 3. Exploratory, post hoc, not preregistered (`testgen/exploratory_val.py`)",
    "## 4. What the preregistration said would follow, and what follows",
    "## 5. Deviations and disclosed limits",
)


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
    assert list(parts) == [name for name, _, _ in REGISTRY], "tables.md sections do not match the registry"
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
