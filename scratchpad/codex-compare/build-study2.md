# Build report — accuracy study 2

Branch `feat/accuracy-study-2`, worktree
`/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-study2`,
based on `fusion/evidence-authority` at `f9482ce`. **Not pushed.**

Full write-up: `benchmarks/expertlongbench/RESULTS-2.md`.

## Commits

| sha | what |
|---|---|
| `2a6f4a5` | the instrumentation, frozen before any run |
| `df3e15b` | absolute run directory (found by a smoke run, before any score) |
| `161a0d1` | `--resume` (added mid-study after the environment killed the run; disclosed) |
| `440864a` | `RESULTS-2.md` + README |

**Code freeze sha: `df3e15b`.** The study restarted once, at instance 1, before any
comparative score existed. `161a0d1` is a mid-study change and it is disclosed in
Deviations 21(b); it decides only *which* seeded samples still need running.

## Answers

**Q2 — does revision help or harm?** 17 paired within-instance revisions across all arm-B
variants: mean **−3.40 CLEAR F1** (SE 3.88), 4 better / 6 worse / 7 unchanged, Wilcoxon
p = 0.320 on 10 usable pairs. Not distinguishable from zero. **Rubric items fixed 3, broken
7.** Split by arm, the only arm whose revisions helped (+8.89, 2 fixed, 0 broken) is the one
whose findings named rubric items; the two raising generic content findings averaged −9.06
and −7.78 and broke 7 items between them while fixing 1.

**Q1 — why is the auditor silent?** Round-one recall against CLEAR ground truth:

| arm | recall | fired |
|---|---:|---:|
| shipped constitution, `gpt-5.6-terra` | **2.0%** (4 of 201 wrong items) | 7/40 |
| auditor → `gpt-5.6-sol` | 3.8% (2/52) | 5/10 |
| constitution → generated from the rubric | **15.5%** (9/58) | 5/10 |

**It is the constitution, not the model.** Task ceiling: 69.2% of reference cells are
derivable from the bytes the auditor sees, so the task caps recall — well above 2%.

Precision is 100% in every arm (4/4, 17/17, 2/2). The auditor never objects to something
correct; it almost never objects to something wrong.

## The thing worth escalating

CrossAudit passes the constitution to the **generator** as well as the auditor
(`generator.build_prompt(task=…, constitution=…)`). So the rubric-shaped rules changed the
writer too, and on the same ten samples B′'s round-one drafts scored **3.3 F1 against 14.7**.
The lever that fixes the audit currently breaks the writing. Splitting the auditor's rules
from what the generator is shown is a concrete next change with a measured motivation.

## Also new

- **D142 has a real confirmation rate**: 23/23 rubric-relevant BLOCKERs confirmed, 0 false
  positives, 95% CI [85.7%, 100%] — up from study 1's single observation. 21 of 44 findings
  are about no rubric item. No arm raised a single ADVISORY across 60 instances.
- **Secondary A/B**: 17.7 vs 16.6 F1, paired −1.19 on 40 pairs, p = 0.447 — negative where
  study 1's was positive, at 2.9× the cost and 1.9× the wall time.

## Spend

**$11.65** of the $15 budget: $11.32 recorded across the three run directories, $0.25 for a
one-instance pipeline smoke test whose numbers are not used, and ~$0.08 for the aborted first
launch — the last is the only reconstructed figure in the report and is labelled as such.

## Harness changes worth keeping

`run.py` now scores every arm-B round (the primary measurement), maps every finding of every
severity onto rubric items, computes per-round auditor recall, generates a rubric-derived
constitution deterministically from `tasks.py`, and probes task checkability. `report2.py` is
new and joins several run directories by arm label. `tests/test_instrumentation.py` pins the
new arithmetic over hand-built cases, including the one that matters: a silent auditor over a
wholly wrong output scores zero recall, not a pass. 109 tests pass.

## Licence

No dataset row, input, reference or model output is committed. `runs/` and `data/` stay
gitignored; `RESULTS-2.md` quotes no finding text and reports findings by rule id, cited
rubric item and CLEAR verdict only — stricter than study 1, deliberately.
