"""The AI4S declaration pack (`dcl/ai4s.py`, `benchmarks/ai4s/DESIGN.md` §4).

Every test runs the real check through `run_checks` over a hand-built
`path -> bytes` increment and asserts the findings that come back — never a
source string. Each docstring names the MUTATION of `ai4s.py` that turns it red
(D10). Where a check has a threshold, the threshold is swept on both sides
rather than sampled at one point (AGENTS.md §3.5): a fix that merely moved a
boundary looks right at any single sample.
"""
from __future__ import annotations

import json
import math
import re

import pytest

from crossaudit.dcl import ai4s
from crossaudit.dcl.framework import ADVISORY, BLOCKER, available, contracts, run_checks
from crossaudit.dcl.profiles import PROFILES, resolve

EXP = "experiments/2026-10-21-demo"
NEW_CHECKS = ["numeric_validity", "range_rules", "derivations", "split_integrity",
              "claims", "repro_declared", "precision"]


# ----------------------------------------------------------------- helpers
def q(name, value, unit="1", **extra):
    return {"name": name, "value": value, "unit": unit,
            "source": "data/d.csv@v1", **extra}


def inc(results: dict | str, files: dict | None = None, *,
        rules: str | None = None, meta: str | None = None) -> dict[str, bytes]:
    """A minimal increment: results.json (+ optional files relative to EXP)."""
    body = results if isinstance(results, str) else json.dumps(results, indent=1)
    out = {f"{EXP}/results.json": body.encode()}
    for rel, data in (files or {}).items():
        out[f"{EXP}/{rel}"] = data.encode() if isinstance(data, str) else data
    if rules is not None:
        out["AUDIT_RULES.md"] = rules.encode()
    if meta is not None:
        out[f"{EXP}/metadata.yml"] = meta.encode()
    return out


def found(files, check):
    return run_checks(files, [check]).findings


def codes(files, check):
    return [(f.severity, f.rule) for f in found(files, check)]


def csv(header, rows):
    return "\n".join([",".join(header)] + [",".join(str(c) for c in r) for r in rows]) + "\n"


# ======================================================= numeric_validity
@pytest.mark.parametrize("raw", ["0", "-3", "1.5", "1e-30", '"0.125"', '"1e3"',
                                 "100000000000000000000000000000"])
def test_numeric_validity_passes_a_finite_number(raw):
    """MUTATION: replace `is_number_shape` with `isinstance(value, float)` — ints
    and numeric strings, which `precision` relies on, start blocking."""
    text = '{"quantities": [{"name": "a", "value": %s, "unit": "1", "source": "s"}]}' % raw
    assert codes(inc(text), "numeric_validity") == []


@pytest.mark.parametrize("raw", ["null", "true", "false", "NaN", "Infinity", "-Infinity",
                                 '"nan"', '"inf"', '"n/a"', '""', '"1.2 eV"', "[]", "{}"])
def test_numeric_validity_blocks_every_non_finite_shape(raw):
    """MUTATION: drop the bool exclusion or the isfinite test in
    `is_number_shape`, or skip string values — one of null / bool / NaN /
    Infinity (which Python's JSON reader accepts) / a non-numeric string passes."""
    text = '{"quantities": [{"name": "a", "value": %s, "unit": "1", "source": "s"}]}' % raw
    assert codes(inc(text), "numeric_validity") == [(BLOCKER, "CA-NUM-005")]


def test_numeric_validity_blocks_a_missing_value_and_skips_unparseable_files():
    """MUTATION: `continue` on a missing value — a row with no value passes. And
    the unparseable file must stay schema's (CA-META-001) business: raising or
    reporting it here would multiply one defect across the pack."""
    assert codes(inc({"quantities": [{"name": "a", "unit": "1"}]}),
                 "numeric_validity") == [(BLOCKER, "CA-NUM-005")]
    assert codes(inc("{not json"), "numeric_validity") == []
    assert codes(inc({"quantities": "no"}), "numeric_validity") == []


# ============================================================ range_rules
RANGES = """# Constitution

```crossaudit-ranges
[{"name": "activation_energy", "unit": "kJ/mol", "min": 0, "max": 500},
 {"name": "p_value", "unit": "1", "min": 0, "max": 1},
 {"name": "mae_*", "unit": "eV", "min": 0}]
```
"""


def ranged(*quantities, rules=RANGES):
    return inc({"quantities": list(quantities)}, rules=rules)


def test_range_rules_pass_in_range_and_ignore_unmatched_quantities():
    """MUTATION: block every quantity no entry matches — an undeclared quantity
    must produce nothing (the pack enforces declared properties, not coverage)."""
    files = ranged(q("activation_energy", 84.2, "kJ/mol"), q("p_value", 0.03),
                   q("mae_test", 0.12, "eV"), q("whatever", -1e9, "furlong"))
    assert codes(files, "range_rules") == []


@pytest.mark.parametrize("value,blocks", [
    (0, False), (1, False), (0.5, False), ("0", False), ("1.000", False),
    (-1e-12, True), (1 + 1e-12, True), (1.0000000000000002, True),
    ("1.00000000000000000001", True), ("-0.00000000000000000001", True),
    (1.4, True), (-3, True)])
def test_range_bounds_are_inclusive_and_compared_as_exact_decimals(value, blocks):
    """MUTATION: `<=`/`>=` for `<`/`>` (bounds exclusive: 0 and 1 block), or a
    float comparison — `"1.00000000000000000001"` rounds to the double 1.0 and
    passes, so the strings one ulp-below-resolution outside each bound redden."""
    got = codes(ranged(q("p_value", value)), "range_rules")
    assert got == ([(BLOCKER, "CA-PHYS-001")] if blocks else []), value


@pytest.mark.parametrize("bound", [0, 500])
@pytest.mark.parametrize("step", [-1e-9, -1e-6, 0, 1e-6, 1e-9])
def test_range_sweep_just_inside_and_outside_both_ends(bound, step):
    """MUTATION: shift either bound by any amount, or make one end exclusive —
    the contiguous sweep across both ends flips at the wrong point."""
    value = bound + step
    outside = value < 0 or value > 500
    got = codes(ranged(q("activation_energy", value, "kJ/mol")), "range_rules")
    assert bool(got) is outside, value


@pytest.mark.parametrize("unit", ["eV", "kj/mol", "kJ/mol ", " kJ/mol", "kJ mol-1", ""])
def test_range_unit_must_be_byte_equal(unit):
    """MUTATION: compare units case-folded or stripped — a swapped or
    re-spelled label (D03 `label_swapped`) passes with its value unchanged."""
    got = codes(ranged(q("activation_energy", 84.2, unit)), "range_rules")
    assert got == [(BLOCKER, "CA-PHYS-001")]


def test_sign_flip_and_glob_and_first_match_wins():
    """MUTATION: try every entry instead of the first match, or use
    `fnmatch.fnmatch` (case-folding through normcase). D07's negated value
    blocks; the first entry decides, in declared order; matching is
    case-sensitive."""
    assert codes(ranged(q("activation_energy", -84.2, "kJ/mol")), "range_rules") == [
        (BLOCKER, "CA-PHYS-001")]
    assert codes(ranged(q("mae_test", -0.1, "eV")), "range_rules") == [
        (BLOCKER, "CA-PHYS-001")]
    tight_first = """```crossaudit-ranges
[{"name": "mae_test", "unit": "eV", "max": 1}, {"name": "mae_*", "unit": "eV", "max": 100}]
```
"""
    loose_first = """```crossaudit-ranges
[{"name": "mae_*", "unit": "eV", "max": 100}, {"name": "mae_test", "unit": "eV", "max": 1}]
```
"""
    assert codes(ranged(q("mae_test", 5, "eV"), rules=tight_first), "range_rules") == [
        (BLOCKER, "CA-PHYS-001")]
    assert codes(ranged(q("mae_test", 5, "eV"), rules=loose_first), "range_rules") == []
    assert codes(ranged(q("MAE_TEST", -5, "eV")), "range_rules") == []


def test_range_value_that_cannot_be_compared_blocks():
    """MUTATION: skip a matched quantity whose value is not a number — the range
    check selected alone would pass a null band gap it was told to bound."""
    assert codes(ranged(q("p_value", None)), "range_rules") == [(BLOCKER, "CA-PHYS-001")]
    assert codes(ranged(q("p_value", "n/a")), "range_rules") == [(BLOCKER, "CA-PHYS-001")]


@pytest.mark.parametrize("block", [
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"unit\": \"1\"\n```\n",       # bad JSON
    "```crossaudit-ranges\n{\"name\": \"p_value\", \"unit\": \"1\"}\n```\n",       # not a list
    "```crossaudit-ranges\n[{\"unit\": \"1\", \"max\": 1}]\n```\n",                 # no name
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"max\": 1}]\n```\n",           # no unit
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"unit\": \"\", \"max\": 1}]\n```\n",
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"unit\": \"1\", \"max\": \"1\"}]\n```\n",
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"unit\": \"1\", \"max\": true}]\n```\n",
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"unit\": \"1\", \"min\": 2, \"max\": 1}]\n```\n",
    "```crossaudit-ranges\n[\"p_value\"]\n```\n",
    "```crossaudit-ranges\n[{\"name\": \"p_value\", \"unit\": \"1\", \"max\": 1}]\n",  # unclosed
    "```crossaudit-ranges\n[]\n```\n\n```crossaudit-ranges\n[]\n```\n",              # two fences
])
def test_malformed_ranges_block_blocks(block):
    """MUTATION: skip an entry missing name/unit, accept a string or bool bound,
    or ignore an unclosed / duplicated fence — a rulebook that cannot be read
    would then read as no rulebook, and pass."""
    got = codes(ranged(q("p_value", 0.5), rules=block), "range_rules")
    assert got and set(got) == {(BLOCKER, "CA-PHYS-001")}, block


def test_ranges_only_come_from_audit_rules_files():
    """MUTATION: read ranges from any Markdown file — a generator could then
    write its own permissive rules into SUMMARY.md. And absent a block, nothing."""
    files = inc({"quantities": [q("p_value", 7)]},
                {"SUMMARY.md": RANGES})
    assert codes(files, "range_rules") == []
    files["GENERAL_AUDIT_RULES.md"] = RANGES.encode()
    assert codes(files, "range_rules") == [(BLOCKER, "CA-PHYS-001")]


# ============================================================ derivations
DATA = csv(["id", "split", "x", "truth", "pred", "group", "response"], [
    ["c1", "train", 1, 1, 1.5, "control", 1],
    ["c2", "train", 2, 2, 2, "control", 2],
    ["c3", "test", 3, 3, 2, "control", 3],
    ["c4", "test", 4, 9, 9, "treated", 4],
])
TWO = csv(["group", "response"], [["c", 1], ["c", 2], ["c", 3], ["t", 4], ["t", 5], ["t", 6]])


def derived(method, inp, value, *, data=DATA, tolerance=None, extra_q=(), name="out"):
    row = {"quantity": name, "method": method, "input": inp}
    if tolerance is not None:
        row["tolerance"] = tolerance
    return inc({"quantities": [q(name, value), *extra_q], "derivations": [row]},
               {"data/d.csv": data})


def assert_derivation(method, inp, expected, *, data=DATA, tol=1e-9, extra_q=()):
    """Passes at the hand value; blocks at the hand value moved by 1%."""
    ok = derived(method, inp, expected, data=data, tolerance={"abs": tol}, extra_q=extra_q)
    assert codes(ok, "derivations") == [], (method, found(ok, "derivations"))
    off = expected * 1.01 if expected else 0.01
    bad = derived(method, inp, off, data=data, tolerance={"abs": tol}, extra_q=extra_q)
    assert codes(bad, "derivations") == [(BLOCKER, "CA-DERIV-001")], method


F = "data/d.csv"
SAMPLE_SD = math.sqrt(5 / 3)        # sample sd of 1, 2, 3, 4: sum sq dev 5, n-1 = 3


@pytest.mark.parametrize("method,inp,expected", [
    ("count", {"file": F, "x": "x"}, 4),
    ("count", {"file": F, "column": "x"}, 4),
    ("count", {"file": F, "x": "id", "where": {"column": "split", "equals": "test"}}, 2),
    ("mean", {"file": F, "x": "x"}, 2.5),
    ("sd", {"file": F, "x": "x"}, SAMPLE_SD),
    ("sem", {"file": F, "x": "x"}, SAMPLE_SD / 2),
    ("min", {"file": F, "x": "x"}, 1),
    ("max", {"file": F, "x": "x"}, 4),
    ("sum", {"file": F, "x": "x"}, 10),
    ("last", {"file": F, "y": "truth"}, 9),
    ("last_delta_abs", {"file": F, "y": "truth"}, 6),
    # truth 1,2,3 vs pred 1.5,2,2 (train+test minus c4): |e| = .5, 0, 1
    ("mae", {"file": F, "truth": "truth", "pred": "pred",
             "where": {"column": "group", "equals": "control"}}, 0.5),
    ("rmse", {"file": F, "truth": "truth", "pred": "pred",
              "where": {"column": "group", "equals": "control"}}, math.sqrt(1.25 / 3)),
    ("r2", {"file": F, "truth": "truth", "pred": "pred",
            "where": {"column": "group", "equals": "control"}}, 1 - 1.25 / 2),
])
def test_each_column_method_against_a_hand_value(method, inp, expected):
    """MUTATION: change any formula in `_METHODS` (n for n-1 in `sd`, sqrt(n)
    dropped from `sem`, the where filter ignored, ...) — its row reddens."""
    assert_derivation(method, inp, expected)


def test_line_and_correlation_methods_against_hand_values():
    """MUTATION: swap x and y, or drop the centring in `_linfit`/`_pearson`.
    x = 1,2,3; y = 2,4,7: Sxy = 5, Sxx = 2, Syy = 114/9."""
    data = csv(["x", "y"], [[1, 2], [2, 4], [3, 7]])
    inp = {"file": F, "x": "x", "y": "y"}
    assert_derivation("linfit_slope", inp, 2.5, data=data)
    assert_derivation("linfit_intercept", inp, -2 / 3, data=data)
    assert_derivation("pearson_r", inp, 5 / math.sqrt(2 * 114 / 9), data=data)


def test_two_sample_methods_against_hand_values():
    """MUTATION: pool the variances, use n for n-1, swap a and b, or ignore the
    per-argument where. a = 1,2,3; b = 4,5,6: difference -3, se = sqrt(2/3),
    t = -3/sqrt(2/3), Welch df = 4 exactly, t_0.975(4) = 2.776445105 (table)."""
    a = {"column": "response", "where": {"column": "group", "equals": "c"}}
    b = {"column": "response", "where": {"column": "group", "equals": "t"}}
    inp = {"file": F, "a": a, "b": b}
    se = math.sqrt(2 / 3)
    assert_derivation("difference", inp, -3, data=TWO)
    assert_derivation("welch_t", inp, -3 / se, data=TWO)
    assert_derivation("welch_df", inp, 4, data=TWO)
    assert_derivation("ci95_low", inp, -3 - 2.776445105 * se, data=TWO, tol=1e-7)
    assert_derivation("ci95_high", inp, -3 + 2.776445105 * se, data=TWO, tol=1e-7)
    # Unequal variances: a = 1,2,3 (var 1, n 3), b = 4,6 (var 2, n 2):
    # df = (1/3 + 1)^2 / ((1/3)^2/2 + 1^2/1) = 32/19.
    unequal = csv(["group", "response"], [["c", 1], ["c", 2], ["c", 3], ["t", 4], ["t", 6]])
    assert_derivation("welch_df", inp, 32 / 19, data=unequal)


def test_physical_methods_recover_the_constants_they_were_built_from():
    """MUTATION: drop the minus sign or the /1000 in the Arrhenius energy, use
    the wrong R, use two_theta instead of theta, or ignore `wavelength`. The
    data are generated from Ea = 50 kJ/mol, ln A = 20 and a = 4 Å exactly."""
    R = 8.314462618
    rates = csv(["T_K", "k"], [[T, repr(math.exp(20 - 50000 / (R * T)))]
                               for T in (300, 350, 400, 450)])
    inp = {"file": F, "T_K": "T_K", "k": "k"}
    assert_derivation("arrhenius_ea_kj_per_mol", inp, 50.0, data=rates, tol=1e-8)
    assert_derivation("arrhenius_ln_a", inp, 20.0, data=rates, tol=1e-8)
    for wavelength, given in ((1.5406, None), (0.7093, 0.7093)):
        peaks = csv(["two_theta_deg", "h", "k", "l"], [
            [repr(2 * math.degrees(math.asin(wavelength * math.sqrt(h*h + k*k + l*l) / 8.0))),
             h, k, l] for h, k, l in ((1, 1, 1), (2, 0, 0), (2, 2, 0), (3, 1, 1))])
        inp = {"file": F, "two_theta_deg": "two_theta_deg", "h": "h", "k": "k", "l": "l"}
        if given is not None:
            inp["wavelength"] = given
        assert_derivation("bragg_cubic_a", inp, 4.0, data=peaks, tol=1e-9)


def test_scalar_methods_read_quantities_and_literals():
    """MUTATION: read `t`/`df`/`x` from a file instead of the quantities list,
    or drop the factor in `scale`. Operands that are quantities no derivation
    grounds still verify the arithmetic — and say so with CA-DERIV-003 only."""
    t, df = q("t_statistic", 2.0), q("df", 10)
    loose = [(ADVISORY, "CA-DERIV-003")]
    inp = {"t": "t_statistic", "df": "df"}
    assert codes(derived("t_pvalue_two_sided", inp, 0.07338803477,
                         tolerance={"abs": 1e-9}, extra_q=(t, df)), "derivations") == loose
    assert codes(derived("t_pvalue_two_sided", inp, 0.07338803477 * 1.01,
                         tolerance={"abs": 1e-9}, extra_q=(t, df)),
                 "derivations") == [(BLOCKER, "CA-DERIV-001")]
    assert_derivation("t_pvalue_two_sided", {"t": 2.0, "df": 10}, 0.07338803477, tol=1e-9)
    inp = {"x": "lattice_a", "factor": 2.5}
    assert codes(derived("scale", inp, 10.0, extra_q=(q("lattice_a", 4.0),)),
                 "derivations") == loose
    assert codes(derived("scale", inp, 10.1, extra_q=(q("lattice_a", 4.0),)),
                 "derivations") == [(BLOCKER, "CA-DERIV-001")]


@pytest.mark.parametrize("t,df,p,tol", [
    (2.0, 10, 0.07339, 5e-6),        # 4 s.f.
    (2.262, 9, 0.05000, 3e-4),       # table quantile, 0.975 at df 9
    (2.228, 10, 0.05000, 3e-4),
    (2.571, 5, 0.05000, 3e-4),
    (12.706, 1, 0.05000, 3e-4),
    (3.169, 10, 0.01000, 3e-4),
    (1.812, 10, 0.10000, 3e-4),
    (1.0, 1, 0.5, 1e-12),            # Cauchy: P(|T|>1) = 1/2 exactly
    (0.0, 5, 1.0, 1e-15),
    (-2.0, 10, 0.07339, 5e-6),       # two-sided: sign does not matter
    (1.959964, 1e7, 0.05, 2e-6),     # tends to the normal
])
def test_t_pvalue_against_published_values(t, df, p, tol):
    """MUTATION: one-sided instead of two-sided (halves every p), a wrong
    argument order in `betainc`, or an early exit in the Lentz loop."""
    assert abs(ai4s.t_pvalue_two_sided(t, df) - p) <= tol


@pytest.mark.parametrize("df,q975", [(1, 12.7062047), (4, 2.7764451), (9, 2.2621572),
                                     (30, 2.0422725), (1e6, 1.9599663)])
def test_t_quantile_inverts_the_cdf(df, q975):
    """MUTATION: bisect toward the wrong side, or stop after a few iterations."""
    assert abs(ai4s.t_quantile_two_sided(0.05, df) - q975) < 1e-6


@pytest.mark.parametrize("rel", [10.0 ** -e for e in range(12, 0, -1)])
@pytest.mark.parametrize("factor", [0.5, 0.9, 0.99, 1.01, 1.1, 2.0])
@pytest.mark.parametrize("sign", [1, -1])
def test_rel_tolerance_flips_exactly_at_the_declared_tolerance(rel, factor, sign):
    """MUTATION: compare relative to the reported value, use `<` against a
    scaled tolerance, or ignore the declared tolerance in favour of the default
    — across twelve decades the verdict flips at a different factor."""
    reported = 2.5 * (1 + sign * factor * rel)
    got = codes(derived("mean", {"file": F, "x": "x"}, reported,
                        tolerance={"rel": rel}), "derivations")
    assert bool(got) is (factor > 1), (rel, factor, sign, got)


@pytest.mark.parametrize("tol", [10.0 ** -e for e in range(12, 0, -1)])
@pytest.mark.parametrize("factor", [0.5, 0.99, 1.01, 2.0])
def test_abs_tolerance_flips_exactly_at_the_declared_tolerance(tol, factor):
    """MUTATION: read `abs` as relative, or `<=` as `<` with a fudge."""
    got = codes(derived("mean", {"file": F, "x": "x"}, 2.5 + factor * tol,
                        tolerance={"abs": tol}), "derivations")
    assert bool(got) is (factor > 1), (tol, factor)


def test_default_tolerance_is_rel_1e9():
    """MUTATION: change the default, or make an absent tolerance accept anything."""
    assert codes(derived("mean", {"file": F, "x": "x"}, 2.5 * (1 + 5e-10)), "derivations") == []
    assert codes(derived("mean", {"file": F, "x": "x"}, 2.5 * (1 + 2e-9)),
                 "derivations") == [(BLOCKER, "CA-DERIV-001")]


@pytest.mark.parametrize("sig", range(2, 9))
def test_sig_tolerance_at_two_to_eight_figures(sig):
    """MUTATION: round only one side, truncate instead of rounding, or count
    decimal places instead of significant figures. mean(1, 1, 2) = 4/3: the
    report rounded to `sig` figures passes; one unit in its last place either
    way blocks; and the same report written with trailing zeros passes."""
    data = csv(["x"], [[1], [1], [2]])
    computed = 4 / 3
    text = format(computed, f".{sig - 1}e")
    ulp = 10.0 ** (math.floor(math.log10(computed)) - sig + 1)

    def at(value):
        return codes(derived("mean", {"file": F, "x": "x"}, value, data=data,
                             tolerance={"sig": sig}), "derivations")

    assert at(float(text)) == [], text
    assert at(text) == []
    assert at(text.replace("e", "0e")) == []
    assert at(float(text) + ulp) == [(BLOCKER, "CA-DERIV-001")]
    assert at(float(text) - ulp) == [(BLOCKER, "CA-DERIV-001")]


def test_wrong_rows_and_n_mismatch_block():
    """MUTATION: ignore `where` — D10 `wrong_rows_used` (a train-row MAE reported
    as test) and D11 (an inflated n) pass."""
    inp = {"file": F, "x": "x", "where": {"column": "split", "equals": "test"}}
    assert codes(derived("mean", inp, 3.5), "derivations") == []
    assert codes(derived("mean", inp, 1.5), "derivations") == [(BLOCKER, "CA-DERIV-001")]
    assert codes(derived("count", inp, 3), "derivations") == [(BLOCKER, "CA-DERIV-001")]
    assert codes(derived("count", {**inp, "where": {"column": "split", "equals": 7}}, 0),
                 "derivations") == []          # int compared as its string; zero rows


@pytest.mark.parametrize("label,method,inp,data", [
    ("unknown method", "mode", {"file": F, "x": "x"}, DATA),
    ("missing file", "mean", {"file": "data/nope.csv", "x": "x"}, DATA),
    ("escapes the experiment", "mean", {"file": "../d.csv", "x": "x"}, DATA),
    ("no file named", "mean", {"x": "x"}, DATA),
    ("missing column", "mean", {"file": F, "x": "nope"}, DATA),
    ("missing argument", "mae", {"file": F, "truth": "truth"}, DATA),
    ("x and column both", "mean", {"file": F, "x": "x", "column": "x"}, DATA),
    ("non-numeric cell", "mean", {"file": F, "x": "id"}, DATA),
    ("empty cell", "mean", {"file": F, "x": "x"}, "x,y\n1,2\n,3\n"),
    ("blank line between rows", "mean", {"file": F, "x": "x"}, "x\n1\n\n1\n"),
    ("extra field", "mean", {"file": F, "x": "x"}, "x\n1,2\n"),
    ("no header", "mean", {"file": F, "x": "x"}, "\n\n"),
    ("decimal comma", "mean", {"file": F, "x": "x"}, 'x\n"1,5"\n'),
    ("short row", "mean", {"file": F, "x": "y"}, "x,y\n1,2\n3\n"),
    ("inf cell", "mean", {"file": F, "x": "x"}, csv(["x"], [["1e99999"]])),
    ("duplicate header", "mean", {"file": F, "x": "x"}, "x,x\n1,2\n"),
    ("where column missing", "mean",
     {"file": F, "x": "x", "where": {"column": "nope", "equals": "a"}}, DATA),
    ("where malformed", "mean", {"file": F, "x": "x", "where": {"column": "split"}}, DATA),
    ("where equals float", "mean",
     {"file": F, "x": "x", "where": {"column": "split", "equals": 1.5}}, DATA),
    ("too few rows", "sd", {"file": F, "x": "x"}, csv(["x"], [[1]])),
    ("zero rows", "mean",
     {"file": F, "x": "x", "where": {"column": "split", "equals": "val"}}, DATA),
    ("zero variance", "r2", {"file": F, "truth": "x", "pred": "x"}, csv(["x"], [[1], [1]])),
    ("not utf-8", "mean", {"file": F, "x": "x"}, b"x\n\xff\xfe\n"),
    ("scalar names nothing", "t_pvalue_two_sided", {"t": "nope", "df": 3}, DATA),
    ("scalar is a bool", "t_pvalue_two_sided", {"t": True, "df": 3}, DATA),
    ("paired arg is a mapping", "mae",
     {"file": F, "truth": {"column": "truth"}, "pred": "pred"}, DATA),
])
def test_a_derivation_that_cannot_be_verified_blocks(label, method, inp, data):
    """MUTATION: turn any `_Undecidable` raise into a skip — what cannot be
    verified would then read as verified (the CA-NUM-001 shape)."""
    got = codes(derived(method, inp, 1.0, data=data), "derivations")
    assert got == [(BLOCKER, "CA-DERIV-001")], label


@pytest.mark.parametrize("results", [
    {"quantities": [q("out", 1)], "derivations": {"quantity": "out"}},
    {"quantities": [q("out", 1)], "derivations": [7]},
    {"quantities": [q("out", 1)], "derivations": [{"method": "mean", "input": {}}]},
    {"quantities": [q("out", 1)], "derivations": [{"quantity": "gone", "method": "mean",
                                                   "input": {"file": F, "x": "x"}}]},
    {"quantities": [q("out", 1), q("out", 1)],
     "derivations": [{"quantity": "out", "method": "mean", "input": {"file": F, "x": "x"}}]},
    {"quantities": [q("out", None)],
     "derivations": [{"quantity": "out", "method": "mean", "input": {"file": F, "x": "x"}}]},
    {"quantities": [q("out", 2.5)],
     "derivations": [{"quantity": "out", "method": "mean", "input": "data/d.csv"}]},
])
def test_malformed_derivation_rows_block(results):
    """MUTATION: skip a row that is not a mapping, a quantity that names no row
    or two rows, or a non-numeric reported value."""
    assert codes(inc(results, {"data/d.csv": DATA}), "derivations") == [
        (BLOCKER, "CA-DERIV-001")]


@pytest.mark.parametrize("tolerance", [{"abs": 1, "rel": 1}, {"abs": -1}, {"abs": "0.1"},
                                       {"rel": True}, {"sig": 0}, {"sig": 2.0}, {"sig": 18},
                                       {"ulp": 1}, [], "1e-9"])
def test_malformed_tolerance_blocks(tolerance):
    """MUTATION: fall back to the default on an unreadable tolerance — a
    generator could then write `{"abs": "1e9"}` and believe it was accepted."""
    got = codes(derived("mean", {"file": F, "x": "x"}, 2.5, tolerance=tolerance),
                "derivations")
    assert got == [(BLOCKER, "CA-DERIV-001")], tolerance


def test_absent_declarations_produce_nothing_and_uncommitted_is_advisory():
    """MUTATION: demand a derivation per quantity (coverage), or block an
    honestly uncommitted file. A file declared uncommitted that IS present is
    verified like any other."""
    assert codes(inc({"quantities": [q("out", 1)]}), "derivations") == []
    assert codes(inc({"quantities": [q("out", 1)], "derivations": []}), "derivations") == []
    away = {"file": "data/big.h5", "uncommitted": True, "x": "x"}
    assert codes(derived("mean", away, 99), "derivations") == [(ADVISORY, "CA-DERIV-002")]
    assert codes(derived("mean", {"file": "uncommitted", "x": "x"}, 99),
                 "derivations") == [(ADVISORY, "CA-DERIV-002")]
    here = {"file": F, "uncommitted": True, "x": "x"}
    assert codes(derived("mean", here, 2.5), "derivations") == []
    assert codes(derived("mean", here, 99), "derivations") == [(BLOCKER, "CA-DERIV-001")]


def test_trailing_blank_lines_are_layout():
    """MUTATION: refuse every blank line — a file ending in a blank line, which
    most editors write, would block on a correct derivation."""
    data = "x\n1\n2\n\n\n"
    assert codes(derived("mean", {"file": F, "x": "x"}, 1.5, data=data), "derivations") == []


def test_bom_is_not_part_of_the_first_column():
    """MUTATION: decode as plain utf-8 — an exported CSV's byte-order mark
    becomes part of the first header and the column reads as missing."""
    data = "﻿x\n1\n2\n".encode()
    assert codes(derived("mean", {"file": F, "x": "x"}, 1.5, data=data), "derivations") == []

# ======================================== derivations v2 (DESIGN.md §9 Amendment 3)
# A variant x label-fraction table: the first dogfood audit had to pre-join the
# two columns because `where` took one clause.
GRID_VALUES = {("sup", "0.02"): [11.0, 12.0], ("sup", "0.1"): [7.0, 8.0],
               ("ssl", "0.02"): [4.0, 5.0], ("ssl", "0.1"): [3.0, 3.5]}
GRID = csv(["variant", "frac", "seed", "mae"],
           [[v, f, s, x] for (v, f), xs in GRID_VALUES.items() for s, x in enumerate(xs)])


def clause(column, equals):
    return {"column": column, "equals": equals}


@pytest.mark.parametrize("cell", sorted(GRID_VALUES))
@pytest.mark.parametrize("order", ["variant_first", "frac_first"])
def test_where_list_selects_the_intersection_of_every_clause(cell, order):
    """MUTATION: apply only the first clause of a list, or OR the clauses —
    every cell of the 2x2 grid then averages rows from a neighbouring cell, so
    the sweep over all four cells (in both clause orders) reddens."""
    variant, frac = cell
    clauses = [clause("variant", variant), clause("frac", frac)]
    if order == "frac_first":
        clauses.reverse()
    inp = {"file": F, "x": "mae", "where": clauses}
    expected = sum(GRID_VALUES[cell]) / 2
    assert_derivation("mean", inp, expected, data=GRID)
    assert codes(derived("count", inp, 2, data=GRID), "derivations") == []


def test_where_list_of_one_equals_the_single_mapping_and_works_per_argument():
    """MUTATION: treat a one-clause list differently from the mapping, or skip
    `_clauses` in the per-argument where of a two-sample method."""
    one = {"file": F, "x": "mae", "where": [clause("variant", "ssl")]}
    assert_derivation("mean", one, 3.875, data=GRID)
    a = {"column": "mae", "where": [clause("variant", "ssl"), clause("frac", "0.1")]}
    b = {"column": "mae", "where": [clause("variant", "sup"), clause("frac", "0.1")]}
    assert_derivation("difference", {"file": F, "a": a, "b": b}, 3.25 - 7.5, data=GRID)


@pytest.mark.parametrize("label,where", [
    ("empty list", []),
    ("element not a mapping", [clause("variant", "ssl"), "frac=0.1"]),
    ("element an int", [clause("variant", "ssl"), 7]),
    ("element missing equals", [clause("variant", "ssl"), {"column": "frac"}]),
    ("element with an extra key", [{"column": "frac", "equals": "0.1", "or": "x"}]),
    ("element equals a float", [clause("variant", "ssl"), clause("frac", 0.1)]),
    ("element equals a bool", [clause("variant", "ssl"), clause("frac", True)]),
    ("element names no column", [clause("variant", "ssl"), clause("nope", "0.1")]),
    ("malformed after a clause that selects nothing", [clause("variant", "zzz"), 7]),
    ("a string", "variant=ssl"),
    ("a nested list", [[clause("variant", "ssl")]]),
])
def test_a_where_list_element_of_the_wrong_shape_blocks(label, where):
    """MUTATION: skip a malformed clause, or stop reading clauses once the rows
    run out — half a filter would then pass as the whole one."""
    inp = {"file": F, "x": "mae", "where": where}
    assert codes(derived("mean", inp, 1.0, data=GRID), "derivations") == [
        (BLOCKER, "CA-DERIV-001")], label
    two = {"file": F, "a": {"column": "mae", "where": where}, "b": "mae"}
    assert codes(derived("difference", two, 1.0, data=GRID), "derivations") == [
        (BLOCKER, "CA-DERIV-001")], label


V5 = csv(["x"], [[3], [1], [4], [1], [5]])       # unsorted, a repeated value


@pytest.mark.parametrize("method,inp,expected,data", [
    # 1,2,3,4: sum of squared deviations 5, n = 4
    ("sd_population", {"file": F, "x": "x"}, math.sqrt(5 / 4), DATA),
    ("sem_population", {"file": F, "x": "x"}, math.sqrt(5 / 4) / 2, DATA),
    ("median", {"file": F, "x": "x"}, 2.5, DATA),
    ("median", {"file": F, "column": "x"}, 3, V5),          # sorted: 1 1 3 4 5
    ("median", {"file": F, "x": "x", "where": clause("split", "test")}, 3.5, DATA),
    # 3,1,4,1,5: mean 2.8, squared deviations sum 12.8
    ("sd_population", {"file": F, "x": "x"}, math.sqrt(12.8 / 5), V5),
    ("sd_population", {"file": F, "x": "x"}, 0.0, csv(["x"], [[7]])),
])
def test_population_and_median_methods_against_hand_values(method, inp, expected, data):
    """MUTATION: n-1 for n in `_var_population`, sqrt(n) dropped from
    `sem_population`, the median taken without sorting or as the upper middle
    element of an even count."""
    assert_derivation(method, inp, expected, data=data)


@pytest.mark.parametrize("n", range(2, 9))
def test_sd_and_sd_population_are_told_apart_at_every_n(n):
    """MUTATION: alias `sd_population` to `sd` (or the reverse) — the dogfood's
    defect, a numpy ddof=0 sd reported as a sample sd, would pass. Swept over
    n = 2..8, the seed counts real reports use: each declaration passes its own
    value and blocks the other's, at the four decimals a report rounds to."""
    data = csv(["x"], [[k * k] for k in range(n)])
    xs = [k * k for k in range(n)]
    m = sum(xs) / n
    ss = sum((x - m) ** 2 for x in xs)
    sample, population = math.sqrt(ss / (n - 1)), math.sqrt(ss / n)
    tol = {"abs": 6e-05}
    for method, own, other in (("sd", sample, population), ("sd_population", population, sample)):
        inp = {"file": F, "x": "x"}
        assert codes(derived(method, inp, round(own, 4), data=data, tolerance=tol),
                     "derivations") == [], (method, n)
        assert codes(derived(method, inp, round(other, 4), data=data, tolerance=tol),
                     "derivations") == [(BLOCKER, "CA-DERIV-001")], (method, n)
    sem = {"file": F, "x": "x"}
    assert codes(derived("sem_population", sem, round(population / math.sqrt(n), 4),
                         data=data, tolerance=tol), "derivations") == []
    assert codes(derived("sem_population", sem, round(sample / math.sqrt(n), 4),
                         data=data, tolerance=tol), "derivations") == [(BLOCKER, "CA-DERIV-001")]


def test_ratio_and_percent_change_in_column_form():
    """MUTATION: use the first row instead of the mean, swap the operands, or
    divide by old instead of |old|. TWO: c = 1,2,3 (mean 2), t = 4,5,6 (mean 5)."""
    c = {"column": "response", "where": clause("group", "c")}
    t = {"column": "response", "where": clause("group", "t")}
    assert_derivation("ratio", {"file": F, "a": t, "b": c}, 2.5, data=TWO)
    assert_derivation("ratio", {"file": F, "a": c, "b": t}, 0.4, data=TWO)
    assert_derivation("percent_change", {"file": F, "new": t, "old": c}, 150.0, data=TWO)
    assert_derivation("percent_change", {"file": F, "new": c, "old": t}, -60.0, data=TWO)
    # a top-level where with plain column operands: means over the same rows
    assert_derivation("ratio", {"file": F, "a": "truth", "b": "x",
                                "where": clause("split", "test")}, 6 / 3.5)
    neg = csv(["g", "v"], [["old", -4], ["old", -4], ["new", -3], ["new", -3]])
    old = {"column": "v", "where": clause("g", "old")}
    new = {"column": "v", "where": clause("g", "new")}
    assert_derivation("percent_change", {"file": F, "new": new, "old": old}, 25.0, data=neg)


@pytest.mark.parametrize("new,old,expected", [
    (3.0, 4.0, -25.0), (5.0, 4.0, 25.0), (-3.0, -4.0, 25.0), (-5.0, -4.0, -25.0),
    (4.0, 4.0, 0.0), (0.0, 2.0, -100.0), (1.0, -1.0, 200.0)])
def test_percent_change_sign_follows_the_change_for_every_sign_of_old(new, old, expected):
    """MUTATION: divide by `old` rather than `abs(old)` — every row with a
    negative reference flips sign — or compute (old - new). The wrong sign of
    the same magnitude must block, which is D18's `percent_sign_flipped`."""
    loose = [(ADVISORY, "CA-DERIV-003")]
    extra = (q("m_new", new), q("m_old", old))
    by_name = {"new": "m_new", "old": "m_old"}
    assert codes(derived("percent_change", by_name, expected, extra_q=extra,
                         tolerance={"abs": 1e-9}), "derivations") == loose
    assert_derivation("percent_change", {"new": new, "old": old}, expected)
    if expected:
        assert codes(derived("percent_change", {"new": new, "old": old}, -expected,
                             tolerance={"abs": 1e-9}), "derivations") == [
            (BLOCKER, "CA-DERIV-001")]


def test_ratio_scalar_form_reads_quantities_and_literals():
    """MUTATION: read the scalar form's strings as columns, or swap a and b."""
    assert_derivation("ratio", {"a": 3.0, "b": 4.0}, 0.75)
    extra = (q("mae_a", 3.0), q("mae_b", 4.0))
    assert codes(derived("ratio", {"a": "mae_a", "b": "mae_b"}, 0.75, extra_q=extra),
                 "derivations") == [(ADVISORY, "CA-DERIV-003")]
    assert codes(derived("ratio", {"a": "mae_b", "b": "mae_a"}, 0.75, extra_q=extra),
                 "derivations") == [(BLOCKER, "CA-DERIV-001")]


@pytest.mark.parametrize("label,method,inp,data", [
    ("ratio by a zero mean", "ratio", {"file": F, "a": "x", "b": "z"}, "x,z\n1,1\n2,-1\n"),
    ("ratio by a zero literal", "ratio", {"a": 1.0, "b": 0}, DATA),
    ("percent from a zero mean", "percent_change", {"file": F, "new": "x", "old": "z"},
     "x,z\n1,0\n2,0\n"),
    ("percent from a zero literal", "percent_change", {"new": 1.0, "old": 0.0}, DATA),
    ("where without a file", "ratio", {"a": "x", "b": "truth",
                                       "where": clause("split", "test")}, DATA),
    ("column mapping without a file", "percent_change",
     {"new": {"column": "x"}, "old": "truth"}, DATA),
    ("scalar names nothing", "ratio", {"a": "nope", "b": 2.0}, DATA),
    ("column form with a literal operand", "ratio", {"file": F, "a": "x", "b": 2.0}, DATA),
    ("column form missing a column", "percent_change", {"file": F, "new": "x", "old": "nope"},
     DATA),
    ("missing operand", "percent_change", {"new": 1.0}, DATA),
    ("median of no rows", "median", {"file": F, "x": "x", "where": clause("split", "val")}, DATA),
    ("sd_population of no rows", "sd_population",
     {"file": F, "x": "x", "where": clause("split", "val")}, DATA),
    ("median of a text cell", "median", {"file": F, "x": "id"}, DATA),
])
def test_a_v2_derivation_that_cannot_be_verified_blocks(label, method, inp, data):
    """MUTATION: return 0 for a zero divisor (the reported 0.0 here then
    passes; an inf is caught a second time by the finiteness guard), or skip an
    empty selection — each would make an unverifiable row read as verified."""
    got = codes(derived(method, inp, 0.0, data=data), "derivations")
    assert got == [(BLOCKER, "CA-DERIV-001")], label


def test_lenient_readings_of_a_where_or_a_lost_file_would_pass_and_must_not():
    """Each case reports the value the lenient reading would compute.

    MUTATION: read `where: []` as no filter (the unfiltered mean, 6.6875,
    would pass), or read a column-form ratio that lost its `file` in the scalar
    form (quantities that happen to share the column names, 3 / 6, would pass)."""
    inp = {"file": F, "x": "mae", "where": []}
    assert codes(derived("mean", inp, 53.5 / 8, data=GRID), "derivations") == [
        (BLOCKER, "CA-DERIV-001")]
    lost = {"a": "x", "b": "truth", "where": clause("split", "test")}
    extra = (q("x", 3.0), q("truth", 6.0))
    assert codes(derived("ratio", lost, 0.5, extra_q=extra), "derivations") == [
        (BLOCKER, "CA-DERIV-001")]
    lost = {"a": {"column": "x"}, "b": "truth"}
    assert codes(derived("ratio", lost, 0.5, extra_q=extra), "derivations") == [
        (BLOCKER, "CA-DERIV-001")]


# ------------------------------------------------- grounding and CA-DERIV-003
def chain(quantities, rows, data=TWO):
    return inc({"quantities": quantities, "derivations": rows}, {"data/d.csv": data})


A_T = {"column": "response", "where": clause("group", "t")}
B_C = {"column": "response", "where": clause("group", "c")}
WELCH_IN = {"file": F, "a": A_T, "b": B_C}
T_TWO = 3 / math.sqrt(2 / 3)                      # welch_t of TWO, treated - control
P_TWO = ai4s.t_pvalue_two_sided(T_TWO, 4.0)


def drow(name, method, inp, tol=1e-9):
    return {"quantity": name, "method": method, "input": inp, "tolerance": {"abs": tol}}


@pytest.mark.parametrize("ground_t,ground_df", [(True, True), (True, False),
                                                (False, True), (False, False)])
def test_a_p_value_is_advisory_exactly_when_t_or_df_is_not_recomputed(ground_t, ground_df):
    """MUTATION: ground a quantity merely because it exists (no advisory ever),
    or demand only one of the operands — the four combinations of a grounded or
    ungrounded t and df each give exactly the advisory they should, naming
    exactly the loose operands, and never block."""
    rows = [drow("p_value", "t_pvalue_two_sided", {"t": "t_statistic", "df": "df"})]
    if ground_t:
        rows.append(drow("t_statistic", "welch_t", WELCH_IN))
    if ground_df:
        rows.append(drow("df", "welch_df", WELCH_IN))
    files = chain([q("t_statistic", T_TWO), q("df", 4.0), q("p_value", P_TWO)], rows)
    got = found(files, "derivations")
    loose = [n for n, ok in (("'t_statistic'", ground_t), ("'df'", ground_df)) if not ok]
    if not loose:
        assert got == []
        return
    assert [(f.severity, f.rule) for f in got] == [(ADVISORY, "CA-DERIV-003")]
    for name in loose:
        assert name in got[0].observation
    for name in ("'t_statistic'", "'df'"):
        if name not in loose:
            assert name not in got[0].observation
    assert "verified against a reported number" in got[0].observation
    assert run_checks(files, ["derivations"]).as_dict()["verdict"] == "PASS"


def test_grounding_follows_chains_and_refuses_cycles_and_uncommitted_roots():
    """MUTATION: ground in a single pass (a chain declared out of order loses
    its tail), ground a cycle, or ground a row whose file is declared
    uncommitted and absent."""
    # mean_t (file) -> half = scale(mean_t, .5) -> r = ratio(half, mean_t): no advisory,
    # whatever order the rows are written in.
    qs = [q("mean_t", 5.0), q("half", 2.5), q("r", 0.5)]
    rows = [drow("r", "ratio", {"a": "half", "b": "mean_t"}),
            drow("half", "scale", {"x": "mean_t", "factor": 0.5}),
            drow("mean_t", "mean", {"file": F, "x": "response",
                                    "where": clause("group", "t")})]
    assert codes(chain(qs, rows), "derivations") == []
    assert codes(chain(qs, list(reversed(rows))), "derivations") == []
    # Without the root row both scalar rows are advisory: the tail inherits it.
    assert codes(chain(qs, rows[:2]), "derivations") == [(ADVISORY, "CA-DERIV-003")] * 2
    # A cycle grounds nothing.
    cyc = [q("u", 2.0), q("w", 4.0)]
    cyc_rows = [drow("u", "scale", {"x": "w", "factor": 0.5}),
                drow("w", "scale", {"x": "u", "factor": 2.0})]
    assert codes(chain(cyc, cyc_rows), "derivations") == [(ADVISORY, "CA-DERIV-003")] * 2
    # An uncommitted, absent root: CA-DERIV-002 for it, CA-DERIV-003 downstream.
    away = [drow("mean_t", "mean", {"file": "data/big.h5", "uncommitted": True,
                                    "x": "response"}),
            drow("half", "scale", {"x": "mean_t", "factor": 0.5})]
    assert codes(chain(qs[:2], away), "derivations") == [
        (ADVISORY, "CA-DERIV-002"), (ADVISORY, "CA-DERIV-003")]


def test_literal_operands_need_no_grounding_and_a_blocked_row_gets_no_advisory():
    """MUTATION: demand grounding for a numeric literal (every `scale` factor
    would be advisory), or add CA-DERIV-003 on top of a CA-DERIV-001."""
    assert codes(derived("t_pvalue_two_sided", {"t": 2.0, "df": 10}, 0.07338803477,
                         tolerance={"abs": 1e-9}), "derivations") == []
    assert codes(derived("scale", {"x": "a", "factor": 2.0}, 99.0, extra_q=(q("a", 1.0),)),
                 "derivations") == [(BLOCKER, "CA-DERIV-001")]


@pytest.mark.parametrize("label,inp,extra_rows,hinted", [
    ("declared over columns (the dogfood's first try)",
     {"file": F, "a": A_T, "b": B_C}, [], True),
    ("t names a quantity no row verifies", {"t": "t_statistic", "df": "df"},
     [drow("df", "welch_df", WELCH_IN)], True),
    ("df names a quantity no row verifies", {"t": "t_statistic", "df": "df"},
     [drow("t_statistic", "welch_t", WELCH_IN)], True),
    ("t is neither a name nor a number", {"t": {"column": "response"}, "df": "df"},
     [drow("df", "welch_df", WELCH_IN)], True),
    ("both grounded, p simply wrong", {"t": "t_statistic", "df": "df"},
     [drow("t_statistic", "welch_t", WELCH_IN), drow("df", "welch_df", WELCH_IN)], False),
    ("literals, p simply wrong", {"t": T_TWO, "df": 4.0}, [], False),
])
def test_the_p_value_block_says_how_to_verify_the_chain(label, inp, extra_rows, hinted):
    """MUTATION: drop `_pvalue_hint`, or attach it whatever the operands — the
    message for a p-value row whose t or df is not recomputed must name welch_t
    and welch_df; a p-value that is simply wrong against recomputed operands must
    not be told to declare rows it already has. (The claim is the message, so
    the message is asserted.)"""
    rows = [drow("p_value", "t_pvalue_two_sided", inp)] + extra_rows
    files = chain([q("t_statistic", T_TWO), q("df", 4.0), q("p_value", P_TWO + 0.01)], rows)
    got = found(files, "derivations")
    p_rows = [f for f in got if "(p_value)" in f.observation]
    assert [(f.severity, f.rule) for f in p_rows] == [(BLOCKER, "CA-DERIV-001")], label
    text = p_rows[0].observation
    assert ("welch_t" in text and "welch_df" in text and "REPORTED" in text) is hinted, text


# ------------------------- input keys: the live-generator experiment's misses
# ~/Claude/crossaudit-dogfood/declarations-experiment/: of 76 generator-written
# declarations 1 verified, and every miss was a shape guess (DESIGN.md §9
# Amendment 3). These pin what the check now says back.
def _obs(files):
    return [(f.severity, f.rule, f.observation) for f in found(files, "derivations")]


@pytest.mark.parametrize("method,inp,expect", [
    ("mae", {"file": F, "x": "truth", "y": "pred"}, "mae takes truth, pred and optional where; got x, y"),
    ("count", {"file": F, "column_name": "id"}, "count takes x and optional where; got column_name"),
    ("last", {"file": F, "x": "truth"}, "last takes y and optional where; got x"),
    ("arrhenius_ea_kj_per_mol", {"file": F, "T": "x", "rate": "truth"},
     "arrhenius_ea_kj_per_mol takes T_K, k and optional where; got T, rate"),
    ("r2", {"file": F, "truth": "truth"}, "r2 takes truth, pred and optional where; got truth (missing pred)"),
    ("t_pvalue_two_sided", {"file": F, "t": 2.0, "df": 10}, "t_pvalue_two_sided takes t, df"),
])
def test_a_guessed_argument_name_is_answered_with_the_names_the_method_takes(method, inp, expect):
    """MUTATION: ignore unknown input keys (the shipped v1 behaviour) or drop the
    key list from the message — a guessed name reads only as "cannot be
    verified", which is what 92 generator rows got back."""
    got = _obs(derived(method, inp, 1.0))
    assert [(s, r) for s, r, _ in got] == [(BLOCKER, "CA-DERIV-001")], got
    assert expect in got[0][2], got[0][2]


def test_a_key_another_method_uses_is_named_as_such():
    """MUTATION: drop the 'argument of' hint — `x` under `mae` should say whose
    argument it is, so the generator can see it picked the wrong row."""
    got = _obs(derived("mae", {"file": F, "x": "truth", "pred": "pred"}, 1.0))
    assert "'x' is an argument of" in got[0][2] and "mean" in got[0][2], got


@pytest.mark.parametrize("key", ["group", "split", "filters", "subset", "select"])
def test_a_bare_filter_key_blocks_and_points_at_where(key):
    """MUTATION: ignore the stray key — the mean then runs over EVERY row and
    the generator is told its value disagrees, when its shape did."""
    got = _obs(derived("mean", {"file": F, "x": "x", key: "test"}, 2.5))
    assert [(s, r) for s, r, _ in got] == [(BLOCKER, "CA-DERIV-001")], key
    assert "where" in got[0][2] and repr(key) in got[0][2], got


@pytest.mark.parametrize("filt,where_rows_mean", [
    ({"split": "test"}, 3.5),
    ({"split": "train"}, 1.5),
    ({"group": "control"}, 2.0),
])
def test_filter_mapping_is_read_as_where_and_reported(filt, where_rows_mean):
    """`filter: {<column>: <value>}` selects exactly the rows `where` would.

    MUTATION: read the alias but select all rows, or accept it silently — the reported mean of the selected rows must verify
    with a CA-DERIV-003 advisory naming the canonical form, and the mean of
    all rows (2.5) must block."""
    inp = {"file": F, "x": "x", "filter": filt}
    got = _obs(derived("mean", inp, where_rows_mean))
    assert [(s, r) for s, r, _ in got] == [(ADVISORY, "CA-DERIV-003")], got
    assert "'where'" in got[0][2] and '"column"' in got[0][2], got
    assert codes(derived("mean", inp, 2.5), "derivations") == [(BLOCKER, "CA-DERIV-001")]
    (col, val), = filt.items()
    plain = {"file": F, "x": "x", "where": clause(col, val)}
    assert codes(derived("mean", plain, where_rows_mean), "derivations") == []


@pytest.mark.parametrize("label,inp", [
    ("filter beside where", {"file": F, "x": "x", "filter": {"split": "test"},
                             "where": clause("split", "test")}),
    ("filter shaped like a where clause", {"file": F, "x": "x",
                                           "filter": {"column": "split", "equals": "test"}}),
    ("empty filter", {"file": F, "x": "x", "filter": {}}),
    ("filter value a float", {"file": F, "x": "x", "filter": {"split": 1.5}}),
    ("filter value a bool", {"file": F, "x": "x", "filter": {"split": True}}),
    ("filter value a list", {"file": F, "x": "x", "filter": {"split": ["test"]}}),
    ("filter a string", {"file": F, "x": "x", "filter": "split=test"}),
    ("filter a list", {"file": F, "x": "x", "filter": [clause("split", "test")]}),
    ("filter names no column", {"file": F, "x": "x", "filter": {"nope": "test"}}),
    ("filter with two columns", {"file": F, "x": "x",
                                 "filter": {"group": "control", "split": "train"}}),
    ("filter on a scalar method", {"t": 2.0, "df": 10, "filter": {"split": "test"}}),
])
def test_an_ambiguous_filter_blocks(label, inp):
    """MUTATION: guess at an ambiguous filter (take where over filter, read a
    where-shaped mapping as a column named 'column', drop an empty one) — the
    alias is read only where it can mean one thing."""
    method = "t_pvalue_two_sided" if "t" in inp else "mean"
    assert codes(derived(method, inp, 3.5), "derivations") == [(BLOCKER, "CA-DERIV-001")], label


def test_an_unknown_key_blocks_even_when_harmless_and_on_an_uncommitted_row():
    """MUTATION: check keys only on committed rows, or only for keys that look
    like filters. A declaration is read exactly or not at all (contract change
    of v2: v1 ignored unknown keys)."""
    assert codes(derived("mean", {"file": F, "x": "x", "note": "hi"}, 2.5),
                 "derivations") == [(BLOCKER, "CA-DERIV-001")]
    away = {"file": "data/big.h5", "uncommitted": True, "x": "x", "filter": {}}
    assert codes(derived("mean", away, 2.5), "derivations") == [(BLOCKER, "CA-DERIV-001")]
    ok = {"file": F, "two_theta_deg": "x", "h": "x", "k": "x", "l": "x", "wavelength": 1.5}
    assert "not among them" not in " ".join(o for *_, o in _obs(derived("bragg_cubic_a", ok, 1.0)))


@pytest.mark.parametrize("bad", ["../data/d.csv", "/abs/data/d.csv", "scripts/../../d.csv"])
def test_a_path_outside_the_experiment_says_what_paths_are_relative_to(bad):
    """MUTATION: drop the base directory from the message — `../data/…`, the
    generators' habit, should be told where paths are rooted."""
    got = _obs(derived("mean", {"file": bad, "x": "x"}, 2.5))
    assert [(s, r) for s, r, _ in got] == [(BLOCKER, "CA-DERIV-001")]
    assert f"relative to {EXP!r}" in got[0][2], got


# --------------------- strict keys in all three places, for every method (Arm C)
SWEEP_DATA = csv(["g", "x", "y", "T_K", "k", "two_theta_deg", "h", "l"], [
    ["a", 1, 2, 300, 0.01, 28.4, 1, 1], ["a", 2, 4, 350, 0.05, 47.3, 2, 0],
    ["b", 4, 7, 400, 0.2, 56.1, 3, 1], ["b", 5, 9, 450, 0.6, 69.1, 4, 0]])


def _valid_input(method):
    """A readable input for every registered method over SWEEP_DATA."""
    kind, keys, _fn = ai4s._METHODS[method]
    if kind == "scalar":
        return {k: 2.0 for k in keys}
    if kind in ("two", "mixed"):
        return {"file": F, keys[0]: {"column": "x", "where": clause("g", "a")},
                keys[1]: {"column": "x", "where": clause("g", "b")}}
    cols = {"x": "x", "y": "y", "truth": "x", "pred": "y", "T_K": "T_K", "k": "k",
            "two_theta_deg": "two_theta_deg", "h": "h", "l": "l"}
    inp = {"file": F, **{k: cols[k] for k in keys}}
    if method == "bragg_cubic_a":
        inp["k"] = "h"
    return inp


def _no_shape_complaint(method, inp):
    obs = " ".join(o for *_, o in _obs(derived(method, inp, 1.0, data=SWEEP_DATA)))
    return "does not take" not in obs and "must be" not in obs and "takes" not in obs


@pytest.mark.parametrize("method", ai4s.METHODS)
@pytest.mark.parametrize("key", ["bogus", "filter", "group", "column", "Where", "x2"])
def test_an_unknown_input_key_blocks_for_every_method(method, key):
    """MUTATION: ignore keys `_allowed_keys` does not list, for any kind — the
    sweep covers every registered method and the keys generators actually
    wrote. The valid input alone draws no shape complaint (so the block below
    is the key's), and the stray key turns it into a CA-DERIV-001 that names
    it — unless it is that method's own alias (`column` for a single-column
    `x`, `filter` read as where in a one-sample or paired form)."""
    inp = _valid_input(method)
    assert _no_shape_complaint(method, inp), method
    kind = ai4s._METHODS[method][0]
    if key in ai4s._allowed_keys(method) or (key == "filter" and kind in ai4s._ALIAS_KINDS):
        return
    bad = {**inp, key: {"g": "a"} if key == "filter" else "x"}
    got = _obs(derived(method, bad, 1.0, data=SWEEP_DATA))
    assert [(s, r) for s, r, _ in got] == [(BLOCKER, "CA-DERIV-001")], (method, key, got)
    assert repr(key) in got[0][2] and f"{method} takes" in got[0][2], got[0][2]


@pytest.mark.parametrize("method", [m for m in ai4s.METHODS
                                    if ai4s._METHODS[m][0] in ("two", "mixed")])
@pytest.mark.parametrize("key", ["filter", "bogus", "equals"])
def test_an_unknown_key_in_a_sample_mapping_blocks(method, key):
    """MUTATION: accept extra keys in an `a`/`b` mapping — `{"column", "filter"}`
    would select every row for that sample."""
    inp = _valid_input(method)
    first = ai4s._METHODS[method][1][0]
    inp[first] = {**inp[first], key: "x"}
    got = _obs(derived(method, inp, 1.0, data=SWEEP_DATA))
    assert [(s, r) for s, r, _ in got] == [(BLOCKER, "CA-DERIV-001")], (method, key)
    assert "cannot be verified" in got[0][2] and repr(first) in got[0][2], got[0][2]


@pytest.mark.parametrize("method", [m for m in ai4s.METHODS
                                    if ai4s._METHODS[m][0] != "scalar"])
@pytest.mark.parametrize("key", ["bogus", "value", "operator"])
def test_an_unknown_key_in_a_where_clause_blocks(method, key):
    """MUTATION: accept a where clause with keys beyond {column, equals} — an
    `operator` the check does not apply would be a filter read as something
    it is not."""
    inp = {**_valid_input(method), "where": {"column": "g", "equals": "a", key: "x"}}
    if ai4s._METHODS[method][0] in ("two", "mixed"):
        inp = {**_valid_input(method), "where": {"column": "x", "equals": "1", key: "x"}}
    assert codes(derived(method, inp, 1.0, data=SWEEP_DATA), "derivations") == [
        (BLOCKER, "CA-DERIV-001")], (method, key)


@pytest.mark.parametrize("method", ["welch_t", "welch_df", "ci95_low", "ci95_high",
                                    "difference", "ratio", "percent_change"])
def test_the_arm_c_shape_is_unverifiable_not_a_value_mismatch(method):
    """The live Arm C row: `filter: {group: control}` as a SIBLING of `a`/`b`.
    v1 ignored it, ran the method over every row and said the value
    disagreed. It must now say the declaration cannot be read, name 'filter'
    and the keys the method takes — and the reported value is set to what the
    every-row computation gives, so a fail-open reading would pass.

    MUTATION: add "two"/"mixed" to `_ALIAS_KINDS` (the filter would be applied
    to both samples) or drop the unknown-key check."""
    keys = ai4s._METHODS[method][1]
    both = {"file": F, keys[0]: "response", keys[1]: "response"}
    every_row = {"file": F, keys[0]: {"column": "response", "where": clause("group", "c")},
                 keys[1]: {"column": "response", "where": clause("group", "c")}}
    arm_c = {**both, "filter": {"group": "c"}}
    fail_open = [f for f in found(derived(method, every_row, 0.0, data=TWO), "derivations")]
    value = 0.0
    for f in fail_open:
        m = re.search(r"gives (\S+),", f.observation)
        if m:
            value = float(m.group(1))
    got = _obs(derived(method, arm_c, value, data=TWO))
    assert [(s, r) for s, r, _ in got] == [(BLOCKER, "CA-DERIV-001")], got
    assert "cannot be verified" in got[0][2] and "'filter'" in got[0][2], got
    assert f"{method} takes {', '.join(keys)} and optional where" in got[0][2], got


# ------------------------------------- the generated table, from registry to prompt
def _table_rows(text):
    rows = {}
    for line in text.splitlines():
        if line.startswith("| `"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows[cells[0].strip("`")] = cells
    return rows


def test_the_method_table_is_the_registry():
    """MUTATION: add a method to `_METHODS` without a meaning, rename an
    argument without the table following, or write a cell holding '|' — the
    table either refuses to render or loses a key here."""
    rows = _table_rows(ai4s.method_table())
    assert list(rows) == list(ai4s.METHODS)
    for m, cells in rows.items():
        assert len(cells) == 4, cells
        named = set(re.findall(r"`([A-Za-z_]+)`", cells[2]))
        want = ai4s._allowed_keys(m) - {"where", "uncommitted"}
        assert named == want, (m, named, want)


def test_the_scaffolded_skill_carries_the_generated_table():
    """MUTATION: ship the template without substituting the placeholder, or a
    hand-written table — the project's skill must hold `method_table()` itself."""
    from crossaudit.scaffold import AI4S_METHOD_TABLE, annotation_skill_tree
    body = annotation_skill_tree(["derivations"])["skills/ai4s-declarations.md"]
    assert AI4S_METHOD_TABLE not in body
    assert ai4s.method_table() in body
    rows = _table_rows(body)
    for m in ai4s.METHODS:
        for k in ai4s._METHODS[m][1]:
            assert f"`{k}`" in rows[m][2], (m, k)


def test_the_generator_prompt_of_a_science_ai4s_project_holds_the_table(tmp_path):
    """The route a generator actually reads: scaffold the project's skills,
    load them, select them against `science-ai4s`, render, and build the
    prompt `cli/build.py` sends (`generator.build_prompt`).

    MUTATION: drop the skill from `ANNOTATION_SKILLS`, gate it on a check
    `science-ai4s` lacks, or stop substituting the table — it is absent here."""
    from crossaudit import generator, skills as skills_mod
    from crossaudit.scaffold import annotation_skill_tree
    checks = resolve("science-ai4s")
    for rel, text in annotation_skill_tree(checks).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    house = skills_mod.load(tmp_path)
    rendered = skills_mod.render(skills_mod.select(house, ["experiments"], checks=checks))
    prompt = generator.build_prompt(task="Compare the two groups.", constitution="# Rules\n",
                                    current={}, skills=rendered)
    assert ai4s.method_table() in prompt
    for m in ai4s.METHODS:
        assert f"| `{m}` |" in prompt, m
    off = skills_mod.render(skills_mod.select(house, ["experiments"], checks=resolve("science")))
    assert ai4s.method_table() not in off


# ------------------------------------------------------------ range units, v2
UNITS_SPELLED = ["kJ/mol", "kJ mol⁻¹", "kJ/mol "]


@pytest.mark.parametrize("declared", UNITS_SPELLED)
@pytest.mark.parametrize("reported", UNITS_SPELLED)
def test_range_units_compare_byte_for_byte_with_no_synonym_table(declared, reported):
    """MUTATION: strip whitespace, or borrow `number_source`'s unit synonym
    table, in `check_range_rules` — the off-diagonal pairs of this 3x3 grid
    then pass. Each spelling passes only against itself."""
    rules = ("```crossaudit-ranges\n" + json.dumps(
        [{"name": "activation_energy", "unit": declared, "min": 0, "max": 500}],
        ensure_ascii=False) + "\n```\n")
    got = codes(ranged(q("activation_energy", 84.2, reported), rules=rules), "range_rules")
    assert got == ([] if declared == reported else [(BLOCKER, "CA-PHYS-001")])


# --------------------------- the skill's two documented behaviours, executed
def _numbers_increment(file_line: str, v: str, quote: str) -> dict[str, bytes]:
    block = json.dumps([{"v": v, "u": "deg", "src": {"file": f"{EXP}/results.txt",
                                                     "quote": quote}}])
    return {f"{EXP}/results.txt": (file_line + "\n").encode(),
            f"{EXP}/SUMMARY.md": (f"The spread is {v} deg.\n\n```crossaudit-numbers\n"
                                  f"{block}\n```\n").encode()}


@pytest.mark.parametrize("file_value", ["0.4", "0.40", "0.400"])
@pytest.mark.parametrize("v", ["0.4", "0.40", "0.400", "4e-1"])
def test_skill_claim_v_is_a_number_and_the_quote_is_characters(file_value, v):
    """Pins what AI4S_DECLARATIONS_SKILL.md tells a generator about trailing
    zeros (gap 5 of the first dogfood audit), by running `number_source`.

    MUTATION (of the skill, not of numbers.py): if the skill's rule were wrong
    in either direction — `v` compared as text, or the quote compared as a
    number — one half of this grid flips. `v` in any spelling matches the file;
    a quote matches only when it is the file's own characters."""
    line = f"sd_sup_10 = {file_value} deg"
    assert codes(_numbers_increment(line, v, line), "number_source") == []
    for quoted in ("0.4", "0.40", "0.400"):
        if quoted == file_value:
            continue
        got = codes(_numbers_increment(line, v, f"sd_sup_10 = {quoted} deg"), "number_source")
        assert got == [(BLOCKER, "CA-NUM-002")], (file_value, v, quoted)


def test_skill_claim_two_revisions_of_one_input_declare_and_verify():
    """Pins the skill's multi-revision example (gap 6) by running the whole
    science-ai4s profile: two revisions of one file under two paths, each
    quantity citing and recomputing from its own, verifies; the revision that
    is not code_version is the CA-DATA-003 advisory and nothing blocks.

    MUTATION: make that CA-DATA-003 a BLOCKER, or resolve a derivation's file
    by basename (both low_label.csv) — the verdict leaves PASS or the second
    mean recomputes from the first file and blocks."""
    old = csv(["variant", "mae"], [["ssl", 4.0], ["ssl", 4.68]])
    new = csv(["variant", "mae"], [["ssl", 3.4], ["ssl", 3.58]])
    results = {
        "quantities": [
            {"name": "mae_ssl_1k", "value": 4.34, "unit": "deg",
             "source": "data/8d43648/low_label.csv@8d43648"},
            {"name": "mae_ssl_5k", "value": 3.49, "unit": "deg",
             "source": "data/e7a316d/low_label.csv@e7a316d"}],
        "derivations": [
            drow("mae_ssl_1k", "mean", {"file": "data/8d43648/low_label.csv", "x": "mae"}, 6e-3),
            drow("mae_ssl_5k", "mean", {"file": "data/e7a316d/low_label.csv", "x": "mae"}, 6e-3)]}
    meta = ("code_version: e7a316d\ninputs:\n  - data/8d43648/low_label.csv@8d43648\n"
            "  - data/e7a316d/low_label.csv@e7a316d\n")
    files = inc(results, {"data/8d43648/low_label.csv": old,
                          "data/e7a316d/low_label.csv": new}, meta=meta)
    result = run_checks(files, resolve("science-ai4s"))
    assert result.as_dict()["verdict"] == "PASS", [f.as_dict() for f in result.findings]
    assert [(f.severity, f.rule) for f in result.findings] == [(ADVISORY, "CA-DATA-003")]
    assert "8d43648" in result.findings[0].observation
    swapped = json.loads(json.dumps(results))
    swapped["derivations"][1]["input"]["file"] = "data/8d43648/low_label.csv"
    files[f"{EXP}/results.json"] = json.dumps(swapped).encode()
    assert (BLOCKER, "CA-DERIV-001") in codes(files, "derivations")


# ======================================================== split_integrity
COMPOUNDS = csv(["id", "system", "y"], [["c1", "A", 1], ["c2", "A", 2], ["c3", "B", 3],
                                       ["c4", "C", 4], ["c5", "C", 5]])


def splits(train, test, **extra):
    doc = {"data": "data/compounds.csv", "id_column": "id", "group_column": "system",
           "train": train, "test": test, **extra}
    return inc({"quantities": []}, {"data/compounds.csv": COMPOUNDS,
                                     "splits.json": json.dumps(doc)})


def test_a_clean_group_split_passes():
    """MUTATION: compare groups across a split with itself — a clean split blocks."""
    assert codes(splits(["c1", "c2", "c3"], ["c4", "c5"]), "split_integrity") == []
    assert codes(splits(["c1", "c2"], ["c4", "c5"], val=["c3"]), "split_integrity") == []


@pytest.mark.parametrize("label,train,test", [
    ("id_overlap", ["c1", "c2", "c4"], ["c4", "c5"]),
    ("group_overlap", ["c1", "c3", "c4"], ["c5"]),
    ("test_id_not_in_data", ["c1", "c2", "c3"], ["c4", "c9"]),
    ("duplicate_test_id", ["c1", "c2", "c3"], ["c4", "c4", "c5"]),
])
def test_each_leakage_variant_blocks(label, train, test):
    """MUTATION: drop any one of the four tests in `_split_findings` — the D12
    variant it guards passes."""
    got = codes(splits(train, test), "split_integrity")
    assert got and set(got) == {(BLOCKER, "CA-ML-001")}, label


def test_group_overlap_is_only_checked_when_a_group_column_is_declared():
    """MUTATION: always read `system` — an id-only split would block on groups
    the project never declared."""
    doc = {"data": "data/compounds.csv", "id_column": "id",
           "train": ["c1", "c3"], "test": ["c2"]}
    files = inc({"quantities": []}, {"data/compounds.csv": COMPOUNDS,
                                     "splits.json": json.dumps(doc)})
    assert codes(files, "split_integrity") == []


@pytest.mark.parametrize("label,doc,data", [
    ("unparseable", "{", COMPOUNDS),
    ("not a mapping", "[]", COMPOUNDS),
    ("no test list", {"data": "data/compounds.csv", "id_column": "id", "train": []}, COMPOUNDS),
    ("ids not a list", {"data": "data/compounds.csv", "id_column": "id",
                        "train": "c1", "test": []}, COMPOUNDS),
    ("data missing", {"data": "data/nope.csv", "id_column": "id",
                      "train": [], "test": []}, COMPOUNDS),
    ("id column missing", {"data": "data/compounds.csv", "id_column": "ID",
                           "train": [], "test": []}, COMPOUNDS),
    ("group column missing", {"data": "data/compounds.csv", "id_column": "id",
                              "group_column": "family", "train": [], "test": []}, COMPOUNDS),
    ("id held twice", {"data": "data/compounds.csv", "id_column": "id",
                       "train": ["c1"], "test": ["c2"]}, COMPOUNDS + "c1,Z,9\n"),
])
def test_a_split_that_cannot_be_read_blocks(label, doc, data):
    """MUTATION: return nothing on an unreadable splits.json or data file."""
    text = doc if isinstance(doc, str) else json.dumps(doc)
    files = inc({"quantities": []}, {"data/compounds.csv": data, "splits.json": text})
    got = codes(files, "split_integrity")
    assert got and set(got) == {(BLOCKER, "CA-ML-001")}, label


def test_no_splits_file_means_nothing():
    """MUTATION: demand a split of every increment."""
    assert codes(inc({"quantities": []}, {"data/compounds.csv": COMPOUNDS}),
                 "split_integrity") == []


# ========================================================= repro_declared
FULL_META = "code_version: v1\ninputs: [data/d.csv@v1]\ncommand: python a.py\n" \
            "environment: python 3.12\nseed: 7\n"


@pytest.mark.parametrize("drop,expected", [
    (None, 0), ("command", 1), ("environment", 1), ("seed", 1)])
def test_repro_reports_each_missing_key_once_and_never_blocks(drop, expected):
    """MUTATION: report one finding for all keys, or make it a BLOCKER — the
    count or the hard-failure assertion reddens."""
    meta = "\n".join(line for line in FULL_META.splitlines()
                     if not (drop and line.startswith(drop)))
    files = inc({"quantities": [], "stochastic": True}, meta=meta)
    result = run_checks(files, ["repro_declared"])
    assert [(f.severity, f.rule) for f in result.findings] == [
        (ADVISORY, "CA-REPRO-001")] * expected
    assert result.hard_failures == 0
    if drop:
        assert drop in result.findings[0].observation


@pytest.mark.parametrize("meta,n", [
    ("code_version: v1\ninputs: []\ncommand: ''\nenvironment: {}\nseed: true\n", 3),
    ("code_version: v1\ninputs: []\ncommand: x\nenvironment: {python: '3.12'}\nseed: '7'\n", 1),
])
def test_repro_rejects_empty_and_mistyped_values(meta, n):
    """MUTATION: test key presence instead of value shape — an empty command,
    an empty mapping, a bool or string seed would pass."""
    files = inc({"quantities": [], "stochastic": True}, meta=meta)
    assert codes(files, "repro_declared") == [(ADVISORY, "CA-REPRO-001")] * n


def test_repro_is_silent_unless_results_are_declared_stochastic():
    """MUTATION: drop the `stochastic is True` gate — a deterministic DFT
    convergence run gets three advisories about a seed it does not have."""
    bare = "code_version: v1\ninputs: []\n"
    for doc in ({"quantities": []}, {"quantities": [], "stochastic": False},
                {"quantities": [], "stochastic": "yes"}):
        assert codes(inc(doc, meta=bare), "repro_declared") == []
    assert codes(inc({"quantities": [], "stochastic": True}), "repro_declared") == [
        (ADVISORY, "CA-REPRO-001")]


# ================================================================= claims
CLAIM_Q = [q("p_value", 0.03), q("p_hi", 0.08), q("ci95_low", -0.2), q("ci95_high", 0.9),
           q("pos_low", 0.1), q("pos_high", 0.4), q("mae_test", 0.12, "eV"),
           q("mae_baseline", 0.2, "eV"), q("alpha", 0.05)]


def claimed(*claims, quantities=CLAIM_Q):
    return inc({"quantities": list(quantities), "claims": list(claims)})


@pytest.mark.parametrize("claim,holds", [
    ({"test": "p_below", "quantity": "p_value", "alpha": 0.05}, True),
    ({"test": "p_below", "quantity": "p_hi", "alpha": 0.05}, False),        # D13 overclaim
    ({"test": "p_below", "quantity": "p_value", "alpha": "alpha"}, True),
    ({"test": "p_below", "quantity": "alpha", "alpha": 0.05}, False),       # p == alpha
    ({"test": "p_at_least", "quantity": "alpha", "alpha": 0.05}, True),
    ({"test": "p_at_least", "quantity": "p_value", "alpha": 0.05}, False),
    ({"test": "ci_excludes_zero", "low": "pos_low", "high": "pos_high"}, True),
    ({"test": "ci_excludes_zero", "low": "ci95_low", "high": "ci95_high"}, False),
    ({"test": "ci_excludes_zero", "low": -0.5, "high": -0.1}, True),
    ({"test": "ci_excludes_zero", "low": 0, "high": 1}, False),              # touches zero
    ({"test": "ci_contains", "low": "ci95_low", "high": "ci95_high", "value": 0}, True),
    ({"test": "ci_contains", "low": "pos_low", "high": "pos_high", "value": 0}, False),
    ({"test": "ci_contains", "low": 0.1, "high": 0.4, "value": 0.4}, True),  # inclusive
    ({"test": "less_than", "quantity": "mae_test", "than": "mae_baseline"}, True),
    ({"test": "less_than", "quantity": "mae_baseline", "than": "mae_test"}, False),
    ({"test": "less_than", "quantity": "mae_test", "than": 0.12}, False),    # strict
    ({"test": "greater_than", "quantity": "mae_baseline", "than": "mae_test"}, True),
    ({"test": "greater_than", "quantity": "mae_test", "than": 0.12}, False),
    ({"test": "within", "quantity": "mae_test", "low": 0.12, "high": 0.2}, True),
    ({"test": "within", "quantity": "mae_test", "low": 0, "high": "mae_test"}, True),
    ({"test": "within", "quantity": "mae_test", "low": 0.13, "high": 1}, False),
])
def test_each_claim_test_true_and_false(claim, holds):
    """MUTATION: flip any comparison in `_TESTS` (strict for inclusive or the
    reverse, `and` for `or` in ci_excludes_zero) — the boundary row of that
    test reddens."""
    got = codes(claimed({"text": "x", **claim}), "claims")
    assert got == ([] if holds else [(BLOCKER, "CA-STAT-004")]), claim


@pytest.mark.parametrize("claim", [
    {"test": "p_below", "quantity": "p_nope", "alpha": 0.05},     # names nothing
    {"test": "p_below", "quantity": "p_value", "alpha": "0.05"},  # a string is a name
    {"test": "p_below", "quantity": "p_value"},                    # missing operand
    {"test": "significant", "quantity": "p_value"},                # unknown test
    {"test": "p_below", "quantity": "p_value", "alpha": True},
    {"test": "p_below", "quantity": "p_value", "alpha": None},
    {"test": "within", "quantity": "mae_test", "low": 1, "high": 0},  # low > high
    {"test": "ci_excludes_zero", "low": 0.5, "high": 0.1},
    "the result is significant",
])
def test_a_claim_that_cannot_be_decided_blocks(claim):
    """MUTATION: skip an undecidable claim — a claim naming a quantity that does
    not exist would pass, which is the generator's cheapest way out."""
    assert codes(claimed(claim), "claims") == [(BLOCKER, "CA-STAT-004")]


def test_claims_absent_or_naming_a_duplicated_or_null_quantity():
    """MUTATION: pick the first of two rows with one name, or read a null value
    as zero."""
    assert codes(inc({"quantities": CLAIM_Q}), "claims") == []
    assert codes(inc({"quantities": CLAIM_Q, "claims": {}}), "claims") == [
        (BLOCKER, "CA-STAT-004")]
    dup = CLAIM_Q + [q("p_value", 0.5)]
    assert codes(claimed({"test": "p_below", "quantity": "p_value", "alpha": 0.05},
                         quantities=dup), "claims") == [(BLOCKER, "CA-STAT-004")]
    null = [q("p_value", None)]
    assert codes(claimed({"test": "p_below", "quantity": "p_value", "alpha": 0.05},
                         quantities=null), "claims") == [(BLOCKER, "CA-STAT-004")]


def test_claims_compare_exact_decimals():
    """MUTATION: compare as floats — 0.05000000000000000001 rounds to the double
    0.05 and a claim of p < alpha with p just above alpha would hold."""
    near = [q("p_value", "0.05000000000000000001")]
    assert codes(claimed({"test": "p_below", "quantity": "p_value", "alpha": 0.05},
                         quantities=near), "claims") == [(BLOCKER, "CA-STAT-004")]


# ============================================================== precision
@pytest.mark.parametrize("places", range(0, 8))
@pytest.mark.parametrize("u,allowed", [(0.03, 3), (0.5, 2), ("0.15", 2), (2, 1), (20, 0),
                                       (0.0004, 5)])
def test_precision_sweep_over_written_decimal_places(places, u, allowed):
    """MUTATION: allow two digits beyond the uncertainty, count significant
    figures instead of decimal places, or read the uncertainty's last digit
    instead of its first — the flip moves off `allowed`."""
    value = f"{84:d}" + ("." + "1" * places if places else "")
    got = codes(inc({"quantities": [q("a", value, uncertainty=u)]}), "precision")
    assert got == ([(ADVISORY, "CA-PREC-001")] if places > allowed else []), (value, u)


def test_precision_reads_floats_via_repr_and_skips_what_it_cannot_judge():
    """MUTATION: report without an uncertainty, on a zero uncertainty, or block."""
    assert codes(inc({"quantities": [q("a", 84.2134, uncertainty=0.5)]}), "precision") == [
        (ADVISORY, "CA-PREC-001")]
    assert codes(inc({"quantities": [q("a", 84.21, uncertainty=0.5)]}), "precision") == []
    for extra in ({}, {"uncertainty": 0}, {"uncertainty": "n/a"}, {"uncertainty": True}):
        assert codes(inc({"quantities": [q("a", 84.2134, **extra)]}), "precision") == []
    assert run_checks(inc({"quantities": [q("a", 84.2134, uncertainty=0.5)]}),
                      ["precision"]).hard_failures == 0


# ======================================================= robustness, registry
@pytest.mark.parametrize("results", [
    {"quantities": "nope", "derivations": [None, 1, "x", {"quantity": 5}],
     "claims": [None, {"test": None}], "stochastic": True},
    {"quantities": [None, 1, {"name": ["x"], "value": {}}, q("a", "1e99999")],
     "derivations": [{"quantity": "a", "method": "mean",
                      "input": {"file": F, "x": "x"}, "tolerance": {"sig": 3}}]},
    {"quantities": [q("a", 1e308)], "derivations": [
        {"quantity": "a", "method": "t_pvalue_two_sided", "input": {"t": 1e308, "df": 1e-300}},
        {"quantity": "a", "method": "scale", "input": {"x": 1e308, "factor": 1e308}}]},
    [1, 2, 3],
])
def test_no_check_raises_on_hostile_shapes(results):
    """MUTATION: remove any isinstance guard — a TypeError escapes `run_checks`
    and the whole audit crashes instead of reporting a finding."""
    files = inc(results, {"data/d.csv": DATA, "splits.json": "[1]"}, rules=RANGES,
                meta="- not a mapping\n")
    run_checks(files, NEW_CHECKS)                  # must not raise


def test_science_ai4s_profile_is_exact_and_science_is_unchanged():
    """MUTATION: edit `science` instead of adding a profile (AGENTS.md §1.2: an
    existing `checks: science` project would change behaviour), or drop or
    reorder a pack check in `science-ai4s`."""
    assert resolve("science") == ["schema", "units", "convergence", "provenance",
                                  "number_source"]
    assert resolve("science-ai4s") == [
        "schema", "units", "convergence", "provenance", "number_source", "complete",
        "numeric_validity", "range_rules", "derivations", "split_integrity", "claims",
        "repro_declared", "precision"]
    assert resolve("science-ai4s")[:5] == resolve("science")
    assert resolve("general") == ["parseable", "declared", "internal", "complete"]
    assert resolve("research") == ["parseable", "declared", "internal", "complete",
                                   "source_provenance"]
    assert resolve("off") == []
    assert sorted(PROFILES) == ["general", "off", "research", "science", "science-ai4s"]
    assert not set(NEW_CHECKS) & set(resolve("science"))


def test_every_new_check_is_registered_with_an_honest_contract():
    """MUTATION: drop a `register` call or the `ai4s` registration import in
    `framework.py` — `available()` loses the name and `run_checks` denies it.
    The blocking checks' contracts must state the honest boundary."""
    names = available()
    for name in NEW_CHECKS:
        assert name in names, name
    live = contracts(NEW_CHECKS)
    for name in ("range_rules", "derivations", "claims"):
        assert "never judges whether a method is appropriate" in live[name], name
    for name in ("repro_declared", "precision"):
        assert "never blocks" in live[name], name


def test_the_skill_ships_with_either_declaration_check_and_not_with_science():
    """MUTATION: register the skill for only one check, or put it in the science
    tree — a `claims`-only project would get no instruction, or every science
    project would be told about blocks nothing reads."""
    from crossaudit import skills as skills_mod
    from crossaudit.scaffold import SCIENCE_CHECKS, annotation_skill_tree

    path = "skills/ai4s-declarations.md"
    assert path not in annotation_skill_tree(SCIENCE_CHECKS)
    for checks in (["derivations"], ["claims"], resolve("science-ai4s")):
        assert path in annotation_skill_tree(checks), checks
    body = annotation_skill_tree(["claims"])[path]
    skill = skills_mod._parse(body, "ai4s-declarations", path)
    assert skill.requires_check == ("derivations", "claims")
    assert [s.name for s in skills_mod.select([skill], ["src"], checks=["claims"])] == [
        "ai4s-declarations"]
    assert skills_mod.select([skill], ["src"], checks=["schema"]) == []
    assert "you name a location, you never say what is at it" in body.lower()
    for method in ai4s.METHODS:
        assert f"{method}" in body, method


# ============================================ the compliant increment: no false blocks
RESULTS_LINE_MAE = '{"name": "mae_test", "value": 0.15, "unit": "eV", ' \
                   '"source": "data/compounds.csv@v1", "uncertainty": 0.05},'


def compliant() -> dict[str, bytes]:
    """A minimal well-formed increment that exercises every pack check."""
    results = "\n".join([
        "{",
        ' "stochastic": true,',
        ' "quantities": [',
        "  " + RESULTS_LINE_MAE,
        '  {"name": "mae_baseline", "value": 0.4, "unit": "eV", "source": "data/compounds.csv@v1"},',
        '  {"name": "n_test", "value": 2, "unit": "1", "source": "data/compounds.csv@v1"},',
        '  {"name": "t_statistic", "value": 2.0, "unit": "1", "source": "data/groups.csv@v1"},',
        '  {"name": "df", "value": 10, "unit": "1", "source": "data/groups.csv@v1"},',
        '  {"name": "p_value", "value": 0.0734, "unit": "1", "source": "data/groups.csv@v1"}',
        " ],",
        ' "convergence": {"converged": true, "achieved": 0.001, "threshold": 0.01},',
        ' "derivations": [',
        '  {"quantity": "mae_test", "method": "mae", "input": {"file": "data/compounds.csv",'
        ' "truth": "truth", "pred": "pred", "where": {"column": "split", "equals": "test"}},'
        ' "tolerance": {"abs": 6e-05}},',
        '  {"quantity": "n_test", "method": "count", "input": {"file": "data/compounds.csv",'
        ' "x": "id", "where": {"column": "split", "equals": "test"}}, "tolerance": {"abs": 0.5}},',
        '  {"quantity": "t_statistic", "method": "welch_t", "input": {"file": "data/groups.csv",'
        ' "a": {"column": "response", "where": {"column": "group", "equals": "a"}},'
        ' "b": {"column": "response", "where": {"column": "group", "equals": "b"}}},'
        ' "tolerance": {"abs": 6e-05}},',
        '  {"quantity": "df", "method": "welch_df", "input": {"file": "data/groups.csv",'
        ' "a": {"column": "response", "where": {"column": "group", "equals": "a"}},'
        ' "b": {"column": "response", "where": {"column": "group", "equals": "b"}}},'
        ' "tolerance": {"abs": 6e-05}},',
        '  {"quantity": "p_value", "method": "t_pvalue_two_sided",'
        ' "input": {"t": "t_statistic", "df": "df"}, "tolerance": {"abs": 6e-05}}',
        " ],",
        ' "claims": [',
        '  {"text": "the model beats the baseline", "test": "less_than",'
        ' "quantity": "mae_test", "than": "mae_baseline"},',
        '  {"text": "not significant at 0.05", "test": "p_at_least",'
        ' "quantity": "p_value", "alpha": 0.05}',
        " ]",
        "}",
    ]) + "\n"
    assert json.loads(results)
    data = csv(["id", "system", "split", "truth", "pred"], [
        ["c1", "A", "train", 1.0, 1.1], ["c2", "A", "train", 1.5, 1.4],
        ["c3", "B", "train", 2.5, 2.6], ["c4", "B", "train", 0.5, 0.7],
        ["c5", "C", "test", 2.0, 2.1], ["c6", "C", "test", 3.0, 2.8]])
    # Two groups of six with equal spread, so Welch df = 2(n-1) = 10 exactly, and
    # a shift of 2.16025 against se = sqrt(7/6) gives t = 2.0000029: the t and
    # df the p-value row reads are themselves recomputed (no CA-DERIV-003).
    groups = csv(["group", "response"],
                 [["b", k] for k in range(6)] + [["a", repr(k + 2.16025)] for k in range(6)])
    split = {"data": "data/compounds.csv", "id_column": "id", "group_column": "system",
             "train": ["c1", "c2", "c3", "c4"], "test": ["c5", "c6"]}
    summary = (
        "The ridge model reaches a test MAE of 0.15 eV on 2 held-out compounds,\n"
        "against a baseline of 0.4 eV.\n\n"
        "```crossaudit-numbers\n"
        + json.dumps([{"v": "0.15", "u": "",
                       "src": {"file": f"{EXP}/results.json",
                               "quote": RESULTS_LINE_MAE}}]) + "\n```\n")
    meta = ("code_version: v1\ninputs:\n  - data/compounds.csv@v1\n  - data/groups.csv@v1\n"
            "command: python scripts/analyse.py\nenvironment: python 3.12, stdlib\n"
            "seed: 20261021\n")
    rules = ("# Constitution\n\nRules for this project.\n\n```crossaudit-ranges\n"
             '[{"name": "mae_*", "unit": "eV", "min": 0, "max": 10},\n'
             ' {"name": "n_*", "unit": "1", "min": 1},\n'
             ' {"name": "p_value", "unit": "1", "min": 0, "max": 1}]\n```\n')
    return {
        "AUDIT_RULES.md": rules.encode(),
        f"{EXP}/metadata.yml": meta.encode(),
        f"{EXP}/results.json": results.encode(),
        f"{EXP}/SUMMARY.md": summary.encode(),
        f"{EXP}/data/compounds.csv": data.encode(),
        f"{EXP}/data/groups.csv": groups.encode(),
        f"{EXP}/splits.json": json.dumps(split).encode(),
    }


def test_the_science_ai4s_profile_passes_a_compliant_increment_with_zero_findings():
    """The pack's proof of no false blocks on a compliant increment.

    MUTATION: any check in the pack that misreads a correct declaration (a
    tolerance read the wrong way round, a where filter not applied, groups
    compared within one split, a bound made exclusive) adds a finding here.
    Determinism: the same bytes give byte-identical results twice."""
    files = compliant()
    result = run_checks(files, resolve("science-ai4s"))
    assert result.findings == [], [f.as_dict() for f in result.findings]
    assert result.as_dict()["verdict"] == "PASS"
    assert result.as_dict() == run_checks(files, resolve("science-ai4s")).as_dict()


def _edit(files, path, old, new):
    out = dict(files)
    text = out[path].decode()
    assert old in text, old
    out[path] = text.replace(old, new, 1).encode()
    return out


R = f"{EXP}/results.json"


@pytest.mark.parametrize("path,old,new,rule", [
    (R, '"value": 0.4,', '"value": NaN,', "CA-NUM-005"),
    (R, '"value": 0.0734', '"value": 1.4', "CA-PHYS-001"),
    (R, '"name": "mae_baseline", "value": 0.4, "unit": "eV"',
     '"name": "mae_baseline", "value": 0.4, "unit": "kJ/mol"', "CA-PHYS-001"),
    (R, '"value": 2, "unit"', '"value": 3, "unit"', "CA-DERIV-001"),
    (R, '"equals": "test"}}, "tolerance": {"abs": 6e-05}',
     '"equals": "train"}}, "tolerance": {"abs": 6e-05}', "CA-DERIV-001"),
    (R, '"value": 0.4,', '"value": 0.1,', "CA-STAT-004"),
    (R, '"test": "p_at_least"', '"test": "p_below"', "CA-STAT-004"),
    (f"{EXP}/splits.json", '"test": ["c5"', '"test": ["c4", "c5"', "CA-ML-001"),
    (f"{EXP}/splits.json", '"test": ["c5"', '"test": ["c9", "c5"', "CA-ML-001"),
])
def test_one_planted_edit_on_the_compliant_increment_blocks_with_the_expected_rule(
        path, old, new, rule):
    """The compliant fixture is not vacuous: each pack check is ENGAGED on it.

    MUTATION: unregister or empty any blocking pack check — its row stays PASS."""
    result = run_checks(_edit(compliant(), path, old, new), resolve("science-ai4s"))
    assert result.as_dict()["verdict"] == "BLOCKED"
    assert rule in {f.rule for f in result.findings if f.severity == BLOCKER}


@pytest.mark.parametrize("path,old,new,rule", [
    (f"{EXP}/metadata.yml", "seed: 20261021\n", "", "CA-REPRO-001"),
    (R, '"name": "mae_baseline", "value": 0.4,',
     '"name": "mae_baseline", "value": 0.4123, "uncertainty": 0.01,', "CA-PREC-001"),
])
def test_the_advisory_checks_are_engaged_on_the_compliant_increment(path, old, new, rule):
    """MUTATION: empty `repro_declared` or `precision` — the advisory never
    appears; make either one a BLOCKER — the verdict leaves PASS."""
    result = run_checks(_edit(compliant(), path, old, new), resolve("science-ai4s"))
    assert result.as_dict()["verdict"] == "PASS", [f.as_dict() for f in result.findings]
    assert [f.rule for f in result.findings] == [rule]
