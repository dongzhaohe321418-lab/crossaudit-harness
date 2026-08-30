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

**Extended, by the engineer implementing it.** Reading the audit of its own fix, it
observed that the rule is symmetric and that we had only written down half of it:
`{}`, malformed JSON and `204` were all treated as ACCEPTANCE without the response
ever establishing that anything was accepted. Its formulation, adopted:

> A claim must be derived from what the response actually established — and
> "delivered" is a claim.

So D23 governs success as well as failure. "We sent it" is exactly as much an
assertion about the world as "it was refused because X", and an optimistic spinner
over a message that was never accepted is the same defect wearing a friendlier face —
worse, in fact, because a person stops watching. It also chose to fix the acceptance
predicate ONCE rather than patch the two sides separately, on the grounds that a 500
diagnosed as a refusal is the same defect on the failure side. That is the D7 instinct
applied without being asked for.

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

### D25 — Exclusion is not degradation, and it does not queue as polish

The design engineer re-ordered the remaining backlog by what a real person meets
first, which is what D5 asks for. Its answer corrected how I had been APPLYING D5,
and the correction matters more than the ordering.

D5 ranks by harm and by how early the harm is hit. I had been reading "a person" as
an average — so accessibility and language landed near the bottom, filed as polish,
because for the average user they are a degradation rather than a blocker. That is
the wrong reading.

For a Chinese-speaking first-timer, an English-only CLI is not a worse experience.
**It is exclusion.** In the engineer's words: for that population "it isn't
degradation, it's exclusion". For a screen-reader user, the ten dynamic containers
that announce nothing are not a missing nicety met at second 90 — they make the
product **unusable rather than degraded**, and for them that finding is not number
four on a list, it is number one.

**Decided: accessibility and language form their own tier, ranked by whether a
population can use the product at all, and that tier is not polish.** Averaging harm
across users hides exactly the users who are most harmed, because the people who
cannot use something at all are always a minority of the people who can.

Concretely: the `--text-3` token work and the send-path generic case stay first,
because they are universal. Then CLI i18n wave 1 and SPEC-9's ten silent containers
are taken as a TIER of their own rather than as the tail of a polish list — the
engineer's recommendation, adopted as written.

This does not change D5. It corrects my application of it: "how badly is a person
hurt" has to be asked about the person most hurt, not about the median one.

### D26 — Two auditors, split by topic, because one vendor cannot report on this class

The codex auditor has now been blocked by a provider content filter on eight turns
across two sessions, including a clean restart, whenever the subject is the
filesystem-authorization boundary. The cause is not the work: a harness that swaps
symlinks and hardlinks to test a defensive boundary looks like an exploit regardless
of purpose, and the filter reads shape rather than intent. It cost us the answer to
D18's deciding question, which I then had to settle by reading code instead of by
execution.

Restarting it a second time would be doing the same thing and expecting a different
result. So:

**The independent auditor role splits into two seats, assigned by TOPIC.**
- Security-boundary work — path authorization, staging, receipts, anything whose
  evidence requires adversarial filesystem manipulation — goes to a **claude**
  auditor. That work is codex-authored, so a claude auditor is properly
  cross-vendor AND is not subject to the filter that blocks the incumbent.
- Everything else — UI, copy, contracts, honesty audits — stays with the **codex**
  auditor, which is cross-vendor against the claude-authored work that makes up most
  of it.

Both write no feature code, which is what makes either able to review anything.

Note this makes vendor independence BETTER rather than worse. The previous
arrangement had a codex auditor reviewing codex-authored security work and
disclosing same-vendor weakness in every verdict — it flagged, accurately and
repeatedly, that a different vendor was likelier to challenge the physical-path and
newline-framing assumptions it shared with the author. It challenged them anyway and
found them, which earned it credit and did not make the arrangement sound. Splitting
by topic happens to put the cross-vendor auditor on exactly the work where
same-vendor review was weakest.

The constraint that forced this is a tooling limit, not a judgement about either
model. Recorded so that a later reader does not conclude the codex auditor was
removed from security work for performance reasons. It found the S0.

### D27 — The auditor refused both my options and gave a better third; D24's line holds

I asked the security auditor for MERGE or DO NOT MERGE on the receipt scope guard.
It gave neither, and its reasoning is better than my framing, so it is adopted.

First, it answered the question I had put twice and never had answered: what would
be TRUE if the closure were structural that would be FALSE of an enumeration. It
found one — a surviving explicit rollback is measurably REDUNDANT, because the
region is carried by the construction itself. Redundancy of a hand-written guard is
the signature of a structural closure, and it is false of an enumeration, where
every guard is load-bearing. The original symptom then survived ten adversarial swap
cases at four windows with zero escapes.

Then it declined both verdicts:
- Not MERGE, because the branch ships `s0_reachable=no` and **that is not true** —
  publication contains an operation that violates the construction's own discipline,
  and D24's standard is "closed by construction END TO END", which includes
  publication. Merging would be the third consecutive merge carrying an open
  S0-class defect justified by "it strictly dominates" — the treadmill D24 exists to
  stop.
- Not DO NOT MERGE, because the defect is pre-existing and identical on integration,
  so holding the branch buys nothing on it and costs a real improvement. And the fix
  is three lines in the same object with the suite green, which it ran.
- So: fix it on this branch and re-audit. "That gets you the clean third round D24
  asked for instead of another dominating merge."

**Adopted.** That is the outcome D24 was written to produce and I had not seen it,
because I had framed the choice as ship-or-hold when the actual answer was one short
round. A rule that binds the manager is worth more when someone uses it to find the
option the manager missed.

Also carried into the merge commit whichever way it lands: the branch's contract
claims closure by construction "from physical publication through exact-byte staging
and commit". Everything FROM publication onward holds. Publication itself is the one
link that does not, and it is inherited rather than authored here — so the claim is
narrower than the sentence, and the sentence gets corrected rather than the claim
quietly enlarged.

### D28 — The deliverable bar, written down because "ship-quality" is not checkable and this is

The owner asked for a continuous improvement loop, running until CrossAudit is a
genuinely deliverable product of the quality that earns a wide audience.

**What I cannot do, stated first.** I cannot produce or verify a star count. Stars
follow from publishing, from an audience, and from luck, and publishing is
outward-facing and requires the owner's approval — it is outside what the manager
may do. A loop that claimed to be driving toward a number it cannot measure would be
the exact overclaim this project spends its days removing. So the loop drives toward
a bar I CAN check, and the owner decides separately whether and when to publish.

**The bar. Each line is checkable, and none of them is "it feels finished".**

1. **No open S0 or S1 against merged code.** Not "none known" — none open, with the
   audit trail showing each was closed by construction or explicitly accepted with
   its reason.
2. **A fresh-user walkthrough of the FROZEN BUNDLE passes**, not source mode. Clean
   HOME, empty project, no credentials. No silence on any action, no raw traceback
   on any path a person can reach, and no claim on screen that the code does not
   support. Today's packaged 4.15.0 fails this on all three counts.
3. **Every UX_TEST_PLAN scenario S1–S7 OBSERVED**, in both themes, both locales,
   desktop and narrow. Observed means screenshot plus page structure, per §2 of that
   plan — a cell reasoned about is not covered.
4. **A screen-reader user can complete first contact.** The ten silent containers
   closed, live regions correct by the slice-0 rule, and the path driven rather than
   inspected. Per D25 this is not polish: for that population the product is
   currently unusable, not merely worse.
5. **The first three minutes work in Chinese.** CLI i18n waves 1 and 2 complete, and
   no contract claiming parity on a surface that does not have it.
6. **Full suite green, and every guard demonstrated to fail** under a deliberate
   mutation recorded in the test (D10). A green suite that would stay green under a
   broken implementation is worth nothing, and we have found that seven times today.
7. **The invariants hold and are demonstrated**, not asserted: the audit core stays
   non-bypassable, the auditor sees evidence only, bounding is fail-closed, and
   nothing on screen or in a docstring promises more than the code delivers.

**What is deliberately NOT on this list:** feature count, benchmark numbers, and
anything measured in stars. A product that meets the seven above is one I would put
in front of a stranger. Whether strangers arrive is the owner's call and the world's.

**How the loop ends.** It ends when 1–7 hold simultaneously on a packaged build, and
the evidence for each is on record rather than remembered. If it stops making
progress — the same class of defect surviving three rounds, per D7 — that is a
finding to surface, not a reason to keep grinding.

### D29 — Two agents refused to manufacture a false all-clear from my routing gap

I dropped the independent honesty audit's findings on the first-three-minutes slice
— it returned MERGE AFTER FIXES and I never routed them to the author. That is my
failure, the same shape as D14 and D20: an action that looked complete from where I
stood and was not.

When I asked the author to pull the findings itself, it could not locate them, so it
asked another agent. **That agent refused to hand over its own list**, on the grounds
that its list was the DESIGN review, not the honesty audit, and:

> "I'm not going to paste anything that could be mistaken for it — if you closed my
> list believing it was w6's, the honesty audit would still be open and you'd think
> it wasn't."

The author then declined to proceed on the same reasoning: closing the design items
a second time and reporting "findings closed" **would have converted a routing gap
into a FALSE ALL-CLEAR, which is worse than the gap**. It asked me to re-run the
audit rather than guess at it.

Both were right, and the second failure would have been much worse than the first. A
gap is visible as a gap; a false all-clear is invisible, and it is invisible
precisely to the person who most needs to see it. This is the project's own thesis —
that a plausible claim and a verified one are different things — applied to my
process rather than to the code.

**Decided:** the honesty audit on `agentA/first-three-minutes` is RE-RUN, by the
cross-vendor auditor, before that slice merges. The consequence is real and I am
taking it: CLI i18n wave 1 is finished and green at 1714/2/0 and cannot rebase until
first-three-minutes lands, so my routing gap now costs a delay on the tier D25 ranks
as exclusion rather than degradation. That cost is mine and it is smaller than
shipping on a manufactured all-clear.

Recorded also because it is evidence the arrangement works in the direction that
matters: the agents did not need me to catch this.

### D30 — It was never a packaging problem. It was a front door nobody had reviewed.

The security audit of the frozen bundle closes with a method note that corrects my
own framing, so it is recorded as the finding rather than as a footnote:

> Three of the four axes I most expected to break — modules, package data, identity
> digests — came back clean, and the one real first-contact defect was in code that
> has nothing to do with freezing. **The frozen bundle is not a different product
> than source. It is the same product with a different front door, and the front
> door is the part nobody had reviewed.**

I had been calling this a frozen-versus-source gap and commissioning a survey of the
differences. That was the wrong shape. Freezing is fine. What was never reviewed is
the ENTRY POINT — what happens before anything a person recognises as the product
starts — because every piece of work this team has done entered through
`crossaudit console` in a directory that was already a project, with a home
directory that already had credentials, run by someone who already knew the
arguments.

**Two consequences adopted.**

**The boundary, stated once instead of per case:** *no unhandled exception leaves
`main()`, in any mode* — and the app-mode startup sequence (support dir, workspace
dir, keys, controller project, config load, bind) is inside it. The auditor found a
worse instance than the one I had: an unwritable workspace directory produces a
traceback written into a log **that the failure screen then invites the person to
open**, so we actively direct them to a stack trace. The remedy is the shape this
codebase already uses everywhere else — a Denial carrying a reason a person can act
on, printed where they are looking, with the exit code preserved.

**D28 condition 2 becomes checkable rather than aspirational.** The auditor turned it
into a guard: *for every argv shape and every startup precondition, stderr contains
no "Traceback (most recent call last)"*, with the D10 counterfactual being to remove
one `except` and watch it go red. It built a 61-shape argv matrix and two
unwritable-directory fixtures and offered them to the author rather than keeping them
as review artifacts. Evidence written by someone other than the author, before the
fix exists, is the strongest kind we have, and this is the second time today that has
decided an outcome.

**And a standing change to how UX evidence counts**, which I have given the design
engineer: a cell is not covered until it has been observed in the FROZEN BUNDLE.
Source mode remains the fast loop for iterating; the bundle is what a person runs. If
driving the bundle is materially harder, we build the instrumentation — I would
rather pay for good evidence than accept comfortable evidence from the wrong artifact.

### D31 — The shipped DMG has no command line, so every CLI surface we built is unreachable

The design engineer paused before a review it had been given, to surface this,
because the cost of deciding late was compounding — another engineer is stacking
i18n wave 2 on wave 1 right now. Pausing to say so was the right call and it is worth
more than the review would have been.

**What it found, by driving the installed bundle rather than reading the build
script.** `Resources/core/CrossAuditCore` hangs on `doctor` with zero output. The
bundle's entry point is `crossaudit.app.main`, not `crossaudit.cli.main`, and
`app.main()` handles exactly two argv forms — `--self-test` and `--project-console`.
Everything else falls through, sets `CROSSAUDIT_APP_MODE=1`, and blocks serving the
console. So `--version`, `doctor`, `init` and `build` are all silently ignored. My
two frozen defects and its one are a single defect.

And the consequence is much larger than a hung terminal. The build script's only
symlink is `/Applications` inside the DMG. **There is no CLI shim. The DMG ships a
GUI app and no command line.** The `crossaudit` on this machine's PATH is a pip
install from 3 August — not the bundle.

**So every CLI surface this team has designed is unreachable from the installed
product**: SPEC-6's front door, doctor's verdict-first restructure, the constitution
moment in `cli/wizard.py`, and CLI i18n waves 1 and 2. All of it lives behind
`cli.main`, which the bundle never calls.

**Decided, in three parts.**

1. **`app.main` dispatches CLI argv shapes to `cli.main`.** This is the work already
   in flight, and it just became the most valuable thing on the board rather than a
   tidy-up: it is what makes a large body of correct, reviewed work reachable at all.
2. **The bundle does not silently install anything onto PATH.** A command-line tool
   appears when a person asks for it, through an explicit action they consent to —
   which is the same rule this product applies to every other capability it acquires.
   Writing to a user's PATH at install time because it is convenient would contradict
   the consent model in the product's own dialogs.
3. **The GUI onboarding path gets the treatment the CLI got.** If DMG users are
   GUI-first, then the four-step onboarding I sampled today is their first three
   minutes, and nobody has walked it as a first-timer except me, once. That is now a
   design commission, not an assumption.

**Nothing built is wasted, and I am not treating it as such.** The CLI work is
already real for source and pip users, who the design engineer correctly noted are
real users, and it becomes real for DMG users the moment (1) lands. But the ORDER was
wrong: we translated and restructured surfaces before checking they were reachable in
the artifact we ship. That is D30's front door lesson arriving a second time, one
level up — nobody had run the installed product the way a person runs it.

### D32 — No anchoring of audit findings to draft passages

Same engineer, on the stream-then-BLOCK question it had flagged in SPEC-10 §5: it
checked the schema instead of asking me. A finding is severity, rule, artifact path
and prose observation — **no span, no quote** — so anchoring findings to passages of
streamed draft is impossible without changing what the auditor emits, which touches
`auditor/prompt.py`.

**Decided: do not change it.** Its reasoning, adopted: asking a model for character
offsets into a rendered increment is exactly the kind of thing it gets confidently
wrong, and **a wrong anchor is worse than none — it would highlight the innocent
passage with total assurance.** That is the §1.5 failure with extra steps, bought at
the cost of touching the auditor's output contract.

The cheaper design gets most of the value: show the finding's observation prominently
against the collapsed draft, with the artifact named, rather than in a findings list.
No new auditor output and no new failure mode. The engineer also downgraded its own
earlier "better than silence" judgement rather than leaving it standing — not to
neutral, since an observation is prose describing what and why and self-locates
better than it had assumed, but honestly less than it had hoped.

### D33 — A guard shaped like the bug it exists to catch; and §0 by proxy

Two rules from one report, both found by the engineer against its own work.

**The allowlist was a guard shaped like the bug.** Its i18n guard carried a 52-entry
allowlist of strings permitted to remain English. Given design's criterion — an entry
is justified only by TYPE, MATCH or TRACE — 37 of the 52 turned out never to have been
needed, and they included `the`, `of`, `test`, `wizard` and `shell`, accumulated from
wrapped sandbox paths. Those are prose. **An allowlist padded with English words is a
guard shaped like the bug it exists to catch**, and real untranslated copy could have
walked straight through it.
It is now 15 entries, each justified and grouped by which criterion justifies it, with
a test asserting that every declared entry is actually needed — so the allowlist
cannot silently re-accumulate. That last part is the fix; the pruning alone would have
regrown.

It also found the guard's path-fragment exclusion depended on **where `tui.note`
happened to wrap a long path**, so whether the guard held varied with the length of
the sandbox's directory name. A guard whose verdict depends on the test environment's
name is not a guard. Now deterministic.

This is the eighth instance today of the same family — something that looks like
verification and is not — and the first where the mechanism was an *allowlist growing
by accretion*. Add it to the pattern: **any list of exceptions needs a test that each
exception is still required**, or it becomes a hole that widens quietly.

**§0 by proxy.** In the same exchange, the design engineer declined to accept the
author's rendering of its own four items and re-drove them itself, on the grounds
that **"an author confirming their own fix to the reviewer is §0 by proxy."**
Adopted. §0 says no agent reviews work it wrote; the corollary nobody had stated is
that a reviewer accepting the author's demonstration has let the author review itself
through the reviewer's hands. A reviewer re-runs; it does not receive.

### D34 — "Changing the rules never changes a decision already made" is false, and D8 rested on it

The re-run honesty audit executed the claim instead of reading it, and it does not
hold. Using the real audit command and controller: one immutable science SHA
processed as round 1 **BLOCKED**; then the constitution alone was loosened and
committed; the same SHA re-entered the same cycle as round 2 and became **PASSED**,
and the cycle's operative status changed from BLOCKED to PASSED. Only the provider
verdict was substituted locally — commit selection, constitution selection, cycle
advancement, receipt assembly and status mutation were all the shipped
implementations.

And the guard: **"The existing guard checks only that the sentence appears before the
menu — it never tests the behaviour asserted by the sentence."** Ninth instance today
of a check that looks like a check.

**Why this is more than a wrong sentence.** D8 decided that a person may freely edit
their own constitution, that the screen SHOWS rather than polices, and that no
warnings are needed — and the entire argument rested on this being true: because
every audit cites the constitution commit and rule changes take effect only between
cycles, **nobody can amend their way out of a decision already made**. That premise
is false, so the design it justified is currently unsafe. A BLOCK can be undone by
loosening the standard and re-running, which makes the audit advisory in exactly the
situation where it matters.

**Decided: make the claim true rather than remove the sentence.** This is not a copy
fix. A decision already made must not be revisable by weakening the standard it was
made against — otherwise the audit is a suggestion, and this product's entire thesis
is that it is not. The sentence is right; the implementation has to catch up to it.
The rule: a cycle that has reached a verdict is closed against constitution changes.
A loosened constitution governs the NEXT cycle, not a re-entry into one already
judged.

D8 stands as a design philosophy — the line is drawn at concealment, not content, and
a weak standard produces an honest audit of a weak standard. But its safety argument
gets rebuilt on a premise that is actually true, and until then the free-editing
design is not safe to ship.

**Two more S1s from the same audit, both the same family:**
- `init` says Ready in source-mode installs where `doctor` immediately returns exit 20
  and Not ready, because a source installation cannot admit receipts. The test named
  `test_init_says_ready_only_when_doctor_would_agree` **never executes doctor**, so it
  misses a supported install mode. The name asserts the property; the body does not
  test it.
- Doctor's 21-line sweep is incomplete: a state-store location that is a regular file
  still reports [PASS] state store though `state.json` cannot exist beneath it, and
  modifying the current constitution without committing still reports [PASS]
  constitution committed — doctor established only that some historical commit touched
  the path. Both are counted in the tally, so the collapsed output reports 15 other
  checks passed while counting two false passes, and the visible "check everything"
  claim stays false.

**And a note on method that I want kept.** The auditor refused to claim its findings
matched the report I lost: *"I cannot honestly claim these findings match the lost
report verbatim; that report is unavailable in this restarted session, and inferring
equivalence would recreate D29's false-all-clear risk."* Third agent today to decline
a plausible claim it could not verify, and the first to cite a decision number while
doing it.

### D35 — A gate that can never be satisfied is as broken as one that always is

The security auditor closed the D24 arc with MERGE, and it guarded against a failure
mode I had not thought to name — my own.

D24 bound me: three consecutive merges carrying an open S0 on the same boundary and
the "strictly dominates" justification is spent. The auditor found three S3 hardening
items on this round and explicitly refused to convert any of them into a gate:

> "D24's justification was spent on open S0s, and there is no open S0 here. Refusing
> to merge over a two-bytecode ordering nit reachable only by Ctrl-C would make the
> gate unfalsifiable — **there is always a narrower window** — and that failure mode
> is the mirror image of the one D24 exists to prevent."

That is right and it is the correction D24 needed. A rule written to stop a manager
shipping indefinitely can, applied without judgement, stop a manager shipping at all
— and a reviewer can always find a narrower window, so an unfalsifiable gate is not
rigour, it is paralysis wearing rigour's clothes.

It also declined to make its own one-line remedy a condition, on the grounds that
"that would be me holding a strictly-dominating branch for a perfect answer, which is
what I told you not to do" — applying its own earlier advice against itself.

**So D24 gains its missing half:** the bar is an open S0 on the boundary, not the
absence of every conceivable narrowing. A finding that does not name a reachable
failure the product can produce is hardening, and hardening is scheduled, not gated.
The distinction is exactly the one this project keeps making elsewhere: what the
evidence establishes, versus what could conceivably be true.

**And the arc, recorded honestly because the merge commit should carry it:** three
rounds; two merged carrying a known open S0 under the "strictly dominates" argument;
the third closes the boundary end to end for every failure mode the product can
produce, and leaves three S3 hardening items — one of which is the last instance of
the very discipline the whole arc was about, and is one line.

### D36 — D34's ruling was directionally right, wrong in mechanism, and too broad

The engineer taking the cycle-integrity fix read the code before building to my
ruling, and came back with a correction in three parts. All three are adopted; my
version of D34 is superseded by this one.

**1. Where the harm actually lives.** I ruled "a cycle that has reached a verdict is
closed against constitution changes." That closes the auditor's repro, because
`const_commit` is resolved as `git log -1 -- cfg.constitution` — current HEAD, pinned
by nothing — so pinning at cycle open and auditing the pinned commit in later rounds
makes round 2 face the strict constitution and stay BLOCKED.

But that is one route, not the defect. `open_or_advance` finds a status in
(OPEN, BLOCKED) on the same SHA, sets status back to OPEN and increments the round;
the verdict recorder then assigns the cycle's status from the new round
**unconditionally**. So:

> **The BLOCKED decision is not superseded. It is erased.**

And the engineer's framing, which is better than mine: *what makes the audit advisory
is not that new work can be judged under new rules — it is that the old decision
stops existing.* Pinning blocks one path to that erasure. It does not make a reached
verdict immutable, so any other path that advances a round can still flip a recorded
BLOCK.

**2. My rule as stated would over-restrict.** "Closed against constitution changes"
would prevent a legitimate case: a person who loosens a rule *because the rule was
wrong* must still be able to re-audit that work. D8 explicitly permits a weak standard
to produce an honest audit of a weak standard — that is the whole of D8 — and my D34
wording would have made D8's permitted case impossible while fixing the abuse of it.

**3. So the rule is: a reached verdict is IMMUTABLE. It is superseded, never erased.**
A later round may produce a new verdict under a new constitution; the earlier one
remains in the record, with what it was judged against. That satisfies the sentence we
ship — changing the rules never changes a decision already made, because the decision
still exists and still says what it said — and it leaves the legitimate re-audit
available, because a new decision is a new decision rather than an overwrite.

Both clauses get built: pin the constitution at cycle open so a round is judged
against the standard its cycle opened under, AND make a recorded verdict immutable so
no path that advances a round can erase one. The first closes the demonstrated repro;
the second closes the class.

Recorded because the correction matters more than the fix: I gave a rule that would
have closed the reported bug and quietly broken a case D8 exists to protect, and the
engineer found it by reading the code before building to my words rather than after.

### D37 — The GUI is the product for the people we ship to, and it writes their constitution silently

I asked which onboarding a DMG user actually meets. The answer is categorical and it
is not close.

The Swift wrapper never sets `process.arguments`, so a double-click launches the core
with **no argv**, which is app mode. The DMG's only symlink is `/Applications`, so
nothing lands on PATH — by design, per D31 part 2. And the CLI is reachable only by
someone who knows to run
`/Applications/CrossAudit.app/Contents/Resources/core/CrossAuditCore <command>` — a
path nobody finds by accident and **the product never mentions**.

So the four-step onboarding is a DMG user's entire first three minutes, and the CLI
first-contact work — SPEC-6's front door, doctor's verdict-first restructure, the
constitution moment, i18n waves 1 and 2 — serves people who already know the product
well enough to open a `.app` bundle. Not wasted: the dispatch makes it correct rather
than broken, and source and pip users are real. **But it is not first contact for the
population we ship to.**

**The corollary is the finding.** The constitution moment is not on the DMG path at
all. `app.py` writes `AUDIT_RULES.md` **silently** and imports nothing from `cli/`. So
for the population that installs the DMG, the product still writes their governing
document without showing it to them and without asking — which is precisely the defect
the constitution moment was built to remove, still live, for everyone who meets the
product the normal way.

That also means D28 condition 5 — the first three minutes working in Chinese — is
currently satisfied for a population that is not the DMG population. The condition
stays, and it now needs the GUI path too.

**Decided.**
1. **A GUI constitution moment is a P0 design slice**, not a follow-up. Silently
   writing a person's governing document is the same §1.5 failure whichever surface
   does it, and the surface that does it is the one almost everyone uses.
2. **CLI discoverability needs an answer that is not a silent PATH install.** D31 part
   2 stands on consent grounds — a command-line tool appears through an explicit
   action a person consents to — but "consented" cannot mean "undiscoverable". The
   product must at least TELL a person the CLI exists and offer to install it. An
   unmentioned path buried four directories inside a bundle is not an offer.
3. **D28's conditions are re-read against the GUI.** Conditions 2, 3, 4 and 5 were
   being measured largely on the CLI. They are about the product a person meets, so
   the GUI is where they have to hold.

**And a defect found sideways, which goes straight to an author.** In judging the
Chinese copy the design engineer suggested a guard, and that guard caught a real
integrity bug: **`git()` strips the pinned constitution's trailing newline, so the
auditor judges bytes that are not the commit's while the receipt cites that commit.**
The receipt names a commit and the auditor saw something else. That is an audit-core
integrity defect, found as a side effect of a copy review.

It also **retracted the larger half of its own finding** once D36 landed — under D36
the English becomes true and the Chinese is true the same way — keeping only a
one-verb precision fix. Fourth time today an agent has narrowed its own claim rather
than let it stand.

### D38 — Findings go in a file. A pane is a scrollback buffer, not a record.

Three routing failures today, all mine, all the same mechanism.

1. I lost the honesty audit's findings on the first-three-minutes slice and never
   routed them (D29). Two agents then refused to reconstruct them, correctly.
2. I told an author to read a reviewer's report rather than relaying it. The author
   could not — it asked the reviewer directly, got no reply, and sat on it refusing to
   guess. By the time I went to relay it myself, **the report had scrolled out of what
   I can read.** So I could not reconstruct it either, and I will not: that would turn
   a routing gap into a false all-clear, which D29 already established is worse than
   the gap.
3. I dispatched a fix for `git()` stripping the pinned constitution's trailing newline
   to one engineer while another had already fixed it — duplicate work in the same
   function, which is D14's shape again.

The common cause is not carelessness about any one hand-off. It is that **I have been
treating agent panes as a record when they are a scrollback buffer.** A finding that
exists only in a terminal can evaporate, and the person who needs it has no way to
reach it.

**Decided, effective immediately for every agent:** findings, review reports and audit
results are WRITTEN TO A FILE, with the path printed in the status line, in addition
to being printed. Name the file after the sha reviewed. A reviewer's job is not done
when it has said something; it is done when the author can read it.

And for me: **relay findings verbatim at the moment I have them.** Pointing at a
location is not routing. I did that twice today and both times the author was left
holding nothing, refusing to guess — which is the behaviour I want and should not have
to rely on.

Recorded under my name because all three were mine, and because the pattern only
became visible when the third one arrived. One is an error; three is a mechanism.

## D39 — Verify the tree you merged, not the tree you tested

Merging the streaming slice I rebased it in a scratch worktree, ran the
suite there (1706 passed), then merged the **branch ref** — whose force
update had failed, so it still pointed at the un-rebased tip. The suite I
cited as the gate had been run on content I did not merge.

The trees turned out identical (`84f8019`), so nothing was wrong. But I
only know that because I checked afterwards, and "it was fine" is not a
gate. My merge rule says the full suite is green on the host; that claim
is about a specific tree, and I had not established which tree.

RULE: before recording a merge as gated, compare the merge result's tree
hash to the tree the suite actually ran against. Identical, or the gate is
not met and the suite re-runs on the merge commit.

This is the same shape as D33 and the codex sweep rule: a value verified
at one point does not transfer to the consumer unless the consumer is the
thing checked. Here I was the consumer and I nearly exempted myself.

## D40 — The PATH collision is S1, not S0, and the ledger is why

The engineer measured what a DMG user must know to reach the CLI: the exact
4-component 67-char path inside the .app, that a CLI exists at all, and that
the `crossaudit` already on their PATH is a *different, older* program. The
product supplies none of the four. Worse than D37 stated: the discoverable
name is actively wrong — installing 4.15.0 and typing `crossaudit doctor`
runs 3.2.0 from August, which predates every S0 fix in this cycle (symlink
escape, erasable verdict, trimmed constitution reader).

I judged this S0 on the theory that both binaries report `receipt schema 2`,
so their receipts would be indistinguishable in one ledger — a stale binary
laundering unaudited work as audited. **That was wrong, and reading
`_selfid.py` is what corrected it.** Receipts already carry the version, a
canonical digest over the loaded code, and the install mode; `verify --admit`
already refuses modes whose code could have changed since digesting. The
schema number is not the compatibility claim I took it for. The ledger
distinguishes the two producers today.

So the defect is not ledger integrity. It is that **the person** cannot tell
which binary answered them. The ledger stays honest while the human is
misled — S1: a false-premise experience on valid input, not data loss.

RULE: severity is assigned after reading the mechanism that would have to be
broken, not from the shape of the hazard. I had a plausible S0 and the
plausibility came from a field name.

Fix scope, accordingly narrow: make install mode and path visible where a
person meets a mismatch. Not a PATH install — D31 refused that on consent
grounds and that still holds.

## D41 — `verify` confirms 7 of 15 receipt claims; the gaps are in the verifier

The codex sweep enumerated every handoff on the audit and run paths where a
value reaches a consumer: **15 paths, 7 checked against source-of-truth
bytes, 8 gaps.** The gaps are not in production. They are in the *verifier*.

The receipt is a set of claims, and `crossaudit verify` re-derives fewer than
half of them from the object they cite. The four that let a false receipt
pass today:

- **#13 constitution** — the verifier hashes the *current working-tree* file,
  not `<constitution_commit>:<path>`. So the D36 pin is enforced where it is
  produced and not where it is consumed, and a receipt could cite a commit
  that does not exist.
- **#14 cycle record** — verdict immutability and the constitution pin are
  guaranteed in the controller and proved nowhere at verify time.
- **#12/#15 report bytes** — `report_commit` ancestry is checked; the bytes
  are read from the working tree, so a report can be edited after the fact.
- **#8 evidence ledger** — `evidence_view` projects entries into the auditor
  prompt without verifying the hash chain; the chain is checked only later,
  when a bound receipt exists. This one is the auditor's *input*.

This is the same shape as every defect this cycle — correct where stored,
unchecked where consumed — but at the product's centre rather than its edge.
"One replayable ledger" is the summary line; a ledger that certifies claims
it does not re-derive is certifying certification.

Dispatched as `audit/verifier-rederives-claims`, ranked by whether a false
receipt passes. #9/#10/#11 (DCL digest, checks list, skills manifest) are
real, queued, and explicitly excluded from that branch so their absence is
not read as closure.

The sweep is trustworthy *because* it refused to count the constitution path
as fixed on the strength of the creation-side byte matrix. A sweep that
rounds toward "covered" is worth nothing.

## D42 — Split the row: producer and consumer get separate verdicts

The mint audit returned MERGE AFTER FIXES on two rows that would have been
one averaged PASS:

- *Unknown server contract* — empty and unsuggested for all five unfamiliar
  kinds. **Pass.**
- *Unknown rendered behaviour* — **positive suggestion remains.**

The server is right: an unrecognised failure kind produces no suggestion,
which is the fail-closed behaviour specified — when we know least we must
not sound confident. The Decision Center simply does not read the capability
fields, so the surface offers optimism the runtime explicitly declined to
express. A response-shape assertion would have called this green, because
the response *was* green.

Third occurrence today of correct-at-the-producer meeting wrong-at-the-
consumer (with the constitution bytes and the mint itself). It is now the
dominant defect shape in this codebase, and averaging the two into one
verdict is what hides it.

RULE: when a contract has a producer and a renderer, the audit reports two
rows. A single verdict over both is not permitted, because the failing half
is invisible in the average.

### Count divergence — D39 on the author's side

The auditor reported the supplied suite count (1625) not reproducible at the
SHA, and 1611 reproducible. I ran it independently at 5c34004: **1611
passed, 2 skipped, 0 failed.** The auditor was right; the author's number did
not come from the tree it committed.

Same defect as my own merge earlier: citing a suite count is a claim about a
specific tree, and citing it means establishing which tree. The rule from
D39 now binds agents as well as me — report the count from the committed
SHA, in a detached checkout, or do not report one.

Verifying the count paid for itself the first time it was asked for.

## D43 — A claim contingent on work in flight is removed, never hedged

SPEC-12 needs a sentence about what happens between cycles that is only true
once the constitution pin is enforced where it is *consumed* (D41). The
design engineer wrote it as a conditional: if the verifier gaps do not
close, the line **comes out** rather than gets softened.

That is the rule. A hedged claim is how "technically kept and substantively
broken" happens — which is the same engineer's grade for the current draft
behaviour, where the promise that the reviewed text governs is honoured in
form while the bytes are generated after the review.

RULE: when a user-facing claim's truth depends on work not yet landed, ship
it whole or not at all. Softening it into something defensible is how a false
sentence survives review.

Status: I cleared the sentence on D36 having landed. The pin is proved where
it is set and not yet where it is consumed. If D41 does not close, the line
comes out — it will not ship on a stale clearance from me.

### Two guard-construction rules from the same spec pass

- **Compare against the rendered expanded text, not the variable the renderer
  was handed.** A guard fed the renderer's own input proves only that the
  renderer agrees with itself. Reported as having failed that way four times
  this week, and it is D42's shape from the client side.
- **Compute from the accessible name, not from the presence of an attribute.**
  `aria-labelledby` pointing at a missing id yields an empty name: passes an
  attribute check, fails a person. Its i18n twin — assert on the pattern
  catalogue, not a fixed string, or every provider whose name is substituted
  falls back to English.

### Dispatch correction

The same bundle drive incidentally observed that `doctor` **already** reports
`install: frozen-app` with a code digest. D40 was briefed as if that were
absent, so that work is narrower than I specified and the engineer has been
told to shrink it rather than build to my brief. Second time today an agent's
side-note corrected a dispatch of mine.

## D44 — Readability before consent; and a merge I cannot prove was reviewed

### The ordering was mine and it was wrong

I commissioned the GUI constitution *consent moment* first. The security
auditor overrode it from the artifact:

> Not the silent write. Fixing that alone gets you a consent dialog for a
> document the person still cannot open afterwards.

The design engineer and I had both already named the trap — the moment must
not become a licence agreement — and I then sequenced my way straight into
it. Consent to a document you cannot subsequently read is a form, not a
choice. Order is now: make the rules readable in Settings › Audit (which
already exists and today renders one sentence), then the moment.

Auditor's F2 is the finding underneath: **a GUI user cannot resolve a verdict
to the rules that produced it.** Remedy queued — the verdict carries and
displays its `constitution_commit`, one additive field in the cycle store,
same shape as D15's `n_a`, derived not guessed.

Also from that audit: `# Constitution — <PROJECT>` is unsubstituted in the
controller's constitution while the demo's is correct. Graded S3; I disagree
with the grade's implication — the case that works is the demo and the case
that is broken is *the project every GUI user is handed*. A placeholder
leaking on the default path is a first-contact defect.

### The S0 I posited does not exist

Eighteen local GUI actions, each with the constitution digested before and
after: zero mutations, final digest equal to baseline. Third severity
hypothesis of mine corrected by evidence today (with D40 and the ledger
theory). Each time the correction came from executing the thing rather than
reasoning about it. That is the system working, and it is cheaper than being
right by luck.

### A gate failure of my own

Task #38 records `b753fbc` (frozen-entry boundary) as "awaiting review".
**I merged it.** My merge rule requires a clean independent review and I have
no record of one clearing this commit.

I am not reconstructing whether a review happened — that is the false
all-clear D29 forbids. It is being reviewed now, post-merge, cross-vendor,
against the artifact. The gap is recorded under my name regardless of what
the review returns, because the defect is that I merged without establishing
the gate, not that the code is necessarily bad.

## D45 — Context exhaustion is a management failure, not an agent failure

I noticed the UI engineer at **97% context** only because it happened to be
visible in a pane read I did for another reason. It was mid-slice with two
fresh S1s queued — a normalisation seam and a contradicting headline, both
needing the whole state in view.

I have been monitoring agent *state* (working / done / stalled) and not agent
*capacity*. An agent at 97% is nominally "working" and is about to lose
everything it has not written down. The monitor cannot see that; I have to.

MECHANISM: when an agent approaches its context limit, it stops, commits what
is coherent, and writes `_handoff/<name>-<sha>.md` containing what a fresh
agent with none of its context would need — what the slice covers and does
not, queued findings restated in its own words (so I can tell whether they
arrived intact), any rule it discovered that exists nowhere else in writing,
and anything it believes but has not proven, marked as such. Then a clean
restart. **It loses the conversation; it does not lose the work.**

Do not let it "just finish first." A subtle fix written by an agent about to
be compacted mid-reasoning is the worst of both — the work is done badly and
the context is gone anyway.

This is D38 generalised. D38 said a finding that lives only in a pane can
evaporate. So can a *method*: the UI engineer's locale-timing rule
(announcing synchronously speaks the English source while the accessible
name, built from the same two nodes, is already translated, because the
locale observer runs a microtask later) exists nowhere in writing, and three
occasions where its guard went red for the wrong reason are pure hard-won
calibration a fresh agent would re-learn expensively.

## D46 — A change contract can outlive the code it describes

The i18n engineer corrected one of its own earlier contracts unprompted: it
claimed Chinese parity satisfied for a `doctor` surface that **no longer
exists**. The claim was true when written and became false when the surface
was replaced — and nothing in our process would have caught it, because we
review contracts against the diff they ship with, never again afterwards.

We lean on contracts heavily: they are how I gate merges and how auditors
scope. A contract that has quietly decoupled from the code is the same
defect class as everything else this cycle — accurate at the producer, wrong
at the consumer — except the consumer is me.

RULE: when a slice removes or replaces a surface, the author checks whether
any earlier contract asserted something about it, and corrects it in the
same commit. An unprompted correction of one's own past claim is the
behaviour to copy.

### "Present, not satisfied" is a legitimate i18n state

The same engineer declined to offer `--lang` on the front door: the string is
translated from the first draft, but one Chinese line in an otherwise English
front door is precisely the seam D21 exists to prevent, so it stays
unreachable until wave 3 lands. Doctor's extended line is machine detail,
untranslated by design per SPEC-7 §4.

That is the honest report — **translated from the first draft, reachable when
wave 3 lands** — and it is better than either claiming parity or claiming a
gap. Recording it so the distinction is available to everyone: a string can
be *present* and deliberately not yet *reachable*, and saying so is not
hedging (D43) because the claim being made is accurate and complete.

## D47 — Retain the last shipped bundle; artifact regression must not be luck

The post-merge review of `b753fbc` came back essentially clean — 18/18 verbs
reach the CLI, 0 raw tracebacks across 60 artifact shapes, every refusal
carrying an actionable `DENIED (config)` line, three known S3s unchanged and
one of them inherited. So the gate failure recorded in D44 was procedural:
I merged without establishing the review, and the code holds. The gap stays
recorded under my name; the code is cleared.

The auditor then raised the thing only its position could see:

> This audit was only possible because two bundles happened to still be
> sitting on disk.

Answering "did a late boundary catch a legitimate path" requires a
*before*-artifact, and nothing in our process keeps one — the DMG build
overwrites into `dist/`. Artifact-to-artifact regression checking has been
luck three times today, and each time it found something.

DECISION: the last shipped bundle is retained deliberately. Every DMG build
archives the previous artifact before overwriting `dist/`, so a before/after
comparison is always available. This pairs with the standing frozen-bundle
reachability gate adopted from the i18n engineer.

### The general form of the S3 objection

I argued the unsubstituted `# Constitution — <PROJECT>` placeholder was worse
than its S3 grade because the case that *works* is the demo and the case that
is *broken* is the project every GUI user is handed. The auditor generalised
it better than I stated it:

> A defect in the default path wearing a low severity because the working
> case is the one nobody meets. That asymmetry is the tell — the same shape
> as this bundle being one commit behind HEAD: the tested thing and the
> shipped thing drifting apart quietly.

RULE: severity is graded on the path a person actually takes. When the
correct behaviour lives on a path few reach and the broken one is the
default, the grade follows the default. This is D39's shape (tested tree vs
merged tree) restated for users instead of commits.

## D48 — I asserted a merge that never happened

I told the design engineer: *"D36 has landed — verdict immutability plus the
constitution pinned at cycle open merged."* I also marked the task complete.

**`fix/cycle-integrity` has never been merged into v5-redesign.** It is a
committed, unreviewed branch. I found this only because an unrelated audit
made me suspicious of my own record and I checked the branch list.

This is worse than D44. There I merged without establishing a review — a
process failure over working code. Here I **asserted a state that did not
exist**, and a downstream decision depended on it: the design engineer had
written the between-cycles sentence as conditional on D36 landing, exactly
per D43, and I supplied a false input to its own correctly-built gate. The
clearance is retracted and the sentence comes out rather than gets softened,
which is that engineer's rule and I am not exempt from it.

The mechanism is the same one D38 and D45 already named, arriving from a
third direction: **I have been treating my own memory as a record.** A pane
is a scrollback buffer; a task list is a to-do; neither is the repository.
Only `git` knows what is merged.

RULE: merge state is **re-derived, never remembered**. Before telling anyone
a slice has landed — an agent, the owner, or myself in a decision entry — run
`git branch --merged` or name the merge commit. "I merged it" is not
evidence; `c34dfd9` is.

I applied this to my own streaming merge an hour ago (D39, tree hash checked
against the tree I tested) and then failed to apply it to someone else's
branch, because verifying my own action felt like the risky case. The risky
case is any claim about state that I did not just derive.

What is actually true, re-derived at the time of writing:
- `fix/cycle-integrity` — committed, unreviewed, **unmerged**. Cross-vendor
  audit dispatched.
- `audit/verifier-rederives-claims` (6342459) — committed, **unmerged**,
  under cross-vendor audit.
- Merged and real: streaming (`c34dfd9`), frozen entry boundary (`b5b3ea5`,
  post-merge review now clean), receipt scope guard (`9195ab7`).

## D49 — D36 pinned `audit` and left `run`; and the receipt hashes the wrong file

Cross-vendor audit of `fix/cycle-integrity` (138db3e): **DO NOT MERGE, one
S0.** Holding this branch was right, and my D48 claim that it had landed was
wrong in a second way — it is not merely unmerged, it is unmergeable as it
stands.

**S0.** `cmd_audit` passes the **pinned** constitution text to the auditor and
passes **`const_path.read_bytes()`** — the current working file — to receipt
construction. A cycle pinned to strict commit C reaches BLOCKED; the
constitution is loosened at L; work continues. The auditor correctly judges
C's bytes. The receipt **cites C and hashes L**. The shipped verifier returns
`verified=true`, `admission_ready=true`, no shortfall, because it re-reads the
working file too. A receipt that names one constitution, hashes another, and
reports an audit against the first clears the binding gate. In this source
harness it was stopped only by the unrelated rule that source installs may
verify but never admit — **in a frozen build that last stop is gone.**

**And the larger finding: `cmd_run` has no pin at all.** It calls
`open_or_advance` without `constitution_commit`, re-reads the working
constitution every round, and writes the current commit into its receipt.
Both guided-path verdict records carried an *empty* constitution commit.

D36 pinned `audit` and left `run` — and `run` is the front door. **I accepted
D36 as done on the strength of the `audit` path.** That is my failure, not the
author's: I verified the mechanism on the surface where it was demonstrated
and did not ask which other surfaces open cycles. It is D47's rule turned on
myself — the working case was the one fewer people meet.

**S1.** `run` still advises "to re-audit this same commit, use `crossaudit
audit --sha …`", which now always refuses. The change created a dead end with
no working dispute route.

Interaction: codex's unmerged `audit/verifier-rederives-claims` makes the
verifier re-derive from the cited commit, turning this S0 from *silently
accepted* into *caught*. A caught bad receipt is still a bad receipt. Both
halves are required and neither branch may be treated as covering the other.

What held under attack, and it is most of the branch: 40 two-process races
produced exactly one winner and one verdict row; SIGKILL on both sides of the
atomic replacement produced intact state and never partial or erased; both
test inversions were judged justified with reasons; the permitted direction
genuinely works; the suite count matched at the SHA.

## D50 — Holding one branch changed the safety of another

The codex engineer, asked to justify inverting a test, traced the property
that test protected — "a receipt is rejected when the working-tree
constitution differs from what was audited" — and then refused to assume it
had landed somewhere else: *"if the merged 27b5653 doctor fix is not present
in integration, this is an open gap rather than a disappeared requirement."*

I checked. **`constitution_commit_state` exists only on
`agentA/first-three-minutes`, which is unmerged because I am holding it** —
for an unrelated reason, a sentence in it that is currently false. That hold
is still right. But it means merging the verifier branch as it stands would
leave the drift-detection property **living nowhere in the product**.

The security auditor reached the same conclusion independently from the other
branch: *"the drift property is now formally homeless while the branch that
would house it is unmerged... that's a sequencing decision rather than a code
one, and it's yours."* Two agents, two directions, same gap.

**My process could not have caught this.** I evaluate each branch against
v5-redesign in isolation. Nothing looks at what a *hold* removes from a
branch that is otherwise ready. A hold is not neutral — it is an edit to the
integration branch's future contents, and its effects land on other people's
work.

RULE: when holding a branch, ask what that branch is the only home for. When
clearing a branch that relocates a property, name where the property now
lives and verify it is reachable **in the integration branch**, not merely
somewhere in the repository.

Resolution: the `constitution_commit_state` check is being extracted as its
own slice that can land independently of everything blocking
first-three-minutes. The verifier branch's stated behaviour change — *"the
verifier ignores post-audit working-tree drift and validates the immutable
commit named by the receipt; drift remains a separate doctor concern"* — is
sequenced behind that extraction, because until it lands the sentence
describes a check that does not exist (D43).

### Two more from the same audit

- **F5 is against my own template.** The change-contract commit messages
  contain literal `\n`, so `REVIEWER:` and `AUDIT:` are not real git
  trailers — `%(trailers)` returns nothing. The contract mechanism I built
  to make review provenance machine-readable has never been machine-readable.
- The auditor applied D35 to itself: the remaining findings are hardening,
  scheduled not gated, *"because F3 is exactly the kind of small,
  newly-introduced defect it would be easy to hold a strictly-dominating
  branch for."* It also asked that F3 be recorded as **introduced here, not
  inherited**, so it is not later mistaken for pre-existing.

### D50 addendum — the tree check fired, and the answer was benign

Merging the verifier branch, the D39 comparison reported merged tree
`73e85eb` against tested tree `67ec669`. The difference was **exactly one
file**: `docs/DECISIONS.md`, 50 lines, the D50 entry I committed to
v5-redesign after creating the test worktree. Source trees identical.

Two things worth keeping:

- The check firing on a benign difference is the check working. A gate that
  only ever returns "identical" is indistinguishable from one that is not
  running. This one has now returned both answers.
- The merge brought in `tests/test_cycle_integrity.py`, which looked for a
  moment like the DO-NOT-MERGE branch arriving by the back door. It is not:
  `fix/cycle-integrity` is still unmerged, `const_path.read_bytes()` does not
  appear in the integration branch, and receipt construction now goes through
  `read_committed_bytes`. The file is codex's own test for the cycle-record
  claim (#14) that happens to share a name. **Checked rather than assumed** —
  a filename is not provenance.

MERGED (local): `audit/verifier-rederives-claims`. Verify now confirms what
the receipt cites.

## D51 — The pin sweep: 3 omissions, 5 by design, and a receipt that backdates skills

Class sweep of every path that opens, advances, or records against a cycle,
and every receipt field naming a source of truth.

**21 production paths.** 13 pin-establishing or pin-preserving. **5 unpinned
by design** — three pre-revision escalation producers and two explicitly
illustrative sample-project mutations. **3 unpinned by omission** — `cmd_run`
open/advance, continuation, and verdict recording. 0 unclassified, 0 direct
cycle-JSON bypasses.

The design/omission split is the part that made this worth asking for. I told
the auditor not to assume an unpinned path is therefore broken: a continuous
build tracking evolving rules is not obviously wrong, and what is wrong is
doing it silently while writing an empty commit into a receipt. It came back
with five defensible and three not, rather than eight problems.

**Scope of the omission is total on the front door:** *"All app, Console,
CLI-build, talk-generator, and provider-retry surfaces converge on this same
`cmd_run` path. There is no GUI-only implementation that repairs it."*

**15 receipt claim groups, 13 source-derived, 2 gaps.** One is the known
constitution S0 — hashes current disk while naming a commit. The other is new:

**S1 — receipts attribute later, uncommitted skills to earlier work.**
`inputs.skills` included `skills/late.md` across all four judgment routes,
although that file was absent from the audited subject commit and created
only afterward. The field records current disk state, not guidance
demonstrably used to generate the work. A receipt asserting that a skill
informed work which predates the skill is a provenance falsehood, and it is
the same shape as the constitution gap: the field names a source of truth and
the writer reads whatever is on disk.

Positive controls were reported alongside: dirty science stayed excluded from
the manifest in all four routes, and report hashes matched the written report
bytes in all four. A sweep that reports only failures cannot be distinguished
from a sweep that only looked for them.

## D52 — An English selector silently truncated a Chinese sweep

The design engineer's D28 sweep of the shipped artifact reported its own
instrument failure rather than its coverage:

> My harness advanced stages with a `button:has-text("Continue")` selector,
> and in Chinese that button reads 继续. So the zh cells never left
> READINESS — zh PROVIDERS and zh ROLES were not observed. That's my
> instrument, not the product.

The sweep would have reported 32 cells covered and I would have believed it.
The two cells most load-bearing for i18n would have been unexamined. This is
the day's dominant defect class — the instrument agreeing with itself while
missing the person — arriving in **our own tooling**, which is the one place
we had not looked.

RULE: test instruments are locale-aware **by construction** — a role or a
stable id — never by adding the next translation to a list. Same shape as
"compute the accessible name, do not check for an attribute."

### Findings, and a second correction to my own dispatch

- **A readiness item states a false consequence in both languages**: "without
  a name and email CrossAudit cannot record audit history", while
  `app.py:98-99` commits with a fallback identity. History *is* recorded.
  Copy that overclaims a harm is the mirror of a check that overclaims a
  verification, and we have spent the day deleting the latter.
- **The CLI front door never renders for a bundle user** — SPEC-6's screen
  exists only in source mode. I had dispatched the install-mode mismatch to
  be shown *on the front door*. It does not exist on the DMG path. **Second
  time today I briefed that task against a surface I had not verified**, the
  first being an assumption that `doctor` did not already report install
  mode. Both corrections came from an agent's incidental observation, not
  from my process.

### The placeholder is regraded

I argued `# Constitution — <PROJECT>` was worse than S3. The design engineer
gave the argument that settles it: *"a template placeholder survives only in
a document nobody was ever shown."* It is not a blemish, it is **evidence of
the silent write** — the defect SPEC-12 exists to remove. Regraded and folded
into that spec.

### What passed, stated because it is the point of the workstream

Across all 32 cells: **zero ✓ on any onboarding stage**, zero horizontal
overflow, zero JS page errors, WELCOME with no Latin at all in Chinese, and
D31 closed **in the artifact** rather than only in the branch. The
false-verification defect that started this work is absent from first contact
in the shipped build.

Unreached and explicitly not inferred: S2, S4, S5, three of four escalation
causes, the demo's inner surfaces — all need a funded run.

## D53 — I got the capture point wrong three times in twenty lines

D47 said retain the previous shipped artifact. I wrote about twenty lines of
shell and got it wrong twice before it worked:

1. **`ditto "$APP" "$PREV/CrossAudit.app"`** — at that point in the script
   `$APP` is the build just made. "The previous artifact" would have been the
   *new* one wearing the old one's name: worse than retaining nothing, because
   it would look like evidence. Fixed by extracting the app from the previous
   DMG instead.
2. **The block sat after line 42**, which is
   `rm -rf … "$DIST/CrossAudit-$VERSION-arm64.dmg"` — the build deletes the
   previous DMG at the very start. So the guard skipped correctly and the
   feature silently never ran. The code was right; its **position** was wrong.

Both are the family we have been finding all day in other people's code: the
value read at the wrong moment. I have spent the session insisting that a
value correct at the producer can be wrong at the consumer, and then made the
same error three times in my own twenty lines.

Two process points, and the second is the one that matters:

- **A feature that silently does nothing looks exactly like a feature that
  works.** After the second attempt the build exited 0, every verification
  step passed, and `dist/previous/` did not exist. Nothing failed. I only
  found it because I went to look.
- **I ran it rather than reasoned about it, and that is the only reason I
  know.** I had committed both broken versions. It is now verified by
  execution: `dist/previous/` holds the prior DMG, its sha256, the `.app`
  extracted from *that* DMG (timestamped from the previous build, not the
  new one), and a retention timestamp.

The rule I have been applying to guards applies to build tooling: a mechanism
that has never been observed doing its job has not been shown to have one.

### Merged this round

- `audit/verifier-rederives-claims` — verify re-derives what the receipt cites.
- `audit/constitution-drift-visible` — doctor fails and de-tallies a drifted
  constitution.

**`2017227` is held**: the verifier branch's behaviour sentence says drift is
"a separate doctor concern", and `app_doctor` has no drift check. It would be
true of the CLI and false of the GUI. The security auditor blocked it using my
own regrading argument — the working case being the one nobody meets.

## D54 — The fix made the failure coherent instead of contradictory

Cycle-integrity R2 (`2e22e3c`): DO NOT MERGE. Four of five closed — all three
`cmd_run` omissions, the five unpinned-by-design paths untouched, skills
deriving from subject-commit bytes, the impossible same-SHA dispute command
gone with honest output. **Receipt bytes equal auditor bytes 4/4 routes**, so
the second-read defect the author set out to fix is fixed.

**And the S0 is still open, through the fix.** The shared `GoverningStandard`
reads the *working* constitution whenever the selected commit equals the
latest constitution commit, then names that commit:

| Route | Cycle pin | Auditor bytes | Receipt hash | Receipt commit |
|---|---|---|---|---|
| `audit`, new | C | **W** | **W** | C |
| `run`, new | C | **W** | **W** | C |
| both pinned continuations | C0 | C0 | C0 | C0 |

Auditor and receipt now agree with each other while both disagree with the Git
object they cite. The author corrected "two reads disagree" by making it one
read; the one read is from the wrong place.

**Consolidation was the right move and it made the failure coherent instead of
contradictory — which is worse.** A contradiction is detectable. A consistent
wrong answer is not. This is the renderer-agrees-with-itself defect arriving at
the audit core *by way of its own repair*, and it is the sharpest form of the
class we have hit twelve times today.

The trap is the condition: `selected commit == latest constitution commit` is
exactly the case where the working file may be dirty and differ from the
commit. It reads as a safe shortcut — same commit, why re-read the object —
and it is the single branch where the shortcut is wrong. Ruling: **delete the
equality shortcut, do not guard it.** A fast path that is right except in the
case that matters is not a fast path. The pinned continuations already show
the correct shape in the author's own code.

### Verifying the author's self-report paid for itself

The author reported catching three guards that could not reach the code they
guard, and fixing them. I asked for independent verification anyway, saying it
was not doubt but that such a claim must not rest on the author's word —
**including when the author is the one who found it.** The auditor's aggregate:
`guards_reach=no`. The class was wider than the instances the author caught.

### A count that looks clean is not a clean count

Reported 1669 is not reproducible. The detached SHA collects 1,672 (1,670
executable, 2 skipped). Two full runs each produced **1,669 passed and one
failure** — a different one each time: the prescribed GitHub flake, and a new
one, an unexpected provider request in the project-deletion parameter. All
1,670 pass in isolated reruns; **no single full run was green.**

"1669 passed" and "1669 passed, 1 failed" are different facts that look
identical once the second half is dropped. RULE: report collected total,
passed, and failed — never the passed number alone. And an unexpected
*provider request* on a deletion path is not obviously a flake; it is being
diagnosed rather than re-run.

## D55 — `app_doctor` omits the half the product exists for

I asked whether `app_doctor` was missing one check or systematically thinner.
The answer was neither, and it is a product finding rather than a check one:

> `cmd_doctor` asks "is this project's audit trustworthy?"; `app_doctor` asks
> "is this Mac able to run the app?" Six GUI rows have no CLI twin, so it
> isn't a subset. **What it omits is the entire audit-integrity half — the
> half this product exists for.** The GUI can tell someone their Git is too
> old and cannot tell them their audit is running against rules they've never
> seen, on an install that may verify but never admit.

The two doctors are not one check apart. They answer different questions, and
only one of them asks the question CrossAudit is for. A parity **docstring**
has been asserting otherwise for free — D46's shape (a claim outliving the
code it describes) living in documentation instead of a contract.

**F3 (S2), found while chasing why the GUI said 0.** `console/server.py:768`
computes the rule count as `const.read_text().count("\n### ")` on the working
tree. Two independent defects in one line: it reads the wrong file, and
`count("\n### ")` **cannot see a heading at byte 0**, so any constitution that
begins with a rule is under-reported by one, silently and permanently. Per the
earlier GUI-honesty audit, that integer is *the entire account of the standard
a GUI user gets.* The "rules = 4" I accepted as correct was correct only
because that constitution happened not to start with a rule.

Closure, adopted as specified, and the third step is the one that matters:
1. move the helper to a shared module;
2. give the constitution row three states (missing / drifted / ready) carrying
   the CLI's **exact sentence**, so both doctors say the same thing in the
   same words;
3. **a test that enumerates `cmd_doctor`'s check names and asserts each is
   either present in `app_doctor.collect()` or on a named, recorded exclusion
   list.**

Step three turns the design-versus-omission distinction — the thing that made
the pin sweep worth asking for — into an executable guard. Steps one and two
close today's gap; step three is why we would not be back here in a month.

`2017227` stays blocked. The auditor's own note on the cost: *"the block is
cheap to clear: there's no design decision to overturn here, only an omission
behind a docstring that claimed otherwise."*

### Team change

Added a second claude auditor (`auditor2`, wA). Cross-vendor review requires a
claude auditor for codex-authored work, and three audit-core branches
(`receipt-derives-remaining`, `mint-render`, plus this) were queued behind one.
The backlog was real and recurring, not a reason to grow the team for its own
sake.
