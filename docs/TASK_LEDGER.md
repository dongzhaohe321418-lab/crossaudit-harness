# Task ledger

Source of truth for who owns what, per `AGENTS.md` §3.2. One row per task.
Agents update their own row's state; the reviewer appends the review verdict.

| # | Task | Owner | Reviewer | Branch | State |
|---|---|---|---|---|---|
| A1 | MCP add-dialog redesign + settings navigation | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | reviewed; S6/S7 verified by the orchestrator |
| A1-fix | Reopening a saved stdio server was refused (codex S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | superseded — shipped an S0, see A1-fix-2 |
| A1-fix-2 | Consent bypass in A1-fix (codex S0) + legacy-argument break (S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | reviewed CLEAN, merged in 47863b6 |
| A2 | page.py consumer for the `context_condensed` stream kind | Agent A (Claude Code) | Agent B (Codex) | `agentA/a2-condensation-consumer` | implemented, suite green — **awaiting independent review** |
| S2 | Stream generator output (contract below) | both — split per contract | each other | _(not started)_ | **contract awaiting codex review; no implementation** |
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

### ~~A→B / B→A: Chinese parity for the B1 condensation event~~ — SUPERSEDED

**Closed. Do not act on this request; it describes a design that was replaced.**

The original ask was for Agent B to list its user-visible strings so Agent A
could add matching `ZH` entries to `console/page.py`, because the page localised
by exact text-node match against a dictionary. Agent B solved the problem better
instead: the run event now carries its own translations on the wire as
`text_i18n` / `detail_i18n` / `summary_i18n`, each `{en, zh}`
(`console/progress.py`). The page selects the active locale from those fields
and never re-translates prose, so there is **no string table to fill in and no
`ZH`/`ZH_PATTERNS` entry to add** for the notice copy.

What that leaves for the page, and what A2 actually did (`console/page.py`):

- select on the active locale with a fallback to the plain `text` / `detail` /
  `summary` field, via a `localeText` helper;
- dictionary-translate only the handful of words the *page itself* adds around
  the notice (its label and the word "round"), which are page copy, not event
  copy;
- re-render on a locale change, because wire-localised copy is chosen at render
  time and the text-node translator cannot reach it by design.

**How this was found and why the record matters.** The stale ask survived two
rounds because it lived on a branch neither agent could edit from where they
were working: `docs/TASK_LEDGER.md` existed only on `agentA/mcp-dialog-settings-nav`,
so Agent B could not strike it without an add/add conflict, and Agent A could not
strike it from the A2 branch for the same reason. It was filed as **S3-4** in the
Agent B review, deliberately left open rather than papered over, and closed here
once the Agent A merge put the file on `v5-redesign`. A reader arriving at this
section now meets the correction instead of the stale instruction.

---

### Open owner decision: a command approval binds a path, not the bytes at it

Recorded here because it is referenced from the A1 history and the wording there
was too strong. **Not decided; nobody builds for it or works around it.**

An approved local MCP command is stored and re-sent as `{command, args}`. That
approval therefore binds *a path plus its arguments*, not the contents of the
executable at that path.

**Correction to the A1-fix-2 commit message.** That commit said `mcp.py`
"re-resolves and re-checks the executable at launch". Codex corrected this in
review and the correction stands: `_safe_command()` re-resolves during
**registration**, immediately before the connection probe — but a later
agent-call session launches the **stored absolute path directly**, without
re-resolving or hashing it. The gap between approval and execution is therefore
wider than that commit implied. Flagging the gap was right; the reassurance
attached to it was not, and this entry is the accurate statement.



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

---

## A1-fix-2 — change contract

```
TASK:        Fix the S0 consent bypass codex found in A1-fix (a tick given for
             command B was sent as approval for a later command C, which the
             server then launched), and the S1 backward-compatibility break that
             made a legacy row with an empty or whitespace argument unsaveable.

SURFACE:     src/crossaudit/console/page.py (MCP dialog JS only — no markup, no
             copy, no translation changed)
             tests/test_mcp_dialog_and_settings_nav.py
             Audit core touched? NO. src/crossaudit/mcp.py UNCHANGED.

INVARIANTS:  §1.1 deny-by-default — approve_local_code is now derived solely
             from vector equality with something a human granted; there is no
             path that sends true for a command nobody ticked. §1.5 never
             overclaim — the app can no longer assert an approval the person did
             not give. §1.2 additive — a stored row with lossy arguments
             round-trips verbatim instead of being silently rewritten.

ACCEPTANCE:  1. The original S0 sequence sends approve_local_code=false and
                launches nothing (execution sentinel stays unfired).
             2. Legacy rows with empty / whitespace / blank-only arguments save
                unchanged, byte-for-byte.
             3. 18 adversarial cases pass.
             4. Regression tests assert what is SENT, not what is displayed.
             5. Full suite green.

UX EVIDENCE: Driven with headless Chromium against a live console. The S0 was
             first reproduced on 4071a4d with an execution sentinel: a script
             the user never approved ran and wrote a file. After the fix the
             same script is never launched.

REVIEWER:    codex — independent of the author (AGENTS.md §0).
```

### The reasoning class that shipped the S0

Not a typo — a modelling error, and worth naming so the third version does not
repeat it.

I modelled consent as **a boolean plus one baseline**, and reasoned only about
the single edge between "the form matches the stored row" and "it does not". The
checkbox's own state was treated as inert. So the clearing branch fired only
while the form still matched the row; once it had diverged, the tick was frozen
and rode along to every later command.

Two habits produced that:

1. **I tested the transitions the bug report named, not the state machine.** The
   brief gave two directions — unchanged saves, changed re-requires — and I
   verified exactly those two and stopped. A stateful control needs sequences,
   not endpoints. The break needs three hops (A -> B -> approve -> C); no
   two-step test can see it.
2. **I asserted on displayed state.** My browser checks read `checked` and
   `hidden`. Displayed state was *correct* at every step of the S0 sequence
   until the last one — what was wrong was the value put on the wire. Assertions
   belong on what is sent.

The fix removes the class rather than the instance: consent is stored **as the
{command, args} vector it was granted for**, and `approve_local_code=true` is
emitted only when the live vector equals a vector a human approved. There is no
"clear it under condition X" branch left to get wrong — a mismatch is simply
unapproved, so the failure mode is a refused save rather than an unapproved
launch.

### Adversarial cases executed (18/18 pass, headless Chromium, live console)

untouched form · **A->B->approve->C** · **A->B->approve->C->approve->D** ·
reorder args · add arg · drop arg · middle-change arg · case change on command ·
symlink to the same binary · trailing slash · ".." traversal to the same file ·
empty argument line · whitespace-padded argument · tick then untick ·
tick for B then restore A · transport stdio->http->stdio · reopen dialog after
ticking · binary edited on disk after render.

Plus the three legacy shapes driven end-to-end: `["server.py",""]`,
`["  padded  "]`, `["a","   "]` — each saved unchanged with stored == sent ==
stored-after.

### Known limit, stated rather than papered over

"binary edited on disk after render" keeps the standing approval, because the
vector (path + arguments) is unchanged. A person approves *a path*, not the
bytes currently at it; that gap exists between any approval and any later
launch, and the client cannot close it. `mcp.py` re-resolves and re-checks the
executable at launch. Flagged because a reviewer should decide whether it is
acceptable rather than discover it.
