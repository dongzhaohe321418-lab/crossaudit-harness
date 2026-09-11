# Study 17 (testgen validation) — sixth independent review (gpt-6-astra), 2026-09-11, target 1cd745e

The numbers reproduce, but the replacement binding remains **unsound for rendered results**. It protects bytes inside markers; it does not protect their presentation or placement.

I independently reran all **16 previous mutations**: every one was rejected. I then found accepted mutations that leave every generated block intact. **All four results-binding tests passed** on these:

| New mutation | Verified rendered effect |
|---|---|
| Append a Markdown table without leading pipes | Displays an extra B row containing `99/43` |
| Append that table inside a blockquote | Displays the same incorrect row |
| Append an HTML table | Displays an unchecked B `99/43` row |
| Put fences around the intact P/C block | Four tables render instead of five; P/C becomes code |
| Exchange intact P/C and corroboration blocks | Correct numbers appear under the wrong explanatory sections |
| Fence the intact P/C block and insert a pipeless replacement | Five tables still render, but the replacement displays `99/43` |

I verified these effects with **Pandoc’s GFM renderer**, inspecting the resulting HTML tables and cells, without writing files.

The defect is concrete in [test_testgen_val.py:224](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/tests/test_testgen_val.py:224): the outside-block check recognizes only lines whose stripped text starts with `|`. The block comparisons also impose no rendered-context or section-placement constraint. Thus the claim that byte comparison “ends that class of defect” remains false. The repair must bind the rendered tables, their complete inventory, and their section association—or generate the surrounding document structure too.

The scientific verification succeeded:

- **Reproduction:** Both archive manifests verify, covering 20 and 11 entries. All three copied study-16 inputs match byte for byte. Archived record counterparts match repository files. In-memory reporting reproduces `numbers.json`, `exploratory.json`, and `tables.md` byte for byte; suite shapes and AST identity also reproduce.
- **Independent arithmetic:** I reconstructed all **870 rule decisions** and independently matched **all 66 rate blocks**, including Wilson intervals and 10,000 problem-cluster resamples at seed **20260915**.
- **No numerical movement:** Numerical records are byte-identical to both round-4-related commits, `ba3addd` and `815d25e`. Every original `numbers.json` value remains unchanged from `eb47c27`. All results-table rows match round 4 after removing the arm table’s indentation. Scientific figures did not change; markers, explanatory prose, and test-count reporting did.

The primary remains:

| Rule | Wrong among kept | Wilson 95% | Problem-cluster interval | Retained |
|---|---:|---:|---:|---:|
| A | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5/7 |
| B | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6/7 |
| C′ | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5/7 |

**A remains selected; all three rules and H17 remain killed on wrong-test rate.**

Further checks:

- **Preregistration and boundary:** The primary redefinition, C′ baseline, selection order, and kill already appear in `97470e1`. Decision logic and generation/execution flow are unchanged from the pre-call implementation. All **444 prompts** reconstruct from specification and visible tests and match draw 1’s hashes and model. Rules consume candidate-failure sets; canonical outcomes score them. Candidate execution uses study 16’s `run_generated`.
- **Timing:** Earliest inferred request start is **22:46:34.725**, after the **22:46:23** code commit. Amendment 2 precedes draw 3’s **22:58:27.171** start. Its 73-call snapshot corresponds to **22:51:17.520**; 77 calls had completed by its commit.
- **Floor and recurrence:** The conservative **29/1,188 = 2.4% floor** holds under the passing-tests-kept convention. Draw-2 recurrence is **23/32 versus 13/189**, with Wilson intervals **54.6–84.4% versus 4.1–11.4%**. The **37/222 = 16.7%** figure is marginal prevalence, not the matched comparator. Recurrence does not establish a shared semantic misreading.
- **Identity, retry, cost:** Response identity is **13/222 and 8/222**. AST identity and its intervals reproduce. The malformed-JSON failure, 75-second retry wait, and **31.761-second** successful retry are supported. Spend is **$3.3493315**; neither cap bound.
- **Reporting:** §§1–2 support the narrowed threshold conclusion. They do not establish that paid rules provide no improvement over C′: A adds four correct F-stratum applications. Earlier exploratory intervals, B’s four additions, unique-test retention/removal, passing counts, and the **11.0×, 11.0×, 7.5×** allowance ratios remain correct.
- **Execution limits:** The selected suite returned **38 passed, three failures because no writable temporary directory exists**. Supplementary stdin replay matched **all 1,160 candidate/canonical outcomes**, but does not certify fresh-directory execution or normal-host full-suite green.

No generated test text was found in the changed study files. `execute.py`, `architectures.py`, `src/`, and kernel directories are untouched throughout the branch history. I modified no files; the worktree remains clean.

**not quotable — the claimed results binding still passes when readers see incorrect or misplaced tables.**
