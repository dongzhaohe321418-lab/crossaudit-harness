"""CrossAudit's loopback HTTP never goes through a proxy (D169, F1).

The autouse `_no_proxy_variables` fixture in conftest scrubs the proxy
variables for the suite's own client. Every test here sets one back INSIDE the
test, pointing at a dead loopback port, so a product call that still consulted
the environment would be sent to the dead proxy and fail. Each product check is
paired with its reverse: the same request through urllib's default opener under
the same variable fails, which is what shows the helper -- not the environment
-- makes the difference (AGENTS.md section 3.5).

Mutation (D10): replacing `open_loopback` with `urllib.request.urlopen` in
daemon / app turns the product assertions red; the `*_reverted_helper_fails`
tests perform exactly that substitution with monkeypatch and assert the failure.
"""
from __future__ import annotations

import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from crossaudit import app, mcp, netutil
from crossaudit.console import daemon

from .loopback import NumericLoopbackHTTPServer
from .test_mcp import HTTPFixture

DEAD_PROXY = "http://127.0.0.1:1"
PROXY_NAMES = ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")


def _set_dead_proxy(monkeypatch):
    for name in PROXY_NAMES:
        monkeypatch.setenv(name, DEAD_PROXY)


def _plain_urlopen(url, *, timeout):
    """What the call sites did before: urllib's default opener.

    Built fresh rather than via `urllib.request.urlopen`, whose module-global
    opener is created on first use and keeps the proxy environment of THAT
    moment -- an earlier test in the session would otherwise decide whether
    this one sees the proxy. A fresh `build_opener()` is the default opener as
    a long-running product process started under the variable has it.
    """
    return urllib.request.build_opener().open(url, timeout=timeout)  # nosec B310


@pytest.fixture()
def console(tmp_path: Path):
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
    cfg = load(root / "crossaudit.yml")
    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()
        daemon.clear_run(cfg)


def _port_and_token(url: str) -> tuple[int, str]:
    parts = urllib.parse.urlsplit(url)
    return int(parts.port), urllib.parse.parse_qs(parts.query)["t"][0]


def test_the_scrub_fixture_leaves_no_proxy_variable():
    import os

    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
                 "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        assert name not in os.environ, name


def test_daemon_probes_reach_a_live_console_under_a_dead_proxy(console, monkeypatch):
    port, token = _port_and_token(console)
    _set_dead_proxy(monkeypatch)

    assert daemon.responding(port, token, timeout=5) is True
    state = daemon.fetch_state({"port": port, "token": token}, timeout=5)
    assert isinstance(state, dict) and state

    # Reverse: urllib's default opener under the same variable goes to the
    # dead proxy and fails, so it is the helper that made the probe succeed.
    health = f"http://127.0.0.1:{port}/api/health?t={token}"
    with pytest.raises(urllib.error.URLError):
        _plain_urlopen(health, timeout=5)


def test_daemon_probe_with_the_reverted_helper_fails(console, monkeypatch):
    port, token = _port_and_token(console)
    _set_dead_proxy(monkeypatch)
    monkeypatch.setattr(daemon, "open_loopback", _plain_urlopen)

    assert daemon.responding(port, token, timeout=5) is False
    assert daemon.fetch_state({"port": port, "token": token}, timeout=5) is None


def test_app_health_check_passes_under_a_dead_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(tmp_path / "support"))
    _set_dead_proxy(monkeypatch)

    result = app.self_test()

    assert result["ok"] is True and result["loopback_token_enforced"] is True


def test_app_health_check_with_the_reverted_helper_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(tmp_path / "support"))
    _set_dead_proxy(monkeypatch)
    monkeypatch.setattr(app, "open_loopback", _plain_urlopen)

    with pytest.raises((RuntimeError, urllib.error.URLError)):
        app.self_test()


def test_open_loopback_refuses_a_remote_url():
    with pytest.raises(ValueError):
        netutil.open_loopback("https://example.com/", timeout=1)


@pytest.mark.parametrize("url,loopback", [
    ("http://127.0.0.1:8080/x", True), ("http://localhost/x", True),
    ("http://[::1]:9/x", True), ("http://LOCALHOST/x", True),
    ("https://example.com/mcp", False), ("http://127.0.0.2/x", False),
    ("http://localhost.example.com/x", False), ("not a url", False),
])
def test_is_loopback_url(url, loopback):
    assert netutil.is_loopback_url(url) is loopback


def _proxies(opener) -> dict:
    """The proxies an opener will use. An empty `ProxyHandler` registers no
    `<scheme>_open` method, so OpenerDirector does not keep it at all: no
    handler means no proxy."""
    handlers = [h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler)]
    assert len(handlers) <= 1
    return dict(handlers[0].proxies) if handlers else {}


def test_opener_for_drops_proxies_only_for_loopback(monkeypatch):
    _set_dead_proxy(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", DEAD_PROXY)

    assert _proxies(netutil.opener_for("http://127.0.0.1:5/mcp")) == {}
    remote = _proxies(netutil.opener_for("https://example.com/mcp"))
    assert remote.get("https") == DEAD_PROXY and remote.get("http") == DEAD_PROXY


def test_loopback_mcp_server_is_reached_under_a_dead_proxy(cfg, monkeypatch):
    httpd = NumericLoopbackHTTPServer(("127.0.0.1", 0), HTTPFixture)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        manager = mcp.Manager()
        server = manager.register(cfg, {
            "name": "Local HTTP", "transport": "http",
            "url": f"http://127.0.0.1:{httpd.server_address[1]}/mcp",
            "enabled": True, "allowed_tools": ["search"],
            "max_calls_per_task": 2,
        })
        _set_dead_proxy(monkeypatch)
        result = manager.call_agent(cfg, {
            "server_id": server["id"], "tool": "search", "arguments": {}})
        assert result["content"][0]["text"] == "remote result"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_remote_mcp_session_keeps_the_users_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", DEAD_PROXY)
    session = mcp._HTTPSession({"url": "https://mcp.example.com/mcp"}, "")
    assert _proxies(session.opener).get("https") == DEAD_PROXY
