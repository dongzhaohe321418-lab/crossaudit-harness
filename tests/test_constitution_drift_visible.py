import argparse

from crossaudit.cli import main


def test_constitution_commit_state_requires_clean_tracked_rules(cfg):
    tracked, dirty = main.constitution_commit_state(cfg)
    assert tracked and not dirty
    const = cfg.root / cfg.constitution
    const.write_text(const.read_text(encoding="utf-8") + "\n### CA-EXTRA-001\n")
    tracked, dirty = main.constitution_commit_state(cfg)
    assert tracked and dirty


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
