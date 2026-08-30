"""The add-MCP dialog's risk surface says what is true, and says it in time.

Design/UX findings D3 and D6, plus the two changes the owner accepted from the
designer's judgement list. All four are the same discipline in different places:
a rule the backend enforces should be visible before it fires, and an absence of
information should never read as information.
"""
from crossaudit.console.page import PAGE


# ------------------------------------------------------------------------- D3
def test_the_local_command_rule_is_expressed_not_only_enforced():
    """The Generator-access rule was already shown as a disabled control plus a
    reason. /api/mcp enforces the local-command approval the same way, so the
    dialog now states it the same way instead of returning a raw denial."""
    assert 'id="mcp-approve-required"' in PAGE
    assert ("Connect runs this command on your Mac, so the approval above is "
            "required before it can run.") in PAGE
    assert ('"Connect runs this command on your Mac, so the approval above is required '
            'before it can run.":"连接会在你的 Mac 上运行此命令，因此必须先勾选上方的批准。"') in PAGE
    assert ("const needed=mcpStep==='connect'&&stdio&&!mcpApprovalGranted();") in PAGE
    assert "if(save)save.disabled=needed;" in PAGE
    # The button carries the reason for assistive tech, not just the eye.
    assert 'id="save-mcp" aria-describedby="mcp-approve-required"' in PAGE


def test_the_gate_is_re_evaluated_everywhere_the_answer_can_change():
    # ticking, typing a different command, switching transport, changing step,
    # and finishing a submit all re-ask the same question.
    assert "mcpTickedFor=event.target.checked?mcpLiveTuple():null;syncMcpApprovalState();" in PAGE
    assert PAGE.count("syncMcpApprovalState()") >= 6
    assert "finally{button.disabled=false;mcpText('save-mcp',mcpStep==='tools'?'Save':'Connect');syncMcpApprovalState();}" in PAGE


# ------------------------------------------------------------------------- D6
def test_a_tool_the_server_did_not_label_says_so_instead_of_showing_nothing():
    """No badge read as "nothing notable"; it meant "the server said nothing".
    Three states, three visibly different treatments (AGENTS.md §1.5)."""
    assert '<i class="mcp-risk unlabelled">Not labelled by the server</i>' in PAGE
    assert '"Not labelled by the server":"服务器未标注"' in PAGE
    # ...and it is not styled like either of the labels the server did give.
    assert (".mcp-risk.unlabelled{border-style:dashed;border-color:var(--line-strong);"
            "color:var(--text-2);background:none}") in PAGE
    # The empty fallback is gone: every advertised tool now carries a badge.
    assert ":note.readOnlyHint?'<i class=\"mcp-risk readonly\">Read-only</i>':''" not in PAGE


# ------------------------------------------------- accepted designer's judgement
def test_the_unverified_caveat_frames_the_list_instead_of_footnoting_it():
    step_two = PAGE.split('data-mcp-step="tools"')[1].split("</section>")[0]
    caveat = step_two.index("are reported by the server itself")
    listing = step_two.index('id="mcp-tool-approve"')
    heading = step_two.index('class="mcp-approve-head"')
    assert caveat < heading < listing, "the caveat must come before the tool list"


def test_select_all_is_not_a_one_click_path_to_approving_destruction():
    assert "Select all except destructive" in PAGE
    assert '"Select all except destructive":"全选（破坏性除外）"' in PAGE
    assert '"Select all":"全选"' not in PAGE
    # Destructive rows are marked in the DOM so the bulk action can skip them...
    assert "+(note.destructiveHint?' data-mcp-destructive':'')" in PAGE
    assert "const safe=boxes.filter(box=>!box.hasAttribute('data-mcp-destructive'));" in PAGE
    # ...filling only ever fills the safe set; clearing may clear everything.
    assert ("if(safe.length&&safe.every(box=>box.checked))boxes.forEach(box=>{box.checked=false;});"
            "\n  else safe.forEach(box=>{box.checked=true;});") in PAGE
    # The count stays a plain count of every advertised tool, not of the subset.
    assert "mcpText('mcp-approve-count',mcpApproved.size+' of '+boxes.length+' approved');" in PAGE


def test_the_bulk_link_disappears_when_it_would_do_nothing():
    """A server advertising only destructive tools has no safe set to fill."""
    assert "if(link)link.hidden=!safe.length;" in PAGE
