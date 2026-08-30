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

Two corrections that runner forced, recorded because they are the interesting
part:

1. The sweep's `listener` key first asked `typeof draftChunk === 'function'`,
   which stays TRUE when the subscription is deleted. A source-shaped check
   wearing a browser check's name — and it let the headline mutation survive. It
   now reports whether a DELIVERED frame reached the consumer.
2. The midway-join mutation first deleted only a `return`, and the next line
   overwrote the draft with the same fresh initialisation. A mutant that did not
   mutate, reported as SURVIVED. "The guard did not catch it" was a statement
   about the mutation, not about the guard.

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
    assert "Generator live draft · not yet audited" in PAGE
    assert ('"Generator live draft · not yet audited":'
            '"生成者实时草稿 · 尚未审计"') in PAGE
