"""P15 — the build's own per-round commit cannot seal a credential into history.

The generator's work is committed by CrossAudit's build lifecycle (not a
model-proposed tool call), so it does not pass through the broker. It gets the
same defense-in-depth the brokered git_commit has: a round whose generated
changes look like a secret is refused, the secret is never committed, and the
run ends cleanly on the existing commit-refused path.
"""
from __future__ import annotations

from crossaudit.cli.build import _staged_secret
from crossaudit.gitio import git

GH_TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"


def test_staged_secret_helper_flags_a_credential(cfg):
    (cfg.root / "work").mkdir(parents=True, exist_ok=True)
    (cfg.root / "work/ok.txt").write_text("nothing to see here\n")
    git("add", "--", "work/ok.txt", cwd=cfg.root)
    assert _staged_secret(cfg) == ""                       # clean
    (cfg.root / "work/leak.txt").write_text(f"token = {GH_TOKEN}\n")
    git("add", "--", "work/leak.txt", cwd=cfg.root)
    assert "GitHub" in _staged_secret(cfg)                 # flagged, kind only
    assert GH_TOKEN not in _staged_secret(cfg)


def test_build_refuses_to_commit_a_generated_secret(science, cfg, transcripts,
                                                    monkeypatch):
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    def fake_generate(**_kwargs):
        return generator_mod.Work(
            summary="add deploy config",
            files={"experiments/demo/deploy.py": f"AWS_KEY = '{AWS_KEY}'\n"})

    monkeypatch.setattr(build_mod, "_generator_complete", lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)

    build_mod.run_loop(cfg, "add a deploy config")

    # The secret was NEVER sealed into git history (the round was refused).
    log = git("log", "-p", cwd=cfg.root, check=False)
    assert AWS_KEY not in log
    # And no cycle recorded a PASS on a secret-bearing commit.
    from crossaudit.controller import StateStore
    cycles = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot()["cycles"]
    assert all(c.get("status") != "PASSED" for c in cycles.values())
