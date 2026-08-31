# Integration audit — `b856e0d`

Auditor: auditor3 (Codex, cross-vendor)

Scope: merged CLI, runtime, receipt/verifier, DCL, and their seams. The
`console/page.py` render path was explicitly excluded because auditor2 had
already audited the combined UX surface.

## Outcome

The ledger claim “no open S0/S1 on merged code” is not shown by this tree.
This audit found 2 S0, 3 S1, 1 S2, and 0 S3 findings.

## Instrument and identity

- Audited a detached checkout at full SHA
  `b856e0df003ee631f688d9789f6cef2b74352e34` in
  `/tmp/crossaudit-integ-audit3-b856e0d.gDu01s`.
- Asserted detached `HEAD`, the target tree object
  `cfa5624589d2312186c67b4f7127f4d53cd1f2ab`, and a clean checkout.
- Ran with an explicit `cd`, the shared interpreter
  `/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python`, and
  `PYTHONPATH="$PWD/src"`.
- Asserted the imported package was
  `/private/tmp/crossaudit-integ-audit3-b856e0d.gDu01s/src/crossaudit/__init__.py`,
  not an installed copy.
- Re-derived ancestry: merge `d836a56` and UX heads `e617bd5`, `fe992d5`, and
  `b3b6ab2` are ancestors; `agentA/cli-i18n-wave1` is not.
- Full suite: 1,881 collected, 1,879 passed, 2 skipped, 0 failed.
- Each mutation was preceded by an anchor check showing that it landed in the
  intended production or test file. All temporary mutations and probes were
  removed afterward.

The integration ref advanced during the audit through documentation-only
commits. A final path comparison found no difference from `b856e0d` under
`src`, `tests`, or `packaging`; the audit verdict nevertheless names the exact
detached SHA inspected.

## Findings

### F1 — S0 — A removed DCL plugin retains verdict authority

`src/crossaudit/dcl/plugins.py` keeps loaded plugins in process-global state.
When the current allowed-plugin list becomes empty, `load_allowed()` returns
without unregistering previously loaded checks. `run_checks()` then continues
to execute the stale registry entry even though the current configuration no
longer authorizes its pack.

A same-process production probe loaded a synthetic `departed-pack`, observed
one hard finding, removed the pack from the allowed list, and ran again. The
second run still returned the plugin’s hard finding and its “plugin still ran”
observation. This lifecycle is reachable in the long-lived console because it
reloads configuration while the DCL registry persists.

This violates the allowlist-only, non-bypassable DCL invariant: authorization
removal does not remove verdict authority.

### F2 — S0 — A corrupt present evidence ledger becomes a signed tool-free receipt

`src/crossaudit/receipt/build.py::_tool_evidence()` returns `None` both when no
evidence exists and when a present ledger fails verification or raises. The
builder consequently omits `tool_evidence` and signs a receipt whose shape is
indistinguishable from an audit that used no tools.

The production probe created a genuine evidence ledger, appended a tool call,
tampered the stored content, and confirmed ledger verification failed with a
digest mismatch. Production receipt construction and signing nevertheless
succeeded; the signature verified and the receipt contained no
`tool_evidence` block.

The broker correctly denies a broken present chain at its own seam, but the
receipt builder later collapses that state to absence. A signed receipt can
therefore omit corrupt append-only evidence instead of denying construction.

### F3 — S1 — An honest signed receipt is denied against the verifier’s current HEAD

`src/crossaudit/receipt/verify.py` checks whether the cited report commit is an
ancestor of the audit repository’s current `HEAD`. The receipt does not cite a
receipt commit, so current `HEAD` is machine state rather than the object the
ordering claim is about.

The reproduction used a real offline audit and the production receipt builder,
committed the honest report, cited that report commit, signed the receipt, and
verified its signature. It then checked out a different branch while retaining
the report commit in the same repository. Core verification denied the honest
receipt solely because the cited report commit was not an ancestor of the
machine’s new `HEAD`.

The current format cannot establish the proposed report-before-receipt ordering
from a cited receipt object. Using ambient `HEAD` converts that format limit
into a false integrity denial.

### F4 — S1 — `crossaudit watch` reports corrupt controller state as empty history

`src/crossaudit/cli/watch.py::gather()` catches `JSONDecodeError` while reading
an existing controller state file and silently keeps the default empty state.

Against a live temporary repository, the probe wrote the existing corrupt
state bytes `b'{"cycles":'`. Production `gather()` returned empty cycles and
events. The terminal then presents the plausible “nothing happened yet” state
instead of saying that the ledger could not be read, while its footer claims
the display is derived from that ledger.

This is a silent-success path: corruption is reported as valid empty history.

### F5 — S1 — The server liveness consumer can die silently while every liveness test passes

The liveness thread in `src/crossaudit/console/server.py` catches every
exception and does nothing. It emits no journal event, tracker signal, visible
failure, or bounded escalation.

An anchored production mutation raised unconditionally immediately before the
server’s `daemon.watchdog_sweep()` call, leaving the watchdog implementation
itself intact but killing every consumer attempt. All 28 tests in
`tests/test_run_liveness.py` still passed. They exercise the producer and
thread-presence seams, not successful delivery through this consumer.

This is the requested absence-of-event class: the consumer never runs, nothing
records that fact, and the suite remains green.

### F6 — S2 — The signed DSSE predicate reads obsolete receipt fields

`src/crossaudit/receipt/sign.py::_predicate()` reads the verdict from the
obsolete top-level `receipt["verdict"]` and the report hash from
`subject["report_sha256"]`. The current receipt schema stores them at
`receipt["audit"]["verdict"]` and `receipt["ledger"]["report_sha256"]`.

A real offline audit followed by production receipt construction and signing
produced a receipt with verdict `DCL_ONLY` and a report digest, while the
decoded signed predicate contained empty values for both. Replacing the entire
predicate with `{}` left all 16 receipt-signing tests green. The full receipt
digest remains signed, so this is not a signature bypass; it is false/empty
provenance in the signed predicate and a test-evidence overclaim.

## Cleared suspicions and boundaries

- The report-provenance producer/consumer work uses the cited report commit and
  detects working-file drift. Its relevant tests have mutations at both sides
  of that seam. The excluded page renderer was not re-audited.
- Constitution, report-blob, configuration, and skill-content verification
  generally read from cited commits. The ambient-`HEAD` ordering check above
  was the exception reproduced here.
- The DCL source-digest `hash9` limitation remains a real receipt-format limit;
  it was not refiled as unfinished implementation work.
- Normal tool-evidence inclusion and tamper-after-binding checks work. F2 is the
  distinct assembly-time collapse of a broken present ledger into absence.
- The DSSE subject digest still binds the complete receipt. F6 concerns the
  predicate’s advertised fields, not cryptographic receipt substitution.
- The merged accessibility S1 documented in D109 lies in the explicitly
  excluded `console/page.py` render path and was not counted again.

## Independence limit

My weakest judgment is the S0 severity assigned to F2: the behavior and signed
omission are reproduced, but the severity depends on treating corruption
between evidence production and receipt assembly as part of the admission
integrity boundary. A security reviewer should independently confirm that
severity. The other findings do not rely on that judgment.
