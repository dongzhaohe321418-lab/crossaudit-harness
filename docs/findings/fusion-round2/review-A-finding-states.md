# Review A — feat/finding-states merged at 50349f9 (base v5-redesign e87b297)

Worktree: scratchpad/wt-review-A (detached 50349f9). Import path verified to the worktree src.

## Verdict: NEEDS CHANGES

Full suite (`pytest tests/`): **1 failed, 2070 passed, 2 skipped** (320 s).
The failure is caused by this change (see defect 2). Targeted runs:
`tests/test_finding_states.py` 17 passed; `test_console_translation_boundary.py`,
`test_console_strings_by_execution.py` pass.

## Defects (numbered, actionable)

1. **`findings.json` is written but never staged — it leaks into the next science commit.**
   `src/crossaudit/cli/main.py:1005` (cmd_audit, `--write-ledger`) and `:1677` (cmd_run)
   `git add` only `receipt.json`/`checks.json`/`report.md` (+ dsse/reproduction/sources
   sidecars). The new sidecar is left untracked in the science repo. Reproduced end-to-end
   with the replay provider (scratch test, two rounds): after round 1 `git status` shows
   `?? cycles/<sha>-r1/findings.json`; the round-2 increment commit then swept it in because
   the generator's commit tool does `git add -A` (`src/crossaudit/broker/tools_git.py:67`),
   so a ledger file lands inside a *science* commit. Round 2's own sidecar stays untracked.
   Side effects: cmd_run prints "uncommitted changes exist" on every later run; console
   setup of an existing working repo refuses on `workspace_dirty`
   (`console/projects.py:1617`); nothing pushes the sidecar to the ledger remote.
   Fix: add `str(rel / "findings.json")` to both `git add` calls (fail-open like the other
   sidecars if you prefer), and add a test that drives `cmd_run` and asserts
   `git ls-files cycles` contains it and `git status --porcelain` is empty.

2. **Suite is red: D106 guard-name rule.** `tests/test_finding_states.py:98`
   `test_no_user_facing_surface_renders_a_state_word` claims a rendering outcome but its body
   only reads `page.py` source; `tests/test_guard_names_match_what_they_check.py::test_no_test_name_claims_an_outcome_its_body_does_not_check` fails. The author's write-up says 6/6 mutations
   red but the full suite was evidently not run. Fix: rename to what it checks
   ("page markup declares no state word") or, better, make it behavioural (defect 3).

3. **The "no user-facing surface" and "report does not carry the state" guards are
   source-string greps and do not bite on the real property.** Probes, all GREEN:
   - M5: `render_report` made to append `f"Status: {f.get('state')}"` → report text contains
     `Status: confirmed`; `test_the_report_does_not_carry_the_state` (`tests/test_finding_states.py:107`)
     still passes because it only looks for the quoted literal in a source slice.
   - M6: `overview.py` note changed to `"alleged"` (dashboard renders it) → passes; the guard
     (`:98`) only scans `console/page.py`, and exempts `"fixed"` entirely (`:103`).
   Fix: assert on rendered output — `render_report(...)` with a DCL failure + model reply,
   and `overview.metrics(...)`/the server payload for a blocked cycle — contain no
   `FINDING_STATES` word (case-insensitive, whole-word so "fixed" can be handled honestly).

4. **The state word does reach the model and the receipt-bound prompt digest.**
   `src/crossaudit/auditor/prompt.py:171` embeds `json.dumps(dcl)` in the auditor prompt;
   with `Finding.state` in `as_dict()` every deterministic finding now ships
   `"state": "confirmed"` to the auditor (verified: `'"state": "confirmed"' in prompt` → True),
   and `prompt_sha256` (bound in the receipt) changes for identical inputs. Old receipts still
   verify (verify.py never re-derives the prompt — checked `receipt/verify.py:296-330`), so the
   kernel rule holds, but `dcl/framework.py:57-58` ("INTERNAL … nothing renders these words")
   and the test name `test_the_state_never_reaches_a_receipt_or_its_digest` (`:118`) overstate.
   Fix: either project `state` out of the DCL JSON handed to the model, or say so in the
   write-up/test name and add a guard that the auditor prompt contains no state word.

5. **`finding_states()` (`src/crossaudit/auditor/run.py:45-66`) does not itself set the
   deterministic default.** Row state is `f.get("state", "")` — the CONFIRMED claim lives only
   in the dataclass default; any DCL dict without the key yields `""`, which is not a member of
   `FINDING_STATES`, and nothing validates membership. Also `artifact` defaults differ
   (`""` deterministic vs `"?"` model). `model_reply=None` and findings missing
   `artifact`/`rule` are handled (validate_reply guarantees dict findings with a known rule).
   Fix: `f.get("state") or CONFIRMED` for the deterministic tier (or assert membership) and one
   artifact default.

## Checked and found acceptable
- Merge resolution of `dcl/framework.py`: diff against each parent is exactly the other side's
  addition; `NOTHING_TO_AUDIT`, `scope_started`, `CheckResult.started` and `FINDING_STATES`
  all present; `Finding.state` is a trailing defaulted field (additive, positional ctors safe).
- Sidecar write is `write_text` like report.md/checks.json (consistent, none atomic).
  Nothing enumerates ledger contents: verify.py and `receipt/reproduction.py` are receipt-driven;
  no packaging manifest lists cycle files; no test asserts an exact ledger file set.
- Mutations that bite: M1 deterministic→ALLEGED (2 red), M2 model→confirmed (2 red),
  M3 both sidecar writes removed (1 red), M4 dashboard copy reverted (1 red),
  M7 state key dropped from deterministic rows (1 red). Tree restored (`git checkout -- .`).
- Copy: "a concern was raised" / "提出了一处疑虑" — clear, non-alarming, ZH entry present,
  stale entry removed; no other reference to the old string outside comments/docs. It
  under-claims for deterministic blocks (those are established), but is never false.
- Cost to a normal user beyond defect 1: one extra small file per cycle; `checks.json`
  gains a `state` key per finding; no new error paths.
