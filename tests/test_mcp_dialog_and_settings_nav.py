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
import subprocess

from crossaudit.console.page import PAGE


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


def test_risk_labels_are_shown_but_never_presented_as_verified():
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
                 "Approved tool names",
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
    result = subprocess.run([node, "-e", harness], text=True, capture_output=True)
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
        '"Select all":"全选"',
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
