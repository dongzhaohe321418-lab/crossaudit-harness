"""Every diagnostic row that speaks also says what to do next.

Six rows told a person something was so and stopped: four `machine:*` contract
rows and the two admission postures. They surfaced when three branches were
staged together and the honesty guard walked a wider set of rows than any single
branch produced.

The guard that found them lives on `audit/honesty-guards`. These are the same
property held from this branch, so the rows stay fixed whichever lands first.
"""
from __future__ import annotations

import argparse

import pytest

from crossaudit.cli import main


# ------------------------------------------------------ w1: the six rows
def test_every_diagnostic_row_that_speaks_also_says_what_to_do(cfg, monkeypatch,
                                                               capsys):
    """The six rows the merged guard found, held directly.

    `machine:*`, `admission tier` and `  toward enforced` told a person
    something and stopped. Four of them are the least readable rows in the
    product to begin with.
    """
    import json as _json

    monkeypatch.chdir(cfg.root)
    main.cmd_doctor(argparse.Namespace(json=True, all=True, fix=False, online=False))
    out = capsys.readouterr().out
    checks = _json.loads(out[out.index("{"):out.rindex("}") + 1])["checks"]

    speaking = [c for c in checks if c["ok"] is not True]
    assert speaking, "no non-passing row in this fixture; the guard is vacuous"
    silent = [c["check"] for c in speaking if not str(c.get("fix", "")).strip()]
    assert silent == [], (
        f"these rows tell a person something and not what to do: {silent}")


def test_a_posture_row_says_there_is_nothing_to_do_rather_than_going_quiet(cfg,
                                                                          monkeypatch,
                                                                          capsys):
    """`admission tier` describes a state of the world, not a fault. Saying
    "nothing to change" IS a next action; silence is not."""
    from crossaudit import admission as adm

    assert set(adm.TIER_NEXT_ACTION) == set(adm.TIER_MEANING), (
        "a tier exists with no stated next action")
    for tier, action in adm.TIER_NEXT_ACTION.items():
        assert action.strip(), f"{tier} has an empty next action"
    assert "nothing to change" in adm.TIER_NEXT_ACTION[adm.LOCAL], (
        "the self-review tier no longer says out loud that there is nothing "
        "to change")


def test_the_next_action_reaches_the_terminal_for_a_posture_row(cfg, monkeypatch,
                                                                capsys):
    monkeypatch.chdir(cfg.root)
    main.cmd_doctor(argparse.Namespace(json=False, all=True, fix=False, online=False))
    rendered = capsys.readouterr().out
    assert "these run automatically before any model sees your work" in rendered, (
        "a contract row's next action exists in the payload and never reaches "
        "the person")


def test_the_new_next_actions_reach_a_chinese_reader():
    from crossaudit.cli import i18n

    for key in ("doctor.machine_check.fix", "doctor.shortfall.fix",
                "doctor.tier.fix.local", "doctor.tier.fix.enforced"):
        assert key in i18n.CATALOGUE["en"], f"{key} missing from en"
        assert key in i18n.CATALOGUE["zh"], f"{key} missing from zh"


def test_the_human_next_action_never_reaches_the_machine_surface(cfg, monkeypatch,
                                                                 capsys):
    """`fix` is the parser's field. Translating it in place is the F3 defect,
    and I made exactly that mistake before this guard existed."""
    import re as _re

    monkeypatch.chdir(cfg.root)
    main.main(["doctor", "--lang", "zh", "--all"])
    assert not _re.search(r"[一-鿿]", capsys.readouterr().out), (
        "translated text reached --all; that surface is a contract with a parser")
