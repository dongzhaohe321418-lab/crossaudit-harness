"""Which CrossAudit is this? (D40)

Install 4.15.0 from the DMG, type `crossaudit`, and you can be routed to a
completely different, older install already on PATH — on the machine this was
found, a 3.2.0 pip install from three weeks earlier — with nothing saying so.
D31 decided the bundle installs nothing on PATH, on consent grounds, and that
stands; it is simply silent about a DIFFERENT crossaudit already being there,
and nobody consented to being routed to an old binary.

The severity is S1, not S0, and the distinction shapes this fix. The LEDGER
already tells the two producers apart: receipts carry the version, a path-tagged
code digest and the install mode, and `verify --admit` refuses install modes
whose code could have changed under them. What is misled is the PERSON. So this
is a false-premise experience on valid input, and the fix belongs on the
surfaces a person reads rather than in the receipt path.
"""
from __future__ import annotations

import argparse
import io
import contextlib
import re
import sys
from pathlib import Path

import pytest

from crossaudit import __version__
from crossaudit.cli import i18n, main


def _capture(argv: list[str]) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            main.main(argv)
        except SystemExit:
            pass
    return buf.getvalue()


def test_running_from_reports_this_process_and_does_not_guess(monkeypatch):
    """Facts about THIS process. It must not go looking for rival installs.

    Guessing where another copy might live would be inventing evidence on the
    exact surface that exists to stop us doing that.
    """
    mode, where = main.running_from()
    assert mode in ("frozen-app", "wheel", "editable", "source", "unknown")
    assert where and Path(where).exists(), f"reported a path that is not there: {where}"


def test_version_names_the_install_mode_and_the_path():
    """`--version` is what a person compares between two installs."""
    out = _capture(["--version"])
    assert __version__ in out
    mode, where = main.running_from()
    assert mode in out, f"--version does not say the install mode: {out!r}"
    assert where in out, f"--version does not say where it is running from: {out!r}"


def test_the_front_door_names_which_install_this_is():
    """The first thing a person reads when nothing is set up."""
    out = _capture([])
    mode, where = main.running_from()
    assert mode in out and where in out


def test_two_installs_are_distinguishable_from_their_own_output(monkeypatch):
    """The point of the whole change, stated as the property it must have.

    Not "we detect a mismatch" — we never claim that. Two runs printing two
    versions and two paths is self-evident without anyone asserting it.
    """
    first = _capture(["--version"])

    # A different install, simulated by moving what `running_from` reports.
    monkeypatch.setattr(main, "running_from",
                        lambda: ("frozen-app",
                                 "/Applications/CrossAudit.app/Contents/"
                                 "Resources/core/CrossAuditCore"))
    second = _capture([])
    assert "frozen-app" in second and "/Applications/CrossAudit.app" in second
    assert first != second
    # And neither output asserts anything about the other.
    for out in (first, second):
        assert "mismatch" not in out.lower()
        assert "another" not in out.lower() or "PATH" in out


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_doctor_says_which_install_this_is_in_both_languages(
        tmp_path, monkeypatch, capsys, lang):
    """Doctor is the command a confused person runs, so it says it out loud.

    An INFO posture line, not a check: "which install is this" has no pass/fail
    axis, and a green marker beside it would be the defect this project has
    spent the week removing. Posture lines render in the DEFAULT view, which is
    where the confused person is.
    """
    project = tmp_path / f"p-{lang}"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / f"home-{lang}"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"k-{lang}.env"))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5", profile="own",
        lang="en"))
    capsys.readouterr()
    from crossaudit.config import load as _load
    _load(project / "crossaudit.yml")
    main.main(["doctor", "--lang", lang])
    out = capsys.readouterr().out

    flat = re.sub(r"\s+", " ", out)
    assert i18n.CATALOGUE[lang]["origin.doctor.label"] in flat
    mode, where = main.running_from()
    assert mode in flat and where in flat
    assert i18n.fallbacks() == (), f"fell back: {i18n.fallbacks()}"
    # A posture, never a verdict.
    assert "[PASS] install origin" not in out
    assert "✗ " + i18n.CATALOGUE[lang]["origin.doctor.label"] not in out


def test_the_origin_line_is_a_posture_not_a_counted_check(
        tmp_path, monkeypatch, capsys):
    """It must not move the tally, because it tests nothing."""
    project = tmp_path / "tally"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home-tally"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / "k-tally.env"))
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5", profile="own",
        lang="en"))
    capsys.readouterr()
    from crossaudit.config import load as _load
    _load(project / "crossaudit.yml")
    main.main(["doctor", "--all"])
    rows = [ln for ln in capsys.readouterr().out.splitlines()
            if "install origin" in ln]
    assert rows and rows[0].startswith("[INFO]"), rows


# ------------------------------------------- D10: demonstrate the guard fails
def test_the_visibility_guard_goes_red_when_the_origin_is_hidden_again(
        monkeypatch):
    """Mutate the real product back to a version string with no origin."""
    honest = _capture(["--version"])
    mode, where = main.running_from()
    assert mode in honest and where in honest

    monkeypatch.setattr(main, "running_from", lambda: ("", ""))
    # Rebuilt parser, as a fresh process would build it.
    silent = _capture(["--version"])
    assert where not in silent, (
        "the mutation did not take; this demonstration proves nothing")
    assert __version__ in silent, "the version itself should still print"
