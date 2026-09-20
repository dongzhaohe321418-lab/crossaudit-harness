# Corrections to the measurement record

Numbers withdrawn or restated, with the evidence for each withdrawal. This file
exists because these results are intended for publication, and a reader deciding
whether to trust the record is entitled to see what the record got wrong before
they find it themselves.

Two sources. Some items were found by re-reading this project's own reports
against the claims being made *from* them. The largest ones, including an error in
this file's own first version, were found by an independent reviewer running on a
different vendor's model over the same records. Its full report is kept verbatim
at `reviews/2026-09-05-cross-vendor.md`; every finding taken from it was
reproduced here from the archived run data before being accepted.

---

## The shape of the failure

The committed reports are, with one exception, careful: they state confidence
intervals, they name their n, and several of them correct earlier reports in this
same line. `RESULTS.md` gives the confirmation rate as "100% (1/1), 95% CI
[20.7%, 100.0%]". `RESULTS-3.md` records the auditor's precision falling from
"100% (2/2)" to 73% and says so in those words.

The failure was **downstream of the reports**, in the layer where results get
summarised into headline claims — planning documents, decision records, and the
working conversation. In that layer the intervals were dropped, and a
one-in-one measurement travelled as "100%". One figure was not merely stripped of
its interval but **invented outright** (item 5).

The lesson is recorded in `EXPERIMENT_RECORD.md` §4, which already requires an
effect size with an interval beside every p. The rule needs to bind wherever a
number is *quoted*, not only where it is first computed.

---

## Withdrawn

**1. The 2.6-point prose noise floor — real, but the wrong estimand.**
*This item was itself wrong when first written here, and is corrected below.*

The figure is not fabricated. Study 5 measured it: three runs of the identical
cross-vendor configuration over the identical 11 fixed drafts gave recalls of
20.3%, 15.3% and 18.6%, SD 2.59 pp, range 5.1 pp. `RESULTS-5.md` reports it
plainly and already warns that "several cannot be judged at all because the floor
measured here covers the auditor and not the generator".

The defect is what it can be used for. It is the standard deviation of a **pooled
micro recall over fixed drafts**. It therefore bounds auditor-side run-to-run
variation and nothing else. It is not the variability of the primary paired
contrast, and it is not the variability of any study in which generation changes.
Every use of it to accept or withdraw a finding from a generation-changing study
is invalid, including its use against study 2's "2.0% to 3.8%".

Two of this project's numbers are read against it correctly, and both concern the
auditor over fixed drafts. Every other use of it should be struck. What is still
missing, and is now being measured, is the run-to-run spread of the **primary
paired contrast** itself.

**How this entry came to be wrong.** It was first written here as "fabricated —
appears in no committed result", on the strength of a search of the committed
tree of one branch. Study 5 is not committed to that branch; it lives in a
scratchpad worktree. The claim was false, it was published in this file, and it
was caught by the same cross-vendor review that produced item 9. That is finding 5
below biting the person writing the corrections: **evidence scattered across
uncommitted worktrees produced a false claim about this project's own record.**
The entry is left in place, corrected, rather than quietly rewritten.

**2. The arm-A-versus-arm-B comparison, in both directions.**
`+2.69 F1` (p = 0.67, 7 non-tied pairs) then `−1.19 F1` (p = 0.447, 18 usable
pairs). It changed sign between studies, and it is confounded: arm B's generator
sees a different prompt entirely. It measures generation variance. It should not
be quoted as evidence for the audit's value **or** against it.

**3. Confirmation rate 100%, false-positive rate 0%.**
1/1 in study 1, 23/23 in study 2. Both reports gave the intervals; the summaries
did not. `RESULTS-3.md` supersedes both at **73%**, on one task and one vendor
pair.

**4. "The auditor's precision is 100%" as a product property.**
It was 2/2 and 4/4. Already corrected in `RESULTS-3.md` to 73%; the withdrawal is
recorded here because the "100%" form outlived the report that retired it.

**5. "Changing the auditor model does nothing."**
The arm varied the model **within one vendor**, on n = 10, because the second
credential was occupied by the generator. What that licenses is "a stronger model
from the same vendor did not help on ten samples". The cross-vendor negative this
was taken to establish **has never been run**.

**6. Study 4's −6.20 replay floor and the 25% growth threshold.**
Fitted on 25 observations, falsified on 16 held out. Already withdrawn in effect:
the default is 0, and `repair.max_document_growth` does not exist on
`fusion/evidence-authority` at all.

**7. Study 1's +4.55 on the eleven untouched instances.**
The report itself calls this framing and variance. It should not appear in any
summary.

**8. Any CLEAR absolute placed beside the ExpertLongBench leaderboard.**
The scorer is a reimplementation; the comparison is not licensed.

**9. Study 4's primary outcome is conditioned on a post-treatment variable.**
This is the most serious item here, and unlike the others it was **not** found by
this project. An independent reviewer from a different vendor found it; the
recomputation below was then reproduced independently before it was accepted.

The preregistration names the primary outcome as the revision delta "for each
instance **where the loop revised at least once**". But the treatment is a change
to the revision scope rules, and it therefore helps decide whether a revision
happens at all. Conditioning the analysis on that event selects on a consequence
of the treatment, which opens a path between the arms that has nothing to do with
the effect being estimated. Selecting on a post-treatment variable is a
recognised way to manufacture an effect where none exists.

The size of the difference it makes:

| analysis | n | effect |
|---|---|---|
| as published, conditioned on both arms revising | 7 | **−19.60 F1** |
| unconditional, all paired instances | 16 | **−4.01 F1**, 95% bootstrap CI [−16.54, +8.33] |

The unconditional estimate is not distinguishable from zero. **"Revision is net
negative" is withdrawn as a finding.** What survives is the descriptive
observation that where a revision did occur it was often harmful, which is a
different and much weaker claim, and cannot carry a change to a shipped default.

This is why the proposed report-not-revise default was correctly stopped before
it shipped. The evidence for it was an artefact of the analysis.

**10. Study 3's "+2.04 F1 — the draft did not fall."**
Withdrawn against a floor measured on its own estimand. Study 5B ran three
replicates **including generation**: draft F1 9.72, 10.42, 6.94, **SD 1.84**.
+2.04 does not clear it. This is the reassurance that made splitting the rules
look free, and it is now unsupported: the recall gain from splitting survives
easily (2% to 23.5%), but the claim that it cost the first draft nothing does
not. Whether it costs anything is unmeasured, not shown to be zero.

Study 2's "a stronger auditor model moved recall from 2.0% to 3.8%" falls to the
same floor, which is the second and better reason to withdraw it (the first,
item 5, is that the arm varied the model within one vendor).

**11. "The cross-vendor auditor sees more." — the premise itself.**
Tested at n = 30 and **not supported, in the opposite direction**. The
cross-vendor auditor recalled **19.8%** of the defects CLEAR found; the generator
judging its own work recalled **31.7%**. Paired **−11.8 pp, CI [−19.2, −4.1]**,
exact Wilcoxon p = 0.0115, and −13.6 pp under the deterministic mapping. Worse on
17 instances, better on 3. The earlier n = 10 result was not a fluke; it was this
effect underpowered.

Stated against itself, as the study's author does: this is the weakest result in
that study. −11.8 pp is smaller than 2 SD of the same statistic at n = 8, it
clears only after scaling to n = 30, and Bonferroni over the study's eleven
comparisons gives 0.127. What supports it is that all five independent estimates
of it are negative.

**What replaces it is larger and cleaner.** `cross` gated **80.0%** of increments
against `self`'s **3.3%**: +76.7 pp, McNemar **p = 2.4 × 10⁻⁷**, 23 discordant
pairs with none pointing back. `cross` filed **all 48** of its findings as
BLOCKER. `self` raised **more** findings (64), filed **61 as ADVISORY**, and was
the **most precise** arm at 82%. Both registered kill criteria cleared, and both
results clear the noise floor outright.

**The defensible sentence is "a stranger is less tolerant", not "a stranger sees
more."** The self-audit does not fail to notice; it notices and forgives. That is
a severity mechanism, and it has been sold as a recall mechanism.

**And "vendor" may be the wrong axis.** `sibling − self` = **−22.2 pp**
(p ≈ 2 × 10⁻⁵): two models from the *same* vendor differ by nearly twice what the
two vendors differ by. What the invariant appears to buy is distance from the
author, not distance from the training corpus. This is a product question, not a
measurement one, and it is open.

---

## The four headline findings, restated

Four findings were carried out of this measurement programme as its results. The
cross-vendor review reached all four. None survives in the form it was stated.

**1. "Revision is net negative."** Withdrawn (item 9). The unconditional effect
is −4.01 F1, CI [−16.54, +8.33]. A second defect compounds it: `report2.py`
records one first-to-final delta per *revised instance* while calling it a
revision, so multi-round changes collapse. Study 3 has 25 revised instances but
**36 transitions**; per transition the figure is −7.64, not −11.01, and the
fixed/broken split is 5/19, not 3/17. And the pooled `p = 0.0014` is not valid
evidence: arms S, R and X change the constitution, the auditor's context and the
revision prompt, and their per-arm means are **−13.56, +5.83 and −14.42**. Pooling
them yields a configuration-weighted mixture, and the 25 observations contain only
18 unique sample ids, so the sign enumeration assumes an independence the data do
not have. **Surviving claim: none.** The direction is suggestive; the number, the
unit and the inference are all withdrawn.

**2. "The constitution, not the model, is the recall bottleneck."** Not
established as causal. The comparison sets shipped B's 4/201 over 40 instances
against 10-instance arms, and **every draft in those arms differs byte-for-byte
from shipped B's**. Arm B′ also changes the generator prompt. No confidence
interval or paired test was supplied for the recall contrast. The micro rates
reproduce; the attribution does not. **Surviving claim: on ten matched instances,
recall differed markedly across rules conditions, on drafts that also differed.**
The clean version of this experiment — re-auditing identical frozen drafts under
each condition — has not been run and is cheap.

**3. "The constitution poisons the generator" (+24.07 F1).** n = 4, no confidence
interval. The four differences are **+16.67, 0, +22.22, +57.41**. One instance
supplies most of the effect. The point estimate reproduces; the uncertainty was
never stated and is extreme. **Surviving claim: a hypothesis worth a real n.**

**4. "Cross-vendor's value is low false positives, not higher recall."** The
false-positive half is the strongest thing here and is not withdrawn. The recall
half is: the +8.9-point advantage rests on **five discordant pairs that all point
one way**, so a percentile bootstrap cannot generate a negative resample and
mechanically returns a positive lower bound. Exact McNemar gives **p = 0.0625**.
The interval [1.8%, 17.9%] does not establish exclusion of zero, and "real in
sign" is not supported. Four of the 56 stratum-P cases are also **timeouts rather
than observed assertion failures**, which contradicts the stated ground truth and
moves recall from 5/56 to 5/52. **Surviving claim: cross-vendor audit flags fewer
correct solutions, which is the number that decides adoption; its recall advantage
is not established.**

## What the review did not find

Stated because negative findings are results, and these were the two that most
threatened the programme:

- **CLEAR's core algorithm is correct.** The full-checklist denominator, the
  precision and recall directions, the per-sample harmonic F1 and the sample-level
  aggregation all match the paper's procedure. No chain-of-thought reaches the
  extractor or comparator. The reimplementation risk that `EXPERIMENT_RECORD.md`
  §6 names as permanent is smaller than feared, though it remains real: the
  scorer does silently coerce malformed mapper replies to `"N/A"` instead of
  rejecting them, and the raw replies were not retained, so the realised impact
  cannot now be measured. Retain them from here on.
- **No hidden-test leakage in the code study.** Not through prompts, imports,
  fixtures, caches, or the generated solutions' filesystem behaviour. The
  population reproduces exactly: C = 455, P = 56, F = 29. Every arm count and
  McNemar p regenerates from the committed records. The weaker claim that
  should replace the report's wording is "not present in runtime prompts or tool
  inputs", since HumanEval+ and MBPP+ predate the models and pretraining
  contamination cannot be excluded by runtime isolation.
- **No p-value was copied from an unrelated comparison.**

## Withdrawn framing

Four prose studies have run over **one task, one 50-row corpus, one
generator/auditor vendor pair**, drawing from the same 50 rows. Nothing in the
prose line is an independent replication at the corpus level. The
multiple-comparison clause in `EXPERIMENT_RECORD.md` §4 applies to the line as a
whole, not to each study as if it were the first.

---

## What no correction touches

**No shipped default rests on a withdrawn number.** This was checked, not assumed.
`authority.lone_model_blocker` remains at the conservative `block`, and D144
states in terms that the default "moves when finding-states produce a confirmation
rate, not before". The strictness dials were sequenced the same way. Where the
summaries drifted, the decision discipline held: the project declined to set
defaults on the numbers now being withdrawn.

**The code study survives intact.** It has model-free ground truth (tests that
pass or fail), a measured noise floor, and a false-positive population. Its
finding — that cross-vendor audit's value is low false-positive rate rather than
higher recall — is not affected by anything above.


## On how item 9 was found

Every other item on this list was found by this project re-reading its own
reports. Item 9, the largest, was not: it came from a reviewer at a different
vendor, reading the same committed records, after several same-vendor review
passes over the same study had missed it. The recomputation was then reproduced
here from the archived run directories before the finding was accepted, which is
the only reason it appears as fact rather than as a claim.

That is this project's own thesis, tested on the project itself, with the project
as the thing found wanting. It belongs in the record as evidence, not as an
embarrassment: a same-vendor reviewer sharing the authors' assumptions did not
see the assumption. A reviewer that did not share it did.

## Study 22 (injection) — both headline figures withdrawn, 2026-09-16 and 2026-09-20

**97.8% and 84.2% are withdrawn. The study gives claim C4 no prospective test.** It was built
to test prospectively what study 21 found post hoc, on a population where
"specification-determined" would be fixed by construction. The construction does not deliver
that property.

Two cross-vendor reviews refused quotation, and the author's own check of the implementation
went further than either asked. F6 was registered as recording the witness **and** recovering
the first failing hidden input by study 21's witness path; it is `bool(obj.get("witness_input"))`
— a truthiness check that never recovers, never executes, and never connects the quote, the
named class, the witness and the failure. Study 21's `witness_for` exists and is never called.
F2 to F5 each accept cases their registered wording excludes, demonstrated by counterexample in
round 2 (`RESULTS-INJECT.md` §5). No filter in this study establishes specification entailment,
and **no repair of F6 alone would have**: recovering the input and executing a witness shows the
edit changes behaviour on an exercised input, not that the specification entails the expected
value there.

So 97.8% conditions on a gate that its own measurement shows selects for detectability — the 40
instances the gate refused are caught 31 times in 40 — and 84.2% removes that gate but leaves a
denominator of "small injected edits that survived a sparse visible suite and failed a hidden
one". Neither is a recall of "defects the specification determines".

**Three corrections to the withdrawal itself**, all from round 2 and none in the direction that
would have made the self-criticism cleaner. F6 is a truthiness check, not a "non-empty string
check": 102 of the 281 recorded witnesses are lists, not strings. Amendment 7 implied F6 *as
registered* would have sufficed; it would not. And the withdrawal had not reached the executable
machinery — `numbers.json` and `tables.md` are standalone artefacts and carried the withdrawn
population label with nothing to mark it, the splice registry still required a withdrawn
sentence as an anchor, and four preregistration passages still argued the conservativeness case.
All now carry the withdrawal, emitted by the generator so a regeneration cannot drop it.

**What survives, as description rather than as a test.** Round 3 of the review found the earlier
"nothing remains quotable" withdrew too much, and it is right: the study is evidence about this
construction process and these archived auditor responses, which is narrow but not nothing. The
auditor blocks these injected edits far more often than the natural residual (90 of 92 against
11 of 92 twins; 79 discordant pairs one way and none the other); the edits the gate refused are
blocked 31 times in 40, which is what killed the conservativeness argument; and a probe separates
the two sets at 96.7% on the items it answered, between 79.9% and 97.3% once the 32 unparsed are
counted at either extreme. **None of that identifies what the auditor is responding to.** The
paired contrast isolates the edit, cues included, and naming was never adjudicated.

**Three corrections round 3 made to this entry's own first version**, each verified here before
acceptance. The self-announcing count is **19** archived instances by a defined case-insensitive
search for added `BUG`/`DEFECT` comments, not seven; only `b2:Mbpp/643` is in I, and removing it
gives 89 of 91. The probe's model is **one of the two gate models**, so it is not the independent
check it was described as, and its two arms share no problem, so it may be separating task sets
rather than edited code. And the claim that the published intervals could not be reproduced was
false: they reproduce exactly at the registered seed 20260916, which is `BOOT_SEED`; a later
`+ 70` offset in the regeneration, not the original computation, was what moved them.

**What would give C4 its prospective test**: a population whose specification-determinedness is
established by someone other than the injector.

Found: the reviews of 2026-09-15 and 2026-09-20, plus the author's own reading of `inject.py`
between them. Reproduced from the archive before acceptance — the 179/102 witness split, the
31-of-40 gate-rejected recall and the filter counterexamples were each recomputed here.

## Standing

Withdrawal is not retraction of the line of work. Every number here was produced
by a study that recorded enough about itself to be checked, which is why it could
be checked. The record is what the corrections are made of.

**12. "The code noise floor is 1.8 points on P."**
Restated. 1.8 was the difference between one specific pair of draws (study 1's
`cross` and `cross-replicate`) — the narrowest of what turned out to be three
pairwise comparisons. Three full draws of the shipped architecture over all 290
instances (`records/explore/`) give a **widest pair of 6.4 points at n = 110 and
9.1 on the confirm half at n = 55** (11, 7 and 6 of 55). The stratum-C column,
on which the adoption constraint is written, is stable at 5, 5, 4 of 74. Every
statement in this record that reads an effect against "1.8 points" should be
re-read against 6.4 at n = 110; the ones in `RESULTS-2.md` (+9.1 recall) and
`RESULTS-EXPLORE.md` (`tri_union`, `hc_u_dc`) survive it, the rest do not.

> **Two numberings from item 13, by merge.** The provenance line (this branch) and the
> ceiling study (`study/ceiling`, merged 2026-09-06 after its twenty-first review)
> each continued the list from item 12 in their own worktree. Renumbering either would
> break the citations inside `RESULTS-CEILING.md` and twenty-one archived reviews, so
> both sequences stand: **the provenance line's items 13–31 first, then the ceiling
> study's items 13–30**, each headed. A citation of "item N" in a ceiling document means
> the ceiling sequence; anywhere else, this line's. Item 32 onward continues this line's.

### The provenance line — items 13–31

**13. "Even with every extension the containment rule does not reach §6's 2%
line, and reaching it depends on the generator's transcription discipline."**
Withdrawn as stated. `docs/design/CONTAINMENT_RULE.md` §5 computed the residue
over **all 401 resolvable rows** — 12 = 2.99% [1.72, 5.16] — but
`PROVENANCE_CHECKS.md` §6's line is *of numbers that **do trace** to the source,
no more than 2% blocked*, and 401 includes rows that do not trace. The hand
gold (`benchmarks/expertlongbench/RESULTS-GOLD.md`) supplies the missing
denominator: 10 of the 12 residual blocks are blocks the gold calls **right**, so
on §6's own estimand the extensions alone land at **0.62%** (draft-clustered
bootstrap [0.00, 1.55], **uncalibrated** per EXPERIMENT_RECORD §10 — it combines
a census with a sample and its coverage is not yet simulated). The `(a)` and
`(c)` skill sentences are still worth writing; they are no longer what stands
between the check and its design target. §5's block-rate ladder (13.22% → 10.47%
→ 5.74% → 2.99%) is arithmetically correct and reproduces exactly; only its
reading against the 2% line is withdrawn.

**31. Arm 4's first record quoted the corpus, and misfiled a new failure class under a
licensed one.** (The ceiling study's own items, 13–30 on `study/ceiling`, follow this line's items below; see the note at the section head.) The Arm 4 results file, the
records emitter's comments, D161 and the handbook quoted short source phrases — the
ranges, the list, the en-dash units and the hyphenated phrase behind the nine wrong
blocks — in a commit whose own text said the corpus was "not redistributed and not
committed". The independent review of the report found it. Every excerpt is replaced
by a description of its shape, and the commit that carried them was rewritten out of
the unpushed branch's history (the archive keeps the located lines, under the licence).

The same review found the two en-dash rows filed as M9c/E6 — "one unit, two Unicode
renderings" — when E6 is a fold applied at comparison time and these rows fail earlier,
in tokenisation: an EN DASH is a boundary to the scanner and `_EXPONENT_TAIL` names only
the ASCII hyphen and U+2212. That is a new class, M10, with no rows in the frozen gold;
it does not inherit E6's licence, and "eight of nine are licensed extensions" was
therefore false — six are. RESULTS-ARM4 §1 and D161 ruling 2 are rewritten; the
projection is stated at both 3 of 189 and 1 of 189. Smaller corrections from the same
review: "not above Arm 3's `uncited`" was false against arm B (7.77% > 6.80%) and is
now "between A and B"; zero-event bootstraps are printed as 0.00–0.00% rather than
"—"; "the false-pass class did not reappear" is narrowed to the 50-row sample's
interval; the seven rule-code disagreements between the labellers are listed in
`GOLD-arm4.csv` rather than silently resolved; and the run's untracked-directory
git status at start is reported as a deviation. The second review found three of
these corrections incomplete: the 1 of 189 projection had been given the Wilson
interval of 1 of 190 (the unit-shortening row's), D161 still said the false-pass class
"did not return", and the handbook's copy of the `uncited` sentence was missed; all
three are fixed in the same file set.

**32. The design's line-scoped coincidental-containment rate was zero by construction.**
`provenance_probe.py` (Arm 1, §6 of `docs/design/PROVENANCE_CHECKS.md`) named the
"owner" lines of a pair as every line its own reader found the pair in, excluded them, and
then asked the same reader whether the remaining lines held the pair — which no remaining
line could. The **0.0% (0/1825)** quoted in PROVENANCE_CHECKS §6 (three places),
CONTAINMENT_RULE §2 and §3, and the probe's docstring is therefore not a measurement of
anything; the file-scoped 27.7% (596/2150) is a real measurement and stands. Study 13's
first probe inherited the shape (owners by `contains_pair`, others tested by
`contains_pair`) and reported 0/3910; the third review of slice 7 found it. The
instrument is rebuilt in `study13/probe.py`: the owner line is the one the generator's own
quotation names, the wrong lines are the rest of that source (and, file-scoped, lines of
other sources), and the containment test is the shipped matcher — on Arm 4's 186 traced
pairs that is **5/930 = 0.54%** line-scoped and 3/930 wrong-source, under base and E3
alike. The §6 "≤ 5%" bar is therefore met by a real number for the first time; the
earlier slices' kill conditions did not rest on it (they used the gold's labelled panel).
PROVENANCE_CHECKS §6 carries one dated note; the figure's other two appearances in that
file and its two in CONTAINMENT_RULE carry an inline pointer to this item; the probe's
docstring and output label say what its line-scoped number is. Found by the third cross-vendor review
of slice 7; the four earlier reviews of the design that quoted the number did not.

### The ceiling study — items 13–30 (numbered on `study/ceiling`)

**13. "The self-audit sees more than the stranger" — restated again, and now with a
measured ceiling on the other side.**
Item 11 withdrew "the cross-vendor auditor sees more" on the strength of a prose study at
n = 30 in which the generator judging its own work recalled **31.7%** against the
cross-vendor auditor's **19.8%**, and replaced it with "a stranger is less tolerant".

Study 8 measures the same contrast on code, against model-free ground truth, with eight
independent readings per family over 110 defective solutions, and the ordering at the
ceiling is **the other way round**: the generator's own model reaches **17.3% (19/110)**
union recall at eight readings, fitted asymptote **16.6%, 95% CI [8.1, 26.3]**; the
cross-vendor auditor reaches **30.0% (33/110)**, fitted asymptote **31.5% [21.7, 45.6]**.
The preregistered primary outcome **A(self) − A(cross) = −14.9 points, 95% bootstrap CI
[−32.1, −2.3]** over problem clusters, and the model-free raw difference at eight readings
is **−12.7 points [−25.0, −0.9]**.

These two results are not in contradiction — different task, different ground truth, and a
different estimand (a single-draw recall against an asymptote over eight draws). What must
change is the summary sentence carried out of item 11. **The direction of the self/cross
recall gap is task-dependent and has now gone both ways**, and neither direction should be
quoted as a property of self-audit. The false-positive half has gone the same way every
time and is not withdrawn: the self-auditor flags more correct work — **24.0% against
16.0%** at eight readings in study 8, and **13 of 56 against 3 of 56** in its closed-loop
arms (+17.9 points [3.6, 24.1], exact McNemar p = 0.0129).

**14. "AI self-audit raises accuracy" was never measured until now, and it does not.**
The programme has measured what auditors *notice* seven times and what the loop *achieves*
once, in a study whose primary outcome was later withdrawn for conditioning on a
post-treatment variable (item 9). Study 8 measures it unconditionally: over a frozen paired
sample of 112 instances, the generator's own model auditing and then revising its own code
changed the fraction passing a hidden test suite by **+0.89 points, 95% exact CI
[−3.16, +3.99], exact McNemar p = 1.0000** — 3 of 56 wrong solutions repaired, 2 of 56
correct ones broken. The preregistered kill condition fired. **No claim that self-audit
raises accuracy is supported by this programme's evidence**, and any planning document that
assumes it should be re-read against `benchmarks/code/RESULTS-CEILING.md`.

What did move: adding one rule to the constitution telling the auditor to find what the
visible tests do not cover raised flags on defective code from 10 of 56 to 25 of 56
(**+26.8 points [12.9, 30.3], p = 0.0003**) and the loop's net accuracy to **+8.04 points
[1.06, 11.16], p = 0.0225**. That is a **secondary** outcome that does not clear the
study's own Bonferroni threshold over twelve planned comparisons (0.00417), and it costs 7
additional false alarms on 56 correct solutions. It licenses a larger confirmatory run, not
a default change.

**15. Study 8's "95% exact" paired intervals — withdrawn, and the method replaced.**
The first committed version of `benchmarks/code/RESULTS-CEILING.md` reported every paired
binary difference with an interval built by taking a Clopper–Pearson interval for the
direction probability **conditional on the discordant pairs** and rescaling it by the
**observed** discordance fraction D/n. Conditioning is legitimate for McNemar's test. It is
not legitimate for an interval on the unconditional risk difference, because D/n is itself
an estimate and its uncertainty is thrown away.

An independent cross-vendor reviewer found this, and it reproduces exactly: enumerating
D ~ Binomial(112, 0.1) with every discordance beneficial gives that construction a coverage
of **0.4162688657**, not 0.95. The headline `self-loop` interval **[−3.16, +3.99] is
withdrawn**, as is every other paired interval in that version.

**What replaces them** (preregistration amendment 4): the problem-cluster percentile
bootstrap as primary, with Tango's unconditional score interval and a Berger–Boos-restricted
exact unconditional interval as checks. Measured coverages 0.960 and 0.998. The headline
becomes **+0.89 pp, cluster CI [−3.54, +5.88], Tango [−3.98, +6.06], exact unconditional
[−6.70, +8.48]**.

**No point estimate changed, and no conclusion changed.** The kill condition fires under the
withdrawn interval and under all three replacements. This entry exists because the interval
was published, not because the finding moved.

Two further corrections to that report, from the same review, both reproduced before being
accepted:

- **"Exactly one secondary contrast clears the correction threshold" was false.** The
  preregistration planned twelve comparisons; **sixteen** were computed, the highlighted
  contrast was not among the twelve, and a second contrast also cleared the threshold. The
  report now carries a full planned/performed/exploratory inventory, a single correction
  family of sixteen, and labels every flag contrast exploratory. **Five planned comparisons —
  the mixed and `astra` asymptote contrasts — were never delivered and are unmeasured.**
- **"The referent raises accuracy" was overstated.** +8.04 pp is the referent arm against its
  own baseline; its exact unconditional interval contains zero. The contrast that isolates
  the referent, against `cross-loop`, is **+5.36 pp, CI [−0.89, +12.07], p = 0.146**. What
  survives is that the referent **moved what the auditor flagged** (+26.8 points on
  stratum-P flags, exploratory), not that it raised accuracy.

**16. "No number had left the harness" — false, by 99 seconds.**
`RESULTS-CEILING.md`'s first version said a swapped Clopper–Pearson tail was caught before
any number escaped. `git show 1a66571:benchmarks/code/records/ceiling/tables.md` carries the
headline interval as **[+3.16, −1.93]**, committed at 18:46:39; the fix landed at 18:48:18.
An erroneous number was in a committed results artefact for that interval. It never reached
prose — the report was first committed at 20:55:51 — but the claim as written was wrong and
is corrected in that report's deviations.

**17. Study 8's replacement intervals were also wrong — the nuisance bound — and its
coverage claims were overstated in both directions.**
Item 15 recorded the withdrawal of a 0.416-coverage interval and its replacement. A second
independent cross-vendor review found the replacements defective in turn.

Both `tango_score_interval` and `exact_unconditional_interval` bounded the nuisance
`q = p_c` above by `(1 − |δ|)/2`; the feasible bound is `(1 − δ)/2`. Correct for a
non-negative difference, wrong for a negative one. Re-executing the pre-fix code:
**Tango covered 0.960 beneficial / 0.953 detrimental; the exact grid covered 0.997
beneficial / 0.0752249063 detrimental** — the last reproduced to ten digits before the fix
was made. *Corrected 2026-09-06: an earlier version of this entry attributed 0.960 to the
exact grid. It is Tango's.* The coverage collapse was confined to the exact grid, and
pre-fix Tango covered adequately while still returning wrong intervals
(`tango_score_interval(20, 70, 112)` gave [−0.539, −0.358] against [−0.577, −0.291]) — so a
coverage figure was never going to catch this, and a **sign-symmetry test** is what does.
Corrected; detrimental coverage is now **0.953 (Tango) and 0.984 (exact grid)**, and a
sign-symmetry test plus a two-directional coverage enumeration are in the suite.

Separately, item 15's replacement claims were too generous. Measured at n = 112: the
primary problem-cluster bootstrap covers **0.924 in the beneficial scenario and 0.953 in
the detrimental one** — the committed simulation gives 0.933 independent and 0.897
clustered — and the exact unconditional check is **grid-approximated** over 41 nuisance
points with no bound on the missed supremum, so "never under-covers" is withdrawn.

*Corrected 2026-09-06 after a third review:* this entry previously said "every interval
published from study 8 should be read as roughly 2 to 5 percentage points optimistic". That
**generalises two scenarios to every estimand and is withdrawn.** The supportable statement
is narrower: the idealised bootstrap under-covers in the beneficial scenario (0.924 against
0.95), the two checks do not under-cover in either scenario tested, and **coverage under
study 8's actual clustered design is unvalidated**.

**No point estimate changed, and no conclusion changed.** No result in study 8 is affected
by the nuisance-bound defect: every paired difference in it has b ≥ c except one, whose
interval is unchanged to the displayed precision.

**18. "Exactly one contrast clears the corrected threshold" — false, twice.**
Item 15 corrected the first version's multiplicity claim and then repeated the error in the
correction itself. **Two** contrasts clear Bonferroni over the family of sixteen, and they
are the same effect measured two ways: `referent-loop` − `cross-loop` on stratum-P flags
(+26.8 points, exact McNemar p = 2.7 × 10⁻⁴, cluster sign-flip p = 8.5 × 10⁻⁴) and on
pooled P + C flags (+19.6 points [11.7, 27.8], p = 3.0 × 10⁻⁶, cluster p = 1.0 × 10⁻⁵).
Both are exploratory: the preregistration named outcome contrasts, not flag contrasts.

**19. Study 8's "self-audit did not raise accuracy" — restated.**
The measured net change was +0.89 points with every interval containing zero **on both
sides**. That licenses "no improvement was established", not "did not raise accuracy". At
n = 112 the study's power was **0.32 against a true +5-point improvement, 0.60 against
+7.5, and 0.81 against +10** (two-sided exact McNemar, worsening rate held at the observed
2/112). An improvement smaller than about 7 points would probably have been missed. The
title and opening of `RESULTS-CEILING.md` are corrected accordingly.

**20. Study 8's coverage figures were mislabelled by scenario, and over-generalised.**
Item 17 gave the detrimental-direction bootstrap coverage as 0.924. That is the *beneficial*
scenario's figure; under `C ~ Bin(112, 0.5)` it is **0.953**. Item 17 also said every
interval published from study 8 "should be read as roughly 2 to 5 percentage points
optimistic" — a generalisation from two independent-instance scenarios to every estimand
under a clustered design. Both are corrected in item 17 itself and in the report.

The supportable statement: **the idealised percentile bootstrap under-covers in the
beneficial scenario (0.924 against 0.95); the two check intervals do not under-cover in
either scenario tested; and coverage under study 8's actual clustered design is
unvalidated.** The exact grid check's 0.984 is additionally sensitive to inward endpoint
rounding — at (0, 44, 112) the grid test accepts δ = −0.5 while bisection returns
−0.499999993614 — and counting that instance as covered gives 0.9895.

**21. `RESULTS-CEILING.md`'s claim that its consistency guard catches every absent prose
interval — false, and the guard has been rewritten.**
The third cross-vendor review showed the guard passed when a quoted interval was mutated by
0.01, and passed when the headline was replaced with `[−99.99, +99.99]`. It rounded to one
decimal, allowed 0.051 of tolerance, ignored the Unicode minus and the leading `+`, and
accepted any interval present anywhere in `numbers.json` regardless of which quantity the
sentence described. Rewritten to compare at displayed precision with zero tolerance and to
bind the headline and primary-outcome spans to their `numbers.json` paths; the review's
mutations are committed as a test of the test.

Rewriting it caught two live defects immediately: a prose interval written `[+6.3, +43.8]`
where the record says **+43.7**, and a flag contrast whose exact unconditional interval was
quoted in prose but never computed into the record. Both fixed.

**This is the third time a defect in study 8's own checking apparatus was found by a reader
rather than by the author**, after the interval method (item 15) and the nuisance bound
(item 17). The pattern is worth stating plainly in the corrections record: **every defect in
this study's statistical machinery has been found by cross-vendor review, and none by the
author's own tests until those tests were rewritten in response.**

**22. Study 8 attributed a coverage figure to the wrong withdrawn method.**
Item 17, and the report and preregistration amendment it summarises, said the **pre-fix
exact-grid** interval covered 0.960 in the beneficial direction. **0.960 is Tango's.**
Re-executing the pre-fix code: Tango covered **0.960 beneficial / 0.953 detrimental**; the
exact grid covered **0.997 beneficial / 0.075 detrimental**. Corrected in all three places,
and the pre-fix estimators are now committed as runnable code with their coverages asserted
as tests, so a label about a withdrawn method cannot drift from its number.

The re-execution also corrects the shape of the story told in item 17. **The coverage
collapse was confined to the exact grid**, and **pre-fix Tango covered adequately while
still returning wrong intervals** — `tango_score_interval(20, 70, 112)` gave
[−0.539, −0.358] against the correct [−0.577, −0.291]. A coverage check in two chosen
scenarios was never going to catch that defect; a sign-symmetry test does.

**23. Study 8's blanket under-coverage claim survived its own withdrawal.**
Item 20 withdrew "every interval should be read as roughly 2 to 5 percentage points
optimistic". The sentence nonetheless remained in the report as deviation 19's own
conclusion. It is now struck through in place and marked superseded, rather than deleted,
so the deviation record shows what it said. **The live claim is the per-method,
per-scenario coverage table, plus the statement that coverage under the actual clustered
design is unvalidated.**

**24. Study 8 published two different intervals for the same number.**
The residual share — 57 of 110 stratum-P instances flagged by no reading — was bootstrapped
twice: once by the residual analysis (seed 20260912, **[40.0, 63.3]**) and again by the
timeout-sensitivity table's registered column (seed 20260923, **[40.4, 63.6]**). Both are
valid bootstrap estimates of the same estimand on the same data; they differ only by seed.
The report quoted each in different places as *the* interval for that number. The same
duplication affected the registered union recalls.

**Both code paths now use the canonical seed**, so the sensitivity table's registered column
is identical to the tables it is meant to be compared against, rather than a second
bootstrap of the same quantity. The published figure for the residual share is
**51.8% (57 of 110), problem-cluster CI [40.0, 63.3]**.

This was found while binding every rate in the report's opening and conclusion to the
specific `numbers.json` array its interval must come from. **No reviewer had caught it, and
no earlier guard could have**: both intervals were real numbers genuinely present in the
record, and every check up to that point asked only whether a quoted interval existed
somewhere — not whether it belonged to the number beside it.

**25. Who found what, corrected.**
An earlier version of this entry said that items 22, 23 and 24 "were found by tests written
in response to reviews". **That is false for 22 and 23, and it took credit that belongs to a
reviewer.** The fourth cross-vendor review reported both explicitly, as its findings 1 and
2: the coverage figure attributed to the wrong withdrawn method, and the blanket
under-coverage claim surviving inside deviation 19. The sixth review caught the
misattribution. The record, accurately:

| item | what | found by |
|---|---|---|
| 15 | the paired interval's 0.416 coverage | **cross-vendor review, round 1** |
| 17 | the nuisance-bound defect; overstated replacement coverage | **cross-vendor review, round 2** |
| 20 | coverage mislabelled by scenario; the over-generalisation | **cross-vendor review, round 3** |
| 21 | the consistency guard did not bite | **cross-vendor review, round 3** |
| 22 | 0.960 attributed to the exact grid when it is Tango's | **cross-vendor review, round 4** |
| 23 | the blanket claim surviving in deviation 19 | **cross-vendor review, round 4** |
| 24 | two different bootstrap intervals for the same number | **the author**, while rewriting the rate bindings that round 5 required |
| — | the swapped Clopper–Pearson beta tail (fixed at `7dc2620`, before round 1) | **the author**, by the author's own test |
| 26 | the reader sentence's interval was never bound; a reused label bound a rate to another family's array | **cross-vendor review, round 6** |
| 27 | seed BOOT_SEED + 7 declared unused while `numbers.json` recorded it as consumed | **cross-vendor review, round 6** |

**Eight of the nine numbered corrections above were found by cross-vendor review, plus
the author-found beta-tail defect that was fixed before round 1.** Of the two the author
found, item 24 emerged only because a reviewer had demanded a mechanism strong enough to
expose it — the rate-to-key binding — so the reviewer's requirement, not the author's
insight, is what made that discovery possible; the beta tail is the one defect the
author's own test caught unprompted.

*The claim is deliberately narrowed to the listed items.* An earlier version said "every
defect in this study's statistical machinery" was found by review, which is not true: the
**swapped Clopper–Pearson beta tail was the author's own find**, caught by the author's own
test and fixed at `7dc2620`, before the first review ran. That one belongs on the other
side of the ledger and is recorded in the report's deviations. The seventh review caught
the overstatement.

That is the study's own thesis, tested on the study, over six rounds. The honest summary is
not "tests written after reviews found further defects". It is: **a reader who did not share
the author's assumptions found essentially everything, and the author's checks improved only
when a reader specified what they had to catch.**

**26. Study 8's reader sentence was not covered by any check, and a reused label bound a
rate to the wrong family.**
`RESULTS-CEILING.md` carries a single sentence it asks a reader to carry away, quoting the
headline as **+0.89 pp with a problem-cluster interval of −3.54 to +5.88**. A declaration in
the consistency guard claimed that sentence's interval was checked by the mechanism that
binds the headline. It was not: that mechanism checks a different sentence. Replacing the
reader sentence's interval with a fabricated "+1.00 to +2.00", or deleting it, left every
test green. Separately, a binding rule anchored on the words "cost (" bound any matching
rate to **astra's one-reading false-positive array**, so an inserted sentence attributing
astra's 9.7% [5.3, 14.5] to the shipped auditor's eight readings — whose value is 16.0%
[10.1, 22.3] — also passed.

Both were found by the sixth cross-vendor review, reproduced, and fixed: the reader
sentence is now bound to `ceiling2.arms.self-loop.net_primary.ci95` with its prose "to"-form
parsed, every reused label carries its discriminating family and reading count, and a
further test fails if any binding rule matches more than once — which is how a sentence
slips under an existing rule's anchor. All three counterexamples are committed as tests.

**27. Study 8 declared a seed unused that its own records showed to be consumed.**
Both manifests stated that no contrast in the study exceeds 22 non-zero problem clusters,
so the sampled sign-flip path is never taken and `BOOT_SEED + 7` (20260915) is never drawn.
**`numbers.json` records the opposite, in plain text**: the pooled self-cross flag contrast
has **25 non-zero clusters** and its p value is annotated `"sampled, 200000 draws, seed
20260915"`. The claim was contradicted by the same file it shipped beside.

The cause was that the seed inventory instrumented one call site — the bootstrap — rather
than the random-number constructor. It now wraps `random.Random` itself, so every generator
is counted whatever path builds it: **34 distinct seeds over 205 constructions**, against
the 32 over 196 the narrower instrument had reported. Found by the sixth cross-vendor
review.

**28. "No published number was ever wrong" — false, and withdrawn.**
Deviation 34 of `RESULTS-CEILING.md` asserted that no published number had ever been wrong
across the review sequence, and that only the strength of the guarantee had been. **The
first half is false**, as the ninth cross-vendor review pointed out. Published numbers that
were wrong and were corrected:

| published | regenerated | corrected in |
|---|---|---|
| `referent−cross` net interval `[−0.88, +12.08]` | `[−0.89, +12.07]` | round 2 |
| referent P-flag exact interval upper bound `+43.8` | `+43.7` | round 3, item 21 |
| detrimental bootstrap coverage quoted as `0.924` | `0.953` for that scenario | round 3, item 20 |
| residual share published as both `[40.4, 63.6]` and `[40.0, 63.3]` | `[40.0, 63.3]` | round 6, item 24 |

The narrow claim that survives: **the synthetic re-attribution counterexamples in rounds 6
to 8 never appeared in a published version, and no empirical point estimate — no asymptote,
union, net, count or classification — has changed since the first version. Interval
estimates did change**, both when the interval method was replaced in rounds 2 and 3 and in
the individual corrections listed above. The sentence as written generalised the narrow
claim into one about the whole history, which the record contradicts.

*Superseded 2026-09-06:* the table above lists four corrections; the tenth review showed it
was incomplete. The complete list, cited by round, is in deviation 34 of
`RESULTS-CEILING.md` and covers fifteen corrected values across rounds 1 to 8.

**29. The consistency guard's stated scope exceeded what a lexical check can enforce.**
`RESULTS-CEILING.md` described its guard as failing the build "if any interval quoted in
prose is absent from `numbers.json`". Four edits pass it: a sentence naming two families,
which moves ownership by grammar while every token the guard wants is present; a claim
carrying an interval but no numeral, which is only membership-checked; a rate written in
words; and anything outside the opening and conclusion. None is fixable lexically.

The description is now exact — *a lexical editing guard for registered numeral templates in
the opening and conclusion: every registered rate must carry its bound interval adjacent and
its sentence must name its family; it does not parse grammatical ownership, does not read
rates written in words, and applies membership checks only outside those sections* — and the
four attacks are committed as passing tests that document the boundary. Found by the ninth
cross-vendor review, whose instruction was to narrow the claim rather than widen the guard.

**30. A build reported as "46 tests pass" had one failing test, and three coverage figures
were compared by nobody.** The eleventh cross-vendor review of study 8 ran the suite and
found `test_no_guarantee_words_outside_their_denials` red on a sentence of the report —
"Every rate carries a 95% … interval" — that the same commit had reported green. The count
was not the runner's; it was a claim. The sentence is rewritten, and from this round the
test count stated for a build is the runner's own summary line, copied.

The same review found the coverage binding described in deviation 38 incomplete: the
statistics suite compared eight of the artefact's eleven figures, so the withdrawn
conditional and both idealised-bootstrap coverages could be edited in the artefact and the
table together with every test green; the report test compared table cells but not the
column headers, so swapping the beneficial and detrimental columns was green; and a
coverage figure quoted in a sentence was checked by nothing. All eleven are compared and
the key set asserted; the headers' column order and every unsigned three-decimal figure in
a sentence about coverage are now read against the artefact.

The guarantee-word check itself exempted quoted spans and stopped scanning at its own
marker, so a forbidden phrase in quotation marks, broken across a line, or written after
the marker survived, and an allowed phrase reused as a bare assertion was green. Allowances
are now whole sentences, matched exactly and required to still occur; the check's tables
are excised precisely and nothing else is skipped; and the review's four attacks are
committed as cases that must be red. Deviation 34's correction table gains the rows the
reviews state that it lacked, one round citation is corrected (round 9, not 8), and its
"complete list" is now "the rows the reviews state". Twenty further sentences across the
report and both test files promised more than their checks do — "every interval", "cannot
drift", "the only rule", "finds them forever", "every inferential quantity", "regenerates
every table" — and each is rewritten to what is checked.
