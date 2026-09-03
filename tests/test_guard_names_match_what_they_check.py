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

#: A name that promises a person saw or heard something. Matched as WHOLE
#: TOKENS, because that is the difference between a claim and a noun: "renders"
#: promises, "render target" names a container; "announces" promises, "the
#: announcer" is a DOM node. The first pattern matched substrings, which forced
#: an exemption to stop it accusing honest names — and the exemption was the
#: hole (the reviewer worded past it with `test_page_markup_renders_x`).
CLAIM_TOKENS = frozenset({
    "render", "renders", "rendered", "rerenders", "announce", "announces",
    "announced", "announcing", "speak", "speaks", "spoken", "neutralise",
    "neutralises", "neutralize", "neutralizes", "display", "displays",
    "displayed", "show", "shows", "shown", "hear", "hears", "heard",
})
#: ...except when the subject is a guard rather than a page. "shown to fail" is
#: a counterfactual about a test, and those are exactly what we want more of.
ABOUT_A_GUARD = re.compile(r"shown_to_fail|guard_is_shown|_reddens|_is_shown_to_", re.I)

#: THERE IS NO NAMING EXEMPTION. A prefix cannot buy a name out of this check:
#: `test_page_markup_renders_x` is flagged exactly like `test_page_renders_x`,
#: because the claim is in the verb and the prefix does not remove it. The only
#: escape is the explicit registry below, which costs a written reason and is
#: checked to still name a live test.


def _claims_an_outcome(name: str) -> bool:
    return bool(set(name.lower().split("_")) & CLAIM_TOKENS)


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


def _product_symbols(tree: ast.AST) -> set[str]:
    """Names this scope pulled out of the product."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("crossaudit"):
            out |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {(a.asname or a.name).split(".")[0]
                    for a in node.names if a.name.startswith("crossaudit")}
    return out


def _root_of(func: ast.AST) -> str | None:
    while isinstance(func, ast.Attribute):
        func = func.value
    return func.id if isinstance(func, ast.Name) else None


def _executes_something(fn: ast.AST, product: set[str], helpers: dict) -> bool:
    """Whether this body CALLS product code, directly or via a local helper.

    Keyed on calls, never on the token ``PAGE``. The first version required
    ``PAGE`` to appear before it would consider a body source-only, which the
    reviewer caught: when the page-script slicers are consolidated that token
    goes, every body stops looking source-only, and this guard silently stops
    guarding — green the whole way. A guard whose trigger a scheduled refactor
    deletes is a timer, not a check.

    Reading a product CONSTANT is not executing it: ``assert "x" in PAGE`` is a
    Name load, and that is precisely the shape this guard exists to flag.
    """
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        root = _root_of(node.func)
        if root is None:
            continue
        # `run_node` is the shared harness that runs an assembled program under
        # node; a body that calls it is executing the shipped script, exactly as
        # a direct `subprocess.run(["node", ...])` was. `eval_page` is the same
        # thing one layer up (tests/harness/render_decision.py): it slices the
        # named functions OUT OF the shipped page and runs them under node.
        # `render_page` is stronger still — it loads the WHOLE shipped script
        # and calls the real `renderConversation`, which is exactly what a
        # slice-and-stub harness could not see. All three are named because
        # they RUN something; a helper whose name merely sounds like rendering
        # buys nothing here.
        if root in product or root in {"subprocess", "urllib", "requests",
                                       "run_node", "eval_page", "render_page"}:
            return True
        if helpers.get(root):          # a module-local helper that does
            return True
    return False


def _offenders(where: Path | None = None) -> list[str]:
    found = []
    for path in sorted((where or TESTS).glob("test_*.py")):
        src = path.read_text(encoding="utf-8")
        try:
            module = ast.parse(src)
        except SyntaxError:
            continue
        product = _product_symbols(module)
        # A test that calls a local helper which calls the product is
        # exercising the product, however it is named — and so is one that
        # calls a helper that calls a helper. One level was a floor, and it
        # accused an honest render test whose cached accessor sat two calls
        # from the harness. Resolved to a fixed point instead.
        helpers = {}
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                helpers[node.name] = _executes_something(node, product, {})
        for _ in range(len(helpers)):
            grew = False
            for node in module.body:
                if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and not helpers[node.name]
                        and _executes_something(node, product, helpers)):
                    helpers[node.name] = True
                    grew = True
            if not grew:
                break
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if not _claims_an_outcome(node.name) or ABOUT_A_GUARD.search(node.name):
                continue
            key = f"{path.name}::{node.name}"
            if key in SOURCE_CLAIMS_BY_DESIGN:
                continue
            if not _executes_something(node, product | _product_symbols(node), helpers):
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
        "from crossaudit.console import overview\n"
        "from crossaudit.console.page import PAGE\n\n\n"
        "def test_page_renders_the_thing_for_real():\n"
        "    assert overview.read_report_texts is not None\n"
        "    assert overview.ReportSource(path=None, text='', commit='',\n"
        "                                 on_disk_differs=False).note\n"
        "    assert 'thing' in PAGE\n",
        encoding="utf-8")
    assert _offenders(tmp_path) == ["test_planted.py::test_page_renders_the_thing"]


def test_the_prefix_cannot_buy_a_name_out_of_the_check(tmp_path):
    """R1. The first version exempted anything named ``test_page_markup_*``, and
    the reviewer worded past it: the prefix declared "markup" while the verb
    still promised a rendering. There is no naming exemption now — the claim is
    in the verb and a prefix does not remove it.
    """
    (tmp_path / "test_bypass.py").write_text(
        "from crossaudit.console.page import PAGE\n\n\n"
        "def test_page_markup_renders_the_thing():\n"
        "    assert 'thing' in PAGE\n",
        encoding="utf-8")
    assert _offenders(tmp_path) == ["test_bypass.py::test_page_markup_renders_the_thing"], (
        "a name can still buy its way out with a prefix")


def test_the_check_does_not_depend_on_the_token_PAGE(tmp_path):
    """R2. The first version required ``PAGE`` to appear before it would treat a
    body as source-only. The page-script slicers are scheduled for
    consolidation; when that lands the token goes, every body stops looking
    source-only, and this guard would have stopped guarding while staying green.
    A guard whose trigger a planned refactor deletes is a timer.
    """
    (tmp_path / "test_renamed_accessor.py").write_text(
        "from crossaudit.console.page import PAGE as CONSOLE_HTML\n\n\n"
        "def test_the_console_renders_the_thing():\n"
        "    assert 'thing' in CONSOLE_HTML\n",
        encoding="utf-8")
    assert _offenders(tmp_path) == [
        "test_renamed_accessor.py::test_the_console_renders_the_thing"], (
        "the check follows the token PAGE rather than whether product code runs")
