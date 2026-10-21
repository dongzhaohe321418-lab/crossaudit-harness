"""A comma is thousands grouping or it is not a number (D169, F4).

`normalise_number` used to strip every comma before matching, so a
transcribed `1,5` normalised to the key of `15` and `1,0,0` to that of `100`,
and `check_number_source` accepted `{"v": "1,5", "u": "mg"}` against
"Add 15 mg of salt." -- the wrong-number-accepted direction the module says
it prevents. Now only valid grouping is stripped; any other comma makes the
token not a number, which every caller turns into CA-NUM-001.

Mutation (D10), run by hand: restoring `.replace(",", "")` ahead of the
match turns every None row of the sweep red and the end-to-end test red
(it passes again with no finding).
"""
from __future__ import annotations

import itertools

import pytest

from crossaudit.dcl.quantities import is_number_shape, normalise_number

from .test_number_source_check import cite, draft, findings, row

NOT_NUMBERS = ["1,5", "1,0,0", "12,34", ",5", "1,", "1,000,", "1,000,00",
               "1,0000", "1234,567", "1,000.5,0", "1.000,5", "0,5", "-1,5",
               "−1,5", "1,5e3", "1,,000", " ,", "1 ,000", "1, 000"]

GROUPED = [("1,000", "1000"), ("12,345.67", "12345.67"), ("1,234,567", "1234567"),
           ("-1,000", "-1000"), ("−1,000", "-1000"), ("+1,000", "1000"),
           ("999,999", "999999"), ("1,000.0", "1000.0"), ("1,000e3", "1000e3"),
           ("10,000,000.25E-2", "10000000.25E-2")]


@pytest.mark.parametrize("token", NOT_NUMBERS)
def test_a_comma_that_is_not_grouping_is_not_a_number(token):
    assert normalise_number(token) is None
    assert is_number_shape(token) is False


@pytest.mark.parametrize("grouped,plain", GROUPED)
def test_valid_thousands_grouping_keys_like_its_comma_free_form(grouped, plain):
    assert normalise_number(plain) is not None
    assert normalise_number(grouped) == normalise_number(plain)


def _grouping_is_valid(token: str) -> bool:
    body = token.lstrip("+-")
    whole = body.split(".")[0]
    groups = whole.split(",")
    return (len(groups) >= 2 and 1 <= len(groups[0]) <= 3
            and all(len(g) == 3 for g in groups[1:]))


def test_contiguous_sweep_of_comma_positions():
    """Every placement of one or two commas in digit strings of length 2..7,
    with and without a fraction: the token is a number exactly when the commas
    group thousands, and then it keys like the comma-free form."""
    checked = 0
    for length in range(2, 8):
        digits = "1234567"[:length]
        for count in (1, 2):
            for cuts in itertools.combinations(range(1, length), count):
                parts, last = [], 0
                for cut in cuts:
                    parts.append(digits[last:cut])
                    last = cut
                parts.append(digits[last:])
                token = ",".join(parts)
                for suffix in ("", ".5"):
                    candidate = token + suffix
                    key = normalise_number(candidate)
                    if _grouping_is_valid(candidate):
                        assert key == normalise_number(digits + suffix), candidate
                    else:
                        assert key is None, candidate
                    checked += 1
    assert checked > 100


def test_the_reported_case_now_blocks_with_ca_num_001():
    span = "Add 15 mg of salt."
    files = {"work/synthesis/RECIPE.md": (span + "\n").encode(),
             "work/explanation.md": draft([row(value="1,5", unit="mg", src=cite(span))],
                                          prose="Add 1,5 mg of salt.")}
    assert [f.rule for f in findings(files)] == ["CA-NUM-001"]


@pytest.mark.parametrize("value,expected", [
    ("15", []),                    # the honest transcription passes
    ("1,5", ["CA-NUM-001"]),       # a decimal comma is not a number
    ("1,0,0", ["CA-NUM-001"]),
])
def test_the_twin_rows_against_one_span(value, expected):
    span = "Add 15 mg of salt."
    files = {"work/synthesis/RECIPE.md": (span + "\n").encode(),
             "work/explanation.md": draft([row(value=value, unit="mg", src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected


def test_a_grouped_thousand_in_the_source_still_matches():
    span = "Spin at 1,000 rpm."
    for value in ("1000", "1,000"):
        files = {"work/synthesis/RECIPE.md": (span + "\n").encode(),
                 "work/explanation.md": draft([row(value=value, unit="rpm",
                                                   src=cite(span))])}
        assert [f.rule for f in findings(files)] == [], value
