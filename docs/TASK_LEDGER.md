# Task ledger

Source of truth for who owns what, per `AGENTS.md` §3.2. One row per task.
Agents update their own row's state; the reviewer appends the review verdict.

| # | Task | Owner | Reviewer | Branch | State |
|---|---|---|---|---|---|
| A1 | MCP add-dialog redesign + settings navigation | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | reviewed; S6/S7 verified by the orchestrator |
| A1-fix | Reopening a saved stdio server was refused (codex S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | superseded — shipped an S0, see A1-fix-2 |
| A1-fix-2 | Consent bypass in A1-fix (codex S0) + legacy-argument break (S1) | Agent A (Claude Code) | Agent B (Codex) | `agentA/mcp-dialog-settings-nav` | reviewed CLEAN, merged in 47863b6 |
| A2 | page.py consumer for the `context_condensed` stream kind | Agent A (Claude Code) | auditor (codex) + design | `agentA/a2-condensation-consumer` | audit findings closed — **awaiting re-review** |
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
launch, and the client cannot close it.

~~`mcp.py` re-resolves and re-checks the executable at launch.~~ **That sentence
is false and is struck.** The independent auditor executed the case rather than
reading it: `_safe_command()` re-resolves during REGISTRATION, immediately before
the connection probe, but later agent-call sessions launch the stored absolute
path directly, without re-resolving or hashing. It proved it end to end —
registration probed one version of a file, a later call launched a replacement at
the same path. So the gap is wider than this entry originally claimed, and nothing
downstream of registration closes it.

The gap is now stated in the product itself rather than only here: the approval
copy says the approval follows the path and arguments, not the file's contents,
and that software at that path may change before a later run.

## A3 — change contract (the first three minutes)

Recorded here late, and that is the point: batches 1-3 carried their contracts
only in commit messages, so an auditor opening this file found the fix round and
nothing it was fixing. The contract belongs where the reviewer looks.

```
TASK:        Close the D6 walkthrough's setup findings: init and doctor
             contradicting each other, green ticks on untested lines, a
             constitution written and committed unseen, the laboratory contract
             given to a prose project, and a front door that omits half the
             product. Batch 4 adds the science inference as a PROPOSAL WITH ITS
             GROUNDS (SPEC 3 §3.5), which was left last because it needs a
             provider to fire.

SURFACE:     src/crossaudit/cli/{main,wizard,tui,build}.py, config.py, errors.py
             tests/test_{first_three_minutes,constitution_moment,doctor,tui,
             science_proposal}.py
             Audit core touched? NO. Nothing under auditor/, broker/, ledger/,
             policy/, dcl/, receipt/ or controller/ is read or written. The
             deterministic pack is SELECTED here; its implementations are not
             touched.

INVARIANTS:  §1.5 never overclaim, which is the whole slice. Also §1.2: the
             machine contract is unchanged — EXIT_CONFIG still returns 20,
             `--json` still carries kind and reason, `doctor --all` still prints
             every line, and `as_dict()` gains no key.

CHINESE PARITY: **NOT APPLICABLE — the CLI has no i18n mechanism at all, tracked
             as D16.** `LANG=zh_CN.UTF-8` renders English on every CLI surface;
             there is no gettext, no reachable translation table, and nothing
             that maps a CLI string to Chinese. Adding ZH entries here would
             produce data nothing reads, which is a §1.5 overclaim wearing a
             translation's clothes. This slice therefore reports parity as not
             applicable rather than as satisfied, per D16, and no console string
             changed. Design has ruled that CLI i18n wave 1 is the ENTIRE init
             wizard rather than the constitution moment alone; the extraction
             notes below are written for that wave.

ACCEPTANCE:  Batches 1-3 as recorded in ff947ae, 0f99e1f and 134a881.
             Batch 4 (this round):
             1. The pack is proposed only where the DRAFTED RULES supply the
                reasons; one incidental term match is not a shape.
             2. The grounds name the person's own rule and, where the drafting
                model attributed it, quote their own words. Nothing is invented.
             3. Accepting it reaches `checks:` in crossaudit.yml; refusing it
                leaves the general pack and keeps the drafted rules.
             4. A prose project is never asked at all.
             5. With no terminal, nothing is proposed and the written config is
                unchanged — silence still never selects the laboratory contract.
             6. Two D10 counterfactuals, each mutating the shipped code.
             7. Full suite green.

REVIEWER:    codex (w3) — cross-vendor, independent of this author
UX REVIEW:   design (w4) — CLI screens; returned MERGE AFTER FIXES on batches
             1-2, all four items closed at c5fb6bb
AUDIT:       auditor — honesty audit in progress, scoped shallow by the manager
```

### What batch 4 actually changes, stated precisely

It does **not** pick a constitution. On the drafted path the constitution is
already the person's, distilled from their own sentence. What batch 4 proposes
is the deterministic `checks:` list — the half batch 2 left welded to a starting
point that nothing revisits after the draft succeeds.

That weld was a real defect and this is the fix for it. Before batch 2 the CLI
gave every project the science pack, which is what the walkthrough met as seven
BLOCKERs about `metadata.yml`. Batch 2 made it always general, which is right for
a prose review and silently wrong for real science: the rules get drafted from
the description, and the machine checks that would verify those very rules never
run. Worse, the only route to the science pack — "Use a different starting
point" — DISCARDS the draft, so "rules drafted from what I said" and "the science
checks" were mutually exclusive. They no longer are.

### Note for CLI i18n wave 1 — where the strings will and will not come out

Written now, while in the file, because the cost is very unevenly distributed.

**Cheap.** `STARTING_POINTS` — labels, hints, consequence lines and the new
per-point `frame` — is already module-level data keyed by starting point. It
extracts to a table almost mechanically. `SEVERITIES`, the option labels in
`_show_and_agree`, and the four `tui.Option` labels are short and self-contained.

**Moderate.** Nearly every sentence in `run()` is an inline f-string inside a
`tui.note`/`tui.warn` call, interpolating a path, an env var name or a vendor.
Each needs to become a keyed template with named slots. There are on the order of
forty of them and they are mechanical but individually hand-checked, because
several read as one sentence across two calls.

**Genuinely awkward, flag it before wave 1 starts.**

1. `tui.select`'s hint is built in `tui.py` as
   `f"↑↓ to move · enter to choose · or type 1-{typeable}"`. It is one string
   shared by every menu in the product, and the count is interpolated. It needs a
   plural-aware template, and it is the string a translator will meet first.
2. The new grounds line interpolates a rule ID, a rule TITLE and the person's own
   words — all three model-generated and untranslatable — into a sentence whose
   word order differs in Chinese. It has to become a template with three slots
   rather than a concatenation, or the Chinese will read as English with Chinese
   words in it.
3. `_reason_inside_setup` interpolates the same env var name twice into one
   sentence. Fine in English; in Chinese the second mention usually drops.
4. `tui.fingerprint` returns `"{n} chars, ending {tail}"` and is embedded in a
   larger sentence by its caller, so two strings must be translated as one unit
   or neither will read correctly.
5. Width. `tui.WIDTH` is 72 and the wrapper counts display columns, which the
   existing `test_wrapping_does_not_overflow_on_chinese` already pins — but the
   boxes in `run()` size themselves from English content. Chinese is roughly half
   the character count at double the width; the boxes want re-measuring, not
   re-wrapping.

---

## A3-fix — change contract (first-three-minutes, design review round 1)

```
TASK:        Close the design/UX engineer's MERGE AFTER FIXES on batches 1 and 2
             of the first-three-minutes slice: the D17 accessibility overclaim at
             wizard.py:325, the print order of the D8 sentence, and two S3s — a
             remedy that names the command the person is inside, and a frame that
             promises a check over a list describing the absence of checking.

SURFACE:     src/crossaudit/cli/tui.py     (select: numbering, number entry, the
                                            spoken outcome; two pure seams)
             src/crossaudit/cli/wizard.py  (the constitution moment: docstring,
                                            print order, per-starting-point frame,
                                            the in-setup remedy)
             tests/test_tui.py, tests/test_constitution_moment.py
             Audit core touched? NO. Nothing under auditor/, broker/, ledger/,
             policy/, dcl/, receipt/ or controller/ is read or written here.

INVARIANTS:  §1.5 never overclaim, three times over. The docstring claimed a
             screen reader receives "the numbered options" of a menu that was not
             numbered; D17 says number the options rather than soften the
             sentence, so the menu is numbered, the number selects, and the
             outcome is said in words — then the sentence is rewritten to
             describe what is now true rather than what we wished were true. The
             consequence frame no longer says "it will check that" over lines
             describing what is not checked. The keyless remedy no longer names a
             route that cannot be taken from where it is printed.
             §1.2 additive: `select` keeps its signature, its return value and
             its non-interactive fallback; `footer` still overrides the hint.

ACCEPTANCE:  1. Typing an option's number chooses that option, on a real pty.
             2. Every option is numbered and the chosen one is named in words,
                with every escape code stripped — the reading with no colour, no
                bold and no cursor movement.
             3. The arrows still work and still report where they landed.
             4. A number with no option behind it selects nothing.
             5. No run of `crossaudit init` prints a bare `crossaudit init` as a
                remedy; a refusal the screen does not recognise passes through
                unchanged.
             6. The D8 sentence is read before the choice, not after it.
             7. The empty starting point's frame does not promise checking, and
                the gating frame is still used where it is true.
             8. Five D10 counterfactuals, each mutating the shipped function and
                run against a live unmutated baseline in the same session.
             9. Full suite green.

UX EVIDENCE: The real `crossaudit init` driven end to end on a real pty, keyless.
             The constitution moment renders "❯ 1) Use these rules …" through
             "4) Show the full rules", accepts `1` as the choice, and prints
             "→ chose 1) Use these rules" before "AUDIT_RULES.md written and
             committed". Transcript captured with escape codes stripped.

CHINESE PARITY: not applicable — the CLI has no i18n mechanism, tracked as D16.
             No console string changed.

REVIEWER:    codex (w3) — cross-vendor, independent of this author
UX REVIEW:   design (w4) — this is a UI slice and w4 raised these findings
```

### What the harness had to learn, recorded because it cost an hour

The pty tests hung, twice, for two reasons that are properties of the product
rather than of the test:

* `read_key` enters raw mode with `TCSAFLUSH`, which **discards input already
  queued**. A key written before the menu draws is thrown away and the menu then
  waits forever for it. So keys are fed only once the drawing has gone quiet,
  which is when the reader is blocked on the next one. (This also means a
  real person's typeahead is dropped. It is existing behaviour, it is defensible
  — it stops a stray keystroke from choosing for you — and it is not this
  slice's to change. Flagged rather than silently relied upon.)
* An escape sequence is **one** keypress. `\x1b` written on its own is a
  complete and correct ESCAPE, so `select` cancels. Each keystroke goes out in a
  single write.

`select` is driven on a worker thread with a join deadline, so a future change
that stops consuming a keypress fails the test instead of hanging the suite.

### One thing fixed that was not asked for, and why it had to be

`_init` in `tests/test_constitution_moment.py` set `HOME`, but `keys_file()`
resolves `DEFAULT_KEYS_FILE`, which was computed from the real home **at import**
— so the tests were reading the developer's own credentials file. That decides
*which* of two refusals the keyless draft raises, which is exactly what the new
test asserts on, so on a machine with a credentials file it would have asserted
the wrong branch. `CROSSAUDIT_KEYS_FILE` now points at the sandbox. No test
wrote to the real file (`tui.secret` returns "" with no tty, so `write_keys` was
never reached), so nothing was left behind by the old behaviour — but it was
reading it.

### Still open from this slice, unchanged

The science inference shown as a proposal with its grounds (SPEC 3 §3.5). It
needs a provider to fire, so it is invisible in the keyless first run this slice
is about. Left last, per the manager.

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
---

## A4 — change contract (CLI i18n, wave 1)

```
TASK:        Translate the ENTIRE `crossaudit init` wizard so a person enters in
             English or Chinese and stays in that language for the whole setup
             (D21), and give the CLI the i18n mechanism D16 records it as not
             having. D25 is why this is not polish: for a Chinese-speaking
             first-timer an English-only CLI is not degradation, it is exclusion.

BASE:        agentA/first-three-minutes at 704aca9, merged with v5-redesign at
             bbb29a0 — NOT bbb29a0 alone. Stated because it is a real dependency
             and the manager owns merge ordering. bbb29a0's wizard is 467 lines
             and contains no constitution moment; the wizard wave 1 has to cover
             is 875 lines and contains it. D21's whole argument is that the
             constitution moment cannot be carved out of its own wizard, so
             translating bbb29a0's `init` would have translated an `init` that
             does not contain the thing wave 1 is P0 for, and thrown the work
             away at the merge. The merge was clean apart from TASK_LEDGER.md.

SURFACE:     src/crossaudit/cli/i18n.py (new), wizard.py, tui.py, main.py
             tests/test_cli_i18n.py (new), test_constitution_moment.py
             Audit core touched? NO.

MECHANISM:   A keyed catalogue in one module, not `gettext`. The argument is in
             the module docstring so it is cheap to overturn; the short form is
             that gettext's fallback is SILENT by design, its msgid is the
             English string (so rewording English silently orphans every
             translation), `.mo` files are binaries a reviewer cannot read and a
             frozen app must ship as data, and the console already uses a table.
             Its real advantages — plurals and translator tooling — are the two
             we need least. Stdlib either way; this is not a dependency call.

FALLBACK:    VISIBLE, in two halves that are both required. A missing
             translation is served in English with an inline `[en] ` mark (so a
             gap shows in a screenshot or a bug report) and recorded (so CI can
             assert on it), and the run prints `[i18n] N string(s) fell back`
             naming the keys. Not an exception: crashing setup over a missing
             sentence turns a copy defect into an outage.

SCOPE OF --lang: offered on `init` and nowhere else, per D21 — accepting it
             globally would let somebody choose Chinese and then meet English at
             the first thing that goes wrong. LANG and LC_ALL are deliberately
             NOT consulted: an environment that happens to be Chinese must not
             opt a person into a partly-translated tool without asking.

NOT TRANSLATED, and why the seam is there:
             rule ids and check names (an id is what traces a verdict back to a
             person's own constitution and to a receipt); exit codes, `--json`
             and every machine-readable field (a scripting contract, per
             errors.py — that seam was drawn once and this does not move it);
             model-generated text, including a drafted rule's title and the
             person's own words quoted back; paths, env var names, git output
             and commands to type; and the CONSTITUTION FILE ITSELF, which is
             project content the auditor reads, not UI.

ACCEPTANCE:  1. 98 keys, symmetric across both languages, no translation left
                sitting in English, no translation inventing a slot.
             2. A real `init --lang zh` run is Chinese at every step, with zero
                fallbacks and no `[en] ` marks.
             3. No English catalogue sentence appears on a Chinese screen, and
                every Latin run on it is a named exception.
             4. A real `init` run defaults to English and is unchanged.
             5. Chinese never overflows a box: every box line measures exactly
                `tui.WIDTH` columns.
             6. `--json` is unaffected.
             7. D10 counterfactual: making the fallback silent goes red.
             8. Full suite green.

CHINESE PARITY: **SATISFIED for the `crossaudit init` wizard only** — every
             screen from the banner to the Next panel, including the
             constitution moment and the check-pack proposal. **NOT APPLICABLE,
             tracked as D16, for every other CLI surface**: doctor, build, run,
             watch, amend, talk, the front door and every refusal outside
             `init`. Those are D21 waves 2-4 and remain English; `--lang` is not
             offered to them, so nobody can reach them in Chinese. Stated as two
             claims rather than one because a blanket "parity satisfied" after
             wave 1 would be exactly the overclaim this team has spent the day
             removing.

REVIEWER:    codex
AUDIT:       auditor
UX REVIEW:   design
```

### What I said I would flag, flagged

Writing the science-proposal slice I said I would say if any string was painful
to extract. Four were, and one of them was a defect rather than a difficulty.

**The defect.** My first Chinese run looked complete and was not. `git init — the
ledger is git…`, the `Next` rows and `(default)` were still English, and
`fallbacks()` reported ZERO — because a string that never went through `t()` is
not a missing translation, it is a missing key, and the fallback counter cannot
see it. A counter that only measures the strings you remembered to route is a
guard shaped exactly like the bug. So the test reads the SCREEN: every Latin run
on a Chinese screen must be a named exception, and no English catalogue sentence
may appear on it. That test is the one that found the gap; the counter did not.

**The three genuine difficulties**, all resolved rather than deferred:
* `tui.select`'s hint is one string shared by every menu in the product with the
  option count interpolated. Translated once, in `tui`, keyed.
* The check-pack grounds line quotes the person's own words inside a sentence
  whose word order differs in Chinese. Splitting the quote onto its own line was
  the fix; a translated clause welded to an untranslatable quote by
  concatenation reads as neither language.
* `_reason_inside_setup` names the same env var twice in one English sentence.
  The Chinese keeps both, because the second is the thing you type.

### Width, checked rather than assumed

`tui._visible` already counts CJK as two columns and `tui._break` already splits
spaceless runs, so the existing wrapper handles Chinese. What needed a test was
the BOXES, which are fixed at `tui.WIDTH` and padded from measured content: the
test asserts every drawn box line is exactly 72 columns in a Chinese run. Note
`tui.note` WRAPS, so every assertion here flattens whitespace first — a sentence
a person reads as one line arrives split and indented in the raw stream, which is
the CLI's version of the rendered-versus-raw distinction that has caught this
team repeatedly.

### One thing I could not do

SPEC-7 is not in the repository, or in any worktree, or in any branch — and
neither are SPEC-1, 2, 3 or 6, which earlier slices also cite. They appear to
exist only in the design engineer's own context. So the two questions the manager
explicitly delegated to design — whether `gettext` is right, and what "visible
fallback" should mean — were decided here instead, with the reasoning written
down where it can be overturned cheaply. Both are marked as the implementer's
call rather than design's, and neither should be read as design having agreed.
Recorded because a spec everyone cites and nobody can open is the same shape as
D20's working-directory drift: it looks fine from where each person stands.

---

## A5 — change contract (CLI i18n, wave 2)

```
TASK:        Translate the keyless failure paths a first-timer hits in the two
             minutes after setup (D21 wave 2): doctor's FAIL detail, its fix and
             its verdict; build's stop message; the un-initialised refusal.
             Design's reason for that grouping is the one to hold onto — this is
             where somebody lands BECAUSE SOMETHING WENT WRONG, which is the
             worst possible moment to change language on them.

BASE:        agentA/cli-i18n-wave1. Waves 1 and 2 together are exactly the first
             three minutes D6 ranked highest.

SURFACE:     src/crossaudit/cli/{i18n,main,build}.py, src/crossaudit/config.py
             tests/test_cli_i18n.py
             Audit core touched? NO — and see the escalation below for the one
             place wave 2 stops BECAUSE it would have had to.

THE SEAM, which is the whole design. `detail` and `fix` on a doctor check are
             carried verbatim by `--json` and by `--all`, and `--all` is
             documented as the stable surface for CI. The check NAME is a
             `--json` key. So none of those are translated. Instead each check
             carries an optional `copy` stem naming its HUMAN copy, resolved at
             render time for the default view only. The machine payload and the
             human payload sit beside each other rather than one being cast to
             the other. Same shape for the refusal: `reason` is the contract and
             stays English, `human` is the sentence a person reads and was
             already deliberately excluded from `as_dict()` — wave 2 uses that
             existing seam rather than inventing one.

--lang IS PER COMMAND, not central. It is declared on `init`, `doctor` and
             `build`, and each of those calls `_speak(args)` as its first
             statement. A dispatcher-level switch was written first and removed:
             it silently translated any command that happened to carry a `--lang`
             attribute, which is how a half-translated surface ships, and it did
             nothing at all for a caller that invokes `cmd_doctor` directly
             rather than through argv — which is how the console and every test
             call these. The set of translated commands is now visible at the
             commands themselves.

ACCEPTANCE:  1. doctor's verdict, FAIL label, consequence and fix are Chinese
                under `--lang zh`, with zero fallbacks, and the exit code is
                identical in both languages.
             2. `doctor --all` contains no Chinese at all.
             3. The refusal's `reason` stays English and is byte-identical in
                `as_dict()`; only `human` translates.
             4. build's stop message translates; the commands inside it do not.
             5. No English catalogue sentence appears on a Chinese doctor screen,
                except one named block (below).
             6. The wave 1 D10 counterfactual still goes red.
             7. Full suite green.

CHINESE PARITY: **SATISFIED for `crossaudit init`, `crossaudit doctor` and
             `crossaudit build`** — waves 1 and 2. **NOT APPLICABLE, tracked as
             D16, for every other CLI surface**: run, watch, verify, amend,
             talk, check, console and the front door. `--lang` is not offered to
             them, so nobody can reach them in Chinese. Three claims, not one.

REVIEWER:    codex
AUDIT:       auditor
UX REVIEW:   design
```

### ESCALATION — the one thing wave 2 could not close, and why

A Chinese `doctor` still shows one English block: the admission posture lines.

`admission.TIER_MEANING` is five literal sentences and `Assessment.shortfalls`
is four more, and both are carried verbatim by `Assessment.as_dict()`. They have
**no stable ids**. Translating them at the render site therefore means keying
them by their English text — which is precisely the msgid trap this mechanism
was chosen to avoid, because rewording the English would silently orphan the
translation. Giving them ids is an additive change to `admission.py`, which
governs what counts as admitted evidence and is audit-core-adjacent: AGENTS.md
§1 says that is a conversation, not a commit.

So wave 2 stops there deliberately. The test carries a NAMED exemption listing
the nine exact strings, plus a second test asserting that at least one of them
still appears — because an exemption list that stops matching becomes
pre-approved English exactly the way an unused allowlist entry does.

**What I need to close it:** a decision on adding stable ids to
`admission.TIER_MEANING` and `Assessment.shortfalls`. It is additive and touches
no verdict, but it is not mine to take.

### What design's SPEC-7 §4 changed about wave 1, retroactively

Design supplied the criterion I had been missing: the seam falls at anything a
person or a script may have to **TYPE, MATCH, or TRACE**. Tested against it, my
wave 1 allowlist failed badly. It had 52 entries and **37 were never needed** —
including `the`, `of`, `test`, `wizard` and `shell`, which had accumulated from
wrapped sandbox paths. Those are PROSE. An allowlist padded with English words
is a guard shaped like the bug it exists to catch: real untranslated copy could
have walked straight through it.

It is now 15 entries, each justified by one of type/match/trace and grouped by
which, with a new test asserting that **every declared entry is actually needed**
so padding cannot re-accumulate. The path-fragment exclusion was also made
deterministic: it had depended on where `tui.note` happened to break a long path
across lines, so whether the guard held varied with the sandbox's name length.

Design also confirmed the catalogue half of that guard is sound and is NOT the
shape that was defeated three times on consent: that guard chased a forbidden
MEANING and paraphrase is unbounded, while this one forbids an English CATALOGUE
sentence — a finite set we own, so its coverage is decidable by construction.
The open half is the allowlist, which is why it now has a guard of its own.

---

## A6 — change contract (which install is this)

```
TASK:        D40. Make install mode and resolved path visible where a person
             meets a mismatch, so `crossaudit 3.2.0 (pip, /Library/...)` beside
             a 4.15.0 app is self-evident rather than silent. NOT a PATH
             install: D31 part 2 refused that on consent grounds and it stands.

SURFACE:     src/crossaudit/cli/main.py (running_from, --version, front door,
             one doctor posture line), src/crossaudit/cli/i18n.py,
             tests/test_install_origin.py, docs/findings/
             Audit core touched? NO. `_selfid` is READ, never changed: the
             receipt path, the code digest and admission are untouched.

WHY S1 AND NOT S0, because it changes the fix. The ledger already tells the two
             producers apart — receipts carry version, a path-tagged code digest
             and install mode, and `verify --admit` refuses modes whose code
             could have changed under them. The person is misled, not the
             record. So the fix belongs on the surfaces a person reads, and
             nothing in the receipt path needed to move.

WHAT IT DOES NOT DO, deliberately. It never looks for other installs and never
             asserts a mismatch. Guessing where a rival copy might live would be
             inventing evidence on the exact surface that exists to stop us
             doing that. Two runs printing two versions and two paths is
             self-evident without anyone claiming it, and a test asserts the
             output contains no such claim.

SURFACES:    3. `--version` (the thing a person compares), the front door (the
             first thing they read when nothing is set up), and `doctor` — which
             is the command a confused person actually runs. In doctor it is an
             INFO POSTURE line, not a check: "which install is this" has no
             pass/fail axis, a green marker beside it would be the defect this
             project has spent the week removing, and posture lines render in
             the DEFAULT view where the confused person is. A test asserts it
             does not move the tally.

CHINESE PARITY: translated in the same commit as the English, not retrofitted.
             The doctor line is REACHABLE in Chinese today, because `doctor`
             carries `--lang` from wave 2, and a test drives it in both
             languages. The `--version` and front-door strings are translated
             and NOT yet reachable, because the front door is D21 wave 3 and
             `--lang` is deliberately not offered there — one Chinese line in an
             otherwise English front door is the seam D21 exists to prevent. So:
             parity satisfied for the doctor surface, present-but-unreachable
             for the other two, and that is stated rather than counted as done.

ACCEPTANCE:  1. `running_from()` reports this process only, and its path exists.
             2. `--version`, the front door and doctor all name mode and path.
             3. Two installs are distinguishable from their own output, with
                neither output asserting anything about the other.
             4. The doctor line is INFO and does not move the tally.
             5. Both languages, zero fallbacks.
             6. D10: hiding the origin again turns the guard red.
             7. Full suite green.

REVIEWER:    codex
AUDIT:       auditor
UX REVIEW:   design
FINDINGS:    docs/findings/w1-bundle-reachability-b5b3ea5.md
```
