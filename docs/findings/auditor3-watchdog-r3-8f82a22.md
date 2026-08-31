# Codex audit — watchdog R3 at `8f82a22`

Auditor: auditor3 (Codex). The branch is Claude-authored; this is the requested
cross-vendor audit. No feature code was written.

## Verdict

`DO NOT MERGE` — S0: 1, S1: 1, S2: 1, S3: 0.

`third_round_same=yes`. R3 removes the declaration API, but replaces it with
two new proxies for delivery. On the CLI a tee records a witness before the
underlying stream reports that it wrote anything. In the browser a global DOM
mutation counter treats hidden, unrelated text as the action's explanation.
Both can mark/suppress `explained` while the person receives zero explanation.

Per the manager's stated stopping rule, this is not a recommendation for an R4.
The workstream should stop and the owner should decide whether the property is
mechanically achievable, or narrow it to a seam the mechanism can actually
observe.

## Target, integration, and suite identity

- `fix/talk-cited-rules` resolves to
  `8f82a2260677666ab4c67df054aa3b11dfd2199d`, exactly the dispatched SHA.
- Detached checkout:
  `/tmp/crossaudit-audit3-watchdog-r3-8f82a22`; clean before the full suite and
  restored clean after every mutation.
- Shared interpreter:
  `/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python`.
- Imported package identity was asserted as
  `/private/tmp/crossaudit-audit3-watchdog-r3-8f82a22/src/crossaudit`.
- Full suite at the exact SHA: **1,841 collected, 1,839 passed, 2 skipped,
  0 failed**.
- At audit close, current integration `v5-redesign` was
  `f807ef22133e66f74ad0416c391ddeae7ae7c780`, and that exact SHA was the merge
  base/ancestor of the target. **No rebase is needed.**

## Findings

### S0-1 — R3 still accepts proxies for delivery on both person-facing surfaces

#### CLI: witnessing occurs before writing, and the write result is ignored

`runtime/watchdog.py:275-279` calls `heard()` and `witness()` before calling the
underlying stream's `write()`. `deliver()` later decides success by string
membership in the unscoped `witnessed` list; it never checks how many characters
the stream reported writing.

I drove the shipped `main(["doctor"])` dispatcher with a command that called
`watchdog.say("doctor completed with no findings")`. Its stdout stream
truthfully returned `0` characters written and stored nothing. The result was:

```text
exit=0
written_chars=0
fallback_bytes=0
watchdog.say returned True
```

The person received zero output, but the tee had already appended the string to
`witnessed`, so `deliver()` marked the watch explained and the dispatcher
suppressed its fallback. This is the founding symptom through the real product
path.

The witness is also not correlated with a delivery attempt or stream. I called
`watch.witness("fixed outcome")`, then delivered the same fixed string to an
unobserved private buffer. The stale string made `deliver()` return true and the
watch state become `explained`. Thus a state transition and fixed string still
satisfy the bar; removing the method named `declare` did not remove declaration
semantics.

#### Console: any page text, including hidden unrelated text, suppresses enforcement

The console has genuinely moved to the correct `api()` browser choke point, but
its delivery predicate is global `watchdogRendered > before`. The
`MutationObserver` increments that counter for any non-furniture text anywhere
under `document.body`; it does not require that the text be visible, associated
with the action, an error, actionable, or in the accessibility tree.

I executed the shipped `watchdogWatch` and `api` functions verbatim in installed
Chrome through DevTools, with `/api/say` fetch forced to fail:

1. With no other mutation, the real DOM received a visible, named alert. Chrome's
   accessibility tree contained an `alert` node and the full sentence as
   `StaticText`. This clears the suspicion that console enforcement never runs.
2. On the same silent action, I added a hidden node whose unrelated text was
   exactly `x`. The counter advanced, the watchdog note was suppressed,
   `document.body.innerText` was empty, and the accessibility tree contained no
   alert or static text. The interface was silent while the watchdog accepted
   the proxy.

The committed Node harness tests a meaningful fixed sentence and furniture, but
never hidden text, unrelated text, or concurrent action text. On a live console,
background rendering by any action can suppress another action's explanation
because both share one global counter.

This is S0 and `explained_by=proxy`: round three still accepts a proxy on both
surfaces, and both executions reproduce unexplained silence.

### S1-1 — the advertised mid-flight enforcement remains return-only

R3 adds real browser enforcement after a failed promise and retains real
terminal CLI enforcement after a command returns. Those parts reach.

The Python watchdog still advertises a 45-second mid-flight silence bound,
however, and `ActionWatch.overdue()` remains an unconsumed boolean. Repository
call-graph search found `overdue()` and `silent_for()` used only by their unit
tests. I drove a watch beyond its bound and obtained:

```text
OVERDUE value=true state=silent
```

No product caller observed it, emitted anything, or changed state. A running or
hung CLI action can therefore remain silent indefinitely. R2 required either a
runtime consumer or removal of the mid-flight claim; R3 does neither and its
`enforcement=reaches` report omits this path. For the dispatched field,
`enforcement=return-only`.

### S2-1 — the `talk` delivery guard is still source inspection

Current `talk` behavior is good: I executed `cmd_talk` with controlled routing
and a real `watchdog.observe`; the lane outcome reached stdout and the watch
ended explained.

The named guard still calls `inspect.getsource()` and searches for the token
`watchdog.say`. I put the production call behind `if False`, so the person
received no lane outcome. `test_talk_states_what_it_did` stayed green: 1 passed.
This is the same open R2 evidence finding, not an R3 production regression.

Under D93 it remains gating: the guard cannot detect the silence it claims to
guard. Replace it with an executed `cmd_talk` transcript assertion and require
the dead-call mutation to redden by its own name.

## Console coverage and enforcement — cleared distinctions

- `console=covered`. I did not infer this from the 36-route registry. The shipped
  `/api/say` action was driven to a rejected fetch in Chrome, and the watchdog
  produced its named fallback in both DOM and accessibility-tree text when no
  proxy intervened. The two explicit fetch bypasses remain `/api/preview` and
  the unload-time `/api/mcp` keepalive; neither is the founding send path.
- Terminal CLI enforcement reaches stderr after a silent return. Console
  failed-action enforcement reaches a visible alert. The binary
  `enforcement=return-only` result is specifically because the separately
  advertised mid-flight CLI bound still has no consumer.
- Removing the CLI fallback made
  `test_a_command_that_returns_silently_is_named` fail by its own name and its
  assertion named `crossaudit doctor`.
- Removing the console note's text made the shipped-client guard fail
  `SILENT_watchdog_wrote_the_missing_sentence`, `SILENT_names_the_action`, and
  `SILENT_says_what_to_do_next` (plus the corresponding Chinese checks).
  Therefore `mutation_names=yes`.

## Other cleared suspicions

- Server-side `ActionWatch` coverage has been removed; the server no longer
  counts preparing or writing an HTTP response as person-facing explanation.
- The console fallback preserves the original exception, waits until its bound,
  names the API action, gives a next step, has `role="alert"`, and supplies
  Chinese copy when `currentLocale` is Chinese.
- Furniture such as `Working…` does not satisfy either the Python or browser
  filter. The defect is arbitrary/unrelated delivery evidence, not the spinner
  regression returning unchanged.
- The fallback-suppression mutations were fully restored; the exact detached
  tree is clean and the three restored targeted guards pass.

## Evidence seam and independence limit

The audit spans the real Python dispatcher and a real Chrome DOM/accessibility
tree, but it injects the shipped console functions into a minimal document
rather than navigating the frozen application. I do not claim theme/layout,
VoiceOver speech, or frozen-DMG parity. That is my weakest seam.

The S0 does not depend on those untested layers: in the failing browser case
both visible `innerText` and Chrome's accessibility tree were empty, and in the
CLI case the underlying stream explicitly reported zero characters written.
