# Independent review — B. results & decisions (fusion/ux-results, R1–R6, merged bf32c8e)

Reviewer: independent (did not write the change). Worktree: detached `bf32c8e` at
`scratchpad/wt-review-results`, `crossaudit.__file__` confirmed inside it, removed at the end.
Python: `crossaudit_v4/.venv/bin/python`. Commits reviewed: `git log --oneline ad1dc0b..fusion/ux-results`
= 6852e4c 7622c74 4d9f2dc 569c323 45db5b2 f44b22f.

## Verdict: **NEEDS CHANGES**

The slice is real work and the suite is green (**2527 passed, 2 skipped, 338.9 s**, foreground, on the
merge commit — the build report's 2507 predates the setup slice merging in). Verdict words, the
observation-first finding, the collapsed Details record and the forecast all render correctly in both
languages. What fails is the *escalation-lock* half of R5: its cause is written by a path that makes
the cycle point at itself, its "earlier decision" is an unrelated task's decision, and the two routes
a person actually uses never write the cause at all. Two smaller items (rule ids still on the first
paint; unknown model ids given invented names) contradict the owner's directives directly.

---

## 1. Rendered surfaces (shipped JS under node, via `tests/harness/render_decision.py`)

### 1a. Chat view

```
PASS, no findings          [en] A Auditor Passed No findings. The audited increment passed.
                           [zh] A 审计者 已通过 未发现问题。该受审增量已通过。

BLOCKED, 1 deterministic + 1 model finding
  [en] A Auditor Needs changes
       No extraction procedure recorded.
         must fix · work/meta.yml · verified by a check · CA-REP-001
       The summary states 0.052 while the data records 0.044.
         must fix · work/a.md · raised by the auditor · CA-TXT-001
  [zh] A 审计者 需要修改
       No extraction procedure recorded.
         必须修改 · work/meta.yml · 已由检查验证 · CA-REP-001
       The summary states 0.052 while the data records 0.044.
         必须修改 · work/a.md · 由审计者提出 · CA-TXT-001
```
The raw word survives only as the colour class (`class="status BLOCKED"`), never as text. Correct.

### 1b. Review card

```
PASS  [en] first paint: Independent review · Passed review · Independent auditor approved the result
           · No blocking findings · Recorded in the audit ledger · Round 1/3 · Passed
           · Automatic checks 4 rules · Admit result
      details: Details | Generator Claude Opus 4.8 | Auditor GPT-5.6 Terra
               | Commit cccccccccccc | Cycle ffffffffffffffff
      [zh] 独立审查 · 通过复核 · 独立审计者已批准该结果 · 没有阻断性问题 · 已记录到审计账本
           · 第 1/3 轮 · 已通过 · 自动检查 4 条规则 · 准入结果
      details: 详情 | 生成者 Claude Opus 4.8 | 审计者 GPT-5.6 Terra | 提交 … | 审计循环 …

BLOCKED [en] first paint: Independent review · Needs changes · Round 1/3 · 2 findings
             · Automatic checks 4 rules · Findings round 1
             · No extraction procedure recorded. must fix · work/meta.yml · verified by a check · CA-REP-001
             · The summary states 0.052 while the data records 0.044. must fix · work/a.md
               · raised by the auditor · CA-TXT-001 · View audit details
        [zh] 独立审查 · 需要修改 · 第 1/3 轮 · 2 项发现 · 自动检查 4 条规则 · 发现的问题 第 1 轮 · … · 查看审计详情
```
`<details>` is closed by default (no ` open`). Correct.

### 1c. Decision Center (all seven causes, both languages) — see §1e for the full slot dump

Flags / titles / what-happened / next step, EN → ZH:

| cause | flag | title | "What happened" | next step |
|---|---|---|---|---|
| nothing_audited | Nothing to review yet / 尚无可审内容 | The task produced no work in the audited folder / 任务未在受审文件夹中产生任何工作 | the task produced no work in the audited folder, so there was nothing to review / 任务未在受审文件夹中产生任何工作，因此没有可审查的内容 | Tell the generator what to create inside the audited folder and run one more round, or stop this task. / 告诉生成者应在受审文件夹中创建什么，然后再运行一轮；或停止此任务。 |
| invalid_reply | Auditor reply unreadable / 审计者回复无法读取 | The auditor’s reply could not be read / 审计者的回复无法读取 | the auditor's reply could not be read / 审计者的回复无法读取 | Run the audit again on the same work, switch the auditor model, or stop this task. / 对同一份工作再次运行审计、更换审计者模型，或停止此任务。 |
| bounds_exceeded | Task too large for one audit / 任务过大，无法一次审计 | The task is too large for one audit / 该任务过大，无法在一次审计中完成 | the task is too large for one audit / 该任务过大，无法一次审计 | Narrow the scope or split the task into smaller pieces and run one more round, or stop this task. / 缩小范围或将任务拆分为更小的部分，然后再运行一轮；或停止此任务。 |
| auditor_escalated | The auditor asked for you / 审计者请你介入 | The auditor asked for your judgment / 审计者请你作出判断 | *(the auditor's own words)* "The claim about sample size cannot be settled from the data given." — section title **What the auditor said / 审计者的说明** | Read the auditor’s reason, then tell the generator how to address it or stop this task. / 阅读审计者的原因，然后告诉生成者如何处理；或停止此任务。 |
| escalation_locked | Waiting on an earlier decision / 等待更早的决定 | This task is already waiting for your earlier decision / 此任务仍在等待你更早的决定 | this task is already waiting for your earlier decision / 此任务仍在等待你更早的决定 | Open the earlier decision and settle it; this task continues from there. / 打开更早的决定并作出处理；此任务将从那里继续。 |
| auditor_concern *(pre-existing)* | The auditor raised a concern / 审计者提出了一项疑虑 | The audit needs your decision / 审计需要你作出决定 | 审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断 (ZH present) | Review the auditor's concern … *(overview prose, translated)* |
| repair_refused *(pre-existing)* | Automatic repair refused / 自动修复被拒绝 | The revision reached outside the audited files / 修订改动了已审计文件之外的内容 | the automatic repair was refused in round 2 because … / 第 2 轮的自动修复被拒绝，原因：… | Tell the generator to keep the fix inside the audited files … / 请告诉生成者把修复限制在已审计文件之内… |

Guidance prefill: `nothing_audited` and `invalid_reply` only, EN and ZH, matching the build report.
Secondary button: `Open the earlier decision / 打开更早的决定`, `hidden=false`, `data-earlier-cycle=<id>`
for `escalation_locked`; `Review provider connection`, hidden, `data-earlier-cycle=""` for every other
cause. Confirmed by direct render.

### 1d. First-paint grep (outside `<details>`), every hit reported

| surface | 40-hex | 12-hex | 7-hex | `anthropic:`/`openai_compat:`/`:claude`/`:gpt` | `CA-[A-Z]+-\d` | raw PASS/BLOCKED/ESCALATE/DCL_ONLY |
|---|---|---|---|---|---|---|
| chat turn, PASS | – | – | – | – | – | – |
| chat turn, BLOCKED | – | – | – | – | **CA-REP-001, CA-TXT-001** | – |
| review card, PASS | – | – | – | – | – | – |
| review card, BLOCKED | – | – | – | – | **CA-REP-001, CA-TXT-001** | – |
| Decision Center, nothing_audited / invalid_reply / bounds_exceeded / escalation_locked | – | – | – | – | – | – |
| Decision Center, auditor_escalated (issues slot) | – | – | – | – | **CA-TXT-001** | – |

**Five hits, all rule ids.** Everything else the owner named — commit shas, cycle ids, provider:model
strings, raw verdict words — is clean on every surface. See defect 4.

### 1e. Forecast line, rendered from `usage.run_forecast` output

| history | EN | ZH |
|---|---|---|
| 0 runs | First run here — no estimate yet | 首次运行，暂无预估 |
| 1 run (150 s, $0.31) | Usually about 3 min · about $0.31 | 通常约 3 分钟 · 约 $0.31 |
| 3 runs (120/180/240 s) | Usually 3–4 min · about $0.30 | 通常 3–4 分钟 · 约 $0.30 |
| 3 identical runs | Usually about 3 min · about $0.30 | 通常约 3 分钟 · 约 $0.30 |
| 10 runs (60…600 s) | Usually 3–8 min · about $0.55 | 通常 3–8 分钟 · 约 $0.55 |
| 10 steady + one 10 h outlier | Usually about 3 min · about $0.30 | 通常约 3 分钟 · 约 $0.30 |
| 3 unpriced runs | Usually 2–3 min | 通常 2–3 分钟 |
| 3 runs of 10–14 s | Usually about 1 min · about $0.01 | 通常约 1 分钟 · 约 $0.01 |

The outlier row is the important one: p50/p75 are unmoved. No `provider:model` string appears.
Missing ledger, corrupt ledger (malformed JSON lines), non-sqlite journal and old-schema journal all
return `{"runs":0,"priced_runs":0,"seconds":null,"usd":null}` without raising — verified by driving
`usage.summary(cfg)` against each. (One exception: defect 10.)

### 1f. Friendly model names — the actual mapping

`Claude Opus 4.8`, `GPT-5.6 Terra`, `Claude Haiku 4.5` (release date dropped), `Gemini 3.5 Pro`,
`DeepSeek V4 Pro`, `Claude 3.5 Sonnet`, `Grok 4`, `Kimi K2`, `GLM 4.6`, `o3 Mini`, `Human`, `""`→`""`.
Unknown ids are **not** returned bare — see defect 6.

---

## 2. Causes: does every ladder branch reach the state store?

Driven end to end through the real `cmd_run` / `cmd_audit` with the replay provider (probe files
written under `tests/`, run, then deleted; worktree left clean):

| ladder branch (`auditor/run.py`) | driver | stored `escalation_cause` |
|---|---|---|
| model reply `ESCALATE` | `cmd_run` | ✅ `auditor_escalated` |
| `invalid` → INVALID_REPLY | `cmd_run` (reply `{"verdict":"WAT"}`) | ✅ `invalid_reply` |
| `not scope_started` → NOTHING_AUDITED | `cmd_run` (emptied audited folder) | ✅ `nothing_audited` |
| `bounded` → BOUNDS_EXCEEDED | pure `escalation_cause` only (no fixture drives the bound) | ⚠ untested end to end |
| `lone_model_blocker: escalate` → contested | pre-existing `auditor_concern`, reaches the row | ✅ |
| `escalation_lock` | see defect 1/3 | ❌ never on the two primary routes |

Legacy path: a row with no stored cause is named from the receipt's `audit_integrity`
(`overview._INTEGRITY_CAUSES`, `receipt_integrity`) — verified green for NOTHING_AUDITED /
INVALID_REPLY / BOUNDS_EXCEEDED; the lock has no legacy fallback at all (there is no integrity code
for it), so a pre-R5 locked record renders the generic "Automatic loop paused" screen.

Every cause's `remediations` is `["revise","stop"]`, and the dialog offers exactly Revise / Stop —
so each cause's *stated* next step is one the dialog offers, except `escalation_locked`, whose primary
action ("Settle the earlier decision") is not a dialog action at all but a link (defects 1–3).

---

## 3. Numbered defects

**1. `escalation_locked` makes a cycle point at itself — a self-referential dead end.**
`src/crossaudit/console/overview.py:497-507` (`_earliest_other_open`), `:621-623`,
`src/crossaudit/console/page.py:4903-4906`.
The cause is written by `record_verdict` **onto the cycle that holds the lock**, because
`open_or_advance` returns `dict(c, cycle_id=<the escalated cycle>, blocked_by_escalation=True)`
(`controller/state.py:215-226`). Reproduced: a cycle escalated by `record_build_escalation`
("the generator produced nothing"), then `crossaudit audit --sha <same>` →
`{'e8e21eab101a83d6': ('ESCALATED', 'escalation_locked')}`. Its own reason is replaced, and
`_earliest_other_open(state, cid)` *excludes* `cid`, so the screen now tells the person
"This task is already waiting for your earlier decision → Open the earlier decision" about a decision
that **is this one**. With no other open escalation the key is omitted entirely, the button is hidden
(`page.py:4906`), and the copy still says "Open the earlier decision first" with nothing to press.
*Fix:* record the lock against the *blocked* commit, not the holding cycle; and when the holder cannot
be named, do not emit `escalation_locked` at all — fall back to the cycle's own cause.

**2. The "earlier decision" is chosen globally, not by who holds the lock.**
`src/crossaudit/console/overview.py:497-507`.
The lock is held by the cycle whose `active_sha` equals this commit or its parent
(`controller/state.py:215-226`). `_earliest_other_open` ignores that and returns the *oldest other
ESCALATED cycle in the project*. Reproduced: cycles A (unrelated, oldest), B (unrelated), C (locked) →
C's `earlier_cycle_id` == A. Settling A does not unblock C.
*Fix:* resolve the holder by `active_sha` (this cycle's `active_sha` or its parent), and drop the row's
`earlier_cycle_id` when no holder matches.

**3. On the two routes a person actually uses, the lock cause is never stored.**
`src/crossaudit/cli/main.py:1651-1656`; `src/crossaudit/controller/state.py:389-393`, `:427-437`.
`cmd_run` (and therefore the console's build loop) prints an English-only CLI sentence and
`return EXIT_ESCALATED` **before** `run_audit`/`record_verdict` — nothing is stored, so no
Decision-Center row is created. `cmd_audit` on the same sha raises `IntegrityDenial`
("round N … already recorded a verdict"). `cmd_audit` on a *new* sha whose parent cycle is escalated
hits `c["active_sha"] != sha` → `stale_verdict_ignored`, returns `EXIT_ESCALATED` with nothing written
(both reproduced). The whole `escalation_locked` copy set, its ZH, `_earliest_other_open` and the
secondary button are therefore unreachable from the product's main path; the tests only exercise them
by passing `escalation_cause="escalation_locked"` straight into `record_verdict`
(`tests/test_ux_results.py:369-372`). *Fix:* give `cmd_run`'s early return a durable decision object
(the way `record_build_escalation` does) before returning, or state plainly that the lock is a
CLI-only surface and delete the console copy.

**4. Rule ids are still on the first paint — the directive says they should not be.**
`src/crossaudit/console/page.py:5931` (`findingCard`), `:4869` (Decision-Center issues).
Five hits in §1d. The build's own test only asserts the id does not *open* the first line
(`tests/test_ux_results.py:119-123`), which is a weaker claim than the one the owner made. Commit,
cycle and model went behind `<details>`; the rule id did not.
*Fix:* move `finding-rule` inside the same disclosure (or a `title=` tooltip only), or have the owner
confirm the muted details line counts as "on demand".

**5. "What happened" restates the title verbatim for four of the five causes.**
`src/crossaudit/console/page.py:4757-4793` (`CAUSE_COPY.title`) vs
`src/crossaudit/console/overview.py:203-214` (`CAUSE_WHY`).
`bounds_exceeded`: "The task is too large for one audit" / "the task is too large for one audit".
`escalation_locked`: identical. `invalid_reply`: identical but for a curly vs straight apostrophe
(`CAUSE_COPY` uses `’`, `CAUSE_WHY` uses `'` — also an inconsistency in itself).
`nothing_audited`: title is a prefix of the line. In Chinese the duplication is exact for
`invalid_reply` and `escalation_locked`. A section a person reads as new information carries none.
*Fix:* make `CAUSE_WHY` say something the title does not (what was checked, what was left untouched),
or drop the "What happened" block for causes where the title already is the whole story.

**6. An unknown model id gets an invented product name instead of degrading to the bare id.**
`src/crossaudit/console/page.py:5941-5954` (`friendlyModel`).
Measured: `openai_compat:abc_xyz-99` → `Abc Xyz 99`; `openai_compat:gpt-oss-120b` → `GPT Oss 120b`;
`openai_compat:Qwen/Qwen3-235B-A22B` → `Qwen Qwen3 235B A22B`; `zhipu:glm-4.6` → `GLM 4.6`
(the real name is GLM-4.6); `openai:gpt-4o` → `GPT 4o`; `llama-3.1-70b-instruct` → `Llama 3.1 70b Instruct`.
`my-model-v2` and `my_model_v2` both render `My Model V2`. An operator who typed the id can no longer
find it — the raw id is only in the inspector. `tests/test_ux_results.py:214` pins the wrong behaviour
(`"custom · openai_compat:my-local-model": "My Local Model"`): mutation M12, which *implements* the
spec's rule, turns that test red.
*Fix:* apply the family table only when a known family token matches; otherwise return the bare id.

**7. The forecast join is O(runs × ledger events) and sits on the console snapshot's hot path.**
`src/crossaudit/usage.py:442`, `:497-521` (`forecast_rows`), `src/crossaudit/console/server.py:812`.
`events` is the *entire* ledger (`usage.jsonl` is never pruned) and `_journal_runs` returns every
retained run (`RETENTION_DAYS = 14.0`, `RETAIN_RECENT_RUNS = 200`, and only when the console daemon's
watchdog sweep actually runs). The `summary()` cache signature now includes the journal mtime/size, so
it is invalidated on **every ledger append**, i.e. after every model call during a live run. Measured
on this machine: 200×5 000 → 33 ms; 500×20 000 → 324 ms; 1 000×50 000 → **1 671 ms** per snapshot.
That is the opposite of "always-visible progress".
*Fix:* sort events by `t` once and bisect each window, and bound the join to the most recent N runs.

**8. Sub-minute runs are floored to "about 1 min", and nothing tests it.**
`src/crossaudit/console/page.py:5961` (`const mins=x=>Math.max(1,…)`).
Mutation M11 removes the floor (a 20 s run then reads "Usually about 0 min") and the suite stays
**green**. The floor is the right call; it just has no guard.
*Fix:* pin it — one case with `seconds.p50 < 60`.

**9. The evidence-tier sentence lost the half that carried the epistemics.**
`src/crossaudit/console/page.py:5922-5923`; pin updated at
`tests/test_console_stop_causes.py:255-268`.
"Raised by the auditor, not yet reproduced" → "raised by the auditor". A model-only claim and a
verified one now differ only by the presence of a trailing word, and the un-reproduced state is
inferable only by absence. The test update itself is honest (it names the mutation and still asserts
both sentences); the copy change is the regression.
*Fix:* "raised by the auditor, not yet reproduced" / 由审计者提出，尚未复现.

**10. A non-UTF-8 byte in the ledger raises out of `summary()`.**
`src/crossaudit/usage.py:365-371`. `UnicodeDecodeError` escapes the `except OSError`, so the whole
snapshot fails, forecast included. Pre-existing (the reader is untouched by this slice), but the
spec's "never blocks/errors with a missing or corrupt ledger" now depends on it.
*Fix:* `errors="replace"` on the open, and count the line as malformed.

**11. "What the auditor said" shows *our* sentence when the auditor recorded no findings.**
`src/crossaudit/console/overview.py:554-561`.
`why = issues[0]["observation"] if cause == "auditor_escalated" and issues else CAUSE_WHY[cause]`, so a
findings-free ESCALATE renders the section title "What the auditor said" over
"the auditor asked for your judgment" — which the auditor did not say, and which repeats the title
verbatim (defect 5). Reproduced in a live `cmd_run` fixture.
*Fix:* fall back to the receipt's stop reason, or swap the section title to "What happened" when the
auditor left no words.

### Copy quality (spec item 5)
Every new EN string is ≤ 2 sentences and plain. Glossary honoured: 审计者 / 生成者 / 准入 / 需要修改 /
需要你 all present and used consistently. Two notes beyond the defects above:
- **PASS renders two different Chinese words on one card**: the status label is 通过复核 and the round
  row is 已通过. The build report's deviation 3 flags 已通过 vs the glossary's 通过; the *inconsistency
  within one card* is the part worth deciding. Suggest: 已通过 everywhere on the surface.
- `Checks only` (DCL_ONLY) is terse to the point of opacity in English; the Chinese 仅自动检查 is
  clearer. Suggest EN "Automatic checks only".

### Regressions (spec item 6)
- `tests/test_console_stop_causes.py::test_the_page_names_the_tier_in_a_sentence_and_never_a_route` —
  updated honestly: the docstring names the mutation, `findingTier` absence is now asserted, the count
  guard moved to `findingCard`, both tier sentences and the route-name guard are still pinned. **Not weakened.**
- `tests/test_report_provenance.py::test_page_markup_places_the_provenance_note_outside_the_findings_list` —
  the marker moved from `class="finding"` to `map(findingCard)` because the class now lives inside the
  shared renderer. Same claim, same strength. **Not weakened.**
- `tests/harness/render_decision.py` — additive only (`getAttribute`/`setAttribute` on the fake DOM,
  a real `t`, and `extra[locale]` outside the slot maps the older tests sweep). **Not weakened.**
- Finding-states surface guard (`test_no_dashboard_surface_carries_a_route_name_or_a_state_word`)
  passes unchanged.

---

## 4. Mutation log (15 mutations; suite = `test_ux_results`, `test_console_stop_causes`, `test_report_provenance`, `test_console_translation_boundary`, `test_overview`, `test_usage`)

| # | mutation | result | first failure |
|---|---|---|---|
| M1 | `verdictWord` returns the raw word | **RED** | `test_the_chat_badge_says_what_the_verdict_means[PASS]` |
| M2 | `findingCard` leads with the rule id | **RED** | `test_a_finding_leads_with_the_observation_and_demotes_the_rule_id` |
| M3 | the Details record renders `<details open>` | **RED** | `test_the_review_card_first_paint_carries_no_identifier[PASSED]` |
| M4 | forecast p50 = mean instead of median | **RED** | `test_a_single_outlier_barely_moves_the_forecast` |
| M5 | drop the `escalation_lock` branch of `escalation_cause` | **RED** | `test_the_cause_follows_the_ladder_in_order` |
| M6 | locked cycle points at the **newest** other open decision | **RED** | `test_the_decision_center_names_every_cause_in_both_languages` |
| M7 | `_journal_runs` counts cancelled/failed runs | **RED** | `test_the_forecast_reads_the_run_journal_read_only` |
| M8 | the locked row carries no `earlier_cycle_id` | **RED** | `test_a_locked_cycle_points_at_the_earlier_decision` |
| M9 | `forecastText` drops the `!f.runs` guard | **GREEN** | *equivalent mutant* — `runs == 0` implies `seconds is None`; no gap |
| M10 | `tierWord` stops distinguishing a verified finding | **RED** | `test_a_finding_leads_with_the_observation_and_demotes_the_rule_id` |
| M11 | remove the one-minute floor in `mins` | **GREEN (SURVIVED)** | **real gap → defect 8** |
| M12 | unknown model ids degrade to the bare id (the spec's rule) | **RED** | `test_friendly_model_names_are_derived_from_the_id` — **the test pins the wrong behaviour → defect 6** |
| M13 | the cause sentence never becomes the stop reason | **RED** | `test_the_decision_center_names_every_cause_in_both_languages` |
| M14 | forecast counts every ledger event, not just the run's window | **RED** | `test_forecast_rows_join_ledger_events_to_run_windows` |
| M15 | the audit cause loses its next step | **RED** | `test_the_stored_cause_reaches_the_dashboard_with_a_why_and_a_next_step[nothing_audited]` |

13 RED / 2 GREEN (one equivalent, one real gap). Guards are genuinely load-bearing; the failures are
of *intent* (defects 1–3, 6), not of coverage.

## 5. Counts
- Commits reviewed: 6. Files touched by this slice: 10.
- Suite on `bf32c8e`, foreground: **2527 passed, 2 skipped, 0 failed, 338.9 s**.
- Rendered scenarios: 4 chat turns, 4 review cards, 14 Decision-Center renders (7 causes × 2 locales),
  8 forecast histories × 2 locales, 23 model-id mappings.
- First-paint grep hits: **5**, all `CA-[A-Z]+-\d`. Zero hex, zero provider:model, zero raw verdicts.
- End-to-end cause probes through `cmd_run`/`cmd_audit`: 6 (3 ✅, 1 untested branch, 2 reproducing defects 1/3).
- Defects: 11 (3 blocking: 1, 2, 3).
- Worktree removed at the end; no tracked file modified (`git status --porcelain` empty after every
  mutation and after the probes).
