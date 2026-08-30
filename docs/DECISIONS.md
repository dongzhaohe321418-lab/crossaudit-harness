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

### D12 — The third text tier does not exist in the light theme; stop pretending it does

The design engineer's token analysis found something better than a fix. `--text-3`
carries 149 uses, 141 of them `color:` and only 8 decorative — dots, a toggle knob,
chevron masks, one gradient — so the blast radius of changing it is small and
known. `--faint` is aliased to it with zero usages and gets deleted.

The uncomfortable part: **in the light theme that tier cannot survive.** No value is
both readable at 11px and distinguishable from `--text-2`. `#646B79` clears AA at
4.73 worst-case but sits 0.02 luminance from `--text-2`, which means it is legible
and no longer a tier. Dark has room — `#9B948A` at 5.46 keeps a genuine third
level.

**Decided:** stop carrying that hierarchy in COLOUR and carry it in weight, size and
position. As the engineer put it, pretending the range exists is how we arrived at
a 2.72 contrast ratio on body copy in the first place. A design system that claims
three legible tiers in a palette that supports two will keep producing unreadable
text, and every individual fix will look arbitrary because the real defect is the
claim, not the value.

This is the same failure this project keeps finding in its code, arriving in the
visual system: an artifact asserting a property it does not have.

Consequence for in-flight work: the MCP batch fixed `.field-help` locally inside
`.mcp-wizard` only, which was correct scoping at the time. Once the token is right
that override must go, or one class renders two different colours depending on
which component it lands in. Both changes touch `page.py`, so whoever lands second
removes it.

### D13 — A stale-base diff is not a deletion

The design review of the MCP batch recorded, prominently, that the raw diff shows
`AGENTS.md -24`, `docs/DECISIONS.md -426` and `test_context_condensation_page.py
-440` — and that the branch deletes none of them. They are stale-base artifacts.

Recorded as a decision because the person most likely to misread that diff is the
merge gate, which is me, and because it is a general hazard now that branches live
long enough to fall behind an integration branch that is moving hourly. A reviewer
who notices this must say so in the review rather than leave it for the merger to
work out, and the merger rebases before reading a diff for content.

### D14 — Holding a file must not orphan the other half of a seam

Two findings in one audit, same cause, and the cause is mine.

The verification-state slice built a correct four-state renderer in `page.py` and
the audit then found that **completed checks are announced as "not run"**: the
server still sends `{name: contract_string}` and never `{description, state}`, so a
real passing `checks.json` with a PASS report renders as "parseable: not run yet,
complete: not run yet". The same audit found the approved `rules_blocking` field
absent, so the constitution row still reads "N rules".

In both cases the console could only say what it was told, and nobody was assigned
to make the server tell it. I held `page.py` for one engineer to prevent two large
branches colliding in it — which was right — and then failed to assign the
server-side half of the same seam, which was not.

Note the direction of the error: the renderer now UNDER-claims rather than
over-claims, so no §1.5 line was crossed. But for this product specifically that is
still a real harm. The design engineer's walkthrough found that a first-timer's
comprehension of the audit is CrossAudit's genuine strength; a console that reports
"not run" for checks that ran teaches them the verification never happens. An
honest under-claim is not automatically a safe one.

**The rule:** when a file is held, the manager assigns the other side of every seam
that file participates in, in the same breath, or the slice is scoped to include
both sides. A held file is a scheduling decision, and scheduling decisions that
strand half a contract are the manager's defect, not the engineer's — the engineer
that reported "the row states only what it is told" was describing the situation
correctly and escalating it correctly.

### D15 — Three states, because we have evidence for three

Building the server half of the check-state seam, the engineer stopped before
editing and reported a contract blocker rather than picking an answer:
`checks.json` records contracts and findings, so **passed**, **failed** and
**not run** are all honestly derivable — but it records no APPLICABILITY fact, so
"does not apply" cannot be distinguished from a check that ran and found nothing.
Making the fourth state real would require an additive applicability result from
`dcl/`, which turns a server-side slice into an audit-core change.

**Decided: three states. `n_a` is not sent, because we cannot honestly derive it.**

Rendering "does not apply" for a vacuous pass would assert a fact we do not have,
which is the exact failure class this team has spent the day removing — and it
would do it on the surface whose whole purpose is to stop the product claiming
verification it did not perform. A check that ran and found nothing has run. Saying
it passed is derivable; saying it did not apply is invention.

The renderer keeps its four-state capability. It is the general treatment and other
surfaces will have genuine applicability; an unreachable branch that is correct
costs nothing, while a reachable branch that lies costs everything. But the commit
and the ledger must state plainly that `n_a` is not currently reachable and why,
so that a future reader meeting a four-state renderer does not assume all four are
live.

**And the trade I am refusing explicitly:** expanding into `dcl/` to give a console
row a fourth badge is the wrong reason to touch the deterministic layer. §1 says an
audit-core change is a conversation, not a commit. Adding an applicability output
to DCL may well be a good change — but it has to be justified by what the AUDIT
needs, not by what a UI wants to display. Logged as a separate candidate to be
argued on its own merits by someone who wants it for the audit's sake.

### D16 — The CLI has no i18n, and our invariant says it must

The design review of the first-three-minutes slice reports something larger than
the slice: **the CLI has no i18n mechanism at all.** `LANG=zh_CN.UTF-8` renders
English. The engineer built to a spec that said English-only, so this is not its
defect — it is a gap between what §1 of AGENTS.md claims and what the product does.

§1 says every user-facing string needs Chinese parity. The console satisfies it.
The CLI never has. So that invariant has been, in part, aspirational, and it has
been reported as satisfied slice after slice because every slice that touched it
was a console slice. Recorded plainly, because an invariant that is only true of
the surfaces we happen to work on is not an invariant, and quietly enjoying the
credit for it is the same failure we keep finding in code.

It also just became materially worse. The constitution moment — a person's
governing document, shown for agreement sixty seconds in — is a CLI screen. A
Chinese-speaking first-timer now meets **the most consequential screen in the
product** in a language they did not choose, at the exact moment they are being
asked to agree to something. The owner works in Chinese.

**Decided:** CLI i18n becomes its own slice, specified before it is built. Until it
lands, no slice may report Chinese parity as satisfied on a CLI surface; it reports
"not applicable — the CLI has no i18n mechanism, tracked as D16" so the gap stays
visible in every contract that touches it rather than being silently skipped.

### D17 — Number the options rather than soften the sentence

The same review found an accessibility docstring at `wizard.py:325` claiming a
screen reader receives "the numbered options" when the shipped menu is not
numbered, and selection is carried by a green `❯`, bold, and position — so the
claim that no meaning is carried by colour or position is not true of the selection
marker. Three of its four claims hold.

That is §1.5 sitting inside the slice built to stop the product overclaiming, which
is now the seventh instance of this shape today.

**Decided: number the options.** Both routes remove the overclaim; only one of them
also makes the product better, because numbering lets the selected item be
announced as TEXT rather than as a glyph and a colour. When a claim and the code
disagree, prefer changing the code to match the claim wherever the claim describes
something worth having. Softening the sentence is the right move only when the
claim itself was wrong.

### D18 — Two reviewers disagreed on severity; the deciding fact was missing, so I asked rather than guessed

The file-identity fix drew a MERGE from the cross-vendor engineering review and a
DO NOT MERGE with three S0s from the invariant audit. Both agree the original S0 is
closed: the audit independently reproduced it on integration `7454bda` (rules
changed, nothing staged, only `AUDIT_RULES.md` modified and invisible to the
auditor) and confirmed the same harness is refused before write on `6dd137e`, with
directory symlinks, dangling chains, hardlinks, inode aliases, traversal, case and
Unicode aliases and target swaps all refused.

They disagree about what remains:

- The engineering review framed the non-atomic `apply()` as an atomicity defect,
  pre-existing, S2, explicitly not worth blocking a security merge for.
- The audit framed the same code as an S0, because after a multi-file refusal the
  working tree holds generator-authored bytes from the REFUSED round while the
  committed tree the auditor reads still holds the old content. That is not only
  data loss; it is the generator's output living outside what the auditor sees.

**The audit's framing is the better one** and I am adopting it. "Half a round on
disk" is an engineering description; "the auditor receives one thing while the
generator's bytes are another" is a non-bypassable-audit violation, and that is the
invariant this product exists to hold. The same facts, read against §1.1 rather
than against tidiness, are worse than they looked.

The audit also found two more: parent-directory creation follows a swapped ancestor
before the later refusal fires, so a model-chosen directory can be created outside
the project and `allowed_dirs` even though no content escapes; and identity is
discarded before staging, so replacing a returned pathname with a hardlink to an
out-of-scope file lets `_stage_generated()` stage bytes from outside scope into the
committed tree. Both say the same thing: **authorization does not precede every
filesystem mutation, and it does not survive later pathname operations.**

**The decision I did NOT make:** whether to merge. The fact that decides it is not
in either report — do findings 2 and 3 reproduce on the INTEGRATION branch, or are
they introduced by this fix? If they pre-exist, merging closes a passive no-race
escape and leaves two races exactly as they were: a clear improvement. If this fix
introduces them, merging trades a passive hole for two racy ones and the arithmetic
is no longer obvious.

I do not know, and neither report says. So I asked the auditor, which has the
harness, rather than reasoning my way to a conclusion I would then have to defend.
A merge gate that guesses on the deciding fact is not a gate. Recorded because the
temptation to merge on the strength of "it closes an S0" was real, and the honest
answer was that I did not yet know what I would be trading.

### D19 — Merge the file-identity fix. All three findings pre-exist; ~~and worse~~ two worse, one equal.

The auditor could not answer D18's question: the provider's content filter blocked
four consecutive turns, because a harness that swaps symlinks and hardlinks to test
a defensive boundary looks exactly like an exploit regardless of purpose. Its
session is poisoned for this topic. So I settled it from the code, which is
stronger than the inference I was trying to avoid.

Integration's `apply()` is four lines:

    for rel, content in sorted(work.files.items()):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")

- `mkdir(parents=True)` creates directories through whatever the pathname resolves
  to at that instant, with no pinning and no no-follow. **Finding 2's exposure
  pre-exists and is worse there**, because integration has no later comparison to
  refuse at — it does not notice.
- `write_text` follows symlinks and writes through them. That IS the original S0.
- `file_identity.py` is absent and `resolve_file_targets` appears zero times.
  **Finding 3 cannot be "identity discarded before staging" on integration, because
  identity is never established** — `_stage_generated` runs `git add --` over raw
  pathnames. Same exposure, with nothing to discard.
- Writes are sequential with no rollback, so **finding 1's non-atomicity pre-exists**
  too. What is new is REACHABILITY: the fix adds mid-write refusals, so a half-round
  can now occur where previously the round completed.

And that last point inverts once you look at what those refusals replace. The
conditions that now trigger a mid-write refusal are conditions under which
integration **silently wrote through and succeeded**. "Half a round on disk after a
refusal" is what we get instead of "a full escape nobody noticed". That is better,
not worse.

**Decided: merge.** The newer build is a strictly better posture. It closes a
passive, no-adversary escape — any project containing a symlink pointing out of
scope is exposed today, and the auditor cannot see the change — while the remaining
exposures require winning a race against a boundary that previously did not exist
at all. The three S0s are queued as the next slice and the DO NOT MERGE verdict
stands as a description of the work remaining, not as a reason to keep a live
passive escape in shipped code for another hour.

Recorded honestly: I wanted the auditor's execution and could not get it. A
code-level determination on four lines whose behaviour is unambiguous is not the
same as a guess, but it is also not the same as running it, and I would rather say
which one I had. The auditor is being restarted clean and will confirm or correct
this after the fact.


**Amendment, from the verification I asked for.** An engineer re-ran this
comparison by EXECUTION on the pre-merge code, which is what I wanted and could not
get at the time. The conclusion holds — `holds=yes` — and the four lines behave
exactly as I read them: on the old code all three findings reproduce with no race
injection at all and the original escape is silent, while on the merged code the
original and both non-racy variants are refused.

Two corrections to my own text, and one of them is against me:
- **Finding 2 is worse on the old code than I claimed.** No race is needed there at
  all, and the CONTENT escapes too, not merely the directory. I understated it.
- **Finding 3 is equal, not worse.** The body of this entry says that correctly —
  "same exposure, with nothing to discard" — but the heading compressed three
  findings into one adjective and got one of them wrong.

The honest claim is: all three pre-exist, two are worse there, one is unchanged.
That still leaves merging clearly right, which is why the decision stands and only
its wording is corrected. Struck in place rather than rewritten, because a record
that quietly loses its own overclaim teaches nobody anything — and because this
entry exists to document a case where I acted on reading rather than execution, so
its own summary being imprecise is exactly the thing worth showing.

### D20 — Manager commits go through `git -C`, not through a working directory

Twice now a decision has been committed to the wrong branch because this shell's
working directory persists between commands and had drifted into a worktree that
was not the integration branch. The first time it was AGENTS.md §3.5, caught by the
design engineer when it went to read the rule it had been told to follow. The second
time it was D12 through D18, caught by an engineer noticing that the integration
copy jumps D11 → D19 while D19's text references a D18 that a reader of integration
cannot find.

Both were invisible from where I was standing: the commit succeeded, the file
looked right, and the branch it landed on was one nobody was reading. That is the
same shape as the defects this team keeps finding — an action that reports success
while doing something other than what was intended — and it is mine.

**The rule: every manager commit uses an explicit `git -C <integration worktree>`.**
No reliance on where the shell happens to be. And when a decision references an
earlier one, the reference is a checkable claim like any other: if D19 cites D18,
D18 must be readable from the same branch.

### D21 — CLI i18n ships as the whole init wizard, not the constitution moment alone

I asked whether the constitution moment could ship translated on its own. The design
engineer's answer is no, and the reason is better than my question.

The constitution moment lives INSIDE `init` — steps 1 through 3 and step 4 are one
continuous sequence in one session. A Chinese consent panel after three English
prompts is not a partial translation; it is **a visible seam in the middle of a
single screen flow**. And a person meeting one Chinese screen inside an English tool
will reasonably conclude the rest is broken rather than untranslated — they would be
reading a real signal, because we would be shipping something that looks
half-finished at the exact moment we ask them to agree to something.

**Wave 1 is the whole init wizard.** It is the smallest coherent unit: a person
enters in English or Chinese and stays there for the entire setup. The constitution
moment is *why* wave 1 is P0 — it is where agreement is asked — but it cannot be
carved out of its own wizard.
**Wave 2** is the keyless failure paths a first-timer hits in the next two minutes:
doctor's FAIL detail, fix and verdict; build's stop message; the un-initialised
console refusal. That is where someone lands *because something went wrong*, which is
the worst possible moment to change language on them. Waves 1 and 2 together are
exactly the first three minutes that D6 ranked highest.
**Wave 3** is the front door — the first thing read, but not the first thing that
blocks, since someone who cannot read it has already been handed `crossaudit init`.
**Wave 4** is everything else.

And `--lang zh` is not offered at all until wave 1 is complete. A half-Chinese wizard
is worse than an English one, for the same reason.

### D22 — Review the sha, and know which kind of "the sha" you need

Adopted from the design engineer, then corrected by it within the hour, which is the
right sequence.

The rule: **a review runs against the sha under review, never against a live
worktree.** It caught itself reviewing a branch whose worktree had moved seven files
underneath it, and its review stood only because it had exported a clean archive
first. Reviewing a moving worktree and reporting it as a review of a commit is a
category error.

The correction: **an archive is enough to DRIVE the product, but not to run the
suite.** Tests that shell out to git — credential scanning does — report false
failures against an export with no `.git`. Suite runs need a real detached checkout:
`git worktree add --detach <path> <sha>`, run, remove. Both of its false alarms today
came from this, and both were caught by the reviewer rather than reported as defects.

### D23 — A confident wrong diagnosis is a regression, even shipped beside a fix

The send-path slice replaces a silence with an explanation, and in its generic path
it explains the wrong thing. A non-JSON HTML 500, an aborted connection, or JSON with
no kind and no reason each render a credential or circuit diagnosis — including a
technical-detail line reading "retry in 7s · circuit_open · exit_code 22 ·
http_status 400" for a request that returned 500 and no JSON at all. The notice is
synthesised from the server's LIVE circuit state rather than from the response that
actually failed.

**Decided: this blocks the merge, and the reasoning generalises.** The defect being
replaced told the person nothing. This tells them something confidently wrong, in the
one field a support conversation quotes verbatim, and sends someone whose local
service just returned 500 to go and fix an Anthropic credential. D5 goal 2 says a
reassuring falsehood is worse than an honest failure, so in that path this is a
regression against our own ranking — shipping in the same commit as a real
improvement.

The rule: **a diagnosis must be derived from the failure being reported, not from
ambient state that happens to be available.** Where the failure carries no
information, the honest output says so and says nothing more. "Something went wrong
and we do not know what" is a worse sentence to write and a better one to read than a
precise account of a different problem.

### D24 — Merge the authorization boundary, and name the limit of this pattern

The cross-vendor engineering review of `fix/authorization-boundary` returned MERGE
AFTER FIXES, and its structural verdict is the one I asked for: *one sentence in,
one mechanism out.* `resolve_file_targets` authorizes, `AppliedFiles` carries that
authorization through parent creation, publication, rollback and staging, and every
consumer takes the binding instead of the string. Symptoms 2 and 3 — parent creation
racing a swapped ancestor, and identity discarded before staging — are closed **by
construction**: there is no window to hit and no pathname to re-resolve. Two previous
rounds of patching had not achieved that.

Finding 1 remains: the receipt has no scope guard, so the third symptom is closed by
ENUMERATION where the other two are closed by construction. The reviewer's words:
this "leaves the S0 you rated S0 reachable through a narrower door, and the branch's
own test suite already contains the proof that the door is dangerous."

It also re-confirmed, on a harness written before this fix existed, that integration
at 05863a6 **today** writes through a symlink into out-of-scope rules invisibly,
creates directories outside the project, and stages out-of-scope bytes.

**Decided: merge.** The branch strictly dominates what is in the integration branch,
the reviewer said so unprompted and recommended not holding it behind a perfect
answer, and finding 1 narrows a door that is currently wide open. Same arithmetic as
D19.

**And the limit, stated now rather than discovered later.** This is the SECOND
consecutive merge carrying a known open S0 on the same code, justified both times by
"it strictly dominates". That reasoning is correct and it is also exactly how a team
talks itself onto a treadmill — each step an improvement, the hole never closed. So:
finding 1 is the next thing its author does, ahead of anything else assigned to it,
and **if a third round arrives still carrying an open S0 on this boundary, the
justification stops working and the slice stops merging until the boundary is closed
by construction end to end.** Improvement is not a licence to stay incomplete
indefinitely; it is a licence to ship the improvement once.
