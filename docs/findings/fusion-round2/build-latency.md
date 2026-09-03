# Build report: perceived latency (branch `fusion/latency`)

Base ad1dc0b; `fusion/evidence-authority` (bf32c8e) merged before the final suite.
Final suite: **2544 passed, 2 skipped** in 347 s (foreground, worktree `src` on `PYTHONPATH`,
`crossaudit.__file__` confirmed inside the worktree).

## Commits

| sha | item |
| --- | --- |
| `fc7bef1` | L1 — `/api/say` answers at once; routing, preparing and lanes narrate through an intake |
| `be09e38` | L2 — streaming through every capable adapter; Anthropic SSE with thinking; on by default |
| `6c3d1dd` | L3 — the audit phase narrates: each check in words, the auditor reading |
| `7b26f62` | L4 — a server-side phase clock: eight silent seconds become a sentence |
| `5c9b698` | L5 — a concise surface: words on the run card, identifiers stay in the record |
| `e58492e` | L5 follow-up — the condensation harness follows the run card's split |
| `0e49c8b` | merge `fusion/evidence-authority` |
| `46c7913` | L5 follow-up — the pipeline test names the round it expects |

L6's tests ship inside each item's commit (`tests/test_perceived_latency.py`, 17 tests, 800 lines).
42 files, +4184/−334 against ad1dc0b (including the merged branch).

## Measured POST latency

Same harness, same stub: the routing provider sleeps 2.0 s, lane stubbed.

| | median | samples |
| --- | --- | --- |
| before (the body the old handler ran inline in the request thread) | **2039 ms** | 2041 / 2039 / 2037 |
| after (`POST /api/say` through the shipped server) | **2.7 ms** | 13.9 / 2.6 / 3.1 / 2.4 / 2.7 |

The first sample carries the socket warm-up. Pinned by
`test_send_returns_before_the_router_has_answered` at < 200 ms.

## New events

Kinds are in `console.progress.PHASE_KINDS`; Chinese comes from `PHASE_TEXT_ZH`
(fixed sentences) or `PHASE_PATTERNS_ZH` / `STILL_WORKING_ZH` / `CHECK_WORDS_ZH`
(the counted ones), so page and non-page clients read one catalogue.

| kind | EN | ZH |
| --- | --- | --- |
| `received` | Got it — working out who should handle this | 已收到，正在判断由谁处理 |
| `routed` (generator) | The generator will do this | 交给生成者处理 |
| `routed` (auditor) | The auditor will answer | 由审计者回答 |
| `routed` (chat) | The generator will reply directly | 生成者将直接回复 |
| `routed` (query / amendment / dispute / ruling / setup) | Looking up the audit record · Drafting a change to the rules · Sending the finding back to the auditor · Recording your ruling · Nothing to set up | 正在查询审计记录 · 正在起草规则修改 · 正在将该结论退回审计者 · 正在记录你的裁定 · 无需设置 |
| `answering` | The generator is replying / The auditor is replying / The auditor is drafting the rule change | 生成者正在回复 / 审计者正在回复 / 审计者正在起草规则修改 |
| `answered` | Reply received | 已收到回复 |
| `preparing` | Reading the workspace · N files | 正在读取工作区 · N 个文件 |
| `prompt_ready` | Asking the generator to write | 正在请生成者撰写 |
| `still_working` | Still routing/preparing/generating/auditing/replying/reviewing · N s | 仍在判断由谁处理／仍在准备／仍在生成／仍在审计／仍在回复／仍在审阅 · N 秒 |
| `auditor_reading` | The auditor is reading N files | 审计者正在阅读 N 个文件 |
| `auditor_progress` | Still reviewing · N s | 仍在审阅 · N 秒 |
| `check_started` | Running the <check> check | 正在运行<检查>检查 |
| `check_finished` | <check> check passed / <check> check found N issues | <检查>检查通过 / <检查>检查发现 N 个问题 |
| `thinking_chunk` | (streamed summarised thinking; label "Thinking") | 思考中 |

Run card additions: `Draft: N words so far` → `草稿：已写 N 字`;
`Generator live reply · not audited` → `生成者实时回复 · 未经审计`;
`Auditor live reply · direct reply` → `审计者实时回复 · 直接回复`.

## Shape of the change

- **L1** `console/intake.py` (new, 256 lines) is the phase record; `accept_say()`
  validates, begins the intake and returns `{accepted, intake, chat_id}`, and a
  worker runs the whole of `say()` with the intake as its watcher. A `Denial` in
  the worker becomes the intake's error with the reason the 400 used to carry, so
  no new traceback can reach the page. `settleIntake()` applies the result exactly
  once from the state, so a reload sees what the original tab saw.
- **L2** `registry.supports_streaming(name)` reads a `supports_streaming` attribute
  off the adapter; `providers/streaming.py` (new) holds the coalescer both adapters
  share; `anthropic.py` gained the SSE path (`content_block_delta` text,
  `thinking_delta` on its own stream). `Config.generator_streaming` defaults True.
- **L3** `dcl.run_checks` took one additive `on_event=None` kwarg — nothing else in
  the kernel — and `auditor/run.py` narrates through the existing `run_audit(on_event=…)`.
- **L4** `runtime/pacing.py` `PhaseClock`, 8 s, injectable clock, emitting through the
  command shell's cancellation-aware emit. Server-side, per D4 — no page timer.
- **L5** `activityRow` renders every line from the wire's `text_i18n` through a
  `conciseDetail` that drops shas, cycle ids, `provider:model` routes and rule ids;
  the pipeline's Commit step names the round.

## Deviations

1. **`setup_needed` stays on the fast path.** `fusion/evidence-authority` put the
   credential check inside `say()`, which L1 moved into the worker; behind it the app
   would show a thread and a working indicator for a message it never sent, and
   `test_setup_preflight` pins a direct body with no `chat_id`. The check is
   presence-only and local — no provider call — so it answers the POST from
   `accept_say()` and remains in `say()` for direct callers.
2. **Two pinned tests updated after the fact.** `test_context_condensation_page.py`
   had to follow L5's split of the run card into `activityRow` (it was dying in node,
   not testing anything), and `test_overview.py` used the Commit step's sha to prove
   ledger-time ordering — it now makes the same point with the round number and
   asserts the sha stays off the card. Both carry docstrings naming the mutation.
3. **`optimisticTurn` carries both.** The working indicator keeps the intake lines and
   the auditor-side mark and shows the merged branch's forecast line in the same body.

## Counts

- 17 new tests in `tests/test_perceived_latency.py`, covering L6 (a)–(g).
- 16 new event kinds / phase sentences, each with EN + ZH.
- Deliberate updates to 4 previously pinned test files
  (`test_generation_stream_provider.py`, `test_admission_and_console.py`,
  `test_context_condensation_page.py`, `test_overview.py`).

---

# Review fixes

Against `review-latency.md`. Items 1–2 (the merge stub joins) were fixed by the
lead on the fusion tip; `fusion/evidence-authority` (fe6660e) merged clean here.
Commits: `71af720` (merge), `aab5c9d` (fixes).

Final suite: **2581 passed, 2 skipped** in 353 s, foreground, worktree on `PYTHONPATH`.

| # | fix |
| --- | --- |
| D3 | `Intake.lane_narration()` returns a plain function carrying `on_chunk`; the lanes get that instead of the bound `provider_event`. Intake SSE frames gained `id: intake:<id>:<seq>` and the stream loop restores that cursor from `Last-Event-ID`. |
| D4 | `say_refusal()` holds every refusal that costs no provider call — consent, credentials, a message in flight — and the handler asks it before `chats.touch`. |
| D5 | `UNEXPECTED_FAILURE` (one sentence, EN + ZH); the exception goes to `traceback.print_exc()`. |
| D6 | `preparing → prompt_ready → generation_started` in `cli/build.py`; the order test follows. |
| D7 | `collapseClockRows()` keeps only the newest of a run of `still_working` / `auditor_progress` rows, in place, before `slice(-12)`. |
| D8 | The thinking row is a `<details>` closed by default, summary "Thinking · not audited" / "思考中 · 未经审计". |

## Why D3 was invisible

A bound method has no `__dict__`. `getattr(on_event, "on_chunk", None)` could
never find one on it and nothing could set one, so the lane looked wired at the
call site and streamed nothing. `Intake.chunk` had zero call sites in `src/`.
`test_the_lane_narration_object_can_carry_the_streaming_callback` now asserts the
seam directly, because the two shapes are indistinguishable where they are passed.

## New tests (9, all in `tests/test_perceived_latency.py`)

- `test_a_streaming_chat_reply_reaches_the_page_as_intake_chunks` — through the real
  console and the real resilience gate; `intake["chunks"] > 0`.
- `test_a_lane_that_does_not_stream_still_ends_with_the_whole_reply` — 0 chunks, whole answer.
- `test_the_lane_narration_object_can_carry_the_streaming_callback` — the seam.
- `test_the_page_renders_a_streamed_lane_reply_as_an_unaudited_turn` — the shipped
  `replyChunk`/`liveReplyTurn` under node over frames from the shipped
  `_intake_sse_frame`; contiguous seqs assemble and wear the unaudited label, a
  dropped frame renders nothing.
- `test_a_refused_second_message_leaves_no_thread_behind` — measured 409, one chat.
- `test_the_refusal_sentences_the_page_paints_are_both_translated`.
- `test_an_unexpected_error_shows_a_sentence_not_the_exception` — the reviewer's
  `ValueError("internal boom with /Users/secret/path")`.
- `test_the_clock_never_crowds_the_narration_off_the_run_card` — a 120 s audit,
  fifteen clock rows in, one out (the newest), the substantive rows kept.
- `test_the_thinking_row_is_folded_shut_and_says_it_is_unaudited`.

Two harnesses followed the code: `test_context_condensation_page.py` extracts
`collapseClockRows`, and the order test's `expected` list is reordered with a
docstring naming the mutation.

## Not addressed

D9 (`generator_streaming` gates the auditor's `auditor_progress` too) and D10
(dead catalogue entries; `_workspace_file_count` walks the scope dirs a second
time) are the review's two MINORs and were outside this pass. D9 is a
config-naming decision — rename the setting or add an auditor flag — worth
settling deliberately rather than in a fix commit. The reviewer's note that
`test_thinking_text_never_reaches_the_auditor_prompt_commit_or_receipt` is partly
tautological also stands; mutation M8 in their log is the assertion that earns
its keep, and folding it in is the right follow-up.

---

# Closure audit 2

Merged `fusion/evidence-authority` (da71b9d), clean. Commits: `fa9e07c` (merge),
`00396e6` (fixes). Full suite: **2600 passed, 2 skipped** in 368 s, foreground.

**1. The `collapseClockRows` call site is pinned.** The D7 test drove the function
directly, so the mutation its own docstring named — dropping the call from
`runCard` — survived. `test_the_shipped_run_card_collapses_the_clock_rows_it_renders`
now renders the shipped `runCard` under node over two consecutive clock rows and
counts one in the HTML; the newest row survives and the substantive row is kept.
Verified red under the mutation.

A first attempt reused `test_context_condensation_page._render` through an
`importlib` load. `test_guard_names_match_what_they_check` correctly rejected it:
a name promising a render over a body in which that guard can see no product call
is exactly the shape it exists to catch. The test drives `subprocess`/node itself
through a module-level `_render_run_card()` helper instead.

**2. The continuation-round note is in `docs/EVIDENCE_AUTHORITY.md`** (§The repair
guard), not only in this report. The screen runs on a *revision* — a round after a
BLOCKED audit within the same run (`repair_round`, False until an audit blocks) —
so a cycle a human resumes starts a new run whose first round has no part of that
section applied, cautions and refusals alike, and no previous findings in the
prompt. The note says why that is deliberate (screening a round the generator was
never shown findings for would redden honest work, D121) and what still holds:
`apply`'s scope denial before staging, every DCL check, and the auditor's own read.
From the second round of the resumed run the screen behaves as documented above it.
