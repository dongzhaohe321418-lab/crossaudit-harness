"""Universal file preview (North Star §11): dispatch, security, and caps.

The preview surface renders untrusted, model-generated file content, so these
tests weigh security first: markdown XSS is neutralised, SVG is never served or
described executably, the raw-bytes endpoint stays tokened, Host-guarded, and
strictly scoped to the audited tree, and every new preview path is capped so a
hostile or huge output cannot exhaust memory or inflate the payload.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest

from crossaudit.config import load
from crossaudit.console import serve, transfers
from crossaudit.console.transfers import TransferError, preview_artifact

from .node_eval import run_node


def commit(cfg, relative: str, data: bytes, message: str) -> None:
    """Record one file as generator output so the preview endpoints resolve it."""
    target = cfg.root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    subprocess.run(["git", "add", "--", relative], cwd=cfg.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=cfg.root, check=True)


@pytest.fixture()
def scoped(cfg):
    return replace(cfg, scope_dirs=["experiments"])


def preview(cfg, relative: str, data: bytes, message: str = "produce (round 1)") -> dict:
    commit(cfg, relative, data, message)
    return preview_artifact(cfg, relative)


PNG_1x1 = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
           + (12).to_bytes(4, "big") + (7).to_bytes(4, "big")
           + b"\x08\x06\x00\x00\x00" + b"\x00\x00\x00\x00" + b"IEND")

XSS_MARKDOWN = (
    "# Report\n\n"
    "<script>alert(1)</script>\n\n"
    "<img src=x onerror=alert(2)>\n\n"
    "[click me](javascript:alert(3))\n"
)

MALICIOUS_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" '
    b'onload="alert(1)"><script>alert(2)</script><rect width="40" height="20"/></svg>'
)


# --------------------------------------------------------------- dispatch table
@pytest.mark.parametrize("relative,data,kind", [
    ("experiments/main.py", b"import os\n\n\ndef main():\n    return 1\n", "text"),
    ("experiments/notes.md", b"# Title\n\nBody\n", "markdown"),
    ("experiments/data.csv", b"name,value\nalpha,3\nbeta,4\n", "table"),
    ("experiments/pixel.png", PNG_1x1, "image"),
    ("experiments/blob.bin", b"\x00\x01\x02\xff\xfe", "binary"),
])
def test_dispatch_returns_the_expected_kind(scoped, relative, data, kind):
    result = preview(scoped, relative, data)
    assert result["kind"] == kind
    assert result["bytes"] == len(data)


def test_python_text_carries_a_language_hint_for_light_highlighting(scoped):
    result = preview(scoped, "experiments/app.py", b"x = 1\n")
    assert result["kind"] == "text"
    assert result["language"] == "python"


@pytest.mark.parametrize("format_name,kind", [("pdf", "pdf"), ("docx", "document")])
def test_office_documents_dispatch_and_carry_structure(cfg, format_name, kind):
    from crossaudit.document_export import (SOURCE_SUFFIX, export_instructions,
                                            render_export)

    scoped_cfg = replace(cfg, scope_dirs=["experiments"])
    relative = f"experiments/report{SOURCE_SUFFIX}"
    (cfg.root / relative).write_text(
        "# Executive summary\n\nBody paragraph.\n\n## Method\n\nMore text.\n")
    final = render_export(cfg.root, [relative],
                          "Write" + export_instructions(format_name))[0]
    subprocess.run(["git", "add", "--", final], cwd=cfg.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "produce report (round 1)"],
                   cwd=cfg.root, check=True)
    result = preview_artifact(scoped_cfg, final)
    assert result["kind"] == kind
    # A structure/outline is provided where extractable.
    assert "outline" in result
    if kind == "document":
        assert any("summary" in o["text"].lower() for o in result["outline"])


# --------------------------------------------------------------------- security
def test_markdown_xss_is_confined_to_data_never_pre_rendered(scoped):
    """The server returns the payload only as escaped-by-the-client data (the
    ``text`` field), never as a ``kind:'html'`` or a pre-rendered markup field.
    Rendering, and thus sanitisation, happens in the client's safe renderer."""
    result = preview(scoped, "experiments/evil.md", XSS_MARKDOWN.encode())
    assert result["kind"] == "markdown"
    assert result["text"] == XSS_MARKDOWN          # preserved verbatim as data
    # No server-side field hands the browser live markup to inject.
    assert "html" not in result


def test_page_markup_contains_the_escape_and_scheme_checks():
    """The client contract: markdown is escaped before formatting, dangerous URL
    schemes are dropped, raw file text is never passed through ``innerHTML``, and
    the HTML-file preview runs in a scriptless sandboxed iframe.
    MARKUP ONLY. This asserts strings are present in ``page.py``; it does not
    render anything and cannot fail if the page never reaches a person. Renamed
    under D106: serving an empty document leaves it green, so a name claiming
    "renders"/"announces" was a property nobody tested.
    """
    from crossaudit.console.page import PAGE

    assert "let s=esc(value)" in PAGE                      # escape before format
    assert "lower.startsWith('javascript:')" in PAGE       # js: scheme blocked
    assert "lower.startsWith('data:')" in PAGE             # data: scheme blocked
    assert "innerHTML=data.text" not in PAGE              # no raw passthrough
    assert "frame.setAttribute('sandbox','')" in PAGE     # scriptless iframe


def test_svg_is_previewed_as_a_non_executable_image(scoped):
    """An SVG carrying onload/script previews as an image (rendered via <img> in
    the browser's secure static mode); its raw markup is never returned in the
    JSON payload to be injected into the DOM."""
    result = preview(scoped, "experiments/logo.svg", MALICIOUS_SVG)
    assert result["kind"] == "image"
    assert result["image_type"] == "svg"
    assert result.get("width") == 40 and result.get("height") == 20
    blob = repr(result)
    assert "<script" not in blob and "onload" not in blob
    assert "text" not in result


def test_out_of_scope_traversal_and_symlink_bytes_are_refused(scoped, cfg):
    # Files that exist but were never recorded as generator output stay closed.
    (cfg.root / "secret.txt").write_text("private")
    for bad in ("../secret.txt", "secret.txt", "experiments/../crossaudit.yml",
                "crossaudit.yml"):
        with pytest.raises(TransferError):
            preview_artifact(scoped, bad)
    # A committed symlink escaping the tree is refused even once recorded.
    if hasattr(__import__("os"), "symlink"):
        link = cfg.root / "experiments" / "escape.png"
        link.parent.mkdir(exist_ok=True)
        link.symlink_to(cfg.root / "crossaudit.yml")
        subprocess.run(["git", "add", "--", "experiments/escape.png"],
                       cwd=cfg.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "produce escape (round 1)"],
                       cwd=cfg.root, check=True)
        with pytest.raises(TransferError):
            preview_artifact(scoped, "experiments/escape.png")


# --------------------------------------------------------------------- caps
def test_oversize_text_is_clipped_not_refused(scoped, monkeypatch):
    monkeypatch.setattr(transfers, "MAX_PREVIEW_TEXT_BYTES", 64)
    result = preview(scoped, "experiments/big.txt", b"A" * 500)
    assert result["truncated"] is True
    assert len(result["text"].encode("utf-8")) <= 64


def test_oversize_docx_is_refused_before_it_is_read(cfg, monkeypatch):
    from crossaudit.document_export import (SOURCE_SUFFIX, export_instructions,
                                            render_export)

    scoped_cfg = replace(cfg, scope_dirs=["experiments"])
    relative = f"experiments/big{SOURCE_SUFFIX}"
    (cfg.root / relative).write_text("# Doc\n\nBody.\n")
    final = render_export(cfg.root, [relative],
                          "Write" + export_instructions("docx"))[0]
    subprocess.run(["git", "add", "--", final], cwd=cfg.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "produce big (round 1)"],
                   cwd=cfg.root, check=True)
    monkeypatch.setattr(transfers, "MAX_PREVIEW_DOCX_BYTES", 16)
    with pytest.raises(TransferError) as excinfo:
        preview_artifact(scoped_cfg, final)
    assert excinfo.value.status == 413


def test_csv_parses_to_rows_and_columns(scoped):
    data = b"city,pop\nOslo,700000\nBergen,280000\n"
    result = preview(scoped, "experiments/cities.csv", data)
    assert result["kind"] == "table"
    assert result["columns"] == ["city", "pop"]
    assert result["rows"] == [["Oslo", "700000"], ["Bergen", "280000"]]
    assert result["col_count"] == 2


def test_huge_csv_is_capped_and_marked_truncated(scoped, monkeypatch):
    monkeypatch.setattr(transfers, "MAX_PREVIEW_TABLE_ROWS", 3)
    body = "h1,h2\n" + "".join(f"{i},{i}\n" for i in range(50))
    result = preview(scoped, "experiments/wide.csv", body.encode())
    assert result["truncated"] is True
    assert len(result["rows"]) <= 3


def test_unknown_binary_returns_honest_metadata_not_a_crash(scoped):
    data = bytes(range(256)) + b"\x00tail"
    result = preview(scoped, "experiments/opaque.dat", data)
    assert result["kind"] == "binary"
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["hex"] and result["sample_bytes"] > 0
    # The hex sample is bounded regardless of file size.
    assert result["sample_bytes"] <= transfers.HEX_SAMPLE_BYTES


# ---------------------------------------------------------- HTTP boundary
@pytest.fixture()
def served(science):
    yml = science / "crossaudit.yml"
    text = yml.read_text()
    if "scope:" not in text:
        yml.write_text(text + "scope:\n  dirs: [experiments]\n")
    cfg = load(science / "crossaudit.yml")
    commit(cfg, "experiments/logo.svg", MALICIOUS_SVG, "produce logo (round 1)")
    commit(cfg, "experiments/read.txt", b"hello\n", "produce read (round 1)")
    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    token = parse_qs(urlparse(url).query)["t"][0]
    origin = f"http://127.0.0.1:{urlparse(url).port}"
    try:
        yield origin, token
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def _get(url: str, **headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, response.read(), dict(response.headers)


def _status_of(call) -> int:
    try:
        call()
    except urllib.error.HTTPError as error:
        try:
            return error.code
        finally:
            error.close()
    raise AssertionError("request unexpectedly succeeded")


def test_raw_bytes_endpoint_requires_the_token(served):
    origin, token = served
    assert _status_of(
        lambda: _get(f"{origin}/api/file?path=experiments/read.txt")) == 403
    assert _status_of(
        lambda: _get(f"{origin}/api/preview?path=experiments/read.txt")) == 403


def test_svg_bytes_are_content_typed_safely_and_not_as_html(served):
    origin, token = served
    status, body, headers = _get(
        f"{origin}/api/file?t={token}&path=experiments/logo.svg&view=1")
    assert status == 200
    ctype = headers.get("content-type", "")
    assert ctype.startswith("image/svg+xml")     # never text/html
    assert "html" not in ctype
    assert headers.get("x-content-type-options") == "nosniff"
    # A scriptless sandbox neutralises any script/onload inside the SVG even on
    # a direct navigation to the bytes.
    assert "sandbox" in headers.get("content-security-policy", "")


def test_http_traversal_and_out_of_scope_are_refused(served):
    origin, token = served
    for bad in ("../crossaudit.yml", "crossaudit.yml", "experiments/missing.txt"):
        code = _status_of(
            lambda p=bad: _get(f"{origin}/api/file?t={token}&path={p}"))
        assert code in (400, 404)


def test_preview_over_http_dispatches_the_svg_as_image(served):
    origin, token = served
    status, body, headers = _get(
        f"{origin}/api/preview?t={token}&path=experiments/logo.svg")
    assert status == 200
    import json
    payload = json.loads(body)
    assert payload["kind"] == "image" and payload["image_type"] == "svg"
    assert "<script" not in body.decode()


# ------------------------------------------------------------ PAGE contract
def test_page_carries_the_preview_framework_markers():
    from crossaudit.console.page import PAGE

    for marker in ('id="file-preview-toolbar"', 'id="file-preview-search"',
                   'id="file-preview-wrap"', 'id="file-preview-copy"',
                   'id="file-preview-outline"', 'id="file-preview-source"',
                   'id="file-preview-zoom-in"', 'id="file-preview-find-next"'):
        assert marker in PAGE


def test_preview_modal_stays_a_named_dialog():
    from crossaudit.console.page import PAGE

    assert 'id="file-preview-modal"' in PAGE
    assert 'role="dialog"' in PAGE
    assert 'aria-modal="true"' in PAGE
    assert 'aria-labelledby="file-preview-title"' in PAGE


def test_new_preview_strings_have_a_chinese_display_layer():
    from crossaudit.console.page import PAGE

    for chinese in ("搜索预览", "自动换行", "复制", "大纲", "放大", "缩小",
                    "字节样本", "重置视图"):
        assert chinese in PAGE


def test_inline_markdown_regexes_are_bounded_against_redos():
    """The inline-markdown link/emphasis regexes must use BOUNDED quantifiers.

    An unbounded ``[^x]+`` over a pathological single line (e.g. a megabyte of
    '[') backtracks O(N^2) and freezes this single-threaded console for minutes
    — a real DoS on the privileged page (found by an adversarial review). Guard
    against reintroducing the unbounded form.
    """
    from crossaudit.console.page import PAGE

    assert r"\[([^\]]+)\]\(([^)]+)\)" not in PAGE   # catastrophic unbounded link
    assert r"{1,2048}" in PAGE                       # capped link url
    assert r"[^`\n]{1,500}" in PAGE                  # capped code span


# --------------------------------------------------------------------------
# D106. The markup check above (test_page_markup_contains_the_escape_and_scheme_checks)
# asserts that `esc(...)` and the scheme comparisons appear in page.py. It cannot
# fail if they are present and never reached: serving an empty document leaves it
# green. A renamed guard states that honestly; it does not make the XSS property
# tested. This runs the SHIPPED renderer over payloads and asserts the output.
#
# The extraction/node pattern is the one ten other test modules already use. It is
# copied rather than shared because there is no common helper yet; consolidating
# those eleven copies is a separate change and is recorded, not done here.
def _preview_page_script() -> str:
    from crossaudit.console.page import PAGE

    return PAGE.split("<script>")[1].split("</script>")[0]


def _preview_fn(signature: str) -> str:
    """One shipped function, sliced out by brace matching -- never re-stated."""
    script = _preview_page_script()
    start = script.index(signature)
    depth, i = 0, script.index("{", start)
    while i < len(script):
        if script[i] == "{":
            depth += 1
        elif script[i] == "}":
            depth -= 1
            if depth == 0:
                return script[start:i + 1]
        i += 1
    raise AssertionError(f"unbalanced: {signature}")


#: Each payload is a real attack shape, with what the renderer must not emit.
XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "[click](javascript:alert(1))",
    "[click](JaVaScRiPt:alert(1))",
    "[click](data:text/html,<script>alert(1)</script>)",
    "[click](vbscript:msgbox(1))",
    "[click](  java\tscript:alert(1))",
    "> <svg/onload=alert(1)>",
    "`<script>alert(1)</script>`",
]
#: Only the renderer's own vocabulary may appear in the output; any other
#: element came from the payload and means escaping failed.
RENDERER_TAGS = {"p", "code", "strong", "em", "a", "blockquote", "ul", "ol",
                 "li", "pre", "hr", "h1", "h2", "h3", "h4", "h5", "h6"}
SAFE_LINK = "[docs](https://example.com/a?b=1&c=2)"


def _render_shipped_markdown(payloads):
    """Run the SHIPPED renderMarkdown over payloads; return the html it emits."""
    script = _preview_page_script()
    esc_src = script[script.index("const esc = s =>"):script.index("const at = t =>")]
    js = "\n".join((
        esc_src,
        _preview_fn("function safeUrl(raw)"),
        _preview_fn("function inlineMarkdown(value)"),
        _preview_fn("function renderMarkdown(value)"),
        "const P=" + json.dumps(payloads) + ";",
        "console.log(JSON.stringify(P.map(p => renderMarkdown(p).html)));",
    ))
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    run = run_node(js, node)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_the_shipped_markdown_renderer_neutralises_real_payloads():
    """These nine payload shapes produce no element or scheme the renderer did
    not choose. Narrower than "no live sink survives", which this does not show.

    WHAT IT COVERS: the nine shapes in XSS_PAYLOADS, through `renderMarkdown`
    and the two functions it delegates to, with the vocabulary check in
    RENDERER_TAGS and the scheme check on emitted tags. A payload shape nobody
    listed here is not covered, and the author chose the list — so a reviewer's
    first job is a payload the author did not think of.

    WHAT IT DOES NOT COVER: anything downstream of this html — insertion,
    sanitiser ordering, CSP, or what a browser does with it. It runs the
    functions in node over a string.

    Its mutation, and this is the acceptance test for the guard itself: make
    `esc` the identity, or `safeUrl` return its input, and this must go red by
    name. The markup check cannot see either -- that is why both exist.
    """
    rendered = _render_shipped_markdown(XSS_PAYLOADS + [SAFE_LINK])
    html = rendered[:-1]
    for payload, out in zip(XSS_PAYLOADS, html):
        # The property is about ELEMENTS and SCHEMES, never about text. An
        # escaped payload legitimately still contains the word "onerror" as
        # inert text inside &lt;...&gt;, and asserting over the text accused a
        # correct renderer -- my own first mistake writing this guard.
        tags = {t.lower() for t in re.findall(r"<\s*/?\s*([A-Za-z][A-Za-z0-9]*)", out)}
        assert tags <= RENDERER_TAGS, (
            f"payload introduced an element: {payload!r} -> {sorted(tags - RENDERER_TAGS)}")
        # No handler-attribute scan: every attribute on an emitted tag is one
        # this renderer wrote, with its value `esc`-ed, so the vocabulary check
        # above already carries it. A `\bon[a-z]+=` scan over tag bodies adds no
        # coverage and WOULD false-accuse a correct renderer on a link whose
        # title or text legitimately reads like a handler. A guard that reddens
        # on correct code gets suppressed, and the habit outlives the guard.
        for tag_body in re.findall(r"<[^>]*>", out):
            low = tag_body.lower()
            for scheme in ("javascript:", "data:", "vbscript:", "file:"):
                assert scheme not in low, (
                    f"dangerous scheme reached a tag: {payload!r} -> {tag_body!r}")
    # A positive control, so the test cannot pass by neutralising everything.
    assert 'href="https://example.com/a?b=1&amp;c=2"' in rendered[-1], rendered[-1]
    assert 'rel="noopener noreferrer nofollow"' in rendered[-1]
