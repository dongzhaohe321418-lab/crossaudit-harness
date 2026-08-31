# Codex audit — watchdog R2 at `b1c9996`

Auditor: auditor3 (Codex). The branch is Claude-authored; this is the requested
cross-vendor audit. No feature code was written.

## Verdict

`DO NOT MERGE` — S0: 1, S1: 2, S2: 1, S3: 0.

R2 repaired the terminal fallback and the current `talk` behavior, but the
watchdog can still certify the founding symptom as explained: an action can
declare one meaningless byte without delivering any byte, and the console
declares success before its response crosses the socket. The stated console
boundary excludes the browser side where the founding defect occurred. The
mid-flight bound is also an unconsumed boolean rather than enforcement.

## Target, integration, and suite identity

- `fix/talk-cited-rules` resolves to
  `b1c9996ba94b0ba2a7e1b99039e61e726e6e7534`, exactly the dispatched SHA.
- Exact detached checkout:
  `/tmp/crossaudit-audit3-watchdog-b1c9996`; clean before and after the audit.
- Shared interpreter:
  `/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python`.
- Imported package identity was asserted as
  `/private/tmp/crossaudit-audit3-watchdog-b1c9996/src/crossaudit` before the
  exact-SHA suite and each independent probe.
- Exact-SHA full suite: **1,819 collected, 1,817 passed, 2 skipped, 0 failed**.
- At audit close, current integration was `v5-redesign` at
  `7ae1e87b5fef14a6a2d5a532403af9f709a1be0d`; merge base was `8509052`, so a
  rebase is required. A detached, conflict-free rebase produced
  `48823a0a2ba943d94eaab3372b227b0fb6ff9404`. The branch itself was not moved.
- Rebased full-suite result: **1,836 collected, 1,834 passed, 2 skipped,
  0 failed**. Its imported package identity was asserted from the rebased
  checkout before collection.

## Findings

### S0-1 — declaration is accepted as delivery, recreating unexplained silence

`ActionWatch.declare()` records arbitrary non-furniture text as `outcome` and
sets the watch to `explained`. `declare_outcome()` only changes that internal
state; its own docstring says it is deliberately not a print. The dispatcher
then suppresses its fallback whenever the internal outcome exists.

I replaced the real `doctor` function at the argparse dispatcher boundary with
an executed command that called `declare_outcome("x")` and returned zero. This
is the smallest fixed string the dispatch asked the audit to attack. Through
the shipped `main(["doctor"])` path the result was:

```text
exit=0
stdout_bytes=0
stderr_bytes=0
watchdog decision=explained
```

The person experiences precisely the founding defect while the mechanism calls
it explained. This is a presence bar: the byte is present in private state,
not content delivered to the person.

The same producer/consumer error is live in the console. Both `_send()` and
`_deny()` call `watch.declare(...)` before headers/body are written. I executed
the real handler `_send()` with a writer that raises `BrokenPipeError`. Delivery
failed, but the resulting watch state was still `explained`:

```text
CONSOLE delivery=failed state=explained
```

This is S0 because the instrument certifies the exact unexplained-silence class
it was commissioned to prevent, including at the surface that founded the
workstream. Required repair: an outcome declaration must not prove delivery.
The guard must execute a declared-but-undelivered command and a failed console
write, and both must remain actionable and named.

### S1-1 — the advertised mid-flight bound has no product consumer

`ActionWatch.overdue()` computes whether silence exceeded 45 seconds, but the
only calls to `overdue()` and `silent_for()` are in tests. No runtime loop,
thread, timer, dispatcher, or console handler reads the result. I drove a watch
past its budget and got `overdue=true`; nothing was emitted and no state change
followed.

Terminal checking happens only after the observed function returns. A hung or
still-running action can therefore remain silent indefinitely, contrary to the
module's repeated claim that an action which “outruns its bound” is narrated.
For this part of enforcement, the value is `return-only`.

Required repair: either connect the relative bound to a real consumer that
names an overdue action while it is running, with an executed timing mutation,
or remove the mid-flight/bounded claim and state that this is terminal-only.

### S1-2 — `uncovered=0` counts the server half and excludes the console a person meets

The 36 derived console actions are POST allowlist paths in `do_POST`; that is
honest coverage of server route dispatch. It is not coverage of the console
action. The browser choke point `api(path, body)` in `console/page.py` has no
watch, no deadline, and no guaranteed visible consumer. The branch's own
finding states that this is the founding defect's side and says nobody should
read `console=covered` as covering the send.

That boundary statement is honest; its consequence is `console=excluded`, not
`uncovered=0`. A green instrument with a footnote around the exact surface it
was built for does not close the workstream. The failed-write execution above
also shows the server half declares an outcome before it knows the consumer
received one.

Required repair: derive initiated browser actions at the shared `api()` choke
point and execute the failure through the visible explanation consumer. The
suite must fail when fetch settles or stalls without an actionable explanation;
server response construction is not that consumer.

### S2-1 — the `talk` regression guard remains green when person delivery is removed

The current production behavior is correct. I executed `cmd_talk` through an
actual watched action with its router and lane controlled: the computed lane
outcome was printed to stdout, then declared, and the watch ended `explained`.
Thus `talk=acted`, not suppressed.

The committed guard does not establish that. It uses `inspect.getsource()` and
asserts only that the token `declare_outcome` appears after the token
`_record_routing`. I removed the production `print(f"\\n  {executed}")` while
leaving the private declaration. The named test
`test_talk_states_what_it_did` stayed green: 1 passed. The person was silent and
the test filed delivery under internal state.

This is S2, and gating under D93 because the guard cannot detect the defect it
claims to guard. Required mutation: remove only the person-facing print and
require an executed `talk` transcript assertion to redden by its own name.

## Requested mutation and properties

- Suppressing the terminal fallback in `cli/main.py` made
  `test_a_command_that_returns_silently_is_named` fail by its own name. Its
  failed assertion contained the exact action `crossaudit doctor`.
  `mutation_names=yes`.
- Restoring the fallback made that test pass and returned the detached tree to
  clean.
- Furniture such as `Working…` and short ellipsis phrases remains rejected, but
  arbitrary fixed text such as `x` passes and need not be delivered.
  `explanation_bar=presence`.
- All 18 argparse verbs and all 36 server POST allowlist paths are derived, not
  maintained in a watchdog list. The missing set is the browser consumer, not
  another server path.
- `record_undeclared()` does reach a committed test through the process-local
  `UNDECLARED` list, and strict mode can print it. That is a real test-visible
  seam. It does not rescue the unconsumed mid-flight `overdue()` result or the
  browser exclusion.

## Cleared suspicions

- The terminal silent-return fallback runs in the shipped dispatcher, reaches
  stderr, names the action, gives a next step, and reddens when suppressed.
- Current `talk` production behavior prints the lane result to the person before
  declaring it; the defect is the committed evidence, not the current behavior.
- The console server wrapper derives names from `parsed.path`, and new accepted
  POST routes inherit the wrapper. There is no second maintained watchlist.
- Denials state their reason, and a normal declared action adds no user-facing
  watchdog noise. I did not find evidence that the terminal wrapper is already
  a usage tax.
- `CROSSAUDIT_WATCHDOG_STRICT` is documented. Its opt-in nature is stated rather
  than silently presented as default user surfacing.

## Evidence seam and independence limit

The audit executed the Python dispatcher, the `talk` function, and the real
console handler's failed-write boundary. It did not drive a live browser fetch
through DOM presentation or assistive technology. That last consumer is both
the branch's stated exclusion and my weakest independent seam. I therefore do
not claim that any existing browser error surface is usable; the finding is the
stronger structural fact that this watchdog never observes that surface.
