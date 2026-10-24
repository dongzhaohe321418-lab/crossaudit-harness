# Cross-vendor review — this release's changes (feat/tui-first), round 13

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at f38e4db (the round-12 repair: ruling rows signed with the project key and bound to the escalation's receipt-commit identity; recovery from committed and verified rows), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-12 sequences; ask whether the signing opens anything, whether a key rotation strands rulings, and whether any way is left for two committed rulings on one escalation through CrossAudit's own paths. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-12 repair verified for every covered case; DO NOT MERGE on one P1 (the residual D176 had recorded as Open: a mutable `ruling_intents` entry still decides whether a verified `reopen` is recovered or is a new escalation, so a writer of the state file can obtain two signed `reopen` rows for one escalation) and two P2 (README and CHANGELOG say "instead of writing a second one" and imply every line is signed; a key rotation or loss strands existing signed rows, with no keyring). The repairs — escalations committed as signed rows so the identity is durable, no implicit key recreation once signed artefacts exist, the two documents qualified — and round 14 are recorded in `…-r14.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P1 — `src/crossaudit/rulings.py:781-785` and `src/crossaudit/controller/state.py:647-654`**  
  A mutable `ruling_intents` entry still decides whether a verified `reopen` is recovered or treated as a new escalation. This permits two committed rulings for one escalation through the normal ruling path.

  Reproduced: force phase-3 state-write failure after `reopen`, then add that committed row’s nonce to `state.json`’s `cycles[cid]["ruling_intents"]`. A second `rulings.rule(..., "reopen", ...)` commits another row rather than reconciling the first:

  ```
  AFTER_FIRST ESCALATED … e23fcce730ef
  SECOND OPEN 2
  ROWS [('reopen', ''), ('reopen', 'e23fcce730ef')]
  ```

  The first refusal correctly says: “the ruling on cycle … was committed to the ledger as …, but the cycle's state could not be written …”. But after tampering, two signed `reopen` rows exist without a new committed escalation.

  This is acknowledged at `docs/DECISIONS.md:8853-8858`, but it remains a merge blocker under the requested “no two committed rulings on one escalation” property. Fix by making escalation identity durable/committed, or fail closed by never treating a verified `reopen` as a new escalation based on mutable state.

- **P2 — `README.md:1019-1024`, `CHANGELOG.md:48-52`**  
  Both say the next ruling recovers the committed ruling “instead of writing a second one,” and imply every ruling line is signed. The P1 sequence writes a second row, and legacy lines are deliberately unsigned and merely listed as unverified. This overclaims behavior.

  Fix: qualify these statements to newly written rulings and disclose the documented residual until it is removed.

- **P2 — `src/crossaudit/crypto/keys.py:50-96`, `src/crossaudit/rulings.py:673-680`**  
  Key rotation/loss strands existing rulings. Verification uses only the current private-seed-derived public key; `keyid` is not a keyring lookup. Replacing/removing the old seed and creating a new key makes old signed rows fail recovery as “no valid signature.” There is no rotation record or retained public-key history.

  Fix: either explicitly make rotation unsupported and refuse replacement/implicit recreation for an existing project, or implement an append-only, authenticated public-key history and key-transition mechanism.

## Requested verification

The round-12 repair itself works for the covered cases:

- Altering/removing the pending intent or adding the obsolete `rows_before` cursor after a post-commit `close` is ignored; the signed committed row is applied and no second commit is made. The tested refusal is: “a committed ruling (close, `<sha>`) already stands for cycle `<cid>`; the state's now reflects it.”
- Shaping local intent to an unsigned foreign row is refused by name: “a committed ruling for cycle … carries no valid signature from this project; nothing was applied, and no new ruling is made until the repository is repaired.”
- Different-key and signature-stripped current-escalation rows are refused; legacy earlier-escalation rows are listed as unverified and a new ruling adds exactly one row.
- A missing/unusable signing key fails closed: “the project signing key at …/ed25519.seed is not available (…); a ruling must be signed, so none was made.” No row or pending intent is written.

The private seed defaults to `.crossaudit/signing/ed25519.seed`, created mode 0600 under a mode-0700 signing directory; `CROSSAUDIT_SIGNING_KEYFILE` can override it. A principal that can read that seed and write the repository can forge accepted rulings. That is the same trust boundary as receipt signing, not a new protection against the key holder. A foreign `escalation_commit` does not apply through normal paths because recovery requires equality with the Git-derived current identity; a key holder with repository control can nevertheless sign a row for that identity.

D176 accurately discloses the remaining duplicate-`reopen` case; D175 is not implicated. README and CHANGELOG overstate it as noted above.

Read in full: `src/crossaudit/rulings.py`, `src/crossaudit/crypto/keys.py`, `src/crossaudit/crypto/ed25519.py`, `tests/test_ruling_signed_rows.py`, `tests/test_ruling_uncertainty_reads.py`, `tests/test_ruling_intent_binding.py`, and `tests/test_ruling_two_phase_intent.py`. I also inspected the affected controller, CLI/i18n, denial catalogue, README, CHANGELOG, D176 rulings 40–42, and the remaining requested tests.

Tests run:

- Requested six-file command: **57 passed, 1 environment error**. The error was `test_a_genuinely_unborn_repository_reads_as_no_rows`, whose console fixture cannot bind loopback in this sandbox (`PermissionError: [Errno 1] Operation not permitted`).
- Non-HTTP rerun of the other five requested files: **48 passed, 1 deselected**.
- `tests/test_ruling_signed_rows.py`: **9 passed**.
- `tests/test_denial_strings_are_legible.py tests/test_cli_i18n.py -k 'not console_serves_the_refusal_in_both_languages_on_the_wire'`: **58 passed, 1 deselected**.

VERDICT: DO NOT MERGE — mutable `ruling_intents` still permits two signed committed reopen rulings for one escalation