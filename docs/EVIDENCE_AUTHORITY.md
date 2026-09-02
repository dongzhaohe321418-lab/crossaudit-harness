# Evidence authority

Where a finding's power to block comes from, and how the receipt proves it.

This is the fused form of two lines of work (D148): the `codex/evidence-governance-fusion`
proposal (an admission policy plus a repair guard) and the v5 line's decisions
D141–D147 (advisory-only constitutions, finding states, an honest empty scope).
The aim is the same on both sides: **a model's opinion is useful evidence, but it
is not, by itself, an instruction to patch.**

## The two tiers

```text
untrusted proposal plane
  generator artifact
       ├── registered deterministic checks   (tier: deterministic — CONFIRMED)
       └── cross-vendor semantic auditor      (tier: model         — ALLEGED)
                         |
                         v
trusted derivation plane
  verdict ladder (auditor/run.py, code only)  ->  evidence authority (auditor/authority.py)
                         |
          +--------------+--------------+----------------+
          |              |              |                |
        PASS          BLOCKED        ESCALATE         DCL_ONLY
       receipt    bounded-revision  human-decision   obtain-audit
```

A deterministic finding is emitted by a registered check over committed bytes:
it is **verified**. A model finding is a reading of the same bytes by an auditor
of a different vendor: it is **raised, not yet reproduced**. Both appear in the
report's `Evidence` table with their tier and whether they were verified by a
check. That
table is what a dual-source audit adds over a single model review: the reader can
see which findings rest on a reproducible check and which rest on a judgment.

## The verdict is decided by code, then recorded with its evidence

The verdict ladder in `auditor/run.py` is unchanged and remains the only place a
verdict is synthesised:

    escalated cycle            -> ESCALATE   (an escalated cycle is not routed around)
    DCL hard failure           -> BLOCKED    (dominates any model opinion)
    unstarted scope            -> ESCALATE   (NOTHING_AUDITED: an empty scope is not clean)
    invalid or failed audit    -> ESCALATE
    prompt bound exceeded      -> ESCALATE
    no model ran               -> DCL_ONLY
    otherwise                  -> the model's own verdict

`auditor/authority.py` runs **after** the ladder and derives from its result:

- the route the workflow must take (`receipt`, `bounded-revision`,
  `human-decision`, `obtain-audit`); the report writes it in plain words
  ("admission", "another revision round", "your decision", "a model audit is
  still needed") and the verifier maps the words back;
- the partition of the evidence into blocking, contested and advisory ids;
- a rationale of one or two plain sentences — never an integrity code, a route
  name, a record id or a finding state (the terminal prints the first one);
- a digest over every evidence record, and a decision id over every other field.

Under the default configuration it never changes the verdict. The receipt's
`authority` block is therefore a record of *why*, bound to the report and to the
receipt digest, not a second judge.

## The dial: what a lone model BLOCKER does

```yaml
authority:
  lone_model_blocker: block      # default
```

| value | behaviour |
|---|---|
| `block` (default) | A model-only BLOCKER goes back to the generator for the bounded revision rounds, exactly as before. The receipt records the blocker as **unverified**, so a confirmation rate can be measured. |
| `escalate` | A model-only BLOCKER stops at round one and becomes a human decision. The generator is not asked to patch a finding no check reproduces. This is the codex proposal's behaviour, opt-in. |

The default stays `block` because D142 ruled that the Observe-style default
does not become the default on argument alone; finding states now make the
confirmation rate computable, and the number will decide. Either way a
deterministic failure blocks and an escalated cycle stays escalated: the dial
cannot weaken the floor or the lock.

## The repair guard

Whatever the dial, a revision that follows a BLOCKED audit is screened before it
is committed (`repair_guard.py`, wired in `cli/build.py`). The screen is a
heuristic — a handful of patterns over the staged diff — and it is named for
what it does: it **surfaces likely defensive edits to the auditor**. It is not
a guarantee that a finding cannot be hidden; the auditor is.

Two kinds of outcome:

**Refusals** — the round is rolled back (files and index), the generator gets
the audit's findings again plus one sentence on what was refused, and one free
retry; a second refusal ends the run with cause `repair_refused` and a Decision
Center card. Only two things are refused, in every mode, because nothing
downstream could review them:

- a file outside the audited directories (`scope.dirs`) — the whole increment
  is in scope, not just the artifacts a finding named, because an honest repair
  routinely touches the data *and* the prose that describes it. The generator's
  `apply` is the first line for this boundary (it denies the write before
  anything is staged, and that refusal too keeps the audit's findings in the
  retry prompt); the screen is the second, over what reached the index;
- a binary the local document renderer did not produce.

**Cautions** — the round is committed and audited as usual; the caution rides
along as a deterministic note (`dcl.notes`, in the auditor's prompt and in the
round's `checks.json`) so the auditor model can raise it as a finding, and the
run shows a `repair_caution` event:

- on **code files only** (never data — JSON, YAML, TOML, INI, CSV, notebooks —
  and never documents): a catch-all `except`, an error handler that does
  nothing, `contextlib.suppress`, a checker-silencing marker (`noqa`,
  `type: ignore`, `pragma: no cover`, ...), a warnings filter set to ignore, a
  skipped or expected-to-fail test, an assertion that can no longer fail, a
  shell step that ignores its own failure — matched on added lines with
  comments, docstrings and string literals stripped first;
- a **deleted** `assert`, `raise` or test that was not re-added — deleting the
  failing check is the classic evasion;
- a code change larger than `repair.max_changed_lines` (default 200; data and
  documents are never budgeted);
- staged files the screen could not read because the diff passed its size cap.

`repair.mode` is the dial: `caution` (default) is the behaviour above;
`refuse` turns every caution into a refusal for projects that would rather
stop than let the auditor weigh it. Prose is never pattern-screened: a report
that discusses a fallback strategy is not defensive programming (D121), and a
guard that reddens honest work is as much a defect as one that misses
defective work.

```yaml
repair:
  enabled: true
  mode: caution          # or refuse
  max_changed_lines: 200
```

## Receipt and verification bindings

New receipts carry an optional `authority` block:

- `policy_version` (`crossaudit-evidence-authority-v1`; unknown versions are refused, known older ones stay verifiable);
- `decision_id`, `workflow_verdict`, `route`, `requires_human`, `lone_model_blocker`;
- `blocking_evidence_ids`, `contested_evidence_ids`, `advisory_evidence_ids`;
- `evidence` (one record per finding: key, severity, tier, state at verdict time, the first 400 characters of the claim plus `claim_sha256` of the full text, artifact, producer, producer digest) and `evidence_digest`;
- `rationale`.

The verifier re-derives the evidence digest and the decision id (so a moved id,
a rewritten sentence, a flipped dial or an added key is caught), checks that
every id names exactly one record, that the route matches the verdict and the
verdict matches the receipt's, and that the report's `evidence route` row says
the same thing in words. Both digests are unkeyed self-checks; tamper-evidence
against a recompute comes from the receipt digest in the controller store and
the signed sidecar. A non-`receipt` route is an admission shortfall; `admit`
needs no route check of its own, because a validated receipt with such a route
cannot carry a PASS verdict.
A receipt without the block is byte-identical to one written before this work
and verifies exactly as before. `RECEIPT_SCHEMA` stays 2.

## What is deliberately not here

- **No consensus rule.** The proposal's "two producers and two mechanism
  families" path is unreachable today: the only verified records are
  deterministic ones, which already block. A rule that names a capability the
  code lacks is a D141/D146 defect. `POLICY_VERSION` reserves the slot; the first
  candidate second producer is the broker's tool evidence, which is already
  digest-bound.
- **No second status vocabulary.** The verdict is the status. Route names are
  internal and never reach the console's main surface.
- **No filtering of what the generator sees.** Under the default dial every
  finding is returned, with the dispute sentence D144 kept: the generator may
  fix, or say why the finding rests on a misreading.

## Code map

- `crossaudit.auditor.authority` — evidence records, derivation, block validation
- `crossaudit.auditor.run` — the ladder, then the derivation; the `Evidence` report section
- `crossaudit.receipt` — the optional block, its validation and its report binding
- `crossaudit.repair_guard` / `crossaudit.cli.build` — the guard and its one-retry wiring
- `crossaudit.config` — `authority:` and `repair:` sections
