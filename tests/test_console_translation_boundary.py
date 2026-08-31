"""Every string a person can read has a Chinese form — including the two kinds
nobody was looking at.

`aria-label` is user-facing text that no sighted reviewer reads and no
visible-text scanner sees. Server-side literals are authored in Python, so
nobody writing them passes through `page.py` where the catalogue lives. Both
are boundaries rather than oversights, and both are asserted here by driving
the SHIPPED translator rather than by reading the source.
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.console import page as page_mod

HARNESS = Path(__file__).parent / "harness"
PAGE = Path(page_mod.__file__)

#: Set explicitly by `applyLocale`, which flips it to 「切换到英文」 when the
#: locale is Chinese. A ZH entry would fight that, so it is exempt BY NAME and
#: the exemption is checked below rather than trusted.
ARIA_EXEMPT = {"Switch to Chinese"}

#: Recorded so the stronger check is not forgotten by anyone reading a green
#: file: the DOM and native accessibility trees DISAGREE on this page
#: (`unnamed=0` vs `unnamed=1`), and a screen reader uses the native one.
#: Nothing in this module can reach it.
NATIVE_AX_TREE_NOT_COVERED = (
    "a name in the DOM is not a name in the accessibility tree; the native-tree "
    "check belongs to the browser/accessibility harness")

#: Fields the console renders to a person as prose.
USER_FACING_FIELDS = {"title", "label", "detail", "summary", "message",
                      "reason", "note", "hint"}


def _static_aria_labels() -> list[str]:
    source = PAGE.read_text()
    return sorted({label for label in re.findall(r'aria-label="([^"]*)"', source)
                   if label and "'" not in label and "+" not in label
                   and "\n" not in label})


def _server_side_literals() -> list[tuple[str, int, str]]:
    """Literals assigned to user-facing fields anywhere in `console/*.py`.

    Derived by walking the modules, not from a list: a new server-side string
    lands in this sweep because it is written, not because someone remembered.

    THE PREDICATE, because a count without one is not a count. This returns
    **occurrences, not distinct values** — one string written at two call sites
    is two rows. An independent reviewer read 26 from this helper while the
    report said 25, and neither was wrong: 26 call sites, 25 distinct strings,
    the difference being `"Project history"` at `chats.py:74` and `chats.py:362`.

    Both units are real and they answer the two halves of the work: **25 is the
    number of catalogue entries** to write, **26 is the number of code sites** to
    key. Report which one you mean.

    Counted: string constants of two or more words, appearing either as a value
    in a dict literal under a key in USER_FACING_FIELDS, or anywhere inside an
    assignment whose target is a name in that set, in `console/*.py` except
    `page.py`. Static AST only — nothing here is execution-scoped, so it cannot
    see a literal passed straight to a call or returned inline.
    """
    found: list[tuple[str, int, str]] = []
    for path in sorted((PAGE.parent).glob("*.py")):
        if path.name == "page.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant)
                            and key.value in USER_FACING_FIELDS
                            and isinstance(value, ast.Constant)
                            and isinstance(value.value, str)
                            and len(value.value.split()) > 1):
                        found.append((path.name, node.lineno, value.value))
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not any(n in USER_FACING_FIELDS for n in names):
                    continue
                for sub in ast.walk(node.value):
                    if (isinstance(sub, ast.Constant)
                            and isinstance(sub.value, str)
                            and len(sub.value.split()) > 1):
                        found.append((path.name, node.lineno, sub.value))
    return found


def _translate(values: list[str], tmp_path: Path) -> dict:
    """Run each value through the SHIPPED zhValue() under node."""
    import json

    shipped = tmp_path / "zh.js"
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"), str(PAGE.parent.parent.parent.parent)],
        capture_output=True, text=True, check=True)
    driver = (extracted.stdout
              + "\nconst V=" + json.dumps(values) + ";"
              + "\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    shipped.write_text(driver)
    out = subprocess.run(["node", str(shipped)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


def _is_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_static_aria_label_reaches_a_chinese_reader(tmp_path):
    """The mechanism already walked `aria-label`; the ENTRIES were missing.

    So this drives the shipped translator over every static label rather than
    scanning the source for CJK — the source is English by construction and
    scanning it measures the wrong thing.

    WHAT THIS DOES NOT ESTABLISH, and it is the check that actually matters:
    a screen reader reads the NATIVE ACCESSIBILITY TREE, not the DOM. The
    composer already measures `unnamed=0` in the DOM tree and `unnamed=1` in
    the native tree — the engines disagree, so a DOM-level pass answers a
    question nobody asked. This test sits one level lower still: it asserts the
    label STRINGS have Chinese forms. It cannot see whether a control reaches
    the AX tree with a name at all, and it must not be read as saying so. That
    check needs the native tree and belongs with the accessibility harness.
    """
    labels = _static_aria_labels()
    assert len(labels) > 50, f"the label reader has drifted: {len(labels)}"
    rendered = _translate([l.replace("&amp;", "&") for l in labels], tmp_path)

    untranslated = sorted(
        label for label in labels
        if label not in ARIA_EXEMPT
        and not _is_chinese(rendered[label.replace("&amp;", "&")]))
    assert untranslated == [], (
        f"a Chinese screen-reader user meets these control labels in English: "
        f"{untranslated}")


def test_the_aria_exemption_is_real_and_not_a_hiding_place():
    """An exemption that stops being true is pre-approved English."""
    source = PAGE.read_text()
    for exempt in ARIA_EXEMPT:
        assert exempt in source, f"{exempt!r} is exempt but no longer exists"
    assert "'切换到英文'" in source, (
        "the locale toggle no longer sets its own Chinese label, so its "
        "exemption is now just an untranslated string")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_server_side_user_facing_literal_reaches_a_chinese_reader(tmp_path):
    """The second boundary: strings authored in Python, rendered by the page.

    One leak found by observation ("Project history") turned out to be 25
    literals across five modules — a boundary, not an oversight.
    """
    literals = _server_side_literals()
    assert len(literals) >= 20, f"the sweep has drifted: {len(literals)}"
    # Both units, pinned, so the two numbers can never diverge unexplained again.
    values = sorted({value for _f, _l, value in literals})
    assert (len(literals), len(values)) == (26, 25), (
        f"the sweep now reports {len(literals)} occurrences / {len(values)} "
        f"distinct; it was 26/25. Say which unit changed and why — a count "
        f"without its unit is what made 25 and 26 look like a disagreement.")
    # A literal ending in ": " is a PREFIX: the person sees it with a reason
    # appended, so it is translated by pattern and testing the bare form would
    # ask the wrong question.
    probes = {v: (v + "reason") if v.rstrip().endswith(":") else v for v in values}
    rendered = _translate(sorted(set(probes.values())), tmp_path)

    untranslated = sorted(v for v in values if not _is_chinese(rendered[probes[v]]))
    assert untranslated == [], (
        f"{len(untranslated)} server-side strings reach a Chinese reader in "
        f"English: {untranslated[:6]}")


# =============== the third population: text built inside JS templates =====
def _js_built_phrases() -> set[str]:
    """English rendered between tags by JS string concatenation.

    A different population from the server-side one, and the distinction
    matters: the MutationObserver at `localizeTree(node)` DOES reach these once
    they are inserted, so the mechanism was never the gap here — the catalogue
    entry was. `Files produced` is one of these, not a server-side literal.
    """
    script = PAGE.read_text().split("<script>")[1].split("</script>")[0]
    found = set()
    for match in re.finditer(r">([A-Z][A-Za-z][^<>'\"{}+]{3,60})<", script):
        text = match.group(1).strip()
        if text and len(text.split()) >= 2 and not text.startswith("http"):
            found.add(text)
    return found


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_text_built_in_javascript_reaches_a_chinese_reader(tmp_path):
    """`Files produced` was found by a sweep after `Project history`.

    Two leaks from two instruments is a category, so this counts the category
    rather than fixing the instance: every phrase JS renders between tags must
    come back Chinese from the shipped translator.
    """
    phrases = sorted(_js_built_phrases())
    assert len(phrases) > 100, f"the phrase reader has drifted: {len(phrases)}"
    rendered = _translate(phrases, tmp_path)
    untranslated = sorted(p for p in phrases if not _is_chinese(rendered[p]))
    assert untranslated == [], (
        f"{len(untranslated)} phrases built in JavaScript reach a Chinese "
        f"reader in English: {untranslated}")


def test_dynamic_content_is_relocalised_after_it_is_inserted():
    """The entry is only half of it: inserted nodes must be walked too.

    If the observer stops calling `localizeTree`, every phrase above renders in
    English no matter how complete the catalogue is — the mechanism and the
    entries are two separate failure modes and this file asserts both.
    """
    source = PAGE.read_text()
    assert "localizeTree(node)" in source, (
        "nothing re-localises dynamically inserted content")
    assert "MutationObserver" in source
