# The activity stream

Why CrossAudit's conversation surface is being rebuilt, what it is being rebuilt
into, and the rules that keep it that way.

## The diagnosis

CrossAudit's console renders the **audit protocol's state machine**. Cycles,
verdicts, escalations and receipts are first-class objects on screen: a state
changes, a card appears, with a heading, a badge, sections and buttons.

Claude Code and Codex render **the user's activity**. Everything that happens —
a thought, a file read, a command, an error, a question — is one row in one
chronological list, in one visual language, collapsed to a line until asked to
open.

Every complaint the owner has raised follows from that one difference, not from
five unrelated defects:

| Symptom | Because |
|---|---|
| A provider returning an empty completion produces the same heavy card as a real audit dispute | Both are "the state machine stopped", and the state machine is the UI |
| The generator's draft is dumped in full | There is no row concept for it to collapse into |
| The thinking animation means nothing | There is no information line for it to mark |
| A commit with no experiment in it says "the audit needs your decision" | A setup mistake and a judgment call share one surface |
| Raw shas and internal words reach the screen | The protocol's own vocabulary is what the surface was built from |

Patching these one at a time produces five better cards. It does not produce a
harness anyone would rather use.

## What the reference harnesses actually do

Observed from the inside, running as an agent in Claude Code. These are
interaction patterns, not styling:

1. **One list.** User messages, agent prose, tool calls, results, errors and
   questions are all rows in the same chronological stream. Nothing lives in a
   separate region that the eye has to learn.
2. **A row is a line.** A tool call is `Read(file.py)`; its result collapses to
   `Read 200 lines`. Detail is one keystroke away and never a navigation.
3. **One status line while working.** A verb in the present participle, the
   elapsed time, the size of what is accumulating, and how to interrupt. It
   occupies one line at the foot of the stream and is replaced by the result.
4. **Errors are rows.** A failed command shows its error in place and the loop
   keeps going or asks. The shape of the interface does not change because
   something went wrong.
5. **Questions are rows.** A permission prompt or a choice appears inline with
   numbered options; the stream continues underneath the answer.
6. **Nothing is modal.** The person is never blocked from typing, scrolling or
   leaving. Attention is asked for by weight and position, not by covering the
   screen.
7. **The verb carries the phase.** "Thinking", "Reading", "Running", "Writing" —
   short, present, in the reader's language, never an internal state name.
8. **One number per row.** Lines read, tokens, files changed, seconds. The number
   that would change what you do next, and no other.
9. **Repetition collapses.** Three consecutive reads become one row with a count.
10. **Density without decoration.** No empty regions, no illustrations, no badge
    that says zero.
11. **Interruptible always.** One key stops the work; typing during work queues.
12. **Identifiers appear only when actionable.** A file path yes; a commit hash,
    a session id, an internal status constant, no.

## The design

### Five row shapes, not twenty-eight event kinds

The loop emits roughly thirty event kinds. The stream renders five shapes. This
is the discipline that keeps it coherent as the engine grows:

| Shape | What it is | Renders as |
|---|---|---|
| **Say** | Words from a person or an agent — your message, the auditor's stated reason, the generator's note | Full text, wrapping |
| **Do** | An action that finished — drafted, committed, checked, audited, rendered | One line, a verb and one number, expandable to its detail |
| **Wait** | Something in progress or retrying | One live line, replaced by its Do row when it resolves — never both |
| **Outcome** | A round's result — passed, needs changes, needs you, checks only | One weightier line; carries the actions when it needs a person |
| **Note** | Worth knowing, needs no action — a budget threshold, a rolled-back attempt, a caution passed to the auditor | One muted line |

Every event maps to exactly one shape. A new event kind must name its shape
before it may be emitted.

### The row

    [actor mark] [verb phrase] · [the one number] · [elapsed]        [›]

- **Actor mark**: a small mark for the generator or the auditor; while a phase is
  live it is the Thinking Orb for that phase, at 20 px, at the head of the line.
  An animation never appears without words beside it.
- **Verb phrase**: present tense while live ("正在撰写"), past when done
  ("已撰写"), in the reader's language, never an internal constant.
- **The one number**: words drafted, files committed, checks run, findings
  raised, seconds waited. One, chosen for that shape.
- **Detail**: opens in place. The draft's text, the file list, the per-check
  results, the findings. Never a modal, never a page change.

### Rounds

A revision round is a group, not a new region. The current round's rows are
open; a finished round collapses to its Outcome row with a count, and expands
in place. The round number lives on that row, not in a separate header.

### The status line

While anything runs, one line sits at the foot of the stream:

    [orb] 正在撰写 · 第 1/3 轮 · 38 秒 · ≈$0.04            [停止]

It is the only persistent chrome. When nothing runs it is not there.

### Failure is not a decision

A machine failure — an empty completion, an unparseable reply, a provider
timeout, a rate limit, a commit with nothing in scope — is a **Note row with an
inline retry**, not an Outcome. It says what failed, in plain words, and offers
the one action that would fix it.

Only a genuine judgment call becomes an Outcome that asks for the person: the
auditor raised a concern, the rounds ran out, an earlier decision is unsettled.
The distinction is the point of the product: the audit's opinion is worth
interrupting someone for; the plumbing's failure is not.

### Decisions happen in the stream

When a round truly needs a person, its Outcome row expands in place: what
happened, why, what the choices are, in three sentences and two buttons. The
cross-task banner keeps counting pending decisions for tasks you are not
looking at. Nothing covers the screen; the composer stays live.

## Rules

1. No modal for anything the loop can retry.
2. No animation without words beside it.
3. No count badge of zero, and no section whose only content is "see above".
4. No hash, cycle id, internal status constant or `provider:model` string outside
   an opened detail.
5. One number per row.
6. A new event kind declares its shape, or it is not rendered.
7. Every string is EN and ZH at the same commit.
8. The composer is never taken away.

## What does not change

The audit itself. Two vendors, deterministic checks that cannot be overridden,
the commit-and-receipt trail, per-call approval, the auditor seeing only
committed bytes. This document is about how the work is shown, and it may not
soften a single thing about how the work is judged.
