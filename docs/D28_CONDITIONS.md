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
| 1 | No open S0/S1 on merged code | A current cross-vendor audit of the merged tree, not per-branch verdicts collected over time | **SHOWN for the UX surface** — auditor2 audited the combined tree `2c21ce7` (not per-branch): 0 S0, 0 S1. Not shown for the rest of the product. |
| 2 | Frozen fresh-user walkthrough | Clean-HOME first contact with the DMG, completed end to end | **IN MEASUREMENT** — CLI half done on `2c21ce7`. GUI half was blocked by token confinement (D107); the owner granted assistive access and it is verified (D108), so the window is now readable and the product was not weakened to get there. |
| 3 | UX S1–S7 across themes / locales / widths | Cells observed on the packaged build; observed means screenshot + read_page, not reasoned about | **PARTIAL** (D81) |
| 4 | Screen-reader first contact | A task completed via the accessibility tree — *containers present is not contents present* | **IN MEASUREMENT** — same wall as condition 2, same unblock (D108). Never once measured on a frozen build; *completed via the accessibility tree*, not landmarks present. |
| 5 | First three minutes in Chinese | Frozen GUI parity, not source-string parity | **PARTIAL** (D81) |
| 6 | Green suite + mutation-proved guards | Each guard demonstrated red by its own name (D64) | **BELIEVED** |
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
