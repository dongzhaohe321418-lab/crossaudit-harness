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
from crossaudit.context.outline import MAX_OUTLINE_BYTES


def _big(seed: str) -> str:
    return seed + "\n" + ("padding line\n" * (MAX_FILE_BYTES // 12))


def test_small_files_pass_through_verbatim():
    files = {"work/a.md": "# Note\n\nshort body\n", "work/b.py": "x = 1\n"}
    assert shape_work(files) == files                 # byte-identical, no change


def test_condensation_observer_is_silent_for_unchanged_files():
    reports = []
    files = {"work/a.md": "# Note\n\nshort body\n"}
    assert shape_work(files, on_condense=reports.append) == files
    assert reports == []


def test_a_large_markdown_file_is_reduced_to_its_headings():
    body = _big("# Review\n## Overview\nlots\n## Method\nlots\n### Detail\n")
    shaped = shape_work({"work/review.md": body})["work/review.md"]
    assert "large file elided" in shaped and "file_read" in shaped
    assert "## Overview" in shaped and "## Method" in shaped and "### Detail" in shaped
    assert "padding line\npadding line" not in shaped   # the bulk body is gone


def test_condensation_observer_names_outlined_and_stubbed_files():
    reports = []
    body = "\n".join(f"line {i}" for i in range(200))
    files = {"work/a.txt": body, "work/b.txt": body}
    observed = shape_work(files, total_budget=1, on_condense=reports.append)
    assert observed == shape_work(files, total_budget=1)
    assert len(reports) == 1
    report = reports[0]
    assert report["reduction"] == "work_files"
    assert set(report["outlined"]) == {"work/a.txt", "work/b.txt"}
    assert set(report["stubbed"]) == {"work/a.txt", "work/b.txt"}
    assert report["before_bytes"] > report["after_bytes"]
    assert report["recovery"] == "file_read"


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


def test_a_pathological_huge_outline_is_itself_capped():
    # 60k one-line defs: without a cap the "outline" would be ~1MB and blow the
    # budget it was meant to shrink. The outline is bounded instead.
    src = "".join(f"def f{i}(): pass\n" for i in range(60_000))
    val = shape_work({"pkg/huge.py": src})["pkg/huge.py"]
    assert "large file elided" in val and "outline truncated" in val
    assert len(val.encode("utf-8")) <= MAX_OUTLINE_BYTES + 500


def test_hard_ceiling_is_actually_enforced_by_stubbing():
    # Even outlined, 40 * ~40KB files would be ~640KB > budget. Pass 3 stubs the
    # least-relevant until the whole set is truly within MAX_WORK_BYTES.
    body = "\n".join("z" * 1000 for _ in range(40)) + "\n"        # ~40KB, kept full
    files = {f"work/f{i:03d}.md": body for i in range(40)}         # ~1.6MB raw
    shaped = shape_work(files)
    total = sum(len(v.encode("utf-8")) for v in shaped.values())
    assert total <= MAX_WORK_BYTES                                 # a real ceiling
    assert set(shaped) == set(files)                               # every path kept
    assert any("not shown this round" in v for v in shaped.values())   # some stubbed


def test_relevance_spends_recall_on_the_least_related_files_first():
    filler = "\n".join("lorem ipsum dolor " * 60 for _ in range(40)) + "\n"   # ~40KB
    relevant = "# QLED review\n" + "\n".join("qled review analysis " * 40
                                             for _ in range(40))               # ~40KB
    # Enough files that even fully outlined they exceed budget, so pass 3 (stub)
    # runs and its relevance ordering is actually exercised.
    files = {f"work/other{i:02d}.md": filler for i in range(40)}
    files.update({f"work/qled{i:02d}.md": relevant for i in range(5)})
    shaped = shape_work(files, task="write a detailed review of qled")
    total = sum(len(v.encode("utf-8")) for v in shaped.values())
    assert total <= MAX_WORK_BYTES
    qled_stubbed = sum("not shown this round" in shaped[p]
                       for p in files if "qled" in p)
    other_stubbed = sum("not shown this round" in shaped[p]
                        for p in files if "other" in p)
    assert qled_stubbed == 0        # task-relevant files are not the ones dropped
    assert other_stubbed > 0        # the irrelevant ones are dropped first


def test_relevance_matches_whole_words_not_substrings_and_drops_stopwords():
    from crossaudit.context.outline import _relevance, _terms
    terms = _terms("add the user login and the password reset flow")
    # generic verbs and function words carry no signal
    assert "the" not in terms and "and" not in terms and "add" not in terms
    assert "login" in terms and "password" in terms
    # a decoy stuffed with words that merely CONTAIN the letters must score 0,
    # while a file with the real whole words scores > 0 — the inversion the review
    # found is gone.
    decoy = "theme candidate standard additional brand " * 50
    real = "login screen: password reset flow for the user login and profile"
    assert _relevance("themes/config.txt", decoy, terms) == 0
    assert _relevance("auth/login.py", real, terms) > 0


def test_findings_named_files_are_kept_fullest():
    # A file the auditor flagged must be reduced last / never stubbed while any
    # un-named file remains — it is exactly what the generator is told to fix.
    body = "\n".join("z" * 1000 for _ in range(40)) + "\n"        # ~40KB, kept full
    files = {f"work/f{i:03d}.md": body for i in range(30)}
    fixme = "work/f015.md"
    findings = f"CA-DATA-001 in {fixme}: the table does not match the text."
    shaped = shape_work(files, task="fix the data", findings=findings)
    total = sum(len(v.encode("utf-8")) for v in shaped.values())
    assert total <= MAX_WORK_BYTES
    # the flagged file is never the one dropped to a stub
    assert "not shown this round" not in shaped[fixme]
    assert any("not shown this round" in shaped[p] for p in files if p != fixme)


def test_pass_two_outlining_shrinks_never_grows():
    # ~40KB files with <=40 very long lines: head_outline returns the whole body,
    # so a naive elide would GROW them (header + full body). With the outline cap
    # the elided form is strictly smaller, and the total only ever decreases.
    body = "\n".join("y" * 1000 for _ in range(40)) + "\n"        # ~40KB, <=40 lines
    files = {f"work/f{i:02d}.csv": body for i in range(12)}        # ~480KB > budget
    raw_total = sum(len(v.encode("utf-8")) for v in files.values())
    assert raw_total > MAX_WORK_BYTES
    shaped = shape_work(files)
    total = sum(len(v.encode("utf-8")) for v in shaped.values())
    assert total <= raw_total                 # never grew
    assert total <= MAX_WORK_BYTES            # and actually bounded now
    assert set(shaped) == set(files)          # every path kept
