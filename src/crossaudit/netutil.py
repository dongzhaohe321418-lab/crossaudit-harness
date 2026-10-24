"""Loopback HTTP that never goes through a proxy (D169).

``urllib.request.urlopen`` and a bare ``build_opener`` install a
``ProxyHandler`` built from ``HTTP_PROXY`` / ``http_proxy`` / ``ALL_PROXY``.
On a machine that exports a local proxy (``HTTP_PROXY=http://127.0.0.1:7897``
is common) a request to ``http://127.0.0.1:<port>`` is then sent to the proxy
instead of the port: the proxy sees the console's session token in the query
string, may strip headers, and answers for a server that is not there, so a
liveness probe can report a dead daemon alive or a live one dead.

Every request CrossAudit makes to its own loopback servers goes through
:func:`loopback_opener` or :func:`open_loopback`, whose opener carries an empty
``ProxyHandler`` -- no proxy, whatever the environment says. Requests to
remote hosts are untouched and keep honouring the proxy variables, because a
user behind a proxy needs them there.
"""
from __future__ import annotations

import urllib.parse
import urllib.request

#: Host names a loopback URL may use. Kept to the literal names the product
#: itself generates or accepts; a name that merely resolves to 127.0.0.1 is not
#: treated as loopback (resolving it would be a network lookup).
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_url(url: str) -> bool:
    """True when ``url`` names a loopback host literally."""
    try:
        host = urllib.parse.urlsplit(str(url)).hostname
    except ValueError:
        return False
    return (host or "").lower() in LOOPBACK_HOSTS


def loopback_opener(*handlers) -> urllib.request.OpenerDirector:
    """An opener that never uses a proxy, with ``handlers`` added.

    ``ProxyHandler({})`` replaces the default environment-derived handler
    (``build_opener`` skips a default class when an instance of it is given).
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), *handlers)


def opener_for(url: str, *handlers) -> urllib.request.OpenerDirector:
    """The proxy-free opener for a loopback ``url``; the default one otherwise."""
    if is_loopback_url(url):
        return loopback_opener(*handlers)
    return urllib.request.build_opener(*handlers)


def open_loopback(url: str | urllib.request.Request, *, timeout: float):
    """``urlopen`` for a loopback URL, bypassing every proxy variable.

    Refuses a non-loopback URL with ``ValueError`` so the helper cannot be used
    to send a remote request around the user's proxy by accident.
    """
    target = url.full_url if isinstance(url, urllib.request.Request) else url
    if not is_loopback_url(target):
        raise ValueError(f"open_loopback is for loopback URLs only, not {target!r}")
    return loopback_opener().open(url, timeout=timeout)
