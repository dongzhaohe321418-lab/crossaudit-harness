"""Access and polish on the MCP surface: design findings D4, D5, D7-D11.

These are the "small" ones, and D5 of the task ledger is why they are here at
all: an engineering S3 a person meets in the first two minutes outranks an S1
nobody reaches. A dialog a screen-reader user cannot follow, a risk badge that
fails AA, and a view with no tab in its own nav are all first-two-minutes
problems.
"""
import re

from crossaudit.console.page import PAGE


# ------------------------------------------------------------------------- D4
def test_both_decision_points_are_announced_and_reachable():
    """#mcp-message in the tools view already had role="alert"; the dialog's own
    error region, its success banner and its running count did not."""
    assert '<div class="wizard-error" id="mcp-error" role="alert" tabindex="-1"></div>' in PAGE
    assert '<div class="mcp-connected" id="mcp-connected" role="status" aria-live="polite">' in PAGE
    assert '<small id="mcp-approve-count" aria-live="polite"></small>' in PAGE
    # The disabled Generator-access box points at the sentence explaining why.
    assert 'id="mcp-enabled" aria-describedby="mcp-enable-note"' in PAGE


def test_a_denial_with_no_field_to_blame_still_moves_focus_to_the_reason():
    assert "catch(e){computeError('mcp-error',e);document.getElementById('mcp-error').focus();}" in PAGE


# ------------------------------------------------------------------------- D5
def test_the_two_safety_strings_are_darkened_in_light_theme_only():
    """Measured composited, not assumed: "May change data" was 4.03:1 and the
    consent heading 3.96:1 against their own 10% washes. Dark was already 5.18 /
    6.76 and is deliberately not touched by these rules."""
    assert ':root[data-theme="light"] .mcp-risk.destructive{color:#A82F26}' in PAGE
    assert ':root[data-theme="light"] .hpc-confirm b{color:#7F540A}' in PAGE
    # The Connected heading measured 4.16:1 on the same surface; same fix.
    assert (':root[data-theme="light"] .mcp-connected b,\n'
            ':root[data-theme="light"] .mcp-approved b{color:#14684A}') in PAGE
    # No dark-theme override was introduced for any of them.
    for selector in (".mcp-risk.destructive", ".hpc-confirm b", ".mcp-connected b"):
        assert ':root[data-theme="dark"] ' + selector not in PAGE


def test_the_rule_a_person_must_satisfy_before_typing_is_legible():
    """The D1 field help and the Arguments help are .field-help, whose --text-3
    measured 2.72:1 light / 3.59:1 dark — the least readable text on the step,
    which is a poor place for the one sentence that has to be read first."""
    assert ".mcp-wizard .field-help{color:var(--text-2)}" in PAGE


# ------------------------------------------------------------------------- D7
def test_a_consent_you_cannot_give_yet_does_not_look_like_one_you_can():
    assert ".hpc-confirm.awaiting{background:var(--surface-2);" in PAGE
    # ...including in light theme, where the darkened heading rule would
    # otherwise out-specify it.
    assert (':root .hpc-confirm.awaiting b,:root[data-theme="light"] '
            '.hpc-confirm.awaiting b{color:var(--text-2)}') in PAGE
    assert "if(consent)consent.classList.toggle('awaiting',none);" in PAGE


# ------------------------------------------------------------------------- D8
def test_the_heading_names_what_is_actually_on_the_step():
    """"Approved tool names" named the free-text field the wizard replaced."""
    assert "Tools this project may use" in PAGE
    assert '"Tools this project may use":"本项目可以使用的工具"' in PAGE
    assert "Approved tool names" not in PAGE


# ------------------------------------------------------------------------- D9
def test_the_footer_note_stops_squeezing_the_buttons_at_narrow_widths():
    assert ".mcp-wizard>.wizard-foot>button{white-space:nowrap;flex:none}" in PAGE
    assert ".mcp-wizard>.wizard-foot{flex-wrap:wrap}" in PAGE
    assert ".mcp-wizard>.wizard-foot>span{flex-basis:100%;max-width:none;margin:0 0 9px}" in PAGE
    assert ".mcp-wizard>.wizard-foot>button:nth-of-type(1){margin-left:auto}" in PAGE


# ------------------------------------------------------------------------ D10
def test_every_panel_view_has_a_tab_and_every_tab_has_a_view():
    """Tools & Skills was in PANEL_TITLES, in openPanelTab's allowlist and had a
    nav icon, but no button — so the panel showed a view absent from its own nav
    and nothing was highlighted while you were on it."""
    nav = PAGE.split('class="panel-tabs"')[1].split("</nav>")[0]
    tabs = re.findall(r'data-view="([a-z]+)"', nav)
    titles = set(re.findall(r"(\w+):'", PAGE.split("const PANEL_TITLES={")[1].split("};")[0]))
    allowed = set(re.findall(
        r"'([a-z]+)'", PAGE.split("function openPanelTab(view){")[1].split("];")[0]))
    assert "tools" in tabs
    assert len(tabs) == len(set(tabs))
    assert set(tabs) == titles == allowed, (sorted(tabs), sorted(titles), sorted(allowed))
    # The icon that already existed now belongs to a control that exists.
    assert '.nav-item[data-view="tools"] .nav-icon{--ui-icon:' in PAGE
    assert '"Tools":"工具"' in PAGE


def test_the_eighth_tab_does_not_squeeze_the_labels_into_each_other():
    """An equal-share basis gave each tab 36px at a 318px panel; "Governed"
    needs 52 and "Compute" 49, so the labels bled together (already true at
    seven tabs, worse at eight). Basis auto plus wrapping means a tab is never
    narrower than its own label.

    The rows also start at the same edge. Centred, row two floated in the middle
    of the strip aligned to nothing above it, which reads as leftovers rather
    than as a grid — and English wraps at EVERY desktop width, so that is the
    permanent layout and not an edge case.
    """
    assert (".panel-tabs{display:flex;flex-wrap:wrap;"
            "gap:2px;padding:0 var(--sp-2) var(--sp-2);flex:none}") in PAGE
    assert "justify-content:center" not in PAGE.split(".panel-tabs{")[1].split("}")[0]
    assert ".panel-tabs .nav-item{flex:0 1 auto;min-width:0;height:40px;padding:0 7px;" in PAGE


# ------------------------------------------------------------------------ D11
def test_the_saved_server_list_uses_the_same_words_as_the_dialog():
    """The meaning of ◉ / ⚠ lived only in a title attribute: unavailable on
    touch, unreliable for a screen reader."""
    assert "note.destructiveHint?' ⚠':note.readOnlyHint?' ◉':''" not in PAGE
    tools_view = PAGE.split("function toolsView(d){")[1].split("\nfunction ")[0]
    for badge in ('<i class="mcp-risk destructive">May change data</i>',
                  '<i class="mcp-risk readonly">Read-only</i>',
                  '<i class="mcp-risk unlabelled">Not labelled by the server</i>'):
        assert badge in tools_view, badge
    assert ".mcp-tool .mcp-risk{margin-left:2px;padding:1px 6px;font-size:10px}" in PAGE
