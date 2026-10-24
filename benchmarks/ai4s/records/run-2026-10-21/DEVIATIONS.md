# Deviations from DESIGN.md, run 2026-10-21

Recorded by the lead after the run, per `benchmarks/EXPERIMENT_RECORD.md` §5.
Numbered; each says whether it could bias the result and in which direction.
Numbers here come from `numbers.json` in this directory or from the
exploratory run's `numbers.json` named in item 1.

1. **The preregistered false-block criterion for H2 cannot be met at the
   preregistered n.** DESIGN §1 requires the extended profile's false-block
   rate on clean controls to have a Wilson 95% upper bound at or below 2.5%,
   and fixes n at 6 domains × 10 seeds = 60 clean controls. A count of 0 of
   60 has a Wilson upper bound of 6.0% (z²/(n+z²)); the bound falls to 2.5%
   only at n ≥ 150. The criterion was therefore unsatisfiable by any data at
   n = 60, which is a design error, not a property of the pack. The
   preregistered decision stands as written — **H2 does not hold on this
   corpus** — and the observed count is 0 of 60. To size the bound, one
   exploratory run was made after the fact with `--seeds-per-domain 30`
   (`records/run-2026-10-21-exploratory-x30/`, 180 clean controls, 5,760
   planted): false blocks 0 of 180 for both profiles, Wilson upper bound
   2.1%, under which the preregistered rule would read "holds". That run is
   post hoc and is labelled exploratory wherever it is quoted; it does not
   replace the preregistered decision. Bias: none on the count; the decision
   rule was biased toward "does not hold" by construction.

2. **The cluster-bootstrap interval for the primary contrast is degenerate**
   ([0.627, 0.627] over 60 templates; also over 180 in the exploratory run).
   The deterministic layer catches a planted (class, variant) identically on
   every template, so the between-template variance of every per-class rate
   is exactly zero and resampling templates changes nothing. The coverage
   simulation in `coverage_check.json` assumed template-level Bernoulli
   variation with a random effect and does not describe this run; the
   report's "calibrated" line is about the simulated design, not this data.
   For this run the interval is to be read as **uncalibrated**, and the point
   estimate as exact for this corpus. Bias: none on the point estimate; the
   interval overstates precision by being a point.

3. **Expectation corrections made before the run** (DESIGN §3): the
   `complete` check reports placeholders as CA-FILE-004 at ADVISORY, not
   CA-CONTENT-001 at BLOCKER, and D04 `revision_mismatch` is the shipped
   check's advisory shape. Both were settled against the shipped code before
   any instance was scored and are recorded in `taxonomy.json`
   `variant_overrides`. Not a deviation from the hypotheses; listed so the
   change is visible.

4. **Corpus size.** DESIGN §1 estimated 1,000–1,500 defective instances; the
   corpus has 1,920 (60 clean), because the per-domain applicability was
   wider than estimated. No effect on inference.

5. **D16 is not planted on `dft_convergence`.** Its analysis is deterministic,
   so `results.json` honestly carries no `stochastic: true` and the
   `repro_declared` check is silent by contract. D16 has n = 150, not 180.

6. **One planted defect can raise up to four findings under `science-ai4s`**
   (D09: CA-NUM-005, CA-PHYS-001, CA-DERIV-001 and sometimes CA-STAT-004 on
   the same quantity). Scoring counts an instance once; attribution asks
   whether an expected rule fired, which it did on every blocked instance
   (1,350 of 1,350). The multiplicity is a reporting-surface follow-up for
   the product (one defect, one finding), not a scoring issue.

7. **The model layer was not run.** `run_auditor.py --dry-run` on the full
   corpus with the `science-ai4s` profile: 1,980 instances, 72.4 MB of
   prompts, ≈ 19.1 M estimated input tokens; at the 2026-08-03 price
   snapshot and 1,500 output tokens per instance, ≈ $92 (gpt-5.6-terra) or
   ≈ $102 (claude-sonnet-5). No credentials exist in this session and the
   spend was not authorised. A single-seed stratified subset (198 instances,
   about one tenth of that) is the sensible first live run.

8. **Interpreter.** The run used Python 3.13.14; no 3.10 interpreter was
   available. The corpus engineer checked that generation is byte-identical
   under 3.9 and 3.13.

9. **Tree state.** `run.json` records `tree dirty: True`: the benchmark,
   the pack and the records were uncommitted at run time, and the git sha it
   names (`1f6120e`) is the base commit, not a commit containing this code.
   The commit that carries this record is the one whose history includes
   this file.
