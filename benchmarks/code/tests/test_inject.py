"""Study 22's population filters, exercised where they decide membership.

Every filter in `inject.filter_one` is mechanical, so every one of them is testable without
a model call. These tests pin the three that can silently admit the wrong instance — F1 (the
quote really is in the specification), F3 (the defect really fails the hidden suite) and F4
(the diff really is small) — plus the JSON parsing the injector's reply goes through.

D10 mutations: make F1 accept a paraphrase (drop `norm_ws`), make F4 count the unified diff's
`+++` header as a changed line, or let `parse_injection` accept an object without `quote` —
each turns one of these red.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

import inject  # noqa: E402
from corpus import load_problems  # noqa: E402


def test_parse_injection_takes_a_fence_prose_or_a_bare_object():
    body = '{"code": "def f():\\n    return 1", "quote": "a b c d e f", "input_class": "x"}'
    assert inject.parse_injection(body)["quote"] == "a b c d e f"
    assert inject.parse_injection("```json\n" + body + "\n```")["code"].startswith("def f")
    assert inject.parse_injection("Here you go:\n" + body + "\nHope that helps.")["input_class"] == "x"


def test_parse_injection_rejects_an_object_missing_a_required_key():
    assert inject.parse_injection('{"code": "x", "quote": "y"}') is None
    assert inject.parse_injection("no json here at all") is None


def test_changed_lines_ignores_the_diff_header():
    same = "def f():\n    return 1\n"
    assert inject.changed_lines(same, same) == 0
    one = "def f():\n    return 2\n"
    assert inject.changed_lines(same, one) == 2          # one line removed, one added


def test_f1_is_a_literal_substring_after_whitespace_only():
    spec = "Write a function to find the\nmaximum value in a given heterogeneous list."
    assert inject.norm_ws("maximum value in a given heterogeneous list") in inject.norm_ws(spec)
    assert inject.norm_ws("maximum   value in\na given heterogeneous list") in inject.norm_ws(spec)
    assert inject.norm_ws("largest value in a heterogeneous list") not in inject.norm_ws(spec)


def test_imports_of_sees_both_import_forms():
    assert inject.imports_of("import math\nfrom collections import Counter\n") == {"math", "collections"}
    assert inject.imports_of("def f(:\n") == {"<unparseable>"}


def test_branched_is_true_only_when_the_changed_line_sits_under_a_conditional():
    base = "def f(n):\n    return n\n"
    branched = "def f(n):\n    if n < 0:\n        return 0\n    return n\n"
    assert inject.changed_line_is_branched(base, branched) is True
    straight = "def f(n):\n    return n + 0\n"
    assert inject.changed_line_is_branched(base, straight) is False


@pytest.fixture(scope="module")
def mbpp_problem():
    for problem in load_problems():
        if problem.problem_id == "Mbpp/244":       # next perfect square; a short numeric one
            return problem
    pytest.skip("corpus not present")


def test_filters_accept_a_real_defect_and_reject_a_visible_breaker(mbpp_problem):
    """The two filters that decide the population, on a real problem and a real suite."""
    problem = mbpp_problem
    base = problem.canonical_solution
    quote = " ".join(problem.spec.split()[:8])
    # A defect that survives the visible tests and fails the hidden ones: negative inputs.
    hidden_only = base + "\n\n_orig = next_Perfect_Square\ndef next_Perfect_Square(n):\n" \
                         "    return 0 if n < 0 else _orig(n)\n"
    row = inject.filter_one(problem, base, {"code": hidden_only, "quote": quote,
                                            "input_class": "negative n", "witness_input": "[-5]"}, 12.0)
    assert row["F1_quote_in_spec"] is True
    assert row["F2_visible_passes"] is True
    # Whether this particular edit fails the hidden suite is the benchmark's business; what
    # this test pins is that F3 reports the suite's own verdict, not a guess.
    assert row["F3_hidden_fails"] == (not row["hidden"]["passed"] and not row["hidden"]["timed_out"])

    breaks_visible = "def next_Perfect_Square(n):\n    return -1\n"
    row2 = inject.filter_one(problem, base, {"code": breaks_visible, "quote": quote,
                                             "input_class": "all", "witness_input": "[1]"}, 12.0)
    assert row2["F2_visible_passes"] is False
    assert row2["accepted_by_filters"] is False


def test_a_quote_that_is_not_in_the_specification_is_rejected(mbpp_problem):
    problem = mbpp_problem
    row = inject.filter_one(problem, problem.canonical_solution,
                            {"code": problem.canonical_solution + "\n# edit\n",
                             "quote": "this sentence appears nowhere in the specification",
                             "input_class": "x", "witness_input": "[1]"}, 12.0)
    assert row["F1_quote_in_spec"] is False
    assert row["accepted_by_filters"] is False


def test_a_quote_shorter_than_six_words_is_rejected(mbpp_problem):
    problem = mbpp_problem
    short = " ".join(problem.spec.split()[:4])
    row = inject.filter_one(problem, problem.canonical_solution,
                            {"code": problem.canonical_solution, "quote": short,
                             "input_class": "x", "witness_input": "[1]"}, 12.0)
    assert row["F1_quote_in_spec"] is False


def test_the_ladder_and_the_models_are_the_preregistered_ones():
    assert inject.LADDER == [("cross", d) for d in range(1, 9)]
    assert inject.INJECTOR_SPEC == "anthropic:claude-haiku-4-5-20251001"
    assert inject.GATE_SPECS == ("anthropic:claude-sonnet-4-6", "openai:gpt-5.6-luna")
    assert inject.MIN_QUOTE_WORDS == 6 and inject.MAX_CHANGED_LINES == 4
