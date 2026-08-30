# Decision record

Product and engineering decisions taken by the engineering manager under the
authority the owner delegated. This file is the manager's; `TASK_LEDGER.md` is the
engineers' change contracts. They are separate files so that a decision recorded
mid-flight does not conflict with every branch in progress — which it was doing.

Every decision is binding on the team until superseded by a later entry here. A
superseded decision is struck with its reason, never quietly edited.

## Decision record — authority, and the decisions taken under it

The owner has delegated development direction and design direction to the
engineering manager. Product and design calls are made here and recorded here;
they do not go back to the owner. What still goes to the owner is a short list of
things the manager is not permitted to do rather than not competent to decide:
entering credentials or authenticating an account, pushing or publishing
anything, and any spend or outward-facing action. Those are boundaries, not
decisions.

Every decision below is binding on the team until superseded by a later entry in
this file. A superseded decision is struck with its reason, never quietly edited.

### D1 — The add-MCP dialog: the two-step wizard is the design

A request arrived to lock in "variant A" of three dialog variants. There were no
three variants. Agent A, asked directly and told explicitly not to reconstruct a
history to fit the question, reported that it produced exactly one design and
never offered a choice between alternatives. What exists in threes is review
rounds: 52b0dd8 (the redesign), 4071a4d (the Configure→Save fix), 293110b (the
consent-vector rebuild).

**Decided:** the two-step wizard — Connect, then Approve tools — is the design of
record. It is merged at 47863b6. No variant work is commissioned.

The reasoning is not merely that it is what exists. The dialog's shape is forced
by the server's own rule: /api/mcp requires connect → read the advertised tools →
approve named tools before the Generator may call anything. A single flat form
cannot express that order, which is why both natural paths through the old form
ended in a raw denial. A design that contradicts the security model it sits on is
not a stylistic option, so a variant round would have been theatre.

The design/UX engineer's independent assessment stands as the input to the NEXT
iteration of this surface. Its findings will be triaged and scheduled like any
other; they do not reopen D1.

### D2 — Auditor vendor: codex now, gemini only if the owner authenticates

True third-vendor independence needs gemini, which requires a one-time Google
login. That is a credential action, outside what the manager may perform.

**Decided:** the independent auditor is a codex agent that writes no feature code.
Against claude-authored code this is properly cross-vendor. Against
codex-authored code it is same-vendor, different-session — weaker, and AGENTS.md
§2 requires the merge commit to say so rather than gloss it. Where a codex-
authored slice touches the audit core, it additionally gets an engineering review
from the claude implementation engineer, so no audit-core change reaches a merge
on a single vendor's judgement.

### D3 — Roadmap order

Slice 1 (surgical edits as the default write path) merges as soon as S1-2r is
closed; it is the largest measured win, 229 bytes against 68,117 for the same
edit. Then slice 2 (streaming), which does not shorten a turn by a millisecond
but removes the silence — and since local overhead measured under 0.2% of a turn,
perceived latency is the only latency there is to win. Then slice 4 (auditor
reasoning effort per tier). Then the mandatory file_read before editing an
outlined file, whose acceptance criteria are already fixed: mean rounds-to-PASS
and edit-refusal rate, split by whether the target was inlined or outlined.

Slice 3 as originally briefed — an async or pipelined audit — stays **rejected**.
The audit is the loop's branch condition, not a side effect: round N+1's prompt
does not exist until round N's audit produces its findings. The only pipelined
form is speculative generation, which doubles provider spend on exactly the
blocked rounds the round budget exists for, and requires showing the user work
that a late BLOCK then retracts. The replacement experiment — skipping the
auditor model call when the deterministic tier has already hard-failed, since the
verdict cannot change — is measurable and stays queued behind the four above.

### D4 — Slice 2 (streaming) contract: countersigned with binding amendments

The design was proposed by the claude implementation engineer and countersigned
by codex, which owns the half of the split where most of these consequences land.
Codex's amendments are ACCEPTED and are binding on both halves. The contract text
on `agentA/a2-condensation-consumer` must be reconciled to this entry at rebase;
where the two disagree, this entry wins, so there is one contract and not two.

Accepted as proposed: one new `RunEvent.kind`, `generation_chunk`; no new
`RunState` and no transition-table change; ordering by explicit `stream.seq`, so
a consumer seeing 0,1,3 knows 2 is missing; explicit termination rather than an
inferred one; and no page-side stall timer — stalls stay with the existing lease
heartbeat, `run_stalled` and `provider_unavailable`. Codex confirmed that last
point survives contact with `runtime/runs.py`: chunk appends renew the lease, so a
silent provider produces no heartbeat and gets the existing narration. The page
does not invent a second timer.

Amendments, each of which changes something real:

1. **"Process-local" was false, and that matters more than it looks.** Streamed
   text lands in the SQLite operational journal and persists under existing
   retention — up to 14 days. The honest formulation is *local operational-journal
   data, subject to existing retention*, and it remains excluded from evidence,
   tool results, auditor prompts, commit messages, receipts and the ledger. The
   P2 guarantee is unchanged; the sentence describing it is now true. A contract
   that had shipped saying "process-local" would have been an §1.5 overclaim
   written into the design rather than into the code.
2. **`response_sha256` is defined exactly**: SHA-256 of the complete assembled
   completion *text*, UTF-8 encoded, matching today's `sha256_text(text)` — not the
   provider's HTTP response body. Chunks are never evidence, and now the sentence
   saying so cannot be satisfied by digesting the wrong bytes.
3. **Carrying the stream on `waiting_reason` is rejected.** That field is
   run-level, cleared by later events, and absent from individual event
   projections. Slice 2 adds a validated `RunEvent.stream` mapping persisted in an
   additive `stream_json` column.
4. **Chunk granularity, which was the open question**: emit the first decoded
   text immediately, then flush at 200 ms or 8 KiB, whichever comes first, with
   incremental UTF-8 decoding and residual text flushed before the terminal event.
   Sequence numbers are assigned *after* coalescing, so they stay contiguous from
   the consumer's view and the gap rule holds. The journal neither renumbers,
   coalesces, nor caps stream rows. Coalescing at the provider is what keeps a
   token-per-event stream from putting thousands of rows in the journal.
5. `generation_chunk` text bypasses the journal's 400-character narration
   truncation, while staying bounded by the 8 KiB chunk contract.
6. **SSE delivery must be incremental**, not a repeated re-serialisation of the
   whole 200-event snapshot tail — otherwise a feature whose entire purpose is
   perceived speed would make the console slower the longer a run gets.
7. **On any sequence gap the page marks or discards the incomplete draft.** It
   never concatenates across a gap and never presents the result as complete.
8. Termination is clarified: provider-controlled completion or failure emits
   `complete` / `aborted`, but cancellation, process death and run failure may
   prevent that callback, because `RunCommandService` moves to `CANCELLING` and
   rejects later generation events. The existing run-terminal or liveness event
   then supersedes the open stream.

Unchanged and non-negotiable: streamed text is unaudited by construction and must
be unmistakably a live draft — no download, no Files panel, no deliverable
styling, visibly superseded when the round commits.

### D5 — The ranking metric is human pain, not engineering severity

Direction from the owner: make CrossAudit genuinely good to use, from the point of
view of the person using it. That is now the top-line goal, and it changes how
work is ranked rather than merely adding items to the list.

**Operationally, what "good to use" means here.** CrossAudit's honest problem is
that it does something slow and invisible — it writes, then an independent auditor
judges — and every second of that is a second the person is looking at nothing. So
the experience goals, in order:

1. **The person always knows what is happening and what to do next.** No silent
   waits, no dead ends, no state that needs the source code to interpret.
2. **Nothing is ever claimed that was not done.** A green check that implies more
   verification than actually happened is worse than an honest failure. This is
   §1.5, and it is a usability rule before it is an integrity rule: a product that
   overclaims teaches people not to trust the parts that are true.
3. **A bad or incomplete request gets a helpful reply, not a red failure.** The
   audit exists to judge work, not to punish typing.
4. **Speed where it is felt.** Local overhead measured under 0.2% of a turn, so
   perceived latency is the only latency there is to win. Streaming does not make
   a turn shorter; it removes the silence, which is the whole complaint.

**Re-ranking.** Slices are now ordered by how much a real person is hurt by the
problem, not by how interesting it is to fix. An engineering S3 that a first-time
user hits in the first two minutes outranks an engineering S1 buried behind a
setting nobody reaches. Severity still governs whether something BLOCKS a merge;
it no longer governs what we work on next.

**Standing commission.** The design/UX engineer owns a recurring first-contact
walkthrough: approach the product as a person who has never seen it, run the
UX_TEST_PLAN scenarios end to end, and report where a human actually gets stuck,
ranked by how badly it hurts them and how early they hit it. Its findings feed the
roadmap directly. Engineering judgement decides HOW to fix; the human-pain ranking
decides WHAT gets fixed first.

**What does not change.** §1 is not negotiable for usability. We do not buy a
smoother experience with a weaker audit core, a silent truncation, or a reassuring
sentence that is not true. Where a genuinely better experience appears to require
weakening an invariant, that is a decision to escalate, not a trade to make
quietly.

### D6 — First-contact walkthrough: the roadmap is re-ordered around what it found

The design/UX engineer walked the product from an empty directory as a person who
had never seen it. Its findings outrank everything currently queued, so the
roadmap moves. Recorded in full because these are the defects that decide whether
anyone gets far enough to care about the rest.

**P0 — the console silently eats your first message.** Hit at roughly sixty
seconds. Type a task, press Send, nothing happens: no spinner, no error, the
thread still reading "What should CrossAudit work on?". The server is not silent —
`POST /api/say` returns HTTP 400 with a plain reason naming the missing
credential. The client discards it. Worse, the send creates a rail entry titled
with the person's own sentence, which opens onto the same empty placeholder;
three attempts produced three identical empty chats. A person concludes the
product is broken, or that they typed something wrong. The fix is to render the
reason that already comes back.

**P0 — four green ✓ for verification that never happened.** On screen at first
paint: "Deterministic checks ✓ convergence ✓ provenance ✓ schema ✓ units", four
lines above "Ledger: 0 Audits 0 Passed 0 Blocked", with zero artifacts, zero
receipts, and the generator never run. The ✓ has no not-yet-run state. Two more of
the same family: the panel reports "8 blocker rules" for a constitution holding 7
BLOCKER and 1 ADVISORY, and `doctor` prints [PASS] on a line whose own text says a
guarantee is not being enforced. This is §1.5 at the exact point where the product
makes its central claim, and D5 goal 2 says a product that overclaims teaches
people to distrust the parts that are true.

**P1 — setup says Ready, and the next command it recommends says not ready.** One
command apart, with the product routing people between them. `init` does warn
about the missing key, but as one line scrolling above a large green box, and it
then recommends `build`, which cannot work either. It also prints "Run crossaudit
init" while the person is inside `crossaudit init`. And `doctor`, whose tagline is
"check everything", never checks the generator key — the one that stops `build` in
round one.

**P1 — the person's constitution is somebody else's, and they never saw it.** A
plain-prose task produced `# Constitution — <PROJECT>` with the placeholder
unreplaced and 7 BLOCKERs about metadata.yml, results.json, quantities and
convergence. The same screen promised the constitution would be "drafted from
this, shown to you, and committed only if you agree". It was not drafted, not
shown, and committed anyway. Their first real build is then blocked for lacking a
file a prose review would never contain — which is the moment the audit stops
reading as a second opinion and starts reading as obstruction.

**P2** — the Decision Center offers every action except the one that works
("Retry provider" fails identically on a missing credential, while the route that
does reach an API-key field is unlabelled); jargon on the surfaces newcomers are
sent to first; and the front door headlines `crossaudit run` while omitting
`build` and `console`, so the generation half of the product is missing from the
first thing anyone reads.

**Re-ordering, per D5.** These displace the MCP dialog batch and the streaming
slice. Streaming was going to be the next speed investment; the walkthrough's
answer to that question was that finding 1 is silence with *no work happening at
all*, so streaming would not have moved that pixel, and a first-timer cannot even
reach the state streaming improves until the send path renders its errors. Fix the
send path first. Streaming remains the right investment after it.

**What the walkthrough could not reach**, and did not infer: the false-premise and
correction scenario, long conversations, live context condensation, and three of
the four escalation causes. All need a live generator and auditor, which means
provider calls. The engineer found the owner's real keys present and deliberately
did not use them, on the grounds that a live run spends the owner's money and
sends project content to third parties. That judgement was correct and the request
is with the owner.

**A correction to the manager's own record.** AGENTS.md §3.5 was committed to the
wrong branch — it landed on `agentA/mcp-dialog-settings-nav` rather than on
v5-redesign, because the manager's shell working directory had drifted. The design
engineer caught it while reading the rule it had been told to follow. It is now
cherry-picked onto v5-redesign and the stray commit removed from the branch that
had already been reviewed at 293110b. The rule that a claim must be checked rather
than assumed applies to the person writing the rules.

### D7 — When a defect class survives three fix rounds, stop patching it

Speed slice 1 has now been through five review rounds. Every round found a real
defect, every fix was correct as far as it went, and the same two classes kept
coming back in a shape nobody had tested:

  R1  a stale OLD block laundered into a fabricated conversational answer, with
      the lie switching on at 40 characters of payload.
  R2  a malformed edit block still reaching the conversational gate; an
      order-dependent parser scan.
  R3  the fix for R2 broke a protected property — prose that merely NAMED the
      marker became a hard failure.
  R4  the fix for R3 restored it, and the sweep was flat.
  R5  the audit found the SAME fabrication defect in an envelope with no OLD or
      NEW section at all: format below 40 letters, conversational above. Both
      earlier sweeps had used a shape that always contained an OLD section, so
      the test named "No payload size may turn a routed edit failure into
      model-authored prose" never executed the class it claimed to exclude.

That is not five careless engineers. It is a decision being made by accumulating
conditions — has it routed to the edit parser, does it carry an OLD section — where
each condition is correct for the shapes anyone thought to try, and the class is
never closed because the shape space was never enumerated.

**The rule.** When a defect class survives three fix rounds, the next change may
not be another condition. It must be a decision that is correct by construction,
and its acceptance must be an EXHAUSTIVE SHAPE MATRIX rather than a sweep of one
shape: every combination of the structural dimensions that distinguish the cases,
crossed with a contiguous sweep of whatever continuous parameter the bug varied
with. If the matrix cannot be enumerated, the decision is not yet well defined and
that is the actual finding.

This is §3.5 taken one step further. §3.5 says a test must execute what it claims.
D7 says that when a claim is about a CLASS, executing one member of the class is
not executing the class.

**Applied to slice 1**, three things must become correct by construction rather
than by condition:
- What counts as a machine-envelope reply, so no payload of any shape or length can
  be presented to a person as something the model said.
- File identity: paths are canonicalised at one point and keyed by that. Today
  `work/a.txt` and `work/./a.txt` validate and resolve independently, both write to
  the same physical file, and lexical ordering decides which edit survives while the
  other is silently discarded. An ambiguous reply must refuse, not partially apply.
- Byte handling: the edit resolver reads with newline translation, so editing one
  line of a CRLF file rewrites every line ending in it. That makes the slice's
  central safety claim — the committed tree, and therefore the auditor's view, is
  byte-identical to the whole-file path — false, and it makes a "surgical" edit a
  whole-file rewrite in disguise.

**On vendor independence, honestly.** This audit was same-vendor: a codex auditor on
codex-authored code. Asked which findings a different vendor would more likely have
caught, it named exactly the two it had just found — the assumption that raw path
strings identify files uniquely, and that "no trailing newline" was the complete
boundary of byte identity. It found the blind spot it predicted it would share.
That is a point in favour of the auditor and not a reason to relax D2: it says
nothing about what a same-vendor reviewer would still be missing.

### D8 — The constitution is the standard; the audit is the mechanism

I asked the design engineer the question I could not answer: if a person can
freely weaken their own constitution at the moment it is created, what is the
audit worth? Its argument is better than my framing and I am adopting it as
policy.

**The line is drawn at concealment, not at content.** The constitution is the
STANDARD; the audit is the MECHANISM. §1.1 protects the mechanism — independence,
evidence-only, deny-by-default, the hash chain — and none of it is touched by what
the standard says. A weak standard does not produce a weak audit. It produces an
honest audit of a weak standard, which is a legitimate thing for a person to
choose. The failure mode that would actually matter is a receipt implying a
stronger standard than was applied, and we are already protected from it: every
audit cites the constitution commit, and rule changes take effect only between
cycles. So nobody can amend their way out of a decision already made — which is
the concrete answer to "edits it into meaninglessness the first time it blocks
them."

**What follows for the design: show, do not police.** No warnings on a minimal
constitution, no "are you sure". Instead the between-cycles rule is said out loud
— *changing the rules never changes a decision already made* — because that single
sentence is what makes editing safe to offer freely, and it converts the worry
into a true statement the person can rely on.

Consequences adopted:
- The least-effort path is three NAMED choices with a default, preceded by four
  plain-language consequence lines and two visible alternatives — not a bare "I
  agree" checkbox. Taking a default among named options is a real decision;
  agreeing to something unread is the rubber stamp we were trying to avoid.
- The minimal option is called "Only what I write myself" rather than "Minimal",
  so its name says what it gives up.
- Provenance is carried by ATTRIBUTION, not by a disclaimer: the drafted path
  quotes the person's own sentence under the rule it produced; the template path
  has nothing to quote, and that absence is the signal. The word "drafted" may
  appear only when a draft happened.
- `crossaudit amend` is provider-backed, so it cannot run in the keyless state —
  yet today's fallback copy offers exactly that as the edit route. $EDITOR becomes
  the keyless path and amend is not offered without a key.

### D9 — A suggested action must prove it can change the situation

From the same review. The Decision Center currently offers "Retry provider · use
the current connection" for a missing credential, which fails identically, while
the route that does reach an API-key field is unlabelled. The root cause is
structural rather than editorial: the "Suggested" tag is static markup on the
reopen radio, and although its LABEL is rewritten per cause, the tag itself can
never move to another option or disappear.

The rule: capability is tested PER INSTANCE against a field the failure actually
carries — `retryable` is already sent — not per action-kind. An absent field means
not-suggestible, which is fail-closed. If nothing is capable, suggest nothing. An
action that cannot possibly work is worse than no action, because it spends the
person's last confidence at the moment they have least.

And the subtle part, which is the reason this is a rule and not a conditional:
`stop` is always capable and must never be suggested. Capability is necessary but
not sufficient — a suggested action must also be a step toward what the person
came for.

**Architecture note, adopted:** the send-path rule and the suggested-action rule
are the same rule wearing two hats. If they ship as separate slices they will
diverge. Remediations are minted ONCE, server-side, in order, and both surfaces
consume them.

### D10 — A guard must be shown to fail, and a semantic guard must not be attempted

Four instances today, across three engineers and four slices, of a test that
looked like it checked something and did not:

  - source-string assertions standing in for rendered behaviour (twice);
  - three independent renders standing in for a locale TRANSITION;
  - a doctor-output parser that assumed a fixed column width and silently dropped
    every row whose label reached it — precisely the rows the file existed to
    check. The tests passed while checking nothing. Its author found it only
    because a test it EXPECTED to fail did not.

That last one is the important one, because it names the technique.

**The technique, now required.** A test whose job is to guard a property must be
demonstrated to FAIL against a deliberate mutation of the thing it guards. Write
the guard, then break the product on purpose, then watch the guard catch it. If it
does not fail, it is not a guard, whatever it is named. Record in the test what
mutation was used — a guard whose counterfactual is written down can be re-checked
by the next person; one whose counterfactual lives in the author's head cannot.
This generalises what one engineer already did voluntarily for the consent
regression test, and it is exactly the method the independent auditor uses when it
attacks a guard instead of reading it.

**And the harder half: some properties must not be guarded mechanically at all.**
The consent slice tried to assert that *no rendered copy implies a stronger
protection than the code provides*. Three successive implementations were defeated
by the auditor — a phrase split across an `<em>`; then a paraphrase appended to
runtime-generated copy by the real callback; then an `aria-label` that Chromium's
accessibility tree exposed as the checkbox's spoken name. None of the last two used
any blacklisted phrasing.

They will keep being defeated, because the property is SEMANTIC and the space of
paraphrase is unbounded. No extractor closes it. Continuing to patch the guard
would be building a thing whose name is a lie, which is the §1.5 failure it exists
to prevent, committed by the guard itself.

**Decided:** stop trying to detect a forbidden MEANING. Detect any CHANGE to consent
copy instead — an approval test over the complete accessible rendered text of every
consent surface, including runtime-generated text and `title` / `aria-label`, since
those were the two escape hatches. The claim then becomes *consent copy cannot
change without a deliberate update to this fixture and a human re-reading it*,
which is true, checkable, and does what we actually need: it forces a person to
look at the wording every time it moves. Name the test for what it does. Do not
name it for what we wish it did.

The general principle: when a guard is defeated three times, ask whether the
property is mechanically decidable at all. If it is not, replace the guarantee with
one that is, and say plainly which guarantee you now have.

**Amendment, from the fifth instance.** An engineer applying D10 found that its own
demonstration had the defect D10 exists to catch: the counterfactual was
established against a STORED ARTIFACT rather than against an unmutated baseline, so
the proof that the guard catches a mutation inherited the same failure mode as the
guard. Its observation is right and is adopted — the demonstration is itself a
test, and nothing exempts a test from being tested.

So: the counterfactual must be established by mutating the real thing and running
the real guard against it, not by comparing to a recorded snapshot of what the
guard once said. And a second test should assert that the guard's COLLECTION
SURFACE has not shrunk, so a refactor that quietly stops collecting one input fails
loudly instead of silently narrowing what is checked.

### D11 — Stop slice 1. Build file identity first, as its own slice.

The invariant audit of the rebuilt slice 1 returned DO NOT MERGE with an S0 and
three S1s. The S0 is the most serious finding this project has produced:

**A surgical edit wrote outside the authorized directory through a symlink.** In a
temporary project with `allowed_dirs=["work"]`, `work/rules-link.md` pointed at
`../AUDIT_RULES.md`. An edit targeting the link changed a BLOCKER rule into an
ADVISORY one. Staging the reported `work/rules-link.md` staged nothing; git showed
only the out-of-scope `AUDIT_RULES.md` as modified and unstaged. So the person
authorized `work/`, the generator changed their governing rules, and **the
auditor's committed-tree input could not see that it had happened**. Validation is
lexical; the resolver checks project-root containment and returns the unresolved
path.

The auditor notes the analogous weakness on the whole-file path PREDATES this
branch. Slice 1 does not create the hole — it makes it reachable through a new
door. That distinction decides what we do next.

**Decided.** Slice 1 does not merge, and it is not patched a sixth time. The three
remaining path findings and most of the S0 share one root: the product has no
canonical FILE IDENTITY boundary. Identity is decided lexically, in more than one
place, and the filesystem disagrees:
- two paths to one target via symlink or hardlink both accepted, both resolved
  against the original bytes, lexical apply order winning and the losing edit
  vanishing;
- `Case-alias.txt` and `case-alias.txt`, and NFC versus NFD spellings, addressing
  the same inode while being accepted as different files;
- a quoted path ending in a space silently stripped, so `spaced.txt␣` was left
  untouched and `spaced.txt` was created instead;
- two dictionary keys differing only by stripped whitespace collapsing silently to
  the later content.

So file identity gets built ONCE, properly, as its own slice, on its own merits,
with the S0 as its acceptance case. One place resolves a requested path to a
physical target and decides authorization against that resolved target. Two
requests reaching one inode is a REFUSAL, not a merge and not a lexical race.
Slice 1 then rebases onto a foundation where most of what kept breaking cannot
occur, and what remains — Unicode line-boundary handling, and byte framing that
mistakes content for protocol delimiters — is genuinely slice 1's own.

**The exhaustiveness claim is itself struck.** The 31,556 cells execute and all
three deliberate mutations were caught, so the tests that exist are real tests.
But the enumeration omits ten material axes, three of which produced live defects.
Calling that matrix exhaustive is a §1.5 overclaim of exactly the kind D7 was
written to stop, committed by the artifact D7 asked for. A matrix is a claim about
COVERAGE, and a coverage claim is checkable: what is enumerated must be stated, and
what is not enumerated must be stated too.

**Escalated to the owner:** the whole-file symlink weakness is pre-existing, which
means it is in the merged product and not only on a branch. That is a security
property of shipped code, so the owner is told plainly rather than having it
folded into a slice summary.

**Vendor note, again honest:** the auditor states same-vendor review is materially
weaker here, because physical-path and newline-framing assumptions are exactly what
a different vendor is likelier to challenge — and it says so while having found
them anyway. The cross-vendor engineering review is still outstanding and slice 1
does not merge without it.
