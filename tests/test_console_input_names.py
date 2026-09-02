"""Every field a person can type into, pick from, or press has a name a
screen reader can say.

Restart handbook: the composer — the one control every task begins in — had no
accessible name while the search box beside it did. A placeholder is not a
name: it vanishes on the first keystroke and several engines do not expose it
as one. So the check is structural and covers every `<input>` and `<textarea>`
in `page.py`, static markup and the ones JavaScript builds alike, rather than
the one field somebody noticed — and `<select>` (options do not name it) and
icon-only `<button>`s, which the review found the first version could not see.

MARKUP ONLY. Asserts on the shipped source; nothing here reaches the native
accessibility tree (see test_console_translation_boundary.NATIVE_AX_TREE_NOT_COVERED).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from crossaudit.console.page import PAGE

NAME_ATTRIBUTES = ("aria-label", "aria-labelledby", "title")


FIELD_TAGS = ("input", "textarea", "select")


class _Fields(HTMLParser):
    """Each input/textarea/select and button in the static markup, with what
    could name it. A button is named by its visible text unless that text is
    aria-hidden (a glyph), in which case it needs an explicit name."""

    def __init__(self) -> None:
        super().__init__()
        self.label_depth = 0
        self.label_for: set[str] = set()
        self.fields: list[dict] = []
        self.buttons: list[dict] = []
        self._open_button: dict | None = None
        self._hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label":
            self.label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag in FIELD_TAGS:
            self.fields.append({"tag": tag, "attrs": a,
                                "in_label": self.label_depth > 0})
        if tag == "button":
            self._open_button = {"attrs": a, "text": ""}
            self.buttons.append(self._open_button)
        elif self._open_button is not None and a.get("aria-hidden") == "true":
            self._hidden_depth += 1

    def handle_data(self, data):
        if self._open_button is not None and not self._hidden_depth:
            self._open_button["text"] += data

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1
        if tag == "button":
            self._open_button = None
            self._hidden_depth = 0
        elif self._open_button is not None and self._hidden_depth and tag in ("span", "i", "b"):
            self._hidden_depth -= 1


def _static_fields() -> tuple[list[dict], set[str]]:
    return _parse().fields, _parse().label_for


def _parse() -> _Fields:
    markup = re.sub(r"<script>.*?</script>", "", PAGE, flags=re.S)
    parser = _Fields()
    parser.feed(markup)
    return parser


def _exposed(attrs: dict) -> bool:
    return attrs.get("type") != "hidden" and "hidden" not in attrs


def _named(field: dict, label_for: set[str]) -> bool:
    a = field["attrs"]
    if any(a.get(name) for name in NAME_ATTRIBUTES):
        return True
    return field["in_label"] or (a.get("id") in label_for)


def test_every_static_field_has_an_accessible_name():
    fields, label_for = _static_fields()
    assert len(fields) > 50, f"the field reader has drifted: {len(fields)}"
    assert any(f["tag"] == "select" for f in fields), "selects are not being read"
    unnamed = [f["attrs"].get("id") or f["attrs"].get("name") or f["tag"]
               for f in fields if _exposed(f["attrs"]) and not _named(f, label_for)]
    assert unnamed == [], f"these fields have no accessible name: {unnamed}"


def test_every_static_button_has_a_name_that_is_not_only_a_glyph():
    buttons = _parse().buttons
    assert len(buttons) > 40, f"the button reader has drifted: {len(buttons)}"
    unnamed = [b["attrs"].get("id") or b["attrs"].get("class") or "button"
               for b in buttons
               if not any(b["attrs"].get(n) for n in NAME_ATTRIBUTES)
               and not re.search(r"[A-Za-z一-鿿]", b["text"])]
    assert unnamed == [], f"these buttons expose no name, only a glyph: {unnamed}"


def test_the_composer_is_named_in_both_languages():
    """The one that was missing, pinned by name; the ZH entry rides the
    attribute translator, so the label must be a catalogue key."""
    match = re.search(r'<textarea id="say"[^>]*>', PAGE)
    assert match and 'aria-label="Your task or message"' in match.group(0)
    assert '"Your task or message":"你的任务或消息"' in PAGE


def test_every_field_javascript_builds_has_an_accessible_name():
    """The templates are string concatenations, so the label ancestry is read
    from the same expression: a `<label` opened before the field on that line
    and not closed before it names the field."""
    script = PAGE.split("<script>")[1].split("</script>")[0]
    unnamed = []
    for line in script.splitlines():
        for match in re.finditer(r"<(input|textarea|select)\b([^>]*)>", line):
            attrs = match.group(2)
            if 'type="hidden"' in attrs:
                continue
            if any(f"{name}=" in attrs for name in NAME_ATTRIBUTES):
                continue
            before = line[:match.start()]
            if before.count("<label") > before.count("</label>"):
                continue
            unnamed.append(match.group(0)[:80])
    assert unnamed == [], f"JavaScript builds these fields without a name: {unnamed}"
    assert 'data-fallback-vendor aria-label="Provider"' in script


def test_every_button_javascript_builds_has_a_name_or_visible_text():
    """Same expression-level reading for buttons: named by an attribute, or
    by text between the tags that is not itself aria-hidden."""
    script = PAGE.split("<script>")[1].split("</script>")[0]
    unnamed = []
    for match in re.finditer(r"<button\b([^>]*)>(.*?)</button>", script, flags=re.S):
        attrs, inner = match.group(1), match.group(2)
        if any(f"{name}=" in attrs for name in NAME_ATTRIBUTES) or "+aria(" in attrs:
            continue
        if "'+" in inner or "+'" in inner:
            continue  # the label is an expression (esc(repair.label), a count)
        visible = re.sub(r"<[^>]*aria-hidden=\"true\"[^>]*>.*?</[a-z]+>", "", inner, flags=re.S)
        visible = re.sub(r"<[^>]+>", "", visible)
        visible = re.sub(r"'\s*\+\s*[^+]*?\+\s*'", " ", visible)
        if not re.search(r"[A-Za-z一-鿿]", visible):
            unnamed.append(match.group(0)[:100])
    assert unnamed == [], f"JavaScript builds these buttons with no name: {unnamed}"
