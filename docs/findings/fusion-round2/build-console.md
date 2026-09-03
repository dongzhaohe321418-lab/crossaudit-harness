# Build report — console slice (D148 causes, evidence tiers, a11y, denial i18n seam)

Branch `fusion/console`, base `f050cbd`, worktree `scratchpad/wt-console`. Not pushed. No DECISIONS.md entry.
Touched: `console/overview.py`, `console/streams.py`, `console/page.py`, `console/server.py`, `cli/i18n.py`,
`cli/denials_zh.py`, `cli/main.py` (two lines, separate commit — see deviation 9); tests `test_console_stop_causes.py`
(new), `test_console_input_names.py` (new), `test_authority_sentences_are_legible.py` (new), `test_denial_strings_are_legible.py`.
`errors.py` unchanged (see deviations). Nothing under `auditor/ receipt/ cli/build.py generator.py repair_guard.py`.
Merged in (both `--no-ff`, clean): `fusion/i18n-denials` (06d8f5d) and `fusion/evidence-authority` (e881e8a, brings ae00a1c).

## Commits

| sha | what |
|---|---|
| `53c83df` | Decision Center copy for `repair_refused` and the escalate-dial stop (derived cause `auditor_concern`); `Cycle.authority_route` + per-finding `tier`/`verified` from `receipt.json["authority"]`, shared by overview and the auditor stream via `annotate_findings`; one-sentence tier line where findings are listed (review detail, Audits view); ZH for every new string incl. patterns for the repair guard's composed reasons; `repair_refused`/`revision_retry` event text ZH; accessible names for the composer, project search and three JS-built fields; the two test files |
| `c5ad655` | two script comments reworded — `test_no_string_literal_in_the_page_script_spans_a_line` reads `//` comments too, and an apostrophe opens a string |
| `06d8f5d` | `git merge --no-ff fusion/i18n-denials` (clean, disjoint files) |
| `815a063` | `server._deny` attaches `reason_zh = i18n.denial_zh(why.reason)` (provenance-first); page `api()`/`previewData()` prefer it under zh via `denialText()`, fall back to `reason` + the text catalogue; denial gate re-measured at the new seam + a wire test |
| `e881e8a` | `git merge --no-ff fusion/evidence-authority` (review-B fixes ae00a1c + docs; clean) |
| `94f0f12` | `i18n.SENTENCES_ZH` + `sentence_zh()`/`sentence_text()` for the four route labels, the integrity clauses, every `_rationale` sentence and the escalate-dial sentence (shared compiler with the denials; `denial_zh` unchanged); denial table caught up with review B (orphaned `admit()` entry removed, verify's unknown-route-label refusal added); `tests/test_authority_sentences_are_legible.py` |
| `a91108e` | `cli/main.py`: the two rationale print sites (`why:`, `Escalated:`) pass through `i18n.sentence_text` — English byte-identical; separate commit so the lead can drop it |

## Tests / counts

- Full suite at `a91108e`, foreground: **2337 passed, 2 skipped** (341 s) — `codex-compare/full-suite-console.txt`. Earlier full runs: 2210/2 at `815a063`; the first run at `53c83df` had one flaky `test_projects_ui.py::test_runtime_model_and_effort_switch_is_committed_atomically`, green alone and in every later run.
- Gates: `test_console_translation_boundary.py`, `test_console_strings_by_execution.py`, `test_admission_and_console.py`, `test_projects_ui.py`, `test_finding_states.py` (incl. `test_no_user_facing_surface_renders_a_state_word`), every `tests/*console*.py`, `test_decision_center_a11y.py`, `test_denial_strings_are_legible.py`, `test_cli_i18n.py`, `test_guard_names_match_what_they_check.py` — all green.
- New tests: 10 in `test_console_stop_causes.py`, 3 in `test_console_input_names.py`, +2 / 1 rewritten in `test_denial_strings_are_legible.py`, 6 in `test_authority_sentences_are_legible.py` (drives `decide_authority` over review B's 7×4×4×2 grid: 14 distinct rationale sentences, all Chinese with no Latin word left).
- Mutations (D10, each restored): drop ZH entry "Automatic repair refused" → red; copy finding `state` into the finding dict → red (stop-causes + finding-states); append `authority_route` to the pipeline Verdict detail → red; remove the composer `aria-label` → 2 red; remove the `auditor_concern` derivation → 2 red.
- Denial i18n, console-driven count (540 distinct Denial sentences, static reader): **before** 52 covered by page text; **after** 538 covered (52 by page text ∪ 538 by served `reason_zh`); residual = exactly the 2 sentences in `ALLOWED_RESIDUAL` (`X: X`, `X\n\n  underlying: X`). The gate asserts `residual <= ALLOWED_RESIDUAL`.

## Every new EN → ZH pair

Evidence-authority sentences (CLI seam, `i18n.SENTENCES_ZH`; the console renders none of these — the Decision Center's `auditor_concern` copy above says it in its own words and route names stay off every surface):
- admission → 准入 · another revision round → 再一轮修订 · your decision → 由你决定 · a model audit is still needed → 仍需模型审计
- nothing was audited: the scope holds no work yet → 没有审计任何内容：范围内尚无工作
- the audit prompt exceeded its size bound, so the auditor did not see everything → 审计提示超出了大小上限，因此审计者没有看到全部内容
- the auditor's reply was not valid → 审计者的回复无效 · the model audit could not run → 模型审计无法运行
- a fixture provider exercised the loop, and a fixture cannot bless a commit → 本轮循环由测试桩供应商驱动，而测试桩不能为提交背书
- the audit did not complete cleanly → 审计未能完整完成
- An earlier escalation holds this cycle under human jurisdiction (the escalation lock), so nothing here routes around it. → 较早的一次升级已将此周期置于人工裁决之下（升级锁定），因此这里的任何路由都不会绕过它。
- Nothing was audited: the scope holds no work yet, so a person owns this round. → 没有审计任何内容：范围内尚无工作，因此本轮由人来负责。
- The only block rests on a model reading without reproduced evidence, so it goes to a person rather than to automatic revision. → 唯一的阻断仅依据模型的判读、没有可复现的证据，因此交由人来处理，而不是自动修订。
- {N} deterministic check failure(s) on committed bytes block this round; the block rests on reproduced evidence. → 已提交内容上有 {N} 项确定性检查失败阻断了本轮；该阻断基于可复现的证据。
- The block rests on the auditor's reading, which no deterministic check reproduced; it enters bounded revision by policy and is recorded as unverified. → 该阻断基于审计者的判读，没有任何确定性检查复现它；按策略进入受限修订，并记录为未验证。
- A model audit is still needed before this round can pass. → 本轮通过之前仍需一次模型审计。
- No finding blocks this round; the deterministic checks and the model audit both completed. → 没有发现阻断本轮；确定性检查和模型审计均已完成。
- The auditor asked for human judgment on this round. → 审计者要求对本轮进行人工判断。
- {Clause}, so a person owns this round. → {clause zh}，因此本轮由人来负责。 · {Clause}, so the receipt is not admissible. → {clause zh}，因此该收据不可准入。 (the clause slot is translated in turn, e.g. "The model audit could not run, so a person owns this round." → 模型审计无法运行，因此本轮由人来负责。)
- {N} further blocking concern(s) from the auditor remain unverified. → 审计者提出的另外 {N} 项阻断性疑虑仍未验证。
- the auditor raised a concern that no deterministic check reproduces; it needs your judgment → 审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断 (also in the console ZH dictionary)
- Denial table (review B catch-up): bound report names an evidence route this verifier does not know: {} → 绑定的报告指明了一个此验证器不认识的证据路由：{}; removed the orphaned "evidence route is {}, not receipt — nothing to admit" (its raise site was deleted by review-B fix 4).

Decision Center, `repair_refused`:
- Automatic repair refused → 自动修复被拒绝
- The revision did not repair the cause → 修订没有修复问题的根源
- The generator’s revision was refused twice: instead of repairing the cause, it tried to make the finding disappear, changed files the audit did not name, or grew larger than an automatic repair may be. Each attempt was rolled back, so the audited files are unchanged and nothing was admitted. → 生成者的修订已两次被拒绝：它没有修复根源，而是试图让问题消失、改动了审计未提及的文件，或超出了自动修复允许的规模。每次尝试都已回滚，因此已审计的文件未被改动，也没有任何结果被准入。
- Why the last revision was refused → 上一次修订被拒绝的原因
- Tell the generator the smallest change that repairs the cause, or stop the task without admitting its output. (overview `requested`) → 请告诉生成者能修复根源的最小改动，或停止任务且不准入其输出。
- Name the file and the smallest change that repairs the cause, then unlock one additional audited round. → 指出文件以及能修复根源的最小改动，然后解锁再一轮受审计尝试。

Decision Center, `auditor_concern` (escalate dial):
- The auditor raised a concern → 审计者提出了一项疑虑
- The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged. → 审计者依据自身判读阻断了本轮；没有任何确定性检查能复现这项疑虑。CrossAudit 不允许仅凭模型的说法驱动自动改写，因此已停止并保持文件不变。
- the auditor raised a concern that no deterministic check reproduces; it needs your judgment (`cli/main.py` sentence, shown as the "What happened" line) → 审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断
- Review the auditor's concern and its evidence. Dispute a misreading, reopen with a recorded reason, or stop without admission. → 请审查审计者的疑虑及其证据。若属误读可提出争议，也可记录理由后重开，或停止且不准入。
- If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded. → 如果疑虑成立，请告诉生成者如何处理；如果属于误读，请在此说明，你的理由会被记录。

Evidence tier line (inspector / review detail only):
- Verified by a deterministic check → 已由确定性检查验证
- Raised by the auditor, not yet reproduced → 由审计者提出，尚未被复现
- Raised by the auditor and verified → 由审计者提出，并已验证

Live run card events (build.py text, translated here):
- the revision was refused before the audit → 修订在审计前被拒绝
- asking for a smaller repair that fixes the cause → 正在要求一次更小、能修复根源的修复
- the revision changed nothing that could be reviewed → 该修订没有做出任何可供审查的改动

Repair-guard reasons (ZH_PATTERNS; the path/count is carried through untranslated):
- the automatic repair was refused in round N because R → 第 N 轮的自动修复被拒绝，原因：R(zh)
- R1; R2; … (event detail) → R1(zh)；R2(zh)
- P is outside what the last audit asked to change (allowed: L) → P 不在上次审计要求修改的范围内（允许：L）
- P is a binary file written directly by the generator, which cannot be reviewed line by line → P 是生成者直接写入的二进制文件，无法逐行审查
- the code change touches N lines, more than the M-line limit for an automatic repair → 代码改动涉及 N 行，超过了自动修复的 M 行上限
- P adds a catch-all `except` that swallows every error → P 新增了会吞掉所有错误的 catch-all `except`
- P adds a bare `pass` where a failure would otherwise surface → P 在本应暴露失败的位置新增了空的 `pass`
- P adds a retry or fallback path instead of fixing the cause → P 新增了重试或回退路径，而不是修复根源
- P adds a suppression that hides a warning or check → P 新增了会隐藏警告或检查的抑制
- P adds a skipped test or a relaxed assertion → P 新增了被跳过的测试或被放宽的断言

Accessible names:
- Your task or message (composer textarea) → 你的任务或消息
- Search projects (hub search) → 搜索项目
- JS-built: "Git author name", "Git author email", "Exact model ID" — existing catalogue entries reused as `aria-label`.

## Deviations, with reasons

1. **Where the file/pattern sentence sits.** The summary stays a fixed, fully translatable sentence; the guard's own sentence ("src/x.py adds a catch-all `except` …") is the "Attempted" block's copy directly beneath it, under the title "Why the last revision was refused". Composing it into the summary would have made the summary a pattern-translated string and put a path inside the dialog's `aria-describedby`. `escalations()` exposes it as `why` by stripping the round wrapper.
2. **`auditor_concern` is derived, not stored.** `record_verdict` has no cause and `cli/main.py` is off-limits, so `escalations()` names it once from `Cycle.authority_route == "human-decision"` (receipt, verifier-bound) or, for a cycle with no receipt beside its report, equality with `CONTESTED_MODEL_BLOCKER_REASON` (lazy import). Never a regex on prose. Row `cause` is otherwise the stored field.
3. **`errors.ESCALATION_REMEDIATIONS` unchanged.** Both causes are kind `audit`; REVISE (a smaller repair / your guidance) and STOP are the right pair. A "Dispute" button would be a new `RemediationAction` and a separate decision.
4. **`verified` for a model finding** is `state == CONFIRMED` from the receipt record (the sidecar's own rule); the STATE WORD itself is never copied — `test_no_dashboard_surface_carries_a_route_name_or_a_state_word` and the finding-states guard both stay green, and the mutation that copies it is red.
5. **Live run card**: `repair_refused` already renders as an ordinary activity line (actor "Process", text + detail) through the same path as `revision_requested`; nothing routes it to a banner. What was missing was ZH for its text and detail, added. The loop steps (ledger-derived) are untouched.
6. **a11y test scope** covers static markup (html.parser, label ancestry / `for=` / aria-label / aria-labelledby / title, hidden exempt) AND the eight JS-built fields (regex per line, `<label` opened before the field). Three JS fields were unnamed and got labels; `hub-search` too.
7. **Denial seam**: `reason_zh` is added only when the table has an entry (`None` → key absent), so a body without it is byte-identical to before. The two other places page.py reads `.reason` (approval card, admission card, governed-action row) are not Denials and were left alone.
9. **`cli/main.py` touched, two lines, separate commit `a91108e`.** The rationale is printed raw at two sites and nothing else routes it through i18n, so the table alone would reach nobody. English output is byte-identical (`sentence_text` is verbatim under en). Drop the commit if the lead prefers a hand-off.
10. **Console dictionary for route labels / rationale: not added.** Nothing in the console renders them (the Verdict detail is unchanged by design, the Decision Center carries its own sentence), and an entry nothing renders is the kind of thing the design system deletes. The escalate-dial sentence IS rendered (the "What happened" line) and is in the dictionary.
8. Incident during my own mutation run: a `git checkout -- src/crossaudit/console` reverted an uncommitted fix, and a following `git stash`/`pop` popped another builder's stash (`stash@{0}: On speed/outlined-edit-read-gate: WIP paused by BOSS…`) into my worktree with conflicts. Restored with `git reset --hard HEAD` + removal of the stash's untracked file; the stash entry is intact (pop kept it on conflict). Nothing of theirs was committed or lost.

## Rendered Decision Center (shipped `openResolution()` under node with a fake DOM; `codex-compare/decision-render.txt`)

```
===== repair_refused EN
flag                 Automatic repair refused
title                The revision did not repair the cause
summary              The generator’s revision was refused twice: instead of repairing the cause, it tried to make the finding disappear, changed files the audit did not name, or grew larger than an automatic repair may be. Each attempt was rolled back, so the audited files are unchanged and nothing was admitted.
attempted · title    Why the last revision was refused
attempted · copy     src/x.py adds a catch-all `except` that swallows every error
recommendation       Tell the generator the smallest change that repairs the cause, or stop the task without admitting its output.
option 1             Revise and continue
option 1 · copy      Name the file and the smallest change that repairs the cause, then unlock one additional audited round.
blocked on           BLOCKER  CA-TXT-001   The summary states 0.052 while the data records 0.044.  Affects work/a.md

===== repair_refused ZH
flag                 自动修复被拒绝
title                修订没有修复问题的根源
summary              生成者的修订已两次被拒绝：它没有修复根源，而是试图让问题消失、改动了审计未提及的文件，或超出了自动修复允许的规模。每次尝试都已回滚，因此已审计的文件未被改动，也没有任何结果被准入。
attempted · title    上一次修订被拒绝的原因
attempted · copy     src/x.py 新增了会吞掉所有错误的 catch-all `except`
recommendation       请告诉生成者能修复根源的最小改动，或停止任务且不准入其输出。
option 1             修订并继续
option 1 · copy      指出文件以及能修复根源的最小改动，然后解锁再一轮受审计尝试。

===== auditor_concern EN
flag                 The auditor raised a concern
title                The audit needs your decision
summary              The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.
attempted · title    What happened
attempted · copy     the auditor raised a concern that no deterministic check reproduces; it needs your judgment
recommendation       Review the auditor's concern and its evidence. Dispute a misreading, reopen with a recorded reason, or stop without admission.
option 1             Revise and continue
option 1 · copy      If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded.

===== auditor_concern ZH
flag                 审计者提出了一项疑虑
title                审计需要你作出决定
summary              审计者依据自身判读阻断了本轮；没有任何确定性检查能复现这项疑虑。CrossAudit 不允许仅凭模型的说法驱动自动改写，因此已停止并保持文件不变。
attempted · title    发生了什么
attempted · copy     审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断
recommendation       请审查审计者的疑虑及其证据。若属误读可提出争议，也可记录理由后重开，或停止且不准入。
option 1             修订并继续
option 1 · copy      如果疑虑成立，请告诉生成者如何处理；如果属于误读，请在此说明，你的理由会被记录。
```

## Review fixes (codex-compare/review-console.md, 12 items) — commits `b965cef` (merge of the lead's e840b18 / 1fba14b / 3049958) and `c92f8c8`

Full suite at `c92f8c8`, foreground: **2387 passed, 2 skipped** (297 s) — `codex-compare/full-suite-console.txt`. Rendered copy after the fixes: `codex-compare/decision-render-fixed.txt`.

| # | fix | guard (mutation red) |
|---|---|---|
| 1 | `Cycle.authority_contested = bool(authority["contested_evidence_ids"])`; `_is_auditor_concern` reads it (never the route) or the exact CLI sentence; plain ESCALATE keeps "Automatic loop paused" | `test_a_plain_escalate_keeps_the_generic_copy` + the node render test: route-derived → 2 red |
| 2 | receipt-only test records the verdict with `escalation_reason=""`; sentence-only case stays separate | M13 (id branch deleted, sentence kept) → 2 red |
| 3 | no "twice"/"两次"; copy rewritten for the MERGED guard rework, where refusals are only out-of-scope files and foreign binaries (the reviewer's wording pre-dates e840b18 and would have been false): title "The revision reached outside the audited files", summary "…it changed files outside the audited directories, or wrote a binary file that cannot be reviewed line by line. The refused attempt was rolled back…" (ZH in the render file) | "twice" back → red |
| 4 | `cmd_run`: `why = invalid_reason or (sentence_text(rationale[0]) if rationale else t("run.human_decision_needed"))`; catalogue key added en/zh (需要人工决定) | `test_the_escalated_line_translates_only_our_own_sentence` → red when invalid_reason passes through |
| 5 | `<select data-fallback-vendor aria-label="Provider">`; a11y test reads `<select>` (static + JS-built) and icon-only `<button>`s (static: text minus aria-hidden glyphs; JS-built: literal buttons with no letters and no expression) | M5 new unnamed static select → red; vendor select unnamed → red |
| 6 | reopen copy ZH reuses 解锁额外一轮受审计执行 | asserted in the render test |
| 7 | request copy (overview `requested`) names only Revise-with-a-reason or Stop — the reviewer's EN/ZH verbatim; no "Dispute"/"提出争议" | render test asserts absence |
| 8 | "asking for a repair that stays within the audited files" (the rework's new retry text) → 正在要求生成者做出不超出已审计文件范围的修复; the old "smaller repair" entry removed with its source string | translation gate |
| 9 | `CONTESTED_MODEL_BLOCKER_REASON` in `errors.py` (main.py imports it; `cli.main.CONTESTED_MODEL_BLOCKER_REASON` still resolves); overview imports errors, no CLI import | — |
| 10 | `receipt_authority` public; `_receipt_authority` kept as alias; streams imports the public name. Rule-only fallback edge documented in the docstring (unchanged) | — |
| 11 | Documented: `reason_zh` is ADDITIVE on every structured JSON refusal regardless of locale; `reason` byte-identical; CLI `--json` has no `reason_zh` | wire test |
| 12 | `tests/harness/render_decision.py` (node, fake DOM, shipped `openResolution` + `zhValue`) and `test_the_decision_center_renders_each_cause_from_the_rows_the_dashboard_builds`: rows from `escalations()` for a refused repair, the dial, a plain ESCALATE — flags/summary/request asserted EN+ZH; this is the test that would have caught defect 1 | route-derived → red |
| + | `repair_caution` event (rework): text "the revision has edits the auditor should weigh" → 本次修订包含需要审计者权衡的改动; every caution/refusal sentence of the reworked guard has a ZH pattern (scope with `notes` hint, binary, budget, unscreened-files count, 6 ADDED + 2 MARKER + 2 REMOVED patterns); the "; "-joined detail is split only at a boundary that begins a guard sentence, so the scope sentence's own semicolon stays inside it and one sentence never recurses; all in `NEW_COPY` of the stop-causes gate | translation gates |

Deviation from ruling (3): the reviewer's summary sentence lists "tried to make the finding disappear … or grew larger than an automatic repair may be"; after the merged rework those are cautions handed to the auditor, not refusals, so the sentence would describe a stop that no longer happens. Kept the reviewer's shape (no count, "The refused attempt was rolled back…") with the two real refusal reasons.

## Round 3 (live-browser defects) — merge `08522ca` (fusion tip c0c98e7), commits `a27db3e`, and the harness follow-up

Full suite foreground: see `codex-compare/full-suite-console.txt` (green). New gate: `tests/test_console_round3.py` (8 tests, 5 rendered under node through the shipped functions via `tests/harness/render_decision.py::eval_page`).

| # | defect | fix | test |
|---|---|---|---|
| 1 | `#locale-toggle` unreachable while a decision card is open (`setDecidingInert` makes `.app` inert; the card sits outside it) | `#decision-locale` in the card header, same handler as the top-bar toggle, relabelled by `applyLocale` (id list + null-guard) | markup: the button is inside `#resolution-modal` and outside `.app`; rendered: `applyLocale('zh')` over a fake DOM → card toggle reads `EN` / `切换到英文`, back to `中文` / `Switch to Chinese` |
| 2 | "需要你决定 等待 provider · 心跳 205214 秒前" | `relAge` (just now / N min ago / N h ago / N day(s) ago), `durationText`, `elapsedText` (`4m 12s elapsed`), `humaniseDetail` (the runtime's `no heartbeat for Ns` event detail); status chip, run-card elapsed, event details and the chat list all go through them; ZH by pattern: 刚刚 / N 分钟前 / N 小时前 / N 天前, 等待供应商 · 心跳 …, 最后心跳 …, 已 … 无心跳, 已运行 N 分 S 秒 / N 小时 M 分. EN "Waiting for provider" → "Waiting for the provider"; ZH 等待供应商 (also for the runtime's lowercase event text) | rendered EN+ZH table; a guard that no `+'s ago'` / `p.elapsed + 's elapsed'` remains; `test_run_liveness` vocabulary updated |
| 3 | 生成端 beside 生成者 | 生成者 in `page.py` (2 sites) and `cli/i18n.py` (1); the @-mention parser still accepts 生成端/执行端/审计端 as input aliases | glossary test over `page.py`, `progress.py`, `i18n.py`, `denials_zh.py` (mention-parser lines exempt) |
| 4 | a days-old chat showed 刚刚 | `Thread.recovered(..., updated=)`: a recovered/legacy thread was re-materialised on EVERY snapshot with `updated=now`. The server now passes `last_seen` (newest commit / report / cycle event per chat) into `chats.snapshot`; unknown = 0 = no time shown | `chats.snapshot` dated by `last_seen`, 0 without it; server wiring asserted |
| 5 | review card's "查看问题并决定" did nothing after 稍后处理; "需要你处理" beside "第 1/3 轮 · 通过" | `decisionRowFor(d, cycleId, sha)`: this cycle's row, then the same commit's, then the chat's; the button carries `data-open-decisions="<cycle id>"`; with no open decision it expands the review detail and opens Audits. `pendingDecisionLine`: "Waiting for the provider · round 2" / "Usage limit reached" / "Needs your decision · round N" under the round rows when the pending decision is a provider/usage stop or a later round than the last report (ZH: 等待供应商 · 第 2 轮 …) | rendered: lookup by id / by commit / none; the four line shapes EN+ZH; markup: handler + fallback |

Also: `test_context_condensation_page.py`'s harness pulls in the three time helpers the run card now uses. Everything else untouched.

## Closure fixes (review-closure.md D2 #8 + page.py:3673) — merge `33b52f7` (fusion tip ad1dc0b), commits `8637c90`, `5fd5fa9`

Full suite foreground: `codex-compare/full-suite-console.txt` (green).

- **Guard sentences, enumerated from the emitters.** `ZH_PATTERNS` rebuilt for rework 2: the scope refusal ("… is outside the audited directories (dirs). Only files inside them may change; if the fix needs another file, say so in `notes`."), the binary refusal, the budget caution, the unscreened-files caution ("N staged file(s) were larger than the review can read …"), "the revision changed nothing that could be reviewed", and ONE row `^(\S+) (adds|removes|changes|renames) (.+)$` whose construct table mirrors `repair_guard.ADDED_PATTERNS` / `MARKER_PATTERNS` / `REMOVED_PATTERNS` (strong and weak) and `_BROAD_RERAISE_SENTENCE` — 14 constructs incl. the seven the audit found in English (re-raise, dead branch, shell or make, changes an assert, renames a test, larger-than-review, scope). The "; "-joined event detail splits only at a boundary that begins a guard sentence, so the scope sentence's own semicolon stays inside it. build.py's event texts and the round-numbered termination reason ride the same rows.
- **Gate replaced.** The hand list in `test_console_stop_causes.NEW_COPY` is gone. `tests/test_repair_guard_console_zh.py`: (a) `test_the_triggers_cover_every_construct_the_guard_can_name` — the trigger set must equal the pattern tables' keys, and every table sentence (strong, weak, re-raise) must be produced by driving `screen_code_file` with a real diff; (b) `test_every_sentence_the_guard_emits_reaches_a_chinese_reader` — every sentence from `screen_code_file` / `RepairGuard.assess` (scope, binary, budget, unscreened, nothing), the `emit("repair_refused"|"repair_caution"|"revision_retry", …)` texts read from build.py's AST, the termination template and a joined detail, through the shipped `zhValue`, must be Chinese with no English sentence word left and the path / count / `notes` carried. A new construct in the tables reddens (a) before it can reach a person.
- **审计方 → 审计者** in the evidence-ledger fallback pattern (`page.py`), pinned by `test_the_console_catalogue_never_says_the_retired_word_for_the_auditor`.
- Regions untouched: run card, review card, decision card, wizards. The new pattern rows sit in the guard block of `ZH_PATTERNS` (above the ledger pattern), not near those regions; no dictionary entry was needed.
