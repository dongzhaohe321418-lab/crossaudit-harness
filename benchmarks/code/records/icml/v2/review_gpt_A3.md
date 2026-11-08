**Do not run the test audits yet.** The execution pipeline largely works, but admission and scoring currently undermine the intended interpretation.

Code references below are relative to `benchmarks/code/icml/`; record IDs refer to `benchmarks/code/records/icml/`. I read all 36 dev clauses, inspected specifications and solutions across all 26 distinct dev problems, replayed 163 construction cases and 345 witnesses, and ran 324 visible/hidden-suite checks. These read-only checks used the available Python 3.9 interpreter; the configured Python 3.13 executor was unavailable.

## (a) BLOCKERS

### 1. Admission is accepting specification contradictions and reference implementation quirks as “missing requirements”

**Evidence:** `e1.py:604–655`; the following construction/adjudication records.

The adjudicator repeatedly treats “not distinguished by visible tests” as equivalent to “not determined by the specification”. Those are different conditions.

| Dev problem | Clause intervention | Methods judgement |
|---|---|---|
| HumanEval/124 | Require two-digit month/day and four-digit year | Largely restates the explicit `mm-dd-yyyy` format; weak evidence of genuinely missing information. |
| HumanEval/125 | Collapse whitespace runs and omit empty words | Plausible clarification, although closely targeted to `split(' ')`. |
| HumanEval/151 | Include Boolean values as integers | Defensible clarification of an ambiguous type convention. |
| Mbpp/264 | Specify the early-years dog-age conversion | Defensible addition of an otherwise unstated conversion rule. |
| Mbpp/278 | Return length minus one when no tuple occurs | Codifies the reference’s final loop index; no ordinary counting rationale is supplied. |
| Mbpp/465 | “Empty” means precisely `None` | Defensible clarification; the enumeration of other falsy values supplies considerable diagnostic assistance. |
| Mbpp/597 | Accept ascending and descending sorted inputs | Plausible domain clarification, directly targeting the ascending-only merge. |
| Mbpp/639 | Exclude names containing later uppercase letters | Changes a task that says to remove names **starting** with lowercase letters. |
| Mbpp/735 | Duplicate the digit of a one-bit number | Changes the operation from toggling middle bits to inserting a bit. |
| Mbpp/771 | Require positive even total expression length, including non-brackets | Codifies the reference’s length precheck; `(a)` has balanced brackets regardless of character-count parity. |
| Mbpp/790 | Require odd numbers at odd indices | Changes the stated predicate, which concerns even indices only. |
| Mbpp/800 | Preserve tabs/newlines while removing ordinary spaces | Contradicts “remove all whitespaces”. |

The records themselves expose inconsistent adjudication:

- `gen-claude-haiku45|Mbpp/800` is rejected for contradicting “all whitespaces”; the near-equivalent Terra clause is admitted. See `adjudications.jsonl:79` versus `:140`.
- The Haiku Mbpp/735 clause is rejected because adding a bit contradicts toggling; the Terra version prescribing the same duplication is admitted at `adjudications.jsonl:126`.
- For Haiku Mbpp/790, the admission note explicitly acknowledges that the original task would return `True` for the illustrated cases, then approves a clause requiring `False`.

**Concrete fix:** conduct a consistent, outcome-blind semantic re-adjudication before test audits. Require explicit justification that the original specification permits both behaviours; agreement with visible tests is insufficient. Reject contradictions and unjustified reference quirks consistently across generators.

**Registered quantities:** enforcing the existing novelty/non-contradiction criteria can change the admitted population and therefore H1–H4. Preserve the original admission decisions and document the correction; do not silently replace items.

### 2. The existing placebo does not distinguish missing information from a defect-specific hint

**Evidence:** `e1.py:452–490`, especially the constructor’s access to the faulty programme and first failing input.

This is an identification problem, even for legitimate clauses. The intervention combines:

- additional behavioural information;
- identification of the troublesome input class;
- attention directed towards the relevant branch or predicate.

An irrelevant sentence controls length, not diagnostic relevance. Mbpp/735 is particularly stark: “one binary digit” and “two copies” practically supply `toggle_middle_bits(1) -> 3`. All four clause readings produce that witness. Avoiding numeric literals does not remove the information leak.

**Concrete fix:** before test audits, freeze an additional, length-matched **relevant but non-resolving** control. It should name the same already-admissible input condition without specifying the disputed output, with independent verification that it adds no behavioural requirement. Keep the registered placebo and H1–H4 intact; register the additional contrast separately.

For a stronger construction, author requirements without seeing the target candidate or its failing input, then apply the frozen execution gates. Requirements should express defensible intended behaviour, rather than translate individual reference-code branches into prose.

**Registered quantities:** an extra arm can leave H1–H4 unchanged. Reconstructing clauses changes the intervention and requires a documented amendment. Without either additional evidence or narrower interpretation, the study establishes the effect of **failure-informed specification supplementation**, not specifically the effect of supplying missing information.

### 3. Ground-truth comparison does not implement the benchmark’s semantics

**Evidence:** `e1.py:190–228, 543–548, 779–799`; `benchmarks/code/execute.py:145–173`.

There are two distinct errors.

- **Suite instrumentation overwrites task-specific tolerances.** Both hidden-suite wrappers substitute an assertion call with tolerance `0`. Mbpp/233’s original suite uses `atol=0.0001`; several other problems do likewise.
- **Witness/admission equality uses a different comparator.** `same()` uses `math.isclose(rel_tol=1e-6, abs_tol=1e-6)` and exact tuple order. The benchmark uses different numerical tolerances and, for Mbpp/579, compares sets.

Concrete consequences:

- For Mbpp/233, `0.6283` versus `0.6283185307179586` passes the benchmark tolerance but fails `same()`.
- Mbpp/579 legitimately ignores ordering. The mixed-type witness supplied by Terra—whose candidate raises `TypeError`—is denied verified diagnosis because its expected tuple has a different order from the reference.
- The reference itself produces different tuple orders under different hash seeds. `run_on()` does not fix `PYTHONHASHSEED`; exact tuple matching makes credit partly depend on process-specific ordering.
- `same("1", 1.0)` returns `True`: converting arbitrary operands to floats can credit a string as the expected numerical result.
- Candidate timeouts and other non-`ok` statuses are treated as disagreement, although the registered endpoint specifies differing output or a candidate exception.

**Concrete fix:** preserve the original suite assertion, including its tolerance, when instrumenting it. Use frozen, problem-specific comparison semantics for construction and witness verification. Separate execution failures from behavioural exceptions, reject inappropriate type coercion, and stabilise execution conditions.

**Registered quantities:** this corrects implementation of registered ground truth and can change selection, admission, VD and WD. Re-execute affected samples and invalidate existing witness caches before rescoring. Encouragingly, all 36 dev classifications also held under the original, unmodified hidden suites; the three admitted tolerance-sensitive test items checked did too.

### 4. Construction cases lose input types, and an admitted control demonstrably violates its clause

**Evidence:** `e1.py:463–465, 524–553`; construction records for Mbpp/261, /278, /446 and /579; `gen-gpt-terra|Mbpp/223`.

JSON arrays turn nested tuple arguments into lists. Consequently, five admitted dev items across those four problems were validated using lists where the task specifies tuples. For Mbpp/278, the adjudicator even excuses this by “treating the list arguments as the sequence”. That does not validate the stated input domain.

Separately, every construction case for Terra Mbpp/223 has expected result `False`. Its control rejects **every** length mismatch, so it passes those cases without implementing the clause. For example:

```python
is_majority([1, 1, 1], 4, 1)
# reference: True
# admitted control: False
```

Both auditors independently detect this defect in all four clause-control readings. The four credited witnesses are already in `witnesses.jsonl`.

**Concrete fix:** preserve argument types using safe Python literals or a typed encoding, and validate domain membership independently of whether the reference happens to execute. Construction cases should exercise materially different outcomes of the clause, including both sides of Boolean thresholds. Do not describe the Mbpp/223 detections as false alarms.

**Registered quantities:** stronger admission or removal of that item changes the population and requires documentation. Under the existing registration, H2 remains a flag rate on *test-passing* controls; it is not a measured false-positive rate on known-correct programmes.

### 5. Missing-data handling disagrees with the registration

**Evidence:** `analyse_e1.py:39–68`; preregistration lines 77–81 and 111–113.

`union()` returns `None` if **any** requested reading is absent. Therefore:

- C2/P2 discard an arm with one valid reading;
- O4 discards an arm with three valid readings;
- pooled analysis drops the entire item if either auditor lacks a contrast.

The registration instead specifies unions over valid readings, dropping an auditor’s item when an arm is missing. O2’s exclusion of incomplete subsets is implemented correctly.

**Concrete fix:** implement the registered valid-reading unions, retain the O2 subset rule, and explicitly resolve how pooled auditor averaging works when only one auditor remains. Report omissions and effective reading counts by arm, auditor and contrast.

**Registered quantities:** this changes estimates when failures occur. No dev headline is affected: every scheduled key ultimately has a valid reading. The pooled incomplete-auditor rule needs clarification before test data exist.

### 6. Analysis can silently turn unfinished or stale verification into negative outcomes

**Evidence:** `analyse_e1.py:22–35`; `e1.py:731–737, 802–816`.

A valid audit containing witnesses but lacking a witness record becomes `vd=False, wd=False`. There is no completeness assertion. Witness caching uses only the reading key—not programme, reference, witness or scorer hashes—and permanently treats any existing result as complete, including infrastructure failures.

Thus stopping witness execution early, or fixing the comparator and rerunning, can produce apparently complete results with missing or obsolete scores.

**Concrete fix:** before analysis, reconcile the full schedule, audit attempts and required witness results; distinguish terminal missing readings from unfinished work. Bind cached results to input and scorer hashes, and retry infrastructure failures without converting them to behavioural negatives.

Also freeze a checksummed pre-test bundle. The E1 records are currently untracked, and `audits_raw.jsonl` retains extracted text rather than the Codex event stream returned by `call()`. The stored tool-use Boolean cannot independently establish that tools were absent.

**Registered quantities:** completeness/provenance checks need not change the estimand; correcting stale or missing scores can change reported values.

### 7. Several registered secondary analyses are absent

**Evidence:** `analyse_e1.py:130–166`; preregistration lines 99–106.

The implementation omits:

- H4 by auditor;
- H3 and H4 by generator;
- much of the promised corresponding flag and witnessed-disagreement contrasts.

E2 produces an any-finding flag curve, but verified diagnosis remains restricted to BLOCKER witnesses. Clarify whether that fulfils “the same under the any-finding rule”.

**Concrete fix:** implement the promised secondary output matrix and denominators before freezing the test analysis. This adds registered outputs without changing hypotheses or thresholds.

## (b) Things to disclose

- **Execution checks were reassuring.** All 36 dev defective programmes passed visible tests and failed both original and instrumented hidden suites. All controls and references passed both. All 163 stored construction cases reproduced the execution-admission conditions. This does not establish semantic validity of the clauses.

- **No final differential missingness appeared in dev.**

  | Auditor | Original: first-attempt valid | Placebo | Clause |
  |---|---:|---:|---:|
  | Terra | 287/288 | 144/144 | 144/144 |
  | Sonnet | 288/288 | 144/144 | 144/144 |

  The single failure was tool use on Haiku Mbpp/579, correct programme, original reading 2. Its second attempt succeeded. Final coverage is **1,152/1,152**, with no duplicate valid keys. This supports dev completeness, not a missing-at-random assumption for future failures.

- **Prompt metadata leakage was not found.** All 216 distinct reconstructed prompt hashes matched the records. No item/problem ID or explicit arm/kind label appeared; no prompt exceeded the builder’s bounds. The clause’s diagnostic content remains recognisable.

- **Witness parsing is mostly reliable.** All **345/345 calls parsed**. Two expected-value strings were unparsable—**0.58%**—but were labelled `expected_correct=False`, not `unparseable`. One includes a useful expected number after extra prose; the other proposes an incorrect expected result. Two flagged replies provide no witness. Ten reference-exception witnesses were correctly excluded under the registered operational domain rule.

- **Reference execution is not proof of domain validity.** The verifier also establishes only an input/output discrepancy, not the correctness of the surrounding explanation or identification of the intended defect. Mutable arguments are separately deserialised for each execution; I found no shared-mutation contamination.

- **Primary arithmetic reproduces.** Complete-data unions, six-subset O2 averaging, equal auditor/item weighting, problem-cluster resampling, seeds and primary verdict thresholds match the registration. All 36 admitted dev items enter every primary contrast. The Amendment-1 generated-control sensitivity correctly uses 25 items: H2 is **−10.0 points**, interval **[−26.79, 7.41]**.

- **Bootstrap quantile convention needs naming.** Line 95 selects the 251st and 9,750th sorted draws. The lower endpoint is one rank above the empirical inverse-CDF convention. Adjacent order statistics coincide for all four dev primary contrasts, so this does not explain the results. Specify a convention without choosing it to improve significance.

- **The manipulation check does not establish equivalence.** Dev H4 is **+4.17 points**, interval **[+0.45, +10.29]**. Its failure does not warrant changing the ±5-point margin.

- **Report the complete funnel and control composition.** Selection yielded 150 items; execution construction admitted 143; adjudication admitted 123: **36 dev and 87 test**. Dev contains 15 same-generator, 10 other-generator and 11 reference controls. Flag counts also include non-behavioural findings, such as complaints about the test-file packaging.

## (c) Judgement

The dev run looks like a functioning data-collection instrument: coverage is complete, prompts reproduce, benchmark classifications hold, and the headline calculations are reproducible. It does **not yet look like a valid instrument for attributing the ceiling effect specifically to missing requirements**. Several admitted clauses reveal the failure condition, redefine the task or legitimise reference bugs; inconsistent adjudication permits these interventions through. The 100% clause-union result is therefore unsurprising without being evidence of fabrication or broken arithmetic. Repair semantic admission, benchmark comparison and analysis completeness before test audits; retain the registered hypotheses and thresholds, and obtain additional evidence separating behavioural information from diagnostic prompting.