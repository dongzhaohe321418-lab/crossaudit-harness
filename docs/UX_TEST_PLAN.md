# CrossAudit — Comprehensive UX Test Plan

A repeatable, mostly-automatable plan for exercising CrossAudit's experience the
way a real person meets it. It is written so the agent that did **not** build a
change can run it and score the result independently (see `AGENTS.md` §0).

The console is a local web UI, so most of this is executable, not hypothetical:
an agent can drive it (open the page, click, type, screenshot, read JS console
errors, switch theme and viewport) rather than describe it.

---

## 1. Setup — get a live console to test against

```bash
# in a throwaway project directory (not the product repo)
crossaudit console          # prints a background pid and a token'd URL
```

- Drive that URL with the browser tools: `preview_start {url}`, then
  `read_page` / `computer` (click, type) / `read_console_messages` /
  `read_network_requests` / `resize_window` (desktop + narrow) / screenshot.
- Prefer text tools (`read_page`, console/network) to verify state; take
  screenshots for the visual record and for the human's acceptance.
- The console self-retires on idle; `crossaudit console --stop` ends it.
- Keep a **fixed test project** with known fixtures so runs are comparable
  (a small doc project, plus one deliberately large/file-heavy project to
  stress context shaping).

---

## 2. Coverage matrix — test the cells, not just the happy path

**Surfaces** × **States** × **Presentation**. Every surface must be seen in each
state that applies to it, in both themes, on desktop and narrow width.

| Surfaces | States | Presentation |
|---|---|---|
| First-launch / onboarding | empty / first-run | light |
| Chat (send, stream, reply) | loading / streaming | dark |
| Projects list + project control | success | desktop |
| Decision Center (escalations) | **error** | narrow / responsive |
| Audit-loop display (rounds, findings) | **escalation** (BLOCK / budget / provider-down / answered) | (reduced-motion) |
| Settings (all sub-panes, nav) | **long conversation / many rounds** | |
| MCP add / manage; Skills manage | **large / file-heavy project** (context shaping visible) | |
| Usage view; Model routing | offline / provider unavailable | |

A cell is **covered** only when it has been observed (screenshot + read_page),
not merely reasoned about.

---

## 3. Scenario walkthroughs (the must-run set)

Each scenario: **Steps → Expected experience → Observe → Pass/Fail heuristic.**
Run each in light and dark; capture a screenshot per meaningful step and the JS
console (must be error-free unless the error is the thing under test).

### S1 — First contact (new user, first project, first review)
- Steps: fresh project → onboarding → state a simple task ("write a short review
  of X") → watch it run to a verdict.
- Expected: the person always knows what is happening and what to do next; no
  dead ends; the deliverable and the audit result are legible.
- Pass: no unexplained state; a first-timer could complete it without docs.

### S2 — Bad / false-premise input  *(the qled class — high priority)*
- Steps: ask for something that does not exist ("write a detailed review of the
  eled"); then correct it ("I meant qled") and say "continue".
- Expected: a **helpful, Claude-like reply**, not a red "audit failed"; the
  correction is honored; "continue" continues the *real* latest intent.
- Pass: no hard-failure screen for a mere bad/incomplete input; the corrected
  subject is what actually gets produced and what the audit judges.

### S3 — Escalation states are human-actionable
- Steps: force each cause — auditor BLOCK, round budget spent, provider
  unavailable, "answered" (conversational).
- Expected: the Decision Center frames each in plain language with a clear next
  action; "answered" reads as *CrossAudit replied*, not as a failure.
- Pass: every escalation names a cause a non-engineer understands and a next step.

### S4 — Long conversation / many rounds (memory, not amnesia)
- Steps: a chat with many turns and a multi-round build.
- Expected: the thread stays coherent; earlier intent is not forgotten; the
  "+N earlier turns" note appears rather than silent truncation; the transcript
  does not grow unusably.
- Pass: continuity holds across turns; nothing important silently disappears.

### S5 — Large / file-heavy project (context shaping is transparent)
- Steps: run a build in the deliberately large project so files get outlined /
  stubbed.
- Expected: when the runtime condenses context (outline / stub / fold), the
  person can tell it happened and that nothing was lost (it is one `file_read`
  away). *This is the transparency gap in the change queue — probe it hard.*
- Pass: condensation is legible, never silent data-loss to the user's eye.

### S6 — Add an MCP tool / manage Skills  *(known-weak surface)*
- Steps: open the MCP add dialog; add a server; manage skills.
- Expected: the dialog is usable and self-explanatory; "manage skills" goes where
  it says (no mis-navigation).
- Pass: a person can add a tool without guessing; no dead links or wrong jumps.

### S7 — Theme + responsive sweep
- Steps: visit every surface in dark mode and at narrow width.
- Expected: no clipped text, overlap, unreadable contrast, or horizontal
  body-scroll; the layout adapts.
- Pass: every surface is legible and intact in both themes and both widths.

---

## 4. Method — how a scenario is run and scored

1. **Author** implements the change and writes its change contract (AGENTS.md).
2. **Reviewer** (the other agent) runs the affected scenarios against a live
   console, blind to the implementation, and records for each step:
   - a screenshot, the `read_page` structure, and any console/network errors;
   - the observed experience vs the scenario's Expected;
   - timing where it matters (does anything feel stuck with no feedback?).
3. Reviewer files findings with a **severity** (below) and a concrete repro.
4. Findings feed the change queue; each becomes its own small slice.

---

## 5. Severity taxonomy + triage

| Sev | Meaning | Handling |
|---|---|---|
| **S0 blocker** | Data loss, a security/audit-core weakening, a dead end with no recovery | Fix before anything else; audit-core issues also get an adversarial review |
| **S1 major** | A core task cannot be completed, or a false-failure on valid input (S2 class) | Next in the queue |
| **S2 moderate** | Confusing/for-engineers-only wording, mis-navigation, missing empty/loading state | Batched into the polish queue |
| **S3 minor** | Cosmetic — spacing, alignment, a dark-mode contrast nit | Opportunistic |

Triage rule: **an honest-but-ugly experience beats a pretty-but-misleading one.**
Anything that overclaims (a green check that did not verify what it implies) is at
least S1, never cosmetic.

---

## 6. Regression — keep it repeatable

- The S1–S7 scenarios are the standing UX regression set; re-run the affected
  ones before every reinstall, and the whole set before a release.
- Record results in a short run log (date, build, scenario, sev findings) so
  regressions are visible across builds.

---

## 7. CrossAudit-specific risk checklist (fast pass)

- [ ] No jargon on the audit-loop display a non-engineer can't read.
- [ ] No red "failure" for a merely bad/incomplete/false-premise input (S2).
- [ ] "answered" reads as a reply, not a failure (Decision Center).
- [ ] Context condensation (outline/stub/fold) is visible, never silent loss (S5).
- [ ] MCP add dialog is usable; "manage skills" navigates correctly (S6).
- [ ] Settings nav: every item lands on the right pane; no overlap at narrow width.
- [ ] i18n: every new user-facing string has ZH parity (no raw English leaking).
- [ ] Dark mode + narrow width: no clipping, overlap, or body horizontal scroll.
- [ ] No green check implies more verification than actually happened.
