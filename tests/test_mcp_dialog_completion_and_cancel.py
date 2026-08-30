"""The add-MCP dialog: a person can finish the task, and declining undoes it.

Two defects the design/UX review found by driving the dialog in Chinese:

D1 — the Server-name field offered `检索工具` as its own example and the backend
     refused it, in English, after a round trip. mcp.py is not this slice's to
     change: server names are identifiers and ASCII is a defensible constraint.
     So the example is ASCII in both locales, the constraint is stated in the
     field before anyone types, and the refusal speaks Chinese.
D2 — step 1 has to POST to read the tool list, so pressing Cancel at step 2 left
     a registered server behind. The row is now a draft that every close path
     deletes, and the dialog says so while it is on screen.
"""
import ast
import pathlib
import re

from crossaudit import mcp
from crossaudit.console.page import PAGE


# ------------------------------------------------------------------------- D1
def test_the_server_name_example_is_one_the_backend_accepts():
    placeholder = re.search(r'id="mcp-name"[^>]*placeholder="([^"]*)"', PAGE)
    assert placeholder, "the server-name field lost its placeholder"
    assert mcp.SERVER_NAME.fullmatch(placeholder.group(1))
    # ...and it stays that value in Chinese. A translated example was a
    # suggestion the field's own backend refuses (AGENTS.md §1.5).
    assert '"Research tools":' not in PAGE


def test_the_name_rule_is_stated_before_typing_and_in_both_languages():
    assert 'id="mcp-name-help"' in PAGE
    assert 'aria-describedby="mcp-name-help"' in PAGE
    assert ("A label for this project. ASCII letters, digits, spaces and . _ - only."
            in PAGE)
    assert ('"A label for this project. ASCII letters, digits, spaces and . _ - only.":'
            '"本项目中的标识名称。仅限 ASCII 字母、数字、空格和 . _ -。"') in PAGE


def test_the_client_side_name_check_is_exactly_the_servers_rule():
    """A mirror, never a second opinion: looser would promise what /api/mcp
    refuses, tighter would refuse a name the project can actually hold."""
    mirror = re.search(r"const MCP_NAME_RE=/\^(.+)\$/;", PAGE)
    assert mirror, "the client-side server-name mirror is gone"
    assert mirror.group(1) == mcp.SERVER_NAME.pattern
    assert "MCP_NAME_RE.test(name)" in PAGE
    assert ("Server names use ASCII letters, digits, spaces and . _ - only. "
            "Rename this server to continue.") in PAGE
    # The field, not just the error box, is marked and focused.
    assert "nameField.setAttribute('aria-invalid','true')" in PAGE
    assert "nameField.focus()" in PAGE


def test_every_constant_mcp_denial_has_a_chinese_translation():
    """A refusal is user-facing text. The backend wording is the contract; this
    pins that none of it reaches a Chinese reader in English only."""
    source = pathlib.Path(mcp.__file__).read_text(encoding="utf-8")
    literals = {
        node.args[0].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "ConfigDenial"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert literals, "no constant ConfigDenial messages found in mcp.py"
    missing = sorted(text for text in literals if '"%s":' % text not in PAGE)
    assert not missing, missing


# ------------------------------------------------------------------------- D2
def test_cancelling_step_two_deletes_the_row_step_one_had_to_create():
    assert "let mcpCreatedId='';" in PAGE
    assert "function discardMcpDraft(){const id=mcpCreatedId;if(!id)return;mcpCreatedId='';" in PAGE
    assert "api('/api/mcp',{action:'remove',server_id:id})" in PAGE
    # Cancel, ×, Escape and the backdrop all funnel through closeMcp.
    assert "function closeMcp(){discardMcpDraft();" in PAGE


def test_only_a_row_this_dialog_created_counts_as_a_draft():
    """Configuring a saved server must never delete it on Cancel."""
    assert "if(!priorId&&server.id)mcpCreatedId=server.id;" in PAGE
    # Saving hands the row over before the dialog closes.
    assert "else{mcpCreatedId='';closeMcp();}" in PAGE


def test_a_failed_delete_is_reported_rather_than_hidden():
    assert "the cancelled connection is still listed; remove it there." in PAGE
    assert "已取消的连接仍在列表中，请在那里将其移除。" in PAGE


def test_the_dialog_says_the_connection_is_not_saved_yet():
    assert "Not saved yet — Cancel removes this connection." in PAGE
    assert ('"Not saved yet — Cancel removes this connection.":'
            '"尚未保存 —— 取消将移除此连接。"') in PAGE
    # Shown only while a draft exists, so Configure never claims it.
    assert "const draft=mcpCreatedId?'<small class=\"mcp-draft-note\">" in PAGE


def test_a_second_identical_server_is_refused_with_a_reason():
    assert "function mcpDuplicate(name,vector,selfId){" in PAGE
    assert ("This project already has an MCP server with that name. "
            "Choose a different name, or configure the existing one.") in PAGE
    assert ("This project already has an MCP server running that exact command. "
            "Configure the existing one instead.") in PAGE
    for chinese in ("此项目已存在同名的 MCP 服务器。请换一个名称，或直接配置已有的服务器。",
                    "此项目已存在运行该命令的 MCP 服务器。请直接配置已有的服务器。"):
        assert chinese in PAGE
    # The row being edited is not its own duplicate.
    assert "filter(row=>row.id!==selfId)" in PAGE


def test_a_hidden_error_box_does_not_keep_a_refusal_that_no_longer_applies():
    assert ("function clearMcpError(){const box=document.getElementById('mcp-error');"
            "box.textContent='';box.className='wizard-error';}") in PAGE
