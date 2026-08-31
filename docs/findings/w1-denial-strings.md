# w1 — the third boundary: refusals are the least-translated strings we have

Per D38. Branch `fix/denial-strings-legible` off `v5-redesign@c652828`.

## 1. The one string

`broker/routing.py:75` raises the audit core's fail-closed denial — a corrupt
evidence ledger refuses to produce a receipt. It works on the frozen build:
exit 21, zero receipts, no blank panel, no spinner. **And a Chinese user cannot
read it.**

It carries the verifier's own reason after a colon, so it is a `ZH_PATTERNS`
entry rather than an exact one; an exact entry would never match the sentence a
person actually sees. Driven through the shipped translator:

    before  evidence ledger cannot be shown to the Auditor: entry 0 digest mismatch…
    after   证据账本无法出示给审计方：entry 0 digest mismatch (content tampered)

The verifier's reason is carried through rather than dropped — a mutation
asserts that, because a translation that swallows the detail is a different
kind of illegibility.

## 2. The class, counted

Every message handed to `Denial`, `ConfigDenial`, `IntegrityDenial` or
`ProviderDenial` in `src/`, probed against the shipped catalogue with a
placeholder standing in for interpolated parts:

    denial/refusal messages found        594   across 46 files
      fully static                       355
      interpolated (need a pattern)      239
    distinct sentences                   530
    WITH a catalogue entry                52   (51 before this fix)
    with NONE                            478

**About 10% coverage.** For comparison, the two boundaries already closed sit at
100%: 64 of 64 aria-labels, 25 of 25 server-side literals. The manager's guess
that this is the least-translated category in the product is correct, and the
gap is an order of magnitude, not a margin.

## 3. Is 530 a total or a floor? A FLOOR, and in both directions

**It undercounts** because it only follows the four `Denial` constructors taking
a literal first argument. It does not see: messages assembled into a variable
and then raised; `ValueError`/`RuntimeError`/`OSError` text that reaches a
person through a handler; provider and subprocess text quoted verbatim into a
refusal; or anything raised in a dependency.

**And it overcounts what a person meets**, because not every denial is
user-facing — some are raised and caught internally, and some can only fire in
states a person cannot produce. I have not separated those, so the *reachable*
denominator is smaller than 530 and I do not know by how much.

So: **478 untranslated is a floor on the work and an upper bound on the harm.**
Establishing the reachable subset is the first task of the slice, not a
precondition for reporting the number.

## 4. The pattern across all three boundaries

    server-side literals   25 of 25   translator cannot reach them
    aria-labels             5 of 64   no sighted reviewer reads them
    denials/refusals      478 of 530  nobody walks the failure path in another language

The three share one cause: **a string is translated in proportion to how often
someone who cares about translation walks past it.** Setup is translated because
everyone runs setup. A denial that fires on a corrupt evidence ledger is walked
by nobody.

**I agree with the rule and would put it more strongly.** Refusals are not merely
*as* important as the happy path — they are the strings where illegibility does
the most damage, because a person who cannot read a warning proceeds as though
it were not there. Every honesty guarantee this product makes assumes the
sentence is understood by the person it protects. An untranslated denial does
not degrade that guarantee; it inverts it, because the refusal still *looks*
like the system working.

The one qualification I would add: this is a **console** fix. There is no CLI
catalogue on integration (D16), so the same denial reaching a terminal is still
English. The boundary is closed on one surface of two.

## 5. Guards and mutations

    D1  the denial pattern removed                     RED (2 tests)
    D2  the pattern drops the verifier's reason        RED
    D3  the denial reworded, orphaning its pattern     RED (2 tests)

The third matters as much as the first: a catalogue entry for a sentence nobody
raises is an entry that rots, and the guard fails when the two drift apart.

The count is pinned as a test so it cannot slide silently — it does not assert
the class is translated, which would be false. It asserts the measurement, so
making coverage worse requires changing the number on purpose.


---

## The execution-scoped enumeration, and its predicate

Committed as `tests/harness/enumerate_console_strings.py` plus
`tests/test_console_strings_by_execution.py`, so the number cannot travel
without what it counts.

    unit          DISTINCT values, not occurrences
    strings       11
    paths driven  8, all returning JSON, across 2 fixture states
      /api/health 200 · /api/state 200 · /api/projects 200 · /api/settings 200
      /api/chats/new 200 · /api/projects/open 400 · /api/doctor 400 ·
      /api/settings 400

**Execution found two strings the pattern sweep structurally could not see** —
`Keychain settings are available in the macOS app` and `Application Doctor
repairs are available in the macOS app`, both reachable only through error
routes, both from the 39 my AST method could not reach because they are passed
to a call rather than assigned.

**And execution produced only 11 of the 25.** The other 14 are not dead: they
need states this fixture never had — existing projects, chats with titles,
running jobs, escalations. That is a path-and-state coverage finding, and the
harness says so rather than reporting a zero.

**One refinement to the reporting rule, from the evidence.** Two runs over
overlapping paths returned *different* elevens. `/api/state` on an empty project
and on a populated one are different paths in every sense that matters, so a
completeness claim is as wide as the paths **and the states** behind it. The
harness records both.

**And one thing I need that does not exist**, per the constraint: enumerating
over all paths needs the console test suite as the driver, which needs a
recording hook on the emit seam. I have not built it and I am not going to
without it being scoped.
