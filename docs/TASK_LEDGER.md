# Task ledger

Source of truth for who owns what, per `AGENTS.md` §3.2. One row per task.
Agents update their own row's state; the reviewer appends the review verdict.

| # | Task | Owner | Reviewer | Branch | State |
|---|---|---|---|---|---|
| A1 | MCP add-dialog redesign + settings navigation | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | reviewed; S6/S7 verified by the orchestrator |
| A1-fix | Reopening a saved stdio server was refused (codex S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | superseded — shipped an S0, see A1-fix-2 |
| A1-fix-2 | Consent bypass in A1-fix (codex S0) + legacy-argument break (S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | fixed, 18/18 attack cases, suite green — **awaiting independent review** |
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

---

## Decision record — authority, and the decisions taken under it

The owner has delegated development direction and design direction to the
engineering manager. Product and design calls are made here and recorded here;
they do not go back to the owner. What still goes to the owner is a short list of
things the manager is not permitted to do rather than not competent to decide:
entering credentials or authenticating an account, pushing or publishing
anything, and any spend or outward-facing action. Those are boundaries, not
decisions.

Every decision below is binding on the team until superseded by a later entry in
this file. A superseded decision is struck with its reason, never quietly edited.

### D1 — The add-MCP dialog: the two-step wizard is the design

A request arrived to lock in "variant A" of three dialog variants. There were no
three variants. Agent A, asked directly and told explicitly not to reconstruct a
history to fit the question, reported that it produced exactly one design and
never offered a choice between alternatives. What exists in threes is review
rounds: 52b0dd8 (the redesign), 4071a4d (the Configure→Save fix), 293110b (the
consent-vector rebuild).

**Decided:** the two-step wizard — Connect, then Approve tools — is the design of
record. It is merged at 47863b6. No variant work is commissioned.

The reasoning is not merely that it is what exists. The dialog's shape is forced
by the server's own rule: /api/mcp requires connect → read the advertised tools →
approve named tools before the Generator may call anything. A single flat form
cannot express that order, which is why both natural paths through the old form
ended in a raw denial. A design that contradicts the security model it sits on is
not a stylistic option, so a variant round would have been theatre.

The design/UX engineer's independent assessment stands as the input to the NEXT
iteration of this surface. Its findings will be triaged and scheduled like any
other; they do not reopen D1.

### D2 — Auditor vendor: codex now, gemini only if the owner authenticates

True third-vendor independence needs gemini, which requires a one-time Google
login. That is a credential action, outside what the manager may perform.

**Decided:** the independent auditor is a codex agent that writes no feature code.
Against claude-authored code this is properly cross-vendor. Against
codex-authored code it is same-vendor, different-session — weaker, and AGENTS.md
§2 requires the merge commit to say so rather than gloss it. Where a codex-
authored slice touches the audit core, it additionally gets an engineering review
from the claude implementation engineer, so no audit-core change reaches a merge
on a single vendor's judgement.

### D3 — Roadmap order

Slice 1 (surgical edits as the default write path) merges as soon as S1-2r is
closed; it is the largest measured win, 229 bytes against 68,117 for the same
edit. Then slice 2 (streaming), which does not shorten a turn by a millisecond
but removes the silence — and since local overhead measured under 0.2% of a turn,
perceived latency is the only latency there is to win. Then slice 4 (auditor
reasoning effort per tier). Then the mandatory file_read before editing an
outlined file, whose acceptance criteria are already fixed: mean rounds-to-PASS
and edit-refusal rate, split by whether the target was inlined or outlined.

Slice 3 as originally briefed — an async or pipelined audit — stays **rejected**.
The audit is the loop's branch condition, not a side effect: round N+1's prompt
does not exist until round N's audit produces its findings. The only pipelined
form is speculative generation, which doubles provider spend on exactly the
blocked rounds the round budget exists for, and requires showing the user work
that a late BLOCK then retracts. The replacement experiment — skipping the
auditor model call when the deterministic tier has already hard-failed, since the
verdict cannot change — is measurable and stays queued behind the four above.

### D4 — Slice 2 (streaming) contract: countersigned with binding amendments

The design was proposed by the claude implementation engineer and countersigned
by codex, which owns the half of the split where most of these consequences land.
Codex's amendments are ACCEPTED and are binding on both halves. The contract text
on `agentA/a2-condensation-consumer` must be reconciled to this entry at rebase;
where the two disagree, this entry wins, so there is one contract and not two.

Accepted as proposed: one new `RunEvent.kind`, `generation_chunk`; no new
`RunState` and no transition-table change; ordering by explicit `stream.seq`, so
a consumer seeing 0,1,3 knows 2 is missing; explicit termination rather than an
inferred one; and no page-side stall timer — stalls stay with the existing lease
heartbeat, `run_stalled` and `provider_unavailable`. Codex confirmed that last
point survives contact with `runtime/runs.py`: chunk appends renew the lease, so a
silent provider produces no heartbeat and gets the existing narration. The page
does not invent a second timer.

Amendments, each of which changes something real:

1. **"Process-local" was false, and that matters more than it looks.** Streamed
   text lands in the SQLite operational journal and persists under existing
   retention — up to 14 days. The honest formulation is *local operational-journal
   data, subject to existing retention*, and it remains excluded from evidence,
   tool results, auditor prompts, commit messages, receipts and the ledger. The
   P2 guarantee is unchanged; the sentence describing it is now true. A contract
   that had shipped saying "process-local" would have been an §1.5 overclaim
   written into the design rather than into the code.
2. **`response_sha256` is defined exactly**: SHA-256 of the complete assembled
   completion *text*, UTF-8 encoded, matching today's `sha256_text(text)` — not the
   provider's HTTP response body. Chunks are never evidence, and now the sentence
   saying so cannot be satisfied by digesting the wrong bytes.
3. **Carrying the stream on `waiting_reason` is rejected.** That field is
   run-level, cleared by later events, and absent from individual event
   projections. Slice 2 adds a validated `RunEvent.stream` mapping persisted in an
   additive `stream_json` column.
4. **Chunk granularity, which was the open question**: emit the first decoded
   text immediately, then flush at 200 ms or 8 KiB, whichever comes first, with
   incremental UTF-8 decoding and residual text flushed before the terminal event.
   Sequence numbers are assigned *after* coalescing, so they stay contiguous from
   the consumer's view and the gap rule holds. The journal neither renumbers,
   coalesces, nor caps stream rows. Coalescing at the provider is what keeps a
   token-per-event stream from putting thousands of rows in the journal.
5. `generation_chunk` text bypasses the journal's 400-character narration
   truncation, while staying bounded by the 8 KiB chunk contract.
6. **SSE delivery must be incremental**, not a repeated re-serialisation of the
   whole 200-event snapshot tail — otherwise a feature whose entire purpose is
   perceived speed would make the console slower the longer a run gets.
7. **On any sequence gap the page marks or discards the incomplete draft.** It
   never concatenates across a gap and never presents the result as complete.
8. Termination is clarified: provider-controlled completion or failure emits
   `complete` / `aborted`, but cancellation, process death and run failure may
   prevent that callback, because `RunCommandService` moves to `CANCELLING` and
   rejects later generation events. The existing run-terminal or liveness event
   then supersedes the open stream.

Unchanged and non-negotiable: streamed text is unaudited by construction and must
be unmistakably a live draft — no download, no Files panel, no deliverable
styling, visibly superseded when the round commits.

### D5 — The ranking metric is human pain, not engineering severity

Direction from the owner: make CrossAudit genuinely good to use, from the point of
view of the person using it. That is now the top-line goal, and it changes how
work is ranked rather than merely adding items to the list.

**Operationally, what "good to use" means here.** CrossAudit's honest problem is
that it does something slow and invisible — it writes, then an independent auditor
judges — and every second of that is a second the person is looking at nothing. So
the experience goals, in order:

1. **The person always knows what is happening and what to do next.** No silent
   waits, no dead ends, no state that needs the source code to interpret.
2. **Nothing is ever claimed that was not done.** A green check that implies more
   verification than actually happened is worse than an honest failure. This is
   §1.5, and it is a usability rule before it is an integrity rule: a product that
   overclaims teaches people not to trust the parts that are true.
3. **A bad or incomplete request gets a helpful reply, not a red failure.** The
   audit exists to judge work, not to punish typing.
4. **Speed where it is felt.** Local overhead measured under 0.2% of a turn, so
   perceived latency is the only latency there is to win. Streaming does not make
   a turn shorter; it removes the silence, which is the whole complaint.

**Re-ranking.** Slices are now ordered by how much a real person is hurt by the
problem, not by how interesting it is to fix. An engineering S3 that a first-time
user hits in the first two minutes outranks an engineering S1 buried behind a
setting nobody reaches. Severity still governs whether something BLOCKS a merge;
it no longer governs what we work on next.

**Standing commission.** The design/UX engineer owns a recurring first-contact
walkthrough: approach the product as a person who has never seen it, run the
UX_TEST_PLAN scenarios end to end, and report where a human actually gets stuck,
ranked by how badly it hurts them and how early they hit it. Its findings feed the
roadmap directly. Engineering judgement decides HOW to fix; the human-pain ranking
decides WHAT gets fixed first.

**What does not change.** §1 is not negotiable for usability. We do not buy a
smoother experience with a weaker audit core, a silent truncation, or a reassuring
sentence that is not true. Where a genuinely better experience appears to require
weakening an invariant, that is a decision to escalate, not a trade to make
quietly.

### D6 — First-contact walkthrough: the roadmap is re-ordered around what it found

The design/UX engineer walked the product from an empty directory as a person who
had never seen it. Its findings outrank everything currently queued, so the
roadmap moves. Recorded in full because these are the defects that decide whether
anyone gets far enough to care about the rest.

**P0 — the console silently eats your first message.** Hit at roughly sixty
seconds. Type a task, press Send, nothing happens: no spinner, no error, the
thread still reading "What should CrossAudit work on?". The server is not silent —
`POST /api/say` returns HTTP 400 with a plain reason naming the missing
credential. The client discards it. Worse, the send creates a rail entry titled
with the person's own sentence, which opens onto the same empty placeholder;
three attempts produced three identical empty chats. A person concludes the
product is broken, or that they typed something wrong. The fix is to render the
reason that already comes back.

**P0 — four green ✓ for verification that never happened.** On screen at first
paint: "Deterministic checks ✓ convergence ✓ provenance ✓ schema ✓ units", four
lines above "Ledger: 0 Audits 0 Passed 0 Blocked", with zero artifacts, zero
receipts, and the generator never run. The ✓ has no not-yet-run state. Two more of
the same family: the panel reports "8 blocker rules" for a constitution holding 7
BLOCKER and 1 ADVISORY, and `doctor` prints [PASS] on a line whose own text says a
guarantee is not being enforced. This is §1.5 at the exact point where the product
makes its central claim, and D5 goal 2 says a product that overclaims teaches
people to distrust the parts that are true.

**P1 — setup says Ready, and the next command it recommends says not ready.** One
command apart, with the product routing people between them. `init` does warn
about the missing key, but as one line scrolling above a large green box, and it
then recommends `build`, which cannot work either. It also prints "Run crossaudit
init" while the person is inside `crossaudit init`. And `doctor`, whose tagline is
"check everything", never checks the generator key — the one that stops `build` in
round one.

**P1 — the person's constitution is somebody else's, and they never saw it.** A
plain-prose task produced `# Constitution — <PROJECT>` with the placeholder
unreplaced and 7 BLOCKERs about metadata.yml, results.json, quantities and
convergence. The same screen promised the constitution would be "drafted from
this, shown to you, and committed only if you agree". It was not drafted, not
shown, and committed anyway. Their first real build is then blocked for lacking a
file a prose review would never contain — which is the moment the audit stops
reading as a second opinion and starts reading as obstruction.

**P2** — the Decision Center offers every action except the one that works
("Retry provider" fails identically on a missing credential, while the route that
does reach an API-key field is unlabelled); jargon on the surfaces newcomers are
sent to first; and the front door headlines `crossaudit run` while omitting
`build` and `console`, so the generation half of the product is missing from the
first thing anyone reads.

**Re-ordering, per D5.** These displace the MCP dialog batch and the streaming
slice. Streaming was going to be the next speed investment; the walkthrough's
answer to that question was that finding 1 is silence with *no work happening at
all*, so streaming would not have moved that pixel, and a first-timer cannot even
reach the state streaming improves until the send path renders its errors. Fix the
send path first. Streaming remains the right investment after it.

**What the walkthrough could not reach**, and did not infer: the false-premise and
correction scenario, long conversations, live context condensation, and three of
the four escalation causes. All need a live generator and auditor, which means
provider calls. The engineer found the owner's real keys present and deliberately
did not use them, on the grounds that a live run spends the owner's money and
sends project content to third parties. That judgement was correct and the request
is with the owner.

**A correction to the manager's own record.** AGENTS.md §3.5 was committed to the
wrong branch — it landed on `agentA/mcp-dialog-settings-nav` rather than on
v5-redesign, because the manager's shell working directory had drifted. The design
engineer caught it while reading the rule it had been told to follow. It is now
cherry-picked onto v5-redesign and the stray commit removed from the branch that
had already been reviewed at 293110b. The rule that a claim must be checked rather
than assumed applies to the person writing the rules.

### D7 — When a defect class survives three fix rounds, stop patching it

Speed slice 1 has now been through five review rounds. Every round found a real
defect, every fix was correct as far as it went, and the same two classes kept
coming back in a shape nobody had tested:

  R1  a stale OLD block laundered into a fabricated conversational answer, with
      the lie switching on at 40 characters of payload.
  R2  a malformed edit block still reaching the conversational gate; an
      order-dependent parser scan.
  R3  the fix for R2 broke a protected property — prose that merely NAMED the
      marker became a hard failure.
  R4  the fix for R3 restored it, and the sweep was flat.
  R5  the audit found the SAME fabrication defect in an envelope with no OLD or
      NEW section at all: format below 40 letters, conversational above. Both
      earlier sweeps had used a shape that always contained an OLD section, so
      the test named "No payload size may turn a routed edit failure into
      model-authored prose" never executed the class it claimed to exclude.

That is not five careless engineers. It is a decision being made by accumulating
conditions — has it routed to the edit parser, does it carry an OLD section — where
each condition is correct for the shapes anyone thought to try, and the class is
never closed because the shape space was never enumerated.

**The rule.** When a defect class survives three fix rounds, the next change may
not be another condition. It must be a decision that is correct by construction,
and its acceptance must be an EXHAUSTIVE SHAPE MATRIX rather than a sweep of one
shape: every combination of the structural dimensions that distinguish the cases,
crossed with a contiguous sweep of whatever continuous parameter the bug varied
with. If the matrix cannot be enumerated, the decision is not yet well defined and
that is the actual finding.

This is §3.5 taken one step further. §3.5 says a test must execute what it claims.
D7 says that when a claim is about a CLASS, executing one member of the class is
not executing the class.

**Applied to slice 1**, three things must become correct by construction rather
than by condition:
- What counts as a machine-envelope reply, so no payload of any shape or length can
  be presented to a person as something the model said.
- File identity: paths are canonicalised at one point and keyed by that. Today
  `work/a.txt` and `work/./a.txt` validate and resolve independently, both write to
  the same physical file, and lexical ordering decides which edit survives while the
  other is silently discarded. An ambiguous reply must refuse, not partially apply.
- Byte handling: the edit resolver reads with newline translation, so editing one
  line of a CRLF file rewrites every line ending in it. That makes the slice's
  central safety claim — the committed tree, and therefore the auditor's view, is
  byte-identical to the whole-file path — false, and it makes a "surgical" edit a
  whole-file rewrite in disguise.

**On vendor independence, honestly.** This audit was same-vendor: a codex auditor on
codex-authored code. Asked which findings a different vendor would more likely have
caught, it named exactly the two it had just found — the assumption that raw path
strings identify files uniquely, and that "no trailing newline" was the complete
boundary of byte identity. It found the blind spot it predicted it would share.
That is a point in favour of the auditor and not a reason to relax D2: it says
nothing about what a same-vendor reviewer would still be missing.

### D8 — The constitution is the standard; the audit is the mechanism

I asked the design engineer the question I could not answer: if a person can
freely weaken their own constitution at the moment it is created, what is the
audit worth? Its argument is better than my framing and I am adopting it as
policy.

**The line is drawn at concealment, not at content.** The constitution is the
STANDARD; the audit is the MECHANISM. §1.1 protects the mechanism — independence,
evidence-only, deny-by-default, the hash chain — and none of it is touched by what
the standard says. A weak standard does not produce a weak audit. It produces an
honest audit of a weak standard, which is a legitimate thing for a person to
choose. The failure mode that would actually matter is a receipt implying a
stronger standard than was applied, and we are already protected from it: every
audit cites the constitution commit, and rule changes take effect only between
cycles. So nobody can amend their way out of a decision already made — which is
the concrete answer to "edits it into meaninglessness the first time it blocks
them."

**What follows for the design: show, do not police.** No warnings on a minimal
constitution, no "are you sure". Instead the between-cycles rule is said out loud
— *changing the rules never changes a decision already made* — because that single
sentence is what makes editing safe to offer freely, and it converts the worry
into a true statement the person can rely on.

Consequences adopted:
- The least-effort path is three NAMED choices with a default, preceded by four
  plain-language consequence lines and two visible alternatives — not a bare "I
  agree" checkbox. Taking a default among named options is a real decision;
  agreeing to something unread is the rubber stamp we were trying to avoid.
- The minimal option is called "Only what I write myself" rather than "Minimal",
  so its name says what it gives up.
- Provenance is carried by ATTRIBUTION, not by a disclaimer: the drafted path
  quotes the person's own sentence under the rule it produced; the template path
  has nothing to quote, and that absence is the signal. The word "drafted" may
  appear only when a draft happened.
- `crossaudit amend` is provider-backed, so it cannot run in the keyless state —
  yet today's fallback copy offers exactly that as the edit route. $EDITOR becomes
  the keyless path and amend is not offered without a key.

### D9 — A suggested action must prove it can change the situation

From the same review. The Decision Center currently offers "Retry provider · use
the current connection" for a missing credential, which fails identically, while
the route that does reach an API-key field is unlabelled. The root cause is
structural rather than editorial: the "Suggested" tag is static markup on the
reopen radio, and although its LABEL is rewritten per cause, the tag itself can
never move to another option or disappear.

The rule: capability is tested PER INSTANCE against a field the failure actually
carries — `retryable` is already sent — not per action-kind. An absent field means
not-suggestible, which is fail-closed. If nothing is capable, suggest nothing. An
action that cannot possibly work is worse than no action, because it spends the
person's last confidence at the moment they have least.

And the subtle part, which is the reason this is a rule and not a conditional:
`stop` is always capable and must never be suggested. Capability is necessary but
not sufficient — a suggested action must also be a step toward what the person
came for.

**Architecture note, adopted:** the send-path rule and the suggested-action rule
are the same rule wearing two hats. If they ship as separate slices they will
diverge. Remediations are minted ONCE, server-side, in order, and both surfaces
consume them.
