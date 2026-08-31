# w1 — F2 (S0): a corrupt evidence ledger became a signed tool-free receipt

Per D38. Branch `fix/receipt-evidence-fail-closed` off `v5-redesign@5181512`.
Audit-core change; §1.1 applies and this is strictly more fail-closed.

## 1. The symptom, executed before and after

`run_audit` denies a broken chain at its own seam, so a whole-cycle probe never
reaches this — my first attempt at reproducing it was denied by the auditor and
proved nothing. The finding is at the **builder**, a separate entry point that
assembles a receipt from an audit that has already run. Driven there:

    BEFORE
      ledger present       : True
      ledger verifies      : False | entry 0 digest mismatch (content tampered)
      receipt construction : SUCCEEDED
      tool_evidence block  : ABSENT
      signed               : True
      -> a tampered chain, signed as an audit that used no tools

    AFTER
      ledger present       : True
      ledger verifies      : False | entry 0 digest mismatch (content tampered)
      receipt construction : DENIED — the evidence ledger for this project is
                             present and does not verify, so a receipt cannot be
                             signed for it
      -> the symptom is absent

## 2. The shape, and what the docstring was doing

`_tool_evidence()` returned `None` for *no ledger*, *empty ledger*, *failed
verification* and *any exception alike*, and its docstring promised the function
"can never break receipt assembly". That promise is what justified the collapse:
absence and failure funnelled through one value, so the builder could not tell
them apart and omitted the block either way.

**A builder must not soften a denial into an absence.** The broker already
refuses a broken chain, and it is the same chain.

## 3. The three states are values, not conditions

    EVIDENCE_ABSENT   no ledger, or a ledger with zero entries   -> no block
    EVIDENCE_INTACT   verifies, at least one entry               -> bind head+count
    EVIDENCE_BROKEN   present and does not verify, or unreadable -> DENY

`_tool_evidence()` returns a frozen `ToolEvidence(state, block, reason)`. The
call site denies on `EVIDENCE_BROKEN` with `IntegrityDenial`, binds on a block,
and writes nothing otherwise. A test asserts the three constants are distinct
values, so renaming the defect rather than fixing it fails by construction.

**A present, unreadable ledger is BROKEN, not absent**: we cannot establish that
no tools ran, and *cannot establish* must never render as *did not happen*.

## 4. Backward compatibility and the honest case

An honest tool-free cycle still mints a receipt with **no** `tool_evidence`
block, so its bytes and digest are unchanged — asserted, not assumed. Denying
absence to catch corruption would have been the worse trade and the manager
ruled it out in advance; a guard holds that too, and mutation E4 (absence made
an error) reddens on it.

The only new denial covers a case that previously produced a false signed
receipt. Strictly more fail-closed, additive, no schema change.

## 5. Mutations — anchored, and one of them corrected me

Every mutation asserts its anchor and fails loudly if the patch does not apply,
because a mutation that silently fails to apply reports the same thing as a
guard that works.

    E1  broken collapses back into absent                RED  (4 tests)
    E2  the denial softened into an omission             RED
          test_a_tampered_ledger_denies_receipt_construction
          test_the_denial_is_not_softened_into_a_warning
    E3  a present unreadable ledger treated as absent    RED  (after a fix)
    E4  absence made an error, denying the honest case   RED

**E3 was green on the first run.** My "unreadable ledger" test wrote garbage
bytes — which `verify()` handles and reports as not-ok, so it never entered the
`except` branch the mutation deleted. The branch was unguarded and the file
still passed. It now puts a directory where the ledger belongs, which makes the
read genuinely raise, and E3 reddens by name.

That is the second time tonight an anchored mutation found a guard of mine that
could not fail, and both times the anchor assertion is what separated "the guard
works" from "the patch missed".

## 6. What this does not cover

* **Severity is not mine to settle.** auditor3 flagged F2's grade as its own
  weakest point; a second security reviewer is confirming it. This is built for
  an S0 and the fix does not depend on the grade.
* **Other collapsed-`None` sites are not swept.** This closes the one the audit
  reproduced. The same shape may exist elsewhere in the receipt path, and a
  sweep of "functions whose `None` means two things" is worth commissioning
  separately rather than my widening this branch.
* Cross-vendor adversarial review is required before merge (§0, audit core).


---

## S3 from the cross-vendor review — my own tautology, on the signing path

The review closed the S0 and found one thing in my fix:

    assert sign_receipt(cfg, receipt, cdir) is not None or True

`X or True` is true for every possible result. The auditor changed
`sign_receipt()` to return `""` before creating any sidecar and **the named test
still passed** — so a test called
`test_an_honest_tool_free_receipt_still_builds_and_signs` was guarding the build
half and nothing about signing.

**Fourth instance of this class tonight**, and the second of them mine. The
others were an unused `inspect.getsource()`, thirteen names claiming behaviour
their bodies did not check, and a coexistence check red by construction. A guard
that cannot fail is worse than no guard: it holds the slot a real one would take
and it reports success.

**Replaced with the property, not a stronger-looking expression.** The test now
requires a non-empty key id, a sidecar on disk, a non-empty sidecar, a
verification that reports `signed` and `verified`, and a key id that matches the
one signing returned. A second test requires the signature to bind **this**
receipt: altering the receipt after signing must stop it verifying, because a
sidecar that verified against anything would satisfy the first test.

**Mutated on the thing it names**, not on the surrounding code:

    G1  sign_receipt returns "" before any sidecar   RED  (the auditor's own)
    G2  the sidecar signs a fixed digest, not this receipt  RED
    G3  a key id is returned but no sidecar is written      RED

All three redden `test_an_honest_tool_free_receipt_still_builds_and_signs` by
name, and each mutation asserts its anchor and fails loudly if it does not land.
Nothing outside `sign.py` was touched, so the test is guarding signing and not
something adjacent to it.
