"""The generator is told it may propose the built-in read-only tools.

The catalog is injected into the *user* prompt only (the system prompt is
unchanged), and only when tools are passed — so a build that offers no tools
produces the exact prompt it did before. A ``server_id:"crossaudit"`` envelope
parses into a ToolRequest the build loop routes to the broker.
"""
from __future__ import annotations

from crossaudit import generator
from crossaudit.broker.routing import BROKER_SERVER_ID, readonly_catalog


def test_prompt_injects_builtin_tools_section_when_offered():
    p = generator.build_prompt(task="t", constitution="c", current={},
                               builtin_tools=readonly_catalog())
    assert "BUILT-IN READ-ONLY TOOLS" in p and "<<<BUILTIN-TOOLS" in p
    assert "file_read" in p and "search" in p
    assert '"server_id":"crossaudit"' in p or "server_id" in p and "crossaudit" in p


def test_prompt_unchanged_when_no_builtin_tools():
    a = generator.build_prompt(task="t", constitution="c", current={})
    b = generator.build_prompt(task="t", constitution="c", current={},
                               builtin_tools=None)
    assert a == b and "BUILTIN-TOOLS" not in a


def test_crossaudit_envelope_parses_to_tool_request():
    text = ('<<<CROSSAUDIT-MCP-TOOL>>>\n'
            '{"server_id":"crossaudit","tool":"file_read",'
            '"arguments":{"path":"work/a.md"}}\n'
            '<<<END-CROSSAUDIT-MCP-TOOL>>>')
    tr = generator.parse_tool_request(text)
    assert tr is not None
    assert tr.request["server_id"] == BROKER_SERVER_ID
    assert tr.request["tool"] == "file_read"
    assert tr.request["arguments"]["path"] == "work/a.md"
