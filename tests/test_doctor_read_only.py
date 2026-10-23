"""`doctor` is read-only unless `--fix` (README "2. Check the installation").

The acceptance run (claim C04) hashed a fresh project before and after
`crossaudit doctor` and found `.crossaudit/state.json` created: the admission
probe, `StateStore.capabilities()`, took the read-modify-write lock and wrote
the state back. These tests run the real `doctor` on a project made by the
real `init` and compare the whole tree, `.git` and `.crossaudit` included.

D10 mutation (checked by hand): restore the old probe in
`StateStore.capabilities` (`with self._locked() as state: ...`) and six go
red: the four `doctor` cases and the tier case on `.crossaudit/state.json`,
and the existing-store case on the rewritten mtime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import init_project, tree_digest  # noqa: E402

from crossaudit.cli import main  # noqa: E402
from crossaudit.controller import StateStore  # noqa: E402
from crossaudit.gitio import git  # noqa: E402


@pytest.mark.parametrize("argv", [["doctor"], ["--json", "doctor"],
                                  ["doctor", "--all"], ["doctor", "--fix"]],
                         ids=["doctor", "json", "all", "fix-without-a-terminal"])
def test_doctor_writes_nothing(tmp_path, monkeypatch, capsys, argv):
    root = init_project(tmp_path, monkeypatch)
    capsys.readouterr()
    before = tree_digest(root)
    main.main(argv)
    out = capsys.readouterr().out
    assert tree_digest(root) == before
    assert not (root / ".crossaudit").exists()
    if "--json" in argv:
        json.loads(out)


def test_doctor_reports_the_same_tier_without_writing(tmp_path, monkeypatch, capsys):
    """The probe still proves atomicity: read-only must not cost the tier."""
    root = init_project(tmp_path, monkeypatch)
    capsys.readouterr()
    main.main(["--json", "doctor"])
    report = json.loads(capsys.readouterr().out)
    caps = StateStore(root / ".crossaudit" / "state.json").capabilities()
    assert caps["atomic"], caps["why_not"]
    assert report["admission"]["tier"]
    assert not (root / ".crossaudit").exists()


def test_capabilities_reads_an_existing_store_without_rewriting_it(tmp_path):
    path = tmp_path / "state" / "state.json"
    store = StateStore(path)
    store.open_or_advance("t/p", "a" * 40, None)
    before = path.read_bytes()
    stat = path.stat()
    # Since the kernel-held lock (review 2026-10-23 round 4) the lock file is
    # never deleted, so the mutation above leaves `state.json.lock` behind as
    # an inert file. What this test guards is that capabilities() itself
    # writes and creates nothing, so the listing is compared before and after.
    listing = sorted(p.name for p in path.parent.iterdir())
    assert listing == ["state.json", "state.json.lock"]
    caps = store.capabilities()
    assert caps["atomic"], caps["why_not"]
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == stat.st_mtime_ns
    assert sorted(p.name for p in path.parent.iterdir()) == listing


def test_a_corrupt_store_still_reports_itself_unlockable(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    caps = StateStore(path).capabilities()
    assert not caps["atomic"] and "corrupt" in caps["why_not"]
    assert path.read_text() == "{not json"


def test_doctor_fix_on_a_terminal_keeps_its_documented_write(tmp_path, monkeypatch,
                                                             capsys):
    """`--fix` in an interactive terminal still offers, and makes, its fixes."""
    root = init_project(tmp_path, monkeypatch)
    rules = root / "AUDIT_RULES.md"
    rules.write_text(rules.read_text() + "\n### CA-EXTRA-001 — an edit\n\nNew.\n")
    head = git("rev-parse", "HEAD", cwd=root)
    # Keys present, so the only offer --fix makes is the constitution commit.
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "test-credential-present")
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "test-credential-present")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    main.main(["doctor", "--fix"])
    assert git("rev-parse", "HEAD", cwd=root) != head
    assert git("log", "-1", "--format=%s", cwd=root) == "constitution: initial version"
