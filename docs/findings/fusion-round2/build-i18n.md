# build-i18n — "479 条拒绝/报错文案没有中文"

Branch `fusion/i18n-denials`, base `f050cbd`, worktree `scratchpad/wt-i18n`. Not pushed.

## 1. How the 479 was measured, and reproducing it

Source: D130 (`docs/DECISIONS.md` §D130), `docs/findings/w1-denial-strings.md`, and the
test that pins it, `tests/test_denial_strings_are_legible.py::test_the_denial_catalogue_gap_is_measured_not_guessed`.
Predicate: every literal or f-string first argument to `Denial(...)`, `ConfigDenial(...)`,
`IntegrityDenial(...)`, `ProviderDenial(...)` under `src/crossaudit`, f-strings rendered with
`X` per interpolated part, DISTINCT sentences, each driven through the console's shipped
`zhValue()` (`console/page.py` `ZH` + `ZH_PATTERNS`, extracted by `tests/harness/extract_zh.py`,
run under node) and counted as covered when the result contains CJK.

Exact reproduction at `f050cbd` (needs node):

    cd <worktree>; export PYTHONPATH=$PWD/src
    /Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python \
      /private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/measure_denials.py out.json
    # -> messages 605  files 46  distinct 540  covered 52  uncovered 488

(`measure_denials.py` imports `_denial_messages()`/`_translate()` from the pinned test and prints the totals.)

**Why 488, not 479.** D130 measured 530 distinct / 51 covered = 479 at its commit; the finding
file records 530 / 52 = 478 after the ledger pattern landed. Between that commit and `f050cbd`
the fusion merges (finding-states, repair guard, authority, held fixes) added 10 new distinct
denials (e.g. `config.py` `authority:`/`repair:` validation, `controller/state.py` escalation
guards). Same predicate, more sentences: 540 − 52 = 488.

## 2. The mechanism, and the one deviation I had to make

Two translation mechanisms already exist, and the 479 was measured against the one I was told
not to touch:

* **Console** — `console/page.py` `const ZH={...}` / `ZH_PATTERNS` / `zhValue()`: text-keyed,
  JS, applied client-side to the `reason` the server sends in `Denial.as_dict()`. Owned by the
  console builder; off-limits for this slice.
* **CLI** — `cli/i18n.py` `t(key)` with dotted keys; for denials the seam is
  `Denial(reason, human=t(...))` (`errors.py`): `reason` is the machine contract (exit code,
  `--json`, and the `DENIED (kind): reason` stderr line which `CrossAuditApp.swift`
  `currentLaunchDenial()` parses by prefix), `human` the sentence a person reads. Only 3 raise
  sites carry `human=`; the other ~600 carry only a reason.

Attaching `human=t(...)` at ~600 raise sites across 46 files — many in the audit core and in
files this slice must not touch — was not viable, and the parent's own instruction ("keep the
English source string as the key; for f-strings translate the template and keep the
placeholders") describes a text-keyed table. So:

* `src/crossaudit/cli/denials_zh.py` — the table, `ENTRIES: ((english, chinese), ...)`, 543
  entries, exact or `{}`-templated (Chinese may reorder with `{0}`, `{1}`).
* `src/crossaudit/cli/i18n.py` — `denial_zh(reason) -> str | None` (exact, then templates,
  most-specific-first: fewest slots then longest literal) and `denial_text(reason)` (English
  verbatim; under zh a missing entry is served as `[en] …` and counted under `denial:` — the
  same marked-and-counted contract as `t()`).
* `src/crossaudit/cli/main.py` — the catch-all prints
  `DENIED ({kind}): {i18n.denial_text(exc.reason)}`. Prefix stays Latin (Swift parses it);
  English output is byte-identical to before; `--json` untouched.

D130's rule ("never identify your own content by its appearance when a user can author content
with the same appearance") is respected: the lookup is applied to `Denial.reason` only —
provenance first, text second — never to free text, and interpolated user parts are captured
and carried through untranslated.

**Console hand-off (not done here, one line for its owner):** `server.py::_deny` can add
`"reason_zh": i18n.denial_zh(why.reason)` to the wire body (the A2 `text_i18n` precedent), or
`page.py` can inline `json.dumps(dict(ENTRIES))` beside `ZH`. Until then the console-driven
count in the pinned test stays at 52/540 — I left that test untouched and green.

## 3. Counts

| measurement | before (f050cbd) | after (9ccf21c) |
|---|---|---|
| distinct Denial sentences (static reader) | 540 | 540 |
| with Chinese via console `zhValue()` | 52 | 52 (console untouched) |
| with Chinese via `i18n.denial_zh()` (CLI seam) | 0 (did not exist) | **538** |
| residual, pinned | — | **2** |

Reproduce the after-count: `test_every_denial_reason_has_chinese_at_the_cli_seam`, or
`python -c "..."` over `_denial_messages()` with `i18n.denial_zh`.

## 4. Residual (2), with reasons — pinned in `ALLOWED_RESIDUAL`

| reader rendering | site | why |
|---|---|---|
| `X: X` | `receipt/build.py:236` `f"{EVIDENCE_BROKEN_REASON}: {evidence.reason}"` | The reader sees only the join of a constant and a variable. The sentence a person meets IS translated by its own template (`the evidence ledger for this project is present and does not verify … used no tools: {}`), whose prefix the orphan test checks against `EVIDENCE_BROKEN_REASON`. |
| `X\n\n  underlying: X` | `providers/base.py:440` `f"{tls_advice()}\n\n  underlying: {exc.reason}"` | Wraps `tls_advice()`, an English paragraph composed at runtime from this machine's certificate paths. Translating the two-word frame around it would be a half-translation that reads as done. Needs `tls_advice()` itself keyed — out of this slice's floor. |

Everything else, including the 3 `human=` sites, the audit-core denials (`ledger/`, `broker/`,
`dcl/`, `controller/`), `receipt/verify.py` (39), `config.py` (39), and all console-API
denials, has an entry. Nothing was classified "internal-only": D130's point is exactly that the
denial nobody expects to see is the one that matters.

## 5. Glossary followed (extracted from `i18n.CATALOGUE["zh"]` + console `ZH`)

Generator/generator 生成者 · Auditor/auditor 审计者 (审计方 kept in the D130 ledger sentence for
parity) · receipt 收据 · verdict 判定 · ledger 账本 · evidence 证据 · admit 准入 · Constitution
章程 · rule 规则 · cycle 周期 · round 轮 · loop 循环 · increment 增量 · provider 供应商 ·
vendor 厂商 · credential 凭据 · fallback route 备用路由 · workspace 工作区 · Keychain 钥匙串 ·
working/audit repository 工作仓库/审计仓库 · science repository 科学仓库 · guidance 指导 ·
skill 技能 · check 检查 · check pack 检查包 · profile 方案 · compute host 计算主机 · job 作业 ·
runtime 运行时 · macOS app macOS 应用 · Settings 设置 · chat 对话 · task 任务 · escalate 升级 ·
reasoning effort 推理强度 · manifest 清单 · reproduction bundle 复现包 · verifier 验证器 ·
dispute 申辩 · amendment 修正 · resolution 裁定 · symlink 符号链接. Kept Latin: identifiers,
config keys, flags, commands, paths, env vars, PASS/BLOCKED/ESCALATED, `API key`, MCP/HPC/JSON.
Punctuation: full-width `：；（）「」` as in the existing catalogues; `——` for em-dash.

## 6. Gate (D10)

`tests/test_denial_strings_are_legible.py` (+4 tests):
* `test_every_denial_reason_has_chinese_at_the_cli_seam` — residual set **==** `ALLOWED_RESIDUAL`
  (equality, so the list cannot carry padding). Mutation: one new `ConfigDenial("…")` without an
  entry → red, naming the sentence.
* `test_every_denial_entry_translates_itself_and_carries_its_slots` — CJK present, every slot
  survives, and the entry that answered is itself (no generic-template swallowing).
* `test_no_denial_entry_is_for_a_sentence_nobody_raises` — orphan guard; the two `pair.py`
  variants and the `EVIDENCE_BROKEN_REASON` template are checked against the source.
* `test_the_cli_denied_line_speaks_chinese_after_its_parsed_prefix` — through `main()`: zh
  sentence after `DENIED (config): `, English byte-identical, missing entry `[en]`-marked and
  counted in the `[i18n]` notice.

## 7. Commits (on `fusion/i18n-denials`, not pushed)

    f769e65  i18n: Chinese for every Denial reason, keyed by its English      (cli/denials_zh.py, +948)
    054d847  cli: serve the DENIED line's reason in the language the command was asked for  (cli/i18n.py, cli/main.py)
    9ccf21c  test: gate the untranslated-denial count at its two-entry residual  (tests/test_denial_strings_are_legible.py)

Files touched: `src/crossaudit/cli/denials_zh.py` (new), `src/crossaudit/cli/i18n.py`,
`src/crossaudit/cli/main.py`, `tests/test_denial_strings_are_legible.py`. Nothing under
`console/`, `auditor/`, `receipt/`, `cli/build.py`, `generator.py`, `repair_guard.py`;
no DECISIONS.md entry.

## 8. Tests

* i18n/CLI slice: `tests/test_denial_strings_are_legible.py tests/test_cli_i18n.py
  tests/test_console_translation_boundary.py tests/test_language_is_reachable.py tests/test_app.py
  tests/test_guard_names_match_what_they_check.py` → 120 passed.
* Full suite, foreground: `python -m pytest -q -p no:cacheprovider tests` →
  **2195 passed, 2 skipped**, 340 s. (`crossaudit.__file__` confirmed inside the worktree.)


---

# review fixes (round 2) — `fusion/i18n-denials` after merging `fusion/evidence-authority`, tip `a3857ec`

Review: `scratchpad/codex-compare/review-i18n.md` (NEEDS CHANGES, 6 items) plus the coordinator's
provider-failure addition. All addressed. Full suite, foreground: **2390 passed, 2 skipped** (310 s);
gate file after the last commit: 45 passed with `test_run_liveness.py`.

## 1. The DENIED line is Chinese for every command

`_language_for(args)` in `cli/main.py` is the one resolver (explicit `--lang` -> `LC_ALL` / `LC_MESSAGES`
/ `LANG` -> en); `_speak()` uses it and so does `main()`'s `except Denial` branch, so the sentence after
the parsed `DENIED (kind): ` prefix comes out in the person's language for every command, not only
init/doctor. There is no saved CLI preference (the console keeps one in a cookie; the CLI reads the
environment), so the resolver has three sources, not four — said in its docstring rather than invented.
Test `test_every_command_refuses_in_the_persons_language[run|check|verify|build]` drives the real
`main()` under `LANG=zh_CN.UTF-8` on a `version: 2` config and asserts
`DENIED (config): 不支持的配置版本 2（应为 1）` with no `[en]`. The dead `--json` check is gone.

## 2. Denial subclasses and composed reasons, measured and covered

Subclasses (fixpoint over `src/`): ConfigDenial, IntegrityDenial, ProviderDenial, ToolError, TokenError,
LedgerError, SSHFailure. The gate's reader (`_denial_messages` in
`tests/test_denial_strings_are_legible.py`) walks that hierarchy, treats factories that pass their reason
through (`_path_denial`) as raise sites, and renders f-strings, `%`, `.format()`, `+` chains and
`.strip()`. `test_the_reader_enumerates_every_denial_subclass` pins it; an untranslated `ToolError("…")`
now reddens the count (the review's M3).

| measurement | review (ebdba80) | now (a3857ec) |
|---|---|---|
| static reader: distinct / covered / residual | 540 / 538 / 2 | **648 / 646 / 2** (['X\n\n  underlying: X', 'X: X']) |
| table entries (`ENTRIES`) | 538–541 (report said 543) | **741**, counted from the file |
| `CLAUSES` (only ever inside a slot) / `COMPOSITES` | — | 45 / 12 |
| reviewer's runtime log (`denial_log.jsonl`, 424 distinct real Denials) resolving | 269 (63%) | **390 (91%)** |
| still unresolved | 155 | 34: test fixtures (`boom`, `nope`, `x`, `stop after stream probe`, `injected provider failure`, …), vendor text (`temperature is unsupported …`), the generator's own prose (`I could not find anything called …`, which must never be translated), two derivation rows a test raises directly, the `tls_advice()` residual |

Mechanism for the composed ones: `COMPOSITES` names the templates whose slot is one of OUR clauses (a
secret kind, a gh hint, an admission shortfall, an authority-block error, a guardrail reason, the
route summary). Only those slots are looked up — exact, then a `; ` list piece by piece, then sentence
by sentence, then a `vendor:model — refusal` route line with the id carried through, then the whole
against a template — so a person's own words are never matched (D130). Templates sort by literal text
first, then slot count, so `Daily token limit reached: {} / {}.` beats the one-slot frame that used
to capture it whole.

## 3. Generic half-translations replaced by specific entries

`Connect {} API key | subscription in Settings…`; `a capability token must be a mapping`; `scratch
directory | remote path | remote input path must be an absolute normalized POSIX path`; the hpc.py
`_bounded_int` labels (concurrent job limit, Generator jobs per task / node / CPU / GPU limit, nodes,
CPUs per task, GPUs) × whole-number / between; the mcp.py `_bounded_json` labels (MCP message / tool
metadata / tool arguments / structured result) × valid-JSON / safety-limit; projects.py `_clean_text`,
`_bounded_number`, `_optional_positive` keys (name, description, auditor/generator vendor/model, max
attempts, backoff seconds, circuit breaker, daily/monthly limits); pair.py `science | audit repository
must be owner/name`; generator/auditor forms of `all configured … provider routes failed | are cooling
down`. `{} does not advertise {} for {}`: its first slot is `SPECS[vendor].label` (projects.py:938 —
OpenAI, Anthropic), a vendor name carried through; the "Auditor" the review saw came from a fixture
label, so it stays a template.

## 4. Corrections table: all 15 rows applied verbatim

Rows 1–15 as proposed (签发 for mint ×6, 核销 for consume ×2, 空回复 ×2, 对话记录 ×2, 受限修订, 证据路由 ×2,
收据 `authority` 区块, 不支持的厂商, 请等 {} 完成, the two `Connect` entries, 能力令牌, 临时目录, 审计者 in
the D130 sentence). The notes too: 人工操作, 打包版 for both `frozen`, 短横线 for every hyphen/dash.

## 5. Glossary pinned

The CLI catalogue aligned to the console (16 replacements: 审计方→审计者, 生成方→生成者, 采信→准入).
`test_the_glossary_is_the_consoles_and_the_retired_terms_are_gone` asserts no retired term (审计方 生成方
采信 铸出 转录 补全) in `CATALOGUE["zh"]`, `ENTRIES`, `CLAUSES` or `SENTENCES_ZH`, and that 审计者 / 生成者 /
准入 / 收据 / 账本 / 判定 are in use. The console twin of the D130 pattern (`审计方` in page.py's
ZH_PATTERNS) is now a fallback behind `reason_zh` and is left to the console owner.

## 6. Coordinator's addition: the keyless first run, on both surfaces

`all configured generator provider routes failed. anthropic:claude-opus-4-8 — anthropic credential
$CROSSAUDIT_GENERATOR_KEY is not configured` ->
`已配置的所有生成者供应商路由都失败了。anthropic:claude-opus-4-8 — 未配置 anthropic 凭据 $CROSSAUDIT_GENERATOR_KEY`;
wrapped by the daemon as `provider failure left this task waiting for a person: …` ->
`供应商失败，该任务正在等待人工处理：…` (a composite of a composite; per-route refusals such as `provider
returned HTTP 401` or `provider unreachable: …` translate in turn, vendor words carried through).
Console seam: `overview.escalations()` adds `why_zh` / `stop_reason_zh` beside the unchanged English;
`page.py` prefers them under zh at the one seam that renders the reason (`resolution-limit-copy`).
Test `test_a_missing_key_provider_failure_is_chinese_on_both_surfaces` drives `resilience.complete()`
with the key env unset (no provider is called), then the CLI lookup and the Decision Center row.

## 7. Minor (review item 7)

Dead `--json` branch removed. `_report_untranslated()` still prints to stdout (pre-existing, unchanged).
The `crossaudit check` TypeError without `scope.dirs` is pre-existing and untouched.

## Commits (on top of the merge of `fusion/evidence-authority`)

```
a3857ec i18n: the one variable-carried refusal the runtime log still showed in English
e796d78 test: the reader walks the Denial hierarchy; every command refuses in the person's language
f3ba516 console: the Decision Center's stop reason served in Chinese beside the English
1957cfb cli: resolve the refusal's language once, for every command; translate clauses in turn
d6f068d i18n: the Denial subclasses, the composed refusals, and the review's corrections
```

Console files touched this round, per the coordinator's instruction: `console/overview.py` (additive
fields), `console/page.py` (one expression). Everything else: `cli/denials_zh.py`, `cli/i18n.py`,
`cli/main.py`, `tests/test_denial_strings_are_legible.py`. Not pushed; no DECISIONS.md entry.


---

# review fixes (round 3) — the garbled Decision Center line, tip `3ba764c` (on e0e3b36)

Reported: `未配置 generator provider failure in round 1: all configured … — anthropic 凭据 $KEY` — the
generic `{} is not configured` matched the whole composed sentence.

1. **Specific templates** for cli/build.py's round-prefixed refusal: `generator|auditor provider failure in
   round {}: all configured … routes failed. {} — {} credential ${} is not configured` →
   `生成者在第 {} 轮失败：已配置的所有生成者供应商路由都失败了。{} — 未配置 {} 凭据 ${}` (auditor likewise),
   plus the composite prefix `<role> provider failure in round {}: {}` for every other refusal.
2. **Leading-slot guard** (`i18n._swallows_a_sentence`): a template that begins with a bare slot refuses a
   match whose slot holds sentence punctuation (`. ; ! ?` + space, newline) or more than six English words
   (whitespace tokens; a path/id/env var is one token). The sentence is then left whole in English,
   `[en]`-marked and counted — never half-translated. Slots with their own translator (composite clauses,
   the authority sentences) are exempt by construction.
3. **Guard test** `test_no_runtime_refusal_is_half_translated` over the committed
   `tests/fixtures/denial_reasons_runtime.jsonl` (409 distinct real Denial reasons, paths scrubbed;
   regenerate with `CROSSAUDIT_DENIAL_LOG=<file> pytest tests`, recorder in `conftest.py`): no answered
   reason has a run of >6 consecutive English words; sole exemption, the vendor's sentence after
   `provider returned HTTP N\n  it said: `. Plus `test_a_leading_slot_template_refuses_to_swallow_a_sentence`
   (D10: delete the guard → red with the exact garbled line).
4. **Harness failure** (`test_console_stop_causes.py::…renders_each_cause…`): `currentLocale` is the page's
   locale accessor; `render_decision.py` now sets it per pass (`en`, `zh`) and the page guards it with
   `typeof`. The test gained a `keyless` row asserting `why_zh` on the card in ZH and the unchanged English
   in EN, with no English run.

Entries now **745**. Full suite, foreground: **2470 passed, 2 skipped, 1 warning in 319.96s (0:05:19)**.
