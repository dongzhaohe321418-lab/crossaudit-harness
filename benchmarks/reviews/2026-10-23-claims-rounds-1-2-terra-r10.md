# Cross-vendor review — this release's changes (feat/tui-first), round 10

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 179bb7b (the round-9 repair: the two-phase ruling with a local intent, foreign rows listed and never applied, the reworded README and CHANGELOG), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-9 sequences; ask whether the intent itself opens anything (a stale or forged intent, the clearing paths, a crash between phases, the binding of the nonce to the row). **Run by:** the Claude lead, 2026-10-24. **Verdict:** the requested sequences verified; DO NOT MERGE on three P1 (a commit that lands but whose confirmation read fails clears the intent as if no commit occurred; a failing `rev-parse` reads as "no commit yet"; the confirmation and the recovery do not bind the nonce, the action and the reason hash to the committed row) and one P2 (D176's older wording still says "failure-atomic transaction"). The repairs and round 11 are recorded in `…-r11.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P1** — [state.py:676](src/crossaudit/controller/state.py:676), [state.py:677](src/crossaudit/controller/state.py:677), [rulings.py:458](src/crossaudit/rulings.py:458): a successful commit followed by a failed `_confirm_committed()` clears the intent as though no commit occurred. `git commit` has already landed before the `cat-file` confirmation at line 461; the broad `except BaseException` then removes and persists removal of the intent. On the next resolve there is no local nonce to reconcile, so it writes a second, possibly opposite, ruling.  
  Reproduction: make the post-commit `cat-file blob HEAD:cycles/rulings.jsonl` fail once. The first call refuses, but leaves a committed row; the next `resolve` creates another row. The new one-shot test only injects `cat-file` during *later recovery after a phase-3 state failure*; it does not cover this confirmation-readback path.  
  Fix: distinguish “commit definitely did not land” from “commit landed but confirmation failed.” Preserve the intent for every post-commit uncertainty, and recover strictly on the next ruling.

- **P1** — [rulings.py:483](src/crossaudit/rulings.py:483)-[486](src/crossaudit/rulings.py:486): `committed_rows(strict=True)` treats every failed `git rev-parse --verify -q HEAD` as “no commit yet.” That includes a corrupt/unreadable HEAD or a transient Git failure, not just an unborn repository. It returns `[]`, after which [state.py:657](src/crossaudit/controller/state.py:657)-[676](src/crossaudit/controller/state.py:676) clears a pending intent and proceeds to a new ruling.  
  I directly injected `128, "", "fatal: corrupt HEAD"` into that Git call; strict mode returned `[]`. This reintroduces the round-9 “unreadable means no pending ruling” fail-open before `ls-tree`/`cat-file`.  
  Fix: only accept a positively identified unborn HEAD as empty; in strict mode turn all other non-zero results into `rulings_unreadable`. Add a one-shot `rev-parse` failure regression following a post-commit state-write failure.

- **P1** — [rulings.py:295](src/crossaudit/rulings.py:295)-[316](src/crossaudit/rulings.py:316), [state.py:638](src/crossaudit/controller/state.py:638)-[650](src/crossaudit/controller/state.py:650): the committed-row check does not verify `intent` (nor the other intent fields), despite claiming to confirm “this ruling.” I directly called `_confirm_committed` with a committed JSON row whose `intent` was changed from `controller-nonce` to `forged-nonce`; it accepted it.

  A clean filter/hook can therefore alter the nonce while preserving the four compared fields. Phase 3 still applies the state change and records the original nonce, although the committed evidence does not carry it. Worse, recovery matches only `cycle_id` and nonce; it never checks that `action` equals the local intent or that `sha256(reason)` equals `reason_sha256`. A writer of `.crossaudit/state.json` can pair a forged pending intent with a committed row and cause that row’s action to apply. `locks.py` expressly says the lock does not protect against a writer of `.crossaudit/`; the state file is not an authenticated authority boundary.

  Fix: compare the complete canonical row, including `intent`, in `_confirm_committed`; during recovery require cycle, nonce, action, reason hash, and valid resolution action to match the stored intent. Add hook/filter and forged-local-intent regressions. The existing nonce test only tests a direct `record()` call with no matching current intent, not a changed committed row.

- **P2** — [DECISIONS.md:8376](docs/DECISIONS.md:8376), [DECISIONS.md:8397](docs/DECISIONS.md:8397): D176 still says the ruling is a “failure-atomic transaction” and “one transaction,” while ruling 30 correctly describes two phases joined by local intent. This contradicts ruling 32’s statement that those claims were replaced “here.”  
  Fix: mark the original D176 heading/ruling as superseded or reword them to the current two-phase protocol. The README and CHANGELOG use the newer, more accurate shape.

## Requested sequence checks

The new tests reproduced the intended repaired cases:

- Barrier race: exactly one ruling commit and final state matches it in both lock orders.
- One-shot recovery `cat-file` failure: refusal says, “the committed rulings log could not be read …; no ruling is made until it can be”; the intent remains and the next attempt reconciles.
- Hand-written row: it is listed as “ruling row in the ledger not made by this controller (<sha>)”; the explicit ruling adds exactly one new row.
- Legacy cycle without `escalated_at`: reconciliation succeeds through the nonce path.
- Post-commit state failure: the refusal says the ruling “was committed to the ledger as <sha> … the next ruling on this cycle applies the committed ruling”; the same action reconciles and the opposite action applies the committed close then refuses.

Those checks do not cover the post-commit confirmation-read failure above, nor the `rev-parse` failure or modified-intent cases.

I read in full: `AGENTS.md`, `src/crossaudit/controller/state.py`, `src/crossaudit/rulings.py`, and `tests/test_ruling_two_phase_intent.py`. I also reviewed the relevant D176/D175 decision-record sections, README/CHANGELOG ruling text, status rendering, Chinese denial catalogue, and related ruling tests. The worktree remained unmodified.

Focused test commands run:

```text
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_two_phase_intent.py
# 10 passed

... tests/test_ruling_reconciled_from_ledger.py -k 'not console'
# 9 passed, 1 deselected

... tests/test_resolve_commits_the_ruling.py
# 13 passed

... tests/test_ruling_log_and_lock_round3.py
# 4 passed

... tests/test_kernel_held_locks.py
# 15 passed

... tests/test_evidence_ledger.py
# 12 passed
```

I also ran the i18n/denial checks: 68 passed, 1 loopback-console test deselected. The initial attempt at that one HTTP case failed only because this sandbox rejects `127.0.0.1` binds (`PermissionError: EPERM`), as expected.

VERDICT: DO NOT MERGE — committed-ruling recovery still has fail-open paths and the nonce is not actually bound to the committed row