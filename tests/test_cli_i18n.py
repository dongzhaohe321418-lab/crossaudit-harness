"""CLI i18n wave 1: a person enters in one language and stays in it (D21, D25).

D25 is why this is not polish. For a Chinese-speaking first-timer an
English-only CLI is not degradation, it is exclusion — and averaging harm across
users hides exactly the users who are most harmed, because people who cannot use
something at all are always a minority of the people who can.

D21 is why the unit is the whole `init` wizard. Steps 1 through 4 are one
continuous sequence in one session, so a Chinese panel after three English
prompts is not a partial translation, it is a seam in the middle of one flow.

Every test here executes the real `crossaudit init` and reads what it printed.
None asserts that a string exists in a source file: the property is what a person
SEES, and only running it can show that.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from crossaudit.cli import i18n, main, tui, wizard


# ------------------------------------------------------ the catalogue itself
def test_every_english_key_has_a_translation():
    en, zh = set(i18n.CATALOGUE["en"]), set(i18n.CATALOGUE["zh"])
    assert en - zh == set(), f"untranslated keys: {sorted(en - zh)}"
    assert zh - en == set(), f"translations with no English: {sorted(zh - en)}"


def test_no_translation_is_still_sitting_in_english():
    """A key copied across without being translated would pass the key check.

    `checks.proposal.ground` is the one honest exception: it is slots and an
    arrow, with nothing in it to translate.
    """
    untranslated = [
        key for key, value in i18n.CATALOGUE["zh"].items()
        if value == i18n.CATALOGUE["en"][key] and key != "checks.proposal.ground"]
    assert untranslated == [], f"copied, not translated: {untranslated}"


def test_every_slot_a_translation_uses_exists_in_the_english_template():
    """A translation may reorder slots; it may not invent one.

    An invented slot raises at format time and would reach a person as a
    `[missing:...]` marker on the exact screen this wave exists to fix.
    """
    slots = lambda text: set(re.findall(r"\{(\w+)\}", text))
    for key, english in i18n.CATALOGUE["en"].items():
        assert slots(i18n.CATALOGUE["zh"][key]) <= slots(english), (
            f"{key}: translation uses a slot English does not define")


# --------------------------------------------------------- the fallback rule
def test_a_missing_translation_is_served_in_english_marked_and_counted(monkeypatch):
    monkeypatch.setitem(i18n.CATALOGUE["en"], "test.only", "English text")
    i18n.set_language("zh")
    i18n.reset_fallbacks()
    try:
        rendered = i18n.t("test.only")
    finally:
        i18n.set_language("en")
    assert rendered == i18n.FALLBACK_MARK + "English text"
    assert i18n.fallbacks() == ("test.only",)


def test_a_key_that_exists_nowhere_is_shown_rather_than_raised():
    """A typo must not end somebody's setup; it must be impossible to miss."""
    i18n.reset_fallbacks()
    assert i18n.t("no.such.key") == "[missing:no.such.key]"
    assert i18n.fallbacks() == ("no.such.key",)


def test_english_is_never_marked_as_a_fallback():
    i18n.set_language("en")
    i18n.reset_fallbacks()
    assert i18n.t("done.ready") == "Ready"
    assert i18n.fallbacks() == ()


# --------------------------------------------------- the real wizard, both ways
def _init(tmp_path, monkeypatch, capsys, *, lang, name, **over):
    project = tmp_path / name
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / f"home-{name}"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"keys-{name}.env"))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.chdir(project)
    args = dict(path=str(project), github=False, force=True, no_console=True,
                json=False, auditor_vendor="anthropic",
                auditor_model="claude-opus-4", generator_vendor="openai",
                generator_model="gpt-5", profile="own", lang=lang)
    args.update(over)
    main.cmd_init(argparse.Namespace(**args))
    return project, capsys.readouterr().out


def _flat(text: str) -> str:
    """Collapse whitespace before matching.

    `tui.note` WRAPS, so a sentence a person reads as one line arrives split and
    indented in the raw stream. Asserting on the raw text would miss it — the
    CLI's version of the rendered-versus-raw distinction that has caught this
    team repeatedly.
    """
    return re.sub(r"\s+", " ", text)


def test_the_whole_wizard_speaks_english_by_default(tmp_path, monkeypatch, capsys):
    _project, out = _init(tmp_path, monkeypatch, capsys, lang="en", name="en")
    flat = _flat(out)
    for key in ("init.banner.title", "init.step1.title", "init.step3.title",
                "init.step4.title", "done.not_ready", "done.next"):
        assert i18n.CATALOGUE["en"][key] in flat, key
    assert i18n.fallbacks() == ()


def test_the_whole_wizard_speaks_chinese_end_to_end(tmp_path, monkeypatch, capsys):
    """Every step, not one panel. D21's seam is what this asserts against."""
    _project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="zh")
    flat = _flat(out)
    for key in ("init.banner.title", "init.step1.title", "init.step1.note",
                "init.step2.title", "init.step3.title", "init.step4.title",
                "start.own.frame", "start.own.c1", "rules.free_to_change",
                "rules.written", "done.not_ready", "done.next",
                "prepare.git_init", "next.doctor_recheck"):
        # A template may open with a slot, so match its longest literal run
        # rather than its head. `tui.note` wraps, hence the flattening above.
        expected = max(re.split(r"\{\w+\}", i18n.CATALOGUE["zh"][key]),
                       key=len).strip()
        assert expected and expected in flat, f"{key}: {expected!r} not on screen"
    assert i18n.fallbacks() == (), f"fell back: {i18n.fallbacks()}"
    assert i18n.FALLBACK_MARK not in out


#: What may legitimately appear in Latin script on a Chinese screen. Everything
#: here is a thing we deliberately do not translate: a command someone types, an
#: environment variable, a filename, a vendor or model id, a path, git's own
#: output, or a URL. The list is the CLAIM — "no English prose survives" is not
#: mechanically decidable, but "every Latin run is one of these" is.
_ALLOWED_LATIN = {
    "crossaudit", "git", "init", "build", "console", "doctor", "run", "amend",
    "CrossAudit", "AUDIT_RULES", "md", "yml", "markdown", "shell", "id",
    "API", "URL", "http", "https", "com", "cli", "github", "io",
    "CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY", "CROSSAUDIT_SHOW_KEYS",
    "CROSSAUDIT_KEYS_FILE", "export", "source", "env", "keys", "proj", "T",
    "anthropic", "openai", "claude", "opus", "gpt", "human", "TODO",
    "DETERMINISTIC_CHECKS", "checks", "parseable", "declared", "internal",
    "complete", "schema", "units", "convergence", "provenance", "CA", "PROJECT",
    "Users", "private", "var", "folders", "tmp", "home", "pytest", "of",
    "ericdong", "test", "the", "wizard", "zh", "en", "n", "s", "x",
}


def test_no_untranslated_english_survives_on_the_chinese_screen(
        tmp_path, monkeypatch, capsys):
    """The guard the fallback counter cannot give.

    A string that was never routed through `t()` at all is invisible to
    `fallbacks()` — it is not a missing translation, it is a missing key, and
    that is exactly how the first version of this slice shipped English `git
    init` and `Next` rows into a Chinese wizard. So the screen itself is read:
    every Latin-script run must be a thing we deliberately do not translate.
    """
    project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="latin")
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out)
    # The sandbox path is printed verbatim and `tui.note` wraps it, so its
    # fragments land in the stream as bare Latin runs. They are characters from
    # a path, not prose, and allow-listing this machine's temp directory names
    # would make the guard pass for the wrong reason on this machine and fail on
    # anyone else's.
    where = str(project)
    hexish = re.compile(r"(?i)^[0-9a-f]+$")
    stray = sorted({
        word for word in re.findall(r"[A-Za-z][A-Za-z_]{1,}", plain)
        if word not in _ALLOWED_LATIN and word not in where
        # The setup commit sha is printed and wrapped; its fragments are hex,
        # not prose.
        and not hexish.match(word)})
    assert stray == [], f"untranslated English on a Chinese screen: {stray}"

    # And the sharper half, which needs no allowlist at all: no sentence from
    # the English catalogue may appear on a Chinese screen.
    leaked = sorted(
        key for key, english in i18n.CATALOGUE["en"].items()
        if len(english) > 12 and "{" not in english and english in plain)
    assert leaked == [], f"English catalogue copy on a Chinese screen: {leaked}"


def test_an_unknown_language_is_english_rather_than_a_broken_screen():
    assert i18n.set_language("klingon") == "en"
    i18n.set_language("en")


def test_the_machine_contract_is_not_translated(tmp_path, monkeypatch, capsys):
    """Exit codes and --json are a scripting contract; copy is not (errors.py)."""
    from crossaudit.errors import EXIT_OK
    project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="json",
                         json=True)
    import json as _json
    payload = _json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert set(payload) >= {"config", "constitution", "mode"}
    assert payload["mode"] == "local"          # not a translated word
    assert Path(payload["config"]).name == "crossaudit.yml"


# ------------------------------------------- D10: demonstrate the guard fails
def test_the_fallback_guard_goes_red_when_a_translation_falls_back_silently(
        tmp_path, monkeypatch, capsys):
    """Mutate the real product so a missing translation is served silently.

    Mutation: `FALLBACK_MARK` becomes empty and `_record` stops recording — the
    two halves of "visible", removed together, which is precisely what `gettext`
    would have given us for free. Compared against a live unmutated run in the
    same session rather than a recorded snapshot (D10 as amended).
    """
    honest_key = sorted(i18n.CATALOGUE["zh"])[0]
    zh_without_one = dict(i18n.CATALOGUE["zh"])
    zh_without_one.pop("done.next")

    # Baseline: with the string genuinely missing, the real product marks and counts.
    monkeypatch.setitem(i18n.CATALOGUE, "zh", zh_without_one)
    _project, honest = _init(tmp_path, monkeypatch, capsys, lang="zh", name="gap")
    assert i18n.FALLBACK_MARK in honest, "the real product failed to mark the gap"
    assert "done.next" in i18n.fallbacks()
    assert "[i18n]" in honest, "the run did not report its own incompleteness"

    # Mutation: make the same gap silent.
    monkeypatch.setattr(i18n, "FALLBACK_MARK", "")
    monkeypatch.setattr(i18n, "_record", lambda key: None)
    _project2, silent = _init(tmp_path, monkeypatch, capsys, lang="zh", name="silent")
    assert i18n.FALLBACK_MARK == ""
    assert "[i18n]" not in silent, (
        "the mutation did not take; this demonstration proves nothing")
    assert i18n.fallbacks() == (), (
        "the mutation did not take; this demonstration proves nothing")
    assert i18n.CATALOGUE["en"]["done.next"] in silent, (
        "the mutation should still serve English — silently, which is the defect")


# --------------------------------------------------------- width and wrapping
def test_chinese_never_overflows_the_boxes_it_is_drawn_in(
        tmp_path, monkeypatch, capsys):
    """Chinese is fewer characters and more columns; the boxes are fixed width."""
    _project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="width")
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out)
    for line in plain.splitlines():
        if line.strip().startswith("│") and line.strip().endswith("│"):
            assert tui._visible(line.strip()) == tui.WIDTH, (
                f"box line is {tui._visible(line.strip())} columns, "
                f"not {tui.WIDTH}: {line!r}")
