"""A Chinese user must be able to reach the Chinese layer.

The catalogue was complete and correct and the switch could not be thrown: the
global `--lang` was read as a verb ("invalid choice: 'zh'"), the system locale
was ignored, and `--help` never mentioned the flag. That is not a coverage
problem — until it is fixed, every translation added is unreachable.

These drive `crossaudit.app.main`, the entry point the frozen bundle runs, so
the reachability claim is about the packaged grammar rather than a source-only
convenience.
"""
from __future__ import annotations

import argparse

import pytest

from crossaudit.app import main as packaged_main
from crossaudit.cli import i18n
from crossaudit.cli import main as cli_main


@pytest.fixture(autouse=True)
def _clean_locale(monkeypatch, tmp_path):
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


def _doctor(capsys, argv):
    """Run through the PACKAGED entry point and return what a person saw."""
    packaged_main(argv)
    return capsys.readouterr().out


def _is_chinese(text: str) -> bool:
    import re

    return bool(re.search(r"[一-鿿]", text))


# --------------------------------------------------- the reported symptom
def test_the_global_flag_parses_before_the_verb(capsys):
    """`crossaudit --lang zh doctor` was read as a verb and refused."""
    out = _doctor(capsys, ["--lang", "zh", "doctor"])
    assert _is_chinese(out), f"the global flag did not reach the language: {out[:120]!r}"


def test_the_flag_still_works_after_the_verb(capsys):
    out = _doctor(capsys, ["doctor", "--lang", "zh"])
    assert _is_chinese(out)


def test_a_command_flag_does_not_silently_undo_the_global_one(capsys):
    """The argparse trap that would quietly revert this fix.

    `doctor` defines its own `--lang`. If that option carries a default rather
    than SUPPRESS, argparse writes the default over the global value whenever
    the person does not repeat the flag — the global flag parses, changes
    nothing, and nothing fails.
    """
    parser_source = __import__("pathlib").Path(cli_main.__file__).read_text()
    assert parser_source.count("default=argparse.SUPPRESS, help=LANG_HELP") >= 1, (
        "a per-command --lang carries its own default again, which overwrites "
        "the global one whenever it is absent")
    out = _doctor(capsys, ["--lang", "zh", "doctor"])
    assert _is_chinese(out)


# ------------------------------------------------------- the system locale
def test_a_chinese_system_locale_needs_no_flag(capsys, monkeypatch):
    """A switch a user has to discover is one most users never find."""
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    out = _doctor(capsys, ["doctor"])
    assert _is_chinese(out), "a Mac set to Chinese still got English"


@pytest.mark.parametrize("value", ["zh_CN.UTF-8", "zh_TW", "zh", "zh-Hans"])
def test_the_locale_reader_accepts_the_shapes_people_have(value, monkeypatch):
    monkeypatch.setenv("LC_ALL", value)
    assert i18n.from_environment() == "zh"


@pytest.mark.parametrize("value", ["C", "POSIX", "", "fr_FR.UTF-8", "de_DE"])
def test_an_unservable_locale_keeps_english(value, monkeypatch):
    """Only a language the catalogue has is honoured; anything else defers."""
    monkeypatch.setenv("LC_ALL", value)
    assert i18n.from_environment() is None


def test_lc_all_outranks_lang(monkeypatch):
    monkeypatch.setenv("LANG", "en_GB.UTF-8")
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
    assert i18n.from_environment() == "zh"


def test_a_neutral_lc_all_defers_to_lang_rather_than_ending_the_search(
        monkeypatch):
    """`LC_ALL=C` with a Chinese `LANG` is a real shell, not a corner.

    A neutral `C`/`POSIX` value means "no preference stated", so it must be
    stepped over rather than treated as an answer. Reading it as an answer ends
    the search and the person's actual `LANG` is never consulted — my mutation
    run found this uncovered, because with `LC_ALL=C` alone the outcome is the
    same either way and only this pairing tells them apart.
    """
    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert i18n.from_environment() == "zh", (
        "a neutral LC_ALL ended the search and hid the person's LANG")

    monkeypatch.setenv("LC_ALL", "POSIX")
    assert i18n.from_environment() == "zh"


def test_an_explicit_flag_beats_the_system_locale(capsys, monkeypatch):
    """Someone overriding their system locale must be able to."""
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert not _is_chinese(_doctor(capsys, ["--lang", "en", "doctor"]))
    assert not _is_chinese(_doctor(capsys, ["doctor", "--lang", "en"]))


def test_english_stays_the_default_when_nothing_asks(capsys):
    assert not _is_chinese(_doctor(capsys, ["doctor"]))


# ------------------------------------------------------------- discoverable
def test_the_flag_is_documented_in_help(capsys):
    """Through the packaged entry, which deliberately swallows argparse's
    SystemExit so the app's no-exception boundary holds — asserting a raise
    here would be asserting the source behaviour, not the bundle's."""
    code = packaged_main(["--help"])
    assert code == 0
    out = capsys.readouterr().out
    assert "--lang" in out, "the flag exists and --help does not mention it"
    assert "{en,zh}" in out, "--help does not say which languages are available"
