# Review: perceived-latency slice — NEEDS CHANGES

Reviewed at `fusion/evidence-authority` = **dc524f3cfef3622a0dda5666354fbdc58241d727**
(merge of `fusion/latency` = 46c7913 into c30740f at 56541ab, plus a conftest commit).
Worktree: `scratchpad/wt-review-latency`, `PYTHONPATH=<wt>/src`,
`crossaudit.__file__` confirmed inside the worktree.

**Verdict: NEEDS CHANGES.** The core latency claim is real and well built — the POST
returns in ~3 ms against a 2 s router, the phase clock is server-side and correct, the
audit narration is genuinely additive, and streaming is now a capability, not a name
check. But the merge itself is **red** (7 tests, both parents green), and the
lane-reply streaming the spec asked for and the build report claims is **dead code that
cannot execute**.

---

## Suite status

```
tests/  ->  7 failed, 2565 passed, 2 skipped in 358.32s   (foreground)
```

Both merge parents are green in isolation:

| tree | tests/test_chat_lane.py | tests/test_perceived_latency.py |
| --- | --- | --- |
| c30740f (billing side) | 15 passed | (file absent) |
| 46c7913 (latency side) | — | 32 passed |
| **56541ab / dc524f3 (merge)** | **6 failed** | **1 failed** |

Every failure is a conflict-resolution join, exactly in the four files flagged.
The owner's "nothing new may error" directive is not met.

---

## Defects

### 1. BLOCKER — `src/crossaudit/cli/talk.py:246` — the joined `lane_chat` call breaks 6 shipped tests

The lead joined billing's `chat_id` and latency's `on_event` into
`_generator_chat_complete(cfg, chat_id="", on_event=None)` (talk.py:212) and calls it
with **three positional** arguments:

```python
    reply = _generator_chat_complete(
        cfg, str(getattr(routing, "chat_id", "") or ""), on_event)(
        system=GENERATOR_CHAT_SYSTEM, prompt=routing.restated)
```

The billing side had updated `tests/test_chat_lane.py`'s six monkeypatched stubs to
`(cfg, chat_id="")`; the merge added a third argument and did not follow through.

```
TypeError: ...<lambda>() takes from 1 to 2 positional arguments but 3 were given
  src/crossaudit/cli/talk.py:246
FAILED test_lane_chat_returns_the_generator_answer
FAILED test_lane_chat_refuses_an_empty_reply
FAILED test_chat_prompt_contains_only_the_user_words
FAILED test_say_chat_answers_without_starting_a_build
FAILED test_provider_exception_during_chat_is_a_clean_refusal
FAILED test_empty_chat_reply_is_ledgered_as_denied_not_answered
```

**Fix.** Give all six stubs in `tests/test_chat_lane.py` an `on_event=None` third
parameter, the same follow-through billing did for `chat_id`. (Confirmed: patching two
of the six locally cleared exactly two failures.) `lane_auditor` (talk.py:192) was
resolved with keyword arguments and survived — prefer that shape here too
(`..., on_event=on_event`) so the next kwarg does not repeat this.

### 2. BLOCKER — `tests/test_perceived_latency.py:498` — the event-order test errors, so checklist item 2 has no guard

`cli/build.py:655` now calls `_generator_complete(cfg, allow_custom,
generator_provider_event, heartbeat, usage_context)` — five positional arguments, the
fifth added by fusion/billing. The latency slice's own stub takes four:

```
TypeError: complete_factory() takes from 2 to 4 positional arguments but 5 were given
  src/crossaudit/cli/build.py:655
FAILED test_events_run_from_submit_to_verdict_in_the_owner_facing_order
```

This is the *only* test covering the submit→verdict ordering. It has been dead since
the merge.

**Fix.** `def complete_factory(_cfg, _allow_custom, on_event=None, _heartbeat=None,
_usage=None):`. Verified: with that one word added the test passes, and the whole file
goes 32/32.

### 3. MAJOR — lane-reply streaming is unreachable code (`console/server.py:1074`)

The spec's L1 requires non-generator lanes to stream "when the provider streams", and
build-latency.md states "Lane replies (chat, direct auditor) stream through here as
`intake_chunk` frames". Neither holds.

`server.py:1074` passes `INTAKE.provider_event` — a **bound method** — as the lane's
`on_event`. `providers/resilience.py:213` then does
`chunk_callback = getattr(on_event, "on_chunk", None)`. A bound method has no
`__dict__`, so that attribute can never be present or set:

```
on_chunk attr on watcher.provider_event: None
attachable: NO -> 'method' object has no attribute 'on_chunk'
                  and no __dict__ for setting new attributes
```

`Intake.chunk()` (intake.py:184) has **zero call sites in `src/`**. Consequently
`_intake_sse_frame` (server.py:490), the `intake_chunk` emission loop
(server.py:1554-1563), `Intake.reply_events`, and page.py's `replyChunk()` /
`liveReplyTurn()` are all unreachable. A chat or direct-auditor question shows three
thinking dots for the whole reply and then jumps to the finished turn — the exact
silent gap the directive forbids, on the one lane where there is no run card to fall
back on. (The same defect masks a second one: `_intake_sse_frame` writes no `id:`
field, so an SSE reconnect would replay from seq 0 and `replyChunk`'s gap rule would
wipe the visible reply. Fix that at the same time.)

**Fix.** Make the watcher's `provider_event` a plain function (or a small callable
object) that carries `on_chunk = INTAKE.chunk` and `on_thinking`, the way
`cli/build.py:625-629` does for the generator; emit `id:` on intake frames and track a
resume cursor. Add a test that a streaming chat stub yields `intake["chunks"] > 0` and
an `intake_chunk` frame on `/api/stream` — nothing currently would notice this
regression.

### 4. MAJOR — `console/server.py:2106` — a refused second message still creates a thread

`chats.touch()` runs before `accept_say()`, so the 409 path leaves an orphan thread
behind. Measured against the real console:

```
FIRST   200 {'accepted': True, 'intake': '3aa71fcf68cca46f', 'chat_id': '41d2...'}
SECOND  HTTPError 409  the previous message is still being handled
CHATS_AFTER_REFUSAL  ... {"id":"41d2...","title":"first"},
                         {"id":"5e47525bb5e4fc35","title":"second", "cycles":0} ...
```

The handler's own comment three lines above ("Before the chat is touched: a message the
app could not send leaves no thread behind") is honoured only for the setup card. The
409 text is also English-only — `settleIntake` renders it through
`route.innerHTML='<b>Refused.</b> '+esc(e.message)` and the ZH catalogue has no entry
for "the previous message is still being handled".

**Fix.** Check `INTAKE.active` (or move `chats.touch` after `accept_say` returns
`accepted`) before touching the chat; add the 409 sentence to the ZH dictionary.
Consider whether a hard 409 is right at all — before this slice a second message
serialised on `MODEL_SWITCH_LOCK` and eventually ran.

### 5. MAJOR — `console/server.py:1156` — a raw exception string is shown to the user

```python
        except Exception as exc:  # noqa: BLE001 -- the page gets a sentence, never a trace
            INTAKE.fail(500, f"{type(exc).__name__}: {exc}"[:400])
```

Measured, with an unexpected error raised inside the lane:

```
UNEXPECTED_ERROR {"status": 500,
                  "reason": "ValueError: internal boom with /Users/secret/path"}
```

`settleIntake` paints that verbatim: **"Refused. ValueError: internal boom with
/Users/secret/path"**. It is not a stack trace, but it is an exception class name and a
filesystem path on the main surface, in English only — precisely what "concise surface"
rules out, and a class of text that could not reach the page before (the handler used to
fail the request instead). Note the *expected* path is fine: a `Denial` in the lane is
caught by `say()` and settles as `executed: "refused — …"`, the same card as before —
verified.

**Fix.** Log the detail; hand the page one fixed EN+ZH sentence ("Something went wrong
handling that message. Nothing was started." / "处理这条消息时出错，没有启动任何任务。").

### 6. MEDIUM — `cli/build.py:744-754` — the phase order reads backwards

```
744: emit("generation_started", ... "writing")
749: emit("preparing", ... "Reading the workspace · N files")
754: emit("prompt_ready", ... "Asking the generator to write")
```

The spec and the checklist both ask for `preparing → generation_started`. As shipped the
user reads "writing", then "Reading the workspace · 12 files", then "Asking the
generator to write". The shipped order test asserts the *emitted* order, so it locks the
wrong sequence in, and this deviation is not listed in build-latency.md.

**Fix.** Move the `preparing` and `prompt_ready` emits above `generation_started` (the
workspace read is what happens in that window), and update `expected` in the order test.

### 7. MEDIUM — `console/page.py:6364` — the clock crowds everything else off the run card

`p.steps.slice(-12)` with no de-duplication, against a clock that appends one
`still_working` per 8 s of silence (`runtime/commands.py:214-231`) and one
`auditor_progress` per 10 s of streaming (`cli/build.py:238-256`). A 120 s audit phase
emits 15 clock rows, so **all 12 visible rows** become "Still auditing · 45 s" /
"Still reviewing · 40 s" and every substantive step scrolls out of view. The cure for
silence should not eat the narration it was added to protect.

**Fix.** Collapse consecutive `still_working` / `auditor_progress` rows to the newest
one when projecting or rendering the activity list.

### 8. MEDIUM — `console/page.py:6369-6372` — thinking is neither collapsed nor marked unaudited

Thinking renders as a bare live-activity row: mark `…`, label `Thinking` / `思考中`, and
the last 160 characters of model reasoning. The live *draft* correctly wears
"Generator live draft · not yet audited" / "生成者实时草稿 · 尚未审计"; thinking — which
is further from evidence — wears nothing, and is not collapsed. D4's rule is that
unaudited model text must be unmistakably unaudited.

**Fix.** Wrap it in a `<details>` closed by default, summary "Thinking · not audited /
思考中 · 未经审计".

### 9. MINOR — `providers/resilience.py:214` — `generator_streaming` now gates the auditor too

The gate dropped `role_name == "generator"` along with the provider equality, so a
project that sets `generator: {streaming: false}` silently loses `auditor_progress`
narration as well. Either rename the setting or read a separate auditor flag.

### 10. MINOR — dead catalogue entries in `console/progress.py`

`"The auditor is reading the commit"` (line 93) and the `answered` kind /
`"Reply received"` (lines 75, 92) have no emitter anywhere in `src/` — the auditor line
is superseded by the counted `PHASE_PATTERNS_ZH` form. Also `cli/build.py:262-274`
(`_workspace_file_count`) adds a second full `rglob` over every scope dir on every
round, purely to produce the count that `_current_work` then re-walks — doubling the
directory walk per round.

---

## What holds up (evidence)

**POST latency (checklist 1).** Real console in a thread, `route_addressed` sleeping
2.0 s, lane stubbed:

```
POST 0  200 {'accepted': True, 'intake': '…', 'chat_id': '60a1…'}  13.8 ms
POST 1  200 …                                                        3.1 ms
POST 2  200 …                                                        2.8 ms
POST 3  200 …                                                        3.4 ms
```

Median **3.1 ms** against a 2 s router (first sample is socket warm-up). The body
carries the chat id, the page's `form.onsubmit` branches on `r.accepted` and holds the
composer until `settleIntake` applies the result from state. The setup card keeps the
fast path and, correctly, creates **no** thread and **no** intake:

```
SETUP_POST 200 {'setup':'credentials','missing':['generator','auditor'],
                'action':'providers','asked':False,'lane':'setup'}
INTAKE_AFTER_SETUP  None
CHATS_AFTER_SETUP   [ Project history ]        # nothing added
```

A `Denial` in the lane reaches the page through the same card as before, with no
traceback and no orphan indicator:

```
INTAKE_STEPS  [('received','Got it — working out who should handle this'),
               ('routed','The generator will reply directly'),
               ('answering','The generator is replying')]
RESULT {'asked':False,'lane':'chat','executed':'refused — no credential for the generator'}
```

**Streaming capability (checklist 3).** `supports_streaming` is read off the adapter, so
the vendor presets built on `openai_compat` inherit it:

```
anthropic True   deepseek True  google True   minimax True  mistral True
moonshot  True   openai_compat True  qwen True  xai True    zhipu True
openai_codex False   replay False
```

`Config.generator_streaming` defaults `True` (config.py:118, 262).
`providers/anthropic.py:102-118` folds only `text_delta` into `self.parts`;
`thinking_delta` goes to a separate `ChunkEmitter` and never into `Reply.text`.

**Phase copy (checklist 6).** 24 sentences/patterns rendered; **max English length 43**
(limit 60); every one has a Chinese form except `provider recovery` (pre-existing at
ad1dc0b, reaches the intake lines as new surface) and `Draft: N words so far` (rendered
page-side with its own ZH branch — fine). Sample:

```
 43 | Got it — working out who should handle this   | 已收到，正在判断由谁处理
 32 | Reading the workspace · 12 files              | 正在读取工作区 · 12 个文件
 23 | Still generating · 45 s                       | 仍在生成 · 45 秒
 22 | Still reviewing · 40 s                        | 仍在审阅 · 40 秒
 26 | Units check found 2 issues                    | 单位检查发现 2 个问题
 22 | Parseable check passed                        | 可解析检查通过
```

**Audit narration (checklist 5).** `dcl/framework.py:175` took exactly one additive
`on_check=None` kwarg and nothing else in `dcl/` changed (diff confirmed); the observer
is called around the unchanged `fn(...)` and cannot alter the result. The verdict event
is untouched. `_auditor_progress_clock` (build.py:238) drops the chunk text on the floor
by construction.

**Deliberately updated tests (checklist 8).** All four are honestly docstringed and none
is weakened: `test_generation_stream_provider.py` got materially *stronger* (loops four
adapters, plus a `replay` negative and a flag-off negative);
`test_overview.py` swaps the sha for the round number and adds a negative asserting the
sha stays off the card; `test_admission_and_console.py` routes through `settled_say` but
keeps every guard; `test_context_condensation_page.py` follows the `activityRow` split.

---

## Mutation log (8 mutations, all red)

| # | file | mutation | test that caught it |
| --- | --- | --- | --- |
| M1 | `config.py:118,262` | `generator_streaming` default `True → False` | `test_generator_streaming_setting_is_boolean_and_on_by_default` (2 failed) |
| M2 | `providers/registry.py:62` | `supports_streaming` returns `True` always | `test_streaming_is_on_by_default_and_threads_to_every_capable_adapter` |
| M3 | `runtime/pacing.py:69` | drop the `now - self._last < self._silence` guard | `test_still_working_fires_after_eight_silent_seconds_and_not_otherwise` |
| M4 | `dcl/framework.py:203` | drop the `on_check(name,"finished",…)` call | `test_run_checks_tells_an_observer_and_decides_nothing_by_it` |
| M5 | `cli/build.py:255` | narrate the chunk text instead of the seconds | `test_the_auditor_clock_narrates_time_and_never_the_reply_text` |
| M6 | `console/server.py:1163` | run `work()` inline instead of in a thread | `test_send_returns_before_the_router_has_answered` |
| M7 | `console/intake.py:113` | drop the `received` narration | `test_the_page_can_show_progress_while_the_router_thinks` |
| M8 | `providers/anthropic.py:113` | append `thinking_delta` into `self.parts` (the committed draft) | `test_anthropic_streams_text_and_thinking_on_separate_contiguous_streams` |

All source mutations reverted with `git checkout --`; the tree is clean.

One weak new test worth noting: `test_thinking_text_never_reaches_the_auditor_prompt_
commit_or_receipt` (test_perceived_latency.py:374) builds the prompt, receipt and commit
log from inputs the sentinel never touched, so three of its five assertions are
near-tautological. The one real assertion is the tracker-snapshot exclusion. M8 above is
the mutation that actually exercises the separation; consider folding it in.

## Counts

- 42 files, +4184/−334 against ad1dc0b (including the merged branch).
- 17 new tests in `tests/test_perceived_latency.py`; 1 of them dead at the merge (D2).
- 16 new event kinds, 24 phase sentences/patterns, max EN length 43 chars.
- 7 suite failures introduced by the merge; both parents green.
