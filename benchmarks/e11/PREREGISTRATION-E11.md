# E11 preregistration: the randomised-contract experiment on BigCodeBench, by localised edits (2026-11-14)

## Why
All of E6's evidence comes from 41 short HumanEval+/MBPP+ functions. E7 tried BigCodeBench and stopped at
construction (5 held-out units against a gate of 12): two models writing whole programs from scratch disagreed with the
reference outside the open class. A first-read review rates a second-domain replication as the change that would most
raise the paper's standing (audit-ceiling-paper/plan/icml2027/reviews/review_gpt_M2.md). E11 changes only how the
programs are built. Registered after E6, E8, E9 and E10 were known; E7's construction records were seen, and E11 reuses
E7's proposals and split, so E11 is an extension whose audit outcomes are held out, not a replication on unused
tasks. No held-out E7 or E11 task has been audited.

## Corpus and splits
E7's frozen corpus: the 121 deterministic BigCodeBench tasks with at least three recorded hidden inputs, E7's
development/held-out split (28/93), its recorded hidden inputs, pandas/numpy comparator and constructor-expression
arguments (`benchmarks/e7/`).

## Construction (E6 v4.3 with one stage changed)
- First attempt: E7's frozen rule proposals (88 usable held out).
- Implement (changed): each of E6's two implementing vendors (Claude Opus 5.5, GPT-6.1-sol) is asked to edit the
  reference solution, docstring removed, minimally, so that the inputs the rule concerns are handled by an explicit
  branch that follows the rule, every other line unchanged; once for each rule (`EDIT_PROMPT` in `e11.py`). One
  attempt each. The minimality is prompted, not enforced: a development edit (BigCodeBench/769) also changed code
  outside its branch. Equivalence outside the class is therefore established as in E6, by execution on the registered
  inputs, not by construction; the paper reports edit sizes (lines differing from the reference).
- Everything else is E6's frozen code: pre-admission, probes, class predicates, v4.3 admission (all agreement checks on
  interface inputs, up to 300 stress inputs), red team, the two judges blind to which rule is the benchmark's.
- Second attempt: as in E6, one new, independent proposal and construction for each held-out problem without a
  first-attempt primary unit, decided by construction outcomes only.
Development pilot (2026-11-14): first attempt 27 proposals, 18 pre-admitted, 11 admitted, 6 past the red team, 4 past
both judges (E7 from scratch: 12, 2, 0, 0); second attempt 23, 14, 8, 2, 1. Five development units in all.

## Go / no-go (E7's registered gate, kept)
Audits run only if at least 12 held-out units (both attempts) pass admission, red team and both judges; otherwise the
funnel is reported and E11 stops. Rationale (2026-11-14, before any held-out construction): the design note had
proposed 20; after the development pilot projected about 17 held-out units, we adopted E7's already-registered gate of
12, chosen there before any data, because the confirmatory hypotheses concern effects of 60 to 80 points, detectable
at that size (see Power). Construction is not stopped on reaching 12: the first attempt runs to completion on every
held-out proposal, second-attempt eligibility is then decided, the second attempt runs to completion, and only then is
the gate evaluated, once, by program (`e11.py freeze --split test` refuses to freeze if any construction stage is
unfinished).

## Arms, auditors and scoring (E10's design)
Four arms appended to the task: none; pointer (E10's frozen wording; class text by E10's rule, then, because E10's rule
only cuts introduced clauses, cut at the last delimiter before any surviving uncertainty word, `neutral_class11`; the
freeze refuses any rendered pointer that still contains one or has fewer than two words, and a refusal is resolved by
a dated amendment before any audit);
sentence-a and sentence-b (E6's sentence arms). Auditors: GPT-5.6-terra and Claude Sonnet 5.5 at the low budget (E6's
sentence configurations), E6's audit prompt and rulebook with E7's constructor-expression wording; two readings per
cell, 32 per unit. Witness scoring, verified diagnosis, cell policy, unit values, problem-level bootstrap (10,000
draws) and missing-data bounds are E6's frozen code. The unrevealed arms are scored under both contracts. Note that
B's oracle is the reference and A's is the other vendor's A edit; all programs share the reference's code outside the
branch.

## Hypotheses (ordered: E11-2 is claimed only if E11-1 holds)
- E11-1: verified diagnosis, sentence minus none: 95% lower confidence limit and worst-case bound above 0 (replicates
  E6-5 on a second benchmark).
- E11-2: verified diagnosis, sentence minus pointer: the same criterion (replicates E10-1).
- E11-3 (descriptive): E9's outside-construction admissibility check (same judges, prompt and code) on E11's units and
  their resolved items: acceptance, exclusion of the non-appended rule, and E11-1/E11-2 on the accepted subsets. There
  are no positive controls in E11, so E9's Disc is not estimable.
Reported either way, without a claim: pointer minus none; the flag rate on correct programs in the sentence arms with
its betting upper bound; the flag preference and the convention advantage in the none and pointer arms (E6-2's
estimand, unregistered here because the expected sample is small); per-configuration estimates.

## Power and interpretation
With 12 to 20 units and a problem-level standard deviation of 0.3 to 0.5, a normal approximation gives 80% power for
differences of roughly 20 to 40 points; E6-5 was 76.8 and E10-1 60.4. A null on the flag preference or convention
advantage at this size is uninformative and will be reported as such. If E11-1 holds, the paper may say the sentence
effect replicates on these edited BigCodeBench programs; that is a conditional claim, not one about ordinary library
code. Both programs share the reference's code and carry an explicit branch in every arm, so the branch is a
code-level cue present throughout, and sentence minus pointer cannot isolate it; where B's branch repeats the
fallback while A's transforms, the benchmark-conforming program may be recognisable. Contract A's oracle is the other
vendor's edit of the same reference, and the judges are the implementing models; E11-3 adds judges outside the
construction. The development pilot gave a high false-flag rate on correct programs in the sentence arms (25%,
5 units), which will be reported. Add problem-level effect plots and leave-one-problem-out estimates for E11-1 and
E11-2. The missing-data bound is an identification bound, not a confidence bound.

## Integrity
Two freezes. The protocol freeze (`e11.py protocol-freeze`), before any held-out construction, binds E11's code and
this file, E10's pointer code, E7's corpus, hidden inputs and code, E6's code, `audit.py`, `execute.py`, the product
source the audit prompt, parser, validator, checks and rulebook come from, both environments' package lists, the CLI
versions, every construction prompt and the routes; held-out construction verifies it. E11 builds its audit-prompt
project under its own records, not E6's (the development audit pilot had rewritten E6's generated rulebook file; it
was restored from the repository and E6's and E10's freeze verifications pass). The population freeze
(`e11.py freeze --split test`) binds E11's code and this file, E10's pointer code, E7's corpus, hidden inputs and code, E6's
code, every construction record, the routes, the gate result, every registered unit's programs, oracles, predicates
and rendered arm texts, and every required reading with its prompt hash; audits and analysis verify it, audits refuse a
freeze whose gate was not met, and the freeze cannot be rewritten once any held-out audit record exists.

Development audit pilot (2026-11-14, 5 units, 160 valid readings): verified diagnosis none 0.0, pointer 15.0,
sentence 85.0; E11-1 +85.0 [65, 100]; E11-2 +70.0 [35, 95]; false flags on correct programs in the sentence arms 25%.
Review P13 (`review_gpt_P13.md`) found blocking defects (freeze guard, prompt-project isolation, dependency binding,
freeze phases, the edit claim) and design limits; all are addressed above before any held-out call.
