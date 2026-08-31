"""A test name is part of its contract, and this checks the contract.

WHAT THIS CATCHES. A test whose NAME claims a rendered outcome — "renders",
"announces", "speaks", "neutralises" — while its BODY only reads page source.
That combination is worse than a missing test: the name is what people read, so
it is ticked off as coverage of a property nobody measured. Thirteen such guards
were renamed under D106 after being proved unable to fail: serving an empty
document left every one of them green.

WHAT THIS DOES NOT CATCH, AND IT IS THE FAILURE THAT ACTUALLY HAPPENED.
**Coverage being deleted out from under us.** This guard sees names; it cannot
see a behavioural test that no longer exists. In one consolidation tonight 52
test cells and a distinctness assertion were removed under a fully green suite,
and nothing here would have said a word — nothing was misnamed, the coverage was
simply gone. Catching that needs a stored before-number, which is the campaign
half and is a project, not this. **Do not mistake this guard for that one.**

Nor does it prove that the tests it leaves alone are any good: passing here means
a name is honest, never that a property is tested.

DERIVED, NOT LISTED. The candidate set comes from walking `tests/` — a new
`test_page_renders_x` is in scope the moment it is written, with no list to
update. A hand-written list of guards to check is the enumeration tautology D64
rejected: it agrees with itself and says nothing about the tree.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: A name that promises a person saw or heard something.
CLAIMS_AN_OUTCOME = re.compile(
    r"renders?|announc|speaks|neutralis|displays\b|is_displayed|hears", re.I)
#: ...except when the subject is a guard rather than a page. "shown to fail" is
#: a counterfactual about a test, and those are exactly what we want more of.
ABOUT_A_GUARD = re.compile(r"shown_to_fail|guard_is_shown|_reddens|_is_shown_to_", re.I)
#: ...and except when the name has ALREADY declared itself a markup check. This
#: prefix is the whole convention: it tells a reader, before they open the body,
#: that a string in a file is what is asserted. A test that declares it is
#: checking markup and then checks markup is not lying, whatever nouns follow —
#: "the announcer" and "every render target" are DOM nodes, not promises. The
#: prefix is a claim in itself, so making it the exemption keeps the convention
#: load-bearing instead of leaving the scanner to guess verbs from nouns.
DECLARED_MARKUP_CHECK = "test_page_markup_"

#: Names that read as an outcome but state a claim ABOUT THE SOURCE, which a
#: source assertion is the right instrument for. Each says why, and each is
#: checked below to still exist — a waiver for a test nobody runs is the
#: pre-approved absence the doctor-parity list was fixed for.
SOURCE_CLAIMS_BY_DESIGN = {
    "test_preview.py::test_new_preview_strings_have_a_chinese_display_layer":
        "‘has a display layer’ is a claim about the catalogue: the zh entry "
        "exists. It does not claim the string reached a screen.",
    "test_thread_ui.py::test_new_strings_have_a_chinese_display_layer":
        "same catalogue claim as the preview one above.",
    "test_live_regions.py::test_the_announcer_is_a_stable_node_outside_every_render_target":
        "‘render target’ is a noun here, not a promise: the claim is that the "
        "announcer node lives OUTSIDE every container that gets replaced, which "
        "is structural. It is also demonstrably alive — stripping role/aria-live "
        "from the node reddens it (D106 mutation M4).",
    "test_live_region_locale_timing.py::"
    "test_the_rule_is_one_function_and_the_announcer_uses_it":
        "states a STRUCTURAL rule — one definition, and the announcer refers to "
        "it — which is a property of the source and is checked in the source.",
}


def _crossaudit_symbols(tree: ast.AST) -> set[str]:
    """Names this module pulled out of the product, PAGE excluded."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("crossaudit"):
            out |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {(a.asname or a.name).split(".")[0]
                    for a in node.names if a.name.startswith("crossaudit")}
    return out - {"PAGE"}


def _reads_only_source(fn: ast.AST, module: ast.AST, src: str) -> bool:
    """True when the body reads page/source text and calls no product code.

    Deciding this by regex accused `test_replay_role_renders_a_sample_descriptor`
    — which really does call `projects.materialize_demo` — so the check is on
    the imported symbols the body actually references, not on words.
    """
    body = ast.get_source_segment(src, fn) or ""
    if not ("PAGE" in body or "read_text()" in body or "getsource" in body):
        return False
    product = _crossaudit_symbols(module) | _crossaudit_symbols(fn)
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id in product:
            return False
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in product:
            return False
    return True


def _offenders(where: Path | None = None) -> list[str]:
    found = []
    for path in sorted((where or TESTS).glob("test_*.py")):
        src = path.read_text(encoding="utf-8")
        try:
            module = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if node.name.startswith(DECLARED_MARKUP_CHECK):
                continue
            if not CLAIMS_AN_OUTCOME.search(node.name) or ABOUT_A_GUARD.search(node.name):
                continue
            key = f"{path.name}::{node.name}"
            if key in SOURCE_CLAIMS_BY_DESIGN:
                continue
            if _reads_only_source(node, module, src):
                found.append(key)
    return found


def test_no_test_name_claims_an_outcome_its_body_does_not_check():
    offenders = _offenders()
    assert offenders == [], (
        "these names promise a person saw or heard something, and their bodies "
        f"only read page source: {offenders}. Rename them to what they check "
        "(\"page markup contains/declares X\"), or give them a body that "
        "exercises the behaviour. See D106.")


def test_every_by_design_waiver_names_a_test_that_exists():
    """A waiver for a test nobody runs is pre-approved absence."""
    live = set()
    for path in TESTS.glob("test_*.py"):
        try:
            module = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                live.add(f"{path.name}::{node.name}")
    stale = sorted(set(SOURCE_CLAIMS_BY_DESIGN) - live)
    assert stale == [], f"waivers naming tests that no longer exist: {stale}"


def test_the_guard_is_shown_to_fail(tmp_path):
    """D64: the deliverable is the guard PLUS the observation of it failing.

    A file carrying the exact defect is planted in a scratch tests/ directory and
    the real scanner is pointed at it. If planting one does not produce an
    offender, this guard is not the mechanism whatever it is named.
    """
    planted = tmp_path / "test_planted.py"
    planted.write_text(
        "from crossaudit.console.page import PAGE\n\n\n"
        "def test_page_renders_the_thing():\n"
        "    assert 'thing' in PAGE\n",
        encoding="utf-8")
    assert _offenders(tmp_path) == ["test_planted.py::test_page_renders_the_thing"]

    # ...and a body that calls the product is NOT an offender, however it is
    # named. This half is what stopped the scanner accusing test_local_demo.
    honest = tmp_path / "test_honest.py"
    honest.write_text(
        "from crossaudit.console import projects\n"
        "from crossaudit.console.page import PAGE\n\n\n"
        "def test_page_renders_the_thing_for_real():\n"
        "    assert projects.DEMO_DIRNAME\n"
        "    assert 'thing' in PAGE\n",
        encoding="utf-8")
    assert _offenders(tmp_path) == ["test_planted.py::test_page_renders_the_thing"]
