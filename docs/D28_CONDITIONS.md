# The seven conditions — evidence ledger

`docs/DECISIONS.md` records *what was decided*. This file records *what is
currently shown*, and it exists because of D72: **I had been counting defect
closures as condition evidence.** They are different activities. Every S0 closed
in this cycle was real work, and none of it was measured on the thing the bar is
about — **a packaged build, met by a person.**

Rules for this file:

- A condition is **SHOWN** only with a named artifact produced on a **packaged
  build**. A suite count is not an artifact. A closure label is not an artifact.
- **BELIEVED** means I expect it to hold and have no packaged-build evidence.
  Believed is not partial credit; on the bar it counts the same as nothing.
- Downgrade on rebuild. **Same properties, different bytes is not the same
  claim** — a condition shown on one build is not shown on the next.
- Every row names *what would show it*, so the gap is a task rather than a mood.

| # | Condition | What would show it | Status |
|---|---|---|---|
| 1 | No open S0/S1 on merged code | A current cross-vendor audit of the merged tree, not per-branch verdicts collected over time | **NOT SHOWN — 2 S0 + 3 S1 open** (D113). The merged-tree audit that this row always required has now been run, and it found what per-branch verdicts could not: a removed DCL plugin keeps verdict authority, and a corrupt evidence ledger signs as a tool-free receipt. Both in the audit core. |
| 2 | Frozen fresh-user walkthrough | Clean-HOME first contact with the DMG, completed end to end | **SHOWN on `2c21ce7`/`dd48bf59afe6`** — CLI first contact from a clean HOME end to end, and GUI first contact `window_reachable=yes first_screen=pass blocked_by=none`. The token never gated this path: the app renders the console in-window and the token gates external browsers only, so D107's tension did not exist (D111). Voids the moment `src/`, `tests/` or `packaging/` moves. |
| 3 | UX S1–S7 across themes / locales / widths | Cells observed on the packaged build; observed means screenshot + read_page, not reasoned about | **PARTIAL, close** — **40 cells, 88/88 observations** on the packaged core, all four gap surfaces seeded (conversation, settings, hub, onboarding), **no new mechanism**. `still_unreachable=none-on-this-console`; the app-mode GUI window remains a separate instrument (native AX, not CDP). 2 confirmed leaks (`Project history`, `Files produced`), 1 candidate **withdrawn** after investigation. `unnamed=0` in the DOM tree but **1 in the native AX tree** (the composer) — the engines disagree, and a screen reader uses the second one. |
| 4 | Screen-reader first contact | A task completed via the accessibility tree — *containers present is not contents present* | **NOT SHOWN** — reported `pass` on `0 unnamed of 5`, which is naming coverage, not the condition. The condition is **a task completed through the accessibility tree**; grading a naming check as completion would be *containers present, contents absent* committed in the ledger written to prevent it. Also `AXDescription` empty on all five. |
| 5 | First three minutes in Chinese | Frozen GUI parity, not source-string parity | **PARTIAL** (D81) |
| 6 | Green suite + mutation-proved guards | Each guard demonstrated red by its own name (D64) | **PARTIAL, unmerged** — 1,448 guards swept; 14 proven unable to fire on the property their name claims, all 14 now renamed or given behavioural cases; `mutation_missed` stratified from 359 to **0 actionable**. Evidence is `audit/dead-guard-sweep d066943`, **not merged and under cross-vendor review**, and its author wrote the guards it verifies. Not SHOWN until that review returns. |
| 7 | Invariants demonstrated | The disk-vs-cited sites guarded, each with its mutation | **PARTIAL** — frozen console enforces loopback + token against an unauthenticated local request (D103); the disk-vs-cited sites remain unguarded |

## Standing gaps

- **Condition 1 is the one most likely to be wrong.** Branch verdicts were
  issued against integration *as it stood before the other branches landed*.
  Four changes to one surface, none reviewed against the other three, is the
  class that has produced the sharpest findings of this cycle (D101).
- **Conditions 3 and 4 share a mechanism and a ceiling.** The guards on the
  surface a person actually looks at are largely **source-text assertions**, so
  a green suite proves changes do not conflict *as text* and proves nothing
  about what rendered. `design/observation-layer` is the only mechanism standing
  on the far side of that line.
- **Condition 6's failure mode is silence.** Three tautological guards were
  found in this cycle (D64, D97, D100) — tests that named a guarantee, asserted
  nothing, and stayed green. A guard that cannot fail occupies the slot a real
  one would take *and reports success.*
- **Condition 2 is the cheapest and covers the most.** Per D72 a single
  clean-HOME packaged walkthrough reaches 2, 3, 4 and 5 at once, because those
  four are all about a person meeting a build rather than about code being
  correct.

## Corrections to this file

**Condition 1, same session.** I recorded it as *shown for the UX surface* on the
strength of a cross-vendor `0 S0, 0 S1`, and twenty minutes later an S1 turned
up on that surface (D109).

The audit was not wrong and neither was the count. **I widened a verdict past
its scope**: auditor2 examined the combined render path of three branches, and I
wrote it down as though it covered the console. That is the same error as
counting defect closures as condition evidence (D72), one level up — *a real
result, recorded against a claim larger than the result.*

RULE: **a condition's row records what was examined, not what was concluded.**
"0 S0, 0 S1" is not an entry; *"0 S0, 0 S1 across the combined render path of
three branches at `2c21ce7`"* is. The second one cannot be quietly widened,
because the scope travels with the number.

**Condition 6, a caveat that outranks the numbers.** The sweep's own author
flagged it in the commit message rather than waiting to be asked: *these are
guards I wrote and verified with my own mutations — particularly the XSS case,
since I chose both the payloads and the mutations that prove they matter.*

**A guard proved by the person who wrote it is exactly the closed loop this
product exists to break**, and it does not stop being one because the person is
careful. The cross-vendor reviewer's first job is a payload the author did not
choose: **an XSS guard that only catches the attacks its author imagined is
close to no guard at all.** Until that returns, condition 6's evidence is a
claim about a claim.
