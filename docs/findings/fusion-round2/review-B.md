# Review B — evidence authority (D148 slices B+C), commits 030d531..dd9f8b4 at f050cbd

Reviewer: independent. Worktree `scratchpad/wt-review-B` (detached f050cbd), `crossaudit.__file__` confirmed inside it. Base worktree `scratchpad/wt-review-B-base` at 50349f9 for byte-identity comparison. No tracked file was left modified (`git status --porcelain` clean after every mutation).

## Verdict: NEEDS CHANGES

The kernel contract holds (default dial is a proven identity over every ladder path; old receipts byte-identical; suite green at 2191 passed). What needs changing is narrower: one dead guard with a false mutation claim, a decision_id that is minted but never checked (so most of the block is not actually bound), two defensive branches nothing bites, and two user-facing sentences that leak internal constants into the terminal the owner reads.

## Defects (numbered, actionable)

1. **`src/crossaudit/auditor/authority.py:173-174` — `not confirmed_blockers` is dead in production and its test's mutation claim is false (D10).**
   In `run_audit` (`run.py:301-321`) `model_decided` is set only in the `elif reply:` branch, which is reached only when `total_hard_failures == 0`; `hard_failures` counts every BLOCKER finding (`dcl/framework.py:112`), so `model_decided and confirmed_blockers` is unreachable. Mutation M1 (delete the guard) survives all three target files and the tests that claim to catch it (`tests/test_evidence_authority.py:92-93` docstring names `test_..._keeps_blocking`; `:105` `test_escalate_dial_does_not_touch_a_deterministic_block`) both pass `model_decided=False`, so they test the other conjunct.
   Fix: either drop the conjunct and state the invariant in a comment (model_decided implies no confirmed blocker), or keep it and add a unit test with `model_decided=True` + `DCL_BLOCKER` + `lone_model_blocker="escalate"` asserting BLOCKED, and rewrite the two docstrings to name a mutation that actually reddens them.

2. **`src/crossaudit/auditor/authority.py:260-306` — `decision_id` is minted over the partition, rationale, dial and route (`:197-210`) but `validate_block` never re-derives it, so everything outside `evidence` is unbound.**
   Tamper matrix on a real PASS receipt (validate + verify both OK, i.e. NOT caught): advisory id moved to `blocking_evidence_ids`; advisory id moved to `contested_evidence_ids`; id duplicated; `decision_id` replaced; `rationale` replaced with "Everything is fine, trust me."; `lone_model_blocker` flipped block→escalate; extra key smuggled into the block. The report's Evidence section prints the rationale, so a doctored sentence reaches the reader through a receipt that "verifies".
   Fix: in `validate_block`, rebuild the `decision_payload` dict exactly as `decide_authority` does (factor it into one helper) and compare `_identifier("authority", payload)` to `raw["decision_id"]`; reject unknown keys (`set(raw) - required`). Add the moved-id and rationale tampers as tests. (Note honestly in the docstring that both digests are unkeyed self-checks; tamper-evidence against a recompute comes from `receipt_digest` in the state store and the DSSE sidecar, not from this block.)

3. **`src/crossaudit/receipt/schema.py:158-161` — the `workflow_verdict == audit.verdict` binding has no test.** Mutation M7 (`if False:`) survives the three target files. `test_a_non_receipt_route_is_a_shortfall_and_admit_refuses` (`tests/test_evidence_authority.py:344`) describes this tamper in its docstring but never performs it.
   Fix: add a test that sets `authority.workflow_verdict="BLOCKED"` and `route="bounded-revision"` (internally consistent) on a PASS receipt and asserts `validate()` raises with "differs from audit verdict".

4. **`src/crossaudit/receipt/verify.py:576-579` — `admit()`'s route refusal is unreachable and untested.** Mutation M9 survives: the only test (`test_evidence_authority.py:353`) reaches `admit()` with a BLOCKED receipt, which the pre-existing verdict check at `:572` already refuses. Given `validate_block` binds route→verdict and `schema.validate` binds verdict→`audit.verdict`, `route != "receipt"` implies `verdict != "PASS"`, so this branch can never fire on a validated receipt.
   Fix: delete the branch (D141/D146: code that names a capability the tests cannot exercise), or make it reachable and test it; do not leave it as an untested "defense".

5. **`src/crossaudit/auditor/authority.py:226-228, 245-246, 250-252` — internal constants in sentences the terminal now prints.** `_rationale`'s docstring says "never an internal word", yet it emits `NOTHING_AUDITED`, `INVALID_REPLY`, `BOUNDS_EXCEEDED`, `PROVIDER_FAILURE`, `NON_EVIDENTIAL_PROVIDER` verbatim. `cli/main.py:1766-1769` (`cmd_run`) now prints `Escalated: The round is escalated because audit integrity is BOUNDS_EXCEEDED.` where it printed `Escalated: a human decision is needed` before, and `cmd_audit` (`:1053-1054`) appends the same as `why:`. The scope sentence also claims the round "is recorded as NOTHING_AUDITED" even when integrity is already PROVIDER_FAILURE (ladder keeps the earlier integrity), so it can be false. `tests/test_evidence_authority.py:118` pins the constant into the sentence, so the fix must move that assertion too.
   Fix: map each integrity to a plain clause ("the change was larger than the auditor could read in full", "the auditor's reply could not be read", "the model audit could not run", "an empty scope: nothing to audit", "a fixture provider cannot bless a commit") and pass `integrity` to the scope sentence rather than hard-coding NOTHING_AUDITED. Assert on the plain clause.

6. **`src/crossaudit/auditor/authority.py:147` — `claim` copies the model's observation verbatim into the receipt with no bound.** A 3 MB observation (accepted by `validate_reply`) produced a 3,000,898-byte `authority` block, committed, digested and signed into the ledger. The report already carries the full text; the receipt should carry a bounded claim.
   Fix: truncate `claim` to a fixed byte budget (e.g. 512 bytes + a marker) and record `claim_sha256` of the full observation if the full text must be bound.

7. **`src/crossaudit/auditor/authority.py:112-113` — `evidence_id` is not an identifier.** Two identical findings hash to the same id (`['ev-0c7a51a63e74f298', 'ev-0c7a51a63e74f298']`), so `advisory_evidence_ids` carries duplicates and the ids no longer name one record each.
   Fix: include the record's ordinal in the identifier payload; assert uniqueness in `validate_block`.

8. **`src/crossaudit/receipt/build.py:260` — the falsy-empty case (`authority={}` from the dataclass default) is not pinned.** Mutation M11 (`if authority is not None:`) survives the three target files; a hand-built `AuditOutcome` flowing through `cmd_audit` would then write `"authority": {}` and `schema.validate` would refuse the receipt with "authority block is missing [...]". `test_a_receipt_without_the_block_is_byte_identical_and_verifies` passes `authority=None` only.
   Fix: parametrize that test over `None` and `{}`.

9. **Product/UX (minor, batch as one change).**
   - `| evidence policy | \`crossaudit-evidence-authority-v1\` |` is a version string in the summary table of every report; nobody reading a report acts on it. Keep it in the receipt, drop it from the report (only the route row is verify-bound).
   - Route names `bounded-revision`, `human-decision`, `obtain-audit`, `receipt` appear as the human row. Acceptable only because verify binds it; consider a plain label column beside it ("goes to automatic revision", "needs a person", "no model audit ran", "ready for a receipt").
   - DCL_ONLY reports say the same thing twice ("No model audit ran; this is a deterministic-tier result only." then, in Evidence, "No model audit ran, so this is a deterministic-tier result and cannot pass on its own.").
   - The `verified` column reads as "this finding is false" for a model row; "reproduced by a check" says what it means.
   - The ZH catalogue in `console/page.py` lacks the new escalate sentence (builder disclosed; must land before the dial is documented).
   - `records_from_audit` raises `AttributeError` on a non-dict finding (only reachable by direct callers; `validate_reply` gates `run_audit`). `render_report` raises `KeyError` on an authority row missing `finding_key`/`artifact` (internal input only). Both are fine to leave, worth a `Mapping` guard if the function is meant to be public.

## What was proven (no defect)

- **Default dial is the identity.** Enumerated 14 ladder paths (escalation_lock ±DCL, DCL hard failure ±model, unstarted scope, invalid reply, bounded, model PASS/BLOCKED/ESCALATE, offline, provider failure ±DCL, non-evidential PASS): `decide_authority(..., lone_model_blocker="block").workflow_verdict == verdict` for every one, `contested_evidence_ids == ()`. Under `"escalate"` exactly `model_BLOCKED` changes (→ ESCALATE, one contested id). Structural reason: the flip requires `model_decided`, set only in the `elif reply:` branch after lock/DCL/scope/invalid/bounded have all been passed.
- **Old receipts verify unchanged.** Same fixed-input receipt (no authority) built and verified under 50349f9 and f050cbd: identical key set, canonical bytes equal modulo `verifier.code_digest_sha256` (expected — the verifier's own code changed), fixture constitution hash and run-specific shas; `verify()` evidence identical (`verified=True`, same shortfall list, same derivations).
- **Digest binding catches:** edited claim (both validate and verify: "authority evidence digest does not match its records"), route↔verdict mismatch, `requires_human` disagreement, `workflow_verdict` vs `audit.verdict` (validate) and vs the report route row (verify), unknown policy version by name, ids not in the block, empty rationale. Messages are clear.
- **Hostile replies through `run_audit`** (finding not a dict, `severity` as list/dict, `findings: null`, nested observation, non-string artifact, `a@b@c` artifact, duplicated findings, 3 MB observation): none crash; invalid shapes land on ESCALATE/INVALID_REPLY with a valid empty block; the receipt round-trips and validates. `render_report` with a `finding_key` lacking `@` renders the whole key.
- **`dcl_source_digest()` cost:** 0.32 ms/call (8 files, 35 KB) — negligible.
- **Config error text** ("authority.lone_model_blocker must be 'block' (bounded revision, the default) or 'escalate' (a person decides at round one)") is plain and names both options. `--json` gains `authority: {policy_version, route, lone_model_blocker, blocking_evidence_ids, contested_evidence_ids}` only when a block exists. The ESCALATE sentence "the auditor raised a concern that no deterministic check reproduces; it needs your judgment" is plain and classifies as `audit`.
- Default runs are one table row pair + one short section noisier; nothing fails more.

## Test counts

- Full suite at f050cbd, foreground in the review worktree: **2191 passed, 2 skipped, 1 warning** in 329 s.
- Target files at f050cbd: `test_evidence_authority.py` 27, `test_finding_states.py` 17, `test_loop_integrity.py` 36 (80 total; the builder's 29/23/33 were counted at dd9f8b4 before the later merges).
- Scratch review tests (deleted after the run): 40 passed (28 ladder cases, tamper matrix, 9 hostile replies, direct-call and report probes); compat dump 1+1.

## Mutation log (each applied to src, three target files run, then `git checkout --`)

| # | mutation | result |
|---|---|---|
| M1 | authority.py: drop `and not confirmed_blockers` | **SURVIVED** (defect 1) |
| M2 | authority.py: skip evidence-digest compare | RED: `test_authority_evidence_digest_detects_mutation`, `test_a_receipt_with_authority_verifies_and_a_tampered_claim_is_refused` |
| M3 | verify.py: drop route-row compare | RED: `test_verify_binds_the_route_row_of_the_report` |
| M4 | verify.py: drop `validate_block` call | RED: `test_a_receipt_with_authority_verifies_and_a_tampered_claim_is_refused` |
| M5 | run.py: pass `"block"` instead of `cfg.authority.lone_model_blocker` | RED: 3 (run, stop-reason, loop round-one) |
| M6 | config.py: accept any dial | RED: `test_config_rejects_an_unknown_dial` |
| M7 | schema.py: drop workflow_verdict↔audit.verdict binding | **SURVIVED** (defect 3) |
| M8 | verify.py: drop route admission shortfall | RED: `test_a_non_receipt_route_is_a_shortfall_and_admit_refuses` |
| M9 | verify.py: drop `admit()` route refusal | **SURVIVED** (defect 4) |
| M10 | cli/main.py: return "" instead of the contested sentence | RED: stop-reason test, loop round-one test |
| M11 | build.py: `if authority is not None:` | **SURVIVED** (defect 8) |
| M12 | authority.py: drop ids⊆evidence check | RED: `test_ids_must_be_within_the_evidence` |
| M13 | authority.py: rationale ignores `scope_started` | RED: `test_an_unstarted_scope_never_yields_the_receipt_route[DCL_ONLY]` |

9 of 13 mutations bit; the 4 survivors are defects 1, 3, 4, 8 above.
