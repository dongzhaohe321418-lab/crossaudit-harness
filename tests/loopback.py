"""HTTP fixtures that bind loopback without a reverse-DNS lookup.

`HTTPServer.server_bind` calls `socket.getfqdn(host)` even when the host is a
numeric loopback address, and `getfqdn` does a reverse lookup that can hang for
as long as the resolver takes to give up. On a GitHub macOS runner that is
longer than the suite's 30s deadline, so

    tests/test_generation_stream_provider.py:94: in __init__
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ...
    socket.py:811: gethostbyaddr(name)
    E   Failed: Timeout (>30.0s) from pytest-timeout

failed on both macOS jobs while every Linux job passed. The address is already
known and numeric; nothing here needs a name for it. `_ConsoleHTTPServer` in the
product does exactly this, for the same reason, on the same call.
"""
from __future__ import annotations

from http.server import HTTPServer, ThreadingHTTPServer
from socketserver import TCPServer


class NumericLoopbackBind:
    """Record the numeric address instead of resolving a name for it."""

    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name = str(self.server_address[0])
        self.server_port = int(self.server_address[1])


class NumericLoopbackHTTPServer(NumericLoopbackBind, ThreadingHTTPServer):
    """Threading server for fixtures that must answer while a test reads."""


class SerialNumericLoopbackHTTPServer(NumericLoopbackBind, HTTPServer):
    """One-request-at-a-time server, for fixtures that want the ordering."""
