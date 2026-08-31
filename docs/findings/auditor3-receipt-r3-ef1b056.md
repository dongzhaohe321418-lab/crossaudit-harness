# Codex audit — `audit/receipt-remaining-r2` at `ef1b056`

Auditor: auditor3 (Codex). The branch is Claude-authored; this review supplies
the requested cross-vendor audit. No feature code was written.

## Verdict

`MERGE` — S0: 0, S1: 0, S2: 0, S3: 2.

The S0 from `9f54b81` is closed. Checks and skills are re-derived from the Git
object cited by the receipt, not the verifier's working directory. The DCL
source digest has no cited source object in receipt schema v2; this branch
honestly reports a comparison with this installation and never turns that
comparison into a denial.

## Target and instrument identity

- `audit/receipt-remaining-r2` resolves to
  `ef1b056fc9cb90d65e13a025ae913e37b563707a`, exactly the dispatched SHA.
- Verification ran from detached checkout
  `/tmp/crossaudit-audit3-ef1b056-20260831`; HEAD was exact and the tree was
  clean before and after the audit.
- The shared interpreter was
  `/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python`.
- Before measuring, the harness asserted that imported `crossaudit` was
  `/private/tmp/crossaudit-audit3-ef1b056-20260831/src/crossaudit`, not the
  installed package.
- Full suite: 1,756 collected, 1,754 passed, 2 skipped, 0 failed.

## The four receipts that exhibited the S0

I executed the shipped `crossaudit verify` path against the four existing,
signed, controller-recorded receipts, rather than constructing receipt dicts:

| Receipt digest | Subject | Result at `ef1b056` |
|---|---|---|
| `0c9f3a51b379796d` | `55f5218ef015` | bindings verified, signature verified, recorded |
| `18af4424d49803db` | `55f5218ef015` | bindings verified, signature verified, recorded |
| `cd51ab2d2081c572` | `8bc31d6ae79a` | bindings verified, signature verified, recorded |
| `fc01f83346d72ea4` | `8bc31d6ae79a` | bindings verified, signature verified, recorded |

Every receipt reported checks and skills derived from its cited commit and
reported `OTHER CHECK LAYER` for the historical DCL digest. None was denied.
The two latest receipts also remained `ADMISSION READY`.

As a separate producer-to-consumer exercise, I minted four new receipts through
the real `cmd_audit` path. All 4/4 had valid detached signatures, exact
controller-history records, and verified through `cmd_verify`. The cases were:

1. clean baseline — checks corroborated;
2. working `crossaudit.yml` edited after mint — cited checks still corroborated;
3. working `crossaudit.yml` edited before honest mint — divergence reported,
   receipt still verified;
4. an uncommitted skill added before honest mint — divergence reported, receipt
   still verified.

For the forged direction, I changed a real receipt's checks claim to `schema`
and changed the uncommitted working file to agree. The committed-object
derivation still returned `diverged`; the working file could not corroborate
the forgery. The full CLI would reject the edited receipt even earlier because
its digest is not the controller-recorded receipt.

## Mutation proof: `reverted_reddens=3/3`

Each mutation changed production code, not test input, and was restored before
the next mutation.

1. `_committed_config_bytes` reverted to
   `(audit_root / crossaudit.yml).read_bytes()`:
   `test_checks_are_rederived_from_the_cited_commit_not_the_working_tree`
   failed with `CHECKS_CITED_OBJECT_GUARD`, observing `corroborated` instead of
   `diverged`.
2. `_committed_skills` reverted to `skills.load(audit_root)`:
   `test_skills_are_rederived_from_the_cited_commit_not_the_working_directory`
   failed with `SKILLS_CITED_OBJECT_GUARD`, again observing `corroborated`
   instead of `diverged`.
3. DCL `local-differs` reverted to an `IntegrityDenial`:
   `test_the_check_layer_digest_is_reported_against_this_installation_never_denied`
   failed with `DCL_DIGEST_IS_NOT_A_DENIAL_GUARD: verification refused this
   receipt`.

After restoration, those three named tests passed 3/3, `git diff --exit-code`
was clean, and HEAD still equalled the dispatched SHA.

## Gap accounting and hash #9

- #10 checks: closed at the consumer against `<cited>:crossaudit.yml`.
- #11 skills: closed at the consumer against `<cited>:skills/`, over the whole
  manifest.
- #9 DCL source: not re-derived; `hash9=real-limit` and `gaps=2/3`.

The receipt carries only `inputs.dcl_source_sha256`. The audited science tree
does not contain CrossAudit's installed DCL sources; `verifier.version` is only
a label; `verifier.code_digest_sha256` is a non-invertible digest of the whole
package; and no repository, commit, path, build artifact, or attestation locates
the minting DCL bytes or loaded plugin sources. A verifier can compare its own
installation, but cannot recover the cited producer object because no such
object is cited. The separate vocabulary in `verify.py` and the CLI —
`local-match` / `local-differs`, rendered as `SAME/OTHER CHECK LAYER` — states
that limit honestly.

## Findings

### S3-1 — the format-limit warning is not colocated with the schema field

`receipt/schema.py:26-27` declares `dcl_source_sha256` as a required input with
no note that the field is a mint-time self-report lacking an addressable source
object. The durable explanation is in the consumer at
`receipt/verify.py:284-291`; the full falsification write-up is under the shared
`_handoff/` directory and is not part of this branch's product/documentation
tree.

This does not make current verification wrong, but it weakens the explicit goal
that a later schema change must not quietly treat the gap as unfinished
verifier work. Put the constraint beside the schema declaration or in committed
product documentation. This is non-gating because runtime behavior and copy are
already honest.

### S3-2 — a committed profile name is re-expanded through the verifier's local table

`receipt/verify.py:84-92` resolves a committed `checks: general` through the
current installation's `dcl.profiles.PROFILES` (`profiles.py:24-50`). Therefore
the source is not only the cited Git object: it is the cited object plus mutable
release-local state.

Executed on an actual signed/controller-recorded profile receipt: its checks
were `corroborated`; after adding one member to the in-process `general` profile
table, the unchanged receipt and unchanged repository reported `diverged`.
That is an honest historical receipt made to look drifted solely by a verifier
release. It cannot recreate the S0 today because divergence only reports and
never denies, hence S3. It becomes blocking if these rows are ever promoted to
enforcement without recording the historical profile expansion or treating the
receipt's concrete checks as authoritative.

## Cleared suspicions and limits of this verdict

- The cited commit is first checked for existence in the audit repository;
  separate-repository absence becomes `not-derivable`, not a read from the
  science repo or the local working directory.
- Skills are compared as a whole manifest. Empty and subset claims cannot
  silently corroborate a non-empty committed tree, and both shipped digest
  conventions are identified rather than blended entry by entry.
- A DCL mismatch does not alter `admission_shortfalls`; admission retains the
  existing whole-package identity check at the point where identity must hold.
- The console does not render `input_derivations`. The documented receipt
  verification command and the changed user-facing renderer are CLI surfaces,
  so I did not charge frozen/console parity to this branch. This verdict stops
  at the verifier result and shipped CLI renderer; it establishes no browser
  DOM, accessibility-tree, or frozen-application parity.
- I did not rebuild the DMG or execute plugin-loaded verification. The
  plugin-source call graph was read, while the decisive honest-history result
  was executed on historical receipts whose DCL digest differed across builds.

## Independence disclosure

Vendor independence is strong for the production review and mutation work:
Codex audited Claude-authored code. My weakest conclusion is S3-1's durability
grade, because it predicts where a future schema maintainer will look rather
than describing a current runtime failure. The S0 closure, both working-file
directions, all three mutation reds, and S3-2's release-local profile drift are
based on executed producer/consumer paths.
