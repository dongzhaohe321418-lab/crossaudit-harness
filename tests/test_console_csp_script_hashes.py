"""The console page's CSP allows exactly its own scripts, by hash (D170, S3).

Before D170 the page was served with `script-src 'unsafe-inline'`, while the
server's docstring called it "a strict inline-only CSP, so nothing on the page
can fetch or exfiltrate". Now the two inline handlers are delegated listeners
and the header lists the SHA-256 of each `<script>` block.

The first test serves the page through the real console server, parses the
body with the standard library's HTML parser (not the regex the product uses
to compute the hashes), hashes every script element's text and compares the
set with the header. D10 mutations run by hand: putting 'unsafe-inline'
back into PAGE_CSP -> the served-page test red; disabling the delegated
Stop branch -> the delegation test red.
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import shutil
import subprocess
import threading
import urllib.request
from html.parser import HTMLParser

import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "harness"))
import render_page  # noqa: E402  (the whole-page harness)
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.bodies: list[str] = []
        self._open = None
        self.handlers: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        for name, _value in attrs:
            if name.lower().startswith("on"):
                self.handlers.append((tag, name))
        if tag == "script":
            self._open = []

    def handle_data(self, data):
        if self._open is not None:
            self._open.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._open is not None:
            self.bodies.append("".join(self._open))
            self._open = None


@pytest.fixture
def console(tmp_path):
    from crossaudit.config import load
    from crossaudit.console import serve

    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
        "checks: [parseable]\n")
    url, httpd = serve(load(root / "crossaudit.yml"), port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def _sha(body: str) -> str:
    digest = hashlib.sha256(body.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def _directive(policy: str, name: str) -> list[str]:
    for part in policy.split(";"):
        words = part.split()
        if words and words[0] == name:
            return words[1:]
    raise AssertionError(f"{name} missing from {policy!r}")


def test_served_page_csp_lists_exactly_the_hashes_of_its_scripts(console):
    with urllib.request.urlopen(console, timeout=5) as response:
        body = response.read().decode("utf-8")
        policy = response.headers["content-security-policy"]
    parser = _Scripts()
    parser.feed(body)
    assert len(parser.bodies) == 2, "the engine and the console script"
    script_src = _directive(policy, "script-src")
    assert sorted(script_src) == sorted(_sha(b) for b in parser.bodies)
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in policy and "'unsafe-hashes'" not in policy
    # Everything else is unchanged.
    assert _directive(policy, "default-src") == ["'none'"]
    assert _directive(policy, "style-src") == ["'unsafe-inline'"]
    assert _directive(policy, "connect-src") == ["'self'"]
    assert _directive(policy, "img-src") == ["'self'", "data:"]
    assert _directive(policy, "frame-src") == ["'self'"]


def test_the_static_page_has_no_inline_event_handler_attribute():
    from crossaudit.console.page import PAGE

    parser = _Scripts()
    parser.feed(PAGE)
    assert parser.handlers == []


@node
def test_rendered_approval_card_carries_no_inline_handler():
    """Rendered through the WHOLE shipped script. The status line's Stop
    button and the live-draft fold are checked the same way, over rendered
    markup, in test_thinking_orb and test_say_less."""
    script = "\n".join([
        "const d={pending_approval:{tool:'write_file',level:3,"
        "reversibility:'reversible',scopes:['once','run','project','deny']}};",
        "console.log(JSON.stringify({approval:approvalCard(d)}));",
    ])
    html = json.loads(render_page.run(ROOT, script).strip().splitlines()[-1])["approval"]
    parser = _Scripts()
    parser.feed(html)
    assert parser.handlers == []
    for scope in ("once", "run", "project", "deny"):
        assert f'data-decision="{scope}"' in html
    assert 'class="approval-card"' in html


@node
def test_delegated_listeners_reach_the_same_functions_the_inline_handlers_called():
    """The page script is loaded whole with document.addEventListener
    recorded; synthetic events are dispatched to every recorded listener.
    What is under test is the dispatch code and its selectors, matched as
    strings by the stub -- a stub DOM cannot evaluate CSS."""
    prelude = ("const __listeners=[];"
               "document.addEventListener=(t,f,c)=>__listeners.push({t:t,f:f,c:!!c});")
    body = """
const calls=[];
requestStop=()=>calls.push('stop');
resolveApproval=(d)=>calls.push('decide:'+d);
rememberDraftOpen=(el)=>calls.push('fold:'+el.id);
openFilePreview=()=>calls.push('preview');
setUsageMode=()=>calls.push('usage');
function fire(type,target){for(const l of __listeners)if(l.t===type)
  l.f({type:type,target:target,preventDefault(){},stopPropagation(){}});}
function el(sel,extra){return Object.assign({closest(s){return s===sel?this:null;},
  matches(s){return s===sel;},getAttribute(k){return (extra||{})[k]||null;}},extra||{});}
const out={};
calls.length=0;fire('click',el('.stream-stop'));out.stop=calls.slice();
calls.length=0;fire('click',el('.approval-card button[data-decision]',{'data-decision':'run'}));out.decide=calls.slice();
calls.length=0;fire('click',el('.something-else'));out.other_click=calls.slice();
calls.length=0;fire('toggle',el('details.draft-fold',{id:'fold-1'}));out.fold=calls.slice();
calls.length=0;fire('toggle',el('details.other',{id:'x'}));out.other_toggle=calls.slice();
out.toggle_capture=__listeners.filter(l=>l.t==='toggle').map(l=>l.c);
console.log(JSON.stringify(out));
"""
    program = "\n".join([
        (render_page.HARNESS / "page_dom.js").read_text(encoding="utf-8"),
        prelude,
        render_page.page_script(ROOT),
        (render_page.HARNESS / "page_drive.js").read_text(encoding="utf-8"),
        body])
    path = pathlib.Path(render_page.tempfile.mkstemp(suffix=".js")[1])
    try:
        path.write_text(program, encoding="utf-8")
        done = subprocess.run([shutil.which("node"), str(path)], text=True,
                              capture_output=True, encoding="utf-8")
    finally:
        path.unlink()
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["stop"] == ["stop"]
    assert out["decide"] == ["decide:run"]
    assert out["other_click"] == []
    assert out["fold"] == ["fold:fold-1"]
    assert out["other_toggle"] == []
    assert out["toggle_capture"] and all(out["toggle_capture"]), "toggle does not bubble; capture is required"
