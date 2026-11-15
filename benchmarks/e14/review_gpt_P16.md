**Do not start the held-out run yet.** The redesign fixes the main freeze and missingness problems from P15, but the structural guarantee remains false, and the interpretation needs narrowing.

1. **Blocking: `confined_to_one_if` can accept different conditions.** In [the matcher](<crossaudit-harness/benchmarks/e14/e14.py:62>), I reproduced `(True, "ok")` for:

   ```python
   def f(x):
       if (
           x < 0): return 1
       return 0
   ```

   versus the same program with `x > 0): return 2`. The first header line matches, while the changed condition occupies the first body statement’s line.

   Ordinary `elif`-condition changes and external import/helper/decorator changes were rejected in my tests. Nested changes can legitimately pass under an enclosing body. Decorators on its first statement can instead cause false rejection. **All 15 accepted development pairs passed a stronger same-AST-position body-masking check**; the counterexample exposes a gate defect, not demonstrated contamination of those pairs.

2. **Blocking: reachability and class selection are not established by [the checks](<crossaudit-harness/benchmarks/e14/e14.py:145>).** Wrapping both complete algorithms in `if True:` passes confinement and behavioural checks, while matching little meaningful structure. The pilot already has imperfect class selection: Mbpp/142’s branch also executes for `([1], [2.0], [3])`, outside its registered equal-value class.

   With exact deterministic equivalence and genuine confinement, differing outputs would imply execution of the differing body. Here, however, E6 uses tolerant comparators: approximate agreement is not transitive. A common midpoint can agree with both separated originals while the new programs differ only in dead code. E14 never directly checks M_A–M_B separation or traces the selected body.

3. **Freeze, missingness and pairing are substantially repaired.** The manifest now covers the corpus module, all three data files and split, alongside inherited code/environment coverage, construction records and required prompt hashes. In-memory coverage probes detected corpus/split changes; closure remained independent of current split membership. One resilience gap: E6’s raw audit rows lack `split`, so the raw-row fallback cannot identify test readings without the marker.

   Pair remapping, problem-level contrasts and the interaction are correct; the two kinds have disjoint problem IDs. Worst-case imputation now enters the bootstrap itself, with **[−2,+2]** interaction bounds. I reproduced **480 valid readings**, E14-1 **+26.7 [6.7,48.3]**, and worst-case **[−6.25,43.75]**, correctly yielding no positive verdict. Stratum intervals remain complete-case, with counts disclosed.

4. **E14-1 answers the narrower surrounding-code question.** After repairing the gate, a positive result supports preference persisting with identical code **outside one branch body**. It does not eliminate implementation-form differences inside that body: [Mbpp/405](<crossaudit-harness/benchmarks/e14/records/edits.jsonl:9>) compares a loop with nested conditionals against `return True`; other pairs compare substantive operations against `pass`. The claim that redundant M_B branches should bias against B is unsupported.

Concrete fixes:

- Match the **same AST position**, preserving the complete condition and surrounding tree; additionally compare exact source outside token-defined body boundaries.
- Record branch execution against the frozen class predicate and directly verify M_A–M_B separation on at least two valid class inputs.
- Narrow the claim to shared surrounding code, or prespecify symmetric constraints on both branch bodies. Remove the directional redundancy claim.
- Add split labels to raw rows and worst-case stratum intervals if retaining “every registered unit” reporting.

No files changed or model calls made. Numerical replay omitted prompt-hash rebuilding because the available Python 3.9 cannot load the product; freeze probes used mocked environment/prompt probes.