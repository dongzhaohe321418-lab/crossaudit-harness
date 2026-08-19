"""Large work files are outlined, not dumped whole, into the generator prompt.

The generator used to receive every scope-dir file in full every round. Small
files still are (the common case); a large file's body is replaced by a compact,
deterministic structural outline plus a marker telling the generator to pull the
full contents with the audited file_read tool — bounding context without losing
recall, and without touching the auditor or the committed bytes.
"""
from __future__ import annotations

from crossaudit.context import (
    MAX_FILE_BYTES,
    MAX_WORK_BYTES,
    outline,
    shape_work,
)


def _big(seed: str) -> str:
    return seed + "\n" + ("padding line\n" * (MAX_FILE_BYTES // 12))


def test_small_files_pass_through_verbatim():
    files = {"work/a.md": "# Note\n\nshort body\n", "work/b.py": "x = 1\n"}
    assert shape_work(files) == files                 # byte-identical, no change


def test_a_large_markdown_file_is_reduced_to_its_headings():
    body = _big("# Review\n## Overview\nlots\n## Method\nlots\n### Detail\n")
    shaped = shape_work({"work/review.md": body})["work/review.md"]
    assert "large file elided" in shaped and "file_read" in shaped
    assert "## Overview" in shaped and "## Method" in shaped and "### Detail" in shaped
    assert "padding line\npadding line" not in shaped   # the bulk body is gone


def test_a_large_python_file_is_reduced_to_its_symbols():
    src = ('"""Module purpose.\n\nmore.\n"""\n'
           "import os\nfrom pathlib import Path\n\n"
           "def top(a, b):\n    return a\n\n"
           "class Widget:\n    def render(self):\n        return 1\n")
    src += "\n" + ("# filler comment line\n" * (MAX_FILE_BYTES // 20))
    shaped = shape_work({"pkg/mod.py": src})["pkg/mod.py"]
    assert "def top(...):" in shaped and "class Widget:" in shaped
    assert "def render(...):" in shaped and "import os" in shaped
    assert '"""Module purpose."""' in shaped
    assert "# filler comment line\n# filler comment line" not in shaped


def test_large_json_is_reduced_to_top_level_keys():
    body = '{\n"alpha": 1,\n"beta": 2,\n' + "".join(
        f'"k{i}": {i},\n' for i in range(MAX_FILE_BYTES // 8)) + '"omega": 0\n}\n'
    shaped = shape_work({"work/data.json": body})["work/data.json"]
    # The leading keys are named (the list is deterministically capped, so far
    # trailing keys are dropped — the outline is a scaffold, not a full copy).
    assert "top-level keys:" in shaped and "alpha" in shaped and "beta" in shaped
    assert '"k0": 0' not in shaped                    # values are not inlined


def test_malformed_python_falls_back_to_head_not_crash():
    src = "def broken(:\n" + ("x\n" * (MAX_FILE_BYTES // 2))
    shaped = shape_work({"pkg/bad.py": src})["pkg/bad.py"]
    assert "large file elided" in shaped
    assert "more lines elided" in shaped              # fell back to leading lines


def test_outline_is_deterministic():
    body = _big("# A\n## B\n## C\n")
    assert outline("work/x.md", body) == outline("work/x.md", body)


def test_many_small_files_are_bounded_by_the_total_budget():
    # Each file is individually under MAX_FILE_BYTES, but together they exceed
    # the aggregate budget: the largest are outlined until the set fits.
    each = "# doc\n" + ("body line for a mid-size file\n" * 1000)   # ~30KB < cap
    n = (MAX_WORK_BYTES // len(each.encode("utf-8"))) + 5
    files = {f"work/f{i:03d}.md": each for i in range(n)}
    shaped = shape_work(files)
    total = sum(len(v.encode("utf-8")) for v in shaped.values())
    assert total <= MAX_WORK_BYTES
    assert any("large file elided" in v for v in shaped.values())   # some outlined
    assert set(shaped) == set(files)                                # every path kept


def test_total_budget_pass_is_deterministic():
    each = "# d\n" + ("x line\n" * 4000)
    files = {f"work/f{i}.md": each for i in range(40)}
    assert shape_work(files) == shape_work(files)
