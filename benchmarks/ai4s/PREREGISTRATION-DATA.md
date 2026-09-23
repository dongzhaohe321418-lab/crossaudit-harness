# A4S-3 — auditing scientific data

Registered 2026-09-23 **before the items are built and before any model call of this study**.
Amendments are numbered and committed before the step they govern. Programme: `plan/AI4S-PROGRAM.md`.

## Question

Can the auditor that reviews code also review a scientific dataset, and what does it catch that a
simple deterministic validator, written from the dataset's own documentation, does not?

## Substrate

Four physical-science tabular datasets from the UCI repository, each verified on its page as
**CC BY 4.0**: Concrete Compressive Strength (165), Airfoil Self-Noise (291), Combined Cycle
Power Plant (294), Superconductivity (464; the target and 11 named features). Zip SHA-256s are
recorded in `records/ai4s/data_sources.json`.

**Clean pools, fixed now from measured anomalies:** exact duplicate rows are removed (concrete 25,
power plant 41, superconductivity 66); power-plant rows with relative humidity above 100% are
removed (55). No dataset has negative or missing cells. Abalone was considered and excluded: its
UCI page gives millimetres and grams while its values are scaled by 1/200, a real documentation
fault that would make a correct flag on a "clean" copy count as a false positive. Wine Quality
was excluded because its page gives no units.

## Items

Each item is a random sample of **120 rows** from one dataset's clean pool, as `data.csv`, with a
**data card** stating the dataset's name, source, what each column is, its unit where the source
states one, and the source's stated range where it gives one. Nothing on the card mentions faults.

* **Clean items:** 35 per dataset (140), each a fresh row sample.
* **Faulty items:** for each dataset, each of seven fault types, 5 seeds (140), one fault per item,
  applied to a fresh sample:

| code | fault | construction |
|---|---|---|
| F1 | mixed units | one unit-bearing column: a random 20% of its rows converted to another unit of the same quantity (×1000 for kg↔g or m↔mm, ÷1000 for Hz→kHz, +273.15 for °C→K, ×145.04 for MPa→psi, −273.15 for K→°C), column header unchanged |
| F2 | impossible values | 3 rows of one non-negative quantity set to the negative of their value |
| F3 | duplicated rows | 12 rows (10%) replaced by exact copies of other rows in the item |
| F4 | shuffled target | the target column permuted among a random 30% of rows |
| F5 | swapped columns | the values of two numeric columns with different ranges exchanged, headers unchanged |
| F6 | missing-value sentinel | 6 cells (5%) of one column set to −999 |
| F7 | truncated precision | one continuous column rounded to integers where the source reports decimals |

The column, rows and conversion are drawn from seed **20260926** per item and recorded with the
item. Ground truth is the construction.

## Auditors

* **LLM auditor, `cross`** (`openai:gpt-5.6-terra`), through the product's `run_audit` with the
  shipped constitution: task = the data card and the instruction "Audit this dataset for
  correctness before it is used in an analysis"; files = `data/data.csv` and `data/CARD.md`.
  **K = 4** readings per item. Flag = at least one BLOCKER.
* **LLM auditor, `self`** (`claude-haiku-4-5`, through the CLI route of A4S-1 Amendment 1), K = 4,
  secondary.
* **Deterministic validator**, written now from the data card alone and frozen in
  `data_validator.py` before any item is built: declared-range check (source ranges where
  stated; non-negativity for every mass, concentration, length, frequency, pressure and absolute
  temperature), exact-duplicate check, sentinel check (any value in {−999, −9999, 9999}), and
  integer-valued check on columns the card declares continuous. It flags an item if any check fires.

## Outcomes

Primary: `cross` union recall at K = 4 on faulty items, by fault type and overall, and union false
positives on clean items, with dataset-clustered and item-level intervals (bootstrap over items
within dataset, 10,000, seed 20260926; four clusters are too few for a cluster bootstrap and the
report says so). Secondary: the same for `self`; the validator's recall and false positives; the
union of LLM and validator; **what only the LLM catches** (faulty items the validator misses and
the LLM flags) by fault type; and **localisation**, whether a flagging finding names the faulted
column, checked by string match on the column's name.

## Expectations stated now

The validator should catch F2, F3, F6 by construction and F7 where declared, and miss F1 (within
range after conversion is possible), F4 and F5 unless ranges separate them. The LLM's value, if
any, is on F1, F4 and F5. That is the comparison the study exists for; no directional hypothesis
about the LLM is registered.

What no reading licenses: a claim about scientific data in general (four tabular datasets, seven
synthetic fault types); calling an LLM flag on a clean item wrong without reading it (a clean
sample can still contain natural oddities the pool filter did not remove).

## Budget and review

Model halt **$45** cumulative across both LLM families, read from the ledgers, failing closed. The
report goes to cross-vendor review and enters the paper only when quotable.

## Amendment 1 — two instrument defects found on a three-item pilot (2026-09-23)

A pilot of three clean concrete items (one `cross` reading each, $0.08) was run to check that the
files reach the auditor. It found two defects in the instrument, not in the data:

* **The card and the CSV named the target column differently.** The UCI header ends in a trailing
  space; the card printed it stripped. Every reading flagged the mismatch, correctly. Column names
  are now stripped of surrounding whitespace in the CSV too, so card and data agree.
* **The task framing did not fit the product.** CrossAudit audits a deliverable against a task;
  "Audit this dataset for correctness" was read as a task the increment failed to perform ("no
  audit result is supplied"). The task now reads: "Deliver a dataset ready for use in a scientific
  analysis: data/data.csv, documented by the data card data/CARD.md, which states what each column
  is and its unit." The data is the deliverable, which is what an auditor of scientific data is
  asked to judge.

The three pilot readings are discarded and archived separately; items are rebuilt with the fixed
names (same seeds, same faults). Known when written: three clean items, all flagged for the name
mismatch; no faulty item had been read.

## Amendment 2 — the files sat outside the audited scope (2026-09-23)

Found after 280 `cross` readings at draw 1 and 33 at draw 2 ($6.6 on the ledger), while writing
the analysis: every reading's verdict was ESCALATE, flagged or not. The project's audited scope is
`work/`, and the items were placed at `data/data.csv` and `data/CARD.md`. The product counts a
scope as started only when a file lies at least two levels below the scope root (or a
`results.json`/`metadata.yml` exists), so these increments were ruled *not started*. The
deterministic tier's result, which is rendered into the auditor's prompt, therefore read
`"verdict": "NOTHING_TO_AUDIT", "scope_started": false` on every item, and the verdict ladder
escalated as for an empty increment. The auditor still received both files and returned findings,
but it read them under a framing that A4S-1's layout (`work/solution/solution.py`) never produces
and a shipped data project would not produce either.

Fix: the files are placed at `work/data/data.csv` and `work/data/CARD.md`, and the task names those
paths ("Deliver a dataset ready for use in a scientific analysis: work/data/data.csv, documented by
the data card work/data/CARD.md, which states what each column is and its unit."). Items, seeds,
faults, K, the flag rule and the budget are unchanged. All 313 readings are void for every
registered outcome and archived as `runs/data_audit_void_scope/`; their spend counts toward the $45
halt.

Known when written: draw-1 flag counts by fault type and on clean items had been looked at (a
progress tally, not an analysis). The fix is determined by the product's scope rule alone and
would be the same whatever those counts were. The void run is not reported as a comparison.

## Amendment 3 — the halt is raised to $60 (2026-09-24)

At $20.04 cumulative (cross draw 1 complete, draw 2 at 25 of 280; self draw 2 in progress), the
projected total for the registered design is about $44, against the $45 halt. The margin was
consumed by the voided run of Amendment 2 ($6.6), which the halt counts by design. The halt is
raised to **$60** so that the registered design can complete; nothing else changes. The reason is
cost alone. Known when written: progress tallies only; no outcome has been computed on any valid
reading, and the analysis script (`analyze_data.py`) was committed before any valid reading
existed.

## Erratum to Amendments 1 and 3 and to the registration (2026-09-24, after the first review)

The first cross-vendor review (`codex-review-a4s3`, report archived there) checked the history
against the commit times and ledgers. Three statements above are wrong, and are corrected here
rather than edited in place:

* **Amendment 1** was committed together with the rebuilt manifest (`64fd36d`), so it did not
  precede the rebuild it governs. It did precede every model call after the pilot.
* **Amendment 3** says `self` was on draw 2; it was on draw 3. It says no outcome had been computed;
  the agent states that, and no record can verify it.
* **The analysis script** (`abd2c9b`, 23:45:32) was committed after 278 valid `self` readings
  existed, not before any valid reading existed, as Amendment 3 and the first report said. The agent
  states it had not analysed them; the records cannot verify that.
* **The registration's pool counts**: the superconductivity pool is deduplicated after selecting its
  12 columns, which removes 84 rows, not the 66 full-row duplicates stated. The concrete source
  README gives Age a range of 1 to 365 days, which the frozen spec omits; the validator therefore
  does not use every range the documentation states.
* **The halt** is not strictly fail-closed: a draw's readings are queued at once, so a halt check
  waits for queued readings, and an unpriced ledger event is tolerated if others are priced. No cap
  was reached.
