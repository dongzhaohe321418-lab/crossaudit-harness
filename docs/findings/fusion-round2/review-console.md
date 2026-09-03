# Review — console slice (53c83df c5ad655 815a063 94f0f12 a91108e), merge ebdba80

Worktree: detached at `ebdba80`, `crossaudit.__file__` confirmed inside it. Reviewer did not write this change.

## Verdict: NEEDS CHANGES

Full suite green (2337 passed, 2 skipped, 393 s) and every builder mutation reproduces, but the main decision surface can show a wrong cause, one summary sentence states a count that is not always true, the a11y guard has a hole with a shipped instance in it, and the CLI seam marks the auditor's own words as an untranslated string.

### Defects (numbered, actionable)

1. **Wrong cause on the Decision Center for any non-dial ESCALATE.** `src/crossaudit/console/overview.py:424-431` (`_is_auditor_concern`) derives `auditor_concern` from `latest.authority_route == "human-decision"`. But `ROUTE_FOR_VERDICT["ESCALATE"] == "human-decision"` for EVERY escalate (`auditor/authority.py:41-46`): the auditor's own ESCALATE verdict, the escalation lock, PROMPT_TRUNCATED / INVALID_REPLY / NOTHING_AUDITED / fixture integrity stops. `cli/main.py:863-868` only mints the dial sentence when `route == "human-decision" AND contested_evidence_ids`. Rendered (below, "ADVERSARIAL_plain_escalate"): flag "The auditor raised a concern", summary "The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites…" beside "What happened: the automatic audit loop stopped" — false and self-contradicting, in both languages. **Fix:** add `Cycle.authority_contested: bool = False` set from `bool(authority.get("contested_evidence_ids"))` in `read_cycles`, and test `latest.authority_contested` (not the route) in `_is_auditor_concern`; add a test: ESCALATE round + receipt with `contested_evidence_ids: []` + default reason → `cause == ""`.

2. **The route-first claim is not guarded.** Mutation M13 (route branch deleted, only the sentence-equality fallback left) is GREEN: `tests/test_console_stop_causes.py:88-101` sets `escalation_reason=CONTESTED_MODEL_BLOCKER_REASON` in the same fixture, so the test cannot tell which source named the cause. **Fix:** in that test record the verdict with `escalation_reason=""` (the receipt alone must name it); keep the sentence-only case in the separate test.

3. **"refused twice" is not always true.** `page.py` summary (`openResolution`, "The generator’s revision was refused twice…" / ZH "已两次被拒绝") and the ZH title. `cli/build.py:964`: `if repair_refusal_used or round_no == cfg.max_rounds` — a single refusal on the final round also stops with `cause="repair_refused"`. **Fix:** drop the count: "The generator’s revision was refused: instead of repairing the cause, it tried to make the finding disappear, changed files the audit did not name, or grew larger than an automatic repair may be. The refused attempt was rolled back, so the audited files are unchanged and nothing was admitted." ZH: "生成者的修订被拒绝：它没有修复根源，而是试图让问题消失、改动了审计未提及的文件，或超出了自动修复允许的规模。被拒绝的尝试已回滚，因此已审计的文件未被改动，也没有任何结果被准入。"

4. **`cli/main.py:1766-1771` (a91108e) pushes authored text through the sentence seam.** `why = outcome.invalid_reason or rationale[0] or "a human decision is needed"` then `i18n.sentence_text(why)`. Under zh: `Escalated: [en] The auditor replied with prose instead of the JSON schema` and `i18n.fallbacks()` records `sentence:<the auditor's prose>` — the end-of-run notice then names the auditor's own words as OUR missing catalogue entry (D130 boundary). The literal fallback "a human decision is needed" has no entry either (`[en] a human decision is needed`). Verified: `sentence_text('The auditor replied with prose…')` → `'[en] The auditor replied…'`, fallbacks `('sentence:The auditor replied…', 'sentence:a human decision is needed')`. **Fix:** translate only the rationale slot: `why = outcome.invalid_reason or (i18n.sentence_text(rationale[0]) if rationale else i18n.t("a human decision is needed"))`, with the literal added to the catalogue. `cmd_audit:1054` is already correct (the `elif` excludes invalid_reason). Otherwise the two-line change is safe: `sentence_text` is verbatim under en, `--json` untouched.

5. **Unnamed `<select>` shipped, and the a11y guard cannot see selects.** `page.py` `renderFallbacks` (file line ~4461): `<select data-fallback-vendor>` has no aria-label/label (options do not name a select). `tests/test_console_input_names.py` covers only `input`/`textarea`; mutation M5 (a new unnamed static `<select>`) is GREEN. Static `<select>`s (24) and all `<button>`s are named. **Fix:** `aria-label="Provider"` (catalogue key exists) on the vendor select, and add `"select"` to both `_Fields` and the JS-built regex in the test.

6. **ZH terminology drift for the same EN phrase.** "unlock one additional audited round": existing entry `解锁额外一轮受审计执行`, new entry `然后解锁再一轮受审计尝试`. **Fix:** reuse the existing phrase: "指出文件以及能修复根源的最小改动，然后解锁额外一轮受审计执行。"

7. **Recommendation names an action the dialog does not offer.** EN "Dispute a misreading, reopen with a recorded reason, or stop without admission." / ZH "若属误读可提出争议…" — the Decision Center has Revise and Stop only (builder deviation 3). "Dispute" reads as a third button and "提出争议" as a formal dispute flow. **Fix:** EN "Review the auditor's concern and its evidence. If it is a misreading, say so in your reason and continue; if it is right, tell the generator how to address it; or stop without admitting the work." ZH "请审查审计者的疑虑及其证据。若属误读，请在理由中说明后继续；若疑虑成立，请告诉生成者如何处理；也可停止任务且不准入其输出。"

8. **ZH wording.** "asking for a smaller repair that fixes the cause" → `正在要求一次更小、能修复根源的修复` ("修复…的修复" is clumsy). Better: `正在要求生成者做出更小、能修复根源的改动`.

9. **Console imports the CLI.** `overview.py:430` lazily imports `crossaudit.cli.main` inside `_is_auditor_concern` (runs on every `escalations()` poll that is not already route-matched; cached after first import, but a console→CLI dependency for one constant). **Fix:** move `CONTESTED_MODEL_BLOCKER_REASON` to `errors.py` beside `_BUDGET_REASON_MARKER`; import it in both.

10. Minor: `streams.py:24` imports the private `_receipt_authority`; make it public. `annotate_findings` rule-only fallback annotates every same-rule finding with the single record (edge; note only).

11. Note (not a defect): `server._deny` adds `reason_zh` to EVERY structured JSON refusal regardless of locale — the EN API body gains a key; `reason` is byte-identical; the CLI `--json` path has no `reason_zh`. Document it as additive.

12. Test-design gap: `openResolution` behaviour for both causes is asserted by string presence only (`test_the_page_keys_both_causes_on_the_structured_field`); a node render of the shipped function (as `test_decision_center_a11y.py` already does, harness at `scratchpad/render_dc.py`) would have caught defect 1.

### Checklist findings

1. Cause derivation reads the receipt's structured `authority.route` (`_receipt_authority`, `Cycle.authority_route`) and an exact-equality fallback on the CLI's constant; no regex over prose. But the route is the wrong field (defect 1).
2. Tier sentence: `findingTier(f)` appears exactly in `turn()` (Audits view) and `reviewCard()` (review detail); absent from `runCard`, the Decision Center issues list and the pipeline Verdict detail. Rendered HTML for a receipt carrying `confirmed`/`alleged` records and route `human-decision`: only the three fixed sentences and the class `verified`; grep for alleged/confirmed/bounded-revision/human-decision/automatic-repair/obtain-audit/withdrawn/overridden/unresolved → all absent. `_strings` walks dataclasses, so a copied state or route in a finding dict is caught (M8, M9 red).
3. Accessibility: static — 0 unnamed input/textarea/select/button; JS-built — one unnamed `<select data-fallback-vendor>` (defect 5). Composer, hub search, doctor name/email, model-ID inputs named. M4/M6/M7 red, M5 green.
4. Denial seam keyed by `why.reason` (the Denial's own field) → `i18n.denial_zh` exact-then-template; `reason_zh` absent when no entry; page `denialText` falls back to `reason` (never undefined/empty: `||data.reason||''`). M1/M2/M3 red. Gate `test_every_denial_reason_reaches_the_console_in_chinese` measures the seam, not the wire (the builder says so) — the wire test is what catches M1/M2.
5. `cli/main.py`: see defect 4.
6. Counts below.

### Rendered Decision Center (shipped `openResolution()` under node; ZH = `zhValue` per slot, as the locale observer does)

```
===== repair_refused EN
flag                 Automatic repair refused
title                The revision did not repair the cause
summary              The generator’s revision was refused twice: instead of repairing the cause, it tried to make the finding disappear, changed files the audit did not name, or grew larger than an automatic repair may be. Each attempt was rolled back, so the audited files are unchanged and nothing was admitted.
limit-title          Why the last revision was refused
limit-copy           src/x.py adds a catch-all `except` that swallows every error
request              Tell the generator the smallest change that repairs the cause, or stop the task without admitting its output.
reopen-title         Revise and continue
reopen-copy          Name the file and the smallest change that repairs the cause, then unlock one additional audited round.
issues               BLOCKER CA-TXT-001 The summary states 0.052 while the data records 0.044. Affects work/a.md
===== repair_refused ZH
flag                 自动修复被拒绝
title                修订没有修复问题的根源
summary              生成者的修订已两次被拒绝：它没有修复根源，而是试图让问题消失、改动了审计未提及的文件，或超出了自动修复允许的规模。每次尝试都已回滚，因此已审计的文件未被改动，也没有任何结果被准入。
limit-title          上一次修订被拒绝的原因
limit-copy           src/x.py 新增了会吞掉所有错误的 catch-all `except`
request              请告诉生成者能修复根源的最小改动，或停止任务且不准入其输出。
reopen-title         修订并继续
reopen-copy          指出文件以及能修复根源的最小改动，然后解锁再一轮受审计尝试。
===== auditor_concern (escalate dial, contested ids present) EN
flag                 The auditor raised a concern
title                The audit needs your decision
summary              The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.
limit-title          What happened
limit-copy           the auditor raised a concern that no deterministic check reproduces; it needs your judgment
request              Review the auditor's concern and its evidence. Dispute a misreading, reopen with a recorded reason, or stop without admission.
reopen-title         Revise and continue
reopen-copy          If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded.
issues               BLOCKER CA-TXT-001 The summary states 0.052 while the data records 0.044. Affects work/a.md
===== auditor_concern ZH
flag                 审计者提出了一项疑虑
title                审计需要你作出决定
summary              审计者依据自身判读阻断了本轮；没有任何确定性检查能复现这项疑虑。CrossAudit 不允许仅凭模型的说法驱动自动改写，因此已停止并保持文件不变。
limit-title          发生了什么
limit-copy           审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断
request              请审查审计者的疑虑及其证据。若属误读可提出争议，也可记录理由后重开，或停止且不准入。
reopen-title         修订并继续
reopen-copy          如果疑虑成立，请告诉生成者如何处理；如果属于误读，请在此说明，你的理由会被记录。
===== ADVERSARIAL_plain_escalate (auditor's own ESCALATE, contested [], default reason) EN  <-- defect 1
flag                 The auditor raised a concern
title                The audit needs your decision
summary              The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.
limit-title          What happened
limit-copy           the automatic audit loop stopped
request              Review the auditor's concern and its evidence. Dispute a misreading, reopen with a recorded reason, or stop without admission.
issues               No structured findings were recorded. Review the stop reason above before continuing.
===== ADVERSARIAL_plain_escalate ZH
flag                 审计者提出了一项疑虑
summary              审计者依据自身判读阻断了本轮；没有任何确定性检查能复现这项疑虑。CrossAudit 不允许仅凭模型的说法驱动自动改写，因此已停止并保持文件不变。
limit-copy           自动审计循环已停止
issues               未记录结构化问题。继续前请检查上方的停止原因。
(ADVERSARIAL_truncated_prompt — integrity stop with a finding — renders the same wrong flag/summary.)
```
Full output: `scratchpad/decision-render-review.txt`; harness `scratchpad/render_dc.py`; rows `scratchpad/rows.json`.

Tier sentences rendered (review detail / Audits): `Verified by a deterministic check` · `Raised by the auditor, not yet reproduced` · `Raised by the auditor and verified` / `已由确定性检查验证` · `由审计者提出，尚未被复现` · `由审计者提出，并已验证` — plain, consistent, no route or state word.

### Mutation log (each applied, targeted tests run, reverted with `git checkout --`)

```
M1 drop reason_zh attach (server._deny)                 RED   test_the_console_serves_the_refusal_in_both_languages_on_the_wire
M2 wrong key: denial_zh(why.kind)                        RED   same wire test (reason_zh != denial_zh(reason))
M3 page ignores reason_zh                                RED   test_the_page_prefers_the_served_chinese… (string assertion)
M4 composer aria-label removed                           RED   test_every_static_field_has_an_accessible_name
M5 new unnamed static <select>                           GREEN <-- gap (defect 5)
M6 new unnamed static <input>                            RED
M7 new unnamed JS-built <input> in fallback row          RED   test_every_field_javascript_builds_has_an_accessible_name
M8 annotate_findings copies `state`                      RED   test_no_dashboard_surface_carries_a_route_name_or_a_state_word
M9 annotate_findings copies `route`                      RED   same
M10 auditor_concern derivation removed                   RED   test_the_escalate_dial_stop_is_named_from_the_receipt_route
M11 repair_refused leads with wrapper, not `why`         RED   (string assertion only)
M12 tier sentence dropped from reviewCard                RED   test_the_page_names_the_tier_in_a_sentence_and_never_a_route
M13 route branch removed, sentence fallback kept         GREEN <-- gap (defect 2)
```
Tree clean after the run (`git status --short` empty).

### Counts
- Gate files (finding_states, denial_strings, translation_boundary, console_stop_causes, console_input_names, decision_center_a11y, authority_sentences, cli_i18n, admission_and_console, projects_ui, guard_names, overview): **237 passed**, 44.7 s.
- Full suite, foreground: **2337 passed, 2 skipped, 1 warning in 393.6 s** (`scratchpad/full-suite-review-console.txt`). Matches the builder's 2337/2.
