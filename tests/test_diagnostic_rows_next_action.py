"""Two rails, one narrow line: a fault must say what to do, a posture must not.

`->` has a fixed meaning in doctor output — YOU HAVE SOMETHING TO DO. That makes
the two properties here edges of the same line rather than two unrelated rules:

  * a row reporting a FAULT must carry a next action; silence leaves a person
    stuck, which is what `test_every_failing_doctor_row_tells_the_person_what_
    to_do_next` on `audit/honesty-guards` exists to prevent;
  * a row reporting a POSTURE must carry no arrow at all, because attaching one
    manufactures a task where nothing is wrong — `test_an_info_line_never_offers
    _a_fix_arrow` in `test_first_three_minutes.py`.

I crossed the second while satisfying the first: I gave all six `[INFO]` rows
arrows. Both existing guards were right and neither, alone, describes the line.
These hold the shape between them from this branch.

WHAT A POSTURE ROW GETS INSTEAD. The admission tier says out loud that there is
nothing to change, as its own second sentence rather than behind an arrow. That
sentence is human copy, so it lives in the human renderer; `--all` and `--json`
stay the verbatim machine surface they are contracted to be (F3).
"""
from __future__ import annotations

import argparse
import json
import re

from crossaudit import admission as adm
from crossaudit.cli import i18n, main

CJK = re.compile(r"[一-鿿]")


def _payload(cfg, monkeypatch, capsys) -> list[dict]:
    """The rows as the parser receives them."""
    monkeypatch.chdir(cfg.root)
    main.cmd_doctor(argparse.Namespace(json=True, all=True, fix=False, online=False))
    out = capsys.readouterr().out
    return json.loads(out[out.index("{"):out.rindex("}") + 1])["checks"]


# ------------------------------------------------------------- rail one
def test_every_row_reporting_a_fault_says_what_to_do_about_it(cfg, monkeypatch,
                                                              capsys):
    """The property the honesty guard is after, with the filter it needs.

    `ok` is tri-valued: True tested and held, False tested and did not, None
    not a test at all. `not c["ok"]` sweeps None in with False, which is how
    six posture rows came to be reported as failing rows with nothing to do.
    A verdict row is the only kind that can be said to have failed.
    """
    checks = _payload(cfg, monkeypatch, capsys)
    failing = [c for c in checks if c["kind"] != "info" and not c["ok"]]
    assert failing, "no failing row in this fixture; the guard would be vacuous"

    silent = [c["check"] for c in failing if not str(c.get("fix", "")).strip()]
    assert silent == [], (
        f"these rows tell a person something is wrong and not what to do "
        f"about it: {silent}")


# ------------------------------------------------------------- rail two
def test_a_posture_row_never_offers_a_next_action(cfg, monkeypatch, capsys):
    """A posture has nothing to fix. The field itself stays empty, so no
    renderer can decide to draw an arrow beside one."""
    checks = _payload(cfg, monkeypatch, capsys)
    info = [c for c in checks if c["kind"] == "info"]
    assert info, "no posture row in this fixture; the guard would be vacuous"

    offered = [c["check"] for c in info if str(c.get("fix", "")).strip()]
    assert offered == [], (
        f"these rows describe a state of the world and offer a remedy for it, "
        f"which reads as: you have something to do. {offered}")


def test_the_configured_contracts_are_descriptions_and_stay_that_way(cfg,
                                                                    monkeypatch,
                                                                    capsys):
    """`machine:*` says what a check covers. D6 turned these from a false
    `[PASS]` into `[INFO]` precisely because they report nothing about this
    project; giving them a remedy walks that back under a different name."""
    checks = _payload(cfg, monkeypatch, capsys)
    contracts = [c for c in checks if c["check"].startswith("machine:")]
    assert contracts, "the configured contracts should be listed"
    for c in contracts:
        assert c["kind"] == "info", f"{c['check']} is not a verdict"
        assert not str(c["fix"]).strip(), (
            f"{c['check']} describes what a check covers; there is nothing to "
            f"do about it. Got: {c['fix']!r}")


# ------------------------------------- what the posture row says instead
def test_the_admission_tier_says_out_loud_that_there_is_nothing_to_change(cfg,
                                                                         monkeypatch,
                                                                         capsys):
    """Silence is not the same as "nothing to do". The row states it."""
    monkeypatch.chdir(cfg.root)
    main.cmd_doctor(argparse.Namespace(json=False, all=False, fix=False,
                                       online=False, lang="en"))
    rendered = capsys.readouterr().out
    assert i18n.CATALOGUE["en"]["doctor.tier.standing.local"] in rendered, (
        "the tier row reports where this project stands and leaves the reader "
        "to work out whether that needs anything")

    # And it is the row's own text, not a promise of work.
    lines = rendered.splitlines()
    for index, line in enumerate(lines[:-1]):
        if "nothing to change unless" in lines[index + 1]:
            assert not lines[index + 1].strip().startswith(("→", "->")), (
                f"the standing sentence is behind an arrow: {lines[index + 1]!r}")


def test_every_tier_can_say_where_it_stands_in_both_languages():
    """The key is built from the tier name, so a tier without one renders
    `[missing:doctor.tier.standing.…]` at a person."""
    for tier in adm.TIER_MEANING:
        key = f"doctor.tier.standing.{tier.lower()}"
        for lang in ("en", "zh"):
            assert key in i18n.CATALOGUE[lang], f"{key} missing from {lang}"
            assert i18n.CATALOGUE[lang][key].strip(), f"{key} is empty in {lang}"


def test_the_standing_sentence_reaches_a_chinese_reader(cfg, monkeypatch, capsys):
    monkeypatch.chdir(cfg.root)
    main.main(["doctor", "--lang", "zh"])
    assert i18n.CATALOGUE["zh"]["doctor.tier.standing.local"] in capsys.readouterr().out


def test_the_standing_sentence_never_reaches_the_machine_surface(cfg, monkeypatch,
                                                                 capsys):
    """It is human copy. `--all` and `--json` are a contract with a parser, and
    putting a translated sentence there is the F3 defect."""
    monkeypatch.chdir(cfg.root)
    main.main(["doctor", "--lang", "zh", "--all"])
    assert not CJK.search(capsys.readouterr().out), (
        "translated text reached --all; that surface is read by scripts")

    main.main(["--json", "doctor", "--lang", "zh"])
    out = capsys.readouterr().out
    checks = json.loads(out[out.index("{"):out.rindex("}") + 1])["checks"]
    for c in checks:
        assert not CJK.search(c["detail"]), c
        assert not CJK.search(str(c.get("standing", ""))), (
            f"{c['check']} carries translated text where a key belongs: {c}")
