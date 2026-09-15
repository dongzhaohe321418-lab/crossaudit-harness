"""Study 23's substrate: the seeded visible/hidden split, and what the auditor is shown.

The split is the only place this study invents something the benchmark did not ship, so it is
the place a mistake would be invisible. These tests pin: that hidden contains visible, that the
split is a deterministic function of the task id alone, that the visible text the auditor reads
is exactly the selected methods, and that the frame record round-trips to the corpus.

D10 mutations: seed the split on the loop index instead of the task id, let `visible_methods`
return three names, or make `visible_tests_text` emit the whole class — each turns one red.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "substrate2"))

import corpus2  # noqa: E402

FRAME = HERE / "records" / "substrate2" / "frame.json"


@pytest.fixture(scope="module")
def frame():
    if not FRAME.exists():
        pytest.skip("frame not frozen here")
    return json.loads(FRAME.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tasks():
    if not FRAME.exists() or not corpus2.DATA.exists():
        pytest.skip("corpus or frame not present")
    return corpus2.load_frame(FRAME)


def test_the_split_is_a_function_of_the_task_id_alone():
    methods = [f"T.test_{i}" for i in range(8)]
    once = corpus2.visible_methods("BigCodeBench/7", methods)
    again = corpus2.visible_methods("BigCodeBench/7", list(reversed(methods)))
    assert once == again == sorted(once)
    assert corpus2.visible_methods("BigCodeBench/8", methods) != once or len(methods) <= 2


def test_the_visible_suite_has_exactly_the_registered_size():
    methods = [f"T.test_{i}" for i in range(6)]
    assert len(corpus2.visible_methods("BigCodeBench/1", methods)) == corpus2.N_VISIBLE == 2


def test_hidden_contains_visible_for_every_task_in_the_frame(tasks):
    for task in tasks:
        assert set(task._visible) <= set(task._methods)
        assert len(task._visible) == corpus2.N_VISIBLE
        assert len(task._methods) >= corpus2.MIN_METHODS


def test_the_two_programs_select_the_registered_methods(tasks):
    task = tasks[0]
    visible = task.visible_program("PLACEHOLDER")
    hidden, instrumented = task.hidden_program("PLACEHOLDER")
    assert instrumented is False
    for method in task._visible:
        assert repr(method) in visible
    for method in task._methods:
        assert repr(method) in hidden
    for method in set(task._methods) - set(task._visible):
        assert repr(method) not in visible


def test_the_visible_text_is_exactly_the_selected_methods_SUPERSEDED():
    """Withdrawn by Amendment 7, and kept named so the failure mode stays on the record.

    This test used to assert the visible text contained exactly the selected methods.
    It passed throughout, and it hid the defect it was meant to guard, because it made
    the text parseable ITSELF:

        ast.parse("class T:\n" + "\n".join("    " + line for line in text.splitlines()))

    It manufactured the class header that the real consumers -- the auditor prompt and
    the generator prompt -- never received. What shipped to the models began at an
    indented `def` and did not parse on any of the 300 tasks. A test that accommodates
    the bug cannot catch it. Replaced by `test_what_the_auditor_is_shown_is_valid_python`,
    which parses the text as the model receives it, and by the split test below it.
    """


def test_the_frame_record_matches_the_corpus(frame, tasks):
    assert frame["n_frame"] == len(frame["frame"]) == len(tasks)
    assert frame["split_rule"]["seed"] == corpus2.SPLIT_SEED
    assert frame["split_rule"]["n_visible"] == corpus2.N_VISIBLE
    by_id = {t.problem_id: t for t in tasks}
    for entry in frame["frame"]:
        task = by_id[entry["task_id"]]
        assert list(task._visible) == entry["visible_methods"]
        assert len(task._methods) == entry["n_test_methods"]


def test_this_substrate_is_harder_than_substrate_1_by_the_two_recorded_measures(frame):
    """The reason for the study: substrate 1's medians are 41 spec words and 6 solution lines."""
    import statistics
    words = statistics.median(e["spec_words"] for e in frame["frame"])
    lines = statistics.median(e["canonical_lines"] for e in frame["frame"])
    assert words > 2 * 41, words
    assert lines > 4 * 6, lines


def test_what_the_auditor_is_shown_is_valid_python(tasks):
    """Amendment 7's guard. The text the auditor and the generator are shown must PARSE.

    This test did not exist, and its absence is why the defect below survived to the
    first cross-vendor review. `visible_tests_text` sliced the selected methods out of
    their class and returned them verbatim, so every file began at an indented `def`:
    300 of 300 tasks raised IndentationError, while scoring executed the intact class.
    The auditor was shown invalid Python on every task of this substrate, which can
    raise recall and false positives together.

    Mutation: drop the class header from `visible_tests_text` and this goes red on the
    first task rather than on none.
    """
    import ast
    for task in tasks:
        text = task.visible_tests_text()
        ast.parse(text)          # raises for the caller to see, with the task in the id


def test_the_visible_suite_shows_every_visible_method_and_no_hidden_one(tasks):
    """The other half: parseable is not enough, it must be the registered split.

    Every method in `_visible` appears; no test method of the hidden suite that is not
    also visible appears. Non-test members (setUp, tearDown, helpers) may appear, and
    must, because 142 of the 301 classes define them and the selected methods call them.
    """
    import ast
    for task in tasks:
        tree = ast.parse(task.visible_tests_text())
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        visible = {m.split(".", 1)[1] for m in task._visible}
        hidden = {m.split(".", 1)[1] for m in task._methods}
        assert visible <= names, (task.problem_id, sorted(visible - names))
        assert not (names & hidden) - visible, (task.problem_id, sorted((names & hidden) - visible))
