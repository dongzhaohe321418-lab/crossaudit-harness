"""Splice records/inject/tables.md into RESULTS-INJECT.md, table by table, verbatim.

    python benchmarks/code/inject/splice_tables.py

The prose is written by hand, the tables never are. The test compares both directions byte
for byte and holds the results file to the skeleton below, so a figure edited in place, or a
table added, dropped, duplicated or moved to another section, fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE))

TABLES = CODE / "records" / "inject" / "tables.md"
RESULTS = CODE / "RESULTS-INJECT.md"

#: name in tables.md, the section heading it belongs under, and the last non-blank line of
#: prose before its BEGIN marker.
REGISTRY = (
    ("primary", "## 1. What was measured",
     "910 stratum-C instances in one seeded order; 281 passed the filters and 92 passed both gates."),
    ("rejected", "## 1. What was measured",
     "then refused**, drawn by `random.Random(20260916)`, under the same auditor and the same K = 8."),
    ("paired", "## 1. What was measured",
     "confound: every instance of I was audited again without the injected lines."),
    ("curve", "## 1. What was measured",
     "And the reading barely needs repeating:"),
    ("probe", "## 3. The limitation that matters most: the defects are detectably artificial",
     "ask whether it was written in one pass or written and then edited."),
    # Round 2: this anchor still demanded "it points the other way", the sentence commit
    # 60babd8 replaced when it found the cross-tab carries no information. The registry is
    # executable machinery, so a stale anchor here is a surviving endorsement of a withdrawn
    # reading -- and the test that would have caught it had been failing, unrun, since then.
    ("xtab", "## 3. The limitation that matters most: the defects are detectably artificial",
     "information, and it is kept here with that verdict rather than deleted:"),
    ("splits", "## 4. The other preregistered secondaries", "## 4. The other preregistered secondaries"),
)


def sections(tables: str) -> dict[str, str]:
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
    return (f"<!-- BEGIN TABLE {name} (records/inject/tables.md) -->",
            f"<!-- END TABLE {name} -->")


def main() -> int:
    text = RESULTS.read_text(encoding="utf-8")
    parts = sections(TABLES.read_text(encoding="utf-8"))
    assert list(parts) == [name for name, _, _ in REGISTRY], \
        f"tables.md sections {list(parts)} do not match the registry"
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
