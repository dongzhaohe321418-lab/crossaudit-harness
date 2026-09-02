"""The refusal a person meets must be one they can read.

The fail-closed denial from the audit core — a corrupt evidence ledger refuses
to produce a receipt — worked perfectly on the frozen build and was illegible to
a Chinese user. A safety mechanism that functions and cannot be read by its
subject is worse than one that fails loudly: the person proceeds confidently
past a warning they could not understand.

These strings are the least translated in the product, and the reason is
structural: nobody walks the failure paths in another language. Setup is
translated because everyone runs setup. A denial that fires when an evidence
ledger is corrupt is seen by nobody — until it is the only thing between a
person and a forged receipt.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.cli import i18n
from crossaudit.console import page as page_mod

HARNESS = Path(__file__).parent / "harness"
CJK = re.compile(r"[一-鿿]")
SRC = Path(page_mod.__file__).parent.parent
DENIAL_TYPES = {"Denial", "ConfigDenial", "IntegrityDenial", "ProviderDenial"}


def _denial_messages() -> list[tuple[str, int, str]]:
    """Every message handed to a Denial constructor, from the shipped source.

    Interpolated messages are probed with a placeholder standing in for the
    substituted part, because that is the shape a person actually reads.
    """
    found: list[tuple[str, int, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name not in DENIAL_TYPES or not node.args:
                continue
            first = node.args[0]
            rel = str(path.relative_to(SRC))
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.append((rel, node.lineno, first.value))
            elif isinstance(first, ast.JoinedStr):
                rendered = "".join(
                    v.value if isinstance(v, ast.Constant) else "X"
                    for v in first.values)
                found.append((rel, node.lineno, rendered))
    return found


def _translate(values: list[str], tmp_path: Path) -> dict:
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"), str(SRC.parent.parent)],
        capture_output=True, text=True, check=True)
    driver = tmp_path / "zh.js"
    driver.write_text(extracted.stdout + "\nconst V=" + json.dumps(values)
                      + ";\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    out = subprocess.run(["node", str(driver)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_fail_closed_evidence_denial_is_legible_in_chinese(tmp_path):
    """The specific sentence: the audit core's own refusal.

    It carries the verifier's reason after a colon, so it is matched as a
    pattern — an exact entry would never match what a person sees, which is the
    same trap as a fixed string carrying a count.
    """
    sentence = ("evidence ledger cannot be shown to the Auditor: "
                "entry 0 digest mismatch (content tampered)")
    rendered = _translate([sentence], tmp_path)[sentence]

    assert re.search(r"[一-鿿]", rendered), (
        f"the fail-closed denial reaches a Chinese reader in English: {rendered!r}")
    assert "entry 0 digest mismatch" in rendered, (
        "the verifier's own reason was dropped instead of carried through")


def test_the_denial_still_exists_where_the_translation_expects_it():
    """A pattern for a sentence nobody raises is a catalogue entry that rots."""
    routing = (SRC / "broker/routing.py").read_text()
    assert "evidence ledger cannot be shown to the Auditor" in routing, (
        "the denial moved; its catalogue pattern now matches nothing")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_denial_reason_reaches_the_console_in_chinese(tmp_path):
    """The console-driven COUNT, measured at the seam the console now uses.

    It was 52/540 when the console translated a refusal by its text alone
    (`page.py` ZH + ZH_PATTERNS). The server now attaches `reason_zh`, looked
    up by the Denial's own reason (`i18n.denial_zh`, D130 provenance-first),
    and the page prefers it under zh, falling back to the text catalogue. So
    a reason is covered when EITHER seam has Chinese for it, and the residual
    may be at most the two sentences ALLOWED_RESIDUAL explains — never more.

    D10 mutation: drop `reason_zh` from `server._deny` — this stays green
    (the seam is measured, not the wire; see the wire test below). Add one
    `ConfigDenial("anything new")` without an entry — red, naming it.
    """
    messages = _denial_messages()
    assert len(messages) > 400, f"the denial reader has drifted: {len(messages)}"
    distinct = sorted({m for _f, _l, m in messages if m.strip()})
    rendered = _translate(distinct, tmp_path)
    by_text = {m for m in distinct if re.search(r"[一-鿿]", rendered[m])}
    by_seam = {m for m in distinct if i18n.denial_zh(m) is not None}
    covered = by_text | by_seam
    residual = set(distinct) - covered
    assert residual <= set(ALLOWED_RESIDUAL), (
        f"refusals the console shows a Chinese reader in English: "
        f"{sorted(residual - set(ALLOWED_RESIDUAL))!r}")
    # The two seams are reported separately so the number keeps its unit.
    assert len(by_text) >= 52 and len(covered) >= len(distinct) - len(ALLOWED_RESIDUAL)


def test_the_console_serves_the_refusal_in_both_languages_on_the_wire():
    """Through the shipped server: a structured refusal carries `reason_zh`
    beside `reason`, and `reason` is byte-identical to what it always was.

    D10 mutation: drop the `reason_zh` line in `server._deny` — red here.
    """
    import threading
    import urllib.error
    import urllib.request

    sys.path.insert(0, str(HARNESS))
    import enumerate_console_strings as harness
    from crossaudit.console.server import serve

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "p"
        root.mkdir()
        cfg = harness.project(root)
        url, httpd = serve(cfg, port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            request = urllib.request.Request(
                url.replace("/?t=", "/api/projects/open?t="),
                data=b'{"root":"/nope"}', method="POST",
                headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raise AssertionError(f"expected a refusal, got {response.status}")
            except urllib.error.HTTPError as denied:
                body = json.loads(denied.read().decode("utf-8"))
        finally:
            httpd.shutdown()
            httpd.server_close()
    assert body.get("denied") is True and body.get("reason"), body
    assert not CJK.search(body["reason"]), "the English reason must not change"
    assert CJK.search(body.get("reason_zh", "")), body
    assert body["reason_zh"] == i18n.denial_zh(body["reason"]), (
        "reason_zh must be the table's answer for THIS reason, nothing else")


def test_the_page_prefers_the_served_chinese_and_falls_back_to_its_catalogue():
    """MARKUP ONLY: the page reads `reason_zh` under zh at both fetch seams
    and still renders `reason` when the body has none."""
    page = Path(page_mod.__file__).read_text()
    assert "(currentLocale==='zh'&&data.reason_zh)||data.reason||''" in page
    assert page.count("denialText(data)") == 3  # the definition and both seams


# ----------------------------------------------------------- the CLI seam
# The console serves a refusal with `reason_zh` beside `reason` (server._deny,
# tests above); the CLI prints it on stderr as `DENIED (kind): reason`, where
# the macOS shell parses the prefix and a person reads the rest. `cli/denials_zh.py` is the Chinese for that
# rest, keyed by the English reason, and these tests keep it complete, honest
# and free of rot.
from crossaudit.cli.denials_zh import ENTRIES  # noqa: E402

#: Reasons deliberately left without an entry, each with the reason why. Keys
#: are the rendering the static reader produces (`X` per interpolated part).
ALLOWED_RESIDUAL = {
    "X: X": (
        "receipt/build.py wraps EVIDENCE_BROKEN_REASON, a constant; the reader "
        "sees only the join. The sentence a person meets is covered by its own "
        "template (see RAISED_BEHIND_THE_READER)."),
    "X\n\n  underlying: X": (
        "providers/base.py wraps tls_advice(), a paragraph composed at runtime "
        "from this machine's certificate paths. Translating the two-word frame "
        "around an English paragraph would be a half-translation, which reads "
        "as done and is not."),
}

#: Entries whose English the static reader cannot see, because the sentence is
#: assembled from a constant or a variable. Each is checked against the source
#: below, so an entry for a sentence nobody raises still fails.
RAISED_BEHIND_THE_READER = {
    "{} has staged changes; commit or restore them before pairing":
        ("cli/pair.py", ['has {where}changes', '"staged "']),
    "{} has changes; commit or restore them before pairing":
        ("cli/pair.py", ['has {where}changes', 'else ""']),
}


def _distinct_denials() -> list[str]:
    return sorted({m for _f, _l, m in _denial_messages() if m.strip()})


def test_every_denial_reason_has_chinese_at_the_cli_seam():
    """The COUNT, pinned at its residual rather than at its coverage.

    D130 measured 479 refusals with no Chinese. The gate is the other way
    round now: every reason the four Denial constructors raise has an entry,
    except the two listed in ALLOWED_RESIDUAL with their reasons. It asserts
    equality, not a ceiling: a residual that disappears must be removed from
    the list too, so the list never carries padding.

    D10 mutation: add one `ConfigDenial("anything new")` anywhere in `src/`
    without an entry, and this goes red naming the sentence. Remove an entry
    from the table, same result. Reword a raised sentence so its entry no
    longer matches, same result — and the orphan test below names the entry.
    """
    distinct = _distinct_denials()
    assert len(distinct) > 500, f"the denial reader has drifted: {len(distinct)}"
    residual = {m for m in distinct if i18n.denial_zh(m) is None}
    assert residual == set(ALLOWED_RESIDUAL), (
        f"refusals a Chinese reader meets in English: "
        f"{sorted(residual - set(ALLOWED_RESIDUAL))!r}; residuals listed but no "
        f"longer raised: {sorted(set(ALLOWED_RESIDUAL) - residual)!r}")


def test_every_denial_entry_translates_itself_and_carries_its_slots():
    """Each entry, driven through the shipped lookup with `X` in every slot.

    Three things at once: the result is Chinese (an entry copied across in
    English would pass the count); every interpolated part survives (a
    translation that drops the path or the sha says less than the English);
    and the entry that answered is THIS one — a more generic template placed
    earlier would otherwise swallow a specific sentence into a half-translated
    one, the exact defect the console's ZH_PATTERNS comment records.
    """
    for english, chinese in ENTRIES:
        slots = english.count("{}")
        rendered = i18n.denial_zh(english.replace("{}", "X"))
        assert rendered is not None, f"entry does not match itself: {english!r}"
        assert CJK.search(rendered), f"copied, not translated: {english!r}"
        assert rendered.count("X") >= slots, (
            f"a slot was dropped: {english!r} -> {rendered!r}")
        expected = (chinese.replace("{}", "X") if "{}" in chinese
                    else chinese.format(*["X"] * slots))
        assert rendered == expected, (
            f"{english!r} was answered by a different entry: {rendered!r}")


def test_no_denial_entry_is_for_a_sentence_nobody_raises():
    """A catalogue entry for a sentence nobody raises is an entry that rots.

    Every English key must be raised by a Denial constructor somewhere in
    `src/` — as the static reader sees it, or, for the few assembled from a
    constant or a variable, as the source text proves.
    """
    from crossaudit.receipt.build import EVIDENCE_BROKEN_REASON

    raised = set(_distinct_denials())
    orphans = []
    for english, _zh in ENTRIES:
        if english.replace("{}", "X") in raised:
            continue
        if english in RAISED_BEHIND_THE_READER:
            rel, needles = RAISED_BEHIND_THE_READER[english]
            source = (SRC / rel).read_text()
            assert all(n in source for n in needles), (
                f"{english!r} is no longer assembled the way its entry assumes")
            continue
        if english.startswith(EVIDENCE_BROKEN_REASON + ": "):
            continue
        orphans.append(english)
    assert orphans == [], f"entries for sentences nobody raises: {orphans!r}"
    seen = [e for e, _ in ENTRIES]
    assert len(seen) == len(set(seen)), "duplicate English keys in the table"


def test_the_cli_denied_line_speaks_chinese_after_its_parsed_prefix(
        monkeypatch, capsys, tmp_path):
    """The line a person meets on stderr, both languages, through `main()`.

    `DENIED (kind): ` stays Latin because CrossAuditApp.swift parses it
    (`hasPrefix("DENIED (")`, then the text after `): `); the sentence after
    it is served in the language the command was asked for. In English the
    line is byte-identical to what it always was.
    """
    import argparse

    from crossaudit.cli import main as main_mod
    from crossaudit.errors import ConfigDenial

    def raising(reason, lang):
        def func(args):
            i18n.set_language(lang)
            i18n.reset_fallbacks()
            raise ConfigDenial(reason)
        return func

    def run(reason, lang):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="verb")
        p = sub.add_parser("boom")
        p.set_defaults(func=raising(reason, lang))
        monkeypatch.setattr(main_mod, "build_parser", lambda: parser)
        try:
            code = main_mod.main(["boom"])
        finally:
            i18n.set_language("en")
        captured = capsys.readouterr()
        return code, captured.err, captured.out

    repo = str(tmp_path / "proj")
    code, err, out = run(f"{repo} is not a git repository", "zh")
    assert code == ConfigDenial.exit_code
    assert err.startswith("DENIED (config): "), err
    assert f"{repo} 不是 git 仓库" in err, err
    assert "is not a git repository" not in err
    assert "[i18n]" not in out + err, "a translated refusal was counted as a fallback"

    code, err, out = run(f"{repo} is not a git repository", "en")
    assert err == f"DENIED (config): {repo} is not a git repository\n"
    assert out == ""

    # A reason with no entry is served in English, MARKED and COUNTED — the
    # same contract as `t()`, so the gap is visible in a screenshot and in CI.
    code, err, out = run("a sentence with no entry", "zh")
    assert "DENIED (config): [en] a sentence with no entry" in err
    assert "[i18n] 1 string(s) fell back to English" in out
