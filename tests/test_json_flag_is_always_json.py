"""`--json` before the command gives JSON on stdout and nothing else.

README "Command reference": commands that emit structured results support the
global `--json` flag. The acceptance run (claim C21) found `crossaudit --json
routing` printing `no routing decisions recorded yet` on a fresh project, and
JSON only once a decision existed. The sweep here runs every command the
claim names on an empty project (the state a script meets first) and on the
same project after one build, and parses stdout whole.

D10 mutation (checked by hand): restore the early `if not rows: print(...)`
ahead of the `--json` branch in `cmd_routing` and three go red with a
JSONDecodeError: both empty-project routing cases, and the after-build sweep
(`build` routes nothing, so its routing log is still empty).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import FakeVendors, init_project, with_keys  # noqa: E402

from crossaudit.cli import main  # noqa: E402

COMMANDS = [["status"], ["doctor"], ["check"], ["routing"],
            ["verify", "cycles/none/receipt.json"]]


def _json_stdout(argv, capsys):
    capsys.readouterr()
    main.main(["--json", *argv])
    out = capsys.readouterr().out
    return json.loads(out)          # raises if anything but one JSON document


@pytest.mark.parametrize("argv", COMMANDS, ids=lambda a: a[0])
def test_every_json_command_prints_only_json_on_an_empty_project(
        tmp_path, monkeypatch, capsys, argv):
    with_keys(monkeypatch)
    init_project(tmp_path, monkeypatch)
    _json_stdout(argv, capsys)


def test_routing_is_an_empty_list_before_anything_was_routed(
        tmp_path, monkeypatch, capsys):
    init_project(tmp_path, monkeypatch)
    assert _json_stdout(["routing"], capsys) == []


def test_every_json_command_prints_only_json_after_a_build(
        tmp_path, monkeypatch, capsys):
    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)
    FakeVendors().install(monkeypatch)
    assert main.main(["build", "Create a small reproducible benchmark"]) == 0
    receipt = sorted((root / "cycles").glob("*-r1/receipt.json"))[0]
    for argv in (["status"], ["doctor"], ["check"], ["routing"],
                 ["verify", str(receipt)]):
        doc = _json_stdout(argv, capsys)
        if argv == ["routing"]:
            assert isinstance(doc, list)        # the same shape as when empty
