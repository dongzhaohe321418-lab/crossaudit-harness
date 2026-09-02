"""The repair guard: a repair may not make a finding disappear (D148 slice D).

Every guard here is shown to fail against a deliberate mutation (D10); the
mutation is named in each docstring. The other half of D10 is D121: a guard
that reddens honest content is as much a defect, so every red case has a
green twin with the same words in a document file.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from crossaudit.repair_guard import (DEFENSIVE_PATTERNS, RepairGuard, is_code_file,
                                     parse_unified_diff)


def _diff(path: str, added: list[str], removed: list[str] = ()) -> str:
    body = "".join(f"-{ln}\n" for ln in removed) + "".join(f"+{ln}\n" for ln in added)
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,{len(removed)} +1,{len(added)} @@\n{body}")


# ---------------------------------------------------------------- codex port

def test_repair_guard_rejects_defensive_and_out_of_scope_changes():
    """Mutation: allow other.py or drop the try/except -> the guard passes."""
    diff = """diff --git a/other.py b/other.py
--- a/other.py
+++ b/other.py
@@ -1 +1,4 @@
-run()
+try:
+    run()
+except Exception:
+    pass
"""
    result = RepairGuard().assess(diff, {"result.py"})
    assert not result.allowed
    assert result.unsupported_files == ("other.py",)
    assert {"broad_exception", "silent_pass"} <= set(result.defensive_patterns)
    # Reasons are plain sentences naming the file, not jargon codes.
    assert any(r.startswith("other.py is outside") for r in result.reasons)
    assert any("other.py adds a catch-all `except`" in r for r in result.reasons)
    assert RepairGuard().assess(_diff("other.py", ["run()"]), {"other.py"}).allowed


def test_trusted_local_renderer_may_replace_a_binary_in_scope():
    """Mutation: drop report.pdf from locally_rendered_files -> refused."""
    diff = """diff --git a/report.pdf b/report.pdf
index 1111111..2222222 100644
Binary files a/report.pdf and b/report.pdf differ
"""
    ok = RepairGuard().assess(diff, set(), locally_rendered_files={"report.pdf"})
    assert ok.allowed and ok.changed_files == ("report.pdf",)
    model_written = RepairGuard().assess(diff, {"report.pdf"})
    assert not model_written.allowed
    assert model_written.binary_files == ("report.pdf",)
    assert any("report.pdf is a binary file" in r for r in model_written.reasons)


# ---------------------------------------------------- one red, one green each

_RED_GREEN = {
    "broad_exception": ("except Exception:", "except ValueError:"),
    "silent_pass": ("    pass", "    passed = True"),
    "retry_or_fallback": ("    return retry(fn)", "    return entry(fn)"),
    "suppression": ("x = 1  # noqa", "x = 1  # note"),
    "disabled_assertion": ("@pytest.mark.skip", "assert value == 1"),
}


def test_pattern_collection_surface_has_not_shrunk():
    """D10 amendment: a refactor that drops a pattern must fail loudly."""
    assert set(DEFENSIVE_PATTERNS) == set(_RED_GREEN)


@pytest.mark.parametrize("name", sorted(_RED_GREEN))
def test_each_pattern_has_a_red_and_a_green_line_in_code(name):
    """Mutation: swap the red and green lines -> both halves fail."""
    red, green = _RED_GREEN[name]
    flagged = RepairGuard().assess(_diff("src/x.py", [red]), {"src/x.py"})
    assert not flagged.allowed and flagged.defensive_patterns == (name,)
    assert flagged.reasons[0].startswith("src/x.py adds ")
    clean = RepairGuard().assess(_diff("src/x.py", [green]), {"src/x.py"})
    assert clean.allowed, clean.reasons


@pytest.mark.parametrize("name", sorted(_RED_GREEN))
def test_patterns_only_screen_added_lines(name):
    """Mutation: screen removed lines too -> deleting a bad line is refused."""
    red, _green = _RED_GREEN[name]
    result = RepairGuard().assess(_diff("src/x.py", ["fixed()"], removed=[red]),
                                  {"src/x.py"})
    assert result.allowed, result.reasons


# --------------------------------------------------- D121: prose is not code

PROSE = ["We skip the introduction and fallback to the plan.",
         "A retry of the fit did not change the best-effort estimate.",
         "except: the noqa xfail wording here is ordinary English"]


@pytest.mark.parametrize("path", ["SUMMARY.md", "notes.txt", "data.csv",
                                  "paper.tex", "report.rst", "README"])
def test_prose_with_retry_fallback_skip_is_not_flagged(path):
    """Positive control below: the same lines in a .py ARE flagged.

    Mutation: add the suffix to CODE_SUFFIXES -> this reddens (D121 defect).
    """
    assert not is_code_file(path)
    result = RepairGuard().assess(_diff(path, PROSE), {path})
    assert result.allowed, result.reasons
    assert result.defensive_patterns == ()


def test_the_same_words_in_a_code_file_are_flagged():
    """The positive control for the prose test: the words are what trigger."""
    result = RepairGuard().assess(_diff("src/x.py", PROSE), {"src/x.py"})
    assert not result.allowed
    assert {"retry_or_fallback", "disabled_assertion",
            "suppression", "broad_exception"} <= set(result.defensive_patterns)


@pytest.mark.parametrize("path,code", [
    ("a.py", True), ("a.pyi", True), ("a.ts", True), ("a.tsx", True), ("a.sh", True),
    ("a.go", True), ("a.rs", True), ("a.R", True), ("a.jl", True), ("a.sql", True),
    ("a.yml", True), ("a.toml", True), ("a.json", True), ("Makefile", True),
    ("docker/Dockerfile", True), ("a.md", False), ("a.txt", False), ("a.csv", False),
    ("a.tex", False), ("a.pdf", False), ("a.png", False), ("Makefile.md", False),
])
def test_code_file_classification(path, code):
    assert is_code_file(path) is code


# ----------------------------------------------------------- the line budget

def test_document_rewrite_is_exempt_from_the_budget_but_code_is_not():
    """A re-rendered report is legitimately large; 300 code lines are not.

    Mutation: count document lines toward the budget -> the .md is refused.
    """
    lines = [f"line {i}" for i in range(300)]
    doc = RepairGuard(200).assess(_diff("report.md", lines), {"report.md"})
    assert doc.allowed and doc.changed_lines == 0 and doc.document_lines == 300
    code = RepairGuard(200).assess(_diff("src/x.py", lines), {"src/x.py"})
    assert not code.allowed and code.changed_lines == 300
    assert code.reasons == (
        "the code change touches 300 lines, more than the 200-line limit for "
        "an automatic repair",)


def test_budget_counts_removed_code_lines_too():
    """Mutation: count only added lines -> a 250-line deletion passes."""
    result = RepairGuard(200).assess(
        _diff("src/x.py", ["one()"], removed=[f"old_{i}()" for i in range(250)]),
        {"src/x.py"})
    assert not result.allowed and result.changed_lines == 251


def test_document_files_are_still_held_to_scope():
    """Budget-exempt is not scope-exempt (mutation: exempt documents from scope)."""
    result = RepairGuard().assess(_diff("other.md", ["hello"]), {"report.md"})
    assert not result.allowed
    assert result.reasons == (
        "other.md is outside what the last audit asked to change (allowed: report.md)",)


def test_budget_must_be_positive():
    with pytest.raises(ValueError):
        RepairGuard(0)


def test_empty_diff_is_refused_with_a_reason():
    result = RepairGuard().assess("", set())
    assert not result.allowed and result.changed_files == ()
    assert result.reasons == ("the revision changed nothing that could be reviewed",)


# --------------------------------------------- real git diff --cached shapes

def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout


def test_a_real_staged_multi_file_diff_parses_added_and_removed_counts(tmp_path):
    """The exact bytes build.py hands the guard: git diff --cached --binary.

    Mutation: treat `--- a/x` as a removed line -> counts are off by one per
    file; treat `+++ b/x` as an added line -> the header path is screened.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "t@example.invalid", cwd=repo)
    _git("config", "user.name", "T", cwd=repo)
    (repo / "src").mkdir()
    (repo / "src/calc.py").write_text("def run():\n    return 1\n    # keep\n")
    (repo / "SUMMARY.md").write_text("one\ntwo\n")
    (repo / "fig.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00old")
    (repo / "with space.md").write_text("old\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "base", cwd=repo)
    (repo / "src/calc.py").write_text("def run():\n    return 2\n")
    (repo / "SUMMARY.md").write_text("one\ntwo\nthree\nfour\n")
    (repo / "fig.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00new")
    (repo / "with space.md").write_text("new\n")
    (repo / "new.txt").write_text("fresh\n")
    _git("add", "-A", cwd=repo)
    diff = _git("diff", "--cached", "--binary", "--no-ext-diff", cwd=repo)

    files = parse_unified_diff(diff)
    assert set(files) == {"src/calc.py", "SUMMARY.md", "fig.png",
                          "with space.md", "new.txt"}
    assert files["src/calc.py"].added == ["    return 2"]
    assert files["src/calc.py"].removed == 2
    assert files["SUMMARY.md"].added == ["three", "four"]
    assert files["SUMMARY.md"].removed == 0
    assert files["fig.png"].binary and files["fig.png"].added == []
    assert files["new.txt"].added == ["fresh"]

    scope = {"src/calc.py", "SUMMARY.md", "with space.md", "new.txt"}
    result = RepairGuard().assess(diff, scope, locally_rendered_files={"fig.png"})
    assert result.allowed, result.reasons
    # code: calc.py -2/+1; documents: SUMMARY +2, 'with space.md' -1/+1, new.txt +1
    assert result.changed_lines == 3 and result.document_lines == 5
    # The same staged bytes with the png written by the model: refused.
    assert not RepairGuard().assess(diff, scope | {"fig.png"}).allowed


def test_a_deleted_file_is_still_a_changed_file():
    """Mutation: drop the diff --git header path -> the deletion is invisible."""
    diff = ("diff --git a/src/old.py b/src/old.py\ndeleted file mode 100644\n"
            "--- a/src/old.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a()\n-b()\n")
    result = RepairGuard().assess(diff, {"src/new.py"})
    assert result.changed_files == ("src/old.py",)
    assert result.unsupported_files == ("src/old.py",)
    assert result.changed_lines == 2
