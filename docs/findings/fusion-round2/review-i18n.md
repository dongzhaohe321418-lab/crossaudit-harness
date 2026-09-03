# review-i18n — independent review of fusion/i18n-denials (+ 94f0f12 SENTENCES_ZH)

Reviewed at merge `ebdba80` in a detached worktree; base for byte-identity `f050cbd`.
Branch commits: `f769e65` table, `054d847` CLI seam, `9ccf21c` gate. `crossaudit.__file__` confirmed inside the worktree.

## Verdict: NEEDS CHANGES

1. **The Chinese DENIED line is unreachable from the default CLI flow.** `i18n.denial_text()` serves Chinese only when `_language == "zh"`, and the language is set only by `_speak()`, which only `cmd_init` and `cmd_doctor` call. Measured: 44 probe commands over two broken configs and a real project under `LC_ALL=LANG=zh_CN.UTF-8` produced 13 `DENIED (…)` lines (`run`, `check`, `verify`, `watch`, `build`, `talk`, `amend`, `pair`, `verify --admit`) — **all 13 in English, zero `[en]` marks, zero `[i18n]` notices**. `init`/`doctor` never reach the `DENIED` branch in those scenarios (they print their own report). So the seam the commit message and `main.py` comment describe ("served in the language the command was asked for") is dormant for every command a person actually hits a refusal on; `test_the_cli_denied_line_speaks_chinese_after_its_parsed_prefix` passes only because its fake command calls `i18n.set_language("zh")` itself. Fix: resolve the refusal's language in the `except Denial` branch (`--lang` → `from_environment()` → en). A refusal is one sentence, so D21's half-translated-wizard argument does not apply to it; the builder's own comment ("a refusal is the string that most needs translating") argues the same. Or, if the per-command policy must stand, say so in the report and the test — the console (server `_deny` → `reason_zh`) is then the only surface where the 538 are reachable.

2. **"538/540" is the static reader's universe, not what a person meets.** Driving the suite's real Denials (625 raised, 424 distinct reasons, via a pytest plugin patching `Denial.__init__`): **269 resolve through `denial_zh`, 155 do not** (63%). Of the 155, ~120 are shipped product sentences located in `src/` (35 are test fixtures like `boom`, `nope`, `stop after stream probe`). The reader misses them because they are raised via subclasses it does not know — `ToolError` (broker/registry), `TokenError` (policy/tokens), `LedgerError` (ledger/chain), `SSHFailure` (hpc), **62 raise sites** — or through a variable/composed reason (`ConfigDenial(why)`, `ProviderDenial(reason, …)`, `%`/`.format`, 9+ sites). Untranslated at runtime include: `path '{}' is outside the grant`, `'{}' is not in the committed tree`, `old_string was not found; …`, `content exceeds the {}-byte write limit`, `unknown token fields: {}`, `provider returned HTTP 4xx\n  it said: …` (18 variants), `Local usage guardrail paused provider calls. …`, `gh repo create failed: …` (4), `commit refused: the staged changes appear to contain a private key block…`, `the evidence ledger has an incomplete final entry (a crash left a torn tail)…`, `authority block does not validate: …`, `the selected PASS is not ready for admission: …`, `refusing two generated paths for one physical file…` (21 in file_identity.py), `web_fetch needs a plain public https:// URL…`, `The saved SSH host key changed…`, `CrossAudit could not read its saved connection settings — unlock the login Keychain and retry.`. **Mutation 3** (below): an untranslated `ToolError("…")` added to `src/` leaves the gate green. Fix: add the four subclasses to `DENIAL_TYPES`, list the composed sites in `RAISED_BEHIND_THE_READER`, re-measure, translate the new residual.

3. **Half-translations at runtime through generic templates** (the exact defect the `_compile` comment warns about, on the Chinese side): `Connect {} {} in Settings…` renders `创建此项目前，请先在设置中连接 Anthropic subscription` / `…Openai API key` (the second slot is our own conditional literal, not user text); `{} must be a mapping` swallows `a capability token must be a mapping` → `a capability token 必须是映射`; `{} must be an absolute normalized POSIX path` swallows `scratch directory …` (hpc.py:99 `{label}`) → `scratch directory 必须是…`; `{} does not advertise {} for {}` renders `Auditor 没有为 gpt-5 提供 'high'` (role label is ours). Fix with specific entries placed before the generic ones, as already done for pair.py's `{where}`.

4. **Copy defects** — see the corrections table (13 rows, 2 glossary-wide).

5. **Vocabulary conflict inside the CLI.** The existing CLI catalogue (`i18n.CATALOGUE["zh"]`, doctor/init) says 审计方 (7) / 生成方 (5) / 采信 (4) for auditor / generator / admit; this table and the console say 审计者 / 生成者 / 准入. Under `crossaudit doctor --lang zh` a person can now read both in one session. The builder's report lists 生成者/审计者 as "the glossary followed" — true of the console, not of the CLI file the table lives next to. Pick one for the CLI (the console's, by weight: 79/37/35 uses) and retire the other; at minimum the D130 entry inside this very table (`审计方`) must agree with its 540 neighbours (`审计者`).

6. **Report accuracy.** Builder report says 543 entries; the branch tip has **538**, the merge **541** (94f0f12 replaced one entry and added others). Counts elsewhere reproduce.

7. Minor: in the `DENIED` branch the `if not getattr(args, "json", False)` is dead (`--json` returned in the first branch); `_report_untranslated()` prints to **stdout** while the refusal is on stderr, so under zh a fallback notice lands on the machine-readable stream (harmless for the Swift shell, which ignores non-`CROSSAUDIT_APP_URL=` stdout lines, but inconsistent). Pre-existing, not this branch: `crossaudit check` in a project with no `scope.dirs` crashes with `TypeError: 'NoneType' object is not subscriptable` (main.py `cmd_check`, base too).

## What is right

- Mechanism is provenance-first (D130): lookup is applied to `Denial.reason` only; user text is never matched. Exact-then-template, most-specific-first ordering is correct and tested (`entry answered by itself`).
- Placeholder safety: script over all 541 entries — 0 count mismatches, 0 stray braces, 0 mixed `{}`/`{n}`; 222 templated entries; 3 reorder with `{n}` (both `no {} found …`, `does not advertise`), all correct. Five real reasons driven through `denial_zh` fill correctly (`{}s` → `{} 秒` included); runtime values (paths, `[Errno 2] …`, shas, lists) are carried through.
- EN output byte-identical to `f050cbd`: 44 commands × (stdout, stderr, exit code) identical after masking the per-run commit sha and worktree path in one traceback; 13 DENIED lines identical; `--json` bodies identical base↔new and en↔zh.
- Swift parse (`CrossAuditApp.swift:316`): `hasPrefix("DENIED (")` + first `"): "` — a Chinese sentence after the prefix is returned whole; no entry contains a newline or an ASCII `): `; the `[i18n]` line goes to stdout, not the log, so the reversed scan is unaffected. (The app launches the core with the GUI environment, which carries no `LANG`, so the launch denial stays English regardless — consistent with finding 1.)
- SENTENCES_ZH (94f0f12): 22 pairs, all accurate and natural; clause-slot recursion (`_sentence_slot`) works; `受限修订` for "bounded revision" is the better rendering (see row 6 below).

## Translation sample (60) — grades

Read all 541 once. A = accurate & natural, B = accurate but awkward/inconsistent, C = wrong/machine-literal/half-translated.

**Default flow (20)**: `{} is not a git repository` A · `no {} found in {} — run …` A (good reorder) · `config version {} unsupported (expected 1)` A · `{}.{} is required` A · `scope.dirs is not set: …` A · `{} ({}) changed no science files …` A · `{} is not committed: an audit must cite …` A · `the committed constitution at {} is empty …` A · `refusing to continue cycle {}: {} does not descend …` A · `watch needs a terminal …` A · `resolve is a human act …` B (人的操作→人工操作) · `receipt unreadable: {}` A · `verdict is {}, not PASS — nothing to admit` A · `receipt sha {} != expected {}` A · `git {} did not finish within {}s …` A · `{} already exists; refusing to overwrite (pass --force …)` A · `no API key in ${}. …` A · `all configured {} provider routes failed. {}` A · `unknown auditor vendor {}` A · `auditor and generator are both {}: same-source supervision …` A.

**Random (20, seed 20260902)**: R1–R20 all A except R15 `there is no unconsumed passing result to admit` B (未消费 → 尚未核销) and R18 `document export discarded its authorization receipt` A.

**Placeholders (20)**: P1–P20 all A except P2 (铸出 → 签发, glossary row 12) and P16 (审计方 → 审计者, row 11).

## Corrections table

| # | English key | current ZH | proposed ZH | reason |
|---|---|---|---|---|
| 1 | choose one primary output format: PDF and Word/DOCX were both requested | 请只选择一种主要输出格式：PDF 和 Word/DOCX 同时被要求了 | 请只选择一种主要输出格式：不能同时要求 PDF 和 Word/DOCX | machine-literal passive |
| 2 | the generator replied in prose instead of the required file envelope | 生成者用散文作答，而不是要求的文件信封 | 生成者回复的是普通文字，而不是要求的文件信封 | 散文 is a literary genre |
| 3 | unsupported provider vendor {} | 不支持的供应商厂商 {} | 不支持的厂商 {} | doubled noun |
| 4 | authority workflow verdict {} differs from audit verdict {} | 权威工作流的判定 {} 与审计判定 {} 不一致 | 收据 authority 区块的工作流判定 {} 与审计判定 {} 不一致 | 权威 = "authoritative"; here `authority` is the receipt block / evidence-authority decision |
| 5 | receipt evidence route {} differs from bound report route {} / bound report has no evidence-route row | 证据路径 | 证据路由 … / 证据路由行 | route ≠ path; 路径 is used for file paths everywhere; the third route entry already says 路由 |
| 6 | authority.lone_model_blocker must be 'block' (bounded revision, the default) … | 有限修订 | 受限修订 | SENTENCES_ZH says 受限修订 for the same term |
| 7 | Connect {} {} in Settings before creating this project | 创建此项目前，请先在设置中连接 {} {} | two entries: `Connect {} API key in Settings…` → 创建此项目前，请先在设置中连接 {} 的 API key；`Connect {} subscription in Settings…` → …连接 {} 订阅 | second slot is our literal; renders "Anthropic subscription" |
| 8 | (new) a capability token must be a mapping | swallowed by `{} must be a mapping` | 能力令牌必须是映射 | half-translation at runtime (policy/tokens.py:144, `TokenError`) |
| 9 | (new) scratch directory must be an absolute normalized POSIX path | swallowed by `{} must be an absolute…` | 临时目录必须是绝对且规范化的 POSIX 路径 | hpc.py:99 `{label}` is ours |
| 10 | workspace build capacity is {}; wait for {} | 工作区构建容量为 {}；请等待 {} | 工作区构建容量为 {}；请等 {} 完成 | slot is project names; 请等待 X dangles |
| 11 | evidence ledger cannot be shown to the Auditor: {} | 证据账本无法出示给审计方：{} | 证据账本无法出示给审计者：{} | only 审计方 in a table of 审计者 (and fix the console twin) |
| 12 | (glossary) minted / mint a receipt — 6 entries (`…altered after it was minted`, `refusing to mint a receipt…` ×2, `no receipt file was minted`, `the verifier that minted this receipt`, `sample data never mints one`) | 铸出 | 签发 | 铸出 is coin-minting; receipts are 签发 in Chinese |
| 13 | (glossary) consumed / unconsumed — `receipt already consumed (replay)`, `there is no unconsumed passing result to admit` | 已被消费 / 未消费 | 已核销（重放）/ 没有尚未核销的 PASS 结果可供准入 | 消费 reads as "spend money"; 核销 is the one-time-voucher term |
| 14 | Anthropic returned an empty completion / provider returned an empty completion | 空的补全 | 空回复 | the table's own `the auditor returned an empty reply` says 空回复; same concept, one word |
| 15 | provider 'replay' needs ${} pointing at a transcript directory | 转录目录 | 对话记录目录 | 转录 = audio transcription |

Notes, not corrections: `{} has {}changes; …` → `有{}更改` would render `有staged 更改` but is never reached (the two specific forms sort first); it exists only to satisfy the orphan test. `frozen` is 打包版 in auditor/run.py and 冻结 in dcl — pick one. 连字符 (guidance names) vs 短横线 (project/job names, SSH alias) for hyphen/dash — both fine, pick one.

## Runtime resolution numbers

| measurement | value |
|---|---|
| static reader: distinct / covered / residual | 540 / 538 / 2 (`X: X`, `X\n\n  underlying: X`) — reproduces |
| table entries | 538 (branch tip) · 541 (merge) · builder said 543 |
| real Denials raised by the full suite (plugin on `Denial.__init__`) | 625, 424 distinct reasons |
| resolve through `denial_zh` | **269 / 424 (63%)** |
| unresolved | 155 — ~120 shipped sentences in `src/`, 35 test fixtures |
| distinct table entries exercised by real Denials | 162 / 541 |
| resolved but half-translated (English prose captured into a slot) | 4 distinct (rows 7–9 and `does not advertise` label) |
| CLI DENIED lines under `zh_CN.UTF-8`, real commands | 13 / 13 English (finding 1) |

## Mutation log (gate `tests/test_denial_strings_are_legible.py`, 9 tests)

| mutation | result |
|---|---|
| baseline | 9 passed |
| M1: append `ConfigDenial("a brand new refusal nobody translated")` to `src/crossaudit/autonomy.py` | **red** — 2 failed (`…has_chinese_at_the_cli_seam`, `…reaches_the_console_in_chinese`), naming the sentence; residual list still exactly the 2 |
| M2: delete the `("the task is empty", …)` entry | **red** — 2 failed, naming `the task is empty` |
| M3: append `ToolError("a second brand new refusal nobody translated")` (subclass of ConfigDenial) | **green** — 9 passed (blind spot, finding 2) |
| after `git checkout -- .` | 9 passed; worktree clean |

## Counts

Full suite, foreground, with the logging plugin (`-p denial_logger`, no test altered): **2337 passed, 2 skipped, 1 warning in 399.6 s** (builder reported 2195 at 9ccf21c; the merge added the console/authority tests). Gate file alone: 9 passed. `tests/test_authority_sentences_are_legible.py`: 6 tests, in the full run.

Byte-identity probe: `scratchpad/cli_probe2.sh` (outputs in `p2-base`, `p2-new`, `p2-zh`). Runtime measurement: `scratchpad/denial_logger.py`, `scratchpad/denial_log.jsonl`.
