# Study 17 — recognising a wrong generated test without the canonical solution

Preregistered on `study/testgen-val` **before any model call** and before `testgen_val.py`
existed, at the commit that adds this file. Binding: study 16's preregistration
(`testgen/PREREGISTRATION.md`, with Amendment 1) and its quotable results
(`RESULTS-TESTGEN.md`), whose records are the frozen inputs here; `architectures.py`'s
information boundary (prompts take plain strings; the hidden suite is unreachable by
construction); `EXPERIMENT_RECORD.md` §9–§10. Owner-authorised spend: up to $8 on the
shipped cross-vendor auditor route.

## 0. What study 16 left, in numbers that are frozen and already known

Study 16 generated one test suite per problem (222 problems, 290 candidate instances) and
found that **every** false positive of the test-generating auditor was a test that also
fails on the canonical solution — a wrong test. With wrong tests removed by the canonical
solution (an oracle the product lacks), the union with the shipped reading auditor
reached 18/55 P at `hc`'s own 5/74 C on the confirm half; without it, the union crossed
the false-positive bar. The question this study asks is whether a wrong test can be
recognised from signals the product HAS: the candidate, the specification, the visible
suite, and further independent draws of the generator.

The frozen record (`records/testgen/rows.jsonl`, `suites.json`; the test text in the
archive `~/Documents/Crossaudit/study-data/wt-testgen-runs/`) says, and this section is
computed from it before any new call:

* 1,199 draw-1 tests; 1,188 are classifiable (the canonical run of one 11-test suite,
  `Mbpp/160`, timed out); **45 are wrong** (fail on the canonical solution), 1,143 right.
* Across the 290 instance rows there are 1,545 test applications (a suite is applied to
  every candidate of its problem). Four rows are execution artefacts — two candidate
  timeouts and two candidates that die before the collector — in which every test is
  recorded as failed without any test having been evaluated. Excluding those four and the
  unclassifiable problem, **107 applications fail on their candidate: 18 wrong, 89
  right.** The other 1,428 applications pass.
* **29 of the 45 wrong tests pass on every candidate they were applied to** (52 of the
  70 wrong-test applications pass). A rule that judges a test by executing it against
  the candidate has no signal on a test that passes; it can act only on the 16 wrong
  tests (18 applications) that fail somewhere.
* The seven `validated-only` confirm-half P instances — flagged by a correct failing test
  and not by `hc` — are `b1:HumanEval/154`, `b1:Mbpp/261`, `b1:Mbpp/297`, `b1:Mbpp/589`,
  `b1:Mbpp/594`, `b2:Mbpp/559`, `b2:Mbpp/594`. Their correct failing draw-1 tests number
  1, 2, 3, 2, 2, 1, 2 respectively; `b2:Mbpp/559` also has one wrong failing test.

## 1. Hypothesis, in a form that can come out false

**H17.** Independent generation draws for the same problem disagree on the wrong tests
more than on the right ones, so that a rule which keeps a failing draw-1 test only when
further draws corroborate the failure removes the wrong tests and keeps the correct
ones. It comes out false if the best preregistered rule leaves more than 2% wrong tests
among the failing tests it keeps, or keeps a correct failing test on fewer than 5 of the
7 `validated-only` instances (§4).

Why it might be true: a wrong test encodes one draw's misreading of an edge the
specification is silent on; a second draw, reading the same specification, may
misread a different edge or none. Why it might be false: the misreading may be the
model's, not the draw's — the same edge read the same wrong way every time — and then
draws agree on the wrong tests exactly as they agree on the right ones.

## 2. What is generated: two further draws, same prompt, same model

Two further independent generations per problem, all 222 problems, with the prompt
builder `architectures.testgen_prompt` unchanged (the per-problem `prompt_sha256` of each
new draw must equal draw 1's, and is recorded), the model `explore.ROUTES["cross"]`
(`openai:gpt-5.6-terra`, the adapters' default sampling, exactly as study 16), parsed and
compiled with `parse_tests` and `compilable` unchanged. Draw 2 is cached in the run
directory as `generated_tests-d2.json`, draw 3 as `generated_tests-d3.json`; the text
stays in the archive (`~/Documents/Crossaudit/study-data/wt-testval-runs/`, with
`MANIFEST.sha256`), never in the repository. Draw 1 is study 16's suite, frozen: its
tests, its per-candidate outcomes and its wrong/right labels are read from the study-16
records and archive and are **not re-executed**.

Each new draw's suite is executed against every candidate instance of its problem
(`testgen.run_generated`, `execute.py` unchanged: subprocess, 30 s wall clock, fresh cwd)
and — for scoring only — against the canonical solution. Study 16's conventions hold: a
candidate run that times out or dies before the collector counts every test of that draw
as failed on that candidate; a canonical run that times out makes that draw's tests
unclassifiable for that problem.

**Degeneracy stop.** Draw 2 is generated first. If more than half of the 222 draw-2
responses are byte-identical to draw 1's (`response_sha256`), the draws are not
independent samples and rules A and B cannot be evaluated: draw 3 is not generated, and
the study reports the identity count and stops. Otherwise draw 3 follows.

## 3. The rules — each applied to draw 1's tests, with no access to the canonical solution

Notation: for a candidate instance *i* of problem *p*, `F1(i)` is the set of draw-1
tests that fail on *i* (from the frozen row), `F2(i)` and `F3(i)` the sets of draw-2
and draw-3 tests that fail on *i*. A rule decides, for each **failing** application
(*t*, *i*) with *t* ∈ `F1(i)`, whether to KEEP or DROP the test on that candidate. A
draw-1 test that passes on the candidate is kept by every rule without a decision: it
flags nothing, and a rule that judges a test by its outcome on the candidate has no
signal on it (§0). "Kept tests" throughout means kept failing applications.

* **Rule A — majority over draws.** Keep (*t*, *i*) iff `F2(i)` is non-empty AND `F3(i)`
  is non-empty: the failure on *i* is matched by at least one failing test in EACH of the
  two other draws. (Draw 1's own failure makes the majority: three draws, all three
  failing on *i*.) An empty draw-2 or draw-3 suite has no failing test and does not match.
* **Rule B — any-draw agreement.** Keep (*t*, *i*) iff `F2(i)` is non-empty OR `F3(i)` is
  non-empty.
* **Rule C as briefed is vacuous and is dropped.** "Keep a draw-1 test only if its
  outcome on the candidate agrees with the visible suite's verdict on the candidate":
  every P and C candidate passes the visible suite by construction of the strata, so the
  visible verdict is "pass" on every candidate the primary is measured on, a failing test
  never agrees with it, and the rule keeps no failing test — 0% wrong among kept tests
  and 0 of 7 retained, before any draw is made. The visible suite carries no information
  about the candidate that the strata have not already used. What it could carry is
  information about the *test* (a generated assertion that contradicts a visible
  assertion on the same input is wrong), but the generator is shown the visible suite
  and told not to repeat it, and no such contradiction exists in the frozen draw-1
  suite to act on; the rule is not preregistered.
* **Rule C′ — within-draw corroboration, the zero-cost comparator.** Keep (*t*, *i*) iff
  |`F1(i)`| ≥ 2: at least one OTHER draw-1 test also fails on *i*. This rule needs no
  further draw and is computable from the frozen record now: it keeps 86 failing
  applications of which **11 are wrong (12.8%)** and retains 5 of the 7 instances. It is
  preregistered as the bar the paid rules must beat, with its value stated so that it is
  a baseline and not a prediction; it is killed already by the wrong-test criterion.

Rules A and B are suite-level: they ask whether an independent suite ALSO finds fault
with this candidate, not whether it contains the same assertion. That is deliberate — a
test-level match would require deciding when two assertions are "the same", which is
either brittle (string equality) or needs a model — and it is the mechanism §1 names.

## 4. Primary outcome, and the kill, written before the run

For each rule, and for the best-performing rule as defined below:

* **(i) The wrong-test rate among kept tests**: of the failing draw-1 applications the
  rule keeps (over all 290 instances, both halves, excluding the four artefact rows and
  the one unclassifiable problem, so at most 107), the fraction that are wrong by study
  16's frozen gold (the 45 tests failing on the canonical solution). Wilson 95% for the
  binomial proportion of kept applications, and a problem-cluster percentile bootstrap
  (seed **20260915**, 10,000 resamples, `report_ceiling.cluster_bootstrap_ci` unchanged;
  the cluster is the problem, since a suite is shared by both candidates of a problem
  and by all three draws). A count small enough that its interval reaches an absurd
  bound is quoted as the count.
* **(ii) Retention**: how many of the seven `validated-only` instances of §0 keep at least
  one correct failing draw-1 test under the rule.

**KILL, per rule:** wrong tests among kept > 2% (point estimate), OR retention < 5 of 7.
At the size available — about 90–107 kept applications — the 2% line allows at most one
wrong application kept (2 of 91 is 2.2%); that is the bar the brief set, and it is
stated here so the reader knows before the run how narrow it is.

**Best-performing rule**, chosen by this order and nothing else: among the rules with
retention ≥ 5 of 7, the lowest point-estimate wrong-test rate among kept; ties broken by
higher retention, then by A before B before C′ (the more conservative rule first). If no
rule reaches 5 of 7, the best rule is the one with the highest retention and H17 is
killed. **H17 holds iff the best-performing rule passes both kill criteria.**

**Deviation from the brief, stated before the run.** The brief defines (i) over the
1,188 classifiable unique tests. §0 shows that 29 of the 45 wrong tests never fail on any
candidate, so under that definition every rule of this kind keeps at least 29 wrong of
about 1,170 tests — a floor of ≥ 2.4%, above the 2% kill line — and the study would be
decided before the draws were made. The primary is therefore defined over the failing
applications, where the rules act. The brief's quantity is reported as a secondary
(§5), with its floor, so the reader can see both.

## 5. Secondaries, all preregistered here

* The brief's unique-test rate: a draw-1 test is "kept" if the rule keeps it on at least
  one candidate, or passes on every candidate (no decision); wrong rate among kept over
  the 1,188, with its ≥ 2.4% floor stated beside it.
* Per rule: correct failing applications retained (of 89) and wrong ones removed (of
  18), each with both intervals; the same at the unique-test level over the 89 draw-1
  tests that fail on at least one candidate (73 right, 16 wrong).
* The arm each rule implies, on the confirm half, against the frozen objective: flag =
  at least one KEPT failing draw-1 test, or a draw-1 candidate timeout (Amendment 1).
  P-recall and C-false-positive rate with both intervals; `hc ∪ testgen-rule` beside
  `hc` (11/55 at 5/74) and the oracle bound `hc ∪ testgen-validated` (18/55 at 5/74).
  These numbers are reported, not decided on: the objective's bar is not this study's
  kill, and the confirm half was already read in study 16.
* Draws 2 and 3 scored against the canonical solution as study 16 scored draw 1: their
  own wrong-test rates with intervals — the replicate of study 16's 45/1,188 = 3.8% that
  its §4 said a second draw would be — and, per problem, whether a problem with a wrong
  draw-1 test also has a wrong draw-2 or draw-3 test (the correlation §1 names as the
  way H17 fails).
* Draw-to-draw identity: responses byte-identical to draw 1 (the degeneracy count), and
  tests identical as normalised source strings between draws.
* Counts: tests per draw, uncompilable, empty suites, timeouts, pre-collector deaths.
* Cost from the project's usage ledger (`run_id` `testgen-val-d2`, `testgen-val-d3`),
  beside the sum of the adapters' per-call figures.

## 6. Boundary, records, budget

Prompts take strings only; the hidden suite is unreachable by construction and
`tests/test_architectures.py` is unchanged and still proves it for this prompt.
`execute.py` and everything under `src/` are unchanged. The canonical solution is used
only to score the rules — the frozen draw-1 gold, and draws 2 and 3's wrong-test rates in
§5 — never inside a rule. Records under `records/testgen-val/`: per-draw suite shapes
(counts, hashes, cost — no text), per-instance outcome rows (failure indices per draw,
kept indices per rule — no text), `numbers.json`. The rules' logic is pure and tested in
`tests/test_testgen_val.py` without the API.

Budget: two draws × 222 calls at study 16's $1.77 per draw ≈ $3.6; cap $5.0 across both
draws; a stopped draw reports its n and the primary is computed on the problems that
have all three draws.

## 7. Decision, written before the run

* H17 holds → the best rule is a candidate product validator; the design note study 16
  §7 promised is written with the rule's measured wrong-test removal and correct-test
  retention, both with intervals, and the arm-level numbers of §5 beside the oracle
  bound.
* H17 fails on the wrong-test rate → draws agree on wrong tests as on right ones (or
  the rule cannot separate them at this n); the finding is that corroboration across
  draws does not recognise a wrong test, and the next question is whether a different
  signal — the model asked about ONE test against the specification, the draft's H17c,
  or contradiction with the visible suite at the test level — does. That is a separate
  preregistration, not this one.
* H17 fails on retention → corroboration costs the recall it was meant to protect; the
  oracle-free validated union stays a research result.

## Amendment 1 — before any model call: one secondary count corrected

Written after the driver's data-loading was checked against the frozen record and before
the first call. §5's unique-test-level secondary counted the draw-1 tests that fail on at
least one candidate as "89 (73 right, 16 wrong)"; that count included the four artefact
rows, in which every test is recorded as failed without being evaluated. Excluding them,
as §4 does for the primary, the set is **80 tests: 64 right, 16 wrong**. Nothing else
changes: not the hypothesis, the rules, the primary, its denominators (107 failing
applications: 18 wrong, 89 right — that figure already excluded the artefacts), the kill,
the seed, or the selection order.

## Amendment 2 — during draw 2, before draw 3 started: the spend cap raised to the authorised $8

Written 2026-09-10 22:51 +08:00, with draw 2 in flight and draw 3 not started
(`generated_tests-d3.json` does not exist). At this minute 73 of 222 draw-2 calls had
landed, at $0.577 in total — $0.0079 per call by the adapters' figure, study 16's rate —
so the two draws project to ≈ $3.5 and §6's $5.0 cap is not expected to bind. The
coordinator has restated that the owner's authorisation for this study is $8, not $5, and
asked that the cap not be allowed to truncate draw 3: **§6's cap is raised from $5.0 to
$8.0 across both draws.** The in-flight invocation was started with a $5 argument; if it
halts there, it is relaunched with the remainder so that the ledger's total across
invocations stays ≤ $8, and the relaunch is recorded in the results. If even $8
truncates draw 3, the run stops at the cap, the truncation is reported, and the rules
are computed on the problems both new draws cover (with the count stated), as §6 already
said. Nothing else changes: not the rules, the primary, the kill, the seed, or the
selection order.

## Amendment 3 — after the results, at the reviewer's request: three statements corrected, none of them a rule

Written 2026-09-10 after `RESULTS-TESTGEN-VAL.md` and its review; the original text above
is left as written. Nothing here changes a hypothesis, rule, outcome, kill, seed or
selection order; the review found every number to reproduce.

* **§0, "The other 1,428 applications pass."** The count is 1,430 across the 290 rows
  (1,556 applications, counting `Mbpp/160`'s 11 and the four artefact rows' 17) and
  1,421 within the 285 clean, classifiable rows (1,528 applications, of which 107
  fail). Study 16's 1,545 excludes `Mbpp/160`'s row.
* **§4, "the 2% line allows at most one wrong application kept."** One at n ≤ 99; two
  at n = 100–107 (2 of 101 is 1.98%). Rule B's n was 101.
* **§3, rule C "keeps no failing test."** That holds on P and C candidates, which pass
  the visible suite. 58 of the 107 failing applications are on F-stratum candidates,
  which fail it, and there C would keep the failing test. C's retention — over the
  seven P instances — would still be 0 of 7, so it would be killed regardless; it stays
  unpreregistered, and the vacuity claim is narrowed to P and C.
