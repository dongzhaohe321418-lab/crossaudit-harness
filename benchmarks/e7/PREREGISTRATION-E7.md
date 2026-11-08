# E7 preregistration (draft): the randomised-contract experiment on data-science code

Draft, 2026-11-08, before any E7 construction call. Protocol: E6's e6-v4.3 (`benchmarks/code/icml/PREREGISTRATION-E6.md`),
run by `benchmarks/e7/e7.py` with E6's stages unchanged. Only the differences are registered here.

## Why
E6 uses HumanEval+/MBPP+ short functions. E7 asks whether the information limit and the effect of stating the
contract carry over to library-heavy data-science code (pandas, numpy, scipy, scikit-learn).

## Corpus and split
BigCodeBench tasks whose declared libraries are within numpy/pandas/scipy/scikit-learn/standard library, with no
plotting, randomness, files, network or mocks in the reference or tests (172), whose reference passes its whole
suite in the E7 executor (135), and with at least three distinct recorded inputs on which the reference is
deterministic under the comparator (121: 28 development, 93 held out; split by a seeded hash of the task id).
Visible suite: two test methods chosen by study 23's seeded rule; hidden suite: all test methods.

## Differences from E6
1. *Hidden inputs* are the entry point's actual arguments recorded while the reference runs its own whole suite
   (`record7.py`), not a suite's input list.
2. *Comparator*: pandas DataFrame/Series/Index equality (dtype not checked, relative tolerance 1e-6), numpy
   allclose (relative 1e-6, NaN equal), float isclose, recursive on lists, tuples and dicts, equality otherwise.
3. *Arguments and witness values* may be pandas/numpy constructor expressions; they must pass a syntax whitelist
   (literals, and calls rooted in pd/np/datetime/math) and are evaluated in the executor, never in the harness.
   Prompts (proposal, probes, red team) and the auditor's witness rule say so; this is the only wording change.
4. *Executor and harness environments*: `.exec7` and `.venv7` (pandas 3.1.1, numpy 2.5.4, scipy 1.18.1,
   scikit-learn 1.9.1), separate from E1/E6's.
5. *One construction attempt only* (no second attempt). *No behavioural check*: there are no task-only generations
   for these tasks.

## Hypotheses (problem-level bootstrap, as E6)
E7-1: resolved minus menu verified diagnosis > 0 and resolved coverage lower bound >= 50 (E6-1's rule). E7-5:
sentence minus none > 0. Ordered family: E7-1, then E7-5. E7-2 (convention advantage) and E7-3 (budget) are
reported descriptively: expected n is too small for them. E7-4 (positive controls, J > 0) separately.

## Go / no-go
Held-out audits run only if at least 12 open units pass admission, red team and both judges; otherwise the
construction funnel is reported as a finding and E7 stops. A pre-test freeze (`freeze7.py`) and a review by a model
from another vendor precede any held-out audit.

## Construction result and decision (2026-11-08, before any E7 audit)
Construction ran on all 121 tasks. A first pass coincided with a provider outage of about one hour in which every
Claude call exited without a reply (all 54 probe calls and 206 positive-control implementation calls); as in E1
Amendment 5, calls that never reached the model do not consume an attempt, so those records were archived
(`records/*_infra_archive.jsonl`) and the stages rerun. Funnel (development / held out), open units: tasks 28 / 93,
pre-admission 12 / 37, admitted (v4.3) 2 / 18, red team passed 0 / 7, both judges 0 / 5. Positive controls: 28 / 93,
11 / 34, 5 / 9, 5 / 3, 5 / 2. The most common rejections were implementations that disagree with the reference outside
the open class, or rule-B implementations that disagree with the reference. **Decision, by the registered go/no-go
rule: no-go** (5 held-out open units, fewer than 12). No E7 audit was run; the funnel is reported as the finding.
For comparison, E6 on HumanEval+/MBPP+ (final frozen records) admitted 79 of 140 pre-admitted held-out first-attempt
units, of which 66 passed the red team and 34 both judges.
