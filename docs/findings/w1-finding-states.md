# w1 — a finding can now say what became of it

Per D38. Branch `feat/finding-states` off `v5-redesign@3af0317`.

## 1. Constraint 3 answered before the field was written

**Old receipts still verify, and the reason is structural rather than lucky.**
Checked first, because the brief said to stop if it could not be done:

* **findings are not in the receipt.** `receipt/build.py` binds
  `report_sha256` and a manifest; it has no findings key at all.
* **`verify.py` does not re-derive findings.** It compares `dcl_source_sha256`
  — a digest of the check layer's own source — never a recomputed finding set.
* **the report is built from named keys** (`severity`, `rule`, `artifact`,
  `check`, `observation`), not from a dict dump, so a new key does not move
  `report_sha256`.

So the field lands where it costs history nothing. A guard asserts findings stay
out of `receipt/build.py`, because the day they enter it, every receipt already
written stops verifying.

## 2. The states, and the two honest defaults

    alleged      raised, nothing yet establishes it
    confirmed    a human or a deterministic check established it
    fixed        the artefact changed and it no longer reproduces
    withdrawn    the raiser retracted it
    overridden   a human ruled against it, on the record
    unresolved   rounds ended with it neither established nor retracted

**Deterministic findings are `confirmed`.** That layer is verdict-in-code:
`hard_failures` is computed without consulting any model and the audit ladder
reads it *before* the model's verdict. Demoting it into an allegation would give
up the distinction the states exist for.

**Model findings are `alleged`.** Raised, with nothing yet establishing them —
which is what makes a confirmation rate computable later.

## 3. The symptom, both runs

    RUN A — a deterministic check fires
      {"artifact": "increment", "rule": "DCL:schema", "severity": "BLOCKER",
       "state": "confirmed", "tier": "deterministic"}

    RUN B — a model raises a finding
      {"artifact": "experiments/demo/results.json", "rule": "CA-DATA-001",
       "severity": "BLOCKER", "state": "alleged", "tier": "model"}

Both from `findings.json`, a sidecar in the cycle directory.

## 4. Where the states live, and why not the report

The report is what a person reads, and constraint 2 says no user-facing surface
renders these words. So the record is a sidecar: not rendered, not receipt-bound.
A guard asserts no state word appears in the report renderer or the console.

## 5. Nothing decides with it

`total_hard_failures` still counts severity and nothing else; the verdict ladder
is untouched. A guard reads `dcl/framework.py`, `auditor/run.py`, `cli/main.py`,
`receipt/build.py` and `receipt/verify.py` and fails if any of them **branches**
on a state — a slice that both introduces the states and changes what they gate
is two changes, and the second cannot be reviewed while the first is moving.

## 6. `a defect was caught` is out

It became checkably false the moment a finding can be `alleged`. Replaced with
**`a concern was raised`** — what the system actually knows — not a softer word
for the same claim. Its Chinese entry moved with it: the stale
`"a defect was caught":"发现了一处缺陷"` would otherwise have translated a string
nothing renders.

## 7. Mutations — 6 of 6 red, anchor-confirmed

    F1  deterministic findings demoted to alleged     RED (2 tests)
    F2  model findings claim to be established        RED (2 tests)
    F3  the slice starts gating on the state          RED  constraint 1
    F4  the states are put into the receipt           RED  constraint 3
    F5  the dashboard claims a defect again           RED  constraint 4
    F6  the states stop being persisted               RED

F6 first ran as an **error rather than a failure** — my patch left the file
syntactically broken, which tests nothing. Rewritten as a clean removal of both
write sites; it then reddened by name.

## 8. One test fixture completed rather than worked around

`test_cycle_binding.py` built a `SimpleNamespace` stand-in for `AuditOutcome`
without `model_reply`. It stayed green only because nothing read that field. It
is read now, and the honest fix is the fixture: a fake missing a field the real
type always has is a fake that can hide a defect. I did not reach for
`getattr(outcome, "model_reply", None)` — tolerating an absent field in
production to keep a test passing is the pattern this codebase has spent the
night removing.
