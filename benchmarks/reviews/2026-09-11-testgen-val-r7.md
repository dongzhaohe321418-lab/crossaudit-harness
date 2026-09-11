# Study 17 (testgen validation) — seventh independent review (gpt-6-astra), 2026-09-11, target 483ab85

**The numbers reproduce unchanged; the claimed rendering invariant remains unsound.** I reconstructed all 31 earlier mutations: every one is rejected. New mutations pass all six binding checks while leaving every generated block byte-identical.

I verified these effects with Pandoc’s GFM renderer and inspected the resulting HTML:

| Accepted mutation | Rendered consequence |
|---|---|
| Insert `<!--` immediately before the §3 heading; the first BEGIN marker closes the comment | All five tables remain, but the three exploratory tables appear under **“Secondaries, as preregistered.”** |
| Surround the document with four-character fences, with three-character “closing” fences immediately inside them | **Zero tables** render; the document becomes code |
| Wrap the P/C anchor and intact block in `<pre>` | Four tables render; P/C becomes preformatted text |
| Insert a heading using `##` followed by a tab before the P/C explanation | P/C and corroboration appear under an unregistered heading |

The fence defect survives a contiguous sweep: **all 34 combinations of backticks/tildes and opening lengths 4–20 passed**, each rendering zero tables.

The [scanner](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/tests/test_testgen_val.py:199) truncates fence delimiters to three characters and tracks neither HTML comments nor raw HTML context. Its heading check recognizes only literal `## ` lines. Consequently, the [claim that rendering follows from the fixed skeleton](/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-testval/benchmarks/code/RESULTS-TESTGEN-VAL.md:258) is false. The repair must validate rendered table inventory and section association, or generate the surrounding structure too.

The scientific checks succeeded:

- **Reproduction:** Both archive manifests verify—20 and 11 entries. All three copied study-16 inputs match byte for byte, as do archived record counterparts. In-memory reporting reproduces `numbers.json`, `exploratory.json`, and `tables.md` byte for byte.
- **Independent arithmetic:** All **870 rule decisions**, 870 arm flags, and **66 rate blocks** match independent aggregation, Wilson calculations, and 10,000 problem-cluster resamples at seed **20260915**.
- **No numerical movement:** Numerical records are byte-identical across rounds 3–6. Every original `numbers.json` value remains unchanged from `eb47c27`. All table lines match round 4 after removing the disclosed arm-table indentation.

| Rule | Wrong among kept | Wilson 95% | Problem-cluster interval | Retained |
|---|---:|---:|---:|---:|
| A | 11/90 = 12.2% | 7.0–20.6% | 3.6–22.6% | 5/7 |
| B | 15/101 = 14.9% | 9.2–23.1% | 6.5–25.5% | 6/7 |
| C′ | 11/86 = 12.8% | 7.3–21.5% | 3.9–23.9% | 5/7 |

**A remains selected; all three rules and H17 remain killed on wrong-test rate.**

Further verification:

- **Preregistration and boundary:** The redefined primary, C′ baseline, selection order, and kill appear in `97470e1`. The earliest inferred request began **22:46:34.725**, after the **22:46:23** implementation commit. All 444 prompts reconstruct and match draw 1’s hashes and model. Decisions use candidate-failure sets; canonical outcomes score them. Candidate execution uses study 16’s unchanged `run_generated` path.
- **Floor and recurrence:** The conservative **29/1,188 floor** is correct under the passing-tests-kept convention. Draw-2 recurrence is **23/32 versus 13/189**; **37/222** is marginal prevalence, not the matched comparator. The revised wording distinguishes them and appropriately qualifies semantic causation.
- **Identity, retry, spend:** Response-hash identity is **13/222 and 8/222**; AST identity and intervals reproduce. The malformed-JSON failure, 75-second wait, and **31.761-second** successful retry are supported. Spend is **$3.3493315**. Amendment 2 precedes draw 3; its 73-call snapshot occurred at **22:51:17.520**, with 77 completions by its commit.
- **Reporting:** §§1–2 support the narrowed threshold conclusion. A retains C′’s applications plus four correct F-stratum applications; “paid rules provide no improvement” is not established. Earlier exploratory, retention/removal, passing-count, and allowance-ratio repairs remain correct.
- **Execution limits:** The selected suite returned **40 passed, three failures because no writable temporary directory exists**. Supplementary stdin replay matched **all 1,160 outcomes**, but does not certify the original fresh-directory execution or normal-host full-suite green.

No generated test text was found in changed files. `execute.py`, `architectures.py`, `src/`, and kernel directories are untouched throughout branch history. I modified no files; the worktree is clean.

**not quotable — the binding still passes when exploratory results render as preregistered findings.**
