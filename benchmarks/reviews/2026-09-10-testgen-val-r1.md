# Study 17 (testgen validation) — first independent review (gpt-6-astra), 2026-09-10, target eb47c27

The numerical kill reproduces, but **HEAD needs reporting corrections before quotation**. I found no change to the preregistered rules or evidence of canonical-solution leakage into their decisions.

1. **The conclusion exceeds the evidence.** [Results §1](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/RESULTS-TESTGEN-VAL.md:34) says corroboration “does not recognise a wrong test” and paid rules “do not beat” C′. What reproduces is failure to meet the specified validation threshold on this substrate. A actually keeps exactly C′’s applications **plus four correct applications**, with identical wrong-test removal and seven-instance retention. Those additions are all F-stratum applications. Say that neither paid rule achieves usable validation; an unqualified no-improvement claim is unsupported.

2. **Problem-level recurrence does not establish the claimed mechanism.** [Results §2](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/RESULTS-TESTGEN-VAL.md:89) correctly reports:
   - 23/32 = **71.9%**, Wilson 54.6–84.4%.
   - 37/222 = **16.7%**, Wilson 12.3–22.1%.

   “Base rate” is valid if explicitly called the **marginal draw-2 prevalence**, rather than the comparison group without draw-1 errors. On the matched, draw-1-classifiable cohort, the comparison is **23 of 32 versus 13 of 189**; the marginal count is 36 of 221. `Mbpp/160`, unknown in draw 1, accounts for the difference. This supports recurring error-prone problems, but does not distinguish the same misreading from different errors on difficult or ambiguous problems. “The misreading is the model’s, not the draw’s” needs qualification.

3. **Some preregistered reporting is missing.** [Preregistration §5](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/testgen/PREREGISTRATION-VAL.md:162) requires unique-test correct retention and wrong removal, with both intervals. The report substitutes wrong-among-kept exposed tests. The missing counts are A **58/64 retained, 6/16 removed**; B **62/64, 3/16**; C′ **56/64, 6/16**. Also, the AST-identity rates have only Wilson intervals despite repeated tests within problems. Their problem-cluster intervals are **35.1–43.0%** and **35.1–42.3%**, respectively.

4. **Correct the smaller factual claims.**
   - [Results line 75](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/RESULTS-TESTGEN-VAL.md:75): six is **two** above four.
   - The first ledger completion is **22:46:38.694**, with earliest inferred request start **22:46:34.725**, rather than a 22:47 stamp. Both follow the code commit at 22:46:23.
   - The retry waited approximately **75 seconds before starting**; its successful call then took 31.761 seconds. It did not succeed 75 seconds later.
   - [Results line 165](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/RESULTS-TESTGEN-VAL.md:165): two wrong applications are allowed at n=100–107; “at most one” is false there.
   - C is vacuous on **P/C**, not the entire primary: 58 of the 107 failing applications are F-stratum applications. Its retention would nevertheless be zero, so dropping it before the run remains defensible.
   - The preregistration’s “other 1,428 applications pass” is incorrect: **1,430 overall**, or **1,421 within clean, classifiable rows**.

The principal calculations are sound:

| Rule | Wrong among kept | Wilson 95% | Problem-cluster 95% | Retained |
|---|---:|---:|---:|---:|
| A | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5/7 |
| B | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6/7 |
| C′ | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5/7 |

All three are killed on rate, and A wins the preregistered selection order.

I verified both archive manifests, all three copied study-16 inputs, frozen rows and suites, archived-versus-committed records, and suite shapes. Reproducing the report in memory yielded **byte-identical `numbers.json`**. An independent Wilson/bootstrap implementation matched all **53 report rate blocks**, using seed 20260915 and 10,000 resamples.

The primary redefinition, C′ baseline, rule order and kill were present in `97470e1`, before any draw-2 call. The floor argument holds under the stipulated passing-tests-kept convention: 29 wrong tests are unreachable, so 29/1,188 is a valid conservative lower bound above the kill threshold. Amendment 2 preceded draw 3; its 73-call snapshot matches 22:51:17, while 77 calls had completed by its 22:51:45 commit.

All 444 prompt hashes match reconstructed prompts and draw 1. Identity counts **13/222, 8/222**, and **486/1,247, 478/1,234** reproduce. The single failed attempt and retry are supported; recorded spend totals **$3.349331**, excluding that unmetered failure.

The implementation uses study 16’s unchanged execution path; rule decisions consume candidate-failure sets only. A supplementary file-free replay matched **all 1,160 candidate/canonical outcomes**. It used `python -c` and an existing cwd, so it does not certify the original fresh-directory execution. The requested test selection returned **35 passes and three temporary-directory failures under the read-only sandbox**; I cannot certify 38 normal-host passes or a green full suite. The boundary test at [test line 52](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/tests/test_testgen_val.py:52) is also only a source-string blacklist, not behavioral proof.

No generated test text was committed; `execute.py`, `architectures.py`, `src/` and kernel directories are untouched. I modified no files.

**not quotable — the most important reason is that failure of these rules to meet the validation threshold is presented as a broader failure of corroboration to recognise wrong tests.**
