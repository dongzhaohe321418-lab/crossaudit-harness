# Study 17 (testgen validation) — third independent review (gpt-6-astra), 2026-09-11, target fb7a982

The primary result reproduces unchanged, and the substantive round-1 and round-2 reporting corrections are present. **One claimed repair remains incomplete: the new exploratory binding test does not bind each reported count and interval to its corresponding result.**

1. **The new test gives false assurance.** In [test_testgen_val.py:202](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/tests/test_testgen_val.py:202), the count string is computed but discarded as `_n`; percentages and intervals are checked for occurrence anywhere in the document. Using in-memory substitutions only, the test still passed when:
   - B’s “10 of 43” became **“99 of 43”**.
   - A’s and B’s P/C exploratory intervals were **swapped**.

   C′’s comparison checks only its numerator, not its denominator or intervals. The present prose and records are correct, but the claimed complete binding is not. Bind each rule’s count, rate and both intervals within its corresponding passage, and compare C′’s complete block with A’s.

2. **One smaller arithmetic overstatement remains.** [Results §5:202](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/RESULTS-TESTGEN-VAL.md:202) says every rule is “an order of magnitude above either count.” B keeps 15 wrong applications against an allowance of two: **7.5 times**, not ten. “Every rule substantially exceeds its allowance” is accurate; the kill is unaffected.

The reproduced primary is:

| Rule | Wrong among kept | Wilson 95% | Problem-cluster 95% | Retained |
|---|---:|---:|---:|---:|
| A | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5/7 |
| B | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6/7 |
| C′ | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5/7 |

**A remains selected; all three rules and H17 remain killed on wrong-test rate.** The primary records and decision equal those at `eb47c27`.

Verification completed:

- **Archives and reproduction:** Both manifests verify, as do all three copied study-16 input hashes. Archived records match repository records. In-memory execution reproduced `numbers.json`, `exploratory.json`, suite shapes and identity records byte for byte. An independent Wilson/bootstrap implementation matched **all 66 rate blocks**, using seed 20260915 and 10,000 resamples; independent aggregation from raw rows also matched the primary, unique-test, arm and exploratory quantities.
- **Round-2 repairs:** The “same misreading” cause claim is withdrawn in §3. All added exploratory intervals reproduce, including A/C′’s 0.0–44.8%, B’s 6.8–47.1%, and exclusive corroboration’s 0.0–84.6% and 23.5–89.5%. B’s additions are exactly **confirm-C 1, confirm-P 2, explore-C 1**, summing to four. The remaining issue is their automated binding, not their arithmetic.
- **Round-1 repairs:** A equals C′ plus four correct F-stratum applications, with identical wrong removal and seven-instance retention. Unique-test retention/removal counts and their intervals reproduce: A **58/64, 6/16**; B **62/64, 3/16**; C′ **56/64, 6/16**. AST-identity counts and cluster intervals reproduce. Amendment 3 preserves the original preregistration and corrects the passing counts, two-allowed boundary and P/C-only vacuity. Passing applications are **1,430 overall; 1,421 clean/classifiable**.
- **Preregistration and boundary:** The changed primary, C′ baseline, selection order and kill existed in `97470e1`. Relevant implementation functions are unchanged from `c5f172c`. Earliest inferred request start is **22:46:34.725**, after the code commit at **22:46:23**. Rules consume only candidate-failure sets; prompts reconstruct from specification and visible tests, with **all 444 hashes matching draw 1**. I found no canonical or hidden-suite leakage into decisions.
- **Floor and recurrence:** The **29/1,188 = 2.4%** conservative floor is correct under the stipulated passing-tests-kept convention. Recurrence reproduces: **23/32 versus 13/189** for draw 2; **26/32 versus 10/189** for draw 3. The **37/222 = 16.7%** quantity is correctly named marginal prevalence, not the negative comparison group. `Mbpp/160` explains the unmatched problem. These figures establish recurrence on error-prone problems, not a shared semantic cause.
- **Identity, retry and spend:** Response identity is **13/222 and 8/222**; AST identity is **486/1,247 and 478/1,234**. The single failed call, 75-second wait and successful **31.761-second** retry are supported. Ledger spend is **$3.3493315**. Amendment 2’s 73-call snapshot corresponds to **22:51:17.520**; 77 calls had completed by its commit. Draw 3 began around **22:58:27.171**. The cap never bound.

I checked §§1–2 against these quantities and found their revised threshold conclusion appropriately scoped.

The selected tests returned **36 passed, three failed because no writable temporary directory exists**. A supplementary file-free replay matched **all 1,160 candidate/canonical outcomes**, but does not certify fresh-directory execution or normal-host full-suite green. No generated test text was committed; `execute.py`, `architectures.py`, `src/` and kernel directories are untouched. I modified no files.

**not quotable — the most important remaining reason is that the claimed §3 evidence-binding repair still accepts incorrect counts and misassigned intervals, contrary to the repository’s testing standard.**
