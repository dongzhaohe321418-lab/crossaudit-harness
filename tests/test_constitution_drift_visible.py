import argparse

from crossaudit import doctor_shared
from crossaudit.cli import main


def test_constitution_state_requires_clean_tracked_rules(cfg):
    """The three states, from the ONE helper both doctors now consume.

    This used to test `main.constitution_commit_state`, a second implementation
    of the same question that happened to agree with this one. The duplicate is
    deleted, so the test moved to the survivor rather than being deleted with it.
    """
    status, detail = doctor_shared.constitution_state(cfg)
    assert status == "ready"
    assert detail == doctor_shared.CONSTITUTION_READY_SENTENCE

    const = cfg.root / cfg.constitution
    const.write_text(const.read_text(encoding="utf-8") + "\n### CA-EXTRA-001\n")
    status, detail = doctor_shared.constitution_state(cfg)
    assert status == "drifted"
    assert "uncommitted changes" in detail

    # "missing" means never committed, not removed: `git log -- <path>` still
    # finds history after a delete, and an audit could still cite that commit.
    from dataclasses import replace as _replace
    never = _replace(cfg, constitution="NEVER_COMMITTED.md")
    (cfg.root / "NEVER_COMMITTED.md").write_text("# not tracked\n")
    status, detail = doctor_shared.constitution_state(never)
    assert status == "missing"
    assert "not tracked" in detail


def test_doctor_excludes_uncommitted_constitution_from_pass_tally(
        cfg, monkeypatch, capsys):
    monkeypatch.chdir(cfg.root)
    args = argparse.Namespace(json=False, all=True, fix=False, online=False)
    const = cfg.root / cfg.constitution
    const.write_text(const.read_text(encoding="utf-8") + "\n### CA-EXTRA-002\n")
    assert main.cmd_doctor(args) != 0
    output = capsys.readouterr().out
    assert "constitution committed" in output
    assert "has uncommitted changes" in output
