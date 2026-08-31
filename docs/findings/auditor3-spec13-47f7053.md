# Codex audit — SPEC-13 at `47f7053`

Auditor: auditor3 (Codex). The branch is Claude-authored; this is the requested
cross-vendor audit. No feature code was written.

## Verdict

`MERGE AFTER FIXES` — S0: 0, S1: 0, S2: 1, S3: 1.

The production behavior passes every dispatched property. The merge hold is a
test-evidence overclaim: the committed module counts G8 as mutation-proven even
though its specified mutation reddens G2, not G8. The fix is confined to the
guard/evidence claim; the accessible-name implementation itself is correct.

## Target and suite identity

- `ux/live-regions` resolves to
  `47f7053917d1484fd0294a227f74b652b0fc60f1`, exactly the dispatched SHA.
- Detached checkout: `/tmp/crossaudit-audit3-spec13-47f7053`; clean before and
  after the audit, with HEAD reasserted at the full SHA.
- Shared interpreter:
  `/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python`.
- Before collection, imported `crossaudit` was asserted as
  `/private/tmp/crossaudit-audit3-spec13-47f7053/src/crossaudit`.
- Full suite: 1,825 collected, 1,823 passed, 2 skipped, 0 failed.
- Targeted committed suite: `tests/test_provider_control_names.py`, 6 passed.

## Requested properties, executed

### G2 is arithmetic over computed accessible names

The source-mode page was served from the detached target with both imported
package identity and the served `page.py` digest asserted before Chromium ran.
Chromium's accessibility tree reported:

- controls in the DOM: 73;
- interactive controls in the accessibility tree: 73;
- distinct computed accessible names: 73;
- repeated names: none;
- empty names: 0.

I changed `frKeyLabel()` to return only the action, producing repeated names
such as `Validate`. G2 alone reddened. It counts distinct names, not elements:
`g2_counts=distinct-names`.

The committed pytest additionally checks the source-side composition over six
catalogue labels and six actions: 36 emitted strings must have cardinality 36.
That test states its seam honestly; it is not the browser proof.

### G3 catches a missing referenced ID

I changed the input's `aria-labelledby` provider reference from the emitted
`fr-name-<vendor>` to nonexistent `fr-nope-<vendor>`. Chromium then computed
the affected input as nameless. G3 reddened by its own name; G1 and G2 also
reddened as expected. `g3_reddens=yes`.

The committed source-side test renders an actual provider row and resolves
every IDREF against the IDs that row emits. It does not merely assert that the
attribute exists.

### The unavailable reason reaches the accessibility tree

On the Chinese ROLES stage with no valid pair, the final control had no native
`disabled` attribute, carried `aria-disabled="true"`, remained focusable, and
declined the click without advancing the step.

I separately queried Chromium's accessibility node for the button rather than
reading the referenced DOM text. It reported:

```text
role=button
name=开始使用 CrossAudit
description=请在上一步至少连接两家不同的供应商，以组成独立的生成者 / 审计者搭配。
disabled=true
focusable=true
```

Thus the reason is present as the computed accessibility description on the
focusable unavailable control: `reason_reachable=yes`.

Reverting `frSetContinue` to native `disabled` reddened G4 by its own name.

### Composed translations use catalogue patterns

The action names, provider links, validation progress, and validation outcomes
are translated through `ZH_PATTERNS`; provider labels remain identifiers. The
specific action pattern precedes the generic `Remove (.+)` pattern, preventing
the generic rule from leaving `API key` in otherwise Chinese copy.

The Chinese accessibility-tree drive checked 71 interactive names with zero
undeclared Latin-prose offenders. The existing visible token `key` is a named
copy exemption for the two provider links, not an accidental fallback.
Replacing the composed action pattern with a never-matching fixed shape
reddened G6 by its own name: `patterns=catalogue`.

## Seam

The committed pytest file stops at source evaluation and rendered IDREF
resolution; by itself it does not compute accessible names. The browser drive
does: G1/G2/G3/G7/G8 use Chromium role/name resolution or
`Accessibility.queryAXTree`. I also forced DOM text and accessibility output to
diverge by adding `aria-hidden="true"` to a status badge; its text remained in
the DOM and G7 alone reddened.

Therefore this audit reaches the Chromium accessibility tree, not merely the
DOM: `seam=a11y-tree`. It does not establish actual VoiceOver speech, a frozen
DMG path, or an end-to-end runtime event through assistive-technology output.
The readiness-list continuous-text-node finding from D87 remains open and is
not closed or changed by this provider-control slice.

## Findings

### S2-1 — the committed module claims a mutation proof G8 does not have

`tests/test_provider_control_names.py:11-14` says G1 through G8 are browser
guards and that every one was observed to fail against its mutation. The
recorded G8 mutation removes group labelling and per-control names. On this DOM,
the consecutive tab stops still have different names, so G8 stays green; G2
reddens because names repeat across providers.

That is useful evidence for G2, but it is not G8 reddening by its own name. By
the standing guard rule, G8 has not been demonstrated as a guard. The external
findings report says this correctly; the committed module and the first commit
message still make the stronger, false claim.

Fix one of two ways before merge:

1. construct a mutation that actually violates G8's consecutive-name property
   and observe G8 red by name; or
2. stop counting G8 as mutation-proven and state that G2 is the load-bearing,
   strictly stronger guard on this DOM.

This is S2 because §1.5 makes a test/docstring overclaim a product-development
invariant, even though the redundant G2 guard already protects the user-facing
property.

### S3-1 — the supplied mutation runner and fixture server now name different trees

The shared mutation runner currently edits:

`/Users/ericdong/Documents/Crossaudit/crossaudit_a11y/src/crossaudit/console/page.py`

while the fixture server imports:

`.../scratchpad/s13rb/src/crossaudit`.

Both trees are clean, byte-identical, and at `47f7053`, so baseline evidence is
plausibly correct. But after the server was repointed, a mutation applied to the
first path cannot reach the page imported from the second. Neither script
asserts the runtime package identity plus served page digest as one condition.

The historical mutation evidence predates that repoint, so I am not calling it
fabricated. I did not rely on it: an independent harness mutated the detached
target, made the fixture import that same target, and asserted the served
`page.py` SHA-256 before every browser drive. G2, G3, G4, G6, and the DOM-vs-AX
G7 mutation all reddened by their own names at `47f7053`.

This is non-gating instrument hardening after the independent rerun, but the
shared harness should take one target path and assert both import identity and
served source digest before future evidence is accepted.

## Cleared suspicions

- Provider labels are derived from the served catalogue rather than supplied
  by the browser driver. Multiword and slug-different labels are included.
- Inputs derive their names from the visible provider-name node plus a hidden,
  translated `API key` node. Buttons and links include the provider in their
  computed names; visible link text remains contained in the accessible name.
- The provider row is a named group, but per-control names do not rely on group
  announcement behavior.
- `aria-disabled` is backed by an action refusal in the click handler; this is
  not styling-only disabled state.
- English and Chinese browser drives both passed with no page errors. The
  duplicate inherited `reading owner messages` catalogue pattern is inert and
  outside this slice; it does not alter first-match output.

## Independence disclosure

Vendor independence is strong for the code and mutation review: Codex audited
Claude-authored work. My weakest boundary is the last consumer: Chromium's AX
tree is real computed accessibility state, but I did not drive VoiceOver or the
frozen application, so I do not claim spoken-output parity beyond that seam.
