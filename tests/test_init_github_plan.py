"""`crossaudit init --github`: the two-repository panel is `pair`'s own plan,
and the GitHub warning says one thing (D173).

The claims harness ran `init --github` with `gh` installed and signed out. The
panel ended "crossaudit pair --apply   does all of it", which was false (branch
protection, listed above it, is never applied), and the warning read "gh
installed but not authenticated (run: gh auth login) — install from
https://cli.github.com first": installed and install, in one line.

These run the real `init` with a fake `gh` on PATH (or none) and read the
screen it prints.
"""
from __future__ import annotations

import argparse
import os
import re

import pytest

from crossaudit.cli import i18n, main

FAKE_GH = """#!/bin/sh
case "$1 $2" in
  "auth status") echo "You are not logged into any GitHub hosts." >&2; exit 1 ;;
esac
echo "fake gh: unscripted call: $*" >&2
exit 1
"""


def _init(tmp_path, monkeypatch, capsys, *, gh: str, lang: str = "en") -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if gh == "signed_out":
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(bin_dir), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    if gh == "absent" and __import__("shutil").which("gh"):
        pytest.skip("a gh is installed in a system directory")
    monkeypatch.delenv("CROSSAUDIT_BUNDLED_GH", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / "keys.env"))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=True, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5", profile="own",
        lang=lang))
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", capsys.readouterr().out)


def _flat(text: str) -> str:
    return re.sub(r"[\s│|]+", " ", text)


@pytest.mark.parametrize("gh", ["signed_out", "absent"])
def test_the_panel_is_pairs_plan_and_names_what_is_left(
        tmp_path, monkeypatch, capsys, gh):
    flat = _flat(_init(tmp_path, monkeypatch, capsys, gh=gh))

    assert "does all of it" not in flat
    for command in ("gh repo create OWNER/project --private",
                    "gh repo create OWNER/project-audit --private",
                    "git remote add origin https://github.com/OWNER/project.git",
                    "git push -u origin HEAD:main",
                    "crossaudit pair --science OWNER/project --audit "
                    "OWNER/project-audit --apply"):
        assert command in flat, command
    afterwards = flat.split(i18n.CATALOGUE["en"]["done.two_repos.afterwards"], 1)
    assert len(afterwards) == 2
    assert "gh api repos/OWNER/project/branches/main/protection -X PUT" in afterwards[1]
    assert "protection" not in afterwards[0]


@pytest.mark.parametrize("gh,says,other", [
    ("signed_out", "done.gh_signed_out", "done.gh_not_installed"),
    ("absent", "done.gh_not_installed", "done.gh_signed_out"),
])
def test_the_github_warning_says_one_thing(tmp_path, monkeypatch, capsys,
                                           gh, says, other):
    flat = _flat(_init(tmp_path, monkeypatch, capsys, gh=gh))
    assert _flat(i18n.CATALOGUE["en"][says]) in flat
    assert _flat(i18n.CATALOGUE["en"][other]) not in flat
    # The contradictory composition is gone from both states.
    assert "install from https://cli.github.com first" not in flat
    assert "installed but not authenticated" not in flat


def test_the_panel_and_warning_are_chinese_in_chinese(tmp_path, monkeypatch, capsys):
    flat = _flat(_init(tmp_path, monkeypatch, capsys, gh="signed_out", lang="zh"))
    for key in ("done.two_repos.afterwards", "done.gh_signed_out"):
        assert _flat(i18n.CATALOGUE["zh"][key]) in flat, key
    apply_zh = max(re.split(r"\{\w+\}", i18n.CATALOGUE["zh"]["done.two_repos.apply"]),
                   key=len).strip()
    assert apply_zh in flat
    assert i18n.fallbacks() == ()
