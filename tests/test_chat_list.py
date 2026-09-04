"""The chat list: what each row says, and where it says it.

Three defects shipped in 4.17.0's sidebar, and each of them is a property of
the rendered list rather than of any one function:

* the legacy thread was the only row with no time at all, because the streams
  it would have been dated from are windowed and its evidence is the oldest in
  the project;
* a row with no status dot started 14 px to the left of a row with one, so the
  column of titles was not a column;
* a long relative time ("12 小时前") ate the title down to about six
  characters, which is not enough to tell two chats apart.

So the fixtures here are not written: `tests/harness/real_state.chat_list`
builds a project by driving the product's own recorders and every row is read
back through `console/server.snapshot`, and the alignment claim is measured in
a real browser off the rendered geometry — a claim about pixels that is
asserted against markup is a claim about nothing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from crossaudit.console import chats, overview

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))

import real_state  # noqa: E402  (rows built by the product, not by a fixture)
import render_page  # noqa: E402  (the whole shipped page, under node)

WORKTREE = Path(overview.__file__).parents[3]
needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

DAY = 86400


def _node_env() -> dict:
    env = dict(os.environ)
    if os.environ.get("CROSSAUDIT_NODE_PATH"):
        env["NODE_PATH"] = os.environ["CROSSAUDIT_NODE_PATH"]
    return env


def _playwright() -> str:
    """The resolved `playwright` entry point, or "" when node cannot find it.

    Resolved through `require`, not imported by name, so the measuring script
    can be a temporary file anywhere on disk and still load a package that
    lives wherever this machine keeps it (CROSSAUDIT_NODE_PATH).
    """
    if shutil.which("node") is None:
        return ""
    probe = subprocess.run(
        ["node", "-e", "console.log(require.resolve('playwright'))"],
        capture_output=True, text=True, env=_node_env())
    return probe.stdout.strip() if probe.returncode == 0 else ""


PLAYWRIGHT = _playwright()
needs_browser = pytest.mark.skipif(
    not PLAYWRIGHT,
    reason="a real browser is needed to measure rendered geometry: "
           "`npm i playwright` and, if it is not on the default resolution "
           "path, set CROSSAUDIT_NODE_PATH to its node_modules")


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """One project holding every chat-row shape, built by the product."""
    cfg, ids = real_state.chat_list(tmp_path_factory.mktemp("chatlist"))
    return cfg, ids


# ------------------------------------------------------- (1) the legacy date
def test_the_legacy_thread_is_dated_by_the_evidence_that_carries_no_chat_id(
        project):
    cfg, ids = project
    rows = real_state.chat_rows(cfg)["items"]
    legacy = next(r for r in rows if r["id"] == chats.LEGACY_CHAT_ID)
    now = int(time.time())
    # Its evidence — an untrailered commit and the report about it — is 40 days
    # old, and that is exactly what the row says.
    assert legacy["updated"] > 0, "a row with no time is a hole in the column"
    age_days = round((now - legacy["updated"]) / DAY)
    assert age_days == 40, age_days
    assert legacy["updated"] < now - DAY, "and it is not dated 'just now'"


def test_the_legacy_date_survives_the_stream_window_moving_past_it(tmp_path):
    """The state the owner actually had: newer threads fill the window.

    Both streams keep only their most recent rows, and the legacy thread's
    evidence is the oldest in the project, so on any project with recent work
    its rows are simply not in the window any more. Dating it from the window
    alone left it blank; dating it from the evidence that carries no chat id
    does not depend on the window at all.
    """
    cfg, _ids = real_state.chat_list(tmp_path, noise=45)
    windowed = {r.get("chat_id") for r in
                real_state.snapshot(cfg)["generator_stream"]}
    assert chats.LEGACY_CHAT_ID not in windowed, "the premise: it fell off"
    legacy = next(r for r in real_state.chat_rows(cfg)["items"]
                  if r["id"] == chats.LEGACY_CHAT_ID)
    assert round((int(time.time()) - legacy["updated"]) / DAY) == 40


def test_a_rematerialised_thread_does_not_refresh_to_now(project):
    """The property the earlier fix was protecting, kept.

    A recovered thread is re-materialised on every snapshot. If it were dated
    by the snapshot, every thread in the list would read "just now" forever.
    """
    cfg, _ids = project
    first = real_state.chat_rows(cfg)["items"]
    time.sleep(1.1)
    second = real_state.chat_rows(cfg)["items"]
    dates = {r["id"]: r["updated"] for r in first}
    assert {r["id"]: r["updated"] for r in second} == dates
    assert all(when < int(time.time()) for when in dates.values())


def test_an_undated_thread_is_still_possible_and_says_so(tmp_path):
    """Every other recovered thread, and what it shows when nothing dates it.

    A thread known only from a Git trailer whose evidence carries no readable
    timestamp still ends at 0 here — the data layer must not invent a date it
    does not have. The row does not go blank for it: `agoShort` renders 0 as
    "—", asserted below, so the column keeps its shape and the row says "no
    date" rather than lying with "just now".
    """
    from crossaudit.config import load

    root = tmp_path / "p"
    root.mkdir()
    (root / "AUDIT_RULES.md").write_text(real_state.RULES)
    (root / "crossaudit.yml").write_text(real_state.CONFIG)
    cfg = load(root / "crossaudit.yml")
    chat = "a" * 16
    rows = chats.snapshot(cfg, [chat], last_seen={})["items"]
    assert [r["updated"] for r in rows if r["id"] == chat] == [0]


# --------------------------------------------------- (2) the reserved dot
@needs_node
def test_every_chat_row_emits_a_status_dot_whether_or_not_it_has_a_status():
    """The markup half of the alignment claim; the geometry half is below."""
    out = json.loads(render_page.run(WORKTREE, r"""
const rows=[{id:'a'.repeat(16),title:'With a dot',updated:1,status:'blocked',
             pinned:false,archived:false,cycles:1},
            {id:'b'.repeat(16),title:'No dot',updated:1,status:'ready',
             pinned:false,archived:false,cycles:0},
            {id:'history',title:'Project history',updated:1,status:'',
             pinned:false,archived:false,cycles:0}];
const archived=[{id:'c'.repeat(16),title:'Archived',updated:1,status:'ready',
                 pinned:false,archived:true,cycles:0}];
lastState={chats:{items:rows,archived:archived,project_pinned:false}};
archivedExpanded=true;
renderTasks(lastState);
const html=document.getElementById('task-list').innerHTML;
console.log(JSON.stringify({
  rows:(html.match(/class="task[ "]/g)||[]).length,
  dots:(html.match(/class="state-dot/g)||[]).length,
  coloured:(html.match(/class="state-dot blocked"/g)||[]).length}));
"""))
    assert out["rows"] == out["dots"] == 4, out
    assert out["coloured"] == 1, "a dot that says something still says it"


@needs_browser
def test_every_title_starts_on_the_same_x_in_a_real_browser(project):
    """Measured, not grepped: the same page, the same CSS, real layout.

    Before this fix the rendered lefts were {29, 43}: `.task-copy` is a flex
    row with an 8px gap, so a row that dropped its 6px dot pulled its title
    14px left of a row that kept one.
    """
    cfg, _ids = project
    rows = _measure(cfg)
    # every shape at once: legacy, dotted, dotless, long CJK, long Latin,
    # the owner's two examples, and the archived row.
    assert len(rows["en"]) == len(rows["zh"]) == 8, rows
    lefts = sorted({row["titleLeft"] for row in rows["en"] + rows["zh"]})
    assert len(lefts) == 1, f"titles start on {len(lefts)} different x: {lefts}"
    assert all(row["dotWidth"] == 6 for row in rows["en"]), rows["en"]


@needs_browser
def test_a_long_title_keeps_a_readable_width_at_the_sidebars_own_size(project):
    """The floor, in the browser that decides it.

    `.task-title` keeps a min-width of 6.5em and the age beside it is short, so
    every title — CJK or Latin, dotted or not, in either language — is at least
    twice the width of the age it shares the row with. Chinese is the tight
    case: "12 小时" is three glyphs wider than "12h".
    """
    cfg, _ids = project
    rows = _measure(cfg)
    for locale in ("en", "zh"):
        for row in rows[locale]:
            assert row["titleWidth"] >= 84, (locale, row)      # the 6.5em floor
            assert row["titleWidth"] > row["metaWidth"] * 2, (locale, row)


@needs_browser
def test_the_owners_two_examples_can_be_told_apart_in_the_rendered_list(project):
    """The bar this list is judged against, read off the screen.

    Not "the box is N pixels wide" but "what does a person see": the longest
    prefix that actually fits, measured in the title's own font. Before the
    fix "生成一个钙钛矿的综述" rendered five glyphs of itself.
    """
    cfg, _ids = project
    for locale in ("en", "zh"):
        rows = {row["title"]: row for row in _measure(cfg)[locale]}
        shown = [rows[title]["visible"] for title in real_state.OWNER_CJK]
        assert all(len(text) >= 6 for text in shown), shown
        assert shown[0] != shown[1], shown


def _measure(cfg) -> dict:
    """The sidebar's rendered geometry, from a browser driving the real server."""
    from crossaudit.console.server import serve

    url, httpd = serve(cfg, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    handle, path = tempfile.mkstemp(suffix=".mjs")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(_MEASURE_JS)
        out = subprocess.run(["node", path, url, PLAYWRIGHT], text=True,
                             capture_output=True, env=_node_env())
        assert out.returncode == 0, out.stderr[-4000:]
        return json.loads(out.stdout)
    finally:
        os.unlink(path)
        httpd.shutdown()


#: Loads the shipped console in Chromium, opens the archived section so every
#: row shape is on the screen at once, and reads each row's geometry in both
#: languages. Headless only changes who watches; the layout is the same engine.
_MEASURE_JS = r"""
const loaded = await import(process.argv[3]);
const chromium = (loaded.chromium || loaded.default.chromium);
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(process.argv[2], { waitUntil: 'networkidle' });
await page.waitForSelector('#task-list .task');
const toggle = await page.$('[data-archived-toggle]');
if (toggle) { await toggle.click(); await page.waitForTimeout(300); }
const probe = () => page.evaluate(() => {
  // What a person can actually READ of a title: the longest prefix that fits
  // inside the box, measured in the element's own font, ellipsis allowed for.
  const visible = el => {
    const cs = getComputedStyle(el);
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const text = el.textContent;
    const room = el.clientWidth - (el.scrollWidth > el.clientWidth + 0.5
      ? ctx.measureText('…').width : 0);
    let n = 0;
    while (n < text.length && ctx.measureText(text.slice(0, n + 1)).width <= room) n++;
    return text.slice(0, n);
  };
  return [...document.querySelectorAll('#task-list .task')].map(row => {
    const title = row.querySelector('.task-title');
    const meta = row.querySelector('.task-meta');
    const dot = row.querySelector('.state-dot');
    const box = title.getBoundingClientRect();
    return { title: title.textContent, meta: meta ? meta.textContent : null,
             hover: row.getAttribute('title'), visible: visible(title),
             dotWidth: dot ? +dot.getBoundingClientRect().width.toFixed(2) : null,
             titleLeft: +box.left.toFixed(2), titleWidth: +box.width.toFixed(2),
             metaWidth: meta ? +meta.getBoundingClientRect().width.toFixed(2) : 0 };
  });
});
const out = { en: await probe() };
for (const el of await page.$$('#locale-toggle, #hub-locale, #decision-locale')) {
  if (await el.isVisible()) { await el.click(); break; }
}
await page.waitForTimeout(700);
out.zh = await probe();
console.log(JSON.stringify(out));
await browser.close();
"""


# ------------------------------------------------------- (3) the age itself
@needs_node
def test_a_row_age_is_short_in_the_row_and_whole_on_hover():
    """`12h` in 24 px of row, `12 h ago` on the title attribute, both in ZH."""
    out = json.loads(render_page.run(WORKTREE, r"""
const now=Date.now()/1000;
const cases=[0,30,5*60,12*3600,3*86400,14*86400];
console.log(JSON.stringify(cases.map(age=>{
  const t=age?now-age:0;
  return {short:agoShort(t),full:agoFull(t),
          zhShort:zhValue(agoShort(t)),
          zhHover:zhValue('生成一个钙钛矿的综述 · '+agoFull(t))};})));
"""))
    assert [row["short"] for row in out] == ["—", "now", "5m", "12h", "3d", "14d"]
    assert [row["full"] for row in out] == [
        "Time unknown", "just now", "5 min ago", "12 h ago", "3 days ago",
        "14 days ago"]
    assert [row["zhShort"] for row in out] == [
        "—", "刚刚", "5 分钟", "12 小时", "3 天", "14 天"]
    assert out[3]["zhHover"] == "生成一个钙钛矿的综述 · 12 小时前"
    assert out[0]["zhHover"] == "生成一个钙钛矿的综述 · 时间未知"


@needs_node
def test_the_row_carries_the_whole_time_and_title_for_hover():
    out = render_page.run(WORKTREE, r"""
lastState={chats:{items:[{id:'a'.repeat(16),title:'生成一个钙钛矿的综述',
  updated:Math.floor(Date.now()/1000)-12*3600,status:'ready',pinned:false,
  archived:false,cycles:0}],archived:[],project_pinned:false}};
renderTasks(lastState);
console.log(document.getElementById('task-list').innerHTML);
""")
    assert 'title="生成一个钙钛矿的综述 · 12 h ago"' in out, out
    assert ">12h<" in out, out
