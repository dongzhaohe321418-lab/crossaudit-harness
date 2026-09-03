# Independent review — token warning & billing slice (fusion/billing @ c30740f)

**Verdict: NEEDS CHANGES.**

The feature works. Every behaviour I drove by hand — alarms, 429 parsing, export,
roll-up, price overrides, the pill, the cost lines — produced the right numbers and
the right sentences in both languages. Nothing in the diff reads another
application's tokens or session files, and nothing calls a vendor usage endpoint.
What is wrong is (a) the *wiring* of attribution is completely untested — six
separate deletions of it pass the whole suite, and one of them is a live bug
already in the tree — and (b) four small copy/honesty defects on the surface the
owner asked to keep smooth.

Counts: full suite **2555 passed, 2 skipped** in 349 s (foreground, worktree `src`
on `PYTHONPATH`, `crossaudit.__file__` confirmed inside the worktree) — matches the
builder's report. `tests/test_billing.py`: 27 tests. 18 mutations run, 6 survived.

---

## Defects

### 1. The auditor's usage line loses its cycle and round — and nothing notices
`src/crossaudit/cli/main.py:1521` (`_usage_context`) is the only place the auditor's
completion learns which cycle and round it belongs to. Delete those two lines and
**the entire suite still passes**:

```
FULL SUITE with M14 (cycle_id/round dropped): 2555 passed, 2 skipped in 339.32s
```

Five more deletions of the same kind survive `test_billing.py + test_usage.py +
test_resilience.py + test_settings_ia.py + test_router_and_constitution.py +
test_chat_lane.py + test_console_translation_boundary.py` (115 tests):

| mutation | file:line | result |
| --- | --- | --- |
| M11 router lane records as `auditor` | `cli/talk.py:374` | GREEN |
| M12 router lane records as `auditor` (console) | `console/server.py:963` | GREEN |
| M13 auditor loses `chat_id` | `cli/build.py:1055` | GREEN |
| M14 auditor loses `cycle_id`/`round` | `cli/main.py:1521` | GREEN (also green on the full suite) |
| M15 chat lane loses `chat_id` | `cli/talk.py:31` | GREEN |
| M16 `prices:` never reaches the ledger | `cli/build.py:74` | GREEN |

`test_billing.py` tests `record_reply` and the aggregators in isolation and never
drives a round. Every one of the six call sites that feed them is unpinned.

**Fix:** one test that runs `build_mod.run_loop` with a stubbed
`providers/resilience.complete` (generator and auditor), reads
`<root>/.crossaudit/usage.jsonl`, and asserts every line carries `run_id`,
`cycle_id`, `round`, `chat_id` and the right `role` — plus one for the router lane
asserting `role == "router"`. I wrote exactly this probe; it is four lines of
assertion on top of the existing `science`/`cfg`/`transcripts` fixtures.

### 2. Round 1's generation is never attributed to the cycle it produced
`src/crossaudit/cli/build.py:607` seeds `usage_context["cycle_id"] = continuation_cycle or ""`,
and `build.py:679` only fills it once a previous audit has opened a cycle. So the
first generator call of every fresh task is written with no `cycle_id`, while the
audit of that same commit is written with one. Ledger from a real
`run_loop` round I drove (replay/fixture providers, PASS in round 1):

```
{'role': 'generator', 'run_id': 'run0123456789ab', 'cycle_id': None,               'round': 1, 'chat_id': 'a1b2c3d4e5f60718', 'total': 150}
{'role': 'auditor',   'run_id': 'run0123456789ab', 'cycle_id': '13c5c212ab9c0ba4', 'round': 1, 'chat_id': 'a1b2c3d4e5f60718', 'total': 220}

per_run   = 370 tokens   (hand sum 150 + 220 ✓)
per_chat  = 370 tokens   (✓)
per_cycle('13c5c212ab9c0ba4') = 220 tokens   (✗ — the true cycle spend is 370)
```

Per-cycle totals therefore under-count every cycle by its own first generation.
**Fix:** set `usage_context["cycle_id"]` when the loop learns `build_cycle_id`
*and* backfill it for the round already in flight, or move the cycle id onto the
generator line the way `main.py:_usage_context` does for the auditor.

### 3. `console/page.py:6594` — ZH countdown gains a stray space on exact hours
```
en  2 h 10 min → "Provider limit reached · resets in 2 h 10 min"        ✓
zh  2 h 10 min → "已达供应商额度上限 · 2 小时 10 分钟后重置"                ✓
en  exactly 2h → "Provider limit reached · resets in 2 h"               ✓
zh  exactly 2h → "已达供应商额度上限 · 2 小时 后重置"                      ✗
zh  25 h       → "已达供应商额度上限 · 25 小时 后重置"                     ✗
```
`.trim()` binds to the parenthesised minutes ternary, not to the joined string, so
the EN branch (which wraps both) is clean and the ZH branch is not.
**Fix:** `if(zh)return ((h?h+' 小时 ':'')+(m||!h?m+' 分钟':'')).trim();`

### 4. `console/page.py:6595` — "resets in now" / "现在后重置"
When the parsed moment has already passed (or the 30 s ticker fires one beat late),
`countdownText` returns the word `now` / `现在` and `resetSentence` glues it into a
preposition that no longer fits:
```
en → "Provider limit reached · resets in now"
zh → "已达供应商额度上限 · 现在后重置"
```
The card sits on this string until the run state changes. `countdownText`'s three
words are pinned by a test; the composed sentence is not.
**Fix:** special-case `s <= 0` in `resetSentence` — "Provider limit reached · you
can retry now" / "已达供应商额度上限 · 现在可以重试" — or drop the line entirely.

### 5. `console/page.py:6558-6560` — the pill reports `$0.00` for an unpriced project
```
usage: 9 calls, 120,000 tokens today, 3.4M this month, every call unpriced
en → "Today $0.00 · Month $0.00"   aria-label "Usage: today $0.00, this month $0.00 · within budget. Open usage"
zh → "今日 $0.00 · 本月 $0.00"
```
`shortUsd` maps "no price" and "zero cost" to the same glyph. The Usage view says
the truth ("N calls this month could not be priced (model X …)"); the always-visible
element says a wrong number. Under the owner's "no needless errors" this is the one
place a person will look first and be misinformed.
**Fix:** in `usageFigure`, fall back to `formatTokens(b.tokens)` (or an em dash)
when `b.unpriced_calls` and `api_value_usd` is falsy.

### 6. `providers/base.py:523` — a non-finite reset moment reaches the journal and the wire
`_parse_duration_seconds` starts with a bare `float(value)`, so `Retry-After: inf`
parses. The moment is then persisted on the run's `waiting_reason`
(`runtime/commands.py:128`) and serialised into the state snapshot:
```
rate_limit_reset(  {"retry-after":"inf"} )  -> inf
json.dumps(denial.detail) -> {..., "rate_limit_reset_at": Infinity, ...}
```
`Infinity` is not JSON; the browser's `JSON.parse` on that SSE frame throws and the
console stops updating. `Retry-After: 99999999999999999999` is merely ugly
("resets in 27777777777777776 h 46 min"). Neither is a likely provider, but both
are one header away and the surface is fail-open.
**Fix:** in `rate_limit_reset`, drop values that are not finite and clamp to a
sane horizon (e.g. `now + 7 days`) before returning.

### 7. `usage.py:214` — a price override silently prices a proxy origin
At `ad1dc0b` the rule was absolute: a non-official origin is never priced
(`_is_official`). The override is now consulted *before* that check, so:
```
official  origin + override -> $18.00  user_priced
PROXY     origin + override -> $18.00  user_priced      (was: unpriced, always)
PROXY     origin, no override -> None  unpriced
```
That is defensible — the user declared the rate — but it is undocumented in the
report, unmentioned in the `record_reply` docstring, and untested either way. Its
real consequence is that a monthly **cost hard limit**, which fails closed the
moment anything is unpriced, now passes on a user-typed guess for a relay whose
actual billing CrossAudit cannot see.
**Fix:** decide it deliberately — either keep it and say so in the docstring plus a
test, or restore `_is_official` as the outer gate.

### 8. `usage.py:869-871` — `project_rollup(now=…)` / `workspace_rollup(now=…)` are inert
`project_rollup` takes `now` and then calls `summary(cfg)` without it. Proof:
```
event stamped 2026-05-15
workspace_rollup([cfg], now=2026-05-15) -> month_tokens 0
workspace_rollup([cfg], now=2026-09-03) -> month_tokens 0
```
No user impact today (the server never passes `now`), but it is a false signature
and it is why the roll-up cannot be tested under a fake clock.
**Fix:** `summary(cfg, now=now)`.

### 9. The export period filter is untested — the mutation survives
`_in_period` can be replaced by `return True` and
`test_billing.py + test_usage.py + test_resilience.py + test_settings_ia.py`
stay green (58 passed). `test_export_carries_the_event_columns_and_is_token_gated`
requests `period=all` and `period=day` but the fixture holds one just-recorded
event, so both answers are identical. The filter itself is correct — I checked it
by hand (day 2 rows / month 3 / all 4 over a four-event ledger spanning two months)
— it is simply unpinned.
**Fix:** add two events outside today/this month to that fixture and assert the
three row counts.

### 10. `usage.py:909` — `monthly_report()` is dead code
28 lines, zero callers in `src/` or `tests/`. The report card the Usage view
actually renders is the JS `monthlyReport` at `page.py:6629`. Delete one of them.

### 11. `console/page.py:6630` — "Passed audits" is all-time under a "this month" header
`monthlyReport` counts every cycle in `d.cycles` with status passed/consumed,
unfiltered by date, inside a section headed `Monthly report · this month`. Every
other row in that table is month-scoped.
**Fix:** filter the cycles by month, or move the row out of the monthly table.

### 12. `tests/test_billing.py:540` — an assertion that cannot fail
```python
assert got["en"]["sentences"][0] in view and "Today&#39;s token budget is 80% used" in view.replace("'", "&#39;") or "Today's token budget is 80% used" in view
```
`A and B or C` — the trailing disjunct alone satisfies it, so the first clause is
decorative. Split it into two asserts.

---

## What I checked and found correct

**Attribution (1).** A real `run_loop` round with fixture providers: generator and
auditor lines carry `run_id`, `round`, `chat_id`, `duration_ms` and (for the
auditor) `cycle_id`. Old lines with no attribution still parse, summarise and
export (empty cells). `per_run` / `per_chat` match a hand sum exactly (370 = 150 +
220). `router` is a real role at `talk.py:374` and `server.py:963`. Defects 1 and 2
are the exceptions.

**Alarms (2).** Fake clock, `daily_token_limit: 1000`:
```
800 tok @2026-09-30 -> fires [80] "Today's token budget is 80% used" / "今日 token 预算已用 80%"
                              resets "Resets at midnight" / "明天 0:00 重置"
same call again      -> []                       (once per threshold)
1000 tok             -> fires [95] only
usage-warnings.json  -> {"daily":{"fired":[80,95],"period":"2026-09-30"}}
caches cleared (restart) -> []                   (persisted, cannot re-fire)
900 tok @2026-10-01  -> fires [80]               (re-armed by the period key)
no budgets configured, 99M tokens -> []          (and no state file is written)
```
Reset wording, both languages:
```
2026-09-30 -> "Resets on Oct 1" / "10 月 1 日重置"
2026-12-15 -> "Resets on Jan 1" / "1 月 1 日重置"
2026-01-31 -> "Resets on Feb 1" / "2 月 1 日重置"
2024-02-29 -> "Resets on Mar 1" / "3 月 1 日重置"
```
Park card, EN/ZH: `"Paused. Resets at midnight"` / `"Paused. 明天 0:00 重置"`.

**429 parsing (3).** `now = 1788400000`:
```
OpenAI  x-ratelimit-reset-requests: 6m0s + -tokens: 1s -> +360 s   (latest window wins)
OpenAI  x-ratelimit-reset: 1788403600 (epoch)          -> +3600 s
OpenAI  250ms / 1h2m3s                                 -> +0.25 s / +3723 s
Anthropic anthropic-ratelimit-tokens-reset RFC 3339 + retry-after: 30 -> the ISO stamp
Retry-After: 120                                       -> +120 s
Retry-After: HTTP date                                 -> the date
no headers, no body                                    -> None (the surface says nothing)
body {"error":{"resets_in_seconds":90}}                -> +90 s
```
Rendered: `"Provider limit reached · resets in 2 h 10 min"` /
`"已达供应商额度上限 · 2 小时 10 分钟后重置"`. Nothing crashes; defects 3, 4 and 6 are
the wording and the non-finite edge.

**No third-party reads.** Grepped the whole `ad1dc0b..c30740f` diff over `src` and
`tests` for `~/.claude`, `~/.codex`, `auth.json`, Keychain items, OAuth and vendor
usage endpoints. The only Keychain matches are CrossAudit's own items
(`io.crossaudit.app.provider.<vendor>`, from the merged setup slice) and one test
comment explicitly refusing to touch the machine's Keychain. No OAuth polling.

**Header pill (4).** EN `"Today $0.42 · Month $12.10"`, ZH `"今日 $0.42 · 本月 $12.10"`;
token mode `"Today 38K · Month 1.2M"`, remembered in `crossaudit-usage-mode`;
`usage-pill ok|warning|blocked`; hidden with `all.calls === 0` and with no `usage`
at all; accessible name `"Usage: today $0.42, this month $12.10 · within budget.
Open usage"` / `"用量：今日 …，本月 … · 预算内。打开用量"`; click → `openPanelTab('usage')`.
**VDS: the top bar gains exactly one element** (18 → 19), the `<button id="usage-pill">`.

**Main-surface cost lines (5).** Rendered HTML, both languages:
```
<div class="run-cost"><span>This task: 12K tokens · ≈$0.08</span></div>
<div class="run-cost"><span>本次任务：12K tokens · ≈$0.08</span></div>
<div class="run-cost"><span>This task: 12K tokens · 2 unpriced</span></div>   (all unpriced)
<div class="run-cost"><span>本次任务：12K tokens · ≈$0.08 · 2 次未计价</span></div> (mixed)
<div class="turn-cost">≈$0.05 · 42 s</div>
<div class="turn-cost">9.0K tokens</div>                                      (unpriced turn)
```
No run id, cycle id, sha, hex string, `provider:model` pair or raw verdict word in
any of them. Mutation M8 (leak `x.run_id` into the turn line) turns
`test_cost_lines_carry_no_run_ids_hashes_or_provider_model_strings` red.

**Unpriced / override (6).**
```
en → "3 calls this month could not be priced (model gpt-9-mini has no price in the snapshot of 2026-08-03)"
     "1 call this month could not be priced (model x has no price in the snapshot of 2026-08-03)"   (singular handled)
zh → "本月有 3 次调用无法计价（模型 gpt-9-mini 在 2026-08-03 的价格快照中没有价格）"
```
`prices:` override → `api_value_usd = 18.0`, `billing_kind = "user_priced"`.
Config validation and its ZH, all six shapes:
```
prices: 5                    -> "prices must be a mapping"                          / "prices 必须是映射"
prices: {m: 7}               -> "prices.m must be a mapping of input, output, …"    / "prices.m 必须是包含 input、output、cache_write、cache_read 的映射"
prices: {m: {input: 1, bogus: 2}} -> same denial (unknown key refused)
prices: {m: {input: -1}}     -> "prices.m.input must be a non-negative number (USD per 1M tokens)" / "prices.m.input 必须是非负数（每 100 万 token 的美元价格）"
prices: {m: {input: true}}   -> same (bool is not a number)
prices: {<200 chars>: {…}}   -> "prices: model ids must be 1 to 160 characters"     / "prices：模型 ID 必须是 1 到 160 个字符"
prices: {}                   -> accepted, {}
```
Every one round-trips through `i18n.denial_zh`. Mutation "override ignored"
(`override = None` in `record_reply`) → `test_user_price_override_is_used_and_stamped`
**red**. Defect 7 is the proxy-origin question.

**Export + roll-up (7).** `/api/usage/export` without `t=` → **403**; `format=xml` →
400; header `t,iso,role,phase,vendor,provider,model,input,output,cache_write,
cache_read,total,method,api_value_usd,billing_kind,price_snapshot,run_id,cycle_id,
round,chat_id,duration_ms` — exactly `EXPORT_COLUMNS`, and the JSON rows carry the
same key set (`set(rows[0]) == set(EXPORT_COLUMNS)`). Periods over a four-event,
two-month ledger: day 2 / month 3 / all 4 ✓. `csv.DictWriter` quotes properly.
"secret" prompt text is absent. Roll-up over two temp projects:
```
alpha  today 115  month 315  unpriced 0  unconfigured
beta   today 900  month 900  unpriced 1  blocked        (daily_token_limit 50)
total  today 1015 month 1215 unpriced 1                 (hand sum ✓)
```
Rendered table, ZH: headers translate through the locale sweep
(`Project/Today/This month/Unpriced/Budget` are all in the catalogue) and the
budget word is translated inline: `预算内`, `未设预算`.

**Copy (8).** Every new literal I traced resolves in ZH — including the ones the
report does not list (`Exact model ID`→准确的模型 ID, `Remove`→移除, `Dismiss`→忽略,
`Tokens`→Token, `Project`→项目, `Today`→今日, `This month`→本月, `Unpriced`→未计价).
The `MutationObserver` at `page.py:4023` covers the async roll-up table, so the
English-in-`innerHTML` pattern is fine. All new sentences are ≤ 2 sentences and
plain. Two wording defects (3, 4) and one honesty defect (5) above; one nit: the ZH
run-card line keeps the English plural `tokens` (`本次任务：12K tokens`) while the
catalogue itself maps `Tokens`→`Token`.

**Regressions (9).** `tests/test_usage.py` and `tests/test_resilience.py` are
**unchanged** and green. The six deliberately-updated pinned tests each carry a
comment naming the mutation they now allow, and each change is the minimum:
`test_chat_lane.py` / `test_router_and_constitution.py` widen fake signatures for
the new `chat_id` / `role` kwargs; `test_generation_stream_runtime.py` widens the
factory for the fifth positional; `test_context_condensation_page.py` stubs
`runCostLine` to `''`; `test_live_region_locale_timing.py` adds `usage-banner` to
the live-region list; `test_settings_ia.py` replaces the "Export isn't available
here yet" pin with the export + roll-up markers. All defensible. One consequence
worth naming: `test_router_and_constitution.py:289` now uses
`lambda _cfg, **_usage: complete`, which swallows `role="router"` — that is why
mutations M11/M12 survive.

---

## Mutation log (18 run, 6 survived)

| # | mutation | site | scope | result |
| --- | --- | --- | --- | --- |
| M1 | attribution ids not written | `usage.py:record_reply` | test_billing | **RED** |
| M2 | alarm re-fires every call (`threshold in already` dropped) | `usage.py:check_budget_warnings` | test_billing | **RED** |
| M3 | 429 takes the earliest window (`max`→`min`) | `providers/base.py:rate_limit_reset` | billing+usage+resilience+settings_ia | **RED** |
| M4 | monthly reset names this month | `usage.py:reset_moments` | test_billing | **RED** |
| M5 | pill never hides when empty | `page.py:renderUsagePill` | test_billing | **RED** |
| M6 | export ignores the period (`_in_period` → True) | `usage.py:818` | billing+usage+resilience+settings_ia | **GREEN — defect 9** |
| M7 | unpriced models never named (`return []`) | `usage.py:unpriced_models` | billing+usage+resilience+settings_ia | **RED** |
| M8 | turn-cost line leaks `run_id` | `page.py:turnCost` | test_billing | **RED** |
| M9 | roll-up total drops a project | `usage.py:workspace_rollup` | test_billing | **RED** |
| M10 | price override ignored | `usage.py:record_reply` | test_billing | **RED** |
| M11 | router lane records as `auditor` | `cli/talk.py:374` | 115-test set | **GREEN — defect 1** |
| M12 | router lane records as `auditor` (console) | `console/server.py:963` | 115-test set | **GREEN — defect 1** |
| M13 | auditor loses `chat_id` | `cli/build.py:1055` | 115-test set | **GREEN — defect 1** |
| M14 | auditor loses `cycle_id`/`round` | `cli/main.py:1521` | 115-test set **and the full 2555-test suite** | **GREEN — defect 1** |
| M15 | chat lane loses `chat_id` | `cli/talk.py:31` | 115-test set | **GREEN — defect 1** |
| M16 | `prices:` never reaches the ledger | `cli/build.py:74` | 115-test set | **GREEN — defect 1** |
| M17 | ZH countdown drops its units | `page.py:countdownText` | 115-test set | **RED** |
| M18 | pill colour ignores fired alarms | `page.py:budgetState` | 115-test set | **RED** |

Every mutation was reverted with `git checkout -- <file>`; the worktree is clean.

## Observations (not defects)

- `summary()` now ships `attribution` in every state frame: up to 50 run / 50 cycle
  / 50 chat buckets plus 200 per-call `turns`, recomputed over the whole ledger.
  Roughly 30 KB added to each SSE snapshot on a busy project. Worth a glance if the
  console ever feels heavy.
- `budget_warning_state` builds its `active` rows with `used=0, budget=0`, so every
  `budget.fired[*].percent` on the wire is `0`. Nothing renders it today.
- `/api/usage/rollup` returns each project's absolute `root` path. Local-only and
  never rendered, but it is more than the table needs.
- `resilience.py:259` sets `rate_limit_reset_at` when *any* route was rate-limited,
  while `rate_limited` requires *all* of them; `providerResetLine` keys off the
  former, so a mixed 429 + 500 exhaustion can still say "Provider limit reached".
