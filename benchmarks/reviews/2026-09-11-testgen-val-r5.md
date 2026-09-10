# Study 17 (testgen validation) — fifth independent review (gpt-6-astra), 2026-09-11, target 815d25e

**The numerical results reproduce unchanged. The binding is harder to fool, but still unsound.** All ten author-listed mutations are rejected; additional mutations pass while changing the rendered tables.

I mutated the document only in memory and checked the resulting HTML with Pandoc’s GFM renderer:

| Mutation | Binding result | Rendered consequence |
|---|---|---|
| All ten author-listed mutations | Rejects | Both round-4 examples are fixed |
| Append an incorrect B row after C′, with one leading space | **Accepts** | Displays another B row containing `99/43` |
| Same duplicate, omitting the optional leading pipe | **Accepts** | Displays the same incorrect duplicate |
| Add one extra leading pipe to B’s existing row | **Accepts** | Shifts its values beneath incorrect columns |
| Remove one cell from the table’s delimiter row | **Accepts** | The table no longer renders as a table |
| Put a correct table in an HTML comment; swap the visible table’s interval headings | **Accepts** | Validates hidden content while displaying mislabeled intervals |
| Swap §1’s Wilson/bootstrap headings | **Accepts** | The headline test also accepts mislabeled intervals |

Both results-binding tests pass on these accepted mutations. I also swept duplicate-row indentation from zero through four spaces: zero is rejected; one through four are accepted and display the wrong cell.

The concrete defects are in [_table_rows](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/tests/test_testgen_val.py:206): it stops at a line without a leading pipe, strips **all** outer pipes, skips the delimiter without validating it, and does not distinguish visible tables from commented text. Whole-cell comparisons are now present, but they operate on a different interpretation of the document than the renderer. The repair needs to validate the rendered table’s headers, complete row set, and cells.

The reproduced primary remains:

| Rule | Wrong among kept | Wilson 95% | Problem-cluster interval | Retained |
|---|---:|---:|---:|---:|
| A | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5/7 |
| B | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6/7 |
| C′ | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5/7 |

**A remains selected; all three rules and H17 remain killed on wrong-test rate.**

Other verification completed:

- **Archives and reproduction:** Both manifests verify; all three copied study-16 inputs match byte for byte. Archived record counterparts match repository files. In-memory reporting reproduces `numbers.json` and `exploratory.json` byte for byte. Independent aggregation, Wilson calculations, and 10,000 problem-cluster resamples at seed **20260915** match **all 66 rate blocks**. Suite shapes and AST identity also reproduce.
- **No numerical movement:** Every original `numbers.json` value remains unchanged from `eb47c27`. `RESULTS-TESTGEN-VAL.md` is byte-identical to `27d1dd5`.
- **Preregistration and boundary:** The changed primary, C′ baseline, selection order, and kill appear in `97470e1`. Decision functions remain unchanged from the pre-call implementation. All **444 new prompts** reconstruct from specification and visible tests and match draw 1. Rules consume candidate-failure sets; I found no canonical or hidden-suite input to their decisions. Candidate execution uses study 16’s `run_generated`.
- **Timing and spend:** Earliest inferred request start is **22:46:34.725**, after the **22:46:23** code commit. Amendment 2 precedes draw 3. Its 73-call snapshot corresponds to **22:51:17.520**; 77 calls had completed by its commit. Spend is **$3.3493315**, so neither cap bound. The single malformed-JSON failure, 75-second wait, and **31.761-second** retry are supported.
- **Floor and recurrence:** The conservative **29/1,188 = 2.4% floor** holds under the stipulated passing-tests-kept convention. Draw-2 recurrence is **23/32 versus 13/189**; draw 3 is **26/32 versus 10/189**. **37/222 = 16.7%** is marginal prevalence, not the matched comparator. `Mbpp/160` explains the difference. Response identity is **13/222 and 8/222**.
- **Earlier reporting repairs:** Unique-test retention/removal, exploratory intervals, B’s four stratum additions, passing counts, and Amendment 3 reproduce. §5’s allowance ratios are correctly **11.0, 11.0, and 7.5 times**. §§1–2 support the narrowed threshold conclusion; they do not establish a shared semantic cause or that paid rules provide no improvement over C′. A retains C′’s applications plus four correct F-stratum applications.
- **Execution limits:** The selected suite returned **36 passed, three failures because no writable temporary directory exists**. A supplementary subprocess replay through stdin matched **all 1,160 candidate/canonical outcomes**; it does not certify fresh-directory execution or normal-host full-suite green.

No generated test text was found in the changed files. `execute.py`, `architectures.py`, `src/`, and kernel directories are untouched throughout the branch history. I modified no files; the worktree remains clean.

**not quotable — the claimed results binding still accepts visibly incorrect tables.**
