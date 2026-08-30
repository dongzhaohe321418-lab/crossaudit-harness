"""Which `crossaudit` answers when a person types it (D40).

The failure: somebody installs the app, types `crossaudit`, and runs an older
pip installation that sits earlier on PATH. On the machine this was found, that
is 3.2.0 from three weeks before a 4.15.0 app — a build predating the symlink
escape fix, the erasable verdict and the trimmed constitution reader.

**It cannot be closed from the CLI side.** In that state our CLI never executes;
the stale one does. `--version` was the first attempt and it is structurally
incapable of reaching the case: the `--version` that runs is the old binary's.
So this looks OUTWARD from the app, which is the one place our code is certainly
running, and it is honest about being partial.

Nothing here executes the other binary. That would mean running a program we did
not build, in the person's environment, because we found it — which §1.1 forbids
and which would hand code execution to anyone who can write to a PATH directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crossaudit import __version__, app_doctor


def test_no_other_crossaudit_on_path_says_nothing():
    assert app_doctor.path_identity(which=lambda _n: None)["state"] == "absent"


def test_our_own_install_is_not_reported_as_a_stranger():
    """The bias is toward silence; a false alarm here is the worst wrong answer."""
    import sys

    beside_me = str(Path(sys.executable).resolve().parent / "crossaudit")
    assert app_doctor.path_identity(which=lambda _n: beside_me)["state"] == "same"


def test_a_different_install_is_named_with_both_paths():
    found = app_doctor.path_identity(which=lambda _n: "/opt/elsewhere/bin/crossaudit")
    assert found["state"] == "different"
    assert found["path"] == "/opt/elsewhere/bin/crossaudit"
    assert found["mine"] and found["mine"] != found["path"]


def test_the_other_version_is_read_from_metadata_and_never_executed(tmp_path,
                                                                    monkeypatch):
    """A pip console script's version is in its dist-info directory NAME.

    Reading it is a filesystem lookup. The guard below is what makes "never
    executed" a fact rather than a promise: any attempt to spawn a process
    during this call fails the test.
    """
    import subprocess

    prefix = tmp_path / "otherenv"
    (prefix / "bin").mkdir(parents=True)
    script = prefix / "bin" / "crossaudit"
    script.write_text("#!/usr/bin/env python\n")
    site = prefix / "lib" / "python3.13" / "site-packages"
    site.mkdir(parents=True)
    (site / "crossaudit-3.2.0.dist-info").mkdir()

    def refuse(*a, **k):
        raise AssertionError("the foreign binary was executed")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "check_output", refuse)

    assert app_doctor._other_crossaudit_version(script) == "3.2.0"
    row = app_doctor.path_identity(which=lambda _n: str(script))
    assert row["state"] == "different" and row["version"] == "3.2.0"


def test_an_unreadable_layout_says_it_does_not_know_rather_than_guessing(tmp_path):
    """"I could not determine its version" is a good row. Guessing is not."""
    script = tmp_path / "weird" / "crossaudit"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n")
    assert app_doctor._other_crossaudit_version(script) == ""
    row = app_doctor.path_identity(which=lambda _n: str(script))
    assert row["state"] == "different"
    assert row["version"] == "", "a version was invented for an unknown layout"


def _row(cfg, monkeypatch, where: str):
    monkeypatch.setattr(app_doctor, "path_identity",
                        lambda **_k: {"state": "different", "path": where,
                                      "version": "3.2.0", "mine": "/Applications/x"})
    rows = app_doctor.collect(cfg, online=False)["checks"]
    return [r for r in rows if r["id"] == "path_identity"]


def test_the_row_states_both_programs_and_does_not_block(cfg, monkeypatch):
    rows = _row(cfg, monkeypatch, "/Library/Frameworks/Python.framework/bin/crossaudit")
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "warning" and row["blocking"] is False, (
        "the app works; what is broken is the person's expectation")
    assert "/Library/Frameworks" in row["detail"]
    assert "3.2.0" in row["detail"]
    assert __version__ in row["detail"] and "/Applications/x" in row["detail"]


def test_the_row_says_why_it_cannot_tell_when_it_cannot(cfg, monkeypatch):
    monkeypatch.setattr(app_doctor, "path_identity",
                        lambda **_k: {"state": "different", "path": "/opt/x",
                                      "version": "", "mine": "/Applications/x"})
    row = [r for r in app_doctor.collect(cfg, online=False)["checks"]
           if r["id"] == "path_identity"][0]
    assert "could not be determined without running it" in row["detail"]
    assert "does not do" in row["detail"]


def test_no_row_when_there_is_nothing_to_say(cfg, monkeypatch):
    for state in ("absent", "same"):
        def quiet(_state=state, **_k):
            return {"state": _state, "path": "", "version": "", "mine": ""}

        monkeypatch.setattr(app_doctor, "path_identity", quiet)
        rows = [r for r in app_doctor.collect(cfg, online=False)["checks"]
                if r["id"] == "path_identity"]
        assert rows == [], f"a row appeared for state {state!r}"


def test_the_guard_goes_red_if_the_row_stops_naming_the_other_program(
        cfg, monkeypatch):
    """D10: the property assertion must fail against a deliberate mutation."""
    def property_holds():
        rows = _row(cfg, monkeypatch, "/Library/other/crossaudit")
        assert rows and "/Library/other/crossaudit" in rows[0]["detail"], (
            "the row does not name the program that will actually answer")

    property_holds()

    real = app_doctor.collect

    def vague(cfg_, **kw):
        out = real(cfg_, **kw)
        for row in out["checks"]:
            if row["id"] == "path_identity":
                row["detail"] = "Another CrossAudit is installed."
        return out

    monkeypatch.setattr(app_doctor, "collect", vague)
    with pytest.raises(AssertionError) as caught:
        property_holds()
    assert "does not name the program" in str(caught.value)
