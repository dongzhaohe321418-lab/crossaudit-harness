"""Add-MCP-server dialog + settings navigation (UX plan S6, §7 checklist).

Two defects are pinned here so they cannot come back:

1. The add-MCP dialog used to present one flat form, while ``/api/mcp`` enforces
   a strict order: connect -> read the advertised tool list -> approve named
   tools -> only then let the Generator call them. Both paths a person would
   naturally take ended in a raw ``ConfigDenial``:
     * ticking "approve all" + "enable" on a new server was refused outright;
     * typing tool names (which the placeholder invited) was refused with
       "an allowed MCP tool is not advertised by this server", because the names
       are not discoverable until after the first connection.
   The dialog is now a two-step wizard that states that order, and tools are
   approved by selecting discovered ones rather than by typing exact names.

2. Settings search ranked each group's own overview row above the individual
   control, so searching "Appearance" opened *General* at the top of the pane
   rather than the Appearance control. Results are now scored by specificity,
   and the listbox is operable from the keyboard as its ARIA role promises.

These are UI-contract tests: they read the static PAGE, and run the pure
ranking function under node where one is available (as test_settings_ia does).
"""
from __future__ import annotations

import re
import shutil

from crossaudit.console.page import PAGE

from .node_eval import run_node


# ------------------------------------------------------- the two-step wizard
def test_dialog_is_a_two_step_wizard_that_names_the_real_order():
    # Both steps exist as addressable panes with a progress marker each.
    for step in ("connect", "tools"):
        assert f'data-mcp-step="{step}"' in PAGE, step
        assert f'data-mcp-marker="{step}"' in PAGE, step
    assert "function setMcpStep(step){" in PAGE
    # The order is stated to the person, not left to be discovered by denial.
    assert ("Connecting only reads the server's tool list. Nothing can be "
            "called until you approve it in the next step.") in PAGE
    assert "Connect the server first, then choose which of its tools this project may use." in PAGE
    # A Back route exists, so step 2 is not a trap.
    assert 'id="mcp-back"' in PAGE


def test_step_one_never_approves_or_enables_anything():
    """The connect step must stay fail-closed: no approvals, no Generator access.

    This is the property that makes an abandoned dialog safe — a server that was
    connected but never finished is left switched off.
    """
    assert "payload.allowed_tools=connecting?[]:[...mcpApproved];" in PAGE
    assert "payload.enabled=connecting?false:fd.has('enabled');" in PAGE


def test_blanket_tool_approval_is_gone_in_favour_of_an_explicit_list():
    # The old "approve everything this connection advertises" checkbox let the
    # stored allowlist differ from what the person actually read. Every approval
    # is now an explicit, visible tick.
    assert "allow_all_tools" not in PAGE
    assert "Approve all tools advertised during this connection" not in PAGE


def test_tools_are_chosen_from_the_advertised_list_not_typed():
    # The free-text "type the exact names" field is gone as an input surface; it
    # survives only as hidden form state mirroring the ticked boxes.
    assert '<input type="hidden" name="allowed_tools_text" id="mcp-allowed-tools">' in PAGE
    assert 'placeholder="search, fetch_record"' not in PAGE
    assert "Comma-separated exact names." not in PAGE
    # Discovered tools render as checkboxes with their advertised metadata.
    assert "function renderMcpTools(){" in PAGE
    assert 'data-mcp-tool="' in PAGE
    assert 'id="mcp-select-all"' in PAGE
    # Server-supplied text is escaped before it reaches the DOM.
    assert "esc(tool.description||'No description provided.')" in PAGE
    assert "esc(tool.name)" in PAGE


def test_enable_is_blocked_until_something_is_approved():
    """/api/mcp refuses "enabled with nothing approved"; the UI says so first."""
    assert "enable.disabled=none;if(none)enable.checked=false;" in PAGE
    assert "Approve at least one tool before the Generator can call this server." in PAGE


def test_page_markup_carries_the_risk_labels_and_the_unverified_disclaimer():
    """MARKUP ONLY. Asserts strings in ``page.py``; renders nothing and cannot
    fail if the page never reaches a person — proved under D106 by serving an
    empty document, which left it green.
    """
    # Annotations come from the server. Surfacing them is useful; implying
    # CrossAudit checked them would be an overclaim (AGENTS.md §1.5).
    assert "note.destructiveHint" in PAGE and "note.readOnlyHint" in PAGE
    assert ("Tool names, descriptions and risk labels are reported by the server "
            "itself and are not verified by CrossAudit.") in PAGE


def test_footer_is_pinned_so_the_primary_action_is_not_below_the_fold():
    # Same layout contract the other wizards already use: fixed head/foot with
    # only the body scrolling. Previously the whole dialog scrolled and the
    # save button sat ~200px past the fold.
    assert ".mcp-wizard{display:flex;flex-direction:column;overflow:hidden}" in PAGE
    assert ".mcp-wizard>.wizard-head,.mcp-wizard>.mcp-steps,.mcp-wizard>.wizard-foot{flex:none}" in PAGE
    assert ".mcp-wizard-body{flex:1;min-height:0;overflow:auto}" in PAGE
    assert 'class="wizard mcp-wizard"' in PAGE


def test_strings_other_tests_depend_on_survive_the_redesign():
    # tests/test_mcp.py pins these; keep them honest and present.
    for text in ('id="mcp-modal"', 'id="mcp-form"', "Add MCP server", "Local stdio",
                 "Streamable HTTP", "I approve this exact local command",
                 "Tools this project may use",
                 "Allow Generator to call the approved tools automatically",
                 "/api/mcp", "data-mcp-configure"):
        assert text in PAGE, text
    assert "eval(" not in PAGE


# --------------------------------------------------------- settings navigation
def test_every_settings_nav_button_has_exactly_one_matching_pane():
    nav = re.findall(r'data-settings-panel="([a-z-]+)"', PAGE)
    panes = re.findall(r'data-settings-pane="([a-z-]+)"', PAGE)
    assert nav, "no settings nav buttons found"
    assert sorted(nav) == sorted(panes)
    assert len(set(nav)) == len(nav), "a settings panel is declared twice"


def test_every_search_index_entry_points_at_a_real_pane_and_anchor():
    panes = set(re.findall(r'data-settings-pane="([a-z-]+)"', PAGE))
    index = re.search(r"const SETTINGS_INDEX=\[(.*?)\n\];", PAGE, re.DOTALL)
    assert index, "settings search index not found"
    body = index.group(1)
    for panel in re.findall(r"\{panel:'([a-z-]+)'", body):
        assert panel in panes, f"search result would open a missing pane: {panel}"
    for anchor in re.findall(r"anchor:'([A-Za-z0-9_-]+)'", body):
        assert f'id="{anchor}"' in PAGE, f"search anchor has no target: {anchor}"


def test_skills_search_entry_has_a_landing_target():
    # "Skills" used to drop the person at the top of Integrations with no
    # skills control anywhere in the pane.
    assert "label:'Skills',anchor:'settings-open-skills'" in PAGE
    assert 'id="settings-open-skills" data-settings-open="skills"' in PAGE
    assert "else if(target==='skills')openSkillsEditor();" in PAGE


def test_manage_skills_lands_on_the_skills_editor():
    # The editor lives in the runtime "Generator guidance" pane, so arriving at
    # the top of that pane read as a wrong jump. Both entry points now focus the
    # control the button names.
    assert "function openSkillsEditor(){" in PAGE
    assert "getElementById('runtime-skill-select')" in PAGE
    assert "if(ev.target.closest('[data-manage-skills]'))openSkillsEditor();" in PAGE


def test_search_results_are_a_keyboard_operable_listbox():
    assert 'role="option"' in PAGE
    assert "aria-selected=" in PAGE
    assert "aria-activedescendant" in PAGE
    assert "function openSettingsResult(row){" in PAGE
    for key in ("ArrowDown", "ArrowUp", "Enter", "Escape"):
        assert f"ev.key==='{key}'" in PAGE, key


def _extract(signature: str) -> str:
    match = re.search(re.escape(signature) + r"\{.*?\n\}", PAGE, re.DOTALL)
    assert match, signature
    return match.group(0)


def test_search_ranks_the_named_item_above_its_group_row():
    node = shutil.which("node")
    if not node:  # Python-only machines still run the rest of the suite.
        return
    harness = _extract("function settingsSearchScore(entry,q)") + """
const A = (cond, msg) => { if (!cond) { throw new Error(msg); } };
// The exact bug: the group's overview row used to outrank the named control.
const generalGroup = {panel:'general',group:'General',label:'General',
  heading:'Language and appearance',purpose:'Choose how CrossAudit looks and reads on this Mac.'};
const appearance = {panel:'general',group:'General',label:'Appearance',
  anchor:'settings-appearance',keywords:'theme light dark'};
A(settingsSearchScore(appearance,'Appearance') > settingsSearchScore(generalGroup,'Appearance'),
  'Appearance must outrank General for the query "Appearance"');

const agentGroup = {panel:'agent',group:'Agent behavior',label:'Agent behavior',
  heading:'Permissions and per-project defaults',purpose:'How the generator ... rounds run'};
const permissions = {panel:'agent',group:'Agent behavior',label:'Permissions',
  anchor:'settings-permissions',keywords:'permissions writes edit files commands'};
A(settingsSearchScore(permissions,'permissions') > settingsSearchScore(agentGroup,'permissions'),
  'Permissions must outrank Agent behavior for the query "permissions"');

const integrations = {panel:'integrations',group:'Integrations',label:'Integrations',
  heading:'MCP, skills, and tools',purpose:'Capabilities the generator can call while it works.'};
const skills = {panel:'integrations',group:'Integrations',label:'Skills',
  anchor:'settings-open-skills',keywords:'skills manage install guidance'};
A(settingsSearchScore(skills,'Skills') > settingsSearchScore(integrations,'Skills'),
  'Skills must outrank Integrations for the query "Skills"');

// An exact label match beats a mere prefix, which beats a keyword-only hit.
A(settingsSearchScore(appearance,'Appearance') > settingsSearchScore(appearance,'Appear'),
  'exact label match should score above a prefix match');
A(settingsSearchScore(appearance,'Appear') > settingsSearchScore(appearance,'dark'),
  'a label prefix should score above a keywords-only hit');
// Case-insensitive, and an empty query stays neutral.
A(settingsSearchScore(appearance,'APPEARANCE') === settingsSearchScore(appearance,'appearance'),
  'ranking must be case-insensitive');
A(settingsSearchScore(appearance,'') === 0, 'empty query scores nothing');
console.log('ok');
"""
    result = run_node(harness, node)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# --------------------------------------------------------------- §24 ZH parity
def test_every_new_visible_string_has_chinese_parity():
    for pair in (
        # dialog shell + steps
        '"Connect the server first, then choose which of its tools this project may use.":'
        '"先连接服务器，再选择本项目可以使用它的哪些工具。"',
        '"Reach the server":"连接到服务器"',
        '"Approve tools":"批准工具"',
        '"Choose what it may do":"选择它可以做什么"',
        # connect step
        '"Call limits":"调用限制"',
        '"Seconds to wait for one response.":"等待单次响应的秒数。"',
        '"How many times a single task may call this server.":"单个任务可以调用此服务器的次数。"',
        '"Connecting only reads the server\'s tool list. Nothing can be called until you '
        'approve it in the next step.":"连接只会读取服务器的工具列表。在你于下一步批准之前，任何工具都不会被调用。"',
        # approve step
        '"Connected":"已连接"',  # reused, already in the dictionary
        '"Save":"保存"',
        '"Saving…":"正在保存…"',
        # Relabelled: the bulk action deliberately stops short of the tools the
        # server labelled destructive, so the label has to say so.
        '"Select all except destructive":"全选（破坏性除外）"',
        '"Clear all":"全部清除"',
        '"Read-only":"只读"',
        '"May change data":"可能修改数据"',
        '"No description provided.":"未提供说明。"',
        '"Advertised tools":"公布的工具"',
        '"This server advertised no tools, so there is nothing to approve.":'
        '"此服务器未公布任何工具，因此没有可批准的内容。"',
        '"Approve at least one tool before the Generator can call this server.":'
        '"先批准至少一个工具，生成者才能调用此服务器。"',
        '"Leave this off to keep the server manual-only. You can turn it on later.":'
        '"保持关闭即为仅手动使用。你可以稍后再开启。"',
    ):
        assert pair in PAGE, pair


def test_generated_approval_counter_is_translated_by_pattern():
    # "2 of 3 approved" is built at runtime, so it needs a ZH_PATTERNS rule
    # rather than a dictionary key.
    assert r"/^(\d+) of (\d+) approved$/i" in PAGE
    assert "已批准 " in PAGE


# ------------------------------- reopening a saved stdio server (regression)
# Configure -> Save on an unchanged saved stdio server used to fail with HTTP
# 400 "approve the exact local MCP command before it runs": openMcp() calls
# mcpForm.reset(), which clears approve_local_code, and an existing server opens
# on step 2 where that checkbox is not rendered, so submit sent false. Editing a
# timeout was therefore impossible. The client now carries the approval the
# person already gave for that exact command, and re-asks the moment it changes.
def test_a_saved_stdio_server_carries_its_standing_command_approval():
    assert "let mcpApprovedCommand=null;let mcpTickedFor=null;" in PAGE
    assert "function mcpCommandUnchanged(){" in PAGE
    # openMcp adopts the stored row's command as the standing approval...
    assert "mcpApprovedCommand=(server&&(server.transport||'stdio')==='stdio')" in PAGE
    # ...and the submit sends it only for a vector a person actually granted.
    assert ("payload.approve_local_code=payload.transport==='stdio'"
            "&&mcpApprovalGranted();") in PAGE


def test_page_markup_declares_the_standing_approval_box_and_its_sentence():
    """MARKUP ONLY. Asserts strings in ``page.py``; renders nothing and cannot
    fail if the page never reaches a person — proved under D106 by serving an
    empty document, which left it green.
    """
    # The asymmetry has to be visible in the form, not discovered as a denial.
    assert 'id="mcp-approve-box"' in PAGE
    assert 'id="mcp-approved-note"' in PAGE
    assert "This exact command is already approved" in PAGE
    assert ("You approved this executable and these arguments when you connected "
            "the server. Editing either one asks you to approve the new command.") in PAGE
    assert "function syncMcpApprovalState(){" in PAGE
    # Editing either field re-evaluates, so the checkbox returns as you type.
    assert ("for(const id of ['mcp-command','mcp-args'])\n"
            "  document.getElementById(id).addEventListener('input',syncMcpApprovalState);") in PAGE
    # Consent is never left pre-ticked underneath the "already approved" state.
    assert "if(approved&&input){input.checked=false;mcpTickedFor=null;}" in PAGE


def test_closing_the_dialog_drops_the_standing_approval():
    # The approval belongs to one dialog session on one server row; it must not
    # survive into the next thing the person opens.
    assert ("mcpApprovedCommand=null;\n  mcpTickedFor=null;mcpRendered=null;\n"
            "  setMcpStep('connect');syncMcpApprovalState();") in PAGE


def _extract_fn(signature: str) -> str:
    """Extract one JS function by brace counting.

    ``_extract`` above matches up to a line-leading ``}``; these helpers close
    with ``;}`` on their last line, so they need real brace matching.
    """
    start = PAGE.index(signature)
    depth, i = 0, PAGE.index("{", start)
    while i < len(PAGE):
        if PAGE[i] == "{":
            depth += 1
        elif PAGE[i] == "}":
            depth -= 1
            if depth == 0:
                return PAGE[start:i + 1]
        i += 1
    raise AssertionError(signature)


def test_command_approval_carries_only_for_an_identical_command():
    """Both directions, executed: unchanged carries, changed re-requires."""
    node = shutil.which("node")
    if not node:  # Python-only machines still run the rest of the suite.
        return
    harness = "\n".join(_extract_fn(sig) for sig in (
        "function mcpArgsValue()", "function mcpSameTuple(left,right)",
        "function mcpLiveTuple()", "function mcpCommandUnchanged()",
    )) + """
const A = (cond, msg) => { if (!cond) { throw new Error(msg); } };
let FIELDS = {command: '', args: ''};
globalThis.document = {getElementById: id => ({
  get value() { return id === 'mcp-command' ? FIELDS.command : FIELDS.args; },
})};
// The stdio half of the expression the submit handler uses. (The ticked-consent
// half has its own test; this one pins the standing-approval half.)
const approveSent = (transport, ticked) =>
  ticked || (transport === 'stdio' && mcpCommandUnchanged());

globalThis.mcpRendered = null;
globalThis.mcpApprovedCommand = {command: '/usr/local/bin/mcp', args: ['-y', 'server']};

// 1. unchanged command + args -> the standing approval carries (the bug).
FIELDS = {command: '/usr/local/bin/mcp', args: '-y\\nserver'};
A(mcpCommandUnchanged(), 'identical command must count as approved');
A(approveSent('stdio', false) === true, 'unchanged stdio save must not need a re-tick');

// 2. changed command -> re-required.
FIELDS = {command: '/usr/local/bin/other', args: '-y\\nserver'};
A(!mcpCommandUnchanged(), 'a changed command must not carry the approval');
A(approveSent('stdio', false) === false, 'changed command must send approve=false');
A(approveSent('stdio', true) === true, 'ticking the box approves the new command');

// 3. changed arguments -> equally re-required.
FIELDS = {command: '/usr/local/bin/mcp', args: '-y\\nOTHER'};
A(!mcpCommandUnchanged(), 'changed arguments must not carry the approval');
FIELDS = {command: '/usr/local/bin/mcp', args: '-y'};
A(!mcpCommandUnchanged(), 'dropping an argument must not carry the approval');
FIELDS = {command: '/usr/local/bin/mcp', args: '-y\\nserver\\nextra'};
A(!mcpCommandUnchanged(), 'adding an argument must not carry the approval');

// 4. whitespace-only edits are the same command, not a new one.
FIELDS = {command: '  /usr/local/bin/mcp  ', args: '-y\\n\\nserver\\n'};
A(mcpCommandUnchanged(), 'trimming/blank lines must not count as a change');

// 5. a brand-new server has no standing approval at all.
globalThis.mcpApprovedCommand = null;
FIELDS = {command: '/usr/local/bin/mcp', args: '-y\\nserver'};
A(!mcpCommandUnchanged(), 'a new server must never carry an approval');
A(approveSent('stdio', false) === false, 'a new server must send approve=false unticked');

// 6. a remote server never sends a local-command approval.
globalThis.mcpApprovedCommand = {command: '/usr/local/bin/mcp', args: []};
FIELDS = {command: '/usr/local/bin/mcp', args: ''};
A(approveSent('http', false) === false, 'http transport must never send approve=true');
console.log('ok');
"""
    result = run_node(harness, node)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_the_new_approval_strings_have_chinese_parity():
    for pair in (
        '"This exact command is already approved":"此命令已获批准"',
        '"You approved this executable and these arguments when you connected the '
        'server. Editing either one asks you to approve the new command.":'
        '"你在连接此服务器时已批准该可执行文件与这些参数。修改其中任何一项都会要求你重新批准新的命令。"',
    ):
        assert pair in PAGE, pair


# ------------------------- consent binds to one execution vector (S0 regression)
# The first version of this fix modelled consent as a boolean plus one baseline
# and only cleared the checkbox while the form still MATCHED the stored row.
# Once the form had diverged, a tick given for command B rode along to command C
# untouched, and the client POSTed approve_local_code=true for an executable no
# human had ever seen — which the server then launched. Consent is now stored AS
# the {command, args} vector it was granted for, and anything sent must equal a
# vector a person actually approved.
def test_consent_is_stored_as_the_vector_it_was_granted_for():
    assert "let mcpApprovedCommand=null;let mcpTickedFor=null;" in PAGE
    assert "function mcpSameTuple(left,right){" in PAGE
    assert "function mcpLiveTuple(){" in PAGE
    assert "function mcpApprovalGranted(){" in PAGE
    # The submit asks one question, and never trusts the raw form flag.
    assert ("payload.approve_local_code=payload.transport==='stdio'&&mcpApprovalGranted();"
            in PAGE)
    assert "fd.has('approve_local_code')" not in PAGE
    # A tick is only ever recorded together with its vector.
    assert "mcpTickedFor=event.target.checked?mcpLiveTuple():null;" in PAGE
    # ...and revoked as soon as the form no longer describes that vector.
    assert ("if(input&&input.checked&&!mcpSameTuple(mcpLiveTuple(),mcpTickedFor)){\n"
            "    input.checked=false;mcpTickedFor=null;}" in PAGE)


def test_untouched_legacy_arguments_round_trip_verbatim():
    """A stored row with an empty or whitespace argument stays saveable (S1)."""
    assert "let mcpRendered=null;" in PAGE
    # The live vector is the stored row itself while the fields are untouched.
    assert ("if(mcpRendered&&commandText===mcpRendered.commandText"
            "&&argsText===mcpRendered.argsText)" in PAGE)
    # ...and that vector is what gets sent, not a re-parse of the lossy textarea.
    assert "payload.args=vector.args;" in PAGE


def test_a_tick_never_carries_to_another_command_or_argument_list():
    """Executes the state machine, asserting what would be SENT.

    Display state is what fooled the first version, so every assertion here is
    on ``mcpApprovalGranted()`` — the single value the submit puts on the wire.
    """
    node = shutil.which("node")
    if not node:  # Python-only machines still run the rest of the suite.
        return
    harness = "\n".join(_extract_fn(sig) for sig in (
        "function mcpArgsValue()", "function mcpSameTuple(left,right)",
        "function mcpLiveTuple()", "function mcpCommandUnchanged()",
        "function mcpApprovalGranted()", "function syncMcpApprovalState()",
    )) + """
const A = (cond, msg) => { if (!cond) { throw new Error(msg); } };
let FIELDS = {command: '', args: ''};
const BOX = {hidden: false, checked: false};
const NOTE = {hidden: true};
// syncMcpApprovalState also drives the step-1 gate now (design finding D3): the
// same answer that decides what goes on the wire decides whether Connect is
// available and whether the reason for that is on screen.
const ASK = {hidden: true};
const SAVE = {disabled: false};
globalThis.mcpStep = 'connect';
const INPUT = {get checked(){return BOX.checked;}, set checked(v){BOX.checked=v;}};
globalThis.document = {
  getElementById: id => id === 'mcp-command' ? {get value(){return FIELDS.command;}}
    : id === 'mcp-args' ? {get value(){return FIELDS.args;}}
    : id === 'mcp-approve-box' ? {...BOX, querySelector: () => INPUT,
        get hidden(){return BOX.hidden;}, set hidden(v){BOX.hidden=v;}}
    : id === 'mcp-approved-note' ? NOTE
    : id === 'mcp-transport' ? {value: 'stdio'}
    : id === 'mcp-approve-required' ? ASK
    : id === 'save-mcp' ? SAVE : null,
  querySelector: () => INPUT,
};
// Typing is what revokes a stale tick, so every edit goes through the handler.
const type = (command, args) => { FIELDS = {command, args}; syncMcpApprovalState(); };
const tick = () => { BOX.checked = true; globalThis.mcpTickedFor = mcpLiveTuple(); };

const GATE = msg => {
  A(SAVE.disabled === !mcpApprovalGranted(), 'D3 gate must track approval: ' + msg);
  A(ASK.hidden === !SAVE.disabled, 'D3 reason must be shown exactly when gated: ' + msg);
};

// A saved server: its stored row proves its owner approved vector A.
globalThis.mcpApprovedCommand = {command: '/bin/A', args: ['-y', 'server']};
globalThis.mcpRendered = {commandText: '/bin/A', argsText: '-y\\nserver',
                          command: '/bin/A', args: ['-y', 'server']};
globalThis.mcpTickedFor = null;
type('/bin/A', '-y\\nserver');
A(mcpApprovalGranted() === true, 'the stored vector must stay approved');
GATE('a stored row needs no fresh tick');

// === THE S0 SEQUENCE: A -> B -> approve B -> C ===
type('/bin/B', '-y\\nserver');
A(mcpApprovalGranted() === false, 'B is not approved yet');
tick();
A(mcpApprovalGranted() === true, 'B is approved once ticked');
type('/bin/C', '-y\\nserver');
A(BOX.checked === false, 'the tick must be revoked when the command changes');
A(mcpApprovalGranted() === false, 'S0: a tick for B must NEVER be sent for C');
GATE('after the command changed under a tick');
// The counterfactual, kept so this test pins the BEHAVIOUR and not merely the
// presence of a function: the shipped-and-broken logic was
// `fd.has('approve_local_code') || mcpCommandUnchanged()`, and the old handler
// left the box ticked once the form had diverged from the stored row — so it
// would have put approve_local_code=true on the wire for /bin/C.
const OLD_LOGIC = (boxStillChecked) => boxStillChecked || mcpCommandUnchanged();
A(OLD_LOGIC(true) === true, 'the old logic did approve C; that is the bug pinned here');
A(mcpApprovalGranted() !== OLD_LOGIC(true), 'the fix must disagree with the old logic here');

// === the longer hop the first fix would also have failed ===
type('/bin/B', '-y\\nserver'); tick();
type('/bin/C', '-y\\nserver'); tick();
type('/bin/D', '-y\\nserver');
A(mcpApprovalGranted() === false, 'S0: a tick for C must NEVER be sent for D');

// changing only the ARGUMENTS revokes just as hard
type('/bin/B', '-y\\nserver'); tick();
type('/bin/B', '-y\\nOTHER');
A(mcpApprovalGranted() === false, 'a tick must not carry to different arguments');
for (const args of ['server\\n-y', '-y', '-y\\nserver\\nextra']) {
  type('/bin/B', '-y\\nserver'); tick(); type('/bin/B', args);
  A(mcpApprovalGranted() === false, 'reorder/drop/add must revoke: ' + args);
}

// returning to a previously approved vector is approved again, by equality
type('/bin/B', '-y\\nserver'); tick();
type('/bin/A', '-y\\nserver');
A(mcpApprovalGranted() === true, 'the stored vector is approved by its own row');
// unticking removes consent outright
type('/bin/B', '-y\\nserver'); tick(); BOX.checked = false;
A(mcpApprovalGranted() === false, 'unticking must withdraw consent');
// a brand-new server (no stored row) is never approved without a tick
globalThis.mcpApprovedCommand = null; globalThis.mcpRendered = null;
globalThis.mcpTickedFor = null; BOX.checked = false;
type('/bin/NEW', '');
A(mcpApprovalGranted() === false, 'a new server must never be pre-approved');

// === S1: an untouched legacy row keeps its exact stored arguments ===
globalThis.mcpApprovedCommand = {command: '/bin/A', args: ['server.py', '']};
globalThis.mcpRendered = {commandText: '/bin/A', argsText: 'server.py\\n',
                          command: '/bin/A', args: ['server.py', '']};
globalThis.mcpTickedFor = null; BOX.checked = false;
FIELDS = {command: '/bin/A', args: 'server.py\\n'};
A(JSON.stringify(mcpLiveTuple().args) === JSON.stringify(['server.py', '']),
  'S1: an untouched empty argument must survive the lossy textarea');
A(mcpApprovalGranted() === true, 'S1: an unchanged legacy row must stay saveable');
globalThis.mcpApprovedCommand = {command: '/bin/A', args: ['  padded  ']};
globalThis.mcpRendered = {commandText: '/bin/A', argsText: '  padded  ',
                          command: '/bin/A', args: ['  padded  ']};
FIELDS = {command: '/bin/A', args: '  padded  '};
A(JSON.stringify(mcpLiveTuple().args) === JSON.stringify(['  padded  ']),
  'S1: whitespace-bearing arguments must survive untouched');
A(mcpApprovalGranted() === true, 'S1: a whitespace argument row must stay saveable');
console.log('ok');
"""
    result = run_node(harness, node)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
