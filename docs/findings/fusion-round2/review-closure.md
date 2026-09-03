# Closure audit — fusion line at e0e3b36 (base v5-redesign e87b297)

Independent reviewer. Worktree `scratchpad/wt-closure` (detached e0e3b36), `crossaudit.__file__` confirmed inside it; a second worktree at v5-redesign for the old-receipt comparison. No tracked file left modified (`git status --porcelain` empty after every mutation). Artefacts: `closure-unit-probe.py`, `closure-mutations.log` (26 real-tree mutations, each restored with `git checkout --`).

## Verdict: NOT READY

Three rows are STILL OPEN, one of them makes the suite red at the tip; seven are PARTIAL (acknowledged-but-unchanged or a narrower fix than asked). Every kernel row is CLOSED and the kernel diff is additive.

### Open rows first

| review | item | claimed fix | verification | status | evidence |
|---|---|---|---|---|---|
| console | 12 — render the shipped `openResolution()` under node so a wrong branch shows as a wrong sentence | c92f8c8 added `tests/harness/render_decision.py` + `test_the_decision_center_renders_each_cause_from_the_rows_the_dashboard_builds` | Full suite at e0e3b36: **1 failed, 2467 passed**; the failure is this test, deterministic (3/3 alone), `ReferenceError: currentLocale is not defined` at `openResolution` — f3ba516 (i18n round 2) added `currentLocale==='zh'&&(row.stop_reason_zh\|\|row.why_zh)` to `page.py:4724` and the harness never defined the global. The lead's own `suite-e0e3b36.log` line 132 shows the same failure. The gate that "would have caught defect 1" catches nothing now. | **STILL OPEN** (regressed after the fix) | `tests/harness/render_decision.py` (no `currentLocale`), `src/crossaudit/console/page.py:4724`, `codex-compare/suite-e0e3b36.log:132-133` |
| D2 | 8 — console/i18n copy stale for the new guard contract | c92f8c8 "every caution/refusal sentence of the reworked guard has a ZH pattern" | Drove the sentences the product emits AFTER rework 2 (8b15fee) through the shipped `zhValue` (harness `extract_zh.py`, node): 7 of 12 come back **English** under zh — the scope refusal (`… (experiments). Only files inside them may change; if the fix needs another file, say so in \`notes\`.` — the pattern at `page.py:3643` still expects the rework-1 shape `…; only files … — if the fix…`), `adds a catch-all \`except\` (its handler re-raises)`, `adds code under a branch that never runs (…)`, `adds a shell or make step that ignores its own failure`, `changes an \`assert\` or \`raise\``, `renames a test`, `N staged file(s) were larger than the review can read …`. The gate `test_every_new_sentence_reaches_a_chinese_reader` (`test_console_stop_causes.py:250-285`) pins the OLD strings (`lay beyond the review size limit`, `adds a shell step`, the dash-joined scope sentence) — sentences nothing emits, so it stays green. On the Decision Center the refused-repair `limit-copy` is `row.why` = the guard sentence, so the most common refusal (out-of-scope file) reads English to a Chinese user. | **STILL OPEN** | `page.py:3643-3659` vs `repair_guard.py:169,162,165,190,194,476-477,504`; probe output in this report's session log |
| approx | 4 — a DECISIONS entry closing D141's "±5%" row by reference | held-fixes builder: "No DECISIONS.md entry (lead writes it)" | `grep -n approximately docs/DECISIONS.md` → only D141/D142 (lines 6152, 6167, 6224); D149 (6544-6620) does not mention the rule, the templates or the prompt sentence. | **STILL OPEN** (minor) | `docs/DECISIONS.md` |

### Partial rows

| review | item | claimed fix | verification | status | evidence |
|---|---|---|---|---|---|
| D | 6 — the 512 KB cap hides files from the screens; take the file list from `staged` for scope AND binary | rework 1: "the scope screen uses git's staged list, so the cap can no longer hide a file" | Scope: yes (unit probe: `notes/x.md` refused from the staged list alone). Binary: no — `untrusted_binary` is derived from the parsed diff only (`repair_guard.py:479-480`). Real loop, cap lowered to 4 KB (as the builder's own M12 test does): generator writes a long SUMMARY.md + `experiments/demo/fig 1.png` → **committed**, no `repair_refused`, only the caution `2 staged file(s) were larger than the review can read and were not screened: …fig 1.png`. The docstring's "hard, in every mode" binary refusal is cap-sized; a >512 KB honest document beside a model-written image commits the image. | PARTIAL | `repair_guard.py:479-480, 501-505`; `cli/build.py:934-936` |
| D | 10 — document that a continuation round after a human resumes is unscreened | "documented, not changed" | Documented only in the build report; nothing in `docs/EVIDENCE_AUTHORITY.md` or `cli/build.py` comments (grep `resum\|continuation` → only the tool-loop comment at build.py:716). | PARTIAL (note-only item) | — |
| D2 | 10 — provider-failure paragraph carried into the retry prompt | "pre-existing, untouched" by ruling | Not changed; honestly stated. | PARTIAL (accepted, pre-existing) | — |
| guardname | 6 — private `getfixturedefs` in `guard_doc` | left as is | `test_guards_state_their_reach.py:31-40` still uses `request._fixturemanager.getfixturedefs`; works on pinned pytest 9.1.1. | PARTIAL (accepted, minor) | — |
| i18n | 5 — one vocabulary (审计者/生成者/准入) | 16 CLI replacements + glossary gate; "console twin left to the console owner" | CLI tables: 0 of 审计方/生成方/采信/铸出/转录/补全 (probe over `CATALOGUE`, `ENTRIES`, `SENTENCES_ZH`). `page.py:3673` still renders `证据账本无法出示给审计方：` — a fallback behind `reason_zh` (the entry exists at the seam, so it is effectively unreachable), but round 3's glossary gate (`test_console_round3.py:127`) did not catch it. | PARTIAL (dead fallback carries the retired term) | `page.py:3673` |
| i18n | 7 — dead `--json` check; `_report_untranslated()` to stdout | dead branch removed; stdout "pre-existing, unchanged" | `main.py:1993-2016`: dead branch gone. Under zh the `[i18n]` notice still goes to stdout while the refusal is on stderr. | PARTIAL (half of a minor item) | `main.py:1450, 2016` |
| i18n | coordinator's addition — "the keyless first run, on both surfaces" | `test_a_missing_key_provider_failure_is_chinese_on_both_surfaces` | Real path, `LANG=zh_CN.UTF-8`, no keys: `crossaudit talk hi` → `DENIED (provider): 已配置的所有审计者供应商路由都失败了。anthropic:claude-fable-5 — 未配置 anthropic 凭据 $CROSSAUDIT_AUDITOR_KEY` (Chinese, correct). `crossaudit build "…"` → the loop prints `generator provider failure in round 1: all configured generator provider routes failed. openai:gpt-5 — …` and `Nothing was written and nothing was audited. / To fix: source … or export CROSSAUDIT_GENERATOR_KEY …` — all English: it leaves through `exc.human` (`main.py:1996-2000`), which no seam translates. The table lookup is proven; the surface a person meets on `build` is not. `crossaudit run` with no key does not deny at all (DCL-only verdict, English by D21 per-command design). | PARTIAL | `main.py:1996-2000` |

### Closed rows

| review | item | claimed fix | verification | status | evidence |
|---|---|---|---|---|---|
| A | 1 findings.json never staged | dd9f8b4 | Read both `git add` calls; **mutation** (drop it from `cmd_run`) → `test_the_sidecar_is_committed…` red. Escalate-dial probe through `cmd_run` left `git status` clean. | CLOSED | `main.py:1031-1032, 1712-1713` |
| A | 2 D106 name/body mismatch | dd9f8b4 | Renamed `test_page_markup_declares_no_state_word` (:164); behavioural one at :143. D106 guard green in the full run. | CLOSED | `tests/test_finding_states.py:143,164` |
| A | 3 source-grep guards do not bite | dd9f8b4 | **Re-performed M5** (`render_report` appends `Status: {state}`) and **M6** (overview note → "alleged"): both red on `test_no_user_facing_surface_renders_a_state_word`. | CLOSED | `closure-mutations.log` |
| A | 4 state word reaches the model and prompt digest | dd9f8b4 | `_model_view` projects `state` out (`prompt.py:137-150`); probe: built prompt contains neither `"state"` nor `confirmed`; mutation (json.dumps(dcl)) red. Old receipts unaffected (verify never re-derives the prompt; cross-tree check below). | CLOSED | `prompt.py:137-150, 188` |
| A | 5 `finding_states()` default | dd9f8b4 | Probe: DCL row without key → `confirmed`, model row → `alleged`, artifact `?` for both tiers; `state: bogus` → `ValueError`. | CLOSED | `run.py:70-84` |
| approx | 1/1b/1c contradiction, "quarter of what", 313 example | 6f6b28c | Text read: "not a BLOCKER on its own; a departure so large … materially noncompliant under the next sentence", "a quarter of the stated length", example 320. **Mutation** "never raise it as a BLOCKER" → red. | CLOSED | `constitution.py:105-113` |
| approx | 2 reach on template/init paths | 6f6b28c | Both templates carry the sentence; `auditor/prompt.py:64-67` too (additive). **Mutation** prompt ADVISORY→BLOCKER red; findings doc §2 rewritten. | CLOSED | `scaffold/templates/*.md:18-20/29-30`, `prompt.py:64-67` |
| approx | 3 test guards spelling | 0b7d424 | **Re-performed M6** ("within one twentieth") → `test_the_five_percent_band_is_gone` red. | CLOSED | log |
| guardname | 1 `connect_ex`/UDP/DNS/raw socket overstated | 6a60d09 | conftest patches `connect`, `connect_ex`, `sendto`, `sendmsg`; NOT COVERED names DNS and `_socket.socket`. **Mutations**: guard body no-op → red in 1.06 s; `connect_ex` unpatched → red. | CLOSED | `tests/conftest.py:63-90, 113-116` |
| guardname | 2 remote check hangs 30 s | 6a60d09 | `settimeout(1)` + `pytest.raises`; the no-op mutation failed in 1.06 s total, not via pytest-timeout. | CLOSED | `test_guards_state_their_reach.py:108-119` |
| guardname | 3 thread exception + leaked socket | 6a60d09 | Main-thread `accept()`, every socket closed; the two guard files run under `-W error`: 13 guard tests pass, 0 warnings (the one `-W error` trip is a pre-existing sqlite `ResourceWarning` in `test_console_strings_by_execution.py`, not this item). | CLOSED | `:145-163` |
| guardname | 4 name test is a literal | 6a60d09 | Uses `request.fixturenames`. | CLOSED | `:55-67` |
| guardname | 5 non-canonical loopback | 6a60d09 | `_is_local` via `ipaddress.is_loopback`; test at :180. | CLOSED | `conftest.py:22-31` |
| guardname | hermeticity of `test_console_strings_by_execution` | 6a60d09 | `github_status` monkeypatched (builder's gh-shim logs before/after in codex-compare). Read only. | CLOSED | `gh-calls-held-fixes.log.before` |
| B | 1 dead `not confirmed_blockers`, false mutation claim | ae00a1c | Conjunct removed, invariant stated; **mutation** drop `model_decided` → `test_escalate_dial_does_not_touch_a_deterministic_block` red. Default-dial identity re-proven over 11 ladder paths; `escalate` flips only `model_BLOCKED`. | CLOSED | `authority.py:240-247` |
| B | 2 `decision_id` never re-derived | ae00a1c | `_decision_payload` shared; **tamper matrix re-performed** on a real block: advisory→blocking, advisory→contested, duplicated id, replaced decision_id, replaced rationale, flipped dial, smuggled key, edited claim, flipped route — 9/9 caught with distinct messages. | CLOSED | `authority.py:99-117, 394-406` |
| B | 3 `workflow_verdict == audit.verdict` untested | ae00a1c | **Mutation** `if False` → `test_the_block_verdict_is_bound_to_the_audit_verdict` red. | CLOSED | `schema.py:158-161` |
| B | 4 unreachable `admit()` route branch | ae00a1c | Deleted; comment says why. | CLOSED | `verify.py:582-585` |
| B | 5 integrity constants in printed sentences | ae00a1c | `INTEGRITY_IN_WORDS`; grid 7 integrities × 4 verdicts × 8 flag combos × 3 record sets × 2 dials → 0 sentences carry a code/route/state/id; unstarted+PROVIDER_FAILURE says both. Real `cmd_run`: `Escalated: The only block rests on a model reading without reproduced evidence…`. **Mutation** code back → red. | CLOSED | `authority.py:69-78, 286-331` |
| B | 6 unbounded `claim` | ae00a1c | 3 MB observation → claim 400 chars, `claim_sha256` = sha256(full), block 1,369 bytes. | CLOSED | `authority.py:64, 213-214` |
| B | 7 `evidence_id` not unique | ae00a1c | Two identical findings → two ids; `validate_block` refuses repeats. | CLOSED | `authority.py:173-177, 373-375` |
| B | 8 `authority={}` unpinned | ae00a1c | **Mutation** `is not None` → `[absent1]` cell red. | CLOSED | `build.py:259` |
| B | 9 report/UX batch | ae00a1c + 94f0f12 | No `evidence policy` row; route row is `ROUTE_LABELS` plain words and `verify` maps back (`ROUTE_FROM_LABEL`, unknown label refused); column "verified by a check"; DCL_ONLY once (test); ZH for the escalate sentence rendered by shipped `zhValue` (probe). | CLOSED | `run.py:153-158, 204-218`, `verify.py:463-477` |
| D | 1 retry prompt loses the finding | a0d7270 | Read `build.py:953-955`; real loop (fig 1.png refusal): round-3 prompt contains both the DCL blocker and the refusal; **mutation** `findings = refusal` → red. | CLOSED | `build.py:953-955` |
| D | 2 scope refuses honest multi-file repairs | a0d7270 (contract change: scope = `scope.dirs`) | Probe: SUMMARY.md/calc.py/helper edits inside `experiments` all allowed; `_blocker_scope` deleted. | CLOSED | `repair_guard.py:98-114` |
| D | 3 word-list patterns redden honest code | a0d7270 | Re-performed H3, H4, H5, H12, H13, H14, H16, H22, H23, H24 → all allowed, zero cautions. | CLOSED | probe |
| D | 4 data files budgeted as code | a0d7270 | `DATA_SUFFIXES`; H15 (300-line results.json) clean. | CLOSED | `repair_guard.py:69-72` |
| D | 5 trivial evasions; name the guard for what it does | a0d7270 | E1, E2, E5, E6, E7, E9, E10 (incl. two-line), E11, E12 → cautions; docstring and `GENERATOR_SYSTEM` say heuristic, list non-claims. | CLOSED | `repair_guard.py:1-50`, `generator.py:43-45` |
| D | 7 M9/M12 untested | c82d5f0 | **Mutation** `locally_rendered = set()` → red; cap test present and exercised. | CLOSED | `test_build_repair_guard.py:247, 281` |
| D | 8 console copy for `repair_refused`, ZH | 53c83df/c92f8c8 | Decision Center branch present; superseded by D2#8 above for the rework-2 sentences. | CLOSED (for the rework-1 strings) | `page.py:4699-4712` |
| D | 9 generator prompt weight | a0d7270 | System bullet no longer says "smallest"; only the findings block does. | CLOSED | `generator.py:43-45, 444` |
| D2 | 1 non-ASCII filename hard-refused | 8b15fee | `_staged_paths` = `--name-only -z`; real loop: `experiments/demo/报告.md` committed, no refusal; direct: staged `图 2.png` returned unquoted; `unquote_path` decodes octal; **mutation** raw unquote → red. | CLOSED | `build.py:332-340`, `repair_guard.py:236-244` |
| D2 | 2 `./experiments` refuses everything | 8b15fee | `in_scope` true for `./experiments`, `experiments/`, `experiments/./demo`, `experiments//demo`; N11 loop-equivalent clean; **mutation** normalise dropped → red. | CLOSED | `repair_guard.py:92-114` |
| D2 | 3 `fig 1.png` bypasses the binary screen | 8b15fee | Real loop: refused with the binary sentence, not in `git log`; header parse of `a/fig 1.png b/fig 1.png` → refused. (Cap variant: see D#6.) | CLOSED | `repair_guard.py:247-264` |
| D2 | 4 false caution sentences | 8b15fee | N1/N2 → "(its handler re-raises)"; N4/N5 → "changes an `assert` or `raise`"; N8 → "renames a test". | CLOSED | `repair_guard.py:169, 186-195, 352-368` |
| D2 | 5 doctest lines redden | 8b15fee | N7 → clean. | CLOSED | `:120, 371-391` |
| D2 | 6 pattern alternatives without a biting test | 8b15fee | **Re-performed R1** (`}` dropped), **R5** (`pragma`), **R10** (unquote) → each red. | CLOSED | log |
| D2 | 7 cheap evasions silent | 8b15fee | X1 dead_branch, X3 importorskip, X10 `.pyx`, X11 `\|\| exit 0`, X15 Makefile `-` → cautions. | CLOSED | `repair_guard.py:62-63, 157-165` |
| D2 | 9 apply-side denial drops the findings | 8b15fee | `audit_findings` prepended on the `generation_refused` path; docs name `apply` as the first line. | CLOSED | `build.py:804`, `EVIDENCE_AUTHORITY.md:100-104` |
| console | 1 wrong cause on every ESCALATE | c92f8c8 | `authority_contested` field; `_is_auditor_concern` never reads the route; **mutation** route-derived → `test_a_plain_escalate_keeps_the_generic_copy` red (whole file, not `-x`). | CLOSED | `overview.py:134, 315, 435-443` |
| console | 2 route-first claim unguarded | c92f8c8 | Receipt-only test records `escalation_reason=""`; **M13 re-performed** → `test_the_escalate_dial_stop_is_named_from_the_receipts_contested_ids` red. | CLOSED | `test_console_stop_causes.py:140-155` |
| console | 3 "refused twice" | c92f8c8 | No "twice"/"两次" in the shipped EN/ZH summary. | CLOSED | `page.py:3296, 4708` |
| console | 4 auditor prose through the sentence seam | c92f8c8 | Only `rationale[0]` is translated; literal via `t("run.human_decision_needed")` (en/zh entries); **mutation** → red. | CLOSED | `main.py:1775-1782`, `i18n.py:172, 364` |
| console | 5 unnamed `<select>`; guard blind to selects | c92f8c8 | `aria-label="Provider"`; **mutations** new unnamed static select / vendor select unnamed → both red. | CLOSED | `page.py:4504`, `test_console_input_names.py:23` |
| console | 6 ZH terminology drift | c92f8c8 | Reopen copy reuses 解锁额外一轮受审计执行. | CLOSED | `page.py:3299` |
| console | 7 "Dispute" names a missing action | c92f8c8 | `requested` names Revise-with-a-reason or Stop; no 提出争议 in page.py. | CLOSED | `overview.py:487-492` |
| console | 8 ZH wording | c92f8c8 | 正在要求生成者做出不超出已审计文件范围的修复. | CLOSED | `page.py:3301` |
| console | 9 console imports the CLI | c92f8c8 | Constant in `errors.py`; overview imports errors. | CLOSED | `errors.py:213`, `overview.py:24` |
| console | 10 private `_receipt_authority` | c92f8c8 | Public name + alias; streams uses the public one. | CLOSED | `overview.py:161, 178`, `streams.py:25` |
| console | 11 `reason_zh` on every refusal — document | c92f8c8 | Comment says additive/absent-when-no-entry. | CLOSED | `server.py:1066-1073` |
| i18n | 1 Chinese DENIED line unreachable | 1957cfb | `main()`'s Denial branch resolves the language; **real path** (`LANG=zh_CN.UTF-8`, fresh subprocess): `run` on a `version: 2` config → `DENIED (config): 不支持的配置版本 2（应为 1）`, `verify nope.json` → `DENIED (integrity): 收据无法读取：[Errno 2] …`, `talk` → Chinese provider denial; `LANG=en_US.UTF-8` byte-identical English. **Mutation** drop `set_language` → red. | CLOSED | `main.py:2013-2014` |
| i18n | 2 subclasses/composed reasons unread (63 %) | d6f068d/e796d78 | Reader walks the hierarchy; **re-performed M3** (untranslated `ToolError` in `broker/registry.py`) → gate red. | CLOSED | `test_denial_strings_are_legible.py:316-357` |
| i18n | 3 half-translations through generic templates | d6f068d | `denial_zh`: `Connect Anthropic subscription…` → …连接 Anthropic 订阅; `Connect OpenAI API key…` → …OpenAI 的 API key; capability token → 能力令牌必须是映射; scratch directory → 临时目录…. | CLOSED | `denials_zh.py:1037, 1075` |
| i18n | 4 corrections table (15 rows) | d6f068d | 14 rows driven through `denial_zh` match the proposed text verbatim; row 6 read at `denials_zh.py:276` (受限修订). | CLOSED | probe |
| i18n | 6 report count | d6f068d | `ENTRIES` = 741 distinct, as the builder's round-2 report says. | CLOSED | `denials_zh.py` |

### Closure guards re-run (all pass)

| guard | result |
|---|---|
| NUL-separated staged paths via the real build loop | `报告.md` committed without refusal; `fig 1.png` refused, rolled back, absent from `git log`; `_staged_paths` returns `experiments/demo/图 2.png` unquoted |
| escalate-dial round-1 stop | real `cmd_run` with `lone_model_blocker: escalate` + replay BLOCKED: exit 11, cycle ESCALATED at round 1, `escalation_reason` == `CONTESTED_MODEL_BLOCKER_REASON`, kind `audit`; receipt carries route `human-decision` + 1 contested id; `crossaudit verify` exit 0 |
| old receipt (no authority block) byte-identical | fixed-input PASS receipt built at v5-redesign and at e0e3b36: identical key paths; every differing value is a per-run sha/id, `verifier.version` 4.15.0→4.16.0 or `verifier.code_digest_sha256`; `verify()` evidence identical (verified, admission_ready, no shortfalls) |
| `verify --admit` with a tampered DSSE signature | `SIGNATURE INVALID  the receipt or its signature was altered; refusing to admit`, exit **21**, no traceback |
| `crossaudit run` under `LANG=zh_CN.UTF-8`, no provider key | no DENIED at all by design (DCL-only verdict); the DENIED path itself is Chinese (`version: 2` config, `verify`, `talk` — table above) |
| `ruff check --select E9,F63,F7,F82 src tests` | All checks passed |
| full suite, foreground | **1 failed, 2467 passed, 2 skipped, 1 warning in 344.9 s** — the failure is the console render gate (open row 1) |

### Kernel diff judgment (`git diff v5-redesign e0e3b36 -- auditor broker ledger policy dcl`)

`broker/`, `ledger/`, `policy/`: **no diff**. `dcl/framework.py`: +22, purely additive (six state constants, `Finding.state` trailing default). `auditor/authority.py`: new file. `auditor/__init__.py`: exports added. Removed non-comment lines, each judged:

- `prompt.py:64` — `missed or substituted requirement is a BLOCKER under CA-TASK-001. The task may \` → same clause kept, two sentences inserted (approximate length is ADVISORY / only a fraction or multiple is noncompliant). Narrows one model-facing reading that the owner ruled a false positive (D141/D142); no deterministic check touched. Not a weakening.
- `prompt.py:188` — `json.dumps(dcl, …)` → `json.dumps(_model_view(dcl), …)`: only the `state` key is projected out of what the model sees; every finding, note and count still goes. Changes `prompt_sha256` for new receipts only; verify never re-derives it (cross-tree check above).
- `run.py:26` — `from dataclasses import dataclass` → `… dataclass, field` (additive).
- `run.py:140, 153, 356, 360-362` — signature/kwarg plumbing for `authority`; the `lines = [ … ]` literal split so the route row can be appended.
- `run.py:336-350` — **the one semantic line**: `verdict = decision.workflow_verdict` after the ladder. Under the default dial `decide_authority` is the identity (re-proven over 11 ladder paths, `contested_evidence_ids == ()`); the only flip is opt-in `escalate` on a model-decided BLOCKED, which moves *toward* a person, never toward PASS. `decide_authority` can raise `ValueError` on an unknown dial/verdict, but the dial is validated at config load and the verdict comes from the ladder's fixed set. Not a weakening.
- `receipt/build.py:176` — `integrity: str = "OK") -> dict:` → adds `authority: dict | None = None`; block written only when truthy. `receipt/schema.py`, `receipt/verify.py`: additions only (`admit()`'s route branch was added and removed inside the fusion line; net zero).

Nothing was removed from a check, a bound, a digest, a refusal or a verdict path.

### Counts

- Rows: 63 numbered review items + 7 closure guards = 70. **CLOSED 53**, **PARTIAL 7**, **STILL OPEN 3**.
- Re-performed without trusting the builder's test: 26 real-tree mutations (26 red, 1 skipped on an ambiguous anchor and verified by reading), 9-cell tamper matrix, 11-path dial identity, 22 honest + 22 evasion guard cases, 4 real-loop runs, 6 real-path CLI invocations under zh, 1 cross-tree receipt comparison.
- Suite: 1 failed / 2467 passed at e0e3b36 (also in the lead's own log).

### What READY needs

1. Define `currentLocale` in `tests/harness/render_decision.py`'s shim (and render each cause under both values) — the suite goes green and the review-12 gate bites again.
2. Replace the rework-1 guard sentences in `page.py`'s `ZH_PATTERNS` (3643-3659) with the rework-2 set from `repair_guard.py` (scope sentence with `). Only files … ;`, re-raise, dead branch, "shell or make step", "changes an `assert` or `raise`", "renames a test", "were larger than the review can read"), and make `NEW_COPY` in `test_console_stop_causes.py` import the sentences from `repair_guard.py` instead of quoting them, so the gate cannot pin a string nobody emits again.
3. One D-entry paragraph for the "approximately" change (D141 row closed by reference).
4. Worth deciding, not blocking: derive `untrusted_binary` from `git diff --cached --numstat -z` (or the staged list) so the binary refusal is not cap-sized; translate or route `exc.human` on the `build` keyless path; drop `审计方` from `page.py:3673`.
