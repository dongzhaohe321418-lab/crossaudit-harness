"""Two CI failures of PR #7, both in our code (2026-10-24).

* The `quality` job configures no git identity, and the ledger-row commits
  ran a plain `git commit`, so every escalation and ruling failed there.
  Every ledger-row commit now passes an explicit identity: the repository's
  `user.name`/`user.email` when both are set, else the product's default
  `CrossAudit <crossaudit@local.invalid>`; the row's `by` records exactly it.
* `_ordered_cycles` broke ties on whole-second history times by the hash id,
  so a fast runner showed the older cycle as newest. It now breaks them by
  the position of each cycle's last event in the chronological history.

Each test names the mutation it catches.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import tuiapp
from crossaudit.config import load
from crossaudit.console.server import _ordered_cycles
from crossaudit.controller import StateStore

CONFIG = ("version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
          "auditor: {vendor: openai, provider: openai_compat, model: m,"
          " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
          "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\nchecks: [parseable]\n")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    (root / ".gitignore").write_text(".crossaudit/\n")
    return root


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture()
def no_identity(tmp_path, monkeypatch):
    """No git identity anywhere: no global or system config, an empty HOME."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                 "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(name, raising=False)


def test_ledger_rows_commit_with_the_default_identity_when_none_is_configured(
        tmp_path, no_identity):
    """Mutation caught: a ledger-row commit without the explicit `-c
    user.name/user.email` pair -- git refuses ("Author identity unknown"),
    the escalation is not committed and the ruling cannot be made."""
    root = _project(tmp_path)
    cfg = load(root / "crossaudit.yml")
    store = StateStore(root / ".crossaudit" / "state.json")
    cid = store.open_or_advance("t/p", "a" * 40, None)["cycle_id"]
    store.escalate(cid, "round budget spent")
    assert store.cycle(cid)["escalation_commit"], store.cycle(cid).get("escalation_error")
    rulings.rule(cfg, store, cid, "close", "ruled where no identity is configured")
    authors = _git(root, "log", "--format=%an <%ae>|%cn <%ce>").splitlines()
    assert authors == ["CrossAudit <crossaudit@local.invalid>|"
                       "CrossAudit <crossaudit@local.invalid>"] * 2
    rows = [json.loads(ln) for ln in (root / "cycles" / "rulings.jsonl")
            .read_text().split("\n") if ln]
    assert [r["by"] for r in rows] == ["CrossAudit <crossaudit@local.invalid>"] * 2
    assert store.cycle(cid)["status"] == "BLOCKED"


def test_a_configured_identity_is_the_one_the_rows_carry(tmp_path, no_identity):
    """The repository's own identity wins when both name and email are set,
    and `by` names the same author as the commit. Mutation caught: always
    using the default (the row would misname a configured author)."""
    root = _project(tmp_path)
    _git(root, "config", "user.name", "Ada Lab")
    _git(root, "config", "user.email", "ada@lab.invalid")
    cfg = load(root / "crossaudit.yml")
    store = StateStore(root / ".crossaudit" / "state.json")
    cid = store.open_or_advance("t/p", "b" * 40, None)["cycle_id"]
    store.escalate(cid, "round budget spent")
    rulings.rule(cfg, store, cid, "reopen", "with the lab's identity")
    assert _git(root, "log", "--format=%an <%ae>").splitlines() == [
        "Ada Lab <ada@lab.invalid>"] * 2
    rows = [json.loads(ln) for ln in (root / "cycles" / "rulings.jsonl")
            .read_text().split("\n") if ln]
    assert [r["by"] for r in rows] == ["Ada Lab <ada@lab.invalid>"] * 2


# ---------------------------------------------------------------- ordering
def _state_with_a_tie() -> dict:
    """Two cycles whose events share one whole second; the PASSED cycle's
    events come first in the history, the ESCALATED cycle's later. The ids
    are chosen so that id order alone would put the ESCALATED one oldest."""
    passed, escalated = "bbbbbbbbbbbbbbbb", "aaaaaaaaaaaaaaaa"
    cycle = {"round": 1, "active_sha": "c" * 40, "repo": "t/p", "root_sha": "c" * 40,
             "parent_receipt": "", "consumed": [], "updated_at": 1000}
    return {"schema": 1,
            "cycles": {passed: dict(cycle, status="PASSED"),
                       escalated: dict(cycle, status="ESCALATED")},
            "history": [{"t": 1000, "event": "opened", "cycle": passed},
                        {"t": 1000, "event": "noted", "cycle": passed},
                        {"t": 1000, "event": "opened", "cycle": escalated},
                        {"t": 1000, "event": "noted", "cycle": escalated}]}


def test_a_tie_in_time_is_broken_by_recorded_order_not_by_id():
    """Mutation caught: dropping the history index from the sort key -- the
    hash id decides and the ESCALATED cycle reads as the oldest."""
    ordered = _ordered_cycles(_state_with_a_tie())
    assert [c["id"] for c in ordered] == ["bbbbbbbbbbbbbbbb", "aaaaaaaaaaaaaaaa"]


def test_the_tui_shows_the_later_cycle_first_on_a_tie(tmp_path):
    """The same tie through the TUI's frame (newest first). Mutation caught:
    the same -- the PASSED cycle would come first."""
    root = _project(tmp_path)
    _git(root, "-c", "user.name=harness", "-c", "user.email=harness@example.invalid",
         "add", "-A")
    _git(root, "-c", "user.name=harness", "-c", "user.email=harness@example.invalid",
         "commit", "-q", "-m", "boot")
    (root / ".crossaudit").mkdir()
    (root / ".crossaudit" / "state.json").write_text(json.dumps(_state_with_a_tie()))
    frame = tuiapp.frame(load(root / "crossaudit.yml"))
    assert [c["id"] for c in frame["cycles"]] == ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"]


# ------------------------------------------------ ambient identity (ruling 55)
def _escalate_and_rule(root: Path, sha: str) -> list[dict]:
    cfg = load(root / "crossaudit.yml")
    store = StateStore(root / ".crossaudit" / "state.json")
    cid = store.open_or_advance("t/p", sha * 40, None)["cycle_id"]
    store.escalate(cid, "round budget spent")
    assert store.cycle(cid)["escalation_commit"], store.cycle(cid).get("escalation_error")
    rulings.rule(cfg, store, cid, "close", "ruled with ambient identity variables")
    return [json.loads(ln) for ln in (root / "cycles" / "rulings.jsonl")
            .read_text().split("\n") if ln]


def _assert_one_person(root: Path, rows: list[dict], expected: str) -> None:
    """The row's `by`, the commit's author and its committer are one string,
    for the escalation row and the ruling row alike."""
    assert [r["by"] for r in rows] == [expected, expected]
    name, email = expected[:-1].split(" <")
    for line in _git(root, "log", "--format=%an|%ae|%cn|%ce").splitlines():
        assert line == f"{name}|{email}|{name}|{email}", line


def test_ambient_author_variables_are_the_identity_of_row_author_and_committer(
        tmp_path, no_identity, monkeypatch):
    """GIT_AUTHOR_* set (and a different GIT_COMMITTER_*), the repository
    configured differently: the ambient author wins, and author, committer
    and `by` all carry it. Mutation caught: setting only the author variables
    in the child environment -- the committer would stay the ambient
    committer."""
    root = _project(tmp_path)
    _git(root, "config", "user.name", "Repo Config")
    _git(root, "config", "user.email", "repo@config.invalid")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ambient Author")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "author@ambient.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Ambient Committer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "committer@ambient.invalid")
    rows = _escalate_and_rule(root, "d")
    _assert_one_person(root, rows, "Ambient Author <author@ambient.invalid>")


def test_a_configured_identity_overrides_ambient_committer_variables(
        tmp_path, no_identity, monkeypatch):
    """The repository configured, only GIT_COMMITTER_* in the environment:
    the configured identity on row, author and committer. Mutation caught:
    dropping the committer variables from the child environment (git would
    record the ambient committer)."""
    root = _project(tmp_path)
    _git(root, "config", "user.name", "Ada Lab")
    _git(root, "config", "user.email", "ada@lab.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Ambient Committer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "committer@ambient.invalid")
    rows = _escalate_and_rule(root, "e")
    _assert_one_person(root, rows, "Ada Lab <ada@lab.invalid>")


def test_with_nothing_configured_ambient_committer_variables_do_not_leak(
        tmp_path, no_identity, monkeypatch):
    """Nothing configured, only GIT_COMMITTER_* set: the default identity on
    row, author and committer. Mutation caught: the same."""
    root = _project(tmp_path)
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Ambient Committer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "committer@ambient.invalid")
    rows = _escalate_and_rule(root, "f")
    _assert_one_person(root, rows, "CrossAudit <crossaudit@local.invalid>")
