# A4S-1 and A4S-1b — auditing scientific code: results

Registrations: `PREREGISTRATION-CODE.md` (A4S-1, with Amendment 1) and `PREREGISTRATION-CODE-B.md`
(A4S-1b, registered after A4S-1's outcomes were computed and before any A4S-1b call). Analyses,
committed before the data they analyse were complete: `analyze_code.py` →
`records/ai4s/code_results.json` (A); `analyze_code_b.py` → `records/ai4s/code_results_b.json` (B and
the paired change). Residual: `residual_sheet.py` → `records/ai4s/residual_results.json`,
`residual_b_results.json`. Post hoc descriptions, labelled so wherever used: `posthoc_code.py` →
`records/ai4s/code_posthoc_a.json`, `code_posthoc_b.json`. Readings:
`~/Documents/Crossaudit/ai4s/runs/audit/` (A) and `runs/audit_b/` (B), 8 draws × 231 instances × 2
families each, every reading `ok`. Spend (ledgers, list-price equivalent for the CLI route): A $25.56
against its $90 halt (cross $16.52, self $9.04); B $21.80 against its $40 halt (cross $12.84, self
$8.95).
Generation (1,014 step samples) cost $10.04 more, summed from its records. Both runners share the non-strict halt disclosed in A4S-3's erratum.

## What was measured

SciCode (Apache-2.0): the frozen generator of Acts 2–3 (`claude-haiku-4-5`) wrote every step three
times in the benchmark's protocol, each sample building on its own earlier steps. An instance (sample,
step) is **correct** if it passes the scientists' tests for the step and **defective** if it fails or
times out; a step enters only if some sample passes it, so these are defects on steps this
generator sometimes solves (184 of 336 evaluated steps had no passing sample and were excluded). 81 defective instances (30 problems) and 150
correct ones (53 problems, drawn at seed 20260925 from 374) were audited. SciCode has no
visible/hidden split, and the auditor saw no tests. Each instance was read 8 times by the shipped
cross-vendor auditor (`cross`, `gpt-5.6-terra`) and 8 times by the generator's own model (`self`,
through the Claude Code CLI with default sampling), through the product's `run_audit`. Flag = any
model BLOCKER; union over readings.

The program each auditor sees holds the sample's functions for steps 1..k, and the tests check only
step k. 51 of the 81 defective instances and 49 of the 150 correct ones have a failing earlier step
in their chain (post hoc description).

**Two arms differ only in the task text.** In A (registered) the task opened with the whole
problem's main description, then the step, background, header and dependencies. In B the task names
the step's function as the deliverable and gives the main description last, "for context only"; the
program bytes are identical: every reading in both arms records the SHA-256 of the program it was
given, and for each of the 231 instances the hashes agree across arms. (A check was run before B's
calls; its output was not retained, so the hash agreement is the evidence.)

## Table 1 — union flag rates (registered outcomes)

Problem-cluster percentile bootstrap, 10,000 resamples (seed 20260925 for A, 20260930 for B).

| family | arm | defective, K=1 | defective, K=8 | correct, K=1 | correct, K=8 |
|---|---|---|---|---|---|
| `cross` | A | 74.5% [61.2, 86.0] | **87.7%** [72.7, 98.6] | 53.6% [41.6, 64.7] | **68.7%** [56.6, 79.7] |
| `cross` | B | 61.7% [47.9, 75.9] | **72.8%** [59.3, 87.3] | 19.8% [12.9, 27.2] | **36.0%** [26.4, 45.6] |
| `self` | A | 29.3% [18.8, 41.5] | 40.7% [28.9, 54.1] | 21.6% [14.4, 29.5] | 27.3% [18.4, 37.3] |
| `self` | B | 21.0% [10.8, 32.9] | 25.9% [14.7, 38.5] | 12.9% [7.3, 19.6] | 18.0% [11.5, 25.6] |

Pooled two-family union (16 readings): A 91.4% [78.8, 100.0] at 72.0% [60.4, 82.4] on correct code;
B 76.5% [62.8, 90.0] at 46.0% [35.8, 56.4]. Flattening statistic (K = 7 → 8 gain on defective
instances): `cross` A 0.00 points (the curve reaches 87.65% at K = 7), B 0.62 [0.15, 1.22]; `self` A
0.77 [0.18, 1.43], B 0.15 [0.00, 0.54].

## The registered contrasts

**H1 (descriptive).** `cross` union recall at K = 8 on SciCode is 87.7% (A) against 30.0% on
EvalPlus in Act 2, but at 68.7% flags on correct code against 16.0%, with no tests shown here where
EvalPlus showed a visible suite. The two are estimates on two substrates with different designs; no
test of their difference is made, and a recall figure here is not comparable without its
false-positive rate.

**H3 (self − cross at K = 8, defective).** A: −46.9 points [−63.0, −30.7] (3 instances flagged only
by `self`, 41 only by `cross`; exact McNemar p = 1.6 × 10⁻⁹; cluster sign-flip p = 2.6 × 10⁻⁵).
B: −46.9 [−61.5, −34.4], from different flag sets that happen to give the same discordant counts
(3 and 41; McNemar p = 1.6 × 10⁻⁹; sign-flip p = 5.0 × 10⁻⁶, sampled). Beside it, the K = 1 mean
difference: A −45.2 [−58.5, −32.4], B −40.7 [−54.5, −28.5]. The `self` family flags less of both
strata in both arms; as in Act 2, the two routes are not sampled alike and differ in route, so the
contrast is between routes, not a measure of self-preference.

**B1 (directional, A4S-1b): supported.** The `cross` flag rate on correct instances falls from 103
of 150 (A) to 54 (B): **−32.7 points [−42.8, −22.4]** (53 instances flagged only in A, 4 only in B;
exact McNemar p = 5.9 × 10⁻¹²; cluster sign-flip p = 5.0 × 10⁻⁶, sampled). Recall also falls: 71 →
59 of 81, **−14.8 [−28.6, −2.7]** (13 against 1; McNemar p = 0.0018; cluster sign-flip p = 0.0625,
with 7 non-zero clusters). For `self`: correct −9.3 [−16.8, −2.2], defective −14.8 [−26.4, −4.3].

**H2 (residual): killed by its registered rule, in both arms.** The residual (defective instances
no reading of either family flagged) was rated on a blind sheet by L1 (the agent that ran the study,
which wrote the rubric and knows the hypotheses; its labels were hashed and time-stamped before L2
ran) and by `gpt-5.6-luna`, which audits nothing here.

| arm | residual | consensus undetermined | disputed | share [cluster CI] | κ | H2 rule |
|---|---|---|---|---|---|---|
| A | 7 instances, 2 problems | 4 | 3 | 57.1% [0.0, 80.0] | −0.24 | killed (lower bound < 50%) |
| B (secondary) | 19 instances, 8 problems | 13 | 3 | 68.4% [28.6, 93.5] | 0.59 | killed (lower bound < 50%) |

Both point estimates are below EvalPlus's 77.2%. The residuals are too small, and in A too clustered,
for the rule's interval to exceed 50%. What the undetermined items involve, on reading: some an unstated convention the tests
fix (the logarithm's base in an entropy, the direction of a minimum-image vector, the origin of a
periodic box, the axis order and spacing of a k-space grid, which qubit of a pair a channel acts on);
others a conflict between the step's text and its tests (a header that promises a 2-D output where
the test expects a vector; a function documented for a vector and tested on higher-rank arrays), or
the units of supplied quantities where the output unit is stated.

## What the auditor objected to on correct code (post hoc)

A pattern count (post hoc; `posthoc_code.py`) matches, in arm A, at least one BLOCKER on 69 of the
103 flagged correct instances (the only kind on 16), and in arm B on 6 of 54 (never alone). The
pattern was written to catch findings that the increment does not implement the whole multi-step
problem (e.g. "implements only `f_V` … no RPA calculation", which is accurate for A), but it also
matches ordinary step-level objections: on reading, none of B's 6 matches makes that demand (they
concern a changed recurrence, the sign of an acceleration, a detection threshold, mass factors, and
a docstring promising a term the code omits), and A's matches include step-level complaints too. The
counts are regex matches, not validated counts of whole-problem objections. Correct instances with no
recorded earlier-step failure are flagged at rates similar to those with one (A 70/101 and 33/49; B
37/101 and 17/49), so flags on correct code remain common without earlier-step failures; this does
not show that earlier-step defects explain none of them.

A seeded sample (seed 20260929) of 20 flagged correct instances with clean chains in arm B, the first
BLOCKER of the first flagged reading of each, read: 6 cite a deviation from an explicit requirement in the step's text (a mass term
omitted from the stated equation of motion; the speed of light taken as 299 792 458 m/s where the
text fixes 3 × 10⁸; a Lennard-Jones potential that is truncated but not shifted as specified; a 2 × 2
array where the text asks for a tuple), 7 a docstring that contradicts its own code (a matrix
documented as floats and built complex), 4 an edge case or dtype (a zero initial residual giving
0/0; a one-point grid; integer output where floats are documented), and 3 an algorithmic claim.
Four of the seven documentation findings concern
earlier steps' functions, which B's task excluded from the deliverable. We did not check these
findings against the tests. Independent review checked four of the requirement findings and found
different situations. In `39.1.s3` and `15.1.s3` the step's prose and its function header disagree,
and the tests follow the header. In `60.2.s1` the prose says "truncated and shifted" while its
displayed formula is unshifted, and the unshifted code passes. In `21.2.s1` the test targets are 0,
0 and 4.4 × 10⁻²⁷, so under the default tolerance a constant zero would pass. As for C16, a flag on
test-passing code is not shown to be wrong or right here.

## Reading

1. **In these SciCode runs, the auditor's flag rate moved substantially with the task framing.**
   Changing only the task text, with the same programs, reduced the `cross` auditor's flags on
   correct code from 68.7% to 36.0% (a 47.6% relative reduction) and its recall from 87.7% to 72.8%.
   The change is the whole reframing (the step named as deliverable, the problem description moved
   last and marked as context, earlier functions exempted), not any one of its parts, and the arms
   were run in sequence, not in randomised order. It shows that a recall figure for an auditor on
   multi-step code depends on a design choice that A's registration did not vary; it does not measure
   how much framing matters in general.
2. **With the step as the deliverable, discrimination is modest.** 72.8% of defective and 36.0% of
   correct instances are flagged at K = 8; at K = 1, 61.7% and 19.8%. What the flags on correct code
   raise, on reading a sample, ranges from divergences between the code and the step's text or its
   own documentation to contradictions within the benchmark's own instructions and tests too weak to
   distinguish outputs; we did not establish which flags point at defects.
3. **The residual is small, and most of it was rated undetermined.** At K = 8 across both families,
   7 (A) or 19 (B) defective instances were never flagged, and most received consensus-undetermined
   labels, but the registered bar for "more than EvalPlus" is not met in either arm. The rubric asks
   whether the prose settles the expected value, not why the program failed or why the auditor
   missed it, so these labels do not explain the misses. The sheets show only the step's function
   (not helpers the test calls, such as `u_triple` in the orientation-matrix items) and truncate long
   expected arrays. Six item bodies appear on both sheets: L1 gave the same label to all six, L2
   changed three.

## What this does not license

A claim about scientific code in general (one benchmark, one generator, steps that build on the
generator's own earlier steps); calling any flag on a correct instance a mistake or a catch; a
comparison of the two families as vendors (routes and sampling differ); reading B as "the" result
and A as an error (both are registered designs, and the difference between them is the finding).

## Deviations

* A4S-1 Amendment 1: the Anthropic route runs through the Claude Code CLI (API credit exhausted);
  about 400 tokens of fixed context, default sampling.
* The OpenAI account ran out of credit during the programme; the `cross` runs of this study started
  after it was restored and lost no reading.
* One arm-A `self` row has `ok = true` with verdict ESCALATE and no flag; `ok` records a completed
  call, not necessarily a binary model verdict.
* The registered analysis's cluster sign-flip test falls back to sampling above 22 non-zero clusters,
  with the ceiling module's fixed seed (20260915), not this study's.
* A4S-1's framing defect was found only after its registered outcomes were computed; A4S-1b was
  registered in response, with that knowledge stated in its registration.
