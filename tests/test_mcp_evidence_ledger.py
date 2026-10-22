"""D174: an MCP tool call made during a build is a governed action in the
evidence ledger, the receipt binds it, and `verify` re-derives it.

A real stdio MCP server (stdlib JSON-RPC, written below) is registered the way
the console registers one, and a real `run_loop` build calls it through a
scripted Generator; the audit after it runs on the replay provider. Each test
names the mutation it catches.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from crossaudit import generator as generator_mod
from crossaudit import mcp
from crossaudit.broker.tools_mcp import governed_mcp_call
from crossaudit.errors import ConfigDenial, IntegrityDenial
from crossaudit.ledger import EvidenceLedger

ARG_MARKER = "ARGUMENT-MARKER-91c4"
OUT_MARKER = "TOOL-OUTPUT-MARKER-7f3e"

SERVER = r'''import json, sys
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    method = message.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "ledger-fixture", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [
            {"name": "lookup", "description": "Look up one value",
             "inputSchema": {"type": "object",
                             "properties": {"query": {"type": "string"}}}},
            {"name": "mutate", "description": "Never allowlisted",
             "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        args = message.get("params", {}).get("arguments", {})
        result = {"content": [{"type": "text",
                               "text": "%s for " % OUT + args.get("query", "")}],
                  "isError": False}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                          "error": {"code": -32601, "message": "missing"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}),
          flush=True)
'''.replace("OUT", repr(OUT_MARKER), 1)


def _register(cfg, tmp_path):
    script = tmp_path / "ledger_fixture_mcp.py"
    script.write_text(SERVER)
    return mcp.MANAGER.register(cfg, {
        "name": "Ledger fixture", "transport": "stdio",
        "command": sys.executable, "args": [str(script)],
        "approve_local_code": True, "enabled": True,
        "allowed_tools": ["lookup"], "max_calls_per_task": 3})


def _ledger(cfg) -> EvidenceLedger:
    return EvidenceLedger(cfg.root / cfg.state_dir / "evidence.jsonl")


def _build_with_one_tool_call(science, cfg, monkeypatch, server_id, seen=None):
    from crossaudit.cli import build as build_mod

    seen = [] if seen is None else seen

    def fake_generate(**kwargs):
        seen.append(kwargs)
        if len(seen) == 1:
            return generator_mod.ToolRequest({
                "server_id": server_id, "tool": "lookup",
                "arguments": {"query": ARG_MARKER}})
        return generator_mod.Work(
            summary="used the lookup",
            files={"experiments/demo/SUMMARY.md": "Looked it up.\n"})

    monkeypatch.setattr(build_mod, "_generator_complete", lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    code = build_mod.run_loop(replace(cfg, scope_dirs=["experiments"], max_rounds=1),
                              "use the approved lookup tool")
    return code, seen


def test_build_mcp_call_is_ledgered_bound_by_the_receipt_and_verified(
        science, cfg, transcripts, monkeypatch, tmp_path, capsys):
    """Mutation: call `mcp.MANAGER.call_agent` from the build directly again
    (the pre-D174 path) -- the ledger file is never created and the receipt
    carries no tool_evidence block."""
    from crossaudit.cli.main import cmd_verify

    server = _register(cfg, tmp_path)
    code, seen = _build_with_one_tool_call(science, cfg, monkeypatch, server["id"])
    assert len(seen) == 2
    assert seen[1]["tool_results"][0]["status"] == "completed"
    assert OUT_MARKER in seen[1]["tool_results"][0]["content"][0]["text"]

    led = _ledger(cfg)
    rows = led.entries()
    assert [r["kind"] for r in rows] == ["tool_call", "tool_result"]
    call, result = rows[0]["payload"], rows[1]["payload"]
    logged = json.loads((cfg.root / cfg.state_dir / "mcp" / "calls.json").read_text())[-1]
    assert call == {
        "tool": "mcp_call", "server_id": server["id"], "mcp_tool": "lookup",
        "args_sha256": logged["arguments_sha256"], "approval": "owner_allowlist",
        "allowlisted": True, "allowlist_sha256": call["allowlist_sha256"],
        "call_ordinal": 1, "call_budget": 3}
    assert len(call["allowlist_sha256"]) == 64
    assert set(result) == {"tool", "server_id", "mcp_tool", "call_id", "status",
                           "result_sha256", "bytes", "truncated", "duration_ms"}
    assert result["status"] == "completed" and result["call_id"] == logged["id"]
    assert result["result_sha256"] == logged["result_sha256"]
    assert result["truncated"] is False and result["bytes"] > 0
    raw = led.path.read_text(encoding="utf-8")
    assert ARG_MARKER not in raw and OUT_MARKER not in raw

    receipts = sorted((cfg.root / cfg.ledger_dir).glob("*/receipt.json"))
    assert receipts, f"the build wrote no receipt (exit {code})"
    receipt = json.loads(receipts[-1].read_text())
    assert receipt["tool_evidence"] == {"ledger_head": led.head(), "entries": 2}

    args = SimpleNamespace(receipt=str(receipts[-1]), science_root=None,
                           audit_root=None, expect_repo=None, expect_sha=None,
                           admit=False, json=True)
    assert cmd_verify(args) == 0
    capsys.readouterr()

    # Mutation: one ledger line edited after the receipt was minted (the
    # result hash rewritten, the stored digest left alone).
    lines = raw.splitlines(keepends=True)
    entry = json.loads(lines[1])
    entry["payload"]["result_sha256"] = "0" * 64
    lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
    led.path.write_text("".join(lines), encoding="utf-8")
    with pytest.raises(IntegrityDenial, match="evidence ledger failed re-derivation"):
        cmd_verify(args)


def test_a_ledger_that_refuses_the_append_stops_the_call_before_it_runs(
        science, cfg, transcripts, monkeypatch, tmp_path):
    """Mutation: catch the ledger's IntegrityDenial in the build as one more
    refused tool result -- the build continues and the run is not stopped."""
    server = _register(cfg, tmp_path)
    led = _ledger(cfg)
    led.append("note", run_id="r", payload={"n": 1}, ts="t0")
    led.path.write_text(led.path.read_text().replace('"n":1', '"n":2'))

    seen: list = []
    with pytest.raises(IntegrityDenial, match="does not verify"):
        _build_with_one_tool_call(science, cfg, monkeypatch, server["id"], seen)
    # The run stopped at the call: the Generator was never handed a
    # "refused" tool result to work around.
    assert len(seen) == 1
    calls = cfg.root / cfg.state_dir / "mcp" / "calls.json"
    assert not calls.exists() or json.loads(calls.read_text()) == []


def test_a_refused_call_is_recorded_as_refused_without_running(cfg, tmp_path):
    """Mutation: append nothing when the owner's policy refuses -- a refused
    governed action disappears from the evidence."""
    server = _register(cfg, tmp_path)
    led = _ledger(cfg)
    with pytest.raises(ConfigDenial, match="not approved"):
        governed_mcp_call(cfg, {"server_id": server["id"], "tool": "mutate",
                                "arguments": {"q": ARG_MARKER}},
                          ledger=led, run_id="run-1", ordinal=1)
    rows = led.entries()
    assert [r["kind"] for r in rows] == ["tool_call", "tool_result"]
    assert rows[0]["payload"]["allowlisted"] is False
    assert rows[0]["payload"]["mcp_tool"] == "mutate"
    assert rows[1]["payload"]["status"] == "refused"
    assert ARG_MARKER not in led.path.read_text()
    assert led.verify().ok
    assert mcp.MANAGER.snapshot(cfg)["calls"] == []


def test_a_model_supplied_identifier_of_the_wrong_shape_is_not_copied(cfg):
    """Mutation: record the request's server id verbatim -- model text of any
    length and content enters the ledger."""
    led = _ledger(cfg)
    with pytest.raises(ConfigDenial):
        governed_mcp_call(cfg, {"server_id": "x" * 500 + ARG_MARKER, "tool": "a b"},
                          ledger=led, run_id="run-1")
    payload = led.entries()[0]["payload"]
    assert payload["server_id"] == "" and payload["mcp_tool"] == ""
