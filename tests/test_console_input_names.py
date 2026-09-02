"""Every text field a person can type into has a name a screen reader can say.

Restart handbook: the composer — the one control every task begins in — had no
accessible name while the search box beside it did. A placeholder is not a
name: it vanishes on the first keystroke and several engines do not expose it
as one. So the check is structural and covers every `<input>` and `<textarea>`
in `page.py`, static markup and the ones JavaScript builds alike, rather than
the one field somebody noticed.

MARKUP ONLY. Asserts on the shipped source; nothing here reaches the native
accessibility tree (see test_console_translation_boundary.NATIVE_AX_TREE_NOT_COVERED).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from crossaudit.console.page import PAGE

NAME_ATTRIBUTES = ("aria-label", "aria-labelledby", "title")


class _Fields(HTMLParser):
    """Each input/textarea in the static markup, with what could name it."""

    def __init__(self) -> None:
        super().__init__()
        self.label_depth = 0
        self.label_for: set[str] = set()
        self.fields: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label":
            self.label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag in ("input", "textarea"):
            self.fields.append({"tag": tag, "attrs": a,
                                "in_label": self.label_depth > 0})

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1


def _static_fields() -> tuple[list[dict], set[str]]:
    markup = re.sub(r"<script>.*?</script>", "", PAGE, flags=re.S)
    parser = _Fields()
    parser.feed(markup)
    return parser.fields, parser.label_for


def _exposed(attrs: dict) -> bool:
    return attrs.get("type") != "hidden" and "hidden" not in attrs


def _named(field: dict, label_for: set[str]) -> bool:
    a = field["attrs"]
    if any(a.get(name) for name in NAME_ATTRIBUTES):
        return True
    return field["in_label"] or (a.get("id") in label_for)


def test_every_static_field_has_an_accessible_name():
    fields, label_for = _static_fields()
    assert len(fields) > 30, f"the field reader has drifted: {len(fields)}"
    unnamed = [f["attrs"].get("id") or f["attrs"].get("name") or f["tag"]
               for f in fields if _exposed(f["attrs"]) and not _named(f, label_for)]
    assert unnamed == [], f"these fields have no accessible name: {unnamed}"


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
        for match in re.finditer(r"<(input|textarea)\b([^>]*)>", line):
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
