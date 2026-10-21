---
requires_check: derivations, claims
---

# Declaring what code can recompute

**The one rule: you name a location, you never say what is at it.** You say
which committed file a number was computed from, which columns, and which rows;
code opens the file and does the arithmetic itself. You never assert that a
number is right — the check answers that, and an answer written into the
declaration is a question nobody asked. If you cannot name the file and the
columns exactly, leave the derivation out. A quantity with no derivation is not
checked and never counts against the work; a derivation that names something
that is not there blocks.

## `derivations` in results.json

One row per quantity you can account for from a committed file:

```json
"derivations": [
  {"quantity": "mae_test", "method": "mae",
   "input": {"file": "predictions.csv", "truth": "bandgap_ev", "pred": "pred_ev",
             "where": {"column": "split", "equals": "test"}},
   "tolerance": {"abs": 6e-05}},
  {"quantity": "difference", "method": "difference",
   "input": {"file": "data/measurements.csv",
             "a": {"column": "response", "where": {"column": "group", "equals": "treated"}},
             "b": {"column": "response", "where": {"column": "group", "equals": "control"}}},
   "tolerance": {"abs": 6e-05}},
  {"quantity": "p_value", "method": "t_pvalue_two_sided",
   "input": {"t": "t_statistic", "df": "df"}, "tolerance": {"abs": 6e-05}}
]
```

- `quantity` is the `name` of exactly one row of `quantities`.
- `file` is relative to the directory holding this results.json, and must be
  committed. `where` keeps the rows whose cell equals the string you give.
- The argument keys are fixed per method: `x` (count, mean, sd, sem, min, max,
  sum); `y` (last, last_delta_abs); `a`, `b` (difference, welch_t, welch_df,
  ci95_low, ci95_high — each a column, or `{"column", "where"}`); `truth`,
  `pred` (mae, rmse, r2); `x`, `y` (pearson_r, linfit_slope, linfit_intercept);
  `T_K`, `k` (arrhenius_ea_kj_per_mol, arrhenius_ln_a); `two_theta_deg`, `h`,
  `k`, `l` and optional `wavelength` in Å (bragg_cubic_a). For
  t_pvalue_two_sided (`t`, `df`) and scale (`x`, `factor`) there is no file: a
  string names another quantity, a number is a literal.
- `tolerance` is one of `{"abs": …}`, `{"rel": …}` or `{"sig": n}`; with none
  the check demands agreement to `rel` 1e-9. **If you rounded the value you
  report, declare a tolerance at least as wide as the rounding** — a value
  written to four decimals needs `abs` of at least 5e-05.
- A file you cannot commit: `"uncommitted": true` beside its `file`. It is
  recorded as advisory, never as checked.

## `claims` in results.json

A claim is a comparison code can decide over your own reported numbers:

```json
"claims": [
  {"text": "the difference is significant", "test": "p_below",
   "quantity": "p_value", "alpha": 0.05},
  {"text": "the 95% interval excludes zero", "test": "ci_excludes_zero",
   "low": "ci95_low", "high": "ci95_high"}
]
```

Tests: `p_below` / `p_at_least` (`quantity`, `alpha`), `ci_excludes_zero`
(`low`, `high`), `ci_contains` (`low`, `high`, `value`), `less_than` /
`greater_than` (`quantity`, `than`), `within` (`quantity`, `low`, `high`). A
string is always a quantity name; a number is a literal. Declare a claim only
when your prose makes it — a false one blocks.

## The ranges block

`AUDIT_RULES.md` may carry one ```crossaudit-ranges block listing, per
quantity name or glob, the unit it must carry and the bounds its value must lie
in. Those are the project's rules, not yours: you do not write that block.
Report every quantity in the unit it names (dimensionless is `"1"`).
