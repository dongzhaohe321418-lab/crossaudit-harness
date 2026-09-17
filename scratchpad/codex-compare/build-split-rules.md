# Split rules: one committed rulebook, two projections

Worktree `/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-split`,
branch `feat/split-rules`, off `fusion/evidence-authority` @ `dc446ae`.

## The measured cause (RESULTS-2.md)

Two defects, one file:

* auditor round-one recall against CLEAR = **2.0 %** (4/201) under the shipped
  generic constitution; a stronger auditor model buys 3.8 %; **rubric-derived
  rules buy 15.5 %**. Precision is 100 % in every arm.
* the same file reaches the generator (`run_loop` -> `generator.build_prompt(
  task=…, constitution=…)`), and those same rubric-derived rules dropped B′'s
  **round-one draft from 14.7 to 3.3 F1** on the shared ten instances.

So the constitution cannot serve both roles: what the auditor needs (specific,
checkable, exhaustive criteria) is what the generator pattern-matches into
headings.

## How it reaches each side today (read before designing)

| where | what happens |
|---|---|
| `cli/build.py:678` | `constitution = (cfg.root/cfg.constitution).read_text()` — one string |
| `cli/build.py:779` | `gen_mod.generate(task=…, constitution=constitution, …)` |
| `generator.py:375` | `"THE RULES YOUR WORK IS JUDGED BY"` + `<<<RULES {constitution} RULES` — **verbatim** |
| `auditor/prompt.py:build` | `CONSTITUTION @ {commit}` + `<<<CONSTITUTION {constitution} CONSTITUTION` — **verbatim** |
| `receipt/build.py:build` | binds `constitution_path`, `constitution_sha256` (of the committed bytes), `constitution_commit`, `prompt_sha256` (the auditor prompt) |
| `receipt/verify.py:420` | re-reads the committed blob at the pinned commit and refuses a hash mismatch |

One string, two consumers, one binding. Nothing in the receipt says *which
text each side received* — because until now there was only one.

## The change

**The committed rules file stays the single artefact** a human edits, that the
ledger binds and the receipt cites. Nothing is split on disk. What each role
*receives* becomes a **projection** of it — a pure, deterministic function of
the committed bytes, so no new authority enters and the binding survives.

`constitution.py` (not a kernel dir) gains:

* `criteria_projection(text) -> text` — **the identity function.** The auditor's
  view is unchanged *by construction*: it still receives every committed byte of
  the rulebook, and `auditor/` is not touched at all. This is the whole reason
  the auditor half of the fix is free: a rubric-grade rules file already gives
  the auditor 15.5 %; what stopped anyone shipping one was the generator.
* `brief_projection(text) -> text` — the **writer's brief**: the rulebook's own
  preamble, the full text of every *shape* rule, and a bare roster (id +
  severity) of every remaining rule, under a fixed sentence saying their
  criteria are the reviewer's and are not an outline to write to.

A rule is a *shape* rule if it is the reserved `CA-TASK-001` (protocol law about
the deliverable's shape: count, format, named subject, inclusions, length) or if
its block carries the marker `<!-- brief -->`. Unmarked rules are acceptance
criteria and reach the auditor only. The marker is an HTML comment, so a
rulebook stays a document a person reads, and the default is the direction the
measurement points: a criterion body does not reach the writer unless a human
says it describes the work rather than grades it.

The projection is applied **inside `generator.build_prompt`**, not at the call
site, so no caller — build loop, console, app — can hand a writer the criteria
by accident. Findings are unchanged: a BLOCKED round still returns the auditor's
specific observations to the generator, which is the mechanism B′ showed
produces targeted repairs.

Shipped templates are curated once: `GENERAL_AUDIT_RULES.md` marks
`CA-USABILITY-001` (locate/open/use — shape), `AUDIT_RULES.md` marks
`CA-META-001` (declares `metadata.yml` + `results.json`) and `CA-REPRO-001`
(carry the command, environment and seed). `CA-TASK-001` needs no marker.

### The binding survives, and now says which text each side got

`receipt/build.py` already receives `constitution_bytes`. It attaches an
additive top-level `projections` block:

```json
"projections": {"auditor":    {"name": "criteria", "sha256": "…"},
                "generator":  {"name": "brief",    "sha256": "…"}}
```

Both digests are recomputed by `verify.py` **from the blob it just re-read at
the pinned commit** and a mismatch is refused — so the block is re-derived, never
trusted. `schema.py` validates it when present, so every receipt already written
still verifies (absence is legal). `prompt_sha256` continues to bind the exact
auditor prompt. A receipt therefore still proves what was judged and against
what, and now also proves what the writer was told.

### Kernel rules held

`auditor/ broker/ ledger/ policy/ dcl/` are untouched. The auditor still sees
only committed bytes — the identity projection is those bytes. Verdict synthesis
is not touched. The receipt still binds the constitution commit; the new block is
additive and re-derived.

### The cost, stated

A rule whose body no longer reaches the writer is a rule the writer can only
learn about by being blocked once. That is a real round-cost trade, it is why
the marker exists, and the study measures rounds.

---

# The measurement

Frozen at `3fa9b65` before the run; nothing changed after a score was read.
Arms S and R ran the tip `dc446ae`, arm X ran `3fa9b65`. Same task, same corpus,
same seed `20260930`, same 20 samples, same settings, same models.
Full results: `benchmarks/expertlongbench/RESULTS-3.md`.

## The headline

| | arm S (shipped) | arm X (split) | paired Δ |
|---|---:|---:|---:|
| **round-one draft F1** (must not fall) | 19.8 | **21.8** | **+2.04** (p = 0.54, n = 20) |
| **auditor round-one recall vs CLEAR** | **2.0%** (2/100) | **23.5%** (23/98) | ~12× |
| auditor precision | 100% (2/2) | 73% (33/45) | down |
| **final F1** | 16.4 | **10.3** | **−6.11** (p = 0.15, n = 20) |
| mean rounds | 1.30 | 2.15 | |
| cost / instance | $0.118 | $0.230 | |

**The draft held and the audit works.** Arm S independently reproduces study 2's
2.0% on a fresh seed, which is the best evidence that the defect was structural.

## The arm that isolates the change

Arm R = rubric rules on the **shipped** code. Rules held fixed, code varied:

| comparison | round-one draft F1 | paired Δ |
|---|---|---:|
| S → R (the poisoning, reproduced) | 22.2 → 4.2 | **−18.06** (0 better, 2 worse of 4) |
| **R → X (the split alone)** | 4.2 → **28.2** | **+24.07** (3 better, 0 worse of 4) |

Arm R is n = 4: capped at 5 for budget before its scores were read, then its
fifth instance died on a provider SSL failure and was not resumed. Direction and
size only — no p-value earns anything on four pairs. But the mechanism needs no
model call to verify: arm R's writer was handed 3343 bytes containing six
transcribed grading criteria; arm X's was handed 1384 bytes containing none.

## What does not help, and why

Arm X's **final** output is 6.11 F1 below arm S's. The cause is measured, and it
is not the constitution. Pooled over all three arms:

> **25 revisions, mean paired −11.01 F1 (SE 2.47), p = 0.0014 exact, rubric items
> fixed 3, broken 17.**

Study 2 saw −3.40 at p = 0.32 and could not settle it. It is settled now. Arm X's
auditor fires on 16 of 20 instances instead of 5, so it triggers 16 revisions
instead of 5, at −14.42 F1 each. The split did not make revision worse; it made
the loop revise more, and revision was already bad. Arm S's own five revisions
averaged −13.56 with 0 items fixed and 3 broken.

**The constitution is no longer the binding constraint. Revision is.**

One lead, worth four revisions against sixteen and nothing more: arm R's
revisions averaged **+5.83** and broke nothing. R and X had the same findings and
differ in what the generator saw *while revising* — R had the cited rule's full
criterion, X had the brief. The brief is right for a blank page; the cited rule's
criterion may be right at revision time, where there is no outline to
pattern-match into. Directly testable, and the obvious follow-on.

## Honest costs

- **Precision fell**, 100% (2/2) → 73% (33/45): twelve confirmed false positives.
  The old 100% had a CI spanning two thirds of the range, so this is the first
  measurement large enough to mean anything rather than a regression from an
  established number — but the direction is down and the count is real.
- **1.95× the cost per instance, 2.1× the wall time.** An auditor that finds
  things sends work back.
- A rule whose body no longer reaches the writer is one the writer can only learn
  about by being blocked once. That is why `<!-- brief -->` exists.

## Spend

$8.44 of $12 — arm S $2.36, arm R $1.48, arm X $4.60.

## Incidents, disclosed

Both arms hit the same environmental failure: `[SSL: UNEXPECTED_EOF_WHILE_READING]`
exhausting every configured route inside CLEAR scoring, through the machine's
HTTP proxy.

- **Arm R** died on its fifth instance and was **not** resumed → reported at n = 4.
- **Arm X** died after 15 of 20 recorded instances and was resumed with `--resume`
  (study 2's Deviation 21b mechanism; it only decides which seeded samples still
  need running). The code was not modified — `3fa9b65` before and after — the
  first 15 records predate the resume byte for byte, and **no score was read
  between the crash and the resume.**

## Verification

Full suite **2733 passed / 2 skipped**, 0 regression, +23 new tests
(`tests/test_constitution_projections.py`, `tests/test_receipt_projections.py`).
A receipt minted during arm X carries `projections` with the auditor's digest
equal to its own `inputs.constitution_sha256` — the identity, proven in the
ledger rather than asserted in a comment.
