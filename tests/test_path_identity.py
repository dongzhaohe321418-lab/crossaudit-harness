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

import os
from pathlib import Path

import pytest

from crossaudit import __version__, app_doctor


def test_no_other_crossaudit_on_path_says_nothing():
    assert app_doctor.path_identity(which=lambda _n: None)["state"] == "absent"


def _install(root: Path, version: str | None, *, record: bool = True) -> Path:
    """A real pip-shaped prefix on disk: `bin/crossaudit`, dist-info and RECORD.

    Built rather than mocked, because the defect this file now guards was in
    how two real paths relate to each other — a fixture returning a canned
    state could not have shown it, and did not. The RECORD is written the way an
    installer writes it, relative to site-packages and carrying the sha256, so
    the ownership check runs against the real shape rather than a convenient one.
    """
    (root / "bin").mkdir(parents=True, exist_ok=True)
    script = root / "bin" / "crossaudit"
    script.write_text("#!/usr/bin/env python\n")
    site = root / "lib" / "python3.13" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    if version:
        dist = site / f"crossaudit-{version}.dist-info"
        dist.mkdir(exist_ok=True)
        if record:
            _record(dist, site, script)
    return script


def _record(dist: Path, site: Path, script: Path) -> None:
    import base64
    import hashlib

    digest = base64.urlsafe_b64encode(
        hashlib.sha256(script.read_bytes()).digest()).rstrip(b"=").decode()
    relative = os.path.relpath(script, site)
    (dist / "RECORD").write_text(
        f"{relative},sha256={digest},{script.stat().st_size}\n")


def test_our_own_install_is_not_reported_as_a_stranger(tmp_path, monkeypatch):
    """The bias is toward silence; a false alarm here is the worst wrong answer.

    This test used to point at `Path(sys.executable).resolve().parent`, i.e. at
    whatever `crossaudit` happened to sit beside the real interpreter. On the
    machine that reported D40 that file is the 3.2.0 install, so the test was
    asserting "same" about a genuine stranger and passing. **It was validated by
    the environment that has the defect.** It builds its own prefix now.
    """
    import sys

    script = _install(tmp_path / "mine", __version__)
    interpreter = tmp_path / "mine" / "bin" / "python3.13"
    interpreter.write_text("")
    monkeypatch.setattr(sys, "executable", str(interpreter))
    assert app_doctor.path_identity(which=lambda _n: str(script))["state"] == "same"


def test_a_virtualenv_does_not_mistake_its_base_prefix_for_itself(tmp_path,
                                                                  monkeypatch):
    """The live D40 failure state, reproduced as the two directories it is.

    A virtualenv's `bin/python` is a symlink into the base prefix, so
    `Path(sys.executable).resolve()` lands in the base `bin` — the directory the
    stale `crossaudit` is in. The sibling test then called the shadowing install
    a sibling and the row stayed silent, which is the one wrong answer this
    surface cannot afford: it is silent precisely when there is something to
    say. Executed against the real machine, the row printed nothing at all.
    """
    import sys

    base_script = _install(tmp_path / "base", "3.2.0")
    base_python = tmp_path / "base" / "bin" / "python3.13"
    base_python.write_text("")
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    venv_python = venv_bin / "python"
    venv_python.symlink_to(base_python)
    monkeypatch.setattr(sys, "executable", str(venv_python))

    assert Path(sys.executable).resolve().parent == base_script.parent, (
        "fixture does not reproduce the topology: the resolved interpreter must "
        "land in the same directory as the shadowing script")

    row = app_doctor.path_identity(which=lambda _n: str(base_script))
    assert row["state"] == "different", (
        "the shadowing install was reported as this one")
    assert row["version"] == "3.2.0"
    assert row["mine"] == str(venv_python), (
        "the row should name the interpreter as invoked, not the base prefix "
        "it borrows a binary from")


def test_the_same_version_beside_us_stays_quiet(tmp_path, monkeypatch):
    """Version evidence outranks the heuristic only when it CONTRADICTS it."""
    import sys

    script = _install(tmp_path / "mine", __version__)
    interpreter = tmp_path / "mine" / "bin" / "python3.13"
    interpreter.write_text("")
    monkeypatch.setattr(sys, "executable", str(interpreter))
    row = app_doctor.path_identity(which=lambda _n: str(script))
    assert row["state"] == "same", "a same-version sibling is not worth a row"


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
    dist = site / "crossaudit-3.2.0.dist-info"
    dist.mkdir()
    _record(dist, site, script)

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


def test_a_half_uninstalled_prefix_reports_no_version_rather_than_the_higher_one(
        tmp_path):
    """Two dist-info directories is what a partial `pip uninstall` leaves.

    Taking the first of `sorted(...)` answered "10.0.0" with nothing
    establishing that the script belonged to it. Sort order is not evidence.
    """
    script = _install(tmp_path / "half", "9.9.9")
    site = tmp_path / "half" / "lib" / "python3.13" / "site-packages"
    other = site / "crossaudit-10.0.0.dist-info"
    other.mkdir()
    _record(other, site, script)

    assert app_doctor._other_crossaudit_version(script) == "", (
        "a version was chosen between two distributions that both claim the file")


def test_a_foreign_program_of_the_same_name_is_not_given_our_version(tmp_path):
    """The scenario the row exists for, and the one it got wrong.

    A prefix that merely happens to have CrossAudit installed, with some other
    program named `crossaudit` in its `bin`. Reporting that prefix's version for
    that program is a confident wrong answer about which program answers you.
    """
    script = _install(tmp_path / "foreign", "1.0.0", record=False)
    assert app_doctor._other_crossaudit_version(script) == ""

    row = app_doctor.path_identity(which=lambda _n: str(script))
    assert row["state"] == "different" and row["version"] == "", (
        "an unowned script was given a version")


def test_a_script_replaced_after_installation_stops_being_owned(tmp_path):
    """RECORD carries a hash, so a swapped console script is detectable."""
    script = _install(tmp_path / "swapped", "3.2.0")
    assert app_doctor._other_crossaudit_version(script) == "3.2.0"

    script.write_text("#!/bin/sh\necho something else entirely\n")
    assert app_doctor._other_crossaudit_version(script) == "", (
        "the version survived the file it describes being replaced")
