# w1 — an empty scope is neither a pass nor a failure

Per D38. Branch `fix/empty-is-not-failed` off `v5-redesign@63fc064`.
Audit core: strictly more fail-closed, additive, no schema change.

## 1. The symptom, executed on a fresh project

Source mode, clean `HOME`, `init` then `check`, nothing else:

    BEFORE
      deterministic layer over …/experiments (working tree)
      verdict: BLOCKED  (2 hard failures)
        [BLOCKER] DCL:schema increment: no results.json in the audited scope
        [BLOCKER] DCL:schema increment: no metadata.yml in the audited scope

    AFTER
      Nothing to check yet — this command reviews work you have added, and
      there is none here so far.
        Add a folder under experiments/ with your results, then run this again.

And the case that must not move, driven immediately after by adding one file:

      verdict: BLOCKED  (2 hard failures)          exit 10
        [BLOCKER] DCL:schema increment: no metadata.yml in the audited scope
        [BLOCKER] DCL:schema …/results.json: results.json has no 'quantities' list

## 2. Three states, decided once

    scope                              verdict
    has an increment, files malformed  BLOCKED            unchanged
    has an increment, files missing    BLOCKED            unchanged
    no increment at all                NOTHING_TO_AUDIT   new

`CheckResult.started` is computed in `run_checks` and the verdict is decided in
`as_dict()`, so every consumer reads the same one rather than re-deriving it.
`scope_started` is additive on the payload; a caller that never sets it keeps
the previous two-state behaviour exactly.

**`scope_started()` errs deliberately toward "started"**: saying started when it
is not keeps today's behaviour, while saying not-started when work exists would
hide a real failure. A `results.json` or `metadata.yml` anywhere, or any file
below the scope root, counts as started. Only an empty scope — or one holding
just the scaffold README `init` wrote — is unstarted.

## 3. The weakening guard, which mattered more than the sentence

An unstarted scope produces **zero hard failures**, and the audit verdict ladder
in `auditor/run.py` decides `BLOCKED` from exactly that count. Without an
explicit branch it would have fallen through the model tier and could have
reached **PASS** — an empty directory becoming a route to a clean verdict, which
is worse than the alarming message this replaces.

So the ladder consults `scope_started` before any PASS is assigned, and an
unstarted scope becomes `ESCALATE` with integrity `NOTHING_AUDITED`: nothing was
audited, and a person owns that. Driven: `audit --offline` on a fresh project
returns ESCALATE, not PASS and not BLOCKED.

Two guards hold this, and they are the first two in the file: an empty scope
cannot produce `PASS`, and the ladder must still consult `scope_started`.

## 4. The words

No `DCL:schema`, no `audited scope`, no `BLOCKER`, no `hard failures`, no
`verdict` — asserted by a test over the shipped strings, not by reading them. It
says what the command is for, that it has nothing to look at, and what would
give it something.

**Chinese, as part of the change.** The new verdict token reaches the console,
which already translates `PASS`/`BLOCKED`/`ESCALATED`, so `NOTHING_TO_AUDIT`
would have rendered there as a raw token — a gap I created and closed in the
same commit. Three entries, all driven through the shipped translator:

    NOTHING_TO_AUDIT                     暂无可审计内容
    NOTHING_TO_AUDIT · 0 finding(s)      暂无可审计内容 · 0 项发现
    the sentence and its next-step line  translated (pattern for the path)

The CLI line itself is English, because there is no CLI catalogue on integration
(D16). The console surface is covered; the terminal surface is not, and that is
the same one-of-two split as the denial string.

## 5. Mutations — 5 of 5 red, each anchor-confirmed

    E1  the third state collapses back into PASS        RED (3 tests)
    E2  the audit ladder stops consulting scope_started RED
    E3  check_schema blocks an unstarted scope again    RED (3 tests)
    E4  scope_started stops erring toward started       RED (2 tests)
    E5  the jargon returns to the first sentence        RED

## 6. The class sweep — reported separately, and it is a floor

Walked rather than grepped, over what a new user does first:

    surface                        empty state
    crossaudit check               WAS the defect — fixed here
    crossaudit status              "(no cycles yet)"                    correct
    crossaudit routing             "no routing decisions recorded yet"  correct
    crossaudit skills              "No skills yet. …" + what one is     correct
    crossaudit watch               "(nothing has happened yet — run …)" correct
    crossaudit audit --offline     ESCALATE, not BLOCKED (this change)  correct
    all 10 registered DCL checks   NOTHING_TO_AUDIT, 0 hard             correct
    console hub, fresh project     status "ready", 0 alarm words        correct

**1 instance found over the surfaces walked**, and the rest already distinguish
empty from failed. `check` was the outlier rather than the first of many.

**Not walked, so `unknown`**: `build`/`run` (need a provider), the console's
first-run overlay and demo screens, `reproduce`, `amend`, `talk`, `resolve`,
`pair`. The count is a floor over the paths listed and claims nothing about
those.
