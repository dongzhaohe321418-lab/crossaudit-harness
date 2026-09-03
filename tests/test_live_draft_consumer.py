"""F7 — the page consumes the named generation_chunk frames.

**Read this before adding to it.** The property this file is named after CANNOT
be settled here, and pretending otherwise would repeat the defect. Thirty
focused streaming tests passed while the property was dead, because they stop at
the transport: production-shaped `generation_chunk` events were persisted and
reached Chromium as named SSE frames, and the page registered no named listener.
A test asserting that frames were emitted passes today and passed then.

So the guard drives a browser. It lives in `_ui_findings/f7-live-draft/`
(`serve_draft_fixture.py` + `sweep_draft.mjs`), built on the handed-over
escalation-render-harness seam — a real console via `serve(cfg, port=0)`, a real
run journal, real named frames, no credentials. Its mutation runner is
`mutate7.py`, and all four mutations were observed to redden their own named
result key, including the headline one: delete the `addEventListener` line and
`listener` goes `registered` -> `ABSENT`.

Corrections this guard has needed, recorded because they are the interesting
part — three found by the mutation runner, one by the cross-vendor audit:

1. The sweep's `listener` key first asked `typeof draftChunk === 'function'`,
   which stays TRUE when the subscription is deleted. A source-shaped check
   wearing a browser check's name — and it let the headline mutation survive. It
   now reports whether a DELIVERED frame reached the consumer.
2. The midway-join mutation first deleted only a `return`, and the next line
   overwrote the draft with the same fresh initialisation. A mutant that did not
   mutate, reported as SURVIVED. "The guard did not catch it" was a statement
   about the mutation, not about the guard.
3. The markup check matched the word "delivery" in its own explanatory comment.
4. **The audit's S3, and the worst of them.** The live-growth step never
   asserted growth at all: it reported the body AFTER the append and nothing
   compared it to the body before, so before and after could be identical and
   the step still passed. Worse in Chinese, where it also appended an ENGLISH
   token — proving growth in one locale while reporting it in another — and
   where a run-scoped acknowledgement counter that restarted at 0 could be
   satisfied by the acknowledgement the English run had left on disk, so the
   fixture appended nothing and the step passed anyway.

   Three separate ways for the same step to pass without the property holding.
   Now: a per-run nonce on every acknowledgement; the appended text is the
   locale under test; and growth is asserted BETWEEN TWO DISTINCT OBSERVATIONS
   — `after` must start with `before` and the remainder must be exactly the
   token sent. If before and after can be identical and still pass, it is not a
   growth assertion. That is the rule from the locale-timing class, arriving in
   the guard rather than the product. A fifth mutation pins it: make the draft
   replace instead of accumulate and `grew` goes true -> false, changing no
   other key.

**What THIS file does** is pin the wiring, so the browser guard cannot silently
stop having anything to find: the listener is registered by name, the draft is
placed in the render, and its copy exists in both locales. That is all it
claims.
"""
from __future__ import annotations

from crossaudit.console.page import PAGE


def _script() -> str:
    return PAGE.split("<script>")[1].split("</script>")[0]


def test_the_named_listener_is_registered_on_the_stream():
    """`onmessage` never sees a named frame: a frame carrying an `event:` line
    is dispatched by name and by name only. That is the whole defect."""
    stream = _script()
    stream = stream[stream.index("function startStream()"):]
    stream = stream[:stream.index("\nconst form=")]
    assert "addEventListener('generation_chunk'" in stream
    assert "draftChunk(" in stream


def test_the_draft_is_actually_placed_in_the_conversation():
    """Consuming the frames and rendering nothing would leave the transport
    correct and the person still seeing nothing — which is the finding."""
    assert "+ optimistic + liveDraftTurn(d) + live" in PAGE


def test_the_draft_never_borrows_the_furniture_of_audited_text():
    """It is unaudited text. It may not wear a file card, a download, a
    delivery band, a PASS mark or any audit styling — driven in the browser as
    `borrowed: []`, pinned here so the markup cannot quietly grow one."""
    markup = PAGE[PAGE.index("function liveDraftTurn(d){"):]
    markup = markup[:markup.index("function startStream()")]
    # Comments stripped first: the prose above this function NAMES the things it
    # must not contain, and the first version of this guard matched its own
    # explanation. A check that reads the comment rather than the code is red
    # for a reason unrelated to the property it guards.
    markup = "\n".join(line for line in markup.split("\n")
                       if not line.strip().startswith("//"))
    for forbidden in ("file-card", "data-download", "delivery", "status PASS",
                      "review-card", "finding", "aria-live"):
        assert forbidden not in markup, (
            f"the live draft borrows {forbidden!r}, which belongs to text that "
            f"has been through the auditor")


def test_the_label_is_the_exact_copy_the_contract_names_in_both_locales():
    """D149/S2: the draft is one summarising line, not a wall of text, so the
    label carries the count and is BUILT rather than looked up in the ZH map.
    Mutation: drop `draftCount` from `draftSummaryLine` and the count vanishes
    from both sentences."""
    assert "'Generator is drafting · '+n+(n===1?' word':' words')+' so far · not yet audited'" in PAGE
    assert "'生成者正在撰写 · 已写 '+n+' 字 · 尚未审计'" in PAGE
    # The old whole-text label is gone from the page and from the catalogue.
    assert "Generator live draft · not yet audited" not in PAGE
