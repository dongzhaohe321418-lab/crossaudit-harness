**Hold the held-out run for checker and interpretation fixes. I found no E14 record-path copy error.**

1. **Copy, freeze and isolation look sound.** E15 correctly renames the manifest, functions, result keys, outputs and ordering seed. Normal entry points target E15’s records; an instrumented state traversal accessed no E14 files. Freeze coverage and closure retain E14’s repairs. The inherited bootstrap seed is harmless. One inherited resilience gap remains: raw audit rows lack `split`, so they cannot independently close construction if both the marker and parsed rows are absent.

2. **The body-form guarantee has holes.** In [`_shape`](</Users/ericdong/Library/Application Support/Claude/scratch-workspaces/74ef214a-bb0b-45f3-a0dd-dab068ffcbe9/c2cff56f-cccf-49f5-bf0f-c2a959dccdde/scratch-2026-11-02-a4ee54/audit/crossaudit-harness/benchmarks/e15/e15.py:117>):
   - **Blocking:** `Match.cases` is never traversed. I reproduced acceptance of otherwise identical `match` blocks containing `return 1` versus `pass; return 2`: different nested statement sequences, counted as the same shape.
   - Non-expression changes also pass, including import aliases and `+=` versus `*=`, contradicting “differing only in expressions”.
   - **Inherited false rejection:** changing an expression in the first statement’s decorator is rejected because confinement starts at the `def` line, placing its decorator outside the permitted body.
   
   All 15 accepted development pairs pass the implemented check; these counterexamples do not establish corruption of those pairs. The two recorded body-form failures correctly exceed the registered token allowance.

3. **E15-1 does not establish the stated code-quantity claim.** It tests preference under matched statement skeletons and approximately bounded Python-token counts. The allowance permits substantial residual asymmetry: accepted **Mbpp/755 has 5 versus 2 tokens**, comparing `_fail(...)` with `None`. Equal counts also permit redundant padding—present in Mbpp/124’s `0 * math.pi` and Mbpp/142’s `False and …`—and different expression-level computation. A long string still counts as one token. Thus “different expressions” does not isolate rule semantics from implementation.

   Also, the cited **+40.0 versus +16.7** compares original conditional-count strata, not branch-body length strata.

Concrete fixes before freezing:

- Traverse every nested statement container, including match cases; preserve non-expression fields and include leading decorators in body boundaries. Add the demonstrated regression cases.
- Narrow the interpretation to **“preference persists under matched statement skeletons and bounded token-count differences”**. For the stronger quantity claim, prespecify equal or counterbalanced lengths; for broader implementation independence, cross rule with presentation.
- State the numerical allowance in the prompt and save/report body counts and shapes. The current analysis omits the preregistered token-count report. Add split labels to E15 raw rows.

Read-only replay reproduced **480/480 valid readings**, **+38.3 [21.7, 55.0]**, and worst-case **+29.7 [6.25, 51.56]**. Prompt rebuilding was unavailable because PyYAML is missing; environment/prompt probes were mocked for state traversal. No files changed or model calls made.