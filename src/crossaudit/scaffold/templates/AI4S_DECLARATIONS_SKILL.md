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

## Where things go

One experiment is one directory. results.json sits beside metadata.yml, never
under `scripts/`, and every path you write inside results.json is relative to
that directory — `data/runs.csv`, never `../data/runs.csv` or an absolute path:

```
experiments/2026-10-21-glucose/
  metadata.yml        code_version, inputs, command, environment, seed
  results.json        quantities, derivations, claims
  results.txt         one "name = value unit" line per quantity
  SUMMARY.md          the prose, ending in its crossaudit-numbers block
  data/measurements.csv
  scripts/analyse.py
```

metadata.yml lists each input as ONE string, `path@revision` — not a mapping
with `path` and `revision` keys, which the schema check refuses:

```yaml
code_version: a1b2c3d
inputs:
  - data/measurements.csv@a1b2c3d
  - scripts/analyse.py@a1b2c3d
command: "python3 scripts/analyse.py --seed 17"
environment: "CPython 3.12, standard library only"
seed: 17
```

Each quantity's `source` is one of those strings, exactly:

```json
"quantities": [
  {"name": "mean_control", "value": 5.731, "unit": "mmol/L",
   "source": "data/measurements.csv@a1b2c3d"}
]
```

The SUMMARY's ```crossaudit-numbers block is a JSON LIST of `{v, u, src}`
rows, not prose or YAML lines; its contract is the provenance-numbers skill,
which this project also loads.

## `derivations` in results.json

One row per quantity you can account for from a committed file. Copy this
shape; change only the names:

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
  committed. `where` — exactly that key, holding `{"column": …, "equals": …}`
  — keeps the rows whose cell equals the value you give. (In a one-sample or paired method, `filter:
  {"group": "control"}` — one column, one value — is read as `where:
  {"column": "group", "equals": "control"}` and reported as an advisory naming
  the canonical form. Any other spelling of a filter, and a `filter` beside
  `a`/`b`, blocks: an ignored filter would compute over every row. In a
  two-sample method each sample's rows go in its own `{"column", "where"}`.) To
  select on several columns, give a list of clauses; a row is kept only when
  every clause holds — no need to pre-join a `variant_frac` column:
  `"where": [{"column": "variant", "equals": "ssl"}, {"column": "label_frac", "equals": "0.1"}]`.
  Cells compare as strings, exactly as the CSV writes them (`0.1` is not `0.10`).
- The input keys are fixed per method, and a key the method does not take
  blocks with a message naming the ones it does. The table below is generated
  from the check's own registry, so these are exactly the names it reads:

{{AI4S_METHOD_TABLE}}

- **sd or sd_population — say which one you computed.** `sd` and `sem` divide
  by n − 1 (the sample statistic). `sd_population` and `sem_population` divide
  by n, which is what `numpy.std(x)` returns unless you pass `ddof=1`. At three
  seeds the two differ by 22%, at two seeds by 41%; declaring the wrong one
  blocks, and declaring the right one is how a ± written with numpy's default
  stays honest.
- `ratio` (`a`, `b`: a / b) and `percent_change` (`new`, `old`:
  100 · (new − old) / |old|, so a decrease is negative) take either form. With
  a `file`, each operand is a column (or `{"column", "where"}`) and the means of
  the selected rows are used: the "+40% improvement" over per-seed MAEs is
  `{"file": "data/runs.csv", "new": {"column": "mae", "where": …ssl…}, "old":
  {"column": "mae", "where": …supervised…}}`. Without a `file`, each operand
  is a quantity name or a number: `{"new": "mae_ssl", "old": "mae_sup"}`. A
  zero divisor blocks.
- **A p-value chain.** t_pvalue_two_sided reads `t` and `df` as REPORTED
  values. Declare the t statistic (`welch_t`) and the degrees of freedom
  (`welch_df`) over the committed file as rows of their own, as in the example
  above; otherwise the p-value is checked only against your reported t, and the
  check says so with the advisory CA-DERIV-003. The same holds for every row
  that reads another quantity (scale, and ratio or percent_change without a
  file): its arithmetic is verified, its inputs only if they have rows too.
- `tolerance` is one of `{"abs": …}`, `{"rel": …}` or `{"sig": n}`; with none
  the check demands agreement to `rel` 1e-9. **If you rounded the value you
  report, declare a tolerance at least as wide as the rounding** — a value
  written to four decimals needs `abs` of at least 5e-05.
- A file you cannot commit: `"uncommitted": true` beside its `file`. It is
  recorded as advisory, never as checked.

## Quoting results.txt in the SUMMARY's numbers block

The `crossaudit-numbers` rows compare two things differently, and a generator
that writes both from the same float trips on the difference:

- `v` is compared as a NUMBER. Trailing zeros are not significant there, so
  `"v": "1.50"` matches a file that says `1.5`, and `"v": "1.5"` matches `1.50`.
- `quote` is compared as CHARACTERS (runs of whitespace folded, nothing else).
  It must be copied out of the file exactly as the file writes it. If
  results.txt was written with Python's `repr`, `str` or `json.dumps`, the
  float 0.40 is written `0.4`, and the quote must say `sd = 0.4 deg` — a quote
  of `sd = 0.40 deg` is not in the file and blocks (CA-NUM-002), whatever `v`
  says.

So: write results.txt first, then copy each quote from it byte for byte, and
write `v` however your prose writes the number. If the prose must show trailing
zeros (`0.40 ± 0.05`), either keep them in the file too (format with
`"%.2f"`, or store the value as the string `"0.40"` in results.json — a numeric
string is a number to every check, and `precision` reads strings as written but
floats through `repr`, where trailing zeros are invisible), or quote the
file's `0.4` and transcribe `"v": "0.40"`.

## Inputs from more than one revision

When the numbers in one increment come from different commits (an ablation run
at one revision, the main table at another), declare each input as
`path@revision` in metadata.yml `inputs`, give every quantity the `source` of
the input it came from, and point its derivation's `file` at the bytes of that
revision. One path holds one set of bytes, so two versions of the same file
need two paths:

```yaml
code_version: c2b68ce
inputs:
  - data/multiseed.csv@c2b68ce
  - data/8d43648/low_label.csv@8d43648    # the 1,000-structure run the table quotes
  - data/e7a316d/low_label.csv@e7a316d    # the 5,000-structure rerun, reported beside it
```

```json
{"name": "mae_ssl_lowlabel_10pct", "value": 4.34, "unit": "deg",
 "source": "data/8d43648/low_label.csv@8d43648"}
```

A source whose revision differs from `code_version` is reported as the advisory
CA-DATA-003. That advisory is the record that the increment mixes revisions; it
never blocks, and it is expected here — say in the SUMMARY which table comes
from which run. Two limits: the revision is a label the check compares as text,
not a commit it can open (nothing verifies that the bytes at that path came from
that revision), and a quantity cannot cite two revisions at once — a number
computed from both runs needs both files and a derivation over each.

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
in. Those are the project's rules, not yours: you do not write that block. It
looks like this, so you can read it (first matching entry wins):

```crossaudit-ranges
[{"name": "mean_*", "unit": "mmol/L", "min": 0, "max": 50},
 {"name": "p_value", "unit": "1", "min": 0, "max": 1}]
```

Report every quantity in the unit it names (dimensionless is `"1"`), spelled
byte for byte as the block spells it: no synonym table, no case folding, no
trimming — `kJ/mol`, `kJ mol⁻¹` and `kJ/mol ` with a trailing space are three
different units there, and the wrong one blocks.
