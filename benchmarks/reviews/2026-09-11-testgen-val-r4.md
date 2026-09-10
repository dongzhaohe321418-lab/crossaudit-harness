# Study 17 (testgen validation) — fourth independent review (gpt-6-astra), 2026-09-11, target ba3addd

The numbers reproduce unchanged, but the §3 binding repair remains incomplete. It now compares whole cells within each rule’s row; it still does not reliably bind those cells to the displayed table’s meaning.

I ran the mutations in memory without changing files:

| Mutation | Binding test |
|---|---|
| Swap A’s and B’s P/C intervals | Rejects |
| Change `10/43` to `99/43` | Rejects |
| Change the actual denominator to `10/99` | Rejects |
| Delete an interval cell | Rejects |
| Corrupt C′’s rate or interval | Rejects |
| Add C′ to the corroboration table | Rejects |
| Corrupt B’s additions sentence | Rejects |
| Swap the **Wilson/bootstrap column headings**, leaving values unchanged | **Accepts** |
| Insert an incorrect **B `99/43` row before the correct B row** | **Accepts** |

These last two are concrete false assurances in [_table_rows](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/tests/test_testgen_val.py:196). Header selection checks only a substring; it never validates the column labels. Assigning `rows[cells[0]]` silently overwrites an earlier duplicate rule. Thus a displayed interval can be mislabeled, or a displayed count incorrect, while the test passes. Validate the complete header and reject duplicate or unexpected rule rows.

The §5 arithmetic repair is correct: **A 11.0×, C′ 11.0×, B 7.5×** their respective allowances.

The reproduced primary remains:

| Rule | Wrong among kept | Wilson 95% | Problem-cluster 95% | Retained |
|---|---:|---:|---:|---:|
| A | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5/7 |
| B | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6/7 |
| C′ | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5/7 |

**A remains selected; all three rules and H17 remain killed on wrong-test rate.**

Verification completed:

- **Reproduction:** Both archive manifests verify, and all three copied study-16 inputs match byte for byte. Archived records match repository records. In-memory reporting reproduces `numbers.json` and `exploratory.json` byte for byte. Independent aggregation, Wilson calculation, and the problem-cluster bootstrap at seed **20260915**, 10,000 resamples match **all 66 rate blocks**. Every pre-existing `numbers.json` value is unchanged from `eb47c27`.
- **Earlier repairs:** The §3 causal claim is withdrawn and qualified. Exploratory intervals reproduce, including C′’s complete equality with A. B’s additions are **confirm-C 1, confirm-P 2, explore-C 1**, reconciling 11 with 15. Unique-test retention/removal reproduces: A **58/64, 6/16**; B **62/64, 3/16**; C′ **56/64, 6/16**. A equals C′ plus four correct F-stratum applications. Passing counts are **1,430 overall; 1,421 clean/classifiable**. Amendment 3 and the blacklist-test disclosure are present.
- **Preregistration and boundary:** The changed primary, C′ baseline, selection order and kill already appear in `97470e1`. Relevant decision functions are unchanged from the pre-call implementation. Earliest inferred request start is **22:46:34.725**, after the **22:46:23** code commit. All **444 prompts** reconstruct from specification and visible tests and match draw 1’s hashes. Rules consume candidate-failure sets; I found no canonical or hidden-suite leakage into decisions. Candidate execution uses study 16’s `run_generated` path.
- **Floor and recurrence:** The conservative **29/1,188 = 2.4% floor** holds under the stipulated passing-tests-kept convention. Draw-2 recurrence is **23/32 versus 13/189**; draw 3 is **26/32 versus 10/189**. **37/222 = 16.7%** is marginal prevalence, correctly distinguished from the matched comparator. `Mbpp/160` explains the unmatched problem. Recurrence does not establish a shared semantic cause.
- **Identity, retry and spend:** Response identity is **13/222 and 8/222**; AST identity is **486/1,247 and 478/1,234**, with reproduced intervals. The single failed call, 75-second wait and **31.761-second** retry are supported. Spend is **$3.3493315**. Amendment 2 precedes draw 3; its 73-call snapshot occurred at **22:51:17.520**, while 77 calls had completed by its commit. The cap never bound.
- **Reporting and limits:** I checked §§1–2 against the records; their revised threshold conclusion is appropriately scoped. The selected suite returned **36 passed, three failures because no writable temporary directory exists**. A supplementary file-free replay matched **all 1,160 candidate/canonical outcomes**, but does not certify fresh-directory execution or normal-host full-suite green.

No generated test text was committed. `execute.py`, `architectures.py`, `src/` and kernel directories are untouched. I modified no files.

**not quotable — the claimed §3 binding still accepts a table that mislabels intervals or displays an incorrect duplicate count.**
