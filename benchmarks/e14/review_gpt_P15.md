**Do not start the held-out run yet.** The main problems concern whether the manipulation achieves matching, freeze coverage, and inference with missing units.

Read-only replay reproduces **600/600 valid development readings**, E14-1 **+30.0**, and E14-2 **+41.7**. Pair remapping is correct; the registered kinds are disjoint; nested state calls restore E14’s paths, including `open2`. Completeness enforces E6’s valid-or-exhausted policy. I found no recurrence of E13’s stale-cell substitution.

1. **A_min does not establish removal of dedicated special cases.**  
   The gate only requires fewer `If`/`IfExp` nodes when A has any. Passing **Mbpp/124** replaces its branch with `(z.imag < 0) * 2 * math.pi`: the exact class-specific condition survives, yet both A_min and B score zero control constructs. **Mbpp/477** passes unchanged, retaining its explicit character replacement. The broader stratum misses comparisons used as arithmetic/index selectors, comprehension filters and library-mediated conditions. It is a reproducible syntactic stratum, but not evidence of matched form. See [construction gate](<crossaudit-harness/benchmarks/e14/e14.py:135>) and [Mbpp/124 edit](<crossaudit-harness/benchmarks/e14/records/edits.jsonl:29>).

   Consequently, **E14-1 tests these simplifications**, with unmatched units included in the primary estimate. **E14-2 tests adding branches to both original implementations**; their existing differences remain. In the pilot, Mbpp/405 has **12 versus 4** counted constructs in A_br versus B′. Neither contrast warrants “preference survives matching code form” as currently implemented.

2. **A_br’s structural gate accepts a failed manipulation.**  
   Appending an unreachable `if False: pass` after A’s return satisfies both structural checks while preserving every execution result. Moreover, whitespace-stripped line retention permits reindentation and arbitrary inserted preprocessing; it does not preserve surrounding control flow. Behavioural testing constrains registered inputs, but cannot repair this structural loophole. See [E14 gate](<crossaudit-harness/benchmarks/e14/e14.py:132>) and [line comparison](<crossaudit-harness/benchmarks/e13/e13.py:65>).

3. **The nested freeze remains incomplete, and its closure guard is mutable.**  
   E14 recomputes E13’s state rather than verifying and binding its saved manifest. That state omits corpus data, `corpus.py` and `split.json`. In an in-memory test, changing a reference implementation and hidden comparator left E14’s manifest unchanged. Separately, `heldout_audits_exist()` derives test membership from the *current* split: moving an audited problem to development changed the guard from true to false despite its retained `split="test"` audit row. This permits reopening construction/freezing after outcomes through split changes. See [nested state](<crossaudit-harness/benchmarks/e14/e14.py:216>) and [closure guard](<crossaudit-harness/benchmarks/e14/e14.py:239>).

4. **The registered decision rule is not a missingness-robust 95% test.**  
   Implementation matches the registration: it requires a positive complete-case confidence limit and a positive worst-case **point** bound. Those conditions do not ensure a positive confidence limit after worst-case missingness. Using the actual bootstrap, 40 observed units—eight differences of 0.25, otherwise zero—and one missing unit produce **+5.0 [1.875, 8.125]**, bound **+2.439**, and a positive verdict; the worst-missing lower endpoint is **−0.610**. Interaction and stratum outputs also omit missingness bounds. See [analysis and verdicts](<crossaudit-harness/benchmarks/e14/e14.py:299>).

Concrete fixes before freezing:

- Rewrite **both rules** into prespecified common forms; construct branched versions from those normalised bases. Freeze an outcome-blind matching decision, and narrow the claim if matching fails.
- Enforce reachable class routing and AST-level preservation outside the permitted insertion; reject disguised dedicated selectors in A_min.
- Bind corpus, split, dependencies and the saved E13 freeze. Close the run using an immutable marker or recorded test labels.
- Apply worst-case missingness to confidence limits; give the interaction its **[−2, +2]** bounds and report stratum denominators/exclusions.

State tests used mocked environment probes. No model calls or file modifications were made.