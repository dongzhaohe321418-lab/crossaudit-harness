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
    or drop the factor in `scale`."""
    t, df = q("t_statistic", 2.0), q("df", 10)
    assert_derivation("t_pvalue_two_sided", {"t": "t_statistic", "df": "df"},
                      0.07338803477, tol=1e-9, extra_q=(t, df))
    assert_derivation("t_pvalue_two_sided", {"t": 2.0, "df": 10}, 0.07338803477, tol=1e-9)
    assert_derivation("scale", {"x": "lattice_a", "factor": 2.5}, 10.0,
                      extra_q=(q("lattice_a", 4.0),))


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
    ("unknown method", "median", {"file": F, "x": "x"}, DATA),
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
        '  {"name": "t_statistic", "value": 2.0, "unit": "1", "source": "data/compounds.csv@v1"},',
        '  {"name": "df", "value": 10, "unit": "1", "source": "data/compounds.csv@v1"},',
        '  {"name": "p_value", "value": 0.0734, "unit": "1", "source": "data/compounds.csv@v1"}',
        " ],",
        ' "convergence": {"converged": true, "achieved": 0.001, "threshold": 0.01},',
        ' "derivations": [',
        '  {"quantity": "mae_test", "method": "mae", "input": {"file": "data/compounds.csv",'
        ' "truth": "truth", "pred": "pred", "where": {"column": "split", "equals": "test"}},'
        ' "tolerance": {"abs": 6e-05}},',
        '  {"quantity": "n_test", "method": "count", "input": {"file": "data/compounds.csv",'
        ' "x": "id", "where": {"column": "split", "equals": "test"}}, "tolerance": {"abs": 0.5}},',
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
    split = {"data": "data/compounds.csv", "id_column": "id", "group_column": "system",
             "train": ["c1", "c2", "c3", "c4"], "test": ["c5", "c6"]}
    summary = (
        "The ridge model reaches a test MAE of 0.15 eV on 2 held-out compounds,\n"
        "against a baseline of 0.4 eV.\n\n"
        "```crossaudit-numbers\n"
        + json.dumps([{"v": "0.15", "u": "",
                       "src": {"file": f"{EXP}/results.json",
                               "quote": RESULTS_LINE_MAE}}]) + "\n```\n")
    meta = ("code_version: v1\ninputs:\n  - data/compounds.csv@v1\n"
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
