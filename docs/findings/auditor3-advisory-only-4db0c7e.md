# Advisory-only constitution review — `4db0c7e`

## Execution ledger

`commands=17` evidence command groups; `wall_time=662s` from detached-worktree
creation through the last evidence read; checkout
`/tmp/crossaudit-advisory-4db0c7e.afHBTJ`; SHA
`4db0c7ee14e822cb01e4287b1e6b1e2e708bdf5d`; tree
`556dfbe6f101bf870f876de04ba42334d1cfc41c`; model at start and finish:
`GPT-5 (Codex)`.

Artifacts:

- `/tmp/crossaudit-advisory-4db0c7e-logs/identity.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/focused.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/independent-probe.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/mutation-model-first.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/mutation-no-universal.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/existing-base.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/existing-tip.log`
- `/tmp/crossaudit-advisory-4db0c7e-logs/full-suite.log`
- this report

Command groups, in execution order:

1. Resolved current integration and `fix/advisory-only-constitution`, showed
   `4db0c7e`, and created the detached worktree.
2. Re-derived the merge base, branch stack, changed paths, and relationship to
   integration.
3. Read the complete stack diff and the relevant production DCL, auditor, and
   constitution sources.
4. Read `run_audit()` with numbered lines and enumerated verdict references.
5. Asserted shared-interpreter import origin, then ran the two focused test
   modules.
6. Inspected the real DCL fixtures and replay-provider construction rather than
   assuming what the supplied tests exercised.
7. Added, anchored, and ran a temporary independent production-path probe using
   a raw advisory-only constitution; then deleted it.
8. Moved model verdict precedence above DCL, anchored the mutation, and ran the
   named deterministic-floor guard.
9. Re-checked the mutation inside the exact synthesis block after rejecting an
   overly broad first anchor.
10. Restored the precedence mutation and asserted a clean diff.
11. Removed the universal-rule prepend, anchored it, and ran the named render
    guard; then restored it.
12. Created a detached parent checkout and compared validation and rendered
    BLOCKER-constitution bytes between parent and tip.
13. Ran the complete detached suite with output and timing written directly to
    artifacts, not through a result-masking pipeline.
14. Read the complete pytest summary and re-asserted SHA, tree, clean status,
    import origin, and current integration position.
15. Enumerated production `Draft.render()` callers and executed a reserved-ID
    replacement/prepend probe.
16. Read every model-verdict access in `validate.py` and derived call-order
    anchors from `run_audit()`.
17. Recorded the evidence wall-clock interval.

The first precedence-mutation anchor searched too broad a scope and matched an
unrelated `elif reply` in report rendering. I did not use it. The replacement
anchor printed and compared only lines 237–243 of `run_audit()` and the git
diff, showing the model-first mutation in the synthesis block before its test
result was accepted.

## Measured result

The model cannot waive a deterministic finding. No S0, S1, or S2 behavior
finding was reproduced. There is one S3 accuracy finding in the replacement
comment.

Full suite: 2,027 collected, 2,025 passed, 2 skipped, 0 failed in 338.82 seconds.
The supplied `1885/0` count was not reused or reconciled by inference.

## Critical production-path probe

The independent probe deliberately did not use `Draft.render()` or its
universal task rule. It passed `run_audit()` a raw constitution containing only
two ADVISORY rules, ensuring the deterministic result could not be attributed
to a hidden constitution BLOCKER.

- With real malformed experiment results and `offline=True`, the deterministic
  layer produced three hard failures, no model reply existed, and the outcome
  was `BLOCKED`.
- With the same raw advisory-only constitution and the same three hard failures,
  a recorded provider reply was parsed and validated as `PASS`. The returned
  model reply remained `PASS`; the final outcome was `BLOCKED`.

The production order is:

1. `run_checks(...).as_dict()` executes at `auditor/run.py:169`.
2. The provider is called and its reply parsed and validated at lines 186–208.
3. Final synthesis checks escalation lock and then
   `dcl["total_hard_failures"] > 0` at lines 237–240.
4. Only if that branch does not hold can `reply["verdict"]` determine the result
   at lines 247–248.

The specified anti-fix moved the model branch above the DCL branch. The named
test
`test_the_deterministic_floor_still_blocks_without_any_blocker_rule` failed with
three hard failures and final `PASS`, explicitly saying the model waived the
floor. The mutation was anchored in the synthesis block and restored.

## Existing configurations

The source stack changes production behavior only in `Draft.validate()`.
For an existing draft containing one BLOCKER and one ADVISORY rule, the parent
and tip both accepted the draft and produced the identical rendered SHA-256:

`672f0e8dbfd59f539e743ebb819aec4f0e5a53b11445e043700c120a53b0ec27`

Both retained severities `BLOCKER,ADVISORY`, emitted exactly one
`CA-TASK-001`, and placed it before the existing rule. The full regression suite
also passed.

## Universal rule prepend

Both production callers of a drafted constitution use `Draft.render()`:
`cli/wizard.py` and `console/projects.py`. The method unconditionally constructs
its rules with `universal_task_rule()` first. A direct probe also supplied a
provider-authored ADVISORY rule using the reserved `CA-TASK-001` ID; rendering
discarded that override, emitted the protocol BLOCKER exactly once, and placed
it before the remaining advisory rule.

Removing the prepend made
`test_the_rendered_constitution_still_carries_the_universal_task_blocker` fail by
its own name. The mutation was anchored and restored.

## Finding

### F1 — S3 — The replacement comment overstates the temporal read order

The safety claim is correct, but the long replacement comment says
`run.py` selects DCL `BLOCKED` “BEFORE it ever reads the model's verdict.” That
is not literally the execution order. `validate_reply()` reads
`reply.get("verdict")` and later `reply["verdict"]` while validating the model
reply, and `run_audit()` calls it at line 207 before final verdict synthesis at
lines 237–248.

This does not create a waiver path: validation cannot choose the final verdict,
and synthesis still gives deterministic `BLOCKED` precedence. The accurate
load-bearing statement is that DCL executes before the provider and final
verdict synthesis gives hard failures priority over a validated model verdict.
The comment and matching test prose should say that instead of claiming the
model verdict has never yet been read.

## Cleared suspicions and limits

- A raw advisory-only constitution with no `CA-TASK-001` still preserved the
  deterministic floor, so the decisive result does not depend on the renderer.
- An advisory-only draft can pass clean work when the model passes; the change
  does not turn all newly permitted configurations into permanent blocks.
- The phrase “advisory-only” does not mean the rendered constitution lacks the
  protocol-level task BLOCKER. The new tests state this boundary explicitly.
- My weakest independence point is the existing-configuration claim: the exact
  byte comparison covers a representative BLOCKER/ADVISORY draft and the source
  diff proves no other production function changed, while the full suite covers
  the broader population. It is not an exhaustive enumeration of every possible
  historical constitution.
