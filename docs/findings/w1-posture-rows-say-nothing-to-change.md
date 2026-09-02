# A posture row states where you stand; it does not offer a remedy

Branch `fix/diagnostic-rows-next-action` @ `dbbb307`, off `v5-redesign@3af0317`.

## What was asked, and what turned out to be true

Six diagnostic rows -- `machine:schema`, `machine:units`, `machine:convergence`,
`machine:provenance`, `admission tier` and `  toward enforced` -- were reported
as telling a person something is wrong and not what to do about it.

Two of those six needed anything. The other four were an artefact of how they
were counted.

`ok` in doctor output is tri-valued and has been since D6:

    True   tested and held      [PASS]
    False  tested and did not   [FAIL]
    None   not a test at all    [INFO]

The guard that produced the list of six filters with `not c["ok"]`, and
`not None` is True. Every `[INFO]` row was swept in. The four `machine:*` rows
are the configured contract DESCRIPTIONS -- the same rows D6 converted from a
false `[PASS]` to `[INFO]` because they report nothing about the project in
front of them. There is nothing to do about them and there never was.

Correction and its measurement: `_handoff/honesty-guard-info-overmatch/`.

## The first attempt was wrong in the other direction

I gave all six rows a next action behind `->` (commit `c19e7b5`). That is a
defect of its own and an existing guard caught it:
`test_an_info_line_never_offers_a_fix_arrow` -- "A posture has nothing to fix;
offering a remedy implies it is broken."

`->` means YOU HAVE SOMETHING TO DO. Putting one beside a row that describes a
state of the world manufactures a task where nothing is wrong, which is the
failure mode this whole line of work is against: presenting fine as act now.

Two guards, two edges, one narrow line:

  * a row reporting a FAULT must carry a next action
  * a row reporting a POSTURE must carry no arrow at all

The discriminator is `kind`, not `ok`.

## What shipped

`admission tier` gains a second sentence OF ITS OWN TEXT -- not an arrow --
that says out loud there is nothing to change:

      How much this project's history proves
          local — self-review; the history is yours to rewrite
          nothing to change unless you want this history to prove more than
          self-review; `crossaudit pair` separates the two agents

One sentence per tier, keyed `doctor.tier.standing.<tier>`, English and Chinese.
The key is built from the tier constant, so a guard walks `adm.TIER_MEANING` and
asserts a non-empty entry in both languages -- that guard caught a real defect
before this shipped: I had keyed the fourth tier `notification` when the
constant is `verified-notification`, which would have rendered
`[missing:doctor.tier.standing.verified-notification]` at anyone on that tier.

The sentence is human copy, so it renders in the human view only. `--all` and
`--json` remain the verbatim machine surface (F3): measured at 0 CJK characters
under `--lang zh`, and the `standing` field carries a KEY, never text.

`  toward enforced` gets no sentence of its own. Each shortfall row is one item
in a list the tier row has already spoken for, and repeating "these are
optional" on every line is noise. The tier row prints above them.

The four `machine:*` rows are unchanged. A guard now holds them that way.

## Mutations (each asserts its anchor and fails loudly if the anchor moved)

    M1  a posture row carries a `fix` again      -> 2 red, incl. the posture rail
    M2  the standing sentence stops rendering    -> 2 red
    M3  one tier's English sentence deleted      -> 1 red (the [missing:] class)
    M4  the Chinese sentence deleted             -> 2 red
    M5  the translated sentence stored in the
        check dict instead of its key (F3)       -> 1 red
    M6  a real [FAIL] row's `fix` emptied        -> 1 red (rail one)

## Suite

In-worktree: 2027 passed, 2 skipped, 265.9s.
Detached at `dbbb307`, HEAD and import origin asserted: 2027 passed, 2 skipped,
269.8s.

## Not done, and visible

In the Chinese human view the tier row's own detail
(`local — self-review; the history is yours to rewrite`) and the shortfall line
render in English. `TIER_MEANING` and the shortfall sentences have no
`detail_copy` and are produced in `admission.py`, which is the server-side
keyed-strings class already queued, not this slice. Measured, not fixed.
