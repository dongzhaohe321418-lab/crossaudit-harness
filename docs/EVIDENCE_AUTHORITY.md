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
report's `Evidence` table with their tier and whether they are verified. That
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
  `human-decision`, `obtain-audit`);
- the partition of the evidence into blocking, contested and advisory ids;
- a rationale of one or two plain sentences;
- a digest over every evidence record, and a decision id over the whole block.

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
is committed (`repair_guard.py`, wired in `cli/build.py`):

- files outside the artifacts the findings named (a missing or unclear artifact
  widens the scope to the whole increment);
- a change-size budget over code files (`repair.max_changed_lines`, default 200;
  documents are exempt from the budget, never from the scope);
- on **added lines of code files only**: broad or bare `except`, silent `pass`,
  new retry / fallback / best-effort paths, `noqa` / `type: ignore` style
  suppressions, disabled or skipped tests;
- binary patches that the local document renderer did not produce.

Prose is never pattern-screened: a report that discusses a fallback strategy is
not defensive programming (D121). A refusal rolls the attempt back, tells the
generator in one sentence what stopped and why, and allows one free retry. A
second refusal ends the run with cause `repair_refused` and a Decision Center
card that says what to do next. The guard is a review trigger, not a theorem
that every flagged construct is wrong: a person may approve a broader change.

```yaml
repair:
  enabled: true
  max_changed_lines: 200
```

## Receipt and verification bindings

New receipts carry an optional `authority` block:

- `policy_version` (`crossaudit-evidence-authority-v1`; unknown versions are refused, known older ones stay verifiable);
- `decision_id`, `workflow_verdict`, `route`, `requires_human`, `lone_model_blocker`;
- `blocking_evidence_ids`, `contested_evidence_ids`, `advisory_evidence_ids`;
- `evidence` (one record per finding: key, severity, tier, state at verdict time, artifact, producer, producer digest) and `evidence_digest`;
- `rationale`.

The verifier re-derives the evidence digest, checks that every id names a record,
that the route matches the verdict, and that the report's `evidence route` row
says the same thing; `admit` refuses a receipt whose route is not `receipt`.
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
