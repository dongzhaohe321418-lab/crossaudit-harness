# T03MaterialSEG, 60 arm-B instances, 17 revisions — revision broke more than it fixed, and the auditor named 2% of what was wrong

**Across 17 measured revisions on ExpertLongBench T03MaterialSEG, the post-revision output
scored 3.4 CLEAR F1 *below* the pre-revision draft it replaced (SE 3.88; 4 better, 6 worse,
7 unchanged; two-sided Wilcoxon p = 0.32) — a difference not distinguishable from zero, but
whose item-level accounting is not ambiguous: the revisions fixed 3 rubric items and broke
7.** And the reason there were only 17 revisions to measure is the first study's finding
made quantitative: under the shipped constitution the auditor raised a finding on 7 of 40
instances, and of the **201 rubric items CLEAR scored wrong in those 40 round-one outputs it
named 4 — a recall against ground truth of 2.0%**.

Study 1 could not tell whether that silence was correct behaviour or a defect. It is a
defect, and the study says which of three candidate causes it is:

| what was changed | auditor recall at round 1 | instances where it fired |
|---|---:|---:|
| nothing (shipped constitution, `gpt-5.6-terra`) | **2.0%** (4/201) | 7/40 |
| the **auditor model** → `gpt-5.6-sol` | **3.8%** (2/52) | 5/10 |
| the **constitution** → generated from the task's rubric | **15.5%** (9/58) | 5/10 |

**It is the constitution.** A stronger auditor model changed nothing. Rules that name what
the work is graded on multiplied recall by about eight. That is a product finding, and it is
actionable.

It also comes with a result nobody wanted: on the same ten samples, the rubric-constitution
arm's *first draft* scored **3.3 F1 against 14.7** for the shipped constitution, because
CrossAudit shows the constitution to the generator as well as the auditor. The rules that
made the audit work made the writing worse.

Whole-study spend: **$11.65** of a $15 budget.

Everything below is measured. Nothing is extrapolated.

---

## What was run

| | |
|---|---|
| task | `T03MaterialSEG` — justify the key decisions in a solid-state synthesis recipe |
| corpus | sha256 `0b525eae93aab406…`, verified against `manifest.json` at every run start |
| sample | **40** of the task's 50, seed `20260912`, sampled after sorting by id |
| generator (every arm) | `anthropic:claude-sonnet-4-6` |
| auditor | `openai:gpt-5.6-terra`, except arm B″ (`openai:gpt-5.6-sol`) |
| CLEAR mapper / judge / adjudicator | `openai:gpt-5.6-terra` |
| settings | `max_rounds: 3`, `checks: general`, `authority.lone_model_blocker: block`, N/A policy literal |
| code | frozen at `df3e15b` before the study; one plumbing change after (see Deviations 21–22) |

Four arms, each entered through the product's real `crossaudit.cli.build.run_loop` in a
fresh git project with a real `crossaudit.yml` and the recipe committed inside the audited
scope:

| arm | n | what differs |
|---|---:|---|
| **A** — single model | 40 | one generator call, the paper's T03 prompt, no audit |
| **B** — CrossAudit, as shipped | 40 | the full loop, `GENERAL_AUDIT_RULES.md` |
| **B′** — rubric constitution | 10 | `AUDIT_RULES.md` generated from the task's own rubric |
| **B″** — different auditor model | 10 | auditor is `gpt-5.6-sol`, everything else fixed |

B′ and B″ run on a strict subset — the first ten by id of arm B's forty — so every
comparison between them is paired on the same samples.

**A fresh seed did not buy a fresh sample.** Drawing 40 of 50 means 10 of study 1's 12
instances reappear. Only `10.1002/adfm.201000591` and `10.1002/adma.202416342` dropped out.
Treat this as a larger look at nearly the same corpus, not an independent replication.

---

## Q2 — does revision help or harm?

Scored **within the instance**: the CLEAR score of the round-1 draft against the CLEAR score
of the final output, same sample, same generator, same scorer. Generation variance — the
thing that made study 1's headline meaningless — cannot enter, because both numbers come out
of the same run.

**17 revisions across all three arm-B variants (of 60 arm-B instances).**

| | |
|---|---:|
| mean paired Δ F1 (post − pre) | **−3.40** |
| standard error | 3.88 |
| better / worse / unchanged | 4 / 6 / **7** |
| rubric items **fixed** by revision | **3** |
| rubric items **broken** by revision | **7** |
| two-sided Wilcoxon signed-rank | W+ = 17, W− = 38, **p = 0.320**, exact, 10 usable pairs (7 exact ties dropped) |

Deltas, sorted: −33.3, −25.0, −23.3, −22.2, −11.1, −9.5, 0, 0, 0, 0, 0, 0, 0, +5.6, +16.7,
+22.2, +22.2.

The p-value says the mean is not distinguishable from zero on 10 usable pairs. The item
counts say something the p-value cannot: **a revision on this task is more likely to destroy
a correct rubric item than to repair a wrong one, 7 to 3.** Study 1 saw this once, on one
instance, and could not tell whether it had found a pattern or an accident. It is a pattern.

Seven of seventeen revisions changed the score by exactly zero. A revision that costs a
generator call, an audit call and a full re-score, and moves no rubric item in either
direction, is the loop's most common outcome when it acts at all.

### Split by arm, and this is where it gets interesting

| arm | revised | mean Δ F1 | items fixed | items broken |
|---|---:|---:|---:|---:|
| **B** (shipped rules) | 7/40 (18%, CI 9–32%) | **−9.06** | 1 | 5 |
| **B′** (rubric rules) | 5/10 (50%, CI 24–76%) | **+8.89** | **2** | **0** |
| **B″** (`gpt-5.6-sol`) | 5/10 (50%, CI 24–76%) | **−7.78** | 0 | 2 |

**The only arm whose revisions helped is the arm whose findings named rubric items.** B′
raised 15 `CA-RUBRIC-*` findings; every one of them mapped to a rubric item and every one was
confirmed wrong by CLEAR in the output it was raised against, and its revisions broke
nothing. B and B″ raised generic `CA-CONTENT-001` / `CA-CONTENT-002` findings, more than half
of which are about no rubric item at all, and their revisions rewrote prose that was already
right.

That is a mechanism, not a correlation: **a finding that names a specific defect produces a
targeted edit; a finding that says "this is incomplete" produces a rewrite, and a rewrite of
a partly-correct document loses some of what was correct.** On n = 5 revisions per arm it is
a hypothesis worth a dedicated study, not a settled result.

---

## Q1 — why is the auditor silent?

For every round, of the rubric items CLEAR scored **wrong** in that very output, how many did
**any** finding raised against it name? Every finding of every severity is mapped onto rubric
items by a model call; the lookup of CLEAR's verdict is not a model call.

| arm | inst | fired | findings | BLOCKERs | items wrong | items named | hit | recall (all rounds) | **recall (round 1)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **B** | 40 | 7 | 12 | 12 | 240 | 4 | 4 | 1.7% | **2.0%** (4/201) |
| **B′** | 10 | 5 | 20 | 20 | 98 | 17 | 17 | 17.3% | **15.5%** (9/58) |
| **B″** | 10 | 5 | 12 | 12 | 96 | 2 | 2 | 2.1% | **3.8%** (2/52) |

Round one is the number that matters: a silent auditor at round one ends the loop, and the
first draft ships.

**Under the shipped configuration the auditor is not quietly agreeing with a good draft. It
is passing an output in which five of six rubric items are wrong, without mentioning any of
them.** 201 of 240 rubric items were wrong across the 40 round-one outputs. It named 4.

### It is not the model

`gpt-5.6-sol` — OpenAI's highest-capability model — fired on more instances (5/10 vs 7/40)
and moved recall from 2.0% to 3.8%, which on 52 wrong items is two items instead of one and
change. **Ten of its twelve findings were about no rubric item**: `CA-CONTENT-001` complaints
about completeness and `CA-CONTENT-002` complaints about consistency, raised against a
document whose actual defect was that it never justified the choice of atmosphere. A better
reader reading the wrong rules reads them more thoroughly.

### It is the constitution

Replacing the four generic rules with six generated mechanically from the task's own rubric —
one BLOCKER per rubric item, the paper's Appendix B description transcribed verbatim, nothing
tuned — took round-one recall from 2.0% to 15.5%. The findings changed character completely:

| arm | rules cited | verdicts |
|---|---|---|
| B | `CA-CONTENT-002` ×8, `CA-CONTENT-001` ×3 | 5 confirmed, 7 about no rubric item |
| B′ | `CA-RUBRIC-001…006` ×15, `CA-CONTENT-001` ×5 | 16 confirmed, 4 about no rubric item |
| B″ | `CA-CONTENT-001` ×6, `CA-CONTENT-002` ×5 | 2 confirmed, 10 about no rubric item |

**Every one of the 15 `CA-RUBRIC-*` findings was confirmed against CLEAR.** Not one false
positive. Across all three arms, of every rubric item any finding named, **100% were in fact
wrong** (B: 4/4, CI 51–100%; B′: 17/17, CI 82–100%; B″: 2/2, CI 34–100%).

That is the shape of the defect, stated precisely: **the auditor's precision is perfect and
its recall is 2%.** It never objects to something that was right. It almost never objects to
something that was wrong. A reviewer with those statistics is not a cautious reviewer; it is
a reviewer that has not been told what to look for.

### The cost of telling it what to look for

15.5% is not 100%, and the arm that achieved it paid for it:

- **Its first drafts were much worse.** On the shared ten samples, B′'s round-1 output scored
  **3.3 F1** against B's **14.7** and B″'s **15.8**. CrossAudit passes the constitution to
  the generator as well as the auditor (`generator.build_prompt(task=…, constitution=…)`), so
  B′ is *not* a clean manipulation of the auditor alone — it changed what the writer was told
  too, and the writer got worse. Rules phrased as audit criteria appear to be bad writing
  instructions.
- **Its final outputs were worse.** On the same ten, B′ finished at 7.8 F1 against B's 14.7
  (paired mean −6.9, p = 0.19). The revisions helped (+8.89) and still did not recover the
  ground the first draft lost.
- **It burned rounds.** Mean rounds 1.7 against B's 1.20, one instance exhausting the round
  budget (exit 11), at 2.3× arm B's per-instance generation cost and 2.4× its wall time.

So the honest statement of the constitution finding is narrow and it is still worth having:
**rules that name the rubric make the audit find things. On this task they also made the
draft worse, and the arm as a whole scored lower.** The lever works; where to pull it — the
auditor's rules, not the generator's — is the next thing to build.

### It is partly the task, but not mostly

The auditor sees only committed bytes: the recipe and the deliverable. The human reference
checklist was annotated from the full published paper. A model probe (one call per sample,
40 samples, no failures) asked whether each reference cell's substance is derivable from the
recipe alone:

| rubric item | derivable from the committed recipe |
|---|---:|
| Synthesis Conditions / Atmosphere | 85.0% |
| Synthesis Conditions / Duration | 85.0% |
| Selection of Precursors / Structural Considerations | 80.0% |
| Selection of Precursors / Physical and Chemical Properties | 70.0% |
| Selection of Precursors / Handling Precursor Reactivity | 62.5% |
| **Synthesis Conditions / Temperature and Heating Method** | **32.5%** |
| **all items** | **69.2%** |

About **69%** of what CLEAR grades is in principle checkable from what the auditor can read.
That caps recall below 100% and it explains why the temperature item — the very item study
1's single blocker was about — is the hardest to audit. It does **not** explain 2%. The
ceiling is 69 and the measurement is 2.

---

## Secondary — arm A against arm B

Study 1's headline question, now demoted, because the answer to it says nothing about
auditing until the auditor speaks.

| | arm A (single model) | arm B (CrossAudit) |
|---|---:|---:|
| **mean F1** | **17.7** | **16.6** |
| std error of F1 | 3.0 | 2.4 |
| mean precision | 16.7 | 15.8 |
| mean recall | 27.1 | 24.6 |
| mean accuracy | 15.4 | 14.6 |
| instances scored | 40/40 | 40/40 |
| failures | 0 | 0 |
| mean rounds | 1.00 | 1.20 |
| generation cost / instance | $0.0198 | $0.0577 |
| wall time / instance | 28.9 s | 53.9 s |

Paired difference (B − A) = **−1.19 F1** on 40 pairs. Arm A won 10, arm B won 8, 22 exact
ties. Two-sided Wilcoxon signed-rank, exact: **p = 0.447** on 18 usable pairs. Not
significant, and now *negative* where study 1's was positive — which is the expected
behaviour of a difference that is generation variance rather than an effect.

Both arms sit inside the paper's Table 2 band for T3 (15.2–19.5 F1 for frontier models),
which is a sanity check on the scorer and nothing more; see Deviations before comparing any
absolute number to the leaderboard.

**At n = 40, CrossAudit's full loop costs 2.9× a single model call and 1.9× the wall time,
and buys a score difference of −1.2 F1 that cannot be distinguished from zero.**

---

## D142 — the BLOCKER confirmation rate

Study 1 had one BLOCKER. This study has **44**, all of them BLOCKERs (no arm raised a single
ADVISORY across 60 instances — itself worth noticing).

| | count | rate |
|---|---:|---|
| confirmed (cited a rubric item CLEAR scored wrong) | 23 | **100%** of rubric-relevant, 95% CI **[85.7%, 100%]** |
| false positive (every cited item was correct) | **0** | **0%**, 95% CI [0%, 14.3%] |
| about no rubric item | 21 | — |

**Confirmation rate 23/23, false-positive rate 0/23.** That is a real number now, not one
observation, and it points one way: when this auditor blocks on something the rubric can
adjudicate, it has never yet been wrong. Twenty-three findings is still small for a policy
default, and every one of them came from a single generator/auditor vendor pair on a single
task, so `authority.lone_model_blocker` should not be moved on this alone. But the risk D142
was worried about — a lone model blocking work over nothing — did not appear at all. The
observed failure mode is the opposite one: it blocks over nothing **often enough to be
useless**, since 21 of 44 findings are about matters the rubric cannot rule on, and it stays
silent about 98% of what is actually wrong.

---

## What it cost

| | |
|---:|---|
| arm A generation (40) | $0.79 |
| arm B generation + auditing (40) | $2.31 |
| CLEAR scoring, arm A (40 × 13 calls) | $1.54 |
| CLEAR scoring, arm B (every round) | $1.96 |
| checkability probe (40 calls) | $0.26 |
| arm B′, everything (10) | $2.24 |
| arm B″, everything (10) | $2.21 |
| **the three recorded runs** | **$11.32** |
| pipeline smoke test, 1 instance (see Deviations 21) | $0.25 |
| aborted first launch, 1 instance (see Deviations 21) | ~$0.08 (reconstructed, not read from a ledger) |
| **total** | **≈ $11.65** of a $15 budget |

Per instance: arm A $0.0198 generation + $0.0386 scoring; arm B $0.0577 generation +
$0.0489 scoring. B′ $0.134 + $0.090; B″ $0.143 + $0.078. **Scoring still costs more than
generating for the single-model arm**, and arm B's scoring cost now scales with rounds
because every round is scored — that is the price of the study's primary measurement and it
is worth it.

To reproduce:

```sh
export PYTHONPATH="$(git rev-parse --show-toplevel)/src"
python benchmarks/expertlongbench/fetch.py
R=benchmarks/expertlongbench/runs
python benchmarks/expertlongbench/run.py --task T03MaterialSEG --n 40 --seed 20260912 \
    --arms AB --probe-checkability --label B --out "$PWD/$R/main-n40"
python benchmarks/expertlongbench/run.py --task T03MaterialSEG --n 40 --seed 20260912 \
    --subset 10 --arms B --audit-rules rubric --label B-rubric --out "$PWD/$R/bprime-rubric"
python benchmarks/expertlongbench/run.py --task T03MaterialSEG --n 40 --seed 20260912 \
    --subset 10 --arms B --auditor openai:gpt-5.6-sol --label B-auditor-sol \
    --out "$PWD/$R/bsecond-auditor"
python benchmarks/expertlongbench/report2.py "$R/main-n40" "$R/bprime-rubric" "$R/bsecond-auditor"
```

`--out` must be absolute (Deviations 21). It will not reproduce byte-identically: the
provider layer exposes no seed and temperature comes from the model's capability card.

---

## What this run does and does not license

**It does not license** the claim that the audit loop improves accuracy. Paired difference
−1.2 F1 at n = 40, p = 0.45.

**It does not license** the claim that revision improves the work it revises. The paired
within-instance difference is −3.4 F1 on 17 revisions, p = 0.32, and the item counts run
7 broken to 3 fixed.

**It does license**, and this is the reason the study exists:

1. **The auditor's round-one recall against ground truth is 2.0% under the shipped
   configuration.** That is a measured product defect, not an inference.
2. **Its precision is 100%.** Every rubric item any finding named, in any arm, was in fact
   wrong. The auditor is not noisy; it is nearly mute.
3. **The constitution is the binding constraint, not the auditor model.** Rubric-derived
   rules: 15.5%. A stronger auditor model: 3.8%. Same task, same subset, same everything
   else.
4. **Rules that name the rubric make the audit work and the writing worse**, because the
   generator is shown the same file. Separating what the auditor is told from what the
   generator is told is a concrete, testable next change.
5. **The revisions that helped were the ones that named a specific rubric item.** B′ fixed 2
   items and broke 0; B and B″ fixed 1 and broke 7 between them. On 5 revisions per arm, a
   hypothesis.
6. **About 69% of this task's rubric is checkable from the bytes the auditor sees.** Ceiling,
   not excuse.

**Do not re-run this study hoping for a different number.** If the configuration changes, the
study restarts and says so here.

---

## Deviations from CLEAR

Study 1's list 1–14 stands. Items 1, 2, 4, 5, 6, 7, 8, 9, 10, 13 and 14 apply unchanged.
Changed and added:

3′. **The judge shares a vendor with the auditor, and this time there was no alternative.**
   Only Anthropic and OpenAI had credentials on this machine. The generator is Anthropic,
   CrossAudit refuses a same-vendor generator/auditor pair, so the auditor must be OpenAI and
   the judge falls back to OpenAI. The bias points in arm B's favour and arm B still lost.
   Study 1 named a third judge vendor as the first thing to fix in a repeat; it is still
   unfixed, for want of a key.

11′. **Sample 40 of 50, seed `20260912`.** Fresh seed, not a fresh sample: 10 of study 1's 12
   instances recur, which is exactly what drawing 40 of 50 predicts.

12′. **Arms A and B still differ in more than "audit on/off"** — arm B's generator sees
   CrossAudit's system prompt, file contract and constitution. This remains the most likely
   explanation of any A/B difference and it is **not** a confound for Q2, which is measured
   inside a single arm-B instance.

15. **The auditor-model arm could not vary the vendor.** Q1's "is it the auditor model?" was
   designed as a different vendor with everything else fixed. With two vendors keyed and one
   occupied by the generator, it varies the model *within* OpenAI (`terra` → `sol`). A
   negative result there rules out less than a cross-vendor negative would: it shows a
   stronger model does not help, not that no other vendor would.

16. **The rubric-derived constitution is our construction.** `rubric_constitution()` in
   `run.py` emits one BLOCKER per rubric item whose body is the Appendix B §B.3.5 description
   transcribed verbatim, plus a fixed sentence about the source material, plus `CA-CONTENT-001`
   retained unchanged. Its preamble is copied from the shipped template so the two
   constitutions differ only in their rules. The contrast is therefore "rubric rules
   replacing `CA-TASK-001` / `CA-CONTENT-002` / `CA-USABILITY-001`", not "rubric rules
   replacing everything".

17. **B′ changes the generator as well as the auditor.** `crossaudit.cli.build.run_loop`
   passes the constitution into `generator.build_prompt`. This was discovered while reading
   the results, is reported above as a finding rather than buried, and means B′ is a test of
   "does a rubric-shaped constitution help the audit", not of "does the auditor improve when
   only its rules change". The clean experiment needs a product change first.

18. **Auditor recall is measured against CLEAR, not against truth.** "Missed it" means "CLEAR
   marked that item wrong and no finding was about it". CLEAR is a model-based containment
   metric with its own error rate, and it inherits every deviation in this list.

19. **Mapping a finding to rubric items is one model call per finding** — study 1's blocker
   step, now run on findings of every severity. A finding the mapper cannot place counts as
   naming nothing, which lowers measured recall if the mapper under-maps; that is the
   direction which flatters the "silent auditor" story, so the unmapped findings are reported
   separately (21 of 44) rather than folded in.

20. **The checkability probe is one model call per sample** asking whether each reference
   cell is derivable from the committed recipe. It is a model's opinion about derivability,
   not an expert's, and it was not validated against human annotation. Report it as an
   order of magnitude, not a constant.

21. **Two harness changes were made after the study first launched, both before any
   comparative score was read.**
   (a) A run directory passed as a *relative* path made the loop resolve its config root
   against the project it had chdir'd into, so every arm-B instance failed with rounds = 0.
   Caught on instance 1, fixed in `df3e15b`, and the study restarted from scratch — one
   arm-A generation, one CLEAR pass and one checkability probe were paid for and discarded
   (≈$0.08, the only reconstructed number in this report). A one-instance pipeline smoke test
   ($0.25) preceded the study and its numbers are not used.
   (b) The n = 40 run was killed by the environment at instance 21 of 40 with 20 instances
   already scored. `--resume` was added (`161a0d1`) so the remaining 20 could be run without
   paying twice for the first 20. It decides which seeded samples still need running and
   touches no arm, prompt, model, setting or scoring path; the 40 samples and their order are
   unchanged. **This is a mid-study code change and it is disclosed rather than hidden.** No
   score was altered by it, and the first 20 instances' records predate it byte for byte.

22. **Every round of arm B is scored**, where study 1 scored the final output plus any round
   carrying a blocker. This is what makes Q2 measurable. It does not change any A/B number
   and it raises arm B's scoring cost in proportion to rounds.

23. **`run_ids` in `main-n40/plan.json` records the same id twice**, a cosmetic bug in the
   resume path's bookkeeping: the resumed invocation appended its run id to a list seeded
   with its own. Cost in this report is summed from the per-instance records, which are
   correct, not from that list.
