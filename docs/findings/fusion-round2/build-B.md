# Build B+C — evidence authority (D148 slices B and C)

Branch `fusion/evidence-authority`, base 50349f9. Worktree
`/Users/ericdong/Documents/Crossaudit/crossaudit_integ` (note: the real
directory name is lowercase; a capitalised `PYTHONPATH` trips
`test_these_guards_ran_against_the_tree_under_test`, which is a path-case
artefact and not a product failure).

## Commits

| sha | what |
|---|---|
| 030d531 | `auditor/authority.py` (EvidenceRecord, decide_authority, validate_block), run.py wiring after the ladder, `AuditOutcome.authority` default, report rows + Evidence section, `config.authority.lone_model_blocker` |
| ad938da | receipt: optional `authority` block (`build`), `schema.validate` runs `validate_block` + verdict binding, `verify` binds the `| evidence route |` row, shortfall + `admit()` refusal |
| 6ae9769 | cli: both `build_receipt` sites, `--json` summary, contested-blocker stop reason, one rationale sentence on ESCALATE |
| 5bf151b | JSON-shaped block (lists), `verify()` re-derives the block for dict receipts, CLI tolerates SimpleNamespace outcomes |
| a70d303 | tests: `tests/test_evidence_authority.py` (29 tests) + loop-integrity escalate-dial variant |
| dd9f8b4 | finding-states follow-up (review A, all five defects): sidecar staged in cmd_audit/cmd_run + cmd_run clean-tree test; the two "no state word" guards now assert on `overview.*` output and `render_report()` text (M5/M6 redden); `auditor/prompt.py` projects `state` out of the DCL JSON the model sees + prompt test; `finding_states()` defaults a DCL row to CONFIRMED and refuses an unknown state; receipt guard renamed honestly (`test_a_receipt_without_the_authority_block_carries_no_state_word`) |

## Full suite at a70d303 (foreground, PYTHONPATH lowercase)

`1 failed, 2098 passed, 2 skipped` in 335 s. The one failure is
`tests/test_guard_names_match_what_they_check.py::test_no_test_name_claims_an_outcome_its_body_does_not_check`,
pre-existing from the finding-states merge (review A defect 2); it is fixed in
the follow-up below. B7 subset: 335 passed before the follow-up.

## Full suite at dd9f8b4 (foreground, after the follow-up)

`2099 passed, 2 skipped, 1 warning` in 326 s — green. Targeted:
`test_finding_states.py` 23, `test_evidence_authority.py` 29,
`test_loop_integrity.py` 33 (incl. the new escalate-dial round-one test),
`test_guard_names_match_what_they_check.py` green. Six follow-up mutations
(M5 report state, M6 overview note, prompt json.dumps(dcl), findings.json
dropped from git add, `f.get("state", "")` default, block written when
authority is None) each turned exactly their guard red.

## Design deviations from the spec

- `decide_authority` also refuses an unknown dial or verdict with `ValueError`
  (cheap, and keeps a typo in config from silently meaning "block").
- `validate_block` additionally checks `requires_human == (route == human-decision)`,
  the dial value, and that `rationale` is non-empty.
- `verify()` re-runs `validate_block` on the dict it is handed (the loader
  already validates files), so a tampered claim is refused by `verify` and not
  only by `schema.validate`.
- `AuthorityDecision.as_dict()` emits lists (not tuples) so the in-memory block
  equals the JSON-loaded one; `validate_block` accepts either.
- The escalate-dial stop reason is a module constant `CONTESTED_MODEL_BLOCKER_REASON`
  in `cli/main.py`; `classify_escalation_kind` reads it as `audit`.
- The report's Evidence table shows `verified yes/no` (never a state word);
  the report keeps `| evidence route | **X** |` because verify binds it.

## Left undone / handoffs

- ZH translation for the new escalation sentence lives in `console/page.py`
  (the regex catalogue near line 3613); that file is owned by another builder.
  Sentence: "the auditor raised a concern that no deterministic check
  reproduces; it needs your judgment". No console test fails without it (the
  sweep covers `console/*.py` literals only).
- Follow-up note: `prompt_sha256` for new receipts changes (the model no
  longer sees `"state"`); `verify.py` never re-derives the prompt, so every
  receipt already written verifies unchanged. Replay transcripts are keyed by
  prompt and are recorded per test, so none shipped in the tree broke.
- Incident: while killing my own stale background pytest I ran
  `pkill -f "pytest -q -p no:cacheprovider tests/"`, which also matched and
  killed another builder's suite run in `scratchpad/wt-held-fixes` (pid 14581,
  log `codex-compare/full-suite-held-fixes.txt`). That run needs re-running.

## Review fixes (review-B.md, 9 items) — commit ae00a1c on top of d6f1b5a

| # | fix | guard (mutation run red) |
|---|---|---|
| 1 | dead `and not confirmed_blockers` removed; invariant stated in a comment (model_decided ⇒ total_hard_failures == 0) | docstrings now name `drop model_decided` / `drop verdict == "BLOCKED"`; `test_escalate_dial_does_not_touch_a_deterministic_block`, `test_escalate_dial_leaves_a_model_pass_alone` |
| 2 | `_decision_payload()` shared by `decide_authority` and `validate_block`; `decision_id` re-derived over every field but `evidence` (represented by `evidence_digest`); unknown keys, repeated ids, non-unique evidence ids refused | `test_decision_id_binds_every_field_outside_the_evidence` (moved id ×2, rationale, dial, decision_id, smuggled key, repeated id) — `if False:` → red |
| 3 | — | `test_the_block_verdict_is_bound_to_the_audit_verdict` — M7 → red |
| 4 | `admit()` route branch **deleted**: after (2)+(3) a validated receipt with a non-`receipt` route cannot carry PASS (both doctorings refused by `validate`), so the branch was unreachable | same test; comment in verify.py says why |
| 5 | `INTEGRITY_IN_WORDS` map; rationale never carries a code; scope sentence under PROVIDER_FAILURE says both; CLI `Escalated:` prints the plain sentence | `test_no_rationale_carries_an_integrity_code` (7 integrities × 4 verdicts × 4 flag sets × 2 record sets), `test_an_unstarted_scope_under_a_provider_failure_says_both_plainly`, `test_the_cli_escalated_line_is_plain_words` — code back in a sentence → 16 red |
| 6 | `claim = observation[:400]` + `claim_sha256` (new `EvidenceRecord` field) | `test_a_claim_is_bounded_and_the_full_text_is_hashed` → red when unbounded |
| 7 | ordinal in the id payload; `validate_block` rejects non-unique ids | `test_two_identical_findings_are_two_records` → red without ordinal |
| 8 | — | `test_a_receipt_without_the_block_is_byte_identical_and_verifies[{}]` — M11 → red |
| 9 | report: no `evidence policy` row; route row renders `ROUTE_LABELS` (admission / another revision round / your decision / a model audit is still needed) and `verify` maps back through `ROUTE_FROM_LABEL` (unknown label refused); DCL_ONLY rationale reworded so "No model audit ran" appears once; column header "verified by a check"; `docs/EVIDENCE_AUTHORITY.md` updated | `test_report_carries_the_route_in_plain_words_and_an_evidence_section`, `test_a_dcl_only_report_says_the_model_audit_is_missing_once`, `test_verify_binds_the_route_row_of_the_report` |

Full suite at ae00a1c, foreground: **2312 passed, 2 skipped, 1 warning** (341 s).
`test_evidence_authority.py`: 148.

ZH strings for the lead (the only i18n mechanisms are `cli/i18n.py` and the
`console/page.py` regex catalogue, both owned elsewhere):
- "the auditor raised a concern that no deterministic check reproduces; it needs your judgment"
- route labels: "admission", "another revision round", "your decision", "a model audit is still needed"
- rationale sentences in `auditor/authority.py::_rationale` and `INTEGRITY_IN_WORDS`
  (the CLI prints `Escalated: <first sentence>`; `cmd_audit --json`-less output prints `why: <first sentence>`).
