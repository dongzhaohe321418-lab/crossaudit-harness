# Study 23 — does the ceiling move with the substrate?

Preregistered on `study/substrate2` **before any model call of this study**, at the commit that
adds this file. Binding: ceiling 1's preregistration §0–§1.5 and `RESULTS-CEILING.md` (the
estimand, the strata, the union-of-K curve, the flattening bar, the interval conventions),
study 2's generation protocol, study 21's rubric (§2 of `rerate/PREREGISTRATION.md`),
`EXPERIMENT_RECORD.md` §9–§10.

## 0. The question

Every number this programme has produced comes from one substrate: HumanEval+ and MBPP+, whose
median task is 41 words of prose and 6 lines of reference code. The ceiling measured there —
union recall 30.0% [20.0, 40.7] at eight readings of the shipped cross-vendor auditor, 48.2%
[36.7, 60.0] pooling twenty readings of three families — is the paper's central quantity, and a
reader is entitled to ask whether it is a property of auditing or of short functions.

This study repeats ceiling 1's measurement, unchanged, on a substrate whose median task is
**117 words of prose and 41 lines of reference code**.

## 1. The substrate, fixed before any generation

**BigCodeBench** (`bigcode/bigcodebench`, split `v0.1.4`, Apache-2.0; 1,140 tasks), reduced by
two mechanical filters applied in the frozen environment and recorded with the environment's
own module inventory:

| | filter |
|---|---|
| S1 | every module the task declares is importable in this project's interpreter |
| S2 | the task's canonical solution passes the task's own unittest suite here, within 60 s |

Measured before this file was written: **326 tasks pass S1 and 289 of those pass S2**. The 37
drops are recorded with their reason (15 need `faker`, 5 `pandas`, 4 `pytz`, 1 `numpy`, 1
`pyfakefs`, 2 time out, 5 fail their own suite). The frame is those **289 tasks**, frozen with
each task's sha256 before generation, and it is not revisited.

This excludes the tasks that need the scientific stack, so the frame is the stdlib half of
BigCodeBench and the results say so wherever they are quoted. What it is not is a selection on
any outcome: no auditor and no generator has seen this corpus.

**Visible and hidden suites.** BigCodeBench ships one unittest class per task; ceiling 1 needs
a suite the author is shown and a suite that decides. The split is mechanical and seeded: the
task's test methods sorted by name, **two** of them chosen by `random.Random(20260917)` as the
**visible** suite, and **all** of them as the **hidden** suite — hidden ⊇ visible, exactly the
relation EvalPlus's plus-suite has to its base suite. 287 of the 289 tasks have at least four
test methods (median five). A task with fewer than three is dropped and counted.

**Strata**, ceiling 1's definitions unchanged: a candidate that passes the visible suite and
fails the hidden one is **P**; passes both, **C**; fails the visible suite, **F**.

## 2. What is run

* **Generation.** `claude-haiku-4-5-20251001`, study 2's prompt shape (the specification and
  the visible tests, nothing else), two batches (`g1`, `g2`) over the 289 tasks, temperature and
  sampling at the harness defaults. Solutions are executed locally; the strata follow.
* **Audit.** The shipped cross-vendor auditor (`openai:gpt-5.6-terra`), holistic, the shipped
  constitution unmodified, **K = 8** independent draws — ceiling 1's `cross` family exactly. If
  budget remains after the eighth cross draw, the same-vendor family (`self`,
  `claude-haiku-4-5`) is run at K = 8 on the same instances, in that order.
* **Scope.** All P instances up to **200**; if more than 200 exist, 200 are drawn by
  `random.Random(20260917)` from the sorted ids, before any audit call. Plus a **C sample of
  150** drawn the same way. The audit set is frozen and committed before the first audit call.

## 3. Hypotheses

* **H23a (primary).** The shipped auditor's union recall at K = 8 on substrate 2's P differs
  from its union recall at K = 8 on substrate 1's P (33/110 = 30.0%). Two-sample problem-cluster
  percentile bootstrap of the difference (seed 20260917, 10,000 resamples), Wilson beside each
  rate. **Sign not fixed**: a harder substrate could go either way, and both directions are
  interesting.
* **H23b.** The saturation curve on substrate 2 at every K from 1 to 8, the constrained
  exponential fit, and ceiling 1's flattening bar (last-step gain ≤ 1.0 point). Where the bar is
  not met the fitted asymptote is an extrapolation and the raw union at K = 8 is quoted.
* **H23c.** Union false positives on the C sample at K = 8, and the recall bought per
  false-positive point, against substrate 1's 16.0% and 1.68.
* **H23d.** If the `self` family runs: the same-vendor minus cross-vendor difference at K = 8,
  against substrate 1's −12.7 points [−25.0, −0.9]. Paired: exact McNemar and the cluster
  sign-flip test.
* **H23e.** The residual — P instances no draw flagged — classified under **study 21's rubric
  verbatim** (§2 of that preregistration, the oracle question asked second), by the same two
  raters, blind to instance id, with κ. This is where substrate 2 can confirm or break study
  21's central finding: on a substrate whose specifications are three times longer, is the
  residual still dominated by failures the prose does not determine?

Primary: H23a. Everything else is secondary; no correction is applied to the secondaries, none
is claimed to clear a corrected threshold, and the full comparison inventory is listed in the
results.

## 4. What would falsify what

* If H23a's interval excludes zero and substrate 2's recall is **lower**, the ceiling is not a
  property of short functions; the paper's headline generalises in the direction that matters
  and says the measured ceiling is, if anything, optimistic.
* If it is **higher**, the paper must say that its central quantity is substrate-dependent and
  that 30.0% is not a general figure. That sentence is written into the results either way.
* If H23e finds the residual is **not** dominated by oracle-defined failures on substrate 2,
  study 21's finding is local to MBPP-style prose, and claim 4 of the paper's ledger is narrowed
  to that substrate in the same revision.

No outcome may change the frame, the split seed, the strata, the ladder, K, the hypotheses or
this section.

## 5. Budget, stopping, boundary

Generation ≈ 578 calls, ≈ $2. Audit ≤ 350 instances × 8 draws for `cross`, and the same for
`self` if it runs. Expected **$40**; cap **$60** on this study's cumulative spend, enforced from
the project ledgers across restarts. The ladder is fixed: `cross` draws 1–8 in order, then
`self` draws 1–8. The run stops at the cap and the completed draws are reported.

Boundary: `src/` and the kernel directories are untouched; ceiling 1's files are not modified.
BigCodeBench is Apache-2.0, so its text may be redistributed, but this study keeps the corpus
out of the repository anyway and commits ids, hashes, counts and outcomes only — the same rule
substrate 1 follows. Solutions and model replies live in the run archive.

---

## Amendment 1 — the visible suite shown to the models did not parse; the audit is void

**Written 2026-09-15, after the first cross-vendor review and before any re-run.**

The review found, and re-running the extraction confirms, that `Task.visible_tests_text()` sliced
the selected test methods out of their enclosing class and returned them verbatim. The text
therefore began at an indented `def` and **failed `ast.parse` on 300 of the 300 tasks**, while
scoring executed the intact class through `unittest.main(argv=...)`. On 142 of the 301 classes the
selected methods also call `setUp`, `tearDown` or helpers that the slice omitted.

`visible_tests_text()` feeds the **auditor** prompt (`audit.py`, `TESTS_PATH`) and the
**generator** prompt (`testgen.py`, `audit2.py`). Both were shown syntactically invalid Python on
every task of this substrate.

**Why this is not a cosmetic defect.** An auditor shown a broken test file can return a finding
about the file rather than about the candidate. That raises the flag rate on **both** strata, so
it inflates recall (H23a) and false positives (H23c) together and is not removable by any analysis
of the existing records: the finding texts were not archived, so no reading can be classified after
the fact. It also confounds the cross-substrate comparison that the paper's second caution rests
on, because substrate 1's `visible_tests_text()` returns valid top-level asserts.

**What this amendment fixes.**

1. `visible_tests_text()` now emits a module that parses: the test file's own prologue, the class
   header, the class's non-test members, and the selected test methods. No test method outside
   `_visible` appears, so the registered split is unchanged and the hidden suite stays hidden.
   Verified across all 300 tasks: 300 parse, 0 visible methods missing, 0 hidden methods leaked.
2. Two tests pin the contract: the text the models are shown must parse, and it must contain every
   visible method and no hidden one.
3. `test_the_visible_text_is_exactly_the_selected_methods` is **withdrawn**. It passed throughout
   and concealed the defect, because it wrapped the text in `class T:` and re-indented every line
   before parsing — the test manufactured the header the real consumers never received. It is kept
   under a `_SUPERSEDED` name with that explanation rather than deleted.

**What this amendment does NOT do, and what it costs.** It does not repair the run. Every number
in `RESULTS-SUBSTRATE2.md` was produced by models reading the broken text, so the 250 instances ×
8 draws × 2 auditor families are **void as evidence for the registered hypotheses** and none of
them may be quoted. H23a to H23e must be re-run against the corrected text before this study
reports anything. The frame, the seeded split, the strata and the generation of candidates are
unaffected as *definitions*, but the candidates were themselves written by a generator reading the
broken text, so the defect population must be regenerated too rather than reused.

**The direction of the bias is not known in advance.** A broken test file could make the auditor
more suspicious (raising both rates) or could waste its attention (lowering recall). We register
now, before the re-run, that we will report the re-run's numbers whichever way they move, and will
publish the comparison against the void run rather than quietly replacing it.

## Amendment 2 — the re-run: what is frozen before the first model call

**Written and committed 2026-09-16, before any model call of the re-run.** Amendment 1 voided the
original run and required a re-run. This amendment fixes what that re-run may and may not do, so
that nothing below is chosen after seeing a result.

**Frozen inputs.**

* The frame is **unchanged**: the same 300 tasks, the same `frame.json`, the same split rule
  (`seed = 20260917`, `n_visible = 2`, `min_methods = 3`). The defect in Amendment 1 was in how the
  visible methods were *rendered for the models*, not in which methods were selected, so the frame
  needs no reselection and gets none.
* The corpus file is `bigcodebench.jsonl`,
  sha256 `6f3442384e576147f71875242068ce217885e0f761603cfb62175736e0331abd`.
* **The corrected visible text is frozen by digest.** Over the 300 frame tasks in frame order, the
  sha256 of `problem_id` + NUL + `visible_tests_text()` is
  **`2c47fb410167fc6e2054d6fad0b62e42e0716d62c5225807a16344b895bba128`**, and all 300 parse. The
  re-run must reproduce this digest before it spends anything; if it does not, the run stops and
  the discrepancy is reported rather than absorbed.
* Generation seed, audit seed, ladder, strata caps and K are ceiling 1's and the original run's,
  unchanged: `SEED = 20260917`, `MAX_P = 200`, `N_C = 150`,
  `LADDER = cross d1..d8 then self d1..d8`.

**Budget and stopping rule.** The cap stays **$60**. The original run spent $28.23 ($1.83
generation, $18.31 `cross`, $8.10 `self`). The re-run is expected to cost slightly more because the
corrected visible text is longer — it now carries the module prologue, the class header and the
fixtures — so more input tokens per call. **If spend reaches $45 the run halts and reports what it
has**, rather than continuing toward the cap.

**How the two runs are reported.** This is fixed now because it is the decision most open to being
made favourably after the fact:

1. The re-run's numbers are the study's numbers. The void run's numbers are **not** replaced or
   deleted; `RESULTS-SUBSTRATE2.md` keeps them under its VOID banner.
2. **Both are reported side by side, whichever way they move**, with the difference stated for
   H23a (recall at K = 8), H23c (false positives at K = 8) and the self arm's draw-to-draw
   agreement. We commit to this before knowing the sign.
3. The comparison is **descriptive and post hoc**. The two runs differ in exactly one respect we
   intended and possibly others we did not, so no p value, interval or hypothesis test is attached
   to the difference between them, and it may not be described as an estimate of "the effect of
   showing a model broken tests". It is one run against one run.
4. If the re-run's numbers are close to the void run's, that does **not** retroactively validate
   the void run. The reason the original is void is that the input was not what the study said it
   was, and that is independent of where the numbers land.

**What still will not be established.** The re-run does not address the second finding of the
first review: the flat `self` curve remains confounded, because that route is sent `temperature 0`
while `cross` is sent no sampling parameter. **No claim that the flatness is an operating-point
effect rather than a sampling effect may be made from this re-run**, and the phrase is barred from
the results unless a temperature-matched arm is added. That arm is not in this budget.

**Registered kill.** If the corrected visible text fails to reproduce the digest above, or if any
task's visible text fails to parse at run time, the run halts before spending and reports the
failure. There is no outcome-dependent kill on the rates themselves: this is a re-measurement of a
voided run, not a test of a new hypothesis.

## Amendment 3 — the resume artefacts now carry the generation they belong to

**Written 2026-09-16, after the re-run's audit exposed the root cause, before the incremental audit.**

**What happened.** The re-run changed `--run` to a fresh run directory, which correctly invalidated
the candidate solutions, and audited a scope frozen from the *voided* generation. Of that scope's
250 ids, under the new candidates 92 were still P, 152 were C and **6 were F** — instances that
fail their own visible suite and must never be audited.

**The root cause is a boundary mismatch, not a forgotten file.** The pipeline keeps run-scoped
artefacts in two places:

| artefact | lives in | invalidated by a new `--run`? |
|---|---|---|
| candidate solutions | `run_dir/solutions/` | **yes** |
| audit readings | `records/substrate2/cache/` | **no** |
| frozen scope | `records/substrate2/audit_set.json` | **no** |

The last two sit in `records/`, which is committed **for provenance** so a reviewer can recompute
every number, and their only reuse condition was `if path.exists()`. So the switch that starts a
re-run cannot reach the two artefacts that most need invalidating. Quarantining `cache/` by hand
made `--plan` go from "0 to run" to a full ladder, which looked like the path was clear and was
precisely why the second artefact went unexamined.

**Why the registered gate did not catch it.** `verify_frame.py` checks the visible-test digest,
because that is where the *previous* failure was. A gate shaped like the last accident does not
stop the next one.

**What is added.** `audit_set.json` now records `generation_sha256`, a digest over every
instance's id, stratum and `solution_sha256`. On every run the audit driver recomputes it and
**refuses** a scope frozen from a different generation, or one predating this amendment that
cannot prove which generation it belongs to. The cache is checked the same way: a cached reading
whose `solution_sha256` differs from the instance's now halts the run. Both refusals are tested,
by restoring the quarantined file and by planting a wrong digest; both exit non-zero with the two
digests named.

**Note on what the guard would NOT have caught, and why the check is the one chosen.** All 4,000
readings of 2026-09-16 *did* match their candidates — the auditor read the right code; only the
scope around it was stale. So "the solutions match" is not evidence that a resume is sound, and the
scope digest, not the per-reading check, is the load-bearing half.

**Cost of the repair.** Re-freezing from the new generation gives 249 instances (99 P, 150 C), of
which **147 were already audited and are reused**; 102 remain, at 16 arms, about **$9**. The 103
readings now out of scope stay bought and unused. We do not keep them by choosing the C sample to
match what was already purchased: that would be selecting a sample after seeing which of it was
paid for. Total study spend stays under the $45 halt registered in Amendment 2.

## Amendment 4 — the re-run halts incomplete: the self family is done, the cross family was never reachable

**Written 2026-09-17, after ten supervised attempts bought nothing.**

**State.** Against the re-frozen scope of 249 instances (99 P, 150 C):

| family | arms | readings | spend |
|---|---|---|---|
| `self` (`claude-haiku-4-5`) | 8 of 8 | **249 of 249 each** | $3.693 |
| `cross` (`openai:gpt-5.6-terra`) | 0 of 8 | **0 bought** | $0.000 |

Study total **$27.85** against the $45 halt registered in Amendment 2. The halt was never
approached, because the blocker cost nothing: a denied call is not billed.

**Why the cross family is empty.** The OpenAI route returned HTTP 429 continuously from
2026-09-16 15:37 to at least 2026-09-17 14:25, **about 23 hours**, across ten supervised attempts
spanning a full night and a working morning.

It is rate limiting and not billing, and that is checked rather than assumed on every attempt:
**no failure row carries `insufficient_quota`, and none carries 401 or 403.** The distinction is
one this programme can make from experience — study 22's Amendment 3 recorded a real credit
exhaustion, and those rows *did* carry `insufficient_quota`.

**A detail about the denials worth keeping.** In the final attempt's first arm, 6,945 of 7,038
rows are the harness's own circuit breaker reporting all routes cooling down, and only **93** are
provider 429s. The retry loop spends almost all of its time failing against its own breaker rather
than testing the API, so a short retry interval mostly re-opens the breaker without learning
anything. The supervisor's interval was lengthened from 15 to 60 minutes and its concurrency
dropped from 3 to 1 for that reason; neither changed the outcome, which is itself evidence that we
were not the cause of the throttling.

**What may and may not be concluded.**

* **H23a, H23b, H23c and H23e are not answered by this re-run.** All of them are about the shipped
  cross-vendor auditor, and it produced no readings. The self family alone cannot stand in for it.
* **The void run stays void.** Amendment 1's reason — the models were shown visible-test text that
  did not parse — is independent of whether a replacement run succeeded.
* **One comparison is available and is reported as descriptive and post hoc**, under Amendment 2's
  rule that forbids attaching a p value or interval to a one-run-against-one-run difference.
  Restricted to the 147 instances present in both runs and in the current scope, the same-vendor
  arm's verdict **splits across the eight draws on 0 of 147 in the void run and on 8 of 147 in the
  re-run**, and the two runs' K = 8 union verdicts differ on **40 of 147**. This is one run against
  one run; it is not an estimate of the effect of showing a model unparseable tests, and it does
  not retroactively validate the void run. What it does establish is that the "identical verdict on
  every instance across every draw" phenomenon the void run reported **does not survive** the
  correction — which matters, because that phenomenon was the empirical illustration behind the
  paper's second caution. The caution's empirical half had already been withdrawn on 2026-09-12 for
  an unrelated reason (the temperature-0 confound); this is a second, independent reason it was
  right to withdraw it.

**Registered stopping decision.** The re-run halts here rather than continuing on a different
route. The cross-vendor auditor could be reached today through a Codex CLI subscription, which we
verified is live and can serve the same model name. **We do not use it.** That path wraps the model
in a different agent harness with its own system prompt and tool loop, so the readings would not be
comparable with ceiling 1's frozen 30.0% comparator, which is the whole point of the contrast. A
different API key on a different account would be comparable, and is the owner's decision to make.

## Amendment 6 — the correction had its own extraction defect; the re-run is void in turn

**Written 2026-09-18, after the cross-vendor review of the re-run refused quotation.**

**What the review found, and it is right.** Amendment 1's repair sliced the "class header" as
`lines[head : target.body[0].lineno - 1]` — up to the first member's `def` line. When that member
carried decorators, the decorators stayed inside the "header" and the member was then emitted
again with them. A hidden method's `@patch` stack was therefore re-attached to whichever visible
method came first.

Verified independently here: **26 of the 300 frame tasks have altered method ASTs, all of them
gaining decorators**. The reviewer executed one — `BigCodeBench/12` — and the displayed test
raised `TypeError: test_script_does_not_exist() takes 2 positional arguments but 5 were given`
while the intact test passed.

**Why Amendment 2's gate did not catch it.** That gate asked two questions: does every displayed
file parse, and does its digest match. Both answers stayed correct. All 300 parsed, no hidden
test *name* appeared, and the digest faithfully froze the defective text — **which is what a
digest does.** A hash pins whatever it is given; it cannot tell a correct extraction from a wrong
one. The gate was shaped like the previous accident (unparseable text) and could not see this one.

**The fix and the stronger gate.** The header now ends at the first line of the first member
*including* its decorators, so it contains the `class` statement and its own decorators only.
`verify_frame.py` gains a **semantic check**: every displayed method's AST must be identical to
the same method in the intact class, and no displayed method may be absent from it. This compares
the objects rather than the syntax. Current state: 300 of 300 parse, **0 altered ASTs, 0 hidden
methods shown**. The digest is re-frozen at
`5c21539e7c3a4bcb03a92284ed06c0a52a609d75dad9bfe8d7c0257b2dcd89f2`.

**The consequence, stated plainly: the re-run of 2026-09-17 is void in turn.** Its models — both
auditor and generator — were shown decorator-corrupted tests on 26 tasks covering 24 audited
instances (12 P, 12 C). That is a smaller defect than the one Amendment 1 voided, and it is still
a defect of the same kind: the text shown was not the text scored. **No number from that run may
be quoted**, including the six reversals it produced, which must now be re-established rather
than carried forward.

**What this costs and what it buys.** Another full re-run at roughly \$37. Registered before it
starts, so it cannot be chosen afterwards: **the six reversals are treated as unconfirmed until
the corrected run reproduces them.** If the third run agrees with the second, the reversals stand
on a clean extraction; if it does not, the second run joins the first as void and this study will
have consumed three runs without a quotable number, which is the outcome the record will carry.

**The pattern worth naming.** Two successive repairs of this one function each introduced a new
defect that the gate written for the *previous* defect could not see. Parse-level checking missed
a semantic divergence; digest-level checking froze it. A gate must test the property the study
actually depends on — here, that the models see the scored suite — and not the property whose
absence caused the last failure.

## Amendment 7 — three gates, each proved able to fail, before any third run

**Written 2026-09-18, before the third run is launched.**

Two runs of this study were voided by the same fault in different costumes: the text shown to
the models was not the suite the scorer executed. Every gate written so far **inspected** that
text — does it parse, does its digest match, does its AST equal the intact class. Each was
written in the aftermath of one accident and could not see the next one. This amendment adds
the gate that tests the property the study actually depends on, and it fixes two registered
invariants that had no check capable of failing.

**1. Execution equivalence (`verify_execution.py`).** For every frame task, the visible suite
is assembled twice against the benchmark's own canonical solution — once from
`visible_program()`, which is what the scorer runs, and once from `visible_tests_text()`, which
is what the auditor and the generator are shown — and both are executed. The outcomes must
agree. Behaviour is settled by running, not by reading.

*Proved able to fail.* Restoring each voided extraction in turn:

| restored defect | gate result |
|---|---|
| Amendment 1's (methods with no class header) | HALT, many tasks `scored passed=True, shown passed=False` |
| Amendment 5's (hidden decorators re-attached) | HALT on `BigCodeBench/1102` |

**Both real accidents are caught by it, and neither was caught by any earlier gate.**
Current state: **300 of 300 agree, 0 divergent**.

**2. The cache guard was vacuous and is now real.** It tested `row["solution_sha256"]` on rows
returned by `explore.load_detector()`, which yields only
`{flagged, cost_usd, source, cost_reconstructed}` — the key is never present, so the guard
passed on every run without comparing anything. It now reads the cache files directly.
*Proved able to fail:* a planted wrong digest makes `--plan` exit 1 naming the instance.

**3. A registered invariant that was never enforced.** Section 2 says an instance failing its
own visible suite must never be audited. Nothing checked it, and the first re-run audited a
scope in which 6 of 250 ids had become stratum F. The driver now refuses a scope containing
anything outside P and C. *Proved able to fail:* planting one F instance makes `--plan` exit 1.

**The rule this amendment adopts for the rest of the study.** A registered invariant is not
enforced by being stated. It is enforced by a check that **can fail**, and a check is not
believed until a planted violation has made it fail. Both halves are required: the cache guard
above was written in good faith, looked correct, and tested a field that does not exist.

**Why `visible_program` and `visible_tests_text` keep diverging.** They are two independent code
paths with nothing binding them together, and both accidents live in that gap. The execution
gate is what binds them; it should be run before generation and before audit, not only on
demand.

## Amendment 8 — the third run: budget, gates, and what counts as a result

**Written and committed 2026-09-18, before the third run's first model call.**

**Spend to date, stated plainly.** \$37.16: generation \$1.91, audit \$35.25 (cross \$23.11,
self \$12.14). Of that, **\$22.25 bought readings on a scope frozen from a superseded
generation** and is unusable, and the remainder bought the run that Amendment 6 voided. **The
study has spent \$37.16 and holds no quotable number.** Amendment 2's \$45 halt was registered
for a single re-run and is now spent; this amendment sets the third run's own budget rather
than quietly continuing under the old one.

**Registered budget.** Generation is expected at about \$1.9 and the audit at about \$35, so
**the cap for this run is \$45 with a halt at \$40**, and the study total will be about \$82.
If the audit reaches \$40 the run stops and reports what it has. No further run is authorised
by this amendment; a fourth would need its own.

**Gates that must pass before anything is spent**, in this order, each proved able to fail by a
planted violation (Amendment 7):

1. `verify_execution.py` — the displayed suite and the scored suite must agree on the canonical
   solution for all 300 frame tasks.
2. `verify_frame.py` — every displayed method AST-identical to the scored one, and the digest
   equal to Amendment 6's `5c21539e…`.
3. The audit driver's own guards — no stratum-F instance in scope, no cached reading whose
   `solution_sha256` disagrees with the current generation.

**Why the candidates are regenerated and not reused.** `visible_tests_text()` feeds the
generator prompt as well as the auditor's. The voided run's candidates were written by a model
reading decorator-corrupted tests on 26 tasks, so the defect population itself is contaminated
and is rebuilt.

**What counts as a result, fixed before the numbers exist.** The six reversals the voided run
produced — the overlapping false-positive intervals, the same-vendor arm splitting, the gain
ratio staying above 1, the flattening bar being missed, H23d spanning zero, and the same-vendor
gain ratio becoming computable — are **unconfirmed**. This run either reproduces them on a
clean extraction or it does not.

* If it **reproduces** them, they stand, and the voided runs are reported as the path to them.
* If it **does not**, the second run joins the first as void, and this study will have consumed
  three runs and roughly \$82 without a quotable number. **That outcome is reported as found**,
  with no further run attempted under this amendment, and the paper continues to carry no
  substrate-2 figure.

Neither outcome is more welcome than the other in how it will be written. This sentence exists
because the three previous corrections in this study each moved a number in the direction that
made the work look better, and this one is registered before the direction is known.
