# Study 21 — the residual re-rated with the oracle question asked first

Preregistration: `rerate/PREREGISTRATION.md` (committed before any label; seed 20260914;
Amendment 1 committed after the residual result and before the first rating of 42 of the 53
flagged instances — 11 had been rated on the first sheet; Amendment 2 after the first review).
Raters: L1 the author; L2 `gpt-6-astra` through the Codex CLI, read-only, from the sheets alone.
Material: ceiling 1's archived residual dump (68 instances: the 57-instance all-family residual
and the 11 instances only the third family flagged) and, under Amendment 1, the 53 stratum-P
instances some draw did flag, built with the same dumper. Each sheet item shows the specification,
the visible suite, the candidate, the canonical solution and the witness (the first failing
hidden inputs with expected and actual values) — and, as the first review found, **the instance
id inside the hidden-outcome record**: the sheets withheld the prior category and (on the
first sheet) per-item flag status, not identity, and L2's second prompt named the sheet
"flagged". Amendment 2 re-runs L2 on one identity-stripped sheet of all 110 P instances (Table
5). No API spend; L2 ran on the Codex subscription.

## The finding

**Under a rubric that asks "does the specification determine the expected value?" before "did
the visible suite exercise this input?", and defines both categories by specification
entailment, the residual is not mostly unexercised edge: 44 of 57 are consensus
`ambiguous-oracle` — and so are 24 of the 53 instances the auditors flagged.** "Oracle-defined"
below means that operational label, nothing more.

<!-- tables:begin -->
### Table 1 — consensus category of the residual, oracle question first

Unit: the instance; primary interval the problem-cluster percentile bootstrap (seed 20260914, 10,000 resamples); Wilson beside it (ignores clustering). `disputed` = the two raters differ; counted toward neither category. Counts of five or fewer are quoted as counts. The sheets carried the instance id (Amendment 2).

| population | n (problems) | category | consensus count | share [95% cluster CI] (Wilson) |
|---|---:|---|---:|---|
| all_families_residual | 57 (34) | `timeout` | 3 | **3 of 57** — quoted as a count, not a rate |
| all_families_residual | 57 (34) | `ambiguous-oracle` | 44 | **44 of 57** (77.2% [62.1, 91.1]; Wilson [64.8, 86.2]) |
| all_families_residual | 57 (34) | `unexercised-edge` | 2 | **2 of 57** — quoted as a count, not a rate |
| all_families_residual | 57 (34) | `disputed` | 8 | **8 of 57** (14.0% [3.4, 26.8]; Wilson [7.3, 25.3]) |
| sheet_68 | 68 (40) | `timeout` | 5 | **5 of 68** — quoted as a count, not a rate |
| sheet_68 | 68 (40) | `ambiguous-oracle` | 46 | **46 of 68** (67.6% [52.2, 82.1]; Wilson [55.8, 77.6]) |
| sheet_68 | 68 (40) | `unexercised-edge` | 9 | **9 of 68** (13.2% [3.0, 25.0]; Wilson [7.1, 23.3]) |
| sheet_68 | 68 (40) | `disputed` | 8 | **8 of 68** (11.8% [2.9, 23.0]; Wilson [6.1, 21.5]) |
| flagged_P | 53 (33) | `timeout` | 4 | **4 of 53** — quoted as a count, not a rate |
| flagged_P | 53 (33) | `ambiguous-oracle` | 24 | **24 of 53** (45.3% [28.3, 63.3]; Wilson [32.7, 58.5]) |
| flagged_P | 53 (33) | `unexercised-edge` | 23 | **23 of 53** (43.4% [25.0, 60.7]; Wilson [31.0, 56.7]) |
| flagged_P | 53 (33) | `disputed` | 2 | **2 of 53** — quoted as a count, not a rate |

### Table 2 — the two raters (disputed instances from both sheets)

| raters | agree | n | Cohen κ (six categories) |
|---|---:|---:|---:|
| L1 (author) vs L2 (`gpt-6-astra`) | 60 | 68 | **0.722** |

| disputed instance | L1 | L2 |
|---|---|---|
| `b1:Mbpp/142` | ambiguous-oracle | unexercised-edge |
| `b1:Mbpp/398` | ambiguous-oracle | unexercised-edge |
| `b1:Mbpp/594` | unexercised-edge | ambiguous-oracle |
| `b1:Mbpp/630` | other | ambiguous-oracle |
| `b1:Mbpp/792` | unexercised-edge | ambiguous-oracle |
| `b2:Mbpp/142` | ambiguous-oracle | unexercised-edge |
| `b2:Mbpp/398` | ambiguous-oracle | unexercised-edge |
| `b2:Mbpp/594` | unexercised-edge | ambiguous-oracle |
| `b2:Mbpp/630` | other | ambiguous-oracle |
| `b2:Mbpp/792` | unexercised-edge | ambiguous-oracle |

| raters, flagged sheet | agree | n | Cohen κ |
|---|---:|---:|---:|
| L1 vs L2 | 51 | 53 | **0.933** |

Test-retest on the 11 instances both sheets carry (rated twice, on sheets that carried the instance id; the flagged sheet's label used): L1 same 11 of 11, L2 same 11 of 11.

### Table 3 — ceiling 1's all-family union recall on the oracle-clean denominator (Amendment 1 secondary)

Rule: Amendment 1: (53 − a_f) / (110 − a_r − a_f); disputed count as not ambiguous. Interval: problem-cluster bootstrap over the 110 P instances' (flagged, ambiguous) pairs, seed 20260924; Wilson beside it.

| denominator | P | flagged by any draw | union recall at K_max [95% cluster CI] (Wilson) | residual share [95% cluster CI] |
|---|---:|---:|---|---|
| registered (ceiling 1) | 110 | 53 | 48.2% [36.7, 60.0] (Wilson [39.1, 57.4]) | 51.8% [40.0, 63.3] |
| oracle-clean (minus 44 residual + 24 flagged consensus-ambiguous) | 42 | 29 | **69.0%** [50.0, 86.4] (Wilson [54.0, 80.9]) | 31.0% [13.6, 50.0] |

The registered intervals are ceiling 1's residual-share interval and its complement. The oracle-clean intervals are bootstraps of a conditional estimand: the bootstrap for this conditional estimand has no committed coverage simulation; uncalibrated. The same holds for every category-conditioned interval in Tables 4 and 5: uncalibrated.

### Table 4 — POST HOC: ceiling 1's union recall by the defect's consensus category

Asked after Table 1's flagged counts were seen; not preregistered. Recall = flagged by any of the 20 draws.

| consensus category | n P instances (problems) | flagged | recall [95% cluster CI] (Wilson) |
|---|---:|---:|---|
| `timeout` | 7 (4) | 4 | **4 of 7** — quoted as a count, not a rate |
| `ambiguous-oracle` | 68 (34) | 24 | **24 of 68** (35.3% [22.1, 50.0]; Wilson [25.0, 47.2]) |
| `unexercised-edge` | 25 (13) | 23 | **23 of 25** (92.0% [75.0, 100.0]; Wilson [75.0, 97.8]) |
| `disputed` | 10 (5) | 2 | **2 of 10** — quoted as a count, not a rate |

### Table 5 — Amendment 2: L2 re-run on one identity-stripped sheet of all 110 P instances

The first sheets carried the instance id and L2's second prompt named the sheet (found by the first review); this pass strips both. L1's labels are unchanged (L1 cannot be re-run without memory of the first passes).

| quantity | value |
|---|---|
| L2 first labels vs identity-stripped pass, same | 108 of 110 (κ 0.963) |
| L1 vs identity-stripped L2, agree | 102 of 110 (κ 0.854) |
| residual consensus (L1 × L2 identity-stripped) | `timeout` 3, `ambiguous-oracle` 44, `unexercised-edge` 2, `other` 2, `disputed` 6 |
| flagged consensus (L1 × L2 identity-stripped) | `timeout` 4, `ambiguous-oracle` 24, `unexercised-edge` 23, `disputed` 2 |
| §3 kill restated | ambiguous 44 of 57, edge 2 of 57 — fires |
| oracle-clean recall restated | 29 of 42 = **69.0%** [50.0, 86.4] (Wilson [54.0, 80.9]) |

| post-hoc split restated | n | flagged | recall [95% cluster CI] (Wilson) |
|---|---:|---:|---|
| `timeout` | 7 | 4 | **4 of 7** — quoted as a count, not a rate |
| `ambiguous-oracle` | 68 | 24 | **24 of 68** (35.3% [22.1, 50.0]; Wilson [25.0, 47.2]) |
| `unexercised-edge` | 25 | 23 | **23 of 25** (92.0% [75.0, 100.0]; Wilson [75.0, 97.8]) |
| `other` | 2 | 0 | **0 of 2** — quoted as a count, not a rate |
| `disputed` | 8 | 2 | **2 of 8** — quoted as a count, not a rate |

### Table 6 — POST HOC: consensus `ambiguous-oracle` share, missed against caught

Not preregistered. Amendment 1 registered that both shares would be reported; it did not register their difference. The two groups are disjoint and together are the 110 P instances. 11 of the 56 problems contribute instances to both, so the bootstrap resamples the union of problems rather than each group independently (seed 20260964, 10,000 resamples, 0 replicates redrawn for an empty group).

| group | n (problems) | consensus `ambiguous-oracle` | share (Wilson) |
|---|---:|---:|---|
| residual — missed by every family | 57 (34) | 44 | **77.2%** (Wilson [64.8, 86.2]) |
| flagged — caught by at least one | 53 (33) | 24 | **45.3%** (Wilson [32.7, 58.5]) |
| **difference** | | | **+31.9 points** [9.6, 53.4] |

The comparison is NOT `sheet_68` against `flagged_P`: that sheet is 57 residual plus 11 flagged instances (Amendment 2), so it contains part of the group it would be compared with.

Being post hoc, this is a description of these 110 instances and not a test. It says what the two registered shares already imply -- what the auditors missed was more often specification-ambiguous than what they caught -- and nothing about why.
<!-- tables:end -->

The preregistered kill for the sentence "the residual is mostly unexercised edge" fires on both
of its conditions: consensus `ambiguous-oracle` is 44 of 57 (the bar was 30), consensus
`unexercised-edge` is 2 of 57 (the bar was 29). Of the 44, ceiling 1's classification had
called 39 `unexercised-edge` and 5 `spec-misreading`.

Amendment 1's secondary: among the 53 flagged P instances the consensus is 24 `ambiguous-oracle`
and 23 `unexercised-edge`, so the oracle-clean denominator is 42 instances, of which 29 were
flagged — union recall 69.0% [50.0, 86.4] against the registered 48.2% [36.7, 60.0]. The
registered number stays the quotable recall; this one says what it would be if the 68
consensus-ambiguous instances were struck from P. Two qualifications: the interval is a bootstrap
of a conditional estimand with no committed coverage simulation (uncalibrated); and
"oracle-clean" means "first witness not consensus-ambiguous", which does not certify the other
hidden failures of the same candidate.

The post-hoc split (Table 4) is the sentence the two preregistered numbers point at: of the 25
P instances both raters call spec-determined-and-unexercised, the twenty draws flagged 23; of the
68 both call oracle-defined, 24. It is post hoc — asked after the flagged counts were seen — and
it is a description of one substrate under one rule, not a preregistered estimate.

Amendment 2's identity-stripped L2 pass (Table 5) moves two labels of 110 (both readings of one
problem, from `ambiguous-oracle` to `other`; κ 0.963 against L2's first labels), leaves the kill
firing at 44 of 57 and 2 of 57, and leaves the oracle-clean recall and the ambiguous, edge and
timeout rows of the post-hoc split at the same counts (the disputed row goes from 2 of 10 to 2 of
8 and an `other` row of 0 of 2 appears). That is stability of L2's labels after the explicit
identity and status information was removed — not evidence that the information had no effect,
since the pass also changed the presentation, the order and the model's sampling — and it says
nothing about L1's.

Table 6 is the control the two registered shares invite and were not registered to supply: the
instances every family missed are consensus `ambiguous-oracle` 44 of 57, the instances at least
one family caught are 24 of 53 — a difference of +31.9 points [9.6, 53.4], an interval that
excludes zero. It is post hoc, so it is a description of these 110 instances and not a test, and
the interval is quoted for shape rather than as a decision rule. The comparison is the residual
against the flagged, not the 68-instance sheet against the flagged: that sheet is 57 residual
plus 11 flagged instances, so it contains part of the group it would be compared with, and the
+22.4 points such a comparison yields is an artefact of the overlap. Eleven of the 56 problems
contribute instances to both groups, so the bootstrap resamples the union of problems; resampling
the two groups independently, as the two-substrate contrast elsewhere in this programme may,
would break the clustering it exists to respect.

What the table does not say is why. A defect that survives every reading being more often
oracle-ambiguous is consistent with the reading that what limits these auditors is the
specification rather than the reading — and equally consistent with ambiguous instances simply
being harder in ways that have nothing to do with the oracle. Nothing here separates the two.

What the two raters were agreeing on, in shape: hidden inputs outside the class the
specification names (unsorted arrays for a function specified over sorted ones; dates not in the
stated format); hidden
expected values that follow from the dataset's reference implementation and not from the
prose (a truncating zip where the prose says "per digit"; a sentinel returned where the prose
says "check"; a count that includes or excludes the unrotated string; a name filter stricter
than the prose's); and inputs on which the prose entails the candidate's value and the hidden
suite asserts another. The consensus `unexercised-edge` instances are the ones where the prose
does determine the value and the visible suite never built the input (a negative bound; deeper
nesting than any visible example; floor division where the prose says division; an unhashable
element; a duplicate the count must pair).

## What this does and does not say

1. **The category depends on the rubric — and that is the result.** Ceiling 1's rule put
   `unexercised-edge` second and `ambiguous-oracle` fifth and defined neither by entailment; this
   study's rule puts the oracle question second, defines `unexercised-edge` as requiring
   specification entailment, gives `ambiguous-oracle` the one-sentence test, and uses two raters
   with a consensus rule. The same 57 instances go 46/57 one way and 44/57 the other. The study
   does not isolate which of those changes did it — ordering, definitions, or raters. What it
   does show is that the classification is not robust to the rubric, so the paper's claim (2) —
   "the ceiling is set by unexercised edges" — cannot be quoted in that form. What survives both
   rubrics is only the count of the residual and the fact that, under the second, most of it
   fails the entailment test.
2. **Raters and blinding.** L1 is the author of both rules and of the paper; L2 is a model of the
   same vendor family as one auditor under study (and as the first reviewer). Neither was blind
   to instance identity: the hidden-outcome record in every sheet item carried the instance id
   (the first review found this; the author had stripped only the header line). The sheets
   withheld the prior category from both, and the first sheet withheld per-item flag status (57
   residual and 11 flagged mixed without a marker) — withheld fields, which for L1 is not the
   same as ignorance: the author built ceiling 1's classification, knew which sheet was which,
   and saw the instance ids. On the second sheet L2's prompt named its status. The 11 instances both sheets carry were rated twice by both
   raters with identical labels (Table 2's retest line) — consistency, not a bound on bias.
   Amendment 2 re-ran L2 on one identity-stripped sheet of all 110 (Table 5). Agreement 60 of 68
   with κ 0.722 on the residual sheet and 51 of 53 with κ 0.933 on the flagged sheet. The
   preregistration asked for a human rater who is not the author; none was available. These are
   the study's largest limitations and they are not ones another labelling pass by these raters
   can remove.
3. **Duplicates.** Each sheet carries two candidates per problem for most problems (study 2's
   two batches from the same generator), with the same specification and often the same witness;
   the raters effectively read 40 and 33 problems (56 on the combined sheet). The problem-cluster
   interval is the one to quote.
4. **What "ambiguous-oracle" means here.** The rule's test is whether one sentence from the
   specification's own words entails the expected value and excludes the candidate's. It is
   deliberately generous to the candidate: an oracle that is stricter than the prose, silent on
   the input class, or contradicted by the prose all land here. A reader who thinks the dataset's
   reference implementation is the specification will call most of these unexercised edges, as
   ceiling 1 did. "Decidable" in the preregistration overstates the rule: "reasonable reading",
   "input class" and "neighbouring" are judgment terms, and a rater's failure to write the
   entailment sentence is evidence, not proof, that the prose lacks one.
5. **Nothing here re-runs an auditor.** Ceiling 1's union recalls, asymptotes and the arm
   differences are untouched; this study changes what the residual is called, not its size.

## Cost

No API spend. L2: three Codex CLI sessions (68, 53 and 110 items); L1: two readings, 68 and 53
items.
