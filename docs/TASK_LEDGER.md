# Task ledger

Source of truth for who owns what, per `AGENTS.md` §3.2. One row per task.
Agents update their own row's state; the reviewer appends the review verdict.

| # | Task | Owner | Reviewer | Branch | State |
|---|---|---|---|---|---|
| A1 | MCP add-dialog redesign + settings navigation | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | reviewed; S6/S7 verified by the orchestrator |
| A1-fix | Reopening a saved stdio server was refused (codex S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | fixed, suite green — **awaiting independent review** |
| B1 | Transparent context-condensation run events | Agent B (Codex) | Agent A (Claude Code) | `agentB/context-condensation-events` | in progress |

---

## A1 — change contract

```
TASK:        Redesign the add-MCP-tool dialog so a person can add a tool without
             guessing, and fix settings navigation so every settings item opens
             the correct pane and lands on the control it names.

SURFACE:     src/crossaudit/console/page.py (console UI markup/CSS/JS + i18n)
             tests/test_mcp_dialog_and_settings_nav.py (new)
             Audit core touched? NO. auditor/ broker/ ledger/ policy/ dcl/
             receipt/ controller/ are untouched; no change to /api/mcp's
             server-side contract in src/crossaudit/mcp.py.

INVARIANTS:  §1.2 additive / backward-compatible — the register payload sent to
             /api/mcp keeps the same field names and types; every string pinned
             by tests/test_mcp.py and tests/test_settings_ia.py survives
             verbatim. §1.5 never overclaim — the dialog now *states* the
             approval order the backend already enforces instead of implying a
             one-shot save that the backend rejects; no tool is shown as
             approved unless the server actually advertised it. The redesign
             only makes the client agree with the server's existing
             deny-by-default rules; it never relaxes them.

ACCEPTANCE:  1. Full suite green: PYTHONPATH=src .venv/bin/python -m pytest -q
                (baseline to beat: 1513 passed, 2 skipped).
             2. Adding a stdio MCP server end-to-end needs no typed tool names
                and produces no ConfigDenial on the guided path.
             3. Approving a tool is done by selecting a discovered tool, never
                by typing an exact name.
             4. The dialog's primary action is reachable without scrolling the
                whole dialog (footer pinned, like every sibling wizard).
             5. Searching a settings item by its own label ranks that item
                first; clicking it opens that item's pane AND scrolls to it.
             6. The settings search listbox is keyboard-operable
                (Down/Up/Enter/Escape) and its options carry role="option".
             7. Every new user-facing string has a Chinese translation.

UX EVIDENCE: Before: dialog screenshot with the primary action 205px below the
             fold; three consent boxes stacked; "Approved tool names" free-text
             asking for names the server has not yet advertised.
             Reproduced denials against a live console + a real stdio MCP
             server (scratchpad fixture):
               - approve-all + enable on a new server
                 -> "connect the MCP server without Generator access first,
                     review the advertised tool list, then configure and enable it"
               - typing the placeholder's own example names
                 -> "an allowed MCP tool is not advertised by this server"
             After: screenshots per step, light + dark, desktop + narrow,
             recorded by the reviewer per docs/UX_TEST_PLAN.md S6 + S7.

REVIEWER:    codex agent — independent of the author (AGENTS.md §0).
             Agent A does not score its own diff.
```

### Shared-boundary note (AGENTS.md §3.1)

`console/page.py` is a shared file. Agent A holds structural ownership of it for
this round; the codex agent stays off `page.py` and coordinates here before
editing it. Handoff is sequential: implement → hand off → independent review →
fix.

### Findings this change is answering

From `docs/UX_TEST_PLAN.md` §7 and scenario S6, verified live rather than assumed:

| ID | Sev | Finding |
|---|---|---|
| UX-MCP-1 | S1 | The dialog implies one-shot save; the backend requires connect → discover → approve → enable. Both naive paths end in a raw `ConfigDenial`. |
| UX-MCP-2 | S1 | "Approved tool names" is free text requiring exact names the user cannot know until after the first connection. Its own placeholder values are rejected. |
| UX-MCP-3 | S2 | The primary action sits 205px below the fold; `.wizard` scrolls as a whole so the footer is not pinned, unlike `.settings-wizard` / `.runtime-wizard` / `.project-wizard`. |
| UX-MCP-4 | S2 | Three amber consent boxes render at once, two of which the backend refuses together on a new server. |
| UX-NAV-1 | S2 | Settings search ranks the generic group entry above the exact item: "Appearance" → *General*, "Permissions" → *Agent behavior*, "Skills" → *Integrations*. The item you searched for is not what opens. |
| UX-NAV-2 | S2 | The results container declares `role="listbox"` but its children are plain buttons with no `role="option"`, and the search box has no keyboard path into the results. |

---

## B1 — change contract

```
TASK:        Emit a durable, user-visible run event whenever generator context
             is condensed by outline, stub, fold, or bounded guidance, naming
             what was reduced and explaining that the complete source remains
             available with one file_read; surface the event in the run stream.

SURFACE:     src/crossaudit/context/outline.py
             src/crossaudit/cli/build.py
             src/crossaudit/console/streams.py
             src/crossaudit/console/progress.py
             src/crossaudit/console/server.py (snapshot wiring only)
             focused tests under tests/
             Audit core touched? NO. auditor/ broker/ ledger/ policy/ dcl/
             receipt/ controller/ remain untouched. console/page.py remains
             exclusively owned by Agent A this round and will not be edited.

INVARIANTS:  §1.2 additive / backward-compatible — introduce only additive run
             event data and preserve existing shaping output and deterministic
             thresholds. §1.3 frozen/offline — standard library only, with no
             model, dependency, or remote call. §1.5 never overclaim — wording
             says the full content remains available through file_read only
             where the runtime actually preserves that access path; event data
             reports observed reduction rather than implying content deletion.
             Generator RULES are never capped or truncated (§5).

ACCEPTANCE:  1. outline, stub, folded prior results, and bounded guidance each
                produce a durable context_condensed event when reduction occurs.
             2. Each event identifies the reduction kind and affected content,
                and says the full content is one file_read away without claiming
                that generator-visible context is complete.
             3. The console run stream/progress mapping renders the event as an
                understandable user-visible update, with Chinese i18n parity.
             4. No event is emitted when no condensation occurred.
             5. Existing shaping/build semantics remain deterministic and
                backward-compatible; focused regression tests cover the event.
             6. Full suite green:
                PYTHONPATH=src .venv/bin/python -m pytest -q

UX EVIDENCE: Independent reviewer runs UX plan S5 against a deliberately large,
             file-heavy project, verifies the condensation notice in the live
             run stream, and records light + dark screenshots plus page/console
             evidence. Agent B supplies automated event/stream test evidence
             but does not score its own UX.

REVIEWER:    Agent A (Claude Code) — independent of the author (AGENTS.md §0).
             Agent B does not grade or merge its own work.
```

### Shared-boundary note (AGENTS.md §3.1)

Agent B owns the additive event contract consumed by `console/streams.py` and
`console/progress.py`. Agent A owns all `console/page.py` structural markup,
CSS, JS, and its page-level presentation this round. If page.py needs a new
event field or DOM hook, Agent B records the requested contract here and waits
for sequential handoff; Agent B does not edit page.py.

### B1 → A1 page handoff request

Agent B's additive wire contract provides locale-ready copy without requiring
the page to parse event prose:

- `progress.steps[kind=context_condensed].text_i18n = {en, zh}`
- `progress.steps[kind=context_condensed].detail_i18n = {en, zh}`
- `generator_stream[kind=context_condensed].summary_i18n = {en, zh}`

Agent A should make the existing generic run-activity renderer and conversation
turn fallback select `currentLocale` (`zh` for `zh-CN`, otherwise `en`) from
those fields, falling back to the existing `text`, `detail`, and `summary`.
This is a page-only consumer change; no new markup or event parsing is needed.
Agent B will independently review that Claude-authored page change and will not
edit it.

---

## Cross-boundary requests

### A→B / B→A: Chinese parity for the B1 condensation event

B1 acceptance item 3 requires Chinese i18n parity for the new run-stream
condensation notice. The locale dictionary (`ZH`) and its regex fallbacks
(`ZH_PATTERNS`) live in `console/page.py`, which Agent A owns this round, and
`streams.py` / `progress.py` cannot translate on their own — the page localises
by exact text-node match against that dictionary.

**Resolution (sequential handoff, AGENTS.md §3.1):** Agent B lands its slice with
the English strings and lists the exact user-visible strings below; Agent A adds
the matching `ZH` entries to `page.py` in the same round. A generated string
(one that interpolates a count or a filename) needs a `ZH_PATTERNS` regex rather
than a dictionary key — flag which kind each string is.

| String (exact English) | Kind | ZH added |
|---|---|---|
| _(Agent B to fill in)_ | key / pattern | ☐ |

Until those entries exist the notice will render in English under 中文, which
would fail the §7 checklist item "no raw English leaking".

---

## A1 — evidence recorded by the author (not a review)

Per AGENTS.md §0 this is *not* a review. It is the reproduction record so the
reviewer can check the claims independently.

Environment: throwaway project + live `crossaudit console`, driven in Chrome,
with a stdlib stdio MCP server fixture advertising three tools
(`search_papers` read-only, `fetch_record` read-only, `purge_cache` destructive).

**Before (on `main`), reproduced live:**
- naive "approve all + enable" on a new server → `connect the MCP server without
  Generator access first, review the advertised tool list, then configure and
  enable it`
- typing the field's own placeholder names → `an allowed MCP tool is not
  advertised by this server`
- `save-mcp` measured 205px below the fold; the whole dialog scrolled, so the
  footer was not pinned. **Correction to an earlier read:** the button was
  reachable by scrolling — it was below the fold, not unreachable. Sev is S2.
- settings search: "Appearance"→*General*, "permissions"→*Agent behavior*,
  "Skills"→*Integrations* as the top hit.

**After (this branch), reproduced live:**
- guided flow adds the server with **zero** denials; stored state is
  `allowed:[fetch_record, search_papers]`, `enabled:true`, with the destructive
  `purge_cache` correctly left unapproved.
- `enabled` checkbox is disabled with an explanation until ≥1 tool is ticked.
- primary action visible without scrolling; body scrolls, footer stays put.
- Configure reopens on step 2 with prior approvals ticked; Back returns to the
  connection step with values intact.
- search ranking: every probed query now returns its own item first; Enter /
  Arrow keys / Escape operate the listbox; `role="option"` +
  `aria-activedescendant` present.
- "Manage Skills" from both entry points lands on and focuses
  `runtime-skill-select`.
- 中文: every new string renders translated, and switching back to English
  restores the English text (no stale Chinese). Server-supplied tool names and
  descriptions are deliberately left untranslated.
- no JS console errors during the walkthrough.

**Known limits, stated honestly:**
- The reviewer still owns the S6 + S7 sweep: dark **and** light at desktop
  **and** narrow width, with screenshots. The author checked light + dark and
  desktop only, and did not complete a narrow-width pass (the automated window
  resize did not change the page viewport).
- Only the stdio transport was exercised end-to-end. The Streamable HTTP branch
  is unchanged in behaviour but was not driven against a live remote server.
- The re-connect path (changing an existing server's command, then Connect)
  clears approvals until Save. That is deliberate and fail-closed, and the
  dialog says so — but it is a behaviour change worth a reviewer's eye.

### A1 — test results (stated exactly)

- Baseline on `main` before the change: **1513 passed, 2 skipped**.
- This branch: **1529 passed, 2 skipped** (+16 = the new
  `tests/test_mcp_dialog_and_settings_nav.py`). Verified green on two separate
  full runs.
- One intermediate full run reported a single failure in
  `tests/test_projects_ui.py::test_failed_github_setup_is_visible_and_resumes_idempotently`.
  It is **flaky and unrelated to this change**: it passes in isolation, the whole
  `test_projects_ui.py` file passes with this change stashed, and the following
  full run was green. That test forks under a multi-threaded process (pytest
  emits a `fork()` DeprecationWarning for this file), so it is load-sensitive.
  Flagged rather than silently re-run — the reviewer should know it can trip.
- `node --check` over the extracted page script parses clean; no JS console
  errors observed during the live walkthrough.

---

## A1-fix — change contract

```
TASK:        Fix codex's S1: Configure -> Save on a saved stdio MCP server was
             refused with HTTP 400 "approve the exact local MCP command before
             it runs", so no field of an existing local server could be edited.

SURFACE:     src/crossaudit/console/page.py (MCP dialog markup/CSS/JS + i18n)
             tests/test_mcp_dialog_and_settings_nav.py (5 new tests)
             Audit core touched? NO. src/crossaudit/mcp.py is UNCHANGED — the
             server-side rule that a local command must be approved before it
             runs keeps refusing exactly as before.

INVARIANTS:  §1.1 non-bypassable core — the fix is entirely client-side and
             makes the client agree with the server's deny-by-default rule
             rather than relaxing it; the refusal path is proven still live.
             §1.5 never overclaim — consent is not fabricated. What is sent is
             either the box the person just ticked, or the approval they already
             gave for that identical command and arguments (read from the stored
             server row). Change the executable or any argument and it reverts
             to false, the checkbox returns unticked, and the server refuses.

ACCEPTANCE:  1. Configure + Save with no change succeeds.
             2. A timeout-only edit succeeds with no fresh command approval.
             3. Editing the command restores the unticked consent box and the
                server still refuses without it.
             4. Both directions covered by tests.
             5. ZH parity for both new strings.
             6. Full suite green.

UX EVIDENCE: Driven against a live console with headless Chromium (the vendored
             playwright in website/node_modules), stdio MCP fixture advertising
             search_papers + fetch_record (read-only) and purge_cache
             (destructive). Before the fix, reproduced the exact defect:
             step=tools, approve_local_code unchecked, Save -> 400, modal stays
             open, "approve the exact local MCP command before it runs".
             After: all six assertions pass, JS console clean.

REVIEWER:    codex — independent of the author (AGENTS.md §0).
```

### What was driven vs. tested

**Driven in a real browser (headless Chromium, live console), both directions:**
- add server -> consent box shown, approved-note hidden;
- Configure + Save unchanged -> modal closes, no error (the reported bug);
- saved server on step 1 -> "already approved" shown, checkbox hidden;
- timeout 30 -> 45 -> accepted, tool ticks preserved, `allowed_tools` and
  `enabled` intact afterwards;
- edit the command -> consent box returns unticked;
- Save with the changed command unticked -> still refused by the server.

**Covered by test only:** the node-level truth table for `mcpCommandUnchanged`
(whitespace-insensitivity, argument add/drop/change, new server, http
transport). The server-side refusal itself was already covered by
`tests/test_mcp.py::test_stdio_requires_exact_command_consent_and_never_uses_a_shell`,
which is untouched.

**Note on a related behaviour, unchanged and deliberate:** the timeout, calls
per task, command and arguments all live on step 1, so editing one routes
through Connect, which re-probes the server and asks for a Save on step 2 before
the change is stored. Between Connect and Save the stored row is disabled with
no approved tools. That is the fail-closed re-connect path documented in the
first commit, not a regression — but it means a timeout edit is two clicks, not
one, and a reviewer may reasonably want that revisited separately.
