# E13 preregistration: a shape control for E6's convention finding (2026-11-15)

## Why
E6's task-alone arm flags the program that departs from the benchmark's behaviour (A) more often than the one that
follows it (B), and diagnoses more readily under the benchmark's contract (E6-2). An unanchored review asked whether
this reflects how A's code looks rather than a convention; an exploratory split (`benchmarks/exploratory/
e6_code_shape.py`, 2026-11-15) found the preference concentrated in units whose A program has more conditionals than
B (+38.8 against +9.5). Registered after E6-E11 were known and after that split was seen; E6's held-out readings are
known. E13's readings (of A, B and the new program B') are new and held out. Review P14 (`review_gpt_P14.md`) found
blocking defects in the first version (kind handling, stale cells, freeze scope, check strictness, bounds); all are
addressed below and the development pilot was rerun.

## Programs
For every registered E6 open unit (first and second attempts; 16 development, 41 held out), the vendor that wrote the
unit's audited programs (`shown_route`) receives the task, program B and the unit's class description, and rewrites B
so that the class inputs go through an explicit `if` branch computing exactly what B computes, every other line
unchanged (`EDIT_PROMPT` in `e13.py`). Check by execution, no model: on every registered admission input of the unit
(hidden suite, proposer inputs, probes, stress inputs, red-team inputs; interface inputs only), B' has the same status
as B (ok, timeout or the same exception type) and, where both return, an equal value under E6's comparator; a unit
without hidden inputs fails. B' must pass the visible tests, have at least one more conditional than B, and keep every
non-blank line of B (insertions only, compared after stripping whitespace). A failed check gets one second edit; units
still failing drop out and are counted as missing (bounds below). Calls that never reach the model and executor
infrastructure failures are retried and consume no attempt.

## Audits
A, B and B' are all read afresh (review P14: E6's historical readings would confound the intervention with the time and
model drift since E6), in one seeded random order that interleaves the three programs, in E6's task-alone arm
(`none`) with E6's four configurations and two readings per cell (24 readings per unit), E6's frozen audit prompt,
rulebook, parser, witness execution, scoring and cell policy; the program text is the only difference between A, B
and B' readings. Records under `benchmarks/e13/records`; E6's records are only read. E6's completeness check (every
required reading valid, every prompt hash as computed from the frozen units) must pass before analysis.

## Hypotheses (held out; problem-level bootstrap, 10,000 draws, E6's code)
Denominator: every registered E6 unit (41 held out). A unit without a checked B' or with an incomplete schedule is
missing and enters the registered bounds at the worst and best values; verdicts require the bounds as well as the
interval.
- E13-1 (primary): flag(B') - flag(B), unit means over configurations. "Shape effect" if the 95% lower limit and the
  lower bound are above 0; "no shape effect detected" if the interval and both bounds lie inside (-10, +10) points;
  otherwise unresolved. The margin, 10 points, is under half E6's flag preference (23.8) and a third of the
  difference between E6's code-shape strata (29.3), so a shape effect large enough to explain those would fall outside
  it; a 95% interval is stricter than the usual 90% for equivalence. At n=41 the equivalence decision has about 80%
  power at a true zero if the paired unit SD is 20 points and little if it is 30; the development SD is reported.
- E13-2: flag preference against B', flag(A) - flag(B'): positive if the lower limit and lower bound are above 0. On
  the same units A - B' = (A - B) - (B' - B), so E13-2 reports the preference that remains, not its cause.
- Secondary, prespecified: E13-1 and E13-2 in the code-shape strata (A has more conditionals than B: 20 held-out
  units; the rest: 21), with their difference; the fresh flag preference A - B and convention advantages with B and
  B'; per-vendor estimates; conditionals and lines added.

## Interpretation
B' is a third program written later by the same vendor; its added branch may look unusual in its own way. A is
unchanged, so E13 tests whether adding shape to B raises its flag rate, not whether removing shape from A lowers it.
If E13-1 finds no shape effect and E13-2 holds, the paper may say the preference survives this shape control; if a
shape effect is found, the paper reports that the preference partly tracks code shape.

## Development pilot (2026-11-15)
First version (archived in `records/pilot_v1/`, B' only, compared with E6's historical readings): 15 of 16 units with a
checked B', 120 readings, flag(B') - flag(B) -1.7 [-5.0, 0.0]. After review P14 (current design, stricter check):
15 of 16 units with a checked B' (200-1,171 registered inputs each, 1-3 conditionals added, no line of B removed; one
unit added no conditional in two edits); 360 of 360 readings valid and E6's completeness check passes. E13-1 -1.7
[-5.0, 0.0] (unit SD 6.5; bounds -7.8, 4.7); fresh flag preference A - B +28.3 [8.3, 48.3]; E13-2 A - B' +30.0
[11.7, 50.0]; no B or B' reading flagged in the shape stratum with more conditionals in A (7 units).

## Integrity
Freeze (`e13.py freeze`, after held-out construction, before any held-out audit) binds this file, `e13.py`, E6's code
(`e6.py`, `e1.py`, `analyse_e6.py`, `audit.py`, `execute.py`, `ceiling.py`), the product source tree, both
interpreters' package lists, every held-out B' with its check, and every required reading with its prompt hash.
Audits and analysis verify it; it cannot be rewritten once a held-out E13 audit record exists.

## Amendment 1 (2026-11-15, after held-out construction, before the freeze and any held-out audit)
Held-out construction gave a checked B' for 40 of 41 units. For Mbpp/93 both edits returned byte-identical code, which
differs from B on 1 of 239 inputs; the construction-completeness rule counted check rows rather than distinct edits,
so it reported the unit as unfinished and the freeze refused. The rule now counts distinct edits (identical edits
share one check). No check, criterion or analysis changes; Mbpp/93 is a missing unit under the registered bounds.

