#!/usr/bin/env python3
"""A stdlib stdio MCP server, the minimum the product's client speaks.

    fakemcp.py <log.jsonl>

Framing: one JSON-RPC 2.0 object per line on stdin/stdout (what
``crossaudit/mcp.py``'s ``_StdioSession`` writes and reads). Methods:
``initialize`` (answers protocol 2025-11-25), ``notifications/initialized``
(ignored), ``tools/list`` (one page), ``tools/call``. Anything else with an id
gets JSON-RPC error -32601.

Tools:
  echo    returns ``echo: <arguments.text>``
  big     returns BIG_BYTES of ASCII text (to test "bounded results")
  secret  advertised but meant to stay off the allowlist; returns a marker

Every launch and every message is appended to the log as one JSON line, with
the launch's environment variable NAMES (never values), whether any value looks
like one of the harness's dummy keys, and an identity (the parent directory's
name) so the harness can tell which copy of the executable was started. The
environment names also go to stderr, as the product captures stderr into its
own error text. Python 3.10+, standard library only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROTOCOL = "2025-11-25"
BIG_BYTES = 1_000_000
SECRET_MARKER = "FAKEMCP-SECRET-TOOL-OUTPUT"
ECHO_PREFIX = "echo: "
DUMMY_FRAGMENT = "HARNESS-"   # both dummy provider keys contain it

TOOLS = [
    {"name": "echo", "title": "Echo", "description": "Returns its text argument.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                     "required": ["text"]}},
    {"name": "big", "title": "Big", "description": f"Returns {BIG_BYTES} bytes of text.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "secret", "title": "Secret", "description": "Must stay off the allowlist.",
     "inputSchema": {"type": "object", "properties": {}}},
]

LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else None
IDENTITY = Path(__file__).resolve().parent.name


def log(event: dict) -> None:
    if LOG is None:
        return
    event = {"t": round(time.time(), 3), "pid": os.getpid(), "identity": IDENTITY, **event}
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def call(name: str, arguments: dict) -> dict:
    if name == "echo":
        return {"content": [{"type": "text", "text": ECHO_PREFIX + str(arguments.get("text", ""))}]}
    if name == "big":
        return {"content": [{"type": "text", "text": "B" * BIG_BYTES}]}
    if name == "secret":
        return {"content": [{"type": "text", "text": SECRET_MARKER}]}
    return {"isError": True, "content": [{"type": "text", "text": f"unknown tool {name}"}]}


def main() -> int:
    keys = sorted(os.environ)
    log({"event": "start", "argv0": str(Path(sys.argv[0]).resolve()), "env_keys": keys,
         "dummy_value_present": any(DUMMY_FRAGMENT in v for v in os.environ.values()),
         "cwd": os.getcwd()})
    sys.stderr.write("fakemcp env keys: " + " ".join(keys) + "\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            log({"event": "bad-json", "bytes": len(line)})
            continue
        method, mid = msg.get("method"), msg.get("id")
        params = msg.get("params") or {}
        entry = {"event": "message", "method": method, "id": mid}
        if method == "tools/call":
            entry["tool"] = params.get("name")
            entry["arguments"] = params.get("arguments")
        log(entry)
        if mid is None:          # a notification
            continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                "serverInfo": {"name": "fakemcp", "version": "1.0"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            send({"jsonrpc": "2.0", "id": mid,
                  "result": call(str(params.get("name", "")), params.get("arguments") or {})})
        else:
            send({"jsonrpc": "2.0", "id": mid,
                  "error": {"code": -32601, "message": f"method not found: {method}"}})
    log({"event": "eof"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
