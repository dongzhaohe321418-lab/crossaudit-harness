# E13 preregistration: a shape control for E6's convention finding (2026-11-15)

## Why
E6's task-alone arm flags the program that departs from the benchmark's behaviour (A) more often than the one that
follows it (B), and diagnoses more readily under the benchmark's contract (E6-2). An unanchored review asked whether
this reflects how A's code looks rather than a convention; an exploratory split (`benchmarks/exploratory/
e6_code_shape.py`, 2026-11-15) found the preference concentrated in units whose A program has more conditionals than
B (+38.8 against +9.5). Registered after E6-E11 were known and after that split was seen; E6's held-out readings are
known. E13's readings of the new program B' are new and held out.

## Programs
For every registered E6 open unit (first and second attempts; 16 development, 41 held out), the vendor that wrote the
unit's audited programs (`shown_route`) receives the task, program B and the unit's class description, and rewrites B
so that the class inputs go through an explicit `if` branch computing exactly what B computes, every other line
unchanged (`EDIT_PROMPT` in `e13.py`). Check by execution, no model: B' equals B under E6's comparator on every
registered admission input of the unit (hidden suite, proposer inputs, probes, stress inputs, red-team inputs;
interface inputs only), B' passes the visible tests, and B' has at least one more conditional than B. A failed check
gets one second edit; units still failing drop out and are counted as missing (bounds below).

## Audits
Only B' is audited. Auditors read one program per call, so A's and B's readings are E6's frozen task-alone readings.
B' is read in E6's task-alone arm (`none`) with E6's four configurations and two readings per cell (8 per unit), E6's
frozen audit prompt, rulebook, parser, witness execution, scoring and cell policy; the program text is the only
change. Records under `benchmarks/e13/records`; E6's records are only read.

## Hypotheses (held out; problem-level bootstrap, 10,000 draws, E6's code)
- E13-1 (primary): flag(B') - flag(B), unit means over configurations. "Shape effect" if the 95% lower limit is above
  0; "no shape effect detected" if the interval lies inside (-10, +10) points; otherwise unresolved.
- E13-2: flag preference with the shape matched, flag(A) - flag(B'): survives if the lower limit is above 0.
- Reported without a claim: the convention advantage with B' in place of B, E6's values on the same units, both
  split by the exploratory code-shape strata; conditionals added; edit sizes; per-vendor estimates.
Missing units (no checked B') enter the registered missing-data bounds at the worst and best values.

## Interpretation
B' is a third program written later by the same vendor; its added branch may look unusual in its own way. A is
unchanged, so E13 tests whether adding shape to B raises its flag rate, not whether removing shape from A lowers it.
If E13-1 finds no shape effect and E13-2 holds, the paper may say the preference survives this shape control; if a
shape effect is found, the paper reports that the preference partly tracks code shape.

## Development pilot (2026-11-15)
15 of 16 development units received a checked B' (200-1,171 registered inputs each, 1-3 conditionals added; one unit
added no conditional in two edits). 120 of 120 readings valid; E6's completeness check confirms every prompt hash.
No B' reading flagged. flag(B') - flag(B) -1.7 [-5.0, 0.0]; flag(A) - flag(B') +36.7 [18.3, 56.7] (E6 on the same
units +35.0).

## Integrity
Freeze (`e13.py freeze`, after held-out construction, before any held-out audit) binds this file, `e13.py`, E6's code
(`e6.py`, `e1.py`, `analyse_e6.py`, `audit.py`, `execute.py`, `ceiling.py`), the product source tree, both
interpreters' package lists, every held-out B' with its check, and every required reading with its prompt hash.
Audits and analysis verify it; it cannot be rewritten once a held-out E13 audit record exists.
