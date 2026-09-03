# Build report — results & decisions UX slice (fusion/ux-results)

Worktree: `/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-ux-results`
Base: `ad1dc0b`. Not pushed. No DECISIONS.md entries.

## Commits (one per item, trailers on every commit)

| sha | item |
|---|---|
| 6852e4c | R1: plain verdict words on the main surface |
| 7622c74 | R2: findings lead with the observation |
| 4d9f2dc | R3: the review card's record is Details, collapsed |
| 569c323 | R4: a forecast line from this project's completed runs |
| 45db5b2 | R5: a cause and a next step for every ESCALATE branch |
| f44b22f | R6: tests for the results & decisions slice |

10 files changed, 1041 insertions(+), 56 deletions(-).
Full suite on the final commit (foreground): **2507 passed, 2 skipped, 0 failed** (311 s).

## Files touched (all inside the assigned regions)

- `src/crossaudit/console/page.py` — chat turn / review card (verdictWord, severityWord, tierWord, findingCard, friendlyModel, forecastText/forecastLine), Decision Center (CAUSE_COPY, openResolution slots, secondary button), CSS, ZH dictionary + 3 ZH patterns. One line each in `optimisticTurn` (task-start turn) and `runCard` run-meta (`(live ? forecastLine(d) : '')`).
- `src/crossaudit/usage.py` — `run_forecast`, `forecast_rows`, `_quartiles`, `_journal_runs` (read-only sqlite), `FORECAST_STATES`; `summary()["forecast"]`; cache signature now includes the journal's mtime/size.
- `src/crossaudit/errors.py` — `ESCALATION_CAUSES`, `escalation_cause(...)` (pure ladder map). `escalation_remediations` untouched.
- `src/crossaudit/controller/state.py` — `record_verdict(..., escalation_cause="")` stores `escalation_cause` (additive).
- `src/crossaudit/cli/main.py` — `_escalation_cause(outcome, cycle)`; both `record_verdict` sites (cmd_run, cmd_audit) pass it.
- `src/crossaudit/console/overview.py` — `Cycle.integrity` (from receipt `audit_integrity`), `receipt_integrity`, `_INTEGRITY_CAUSES` legacy fallback, `CAUSE_WHY`, `CAUSE_REQUESTED`, `_earliest_other_open`, `earlier_cycle_id` on locked rows; fixed sentence becomes the stop reason when none was recorded.
- `tests/harness/render_decision.py` — extracts CAUSE_COPY / VERDICT_WORDS / verdictWord / severityWord, defines `t`, records `extra[locale]` (guidance value, secondary button label/hidden/target).
- `tests/test_console_stop_causes.py`, `tests/test_report_provenance.py` — two pins updated deliberately, docstrings name the mutation (findingTier → tierWord on the details line; findings rendered by `findingCard`).
- `tests/test_ux_results.py` — new, 26 test functions (37 cases with parametrisation).

## R1 — verdict words

| raw | EN | ZH |
|---|---|---|
| PASS / PASSED | Passed | 已通过 (existing entry — see deviations) |
| CONSUMED | Admitted | 已准入 (existing) |
| BLOCKED | Needs changes | 需要修改 (existing) |
| ESCALATE / ESCALATED | Needs you | 需要你 (new) |
| DCL_ONLY | Checks only | 仅自动检查 (new) |

Applied to: chat auditor badge, review-card round rows, Decision Center attempt rows. Raw word kept as the CSS class and everywhere non-surface (`--json`, receipts, reports, inspector) — pinned by `test_the_raw_words_survive_where_scripts_and_records_read_them`.
New ZH pattern: `^(\d+) issues?$` → `N 个问题`.

## R2 — findings

New strings (EN → ZH): `must fix` → 必须修改; `suggestion` → 建议; `verified by a check` → 已由检查验证; `raised by the auditor` → 由审计者提出; `raised by the auditor, verified` → 由审计者提出，已验证.
Markup: `<p class="finding-observation">` first; `<div class="finding-details">` = severity · artifact · tier sentence · `<span class="finding-rule" title="rule id">`. Same renderer for chat turn, review card, Decision Center issues. `findingTier` (separate `<small>` row) removed; its three sentences stay in the ZH dictionary (still asserted by the existing NEW_COPY sweep).

## R3 — Details

`Record` → `Details` / 详情 as a closed `<details>` inside the review card's detail area; rows: Generator, Auditor (friendly names), Commit (12-hex), Cycle (16-hex). New ZH: `Details` → 详情, `Human` → 人工.
`friendlyModel`: `anthropic · anthropic:claude-opus-4-8 · high` → `Claude Opus 4.8`; `gpt-5.6-terra` → `GPT-5.6 Terra`; `claude-haiku-4-5-20251001` → `Claude Haiku 4.5`; `gemini-3.5-pro` → `Gemini 3.5 Pro`; `deepseek-v4-pro` → `DeepSeek V4 Pro`; unknown ids → capitalised words of the id without the provider prefix.
Grep test on rendered HTML (`test_the_review_card_first_paint_carries_no_identifier`, PASSED/BLOCKED/ESCALATED): outside `<details>` no `[0-9a-f]{12,40}`, no `anthropic:|openai_compat:|openai_codex:|:claude|:gpt`, no raw verdict word; no finding's first line matches `CA-[A-Z]+-\d`.

## R4 — forecast

`usage.run_forecast(rows)` → `{"runs", "priced_runs", "seconds": {p25,p50,p75}|None, "usd": {...}|None}`; `forecast_rows(events, runs)` joins ledger events into each run's wall-clock window (the ledger has no run id); `_journal_runs` reads `runs` where `state IN ('PASSED','WAITING_FOR_HUMAN')` and `finished IS NOT NULL` (cancelled/interrupted/parked runs excluded so they cannot bias the estimate low). Exposed at `snapshot.usage.forecast`.
Rendered line (EN / ZH):
- ≥3 runs, spread: `Usually 2–4 min · about $0.30` / `通常 2–4 分钟 · 约 $0.30`
- 1–2 runs or no spread: `Usually about 3 min · about $0.30` / `通常约 3 分钟 · 约 $0.30`
- unpriced: cost segment omitted (`Usually 1–2 min` / `通常 1–2 分钟`)
- no runs: `First run here — no estimate yet` / `首次运行，暂无预估`
Placement: `optimisticTurn` (task-start turn, under the working dots) and the run-card run-meta while the run is live.

## R5 — cause → copy table (Decision Center slots; EN / ZH)

| cause | flag | title | what-happened line (limit-copy) | next step (request) | primary action (reopen title / copy) | guidance prefill |
|---|---|---|---|---|---|---|
| nothing_audited | Nothing to review yet / 尚无可审内容 | The task produced no work in the audited folder / 任务未在受审文件夹中产生任何工作 | the task produced no work in the audited folder, so there was nothing to review / 任务未在受审文件夹中产生任何工作，因此没有可审查的内容 | Tell the generator what to create inside the audited folder and run one more round, or stop this task. / 告诉生成者应在受审文件夹中创建什么，然后再运行一轮；或停止此任务。 | Revise and continue — Say which files should be created inside the audited folder, then unlock one additional audited round. / 说明应在受审文件夹中创建哪些文件，然后解锁额外一轮受审计执行。 | Create the deliverable inside the audited folder; nothing was produced there. / 请在受审文件夹中创建交付物；此前那里没有产生任何内容。 |
| invalid_reply | Auditor reply unreadable / 审计者回复无法读取 | The auditor’s reply could not be read / 审计者的回复无法读取 | the auditor's reply could not be read / 审计者的回复无法读取 | Run the audit again on the same work, switch the auditor model, or stop this task. / 对同一份工作再次运行审计、更换审计者模型，或停止此任务。 | **Run the audit again** / 再次运行审计 — Unlock one more round with the work unchanged so the auditor can answer again. / 在工作不变的情况下解锁一轮，让审计者再次作答。 | Run the audit again on the same work; the previous auditor reply could not be read. / 请对同一份工作再次运行审计；上一次审计者的回复无法读取。 |
| bounds_exceeded | Task too large for one audit / 任务过大，无法一次审计 | The task is too large for one audit / 该任务过大，无法在一次审计中完成 | the task is too large for one audit / 该任务过大，无法一次审计 | Narrow the scope or split the task into smaller pieces and run one more round, or stop this task. / 缩小范围或将任务拆分为更小的部分，然后再运行一轮；或停止此任务。 | Revise and continue — Name the smaller piece the next round should cover, then unlock one additional audited round. / 指明下一轮应覆盖的较小部分，然后解锁额外一轮受审计执行。 | — |
| auditor_escalated | The auditor asked for you / 审计者请你介入 | The auditor asked for your judgment / 审计者请你作出判断 | the auditor's stated reason (first finding's observation, its own words) — else "the auditor asked for your judgment" / 审计者请你作出判断; section title "What the auditor said" / 审计者的说明 | Read the auditor’s reason, then tell the generator how to address it or stop this task. / 阅读审计者的原因，然后告诉生成者如何处理；或停止此任务。 | Revise and continue — Tell the generator how to address the auditor’s reason, then unlock one additional audited round. / 告诉生成者如何处理审计者的原因，然后解锁额外一轮受审计执行。 | — |
| escalation_locked | Waiting on an earlier decision / 等待更早的决定 | This task is already waiting for your earlier decision / 此任务仍在等待你更早的决定 | this task is already waiting for your earlier decision / 此任务仍在等待你更早的决定 | Open the earlier decision and settle it; this task continues from there. / 打开更早的决定并作出处理；此任务将从那里继续。 | Settle the earlier decision / 先处理更早的决定 — Open the earlier decision first. Guidance recorded here applies once it is settled. / 请先打开更早的决定。此处记录的指引将在其处理完毕后生效。 Secondary button **Open the earlier decision** / 打开更早的决定 → `openResolution(earlier_cycle_id)` | — |

Summary sentences (resolution-summary), "What happened" / 发生了什么 section titles and the findings-slot `empty` sentences per cause are also in the ZH dictionary (all listed in the R5 commit's ZH block; every one is swept by `test_every_new_string_reaches_a_chinese_reader`).

Cause producers: `errors.escalation_cause` (order = ladder: lock → NOTHING_AUDITED → INVALID_REPLY → BOUNDS_EXCEEDED → contested (auditor_concern) → model ESCALATE (auditor_escalated) → ""), stored by `record_verdict`; legacy rows without the field are named from the receipt's `audit_integrity` in `overview.escalations`. Remediations stay `["revise","stop"]` for every audit cause.

## Deviations (and why)

1. **Mapping site.** The directive says "map … to a cause in build.py (~1100-1110)". The `cause = ""` fallback there is only reached for build-loop stops (rounds exhausted etc.); the five ESCALATE branches are recorded by `cmd_run`/`cmd_audit` (`main.py` → `record_verdict`), which `build.py` returns from immediately (`if status == "ESCALATED": return EXIT_ESCALATED`). So the pure map lives in `errors.py` (beside the remediation tables) and is called from `main.py`; `build.py` is untouched. Legacy/receipt fallback in `overview.py`.
2. **"Run the audit again" is a Revise, not an audit-only retry.** The server's direct retry (`/api/resolve` action `retry_provider`) is refused for non-provider escalations ("only a provider-failure escalation can be retried directly"), and no audit-only remediation exists. The primary option is relabelled "Run the audit again" with the guidance prefilled ("Run the audit again on the same work…"), which reopens the cycle for one more round with the work unchanged.
3. **PASS → "Passed" / 已通过, not 通过.** `"Passed":"已通过"` already ships (used by the review card's status label and elsewhere); the raw-word entry `"PASS":"通过"` also exists for the inspector. Changing the shared entry would alter other surfaces; "已通过" is the natural badge form. Flagging for the owner to override if 通过 is wanted.
4. **Friendly model names are derived, not looked up.** `providers/specs.py` carries `(id, capability note)` pairs, no display names, and `providers/` belongs to another builder. `friendlyModel` derives the name from the id (family table + version join); the raw id stays in the inspector.
5. **One-line insert inside `runCard`** (other builder's region) as instructed: `+ (live ? forecastLine(d) : '')` in the run-meta row; nothing else in 6016-6099 changed.
6. **Harness change is additive**: `render()` now returns `extra` beside `en`/`zh` (older tests sweep only the two slot maps; verified green).
7. The apostrophe-in-JS-comment scanner (`test_no_string_literal_in_the_page_script_spans_a_line`) rejected three of my comment lines; reworded ("the auditor ladder", "The one real action of a locked cycle").

## Counts

- Commits: 6 (R1–R6), all with `Co-Authored-By` + `Claude-Session` trailers.
- New tests: 26 functions / 37 cases in `tests/test_ux_results.py`; 2 existing tests updated with mutation-naming docstrings; 1 harness extended.
- New ZH dictionary entries: 40 lines added to `page.py`'s `ZH` (≈62 distinct EN→ZH pairs) + 3 patterns (`N issues`, `Usually A–B min…`, `Usually about N min…`).
- New page functions: verdictWord, severityWord, tierWord, findingCard, friendlyModel, forecastText, forecastLine; new table CAUSE_COPY, VERDICT_WORDS, MODEL_FAMILY. Removed: findingTier.
- Full suite: 2507 passed, 2 skipped (node-dependent tests ran; node present).

---

# Review fixes (after `review-ux-results.md`, lead's rulings 1–7)

Branch `fusion/ux-results`, fast-forwarded to `fusion/evidence-authority` tip `dc524f3` (no conflicts; the tip already contained the six R1–R6 commits via bf32c8e), then:

| sha | commit |
|---|---|
| 15ace92 | tests: chat-lane and latency fakes accept the billing slice's usage_context (out of slice — 7 failures on the untouched tip; test fakes widened only) |
| 7b91eae | review fixes: the lock names its holder, rule ids off the first paint, bare model ids, cached forecast |

Full suite on 7b91eae, foreground: **2575 passed, 2 skipped, 0 failed** (352.6 s).

## Ruling by ruling

**(1)(2) Lock recorded on the refused commit; "open the earlier decision" targets the holder.**
`state.record_build_escalation(..., locked_by=)` stores the holder on the REFUSED commit's own cycle; the holder's record is never touched. `main._lock_holder` starts from the cycle `open_or_advance` refused for and follows `locked_by` through a chain of refused commits (bounded) to the decision actually pending. `main._record_lock` writes the object for a new sha and writes nothing when the sha IS the holder's commit. `overview.escalations` emits `earlier_cycle_id` only from `locked_by` when that cycle is still ESCALATED, and otherwise drops the lock cause (falls back to the receipt-derived cause or "") — no self-reference, no "oldest escalation in the project". `_earliest_other_open` deleted.
Proof: `test_a_locked_cycle_points_at_its_holder_not_the_oldest_decision` (A oldest, B, C locked by B → C→B, never A, never C; settle B → C no longer claims a lock) and the real-command scenario below.

**(3) Cause stored on the primary routes.** `cmd_run`'s early return now calls `_record_lock` before `return EXIT_ESCALATED` (and prints `crossaudit resolve <holder>`); `cmd_audit` records through `_record_round`, which under the lock writes the refused commit's object instead of a stale/duplicate `record_verdict`. `test_the_real_commands_record_the_lock_on_the_refused_commit` drives `cmd_run` (A, B escalate on unrelated lineages; C on B refused) and `cmd_audit` (D on C refused) with the replay provider — no cause injected; both C and D name B; A/B untouched; re-running B's own commit writes nothing new. Note: the lock reads the direct parent, so in a local deployment (ledger commits between generator commits) it fires for a re-audit of the escalated commit or a commit made directly on it; the test commits C on B's commit for that reason.

**(4) Rule ids off the first paint.** `findingCard` and the Decision Center issues no longer render `.finding-rule`; the id is the details line's `title` tooltip (`Rule id: CA-…`, ZH pattern `规则编号：…`) and, on the review card, a `Rules` row inside the collapsed Details block. Grep test strict: `RULE_ID` must not match the visible first paint of the chat turn, the review card, or the Decision Center issues slot. Reviewer's five hits → 0.

**(5)(11) One distinct "What happened" sentence per cause** (`overview.CAUSE_WHY`), none a restatement or prefix of its title or summary (asserted by folding both). A wordless `auditor_escalated` gets our sentence under the title "What happened" (not "What the auditor said").

| cause | What happened (EN / ZH) |
|---|---|
| nothing_audited | The generator finished without writing any file under the audited folder, so the auditor had no files to check; the folder is unchanged. / 生成者完成时没有在受审文件夹下写入任何文件，审计者因此没有可检查的文件；该文件夹未改动。 |
| invalid_reply | The reply was checked against the required format and rejected; CrossAudit never guesses a verdict from a reply it cannot parse, so the round was handed to you. / 该回复经过格式校验后被拒绝；CrossAudit 不会从无法解析的回复中猜测裁定，因此本轮交由你处理。 |
| bounds_exceeded | The audited files exceed what one audit prompt can hold; the auditor was not shown a partial set, and nothing was judged. / 受审文件超出了单次审计提示能容纳的范围；审计者没有被展示部分文件，也没有作出任何判断。 |
| auditor_escalated (no findings) | The auditor returned no findings and no reason; only its request for a human decision was recorded. / 审计者没有返回任何发现或原因；仅记录了其请人工决定的请求。 |
| escalation_locked | A newer commit was made while an earlier round was still waiting for you; the new commit was not audited, so the pending decision cannot be overtaken. / 在更早的一轮仍在等待你时，产生了新的提交；新提交未被审计，因此待定的决定不会被绕过。 |

**(6) Unknown model ids render bare.** `friendlyModel` names only the catalogue shapes (claude-{opus,sonnet,haiku}-N-M[-date], claude-N-M-{…}, gpt-N.M-{sol,terra,luna}, gemini-N.M-{pro,flash}, deepseek-vN-{pro,flash}); anything else is the id without its provider prefix (`gpt-oss-120b`, `Qwen/Qwen3-235B-A22B`, `glm-4.6`, `gpt-4o`, `my-local-model`). M12 is now the pinned behaviour.

**(7) Forecast cost.** `usage.project_forecast` caches on `(ledger mtime, ledger size, tuple of completed run rows)`; `forecast_rows` sorts the timeline once and bisects each run's window (legacy rows without `run_id`; attributed rows use the billing slice's `aggregate_by`). `test_the_forecast_is_cached_and_the_join_is_not_quadratic`: 1000 runs × 50 000 lines — cached snapshot path < 50 ms (measured ≈0.05 ms), forecast cache hit < 50 ms, uncached bisected join < 1 s (was 1.7 s quadratic). The 50 000-line JSON parse on a ledger append is `read_events`, pre-existing and outside this slice.
Sub-minute floor: p75 (ranged) or p50 under 60 s → "Usually under a minute" / 通常不到 1 分钟 (+ cost); pinned for 10–14 s and 20 s runs (review M11).

**(8)(9)(10)** Floor pinned (above). Tier sentence restored: "raised by the auditor, not yet reproduced" / 由审计者提出，尚未复现. `read_events` opens with `errors="replace"`; a damaged line counts as malformed and the snapshot (forecast included) still renders — `test_a_non_utf8_byte_in_the_ledger_does_not_take_the_snapshot_down`.

## New/changed strings (EN → ZH)
`Usually under a minute` → 通常不到 1 分钟 (+ pattern with cost); `Rule id: <id>` → 规则编号：<id> (pattern); `Rules` → 规则; `raised by the auditor, not yet reproduced` → 由审计者提出，尚未复现 (replaces `raised by the auditor`); the five CAUSE_WHY sentences above (replace the five earlier ones).

## Not changed (flagged for the owner)
- PASS reads 已通过 on the round row while the pre-existing status label says 通过复核; "Checks only" kept as directed (reviewer suggests "Automatic checks only").
- `bounds_exceeded` still has no end-to-end fixture that drives the prompt bound; covered by the pure ladder test and the receipt-derived fallback.

## Counts
Files changed in 7b91eae: 8 (state.py, main.py, overview.py, page.py, usage.py, render_decision.py, test_console_stop_causes.py, test_ux_results.py). test_ux_results.py: 30 functions / 40 cases (+4 tests: holder scenario, real-command lock, cache/timing, non-UTF-8 ledger; friendlyModel/forecast/grep cases extended).
