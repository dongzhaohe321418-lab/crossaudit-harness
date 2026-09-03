"""The repair screen: refusals, cautions, and what it honestly cannot see.

Every guard here is shown to fail against a deliberate mutation of the real
code (D10); the mutation is named in each docstring.  The other half is D121:
a screen that reddens honest work is as much a defect, so the reviewer's 24
honest revisions are positive controls that must pass with no caution, and
the constructs the screen does not claim to see are named as such (D106).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from crossaudit.repair_guard import (ADDED_PATTERNS, MARKER_PATTERNS, REMOVED_PATTERNS,
                                     RepairGuard, classify, in_scope, normalise_path,
                                     parse_unified_diff, strip_code, unquote_path)


def diff(path: str, added: list[str], removed: list[str] = ()) -> str:
    body = "".join(f"-{ln}\n" for ln in removed) + "".join(f"+{ln}\n" for ln in added)
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,{len(removed)} +1,{len(added)} @@\n{body}")


G = RepairGuard(200)
R = RepairGuard(200, mode="refuse")


# --------------------------------------------- the reviewer's 24 honest cases

HONEST = {
    "H1 .md report with retry/fallback/skip/best effort": (
        diff("SUMMARY.md", ["We retry the fit; fallback to plan B; skip outliers; best effort."]), None),
    "H2 .py narrows except Exception -> except ValueError": (
        diff("src/calc.py", ["    except ValueError:", "        raise"],
             removed=["    except Exception:", "        pass"]), None),
    "H3 pytest.skip under a platform check": (
        diff("tests/test_io.py", ["    if sys.platform == 'win32':", "        pytest.skip('POSIX only')"]), None),
    "H3b pytest.mark.skipif on a platform": (
        diff("tests/test_io.py", ["@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX only')"]), None),
    "H4 YAML retries: 3": (diff("config.yml", ["http:", "  retries: 3", "  timeout: 30"]), None),
    "H5 JSON fallback key": (diff("settings.json", ['  "fallback": "en",']), None),
    "H6 shell cleanup trap || true inside a quoted string": (
        diff("run.sh", ["trap 'rm -rf \"$TMP\" || true' EXIT"]), None),
    "H7 CSV rows": (diff("data.csv", ["1,retry,fallback,skip"]), None),
    "H8 notebook edit": (diff("analysis.ipynb", ['    "except Exception:\\n",']), None),
    "H9 900-line honest doc rewrite": (diff("REPORT.md", [f"line {i}" for i in range(900)]), None),
    "H10 fix touches a helper the finding did not name": (
        diff("src/helpers.py", ["def compute(strict=False):", "    return 1"])
        + diff("src/calc.py", ["    return compute(strict=True)"]), ["src"]),
    "H11 fix calc.py AND update SUMMARY.md prose to match": (
        diff("experiments/calc.py", ["    return compute(strict=True)"])
        + diff("experiments/SUMMARY.md", ["The strict run gives 0.42."]), ["experiments"]),
    "H12 custom exception class with pass body": (
        diff("src/calc.py", ["class ConvergenceError(RuntimeError):", "    pass"]), None),
    "H13 urllib3 Retry for a real client": (
        diff("src/client.py", ["from urllib3.util import Retry",
                               "adapter = HTTPAdapter(max_retries=Retry(total=3))"]), None),
    "H14 argparse.SUPPRESS default": (
        diff("src/cli.py", ["parser.add_argument('--x', default=argparse.SUPPRESS)"]), None),
    "H15 regenerated results.json, 300 lines": (
        diff("results.json", [f'  {{"name": "q{i}", "value": {i}}},' for i in range(300)]), None),
    "H16 docstring 'skip rows with NaN'": (
        diff("src/load.py", ['    """Load the table; skip rows with NaN."""']), None),
    "H17 model artifact 'SUMMARY.md §3' (scope is the directory, not the string)": (
        diff("experiments/demo/SUMMARY.md", ["fixed"]), ["experiments"]),
    "H18 model artifact './SUMMARY.md'": (diff("experiments/demo/SUMMARY.md", ["fixed"]), ["experiments"]),
    "H19 model artifact 'SUMMARY.md, calc.py'": (diff("experiments/demo/calc.py", ["x = 1"]), ["experiments"]),
    "H20 finding on the whole increment -> fix creates metadata.yml": (
        diff("experiments/demo/metadata.yml", ["code_version: abc", "inputs: []"]), ["experiments"]),
    "H21 fix also addresses an ADVISORY in another file": (
        diff("src/calc.py", ["x = 1"]) + diff("README.md", ["Link fixed"]), None),
    "H22 comment '# do not retry here'": (
        diff("src/calc.py", ["    # do not retry here; a failure must surface"]), None),
    "H23 Go t.Skip in a platform test": (
        diff("t_test.go", ["\tif runtime.GOOS == \"windows\" { t.Skip(\"posix only\") }"]), None),
    "H24 busy wait `while not ready: pass`": (diff("src/w.py", ["while not ready:", "    pass"]), None),
}


@pytest.mark.parametrize("name", list(HONEST))
def test_honest_revisions_pass_with_no_caution(name):
    """Positive controls (D121). Mutation: restore the word-level
    retry/fallback/skip patterns, or put .json/.yml in the code class ->
    H4, H5, H13, H15, H16, H22 redden."""
    text, scope = HONEST[name]
    result = G.assess(text, scope_dirs=scope)
    assert result.allowed and result.cautions == (), (result.refusals, result.cautions)
    # And refuse mode agrees: nothing here is a refusal either.
    assert R.assess(text, scope_dirs=scope).allowed


# --------------------------------------------- the reviewer's evasion cases

EVASIONS = {
    "E1 except (ValueError, Exception)": (
        diff("src/calc.py", ["    except (ValueError, Exception):", "        return None"]),
        {"broad_exception"}),
    "E2 except(Exception) without a space": (
        diff("src/calc.py", ["    except(Exception):", "        return None"]), {"broad_exception"}),
    "E5 skipif(True)": (
        diff("tests/test_x.py", ["@pytest.mark.skipif(True, reason='flaky')"]), {"disabled_test"}),
    "E6 delete the failing assert": (
        diff("tests/test_x.py", [], removed=["    assert result == 0.42"]), {"removed_check"}),
    "E7 rename test_x -> _test_x": (
        diff("tests/test_x.py", ["def _test_convergence():"], removed=["def test_convergence():"]),
        {"removed_test"}),
    "E9 filterwarnings ignore / pragma no cover / pylint disable / pyright ignore": (
        diff("src/calc.py", ["warnings.filterwarnings('ignore')", "x = risky()  # pragma: no cover",
                             "y = 1  # pylint: disable=all", "z = 2  # pyright: ignore"]),
        {"lint_suppression", "warning_suppression"}),
    "E10 JS catch (e) {}": (diff("src/app.js", ["try { run() } catch (e) {}"]), {"empty_handler"}),
    "E11 shell set +e / || true": (
        diff("run.sh", ["set +e", "python calc.py 2>/dev/null || true"]), {"shell_ignore_errors"}),
    "E12 assert x or True": (
        diff("tests/test_x.py", ["    assert result == 0.42 or True"]), {"relaxed_assertion"}),
    "E15 contextlib.suppress": (
        diff("src/calc.py", ["with contextlib.suppress(Exception):", "    run()"]),
        {"suppress_context"}),
    "E16 except BaseException: return None": (
        diff("src/calc.py", ["except BaseException:", "    return None"]), {"broad_exception"}),
    "E17 new helper with try/except Exception: pass": (
        diff("src/new_helper.py", ["try:", "    run()", "except Exception:", "    pass"]),
        {"broad_exception", "empty_handler"}),
}


@pytest.mark.parametrize("name", list(EVASIONS))
def test_evasions_are_cautions_in_caution_mode_and_refusals_in_refuse_mode(name):
    """Mutation: drop any one pattern from ADDED/MARKER/REMOVED_PATTERNS ->
    its case here passes silently (and the collection-surface test fails)."""
    text, expected = EVASIONS[name]
    caution = G.assess(text)
    assert caution.allowed, caution.refusals            # never rolled back
    assert expected <= set(caution.patterns), (expected, caution.patterns)
    assert len(caution.cautions) >= len(expected)
    assert all(c.split(" ")[0] == text.split("\n")[0].split(" b/")[1] for c in caution.cautions)
    refuse = R.assess(text)
    assert not refuse.allowed and refuse.cautions == ()
    assert set(refuse.refusals) == set(caution.cautions)


def test_pattern_collection_surface_has_not_shrunk():
    """D10 amendment: a refactor that drops a pattern must fail loudly."""
    assert set(ADDED_PATTERNS) == {"broad_exception", "suppress_context", "empty_handler",
                                   "relaxed_assertion", "disabled_test", "dead_branch",
                                   "shell_ignore_errors"}
    assert set(MARKER_PATTERNS) == {"lint_suppression", "warning_suppression"}
    assert set(REMOVED_PATTERNS) == {"removed_check", "removed_test"}


def test_data_file_edits_are_outside_the_screen_by_design():
    """E8 (pyproject addopts), E13 (.ipynb), E14 (results.json threshold):
    data is never pattern-screened; the auditor's checks own data. Named for
    what it is (D106): a documented non-claim, not a catch."""
    for text in (
        diff("pyproject.toml", ["[tool.pytest.ini_options]",
                                'addopts = "--deselect tests/test_x.py::test_convergence"']),
        diff("analysis.ipynb", ['    "except Exception:\\n",', '    "    pass\\n"']),
        diff("results.json", ['  "threshold": 1e-1,'], removed=['  "threshold": 1e-6,']),
    ):
        result = G.assess(text)
        assert result.allowed and result.cautions == () and result.changed_lines == 0


def test_constructs_the_screen_does_not_claim_to_see_are_not_flagged():
    """E3 (narrow except + continue), E4 (early return {}), E19 (sys.exit(0)):
    semantically defensive, syntactically ordinary. The docstring says so;
    this test pins the honest boundary rather than pretending otherwise."""
    for text in (
        diff("src/calc.py", ["    except ValueError:", "        logging.exception('bad row')",
                             "        continue"]),
        diff("src/calc.py", ["    if not data:", "        return {}"]),
        diff("src/calc.py", ["    except ValueError as e:", "        sys.exit(0)"]),
    ):
        assert G.assess(text).cautions == ()


# ------------------------------------------------- one red, one green each

ADDED_RED_GREEN = {
    "broad_exception": ("except Exception:", "except ValueError:"),
    "suppress_context": ("with contextlib.suppress(OSError):", "with open(p) as f:"),
    "empty_handler": ("except OSError: pass", "except OSError: log()"),
    "relaxed_assertion": ("assert result == 1 or True", "assert result == 1"),
    "disabled_test": ("@pytest.mark.skip", "@pytest.mark.parametrize('x', [1])"),
    "shell_ignore_errors": ("set +e", "set -e"),
    "dead_branch": ("if TYPE_CHECKING:", "if typing_ok:"),
}
MARKER_RED_GREEN = {
    "lint_suppression": ("x = 1  # noqa", "x = 1  # note"),
    "warning_suppression": ("warnings.filterwarnings('ignore')", "warnings.filterwarnings('error')"),
}
REMOVED_RED_GREEN = {
    "removed_check": ("    assert x == 1", "    x = 1"),
    "removed_test": ("def test_alpha():", "def helper():"),
}


@pytest.mark.parametrize("name", sorted(ADDED_RED_GREEN | MARKER_RED_GREEN))
def test_each_added_line_pattern_has_a_red_and_a_green(name):
    """Mutation: swap red and green -> both halves fail."""
    red, green = (ADDED_RED_GREEN | MARKER_RED_GREEN)[name]
    hit = G.assess(diff("src/x.py", [red]))
    assert hit.patterns == (name,) and hit.cautions[0].startswith("src/x.py adds ")
    assert G.assess(diff("src/x.py", [green])).cautions == ()


@pytest.mark.parametrize("name", sorted(REMOVED_RED_GREEN))
def test_each_removed_line_pattern_has_a_red_and_a_green(name):
    """Mutation: stop screening removed lines -> the red half passes."""
    red, green = REMOVED_RED_GREEN[name]
    hit = G.assess(diff("src/x.py", ["y = 2"], removed=[red]))
    assert hit.patterns == (name,) and hit.cautions[0].startswith("src/x.py removes ")
    assert G.assess(diff("src/x.py", ["y = 2"], removed=[green])).cautions == ()


def test_a_moved_assert_is_not_a_removed_check():
    """Re-indenting or moving an assert keeps it. Mutation: compare removed
    lines against nothing -> a moved assert is flagged as deleted."""
    text = diff("tests/test_x.py", ["    if cond:", "        assert x == 1"],
                removed=["    assert x == 1"])
    assert G.assess(text).cautions == ()


def test_two_line_empty_handler_needs_the_except_header_above_it():
    """Mutation: drop the previous-line context -> H12/H24's `pass` redden
    or the two-line handler goes unseen."""
    assert G.assess(diff("src/x.py", ["except OSError:", "    pass"])).patterns == ("empty_handler",)
    assert G.assess(diff("src/x.py", ["except OSError:", "    log()"])).cautions == ()
    assert G.assess(diff("src/x.py", ["if x:", "    pass"])).cautions == ()
    # The header may be a context line of the hunk, not an added one.
    text = ("diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n"
            "@@ -1,2 +1,2 @@\n except OSError:\n-    raise\n+    pass\n")
    assert G.assess(text).patterns == ("empty_handler", "removed_check")


def test_strings_and_comments_are_stripped_before_construct_matching():
    """Mutation: skip strip_code -> the string and the comment redden."""
    assert strip_code('x = "except Exception:"  # except Exception:') == 'x = ""'
    assert strip_code("    # except Exception:") == ""
    assert strip_code('    """except Exception:"""') == ""
    assert strip_code("url = 'http://x/y'  // trailing") == 'url = ""'
    assert G.assess(diff("src/x.py", ['x = "except Exception:"', "# except:"])).cautions == ()
    # but markers live in comments and are matched raw
    assert G.assess(diff("src/x.py", ["x = 1  # type: ignore"])).patterns == ("lint_suppression",)


# ----------------------------------------------------------- file classes

@pytest.mark.parametrize("path,kind", [
    ("a.py", "code"), ("a.pyi", "code"), ("a.ts", "code"), ("a.sh", "code"), ("a.go", "code"),
    ("a.rs", "code"), ("a.R", "code"), ("a.jl", "code"), ("a.sql", "code"), ("Makefile", "code"),
    ("docker/Dockerfile", "code"), ("a.json", "data"), ("a.yml", "data"), ("a.yaml", "data"),
    ("a.toml", "data"), ("a.ini", "data"), ("a.cfg", "data"), ("a.csv", "data"),
    ("a.ipynb", "data"), ("a.md", "document"), ("a.txt", "document"), ("a.tex", "document"),
    ("a.pdf", "document"), ("a.png", "document"), ("README", "document"), ("Makefile.md", "document"),
])
def test_file_classification(path, kind):
    """Mutation: move .json to code -> H15 is budgeted and H5 reddens."""
    assert classify(path) == kind


def test_scope_is_the_audited_directories():
    """Mutation: drop normalise_path from in_scope -> `./experiments`,
    `experiments/./demo` and `experiments//demo` refuse every repair (N11)."""
    for spelling in ("./experiments", "experiments/", "experiments/./demo",
                     "experiments//demo", "experiments/demo/", "./experiments/demo"):
        assert in_scope("experiments/demo/x.py", [spelling]), spelling
        assert in_scope("./experiments/demo/x.py", [spelling]), spelling
    assert normalise_path("./experiments/") == "experiments"
    assert normalise_path("experiments//demo/./x.py") == "experiments/demo/x.py"
    assert normalise_path("./") == "" and normalise_path(".") == ""
    assert in_scope("anything/at/all.py", None)
    assert in_scope("anything/at/all.py", [])
    assert in_scope("experiments/demo/x.py", ["experiments"])
    assert in_scope("experiments/demo/x.py", ["experiments/"])
    assert not in_scope("experimentsX/x.py", ["experiments"])
    assert not in_scope("notes/x.md", ["experiments", "src"])
    assert in_scope("notes/x.md", ["."])


# ------------------------------------------------------------ the budget

def test_budget_is_a_caution_over_code_only():
    """A re-rendered report or regenerated data is legitimately large.

    Mutation: count data/document lines -> the .md/.json cases caution;
    treat the budget as a refusal in caution mode -> the .py case is refused.
    """
    lines = [f"line {i}" for i in range(300)]
    for path in ("report.md", "results.json"):
        r = G.assess(diff(path, lines))
        assert r.allowed and r.cautions == () and r.changed_lines == 0 and r.document_lines == 300
    code = G.assess(diff("src/x.py", lines))
    assert code.allowed and code.changed_lines == 300
    assert code.cautions == ("the code change touches 300 lines, more than the 200-line "
                             "limit for an automatic repair",)
    assert not R.assess(diff("src/x.py", lines)).allowed


def test_budget_counts_removed_code_lines_too():
    """Mutation: count only added lines -> a 250-line deletion is silent."""
    r = G.assess(diff("src/x.py", ["one()"], removed=[f"old_{i}()" for i in range(250)]))
    assert r.changed_lines == 251 and any("touches 251 lines" in c for c in r.cautions)


def test_bad_arguments_are_refused():
    with pytest.raises(ValueError):
        RepairGuard(0)
    with pytest.raises(ValueError):
        RepairGuard(200, mode="loud")


# ------------------------------------------------------- hard refusals

def test_a_file_outside_the_audited_directories_is_refused_by_name():
    """Mutation: drop the scope screen -> allowed."""
    r = G.assess(diff("notes/x.md", ["hello"]), scope_dirs=["experiments", "src"])
    assert not r.allowed and r.unsupported_files == ("notes/x.md",)
    assert r.refusals == (
        "notes/x.md is outside the audited directories (experiments, src). Only files "
        "inside them may change; if the fix needs another file, say so in `notes`.",)
    assert G.assess(diff("notes/x.md", ["hello"])).allowed          # no scope: whole tree


def test_scope_uses_the_staged_list_so_a_capped_diff_cannot_hide_a_file():
    """M12 at the unit level. Mutation: screen only parsed files for scope ->
    the file beyond the cap is invisible."""
    big = diff("docs/A_big.md", ["x" * 600_000]) + diff("src/calc.py", ["except Exception:", "    pass"])
    cut = big[:512 * 1024]
    assert "src/calc.py" not in cut
    r = G.assess(cut, scope_dirs=["docs"], staged_files=["docs/A_big.md", "src/calc.py"],
                 truncated=True)
    assert not r.allowed and r.unsupported_files == ("src/calc.py",)
    inside = G.assess(cut, scope_dirs=["docs", "src"],
                      staged_files=["docs/A_big.md", "src/calc.py"], truncated=True)
    assert inside.allowed and inside.unscreened_files == ("src/calc.py",)
    assert inside.cautions == ("1 staged file(s) were larger than the review can read and "
                               "were not screened: src/calc.py",)
    assert not R.assess(cut, scope_dirs=["docs", "src"],
                        staged_files=["docs/A_big.md", "src/calc.py"], truncated=True).allowed
    # Not truncated: a staged path the diff does not show is not "unscreened".
    assert G.assess(cut, staged_files=["docs/A_big.md", "src/calc.py"]).cautions == ()


def test_a_binary_passes_only_when_the_local_document_export_produced_it():
    """Mutation: drop report.pdf from locally_rendered_files -> refused."""
    text = ("diff --git a/report.pdf b/report.pdf\nindex 1111111..2222222 100644\n"
            "Binary files a/report.pdf and b/report.pdf differ\n")
    ok = G.assess(text, locally_rendered_files={"report.pdf"})
    assert ok.allowed and ok.changed_files == ("report.pdf",)
    bad = G.assess(text)
    assert not bad.allowed and bad.binary_files == ("report.pdf",)
    assert bad.refusals == ("report.pdf is a binary file written directly by the generator, "
                            "which cannot be reviewed line by line",)


def test_empty_diff_is_refused_with_a_reason():
    r = G.assess("")
    assert not r.allowed and r.refusals == ("the revision changed nothing that could be reviewed",)


# --------------------------------------------- real git diff --cached shape

def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout


def test_a_real_staged_multi_file_diff_parses_added_removed_and_binary(tmp_path):
    """The exact bytes build.py hands the screen: git diff --cached --binary.

    Mutation: treat `--- a/x` as a removed line -> counts off by one per
    file; treat `+++ b/x` as added -> the header path is screened.
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
    text = _git("diff", "--cached", "--binary", "--no-ext-diff", cwd=repo)

    files = parse_unified_diff(text)
    assert set(files) == {"src/calc.py", "SUMMARY.md", "fig.png", "with space.md", "new.txt"}
    assert files["src/calc.py"].added == ["    return 2"]
    assert files["src/calc.py"].removed == ["    return 1", "    # keep"]
    assert files["SUMMARY.md"].added == ["three", "four"] and files["SUMMARY.md"].removed == []
    assert files["fig.png"].binary and files["fig.png"].added == []
    assert files["new.txt"].added == ["fresh"]

    staged = _git("diff", "--cached", "--name-only", cwd=repo).split()
    r = G.assess(text, staged_files=staged, locally_rendered_files={"fig.png"})
    assert r.allowed and r.cautions == (), (r.refusals, r.cautions)
    # code: calc.py -2/+1; documents: SUMMARY +2, 'with space.md' -1/+1, new.txt +1
    assert r.changed_lines == 3 and r.document_lines == 5
    assert not G.assess(text, staged_files=staged).allowed          # png written by the model


def test_a_deleted_file_is_still_a_changed_file():
    """Mutation: drop the diff --git header path -> the deletion is invisible."""
    text = ("diff --git a/src/old.py b/src/old.py\ndeleted file mode 100644\n"
            "--- a/src/old.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a()\n-assert b()\n")
    r = G.assess(text, scope_dirs=["docs"])
    assert r.changed_files == ("src/old.py",) and r.unsupported_files == ("src/old.py",)
    assert r.changed_lines == 2 and "removed_check" in r.patterns


# ============================================================ review D2

# ------------------------------------------ truthful sentences (D2 #4, #5)

TRUTHFUL = {
    "N1 except Exception + raise ... from": (
        diff("src/calc.py", ["    except Exception as exc:",
                             "        raise ConvergenceError(str(exc)) from exc"]),
        "src/calc.py adds a catch-all `except` (its handler re-raises)"),
    "N2 except Exception: log; raise": (
        diff("src/calc.py", ["    except Exception:", "        log.exception('fit failed')",
                             "        raise"]),
        "src/calc.py adds a catch-all `except` (its handler re-raises)"),
    "N2b one-line except Exception: raise": (
        diff("src/calc.py", ["    except Exception: raise"]),
        "src/calc.py adds a catch-all `except` (its handler re-raises)"),
    "N4 assert tightened to pytest.approx": (
        diff("tests/test_x.py", ["    assert result == pytest.approx(0.42, rel=1e-6)"],
             removed=["    assert result == 0.42"]),
        "tests/test_x.py changes an `assert` or `raise`"),
    "N5 raise reworded": (
        diff("src/calc.py", ["    raise ConvergenceError(f'not converged after {n} steps')"],
             removed=["    raise RuntimeError('not converged')"]),
        "src/calc.py changes an `assert` or `raise`"),
    "N8 test renamed, still a test": (
        diff("tests/test_x.py", ["def test_convergence_strict():"],
             removed=["def test_convergence():"]),
        "tests/test_x.py renames a test"),
    "E16 except BaseException: return None (no re-raise)": (
        diff("src/calc.py", ["    except BaseException:", "        return None"]),
        "src/calc.py adds a catch-all `except` that swallows every error"),
    "E6 assert deleted, nothing replaced it": (
        diff("tests/test_x.py", ["    x = 1"], removed=["    assert result == 0.42"]),
        "tests/test_x.py removes an `assert` or `raise` without replacing it"),
    "X13 assert turned into if/print": (
        diff("tests/test_x.py", ["    if not result == 0.42:", "        print('mismatch')"],
             removed=["    assert result == 0.42"]),
        "tests/test_x.py removes an `assert` or `raise` without replacing it"),
    "E7 test_x -> _test_x is a removal": (
        diff("tests/test_x.py", ["def _test_convergence():"], removed=["def test_convergence():"]),
        "tests/test_x.py removes a test"),
}


@pytest.mark.parametrize("name", list(TRUTHFUL))
def test_caution_sentences_are_true_as_written(name):
    """Mutation: drop _handler_reraises / the same-hunk keyword check / the
    added-test check -> the strong sentence is said of an honest edit."""
    text, sentence = TRUTHFUL[name]
    result = G.assess(text)
    assert result.allowed and sentence in result.cautions, result.cautions


def test_the_reraise_check_stops_at_the_handler_s_dedent():
    """A `raise` after the handler is not the handler's. Mutation: ignore
    indentation in _handler_reraises -> the strong sentence disappears."""
    text = diff("src/calc.py", ["    except Exception:", "        return None",
                                "    raise RuntimeError('unreachable')"])
    assert "src/calc.py adds a catch-all `except` that swallows every error" in G.assess(text).cautions


@pytest.mark.parametrize("text", [
    diff("src/calc.py", ['    """Run the fit.', "", "    >>> try:", "    ...     run()",
                         "    ... except Exception:", "    ...     pass", '    """']),
    diff("src/calc.py", ['    """Notes.', "    except Exception:", "        pass",
                         "    set +e", '    """']),
    diff("src/calc.py", ["    >>> assert x  # doctest", "    ... except Exception: pass"]),
])
def test_doctest_lines_and_docstring_interiors_are_not_code(text):
    """N7. Mutation: drop `>>>`/`...` from _COMMENT_START or the per-hunk
    docstring state -> a doctest reddens."""
    assert G.assess(text).cautions == ()


# ------------------------------------ every alternative bites (D2 #6, #7)

ALTERNATIVES = [
    ("broad_exception", "except:"), ("broad_exception", "except Exception:"),
    ("broad_exception", "except BaseException as e:"),
    ("broad_exception", "except (ValueError, Exception):"),
    ("broad_exception", "except(Exception):"), ("broad_exception", "} catch (Throwable t) {"),
    ("broad_exception", "} catch (Exception e) {"),
    ("suppress_context", "with contextlib.suppress(OSError):"),
    ("empty_handler", "except OSError: pass"), ("empty_handler", "except OSError: ..."),
    ("empty_handler", "try { run() } catch (e) {}"), ("empty_handler", "catch {}"),
    ("relaxed_assertion", "assert True"), ("relaxed_assertion", "assert 1"),
    ("relaxed_assertion", "assert x == 1 or True"),
    ("disabled_test", "@pytest.mark.skip"), ("disabled_test", "@pytest.mark.skipif(True, reason='x')"),
    ("disabled_test", "@pytest.mark.xfail"), ("disabled_test", "@unittest.skip('x')"),
    ("disabled_test", "pytest.importorskip('nope')"),
    ("disabled_test", "pytestmark = pytest.mark.skip(reason='later')"),
    ("dead_branch", "if TYPE_CHECKING:"), ("dead_branch", "if False:"), ("dead_branch", "if 0:"),
    ("shell_ignore_errors", "set +e"), ("shell_ignore_errors", "python calc.py || true"),
    ("shell_ignore_errors", "python calc.py || exit 0"), ("shell_ignore_errors", "\t-python calc.py"),
    ("lint_suppression", "x = 1  # noqa"), ("lint_suppression", "x = 1  # noqa: E501"),
    ("lint_suppression", "x = 1  # type: ignore"), ("lint_suppression", "x = risky()  # pragma: no cover"),
    ("lint_suppression", "y = 1  # pylint: disable=all"), ("lint_suppression", "z = 2  # pyright: ignore"),
    ("lint_suppression", "z = 2  # mypy: ignore-errors"), ("lint_suppression", "/* eslint-disable */"),
    ("lint_suppression", "// @ts-ignore"), ("lint_suppression", "// @ts-nocheck"),
    ("warning_suppression", "warnings.filterwarnings('ignore')"),
    ("warning_suppression", "warnings.simplefilter(\"ignore\", RuntimeWarning)"),
]


@pytest.mark.parametrize("name,line", ALTERNATIVES, ids=[f"{n}:{l.strip()[:28]}" for n, l in ALTERNATIVES])
def test_every_pattern_alternative_bites(name, line):
    """Mutation: delete any single alternative from its regex -> its row fails
    (review D2 survivors R1, R5-R9)."""
    result = G.assess(diff("src/x.py", [line]))
    assert name in result.patterns, (line, result.patterns, result.cautions)


def test_two_line_js_catch_is_an_empty_handler():
    """R1. Mutation: drop `}` from _PASS_ONLY -> unseen."""
    result = G.assess(diff("src/app.js", ["try { run() } catch (e) {", "}"]))
    assert "empty_handler" in result.patterns
    assert G.assess(diff("src/app.js", ["try { run() } catch (e) {", "  report(e)", "}"])).cautions == ()


def test_pyx_is_code_and_makefile_recipe_prefix_is_a_caution():
    """X10, X15. Mutation: drop .pyx from CODE_SUFFIXES / `^\t-` from the
    shell pattern -> silent."""
    assert classify("fast.pyx") == "code" and classify("fast.pxd") == "code"
    assert "broad_exception" in G.assess(diff("src/fast.pyx", ["except Exception:", "    pass"])).patterns
    assert "shell_ignore_errors" in G.assess(diff("Makefile", ["\t-python calc.py"])).patterns
    assert G.assess(diff("Makefile", ["\tpython calc.py"])).cautions == ()


def test_wrapping_the_reinstated_line_in_a_dead_branch_is_a_caution():
    """X1. Mutation: drop dead_branch -> the moved-line equality hides it."""
    text = diff("src/calc.py", ["if TYPE_CHECKING:", "    check_convergence(result)"],
                removed=["check_convergence(result)"])
    assert "dead_branch" in G.assess(text).patterns


# ---------------------------------------- path spellings (D2 #1, #2, #3)

def test_git_quoted_paths_unquote_to_their_utf8_text():
    """R10. Mutation: return the raw token -> the refusal names
    `"\\346\\212\\245..."` and the scope screen refuses a Chinese name."""
    assert unquote_path('"\\346\\212\\245\\345\\221\\212.md"') == "报告.md"
    assert unquote_path('"say \\"hi\\".md"') == 'say "hi".md'
    assert unquote_path("plain.md") == "plain.md"


def test_a_real_staged_diff_with_cjk_space_and_quote_names(tmp_path):
    """The exact bytes build.py hands the screen with core.quotepath=false and
    the NUL-separated staged list. Mutation: drop the equal-halves header
    split -> `fig 1.png` is never parsed and the model-written binary
    passes; drop quotepath=false / -z -> `报告.md` is refused as out of
    scope."""
    repo = tmp_path / "repo"
    (repo / "experiments").mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "t@example.invalid", cwd=repo)
    _git("config", "user.name", "T", cwd=repo)
    (repo / "a.md").write_text("x\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "base", cwd=repo)
    (repo / "experiments/报告.md").write_text("报告正文\n")
    (repo / "experiments/fig 1.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00new")
    (repo / 'experiments/say "hi".py').write_text("except Exception:\n    pass\n")
    _git("add", "-A", cwd=repo)
    text = _git("-c", "core.quotepath=false", "diff", "--cached", "--binary", "--no-ext-diff", cwd=repo)
    raw = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=str(repo),
                         capture_output=True, check=True).stdout
    staged = [p.decode("utf-8") for p in raw.split(b"\0") if p]
    assert set(staged) == {"experiments/报告.md", "experiments/fig 1.png", 'experiments/say "hi".py'}

    files = parse_unified_diff(text)
    assert set(files) == set(staged)
    assert files["experiments/fig 1.png"].binary
    assert files["experiments/报告.md"].added == ["报告正文"]

    r = G.assess(text, scope_dirs=["./experiments"], staged_files=staged)
    assert r.unsupported_files == ()                       # all three are in scope
    assert r.binary_files == ("experiments/fig 1.png",)    # the space did not hide it
    assert r.refusals == ("experiments/fig 1.png is a binary file written directly by the "
                          "generator, which cannot be reviewed line by line",)
    assert 'experiments/say "hi".py adds a catch-all `except` that swallows every error' in r.cautions
    ok = G.assess(text, scope_dirs=["experiments"], staged_files=staged,
                  locally_rendered_files={"experiments/fig 1.png"})
    assert ok.allowed
    # And the quoted (quotepath=true) spelling of the same diff still parses.
    quoted = _git("-c", "core.quotepath=true", "diff", "--cached", "--binary", "--no-ext-diff", cwd=repo)
    assert set(parse_unified_diff(quoted)) == set(staged)


# ==================================================== closure audit D #6

def test_numstat_names_binaries_independently_of_the_diff_text(tmp_path):
    """`git diff --cached --numstat -z` is the binary screen's source.
    Mutation: treat `-\\t-` as text -> no binary is reported."""
    from crossaudit.repair_guard import parse_numstat

    repo = tmp_path / "repo"
    (repo / "experiments").mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "t@example.invalid", cwd=repo)
    _git("config", "user.name", "T", cwd=repo)
    (repo / "a.md").write_text("x\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "base", cwd=repo)
    (repo / "experiments/图 2.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00new")
    (repo / "experiments/fig 1.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00new")
    (repo / "experiments/报告.md").write_text("one\ntwo\n")
    _git("add", "-A", cwd=repo)
    raw = subprocess.run(["git", "diff", "--cached", "--numstat", "-z"], cwd=str(repo),
                         capture_output=True, check=True).stdout
    stat = parse_numstat(raw)
    assert stat["experiments/图 2.png"] == (None, None, True)
    assert stat["experiments/fig 1.png"] == (None, None, True)
    assert stat["experiments/报告.md"] == (2, 0, False)
    # The rename form (added\tremoved\t\0old\0new\0) keeps the post-image path.
    assert parse_numstat(b"-\t-\t\0old.png\0new dir/new.png\0") == {
        "new dir/new.png": (None, None, True)}


def test_a_reported_binary_is_refused_even_when_the_diff_was_cut_before_it():
    """Closure D #6. Mutation: derive untrusted_binary from the diff text only
    -> a binary past the cap is committed with a caution."""
    big = diff("docs/A_big.md", ["x" * 600_000]) + (
        "diff --git a/docs/fig 1.png b/docs/fig 1.png\nindex 1..2 100644\n"
        "Binary files a/docs/fig 1.png and b/docs/fig 1.png differ\n")
    cut = big[:512 * 1024]
    assert "fig 1.png" not in cut
    staged = ["docs/A_big.md", "docs/fig 1.png"]
    r = G.assess(cut, scope_dirs=["docs"], staged_files=staged,
                 binary_files=["docs/fig 1.png"], truncated=True)
    assert not r.allowed and r.binary_files == ("docs/fig 1.png",)
    assert r.unscreened_files == ()                  # it was screened: refused
    ok = G.assess(cut, scope_dirs=["docs"], staged_files=staged,
                  binary_files=["docs/fig 1.png"],
                  locally_rendered_files={"docs/fig 1.png"}, truncated=True)
    assert ok.allowed and ok.binary_files == ()
