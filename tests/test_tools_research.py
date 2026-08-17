"""Slice B — governed research retrieval: paper_search + web_fetch (Level 4).

The library card, not a browser: both tools are read-only, always per-call
approval-gated (never auto-run — proven here with the network monkeypatched so
nothing real is ever contacted), SSRF-guarded, size/time-capped, and their
evidence carries hashes and counts — never the query text or page content.
"""
from __future__ import annotations

import io
import json
import urllib.parse

import pytest

from crossaudit.broker import ToolBroker, full_registry
from crossaudit.broker import tools_research as research
from crossaudit.broker.approval import WORKSPACE_WRITES, AuthorizationStore
from crossaudit.broker.registry import ToolError
from crossaudit.broker.routing import live_catalog
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>Perovskite Stability Under Illumination</title>
    <published>2024-01-03T00:00:00Z</published>
    <summary>We study how additives change degradation kinetics.</summary>
    <author><name>A. Chen</name></author>
    <author><name>B. Okafor</name></author>
  </entry>
</feed>"""

S2_JSON = {"data": [{
    "title": "Additive screening for perovskite films",
    "authors": [{"name": "C. Diaz"}], "year": 2023, "venue": "Nature Energy",
    "externalIds": {"DOI": "10.1000/xyz"}, "url": "https://example.org/p1",
    "abstract": "A large screen of additives."}]}

PUBMED_SEARCH = {"esearchresult": {"idlist": ["12345"]}}
PUBMED_SUMMARY = {"result": {"12345": {
    "title": "Perovskite toxicity review", "pubdate": "2022 Jan",
    "fulljournalname": "J. Materials", "authors": [{"name": "D. E"}]}}}

HTML_PAGE = (b"<!doctype html><html><head><title>T</title>"
             b"<script>var ignored=1;</script><style>.x{}</style></head>"
             b"<body><h1>Findings</h1><p>Additives slow degradation.</p>"
             b"</body></html>")


def _tok(tools=("paper_search", "web_fetch")):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": list(tools), "paths": ["**"],
        "writable": False, "expires_at": "2100-01-01T00:00:00Z"})


def _broker(tmp_path):
    return ToolBroker(full_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))


# ------------------------------------------------ never auto-runs, no network
def test_paper_search_never_auto_runs(cfg, tmp_path, monkeypatch):
    fired = []
    monkeypatch.setattr(research, "_http_get",
                        lambda *a, **k: fired.append(1) or b"")
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)   # even fully authorized
    r = _broker(tmp_path).execute(
        {"tool": "paper_search", "args": {"query": "perovskite"}},
        _tok(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval" and fired == []   # nothing contacted


def test_web_fetch_never_auto_runs(cfg, tmp_path, monkeypatch):
    fired = []
    monkeypatch.setattr(research, "_http_get",
                        lambda *a, **k: fired.append(1) or b"")
    r = _broker(tmp_path).execute(
        {"tool": "web_fetch", "args": {"url": "https://example.org/x"}},
        _tok(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval" and fired == []


def test_research_tools_are_offered_in_every_live_catalog(cfg):
    names = [row["name"] for row in live_catalog(cfg)]
    assert "paper_search" in names and "web_fetch" in names


# ------------------------------------------------------------- parsers (canned)
def test_arxiv_parser(monkeypatch):
    monkeypatch.setattr(research, "_http_get",
                        lambda url, **k: ARXIV_ATOM.encode())
    out = research.paper_search(None, {"query": "perovskite"}, _tok())
    assert out["source"] == "arxiv" and out["result_count"] == 1
    row = out["results"][0]
    assert row["title"].startswith("Perovskite Stability")
    assert row["authors"] == ["A. Chen", "B. Okafor"]
    assert row["year"] == "2024" and row["id"] == "2401.01234v1"
    assert row["url"] == "https://arxiv.org/abs/2401.01234v1"
    assert "degradation" in row["snippet"]
    assert len(out["query_sha256"]) == 64 and len(out["result_sha256"]) == 64


def test_semantic_scholar_parser(monkeypatch):
    monkeypatch.setattr(research, "_http_get",
                        lambda url, **k: json.dumps(S2_JSON).encode())
    out = research.paper_search(None, {"query": "x",
                                       "source": "semantic_scholar"}, _tok())
    row = out["results"][0]
    assert row["venue"] == "Nature Energy" and row["id"] == "10.1000/xyz"
    assert row["year"] == "2023"


def test_pubmed_parser_two_step(monkeypatch):
    calls = []

    def fake_get(url, **k):
        calls.append(url)
        body = PUBMED_SEARCH if "esearch" in url else PUBMED_SUMMARY
        return json.dumps(body).encode()

    monkeypatch.setattr(research, "_http_get", fake_get)
    out = research.paper_search(None, {"query": "toxicity",
                                       "source": "pubmed"}, _tok())
    assert len(calls) == 2 and "esearch" in calls[0] and "esummary" in calls[1]
    row = out["results"][0]
    assert row["id"] == "PMID:12345"
    assert row["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"


def test_paper_search_only_contacts_its_fixed_endpoints(monkeypatch):
    seen = []

    def fake_get(url, **k):
        seen.append(url)
        return ARXIV_ATOM.encode()

    monkeypatch.setattr(research, "_http_get", fake_get)
    research.paper_search(None, {"query": "q"}, _tok())
    host = urllib.parse.urlsplit(seen[0]).hostname
    assert host == "export.arxiv.org"                     # pinned origin


def test_html_text_extraction_skips_script_and_style(monkeypatch):
    monkeypatch.setattr(research, "_safe_public_url", lambda u: str(u))
    monkeypatch.setattr(research, "_http_get", lambda url, **k: HTML_PAGE)
    out = research.web_fetch(None, {"url": "https://example.org/a"}, _tok())
    assert out["kind"] == "html"
    assert "Additives slow degradation." in out["text"]
    assert "var ignored" not in out["text"]
    assert out["content_sha256"] and out["chars"] > 0


def test_pdf_text_extraction(monkeypatch):
    from pypdf import PdfWriter
    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buf)
    monkeypatch.setattr(research, "_safe_public_url", lambda u: str(u))
    monkeypatch.setattr(research, "_http_get", lambda url, **k: buf.getvalue())
    out = research.web_fetch(None, {"url": "https://example.org/p.pdf"}, _tok())
    assert out["kind"] == "pdf" and out["bytes"] == len(buf.getvalue())


# ----------------------------------------------------------- refusals / faults
@pytest.mark.parametrize("url", [
    "http://example.org/x",                    # plaintext
    "https://user:pw@example.org/x",           # credentials
    "https://example.org/x#frag",              # fragment
    "ftp://example.org/x", "", "not a url",
])
def test_web_fetch_refuses_unsafe_urls(url):
    with pytest.raises(ToolError):
        research._safe_public_url(url)


def test_web_fetch_refuses_private_hosts(monkeypatch):
    monkeypatch.setattr(research.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.5", 443))])
    with pytest.raises(ToolError, match="private or reserved"):
        research._safe_public_url("https://internal.corp/x")


def test_oversize_fetch_is_refused(monkeypatch):
    class Resp:
        headers = {}
        def read(self, n): return b"x" * n
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class Opener:
        def open(self, req, timeout): return Resp()

    monkeypatch.setattr(research.urllib.request, "build_opener",
                        lambda *a: Opener())
    with pytest.raises(ToolError, match="5 MiB"):
        research._http_get("https://example.org/big")


def test_malformed_xml_is_a_clean_refusal(monkeypatch):
    monkeypatch.setattr(research, "_http_get", lambda url, **k: b"not xml at all")
    with pytest.raises(ToolError, match="malformed XML"):
        research.paper_search(None, {"query": "q"}, _tok())


def test_empty_query_and_unknown_source_are_refused():
    with pytest.raises(ToolError, match="non-empty"):
        research.paper_search(None, {"query": "  "}, _tok())
    with pytest.raises(ToolError, match="unknown source"):
        research.paper_search(None, {"query": "q", "source": "google"}, _tok())


# --------------------------------------------------------------- evidence hygiene
def test_ledger_carries_hashes_never_content(cfg, tmp_path, monkeypatch):
    """Approve via a stub gate and confirm the ledger records only the declared
    evidence fields — the query text, abstracts and page text never enter it."""
    from crossaudit.broker import humanapproval as ha

    monkeypatch.setattr(research, "_http_get",
                        lambda url, **k: ARXIV_ATOM.encode())

    class YesGate:
        def __call__(self, proposal, decision, cfg=None, run_id=""):
            from crossaudit.broker.approval import Approval
            return Approval(granted=True, reason="test grant")

    broker = ToolBroker(full_registry(), EvidenceLedger(tmp_path / "ev.jsonl"),
                        approver=YesGate())
    r = broker.execute({"tool": "paper_search",
                        "args": {"query": "SECRETQUERY perovskite"}},
                       _tok(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "succeeded" and r.output["result_count"] == 1
    raw = (tmp_path / "ev.jsonl").read_bytes().decode()
    assert "SECRETQUERY" not in raw                      # query never ledgered
    assert "degradation kinetics" not in raw             # abstract never ledgered
    assert '"result_count":1' in raw.replace(" ", "") or '"result_count": 1' in raw
