# Study 17 — recognising a wrong generated test without the canonical solution: results

Preregistration `testgen/PREREGISTRATION-VAL.md` (97470e1, 22:42 +08:00), Amendment 1
(6bf5dbc, 22:43, one secondary count), Amendment 2 (92522e4, 22:51, the spend cap raised to
the authorised $8 while draw 2 was in flight and before draw 3 started); the driver and its
tests were committed (c5f172c, 22:46:23) before the first call: the ledger's first
completion is stamped 22:46:38.694 with a 3,969 ms duration, so its request began at
about 22:46:34.7, eleven seconds after the commit.
Records: `records/testgen-val/{rows.jsonl, suites-d2.json, suites-d3.json, identity.json,
ledger.json, manifest.json, numbers.json}` — counts, hashes and per-test indices, no test
text. The generated text is in the run archive (`~/Documents/Crossaudit/study-data/
wt-testval-runs/`, `MANIFEST.sha256`), as study 16's is. Harness `testgen_val.py`; rule
tests `tests/test_testgen_val.py`. Report: `testgen_val.py report`; the exploratory lines
in §3 come from `testgen/exploratory_val.py` and are labelled. **Every table below is
generated, not typed**: `testgen_val.py report` renders them from `numbers.json` and
`exploratory.json` into `records/testgen-val/tables.md`, and `testgen/splice_tables.py`
splices that file between the markers in this document; the tests compare both directions
byte for byte (studies 18 and the ceiling study use the same pattern).

## 1. The preregistered decision

Two further draws of the generator for all 222 problems (same prompt — every one of the
444 per-problem prompt hashes equals draw 1's — same model, the adapters' default
sampling), executed against every candidate; draw 1 is study 16's suite, frozen. The rules
decide, for each draw-1 test that FAILS on a candidate, whether to keep it, from the other
draws' outcomes on that candidate and nothing else (§3 of the preregistration). Of the
1,545 test applications, 107 fail on a clean, classifiable candidate: 18 wrong (the test
also fails on the canonical solution), 89 right.

<!-- BEGIN TABLE primary (records/testgen-val/tables.md) -->
| rule | wrong among kept failing applications | Wilson 95% | problem-cluster bootstrap | retained of the 7 | verdict |
|---|---|---|---|---|---|
| A — majority over draws (draw 2 AND draw 3 also fail on the candidate) | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5 of 7 | **KILL** (wrong rate) |
| B — any-draw agreement (draw 2 OR draw 3 also fails) | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6 of 7 | **KILL** (wrong rate) |
| C′ — within-draw corroboration (another draw-1 test also fails; no new call) | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5 of 7 | **KILL** (wrong rate) |
<!-- END TABLE primary -->

The intervals are for the binomial proportion of kept failing applications; Wilson
treats applications as independent, the bootstrap resamples whole problems (seed
20260915, 10,000 resamples), which is the unit that repeats. **The best-performing rule by
the preregistered order is A** (lowest point estimate among rules retaining ≥ 5 of 7);
it is killed by the wrong-test criterion, and so **H17 is KILLED**: neither paid rule
reaches the preregistered validation threshold on this substrate. No rule is near the 2%
line — the lower bootstrap bound of the best rule is 3.6%. Against the free comparator,
A keeps exactly C′'s 86 applications plus four correct ones, all on F-stratum candidates
(both candidates of `HumanEval/65` and of `HumanEval/93`), with identical wrong-test
removal (7 of 18) and identical retention (5 of 7); B keeps more of both classes. Whether
the extra draws improve on the free comparator is not a question this study can settle —
the difference is four correct applications on candidates that fail the visible suite —
and no claim either way is made.

What each rule did to the two classes, with both intervals (Wilson; bootstrap):

* Right failing applications retained (of 89): A 79 = 88.8% (80.5–93.8; 77.8–96.8);
  B 86 = 96.6% (90.6–98.8; 90.3–100.0); C′ 75 = 84.3% (75.3–90.4; 70.7–93.9).
* Wrong failing applications removed (of 18): A 7 = 38.9% (20.3–61.4; 14.3–71.4);
  B 3 = 16.7% (5.8–39.2; 0.0–40.0); C′ 7 = 38.9% (the same interval as A).
* Retention: A and C′ keep a correct failing test on `b1:Mbpp/261`, `b1:Mbpp/297`,
  `b1:Mbpp/589`, `b1:Mbpp/594`, `b2:Mbpp/594` and drop `b1:HumanEval/154` (draw 2 has
  one failing test on that candidate, draw 3 none) and `b2:Mbpp/559` (neither replicate
  draw has a failing test on it: the defect draw 1 found, the other two draws did not
  reach). B keeps six, dropping only `b2:Mbpp/559`.

## 2. Secondaries, as preregistered

* **The brief's unique-test quantity** (§5; a draw-1 test is kept if the rule keeps it on
  any candidate, or it passes on every candidate). Over the 1,188 classifiable tests: A
  keeps 1,176 of which 39 are wrong = 3.3% (Wilson 2.4–4.5%; bootstrap 2.1–4.6%); B 1,183,
  42 wrong = 3.6% (2.6–4.8%; 2.3–4.9%); C′ 1,174, 39 wrong = 3.3% (2.4–4.5%; 2.1–4.7%). The
  floor the preregistration stated — 29 of the 45 wrong tests never fail on any candidate
  and cannot be reached by any rule of this kind, 29/1,188 = 2.4% — is most of every
  rule's figure. At the exposed-test level (the 80 draw-1 tests that fail on at least one
  clean candidate; Amendment 1): A 10 wrong of 68 kept = 14.7% (8.2–25.0%; 4.4–27.6%); B
  13 of 75 = 17.3% (10.4–27.4%; 7.2–29.9%); C′ 10 of 66 = 15.2% (8.4–25.7%; 4.5–28.8%).
  At that level, correct exposed tests retained (of 64): A 58 = 90.6% (Wilson 81.0–95.6%;
  bootstrap 81.1–97.2%); B 62 = 96.9% (89.3–99.1%; 91.2–100.0%); C′ 56 = 87.5% (77.2–
  93.5%; 76.4–95.1%). Wrong exposed tests removed (of 16): A 6 = 37.5% (18.5–61.4%;
  13.6–69.2%); B 3 = 18.8% (6.6–43.0%; 0.0–42.9%); C′ 6 = 37.5% (the same interval as A).
* **The arm each rule implies**, confirm half (flag = a kept failing draw-1 test, or a
  draw-1 timeout), reported and not decided on:

<!-- BEGIN TABLE arm (records/testgen-val/tables.md) -->
| arm | confirm P-recall | Wilson | bootstrap | confirm C-FP | Wilson | bootstrap |
|---|---|---|---|---|---|---|
| `testgen-A` (= `testgen-C′` on P and C) | 8/55 = 14.5% | 7.6–26.2% | 3.8–26.3% | 1/74 = 1.4% | 0.2–7.3% | 0.0–4.1% |
| `testgen-B` | 12/55 = 21.8% | 12.9–34.4% | 9.3–35.7% | 2/74 = 2.7% | 0.7–9.3% | 0.0–6.8% |
| `hc ∪ testgen-A` | 16/55 = 29.1% | 18.8–42.1% | 16.7–42.0% | 6/74 = 8.1% | 3.8–16.6% | 2.7–14.9% |
| `hc ∪ testgen-B` | 18/55 = 32.7% | 21.8–45.9% | 19.3–46.7% | 6/74 = 8.1% | 3.8–16.6% | 2.7–14.9% |
<!-- END TABLE arm -->

  For reference (study 16, frozen): `hc` 11/55 at 5/74; `testgen` 13/55 at 3/74;
  the oracle bound `hc ∪ testgen-validated` 18/55 at 5/74. Rule B's union reaches the
  oracle bound's recall count with one more false positive than `hc` alone — 6 of 74,
  which is two over the objective's 4 and one over the kill bar's 5 — because of
  `b2:HumanEval/157`, a correct candidate that all three draws fail with a wrong test.
  Rule A's union keeps 16 at the same 6. Explore half, reported once and carrying no
  claim: `testgen-A` 4/55 P, 2/76 C; `testgen-B` 8/55, 3/76; `hc ∪ testgen-A` 7/55 at
  2/76; `hc ∪ testgen-B` 10/55 at 3/76. F stratum (confirm, 15): A 13, B 13, C′ 11.
* **Draws 2 and 3 scored against the canonical solution** — the replicate study 16 §4
  said a second draw would be. Draw 2: 1,247 tests (mean 5.6 per problem, min 0, max 11,
  one suite empty, none uncompilable), **57 wrong = 4.6%** (Wilson 3.5–5.9%; bootstrap
  3.2–6.2%), 37 problems with a wrong test. Draw 3: 1,234 tests (mean 5.6, max 10, one
  empty, none uncompilable), **54 wrong = 4.4%** (3.4–5.7%; 3.0–5.9%), 37 problems.
  Study 16's draw 1 was 45 of 1,188 = 3.8% (2.8–5.0%; 2.5–5.2%); the three draws' intervals
  overlap. No canonical run timed out in draws 2 or 3 (draw 1's `Mbpp/160` did); each
  draw had 2 candidate timeouts and 2 pre-collector deaths, the same four instances as
  draw 1.
* **Wrong tests recur across draws, by problem.** Of the 32 problems with a wrong
  draw-1 test, 23 also have a wrong draw-2 test (71.9%, Wilson 54.6–84.4%), 26 a wrong
  draw-3 test (81.3%, 64.7–91.1%), 27 one in either. The marginal draw-2 prevalence is 37
  of 222 = 16.7% (12.3–22.1%), draw 3's the same count. The matched comparison, on the
  221 problems classifiable in draw 1: draw 2 is wrong on 23 of the 32 with a wrong
  draw-1 test against 13 of the 189 without (6.9%, 4.1–11.4%); draw 3 on 26 of 32 against
  10 of 189 (5.3%, 2.9–9.5%). `Mbpp/160` — unknown in draw 1, wrong in both new draws —
  is the difference between the marginal 37 of 222 and the cohort's 36 of 221 (16.3%,
  12.0–21.7%). 52 problems have a wrong test in at least one of the three draws. This is
  consistent with the failure mode the preregistration's §1 named — the misreading is
  the model's, not the draw's — but recurrence by problem does not distinguish the same
  misreading repeated from different errors on problems that are hard or ambiguous; the
  records hold indices, not assertions, and that distinction was not preregistered.
* **Draw-to-draw identity.** 13 of 222 draw-2 responses and 8 of 222 draw-3 responses are
  byte-identical to draw 1's (under the 50% degeneracy stop). At the test level, 486 of
  1,247 draw-2 tests (39.0%, Wilson 36.3–41.7%; problem-cluster bootstrap 35.1–43.0%)
  and 478 of 1,234 draw-3 tests (38.7%, 36.1–41.5%; 35.1–42.3%) are AST-identical to a
  draw-1 test of the same problem.
* **Cost, from the project's usage ledger** (`records/testgen-val/ledger.json`, read from
  the run's `.crossaudit/usage.jsonl`): `testgen-val-d2` 222 calls, $1.6635 (124,814 in /
  90,100 out tokens); `testgen-val-d3` 222 calls, $1.6858 (122,648 / 91,909); **$3.3493 in
  total**, against the $3.6 estimate, the $8 authorisation and Amendment 2's cap. The
  adapters' per-call sums in `suites-d2.json` / `suites-d3.json` are the same figures
  (same source). One draw-3 call (`HumanEval/76`) failed on the first pass — the provider
  returned malformed JSON. The driver waited 75 s before its second pass, in which the
  call succeeded in 31.8 s (completion stamped 23:13:50.834); the failed attempt is not
  metered. Amortised over the 290 instances the two extra draws are
  $0.0115 per instance, about twice study 16's `testgen` ($0.0061) — and they bought no
  usable validation.

## 3. Exploratory, post hoc, not preregistered (`testgen/exploratory_val.py`)

Every figure in this section was computed after the result was seen; the intervals are
the study's own (Wilson; problem-cluster percentile bootstrap, seed 20260915, 10,000
resamples), recomputed here and written to `records/testgen-val/exploratory.json`.

**Where the kept wrong applications sit** (a kept failing draw-1 application whose test
also fails the canonical solution):

<!-- BEGIN TABLE where (records/testgen-val/tables.md) -->
| rule | kept wrong applications | on instances | by half-stratum |
|---|---|---|---|
| A | 11 | 7 | confirm-C 2, confirm-F 4, explore-C 4, explore-F 1 |
| B | 15 | 11 | confirm-C 3, confirm-F 4, confirm-P 2, explore-C 5, explore-F 1 |
| C′ | 11 | 7 | confirm-C 2, confirm-F 4, explore-C 4, explore-F 1 |
<!-- END TABLE where -->

B's four additions over A are confirm-C 1, confirm-P 2 and explore-C 1, which reconcile
11 with 15.

**On P and C rows only** — the candidates the product meets. On an F candidate, which
fails the visible suite, corroboration is trivial: broken code fails correct tests too.

<!-- BEGIN TABLE pc (records/testgen-val/tables.md) -->
| rule | wrong among kept, P and C rows only | Wilson | problem-cluster bootstrap |
|---|---|---|---|
| A | 6/33 = 18.2% | 8.6–34.4% | 0.0–44.8% |
| B | 10/43 = 23.3% | 13.2–37.7% | 6.8–47.1% |
| C′ | 6/33 = 18.2% | 8.6–34.4% | 0.0–44.8% |
<!-- END TABLE pc -->

C′'s row is A's row in every column: on P and C candidates the two rules keep the same
applications. The rules are no better where it matters, and at this n the cluster
intervals are wide enough to include rates far above these and, for A and C′, zero.

**Corroborated ONLY by tests that themselves fail the canonical solution** — every
failing draw-2 and draw-3 test on that candidate is wrong — among each rule's kept wrong
applications:

<!-- BEGIN TABLE corroboration (records/testgen-val/tables.md) -->
| rule | corroborated only by canonical-failing tests | Wilson | problem-cluster bootstrap |
|---|---|---|---|
| A | 5/11 = 45.5% | 21.3–72.0% | 0.0–84.6% |
| B | 9/15 = 60.0% | 35.7–80.2% | 23.5–89.5% |
<!-- END TABLE corroboration -->

C′ consults no other draw, so the quantity is not defined for it. What these two rows
establish is corroboration by canonical-failing tests, and no more: they do not identify
the cause, and they do not separate a misreading the model repeats from a specification
the canonical solution itself reads differently — the same qualification §2 makes of the
recurrence figures. The records hold indices, not assertions, and neither reading was
preregistered.
* Study 16's three confirm-C false positives: `b1:Mbpp/781` is dropped by every rule,
  `b1:Mbpp/16` by A and C′ but not B, `b2:HumanEval/157` by none.

## 4. What the preregistration said would follow, and what follows

§7's second branch: H17 fails on the wrong-test rate. Draws agree on wrong tests as they
agree on right ones — more, by problem — so corroboration across draws, as preregistered
here, does not reach the validation threshold, and the seven-instance recall the
oracle-validated union gained stays a research result. The next question, if it is asked, is a different signal: the
model shown ONE test against the specification (the draft's H17c), or a test-level
contradiction with the visible suite; either is a separate preregistration. The design
note study 16 §7 promised for the test-generating auditor is not written from this
study: what this study adds to it is that the wrong-test rate replicates (3.8%, 4.6%,
4.4%) and is a property of the model on this corpus, not of a draw.

## 5. Deviations and disclosed limits

A note on this file's history, recorded at the reviewer's request and carrying no claim
about the result: **every figure here has reproduced unchanged since review round 1**.
Rounds 2 and 3 corrected statements the numbers did not support; rounds 3 to 8 concerned
the medium rather than the measurement — whether this document could be edited to mislead
a reader while its records stayed honest.

* **Primary redefined before the run, stated in the preregistration §4.** The brief
  defined (i) over the 1,188 unique tests; the frozen record shows 29 of the 45 wrong
  tests never fail on any candidate, so that quantity has a 2.4% floor above the 2% kill
  for every rule of this kind. The primary is over the 107 failing applications, where
  the rules act; the brief's quantity is §2's first secondary.
* **Rule C as briefed was dropped as vacuous** (preregistration §3: every P and C
  candidate passes the visible suite, so the rule keeps no failing test). That argument
  holds on P and C candidates only: 58 of the 107 failing applications are on F-stratum
  candidates, which fail the visible suite, and there rule C would keep the failing
  test. The retention criterion is over P instances, so C's retention would still be 0 of
  7 and it would be killed regardless; the vacuity claim is narrowed in Amendment 3. C′,
  the zero-cost comparator, was preregistered in its place with its already-computable
  baseline (86 kept, 11 wrong, 5 of 7) stated, not predicted.
* **Amendment 1** corrected one secondary count (exposed tests 80, not 89) before any
  call. **Amendment 2** raised the spend cap from $5 to the owner-authorised $8 during
  draw 2 (73 of 222 calls landed, $0.0079 per call) and before draw 3 started; the cap
  never bound — the invocation ran with its original `--budget-usd 5` argument and
  finished at $3.35 without halting, so no relaunch was needed.
* **§3 is post hoc.** The P-and-C-only reading and the "corroborated only by wrong
  tests" count were computed after the result was seen; they explain the kill and
  cannot rescue or sharpen it.
* One model (the shipped cross-vendor route), one temperature (the adapters' default),
  one corpus; the correlation finding licenses a statement about this model on this
  corpus only.
* Draw 1 is frozen from study 16 and was not re-executed; draws 2 and 3 were executed
  fresh with the same executor on the same solutions (their inputs' hashes equal the
  study-16 archive's, `records/testgen-val/manifest.json`). The four artefact instances
  recur in every draw, which says they are the candidates', not the tests'.
* **The retention count is tiny**: 5 of 7 against 6 of 7 is one instance, and the
  seven were chosen by study 16's result; the kill did not turn on retention.
* The kill's 2% line allows one wrong application kept at n ≤ 99 and two at n = 100–107
  (2 of 101 is 1.98%); the preregistration's "at most one" was wrong for the top of the
  range and is corrected in Amendment 3. Every rule substantially exceeds its allowance —
  A keeps 11 wrong against an allowance of 1 at n = 90, C′ 11 against 1 at n = 86, B 15
  against 2 at n = 101, i.e. 11.0, 11.0 and 7.5 times — so the verdict does not depend on
  which of the two allowances applies.
* The rules are suite-level (does another draw also fail on this candidate), as
  preregistered; a test-level match (the same assertion in another draw — 39% of the
  new draws' tests are AST-identical to a draw-1 test) was not preregistered and is not
  evaluated here.
* The suite of this study and study 16's (`test_testgen_val.py`, `test_testgen.py`,
  `test_architectures.py`) is green on the run host: 46 tests at this commit, 38 at the
  round-3 one. The independent reviewer could run 35 of those 38 — three need a writable
  temporary directory for the executor's subprocess and were skipped in that environment
  — so full-suite green is certified on the run host and on hosts that allow it, not
  everywhere.
* `tests/test_testgen_val.py::test_the_rules_never_see_the_canonical_solution` checks that
  the string "canonical" is absent from `keep`'s source — a blacklist, not behavioural
  proof that a rule cannot reach the oracle. What holds behaviourally is narrower:
  `keep` takes the three failure-index sets and nothing else, and the rule tests
  exercise it on synthetic sets alone.
* **The records are authoritative; this rendered Markdown is a convenience.** Round 9
  refused quotation because the previous wording here — introduced by round 8's own repair —
  said the tests prove a chain beginning with `numbers.json` and `exploratory.json`
  reconstructing from the archived run. **They do not.** `tests/test_testgen_val.py` never
  invokes `testgen_val.py report` or `testgen/exploratory_val.py` and never compares a
  reconstructed record; the reviewer demonstrated this by emptying `rows.jsonl` and by
  setting A's retained numerator to `999`, under each of which **all 43 runnable tests still
  passed**. What is true is two separate things, and they carry different weight. *Independent
  replay* — the reviewer's, and round 3's before it — reproduced the records byte for byte from
  the archive. *The automated tests* compare the generated tables against `tables.md` and check
  selected prose strings; they do not test reconstruction at all. A reader who wants the figures
  should read the records, which the harness writes, and may treat the Markdown as a
  presentation of them.
* **The document checks raise the cost of a misleading edit; they do not close the
  class.** Nine structural checks hold this file to a registered skeleton — no
  table-like construct outside the generated blocks, blocks unique and in registered
  order under registered headings after registered anchors, no marker in a fence or a
  blockquote, no HTML comment that is not a marker, no raw HTML, registered headings,
  bounded fences — and the round-7 commit records forty-six mutations they reject. Round
  8 then found twelve more that leave every generated block byte-identical and still
  change what renders: a heading neutralised by fencing it, headings indented one to
  three spaces or written in setext form (underlined rather than hashed) so the
  registered-heading check does not see them, and further fence tricks such as a fence
  line carrying trailing text. Those categories remain open, and on round 8's
  recommendation — which I share — the hardening stops here rather than growing a tenth
  check: the Markdown is not the artefact the study rests on. Credit for finding them is
  round 8's.
* The checks have a price, paid here rather than hidden: this file cannot quote a pipe
  character, write raw HTML or open an HTML comment in its prose, and the wording of
  these bullets was changed twice when the checks caught the sentences describing them.
  The prose figures — the verdicts, the draw wrong-test counts, the ledger totals, §3's
  statements about the record — are bound to `numbers.json` and `exploratory.json` as
  strings; every other figure in this file is checked by the reader.
