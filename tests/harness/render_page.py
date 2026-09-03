"""Render the conversation through the WHOLE shipped page, under node.

`render_decision.eval_page` slices named functions out of `page.py` and stubs
whatever they call. That is fast, and it is why a whole class of defect walked
past twenty-seven green tests: a slice cannot see a collapsed `<details>`, a
second surface rendered further down `renderConversation`, the delegated click
handler, or the real wire projection. An independent review loaded the script
whole, called `renderConversation` and found the owner's original complaints
still on the screen.

So this harness loads the entire `<script>` — every line the browser gets —
over a dumb DOM stub, calls the real `renderConversation(d)`, and hands back
what `#conversation` actually holds. Nothing is stubbed: `turn`, `reviewCard`,
`statusLine`, `admissionCard`, the live-draft consumer and the orbs are all the
shipped ones.

Two projections come back with it, and the difference between them is the
point:

* ``html`` — everything rendered.
* ``first_paint`` — what is on the SCREEN before anyone opens anything. A
  ``<details>`` without ``open`` contributes its ``<summary>`` and nothing
  else. An action that only appears in ``html`` is an action nobody is offered.

The ZH pane runs the rendered text through the page's own ``zhValue`` the way
the locale MutationObserver does, so a Chinese pane here is what a Chinese
reader gets — including any English that never reached the catalogue.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile

HARNESS = pathlib.Path(__file__).parent


def page_script(worktree: pathlib.Path) -> str:
    """The console's own `<script>`, verbatim."""
    src = (worktree / "src/crossaudit/console/page.py").read_text(encoding="utf-8")
    return src.split("<script>")[1].split("</script>")[0]


def _program(worktree: pathlib.Path, body: str) -> str:
    return "\n".join([
        (HARNESS / "page_dom.js").read_text(encoding="utf-8"),
        page_script(worktree),
        (HARNESS / "page_drive.js").read_text(encoding="utf-8"),
        body,
    ])


def run(worktree: pathlib.Path, body: str) -> str:
    """Run `body` with the whole shipped page loaded. Returns stdout."""
    handle, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(_program(worktree, body))
        out = subprocess.run([shutil.which("node") or "node", path],
                             text=True, capture_output=True,
                             encoding="utf-8", errors="replace")
        assert out.returncode == 0, out.stderr
        return out.stdout
    finally:
        os.unlink(path)


def render(worktree: pathlib.Path, states: dict, *,
           locales: tuple[str, ...] = ("en", "zh"), opts: dict | None = None) -> dict:
    """{name: {locale: {"html", "first_paint", "text"}}} for each state.

    `opts` is per-name and may carry `chat`, `liveDraft`, `liveThinking`,
    `optimisticSend` — the client-side state `renderConversation` reads.
    """
    body = """
const OUT={};
for(const [name,d] of Object.entries(STATES)){
  OUT[name]={};
  for(const locale of LOCALES){
    const html=__render(d,locale,(OPTS[name]||{}));
    OUT[name][locale]={html:html,first_paint:__firstPaint(html),text:__textOf(html)};
  }
}
console.log(JSON.stringify(OUT));
"""
    head = (f"const STATES={json.dumps(states, ensure_ascii=False)};"
            f"const LOCALES={json.dumps(list(locales))};"
            f"const OPTS={json.dumps(opts or {}, ensure_ascii=False)};")
    return json.loads(run(worktree, head + body))


def globals_of(worktree: pathlib.Path, names: list[str]) -> dict:
    """The named page globals, read out of the WHOLE loaded script."""
    return json.loads(run(
        worktree, f"console.log(JSON.stringify(__globals({json.dumps(names)})));"))


def render_and_click(worktree: pathlib.Path, states: dict, *,
                     locale: str = "en", opts: dict | None = None) -> dict:
    """Render each state, then drive EVERY action it offers through the page's
    own delegated click handler, reporting what became modal.

    This is what makes design rules 1 and 8 mechanical: a substring blacklist
    over a source slice cannot see that a button leads, three calls later, to
    `openResolution` -> `aria-modal` + `inert` on the shell that holds the
    composer. Driving the shipped handler can.
    """
    body = """
const OUT={};
for(const [name,d] of Object.entries(STATES)){
  const html=__render(d,LOCALE,(OPTS[name]||{}));
  const before=__shellState();
  const actions=__actionsIn(html);
  const after=[];
  for(const attrs of actions){
    __render(d,LOCALE,(OPTS[name]||{}));       // a fresh paint per click
    __clickAction(attrs);
    after.push({attrs:attrs,shell:__shellState()});
  }
  OUT[name]={html:html,first_paint:__firstPaint(html),before:before,clicks:after};
}
console.log(JSON.stringify(OUT));
"""
    head = (f"const STATES={json.dumps(states, ensure_ascii=False)};"
            f"const LOCALE={json.dumps(locale)};"
            f"const OPTS={json.dumps(opts or {}, ensure_ascii=False)};")
    return json.loads(run(worktree, head + body))
