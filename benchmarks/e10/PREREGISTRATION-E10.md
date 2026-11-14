# E10 preregistration: does stating the requirement add more than pointing at the behaviour? (2026-11-14)

## Why
E6-5 shows that one sentence stating the contract raises verified diagnosis by 76.8 points over the task alone. The
sentence does two things at once: it supplies the missing requirement and it directs the auditor to the input class
where the programs differ. E6's undecided menu names the class too, but it also signals uncertainty, so it is not a
clean attention control (first-read review, review_gpt_M1.md, weakness 4). E10 adds the missing control: a pointer
that names the input class and no rule. Registered after the E6, E8 and E9 held-out results were known; E10 makes new
audit calls only and changes no earlier record, estimate or verdict.

## Units, arms and readings
E6's 41 registered held-out open units (34 first attempt, 7 second attempt), with their frozen programs, oracles,
predicates and input-class descriptions. Four arms, each defined by the text appended to the task:
- none: nothing;
- pointer: "Additional note: pay particular attention to how the function handles the following kind of input:
  <class>", where <class> is the unit's frozen input-class description from construction (for example "Inputs where
  both the base and exponent are zero"), cut by a fixed rule (`neutral_class`) before its first clause, introduced
  by "for which", "whose", "requiring" or "but", that says what is unspecified or names the alternatives (it contains
  "unspecified", "ambiguous", "may", "either", "convention", "differs" or "requiring"); clauses that only define the
  class are kept. The rule was written before any E10 audit, after reading the class texts, because nine held-out
  descriptions say what is unspecified and two name both rules, which would make the pointer a menu;
- sentence-a, sentence-b: one rule as an ordinary requirement (E6's sentence arms, byte-identical text).
Auditors: E6's sentence configurations, GPT-5.6-terra and Claude Sonnet 5.5 at the low budget, with E6's shipped
rulebook and audit prompt. Each cell (unit, program, arm, configuration) is read twice: 32 readings per unit, 1,312 in
all, run afresh and interleaved in random order, so the none and sentence arms are contemporaneous replicates rather
than reuses of E6's readings.

## Scoring and analysis (E6's frozen code, unchanged)
Witness scoring, verified diagnosis, the cell policy (flag if either reading flags), unit values (means over the two
configurations), problem-level bootstrap (10,000 draws) and missing-data bounds are E6's (`e6.py`, `analyse_e6.py`
at their frozen hashes). none and pointer reveal no contract, so their readings are scored under both contracts, as
E6's unrevealed arms; sentence-X reveals contract X. Attempts follow E6 (three, with E1 Amendment 5's accounting).

## Hypothesis and estimands
- E10-1 (the one confirmatory claim): verified diagnosis in the sentence arms minus the pointer arm; the 95% lower
  confidence limit and the worst-case missing-data bound both above 0. Supported means that stating the requirement
  adds diagnosis beyond directing attention to the input class.
- Reported either way, two-sided, without a claim: E10-2, pointer minus none (what attention alone does to verified
  diagnosis); sentence minus none (a contemporaneous replicate of E6-5); the flag rate on defective and correct
  programs per arm; the flag preference (flags on program A minus program B) and the convention advantage in the
  none and pointer arms (whether pointing at the behaviour makes the benchmark's convention more visible); per-
  configuration E10-1 and E10-2.

## Interpretation fixed in advance (margins set before any held-out call)
- E10-1 supported: the paper may say that stating the requirement improves verified diagnosis beyond this pointer.
  Failing to establish E10-1 is not evidence that the two are close.
- "Pointing at the input class adds little": only if the upper 95% limit of E10-2 (pointer minus none) is below 20
  points.
- "Much of the sentence's effect may be attention": the paper must say so if the upper 95% limit of E10-1 is below
  20 points, and must then weaken its mechanism claims.
- Otherwise the paper reports the estimates without a mechanism conclusion beyond E10-1.
The pointer names the class in the constructor's words, which may itself hint at what matters, and it is phrased as a
note, not a requirement; it is one attention control, not all of them. The auditors are two of E6's configurations at
the low budget; results are conditional on these identities and on familiar benchmark tasks.

## Additional reporting
- Missing-data bounds for every contrast, the flag preference and the convention advantage.
- Located rate per arm: the share of flagging readings whose witnesses include a valid, in-class, in-interface call,
  whether or not the stated expected value is right (descriptive; separates finding the input from knowing the answer).
- Sensitivity without the two exception-contract units (MBPP 93, 623), whose contract-A diagnosis the frozen scorer
  cannot credit (E6 appendix); the primary analysis keeps them.
- Power: the inferential unit is the problem (41). With a paired problem-level standard deviation of 0.3 to 0.5, a
  normal approximation gives 80% power at a two-sided 5% level for differences of about 13 to 22 points; E6's
  sentence-minus-none effect was 76.8 points.

## Order of runs
Audits are shuffled within each unit kind (first-attempt units, then second-attempt units), so arms are interleaved
within each kind; witness scoring follows each kind's audits.

## Integrity
Before any held-out audit, witness scoring or analysis, `e10.py` verifies E6's freeze computed under E6's own
configuration (every field except the repository commit; every frozen dependency file must match, and the benchmark
tree, `benchmarks/code`, may differ only by the one file added since, `icml/e6_exception_sensitivity.py`; E9 and E10
lie outside it) and E10's freeze
(this file, `e10.py`, E6's code, routes, units and every rendered arm text).

## Development pilot
Before the freeze, the same code runs on a development pilot population, the first four registered development open
units by E6's population order and the second-attempt units among them (`--limit 4`), to check that audits, witness
scoring and analysis run end to end. Review P12 (`review_gpt_P12.md`) found blocking defects in freeze verification,
pilot scoping and interpretation; all are fixed above and in `e10.py` before the freeze.

Pilot result (2026-11-14, 8 development units, 256 valid readings, all witness sets scored): verified diagnosis
none 0.0, pointer 31.2, sentence 93.8; E10-1 +62.5 [46.9, 78.1]; E10-2 +31.2 [18.8, 43.8]; located rate among flagging
readings: pointer 100% (20), sentence 97% (73). The pointer wording is unchanged.
