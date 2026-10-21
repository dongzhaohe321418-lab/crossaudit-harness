"""A project made the way the README makes one, for the README-flow tests.

The black-box acceptance run (benchmarks/claims) found gaps between README
sentences and the product by running the documented commands on a project the
documented command created. These helpers do the same in-process: the project
comes from the real `crossaudit init ... --no-console` with stdin not a
terminal (pytest's stdin is not one), never from a hand-written fixture, so a
test cannot pass on a shape `init` does not produce.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

INIT_ARGV = ["--no-console",
             "--auditor-vendor", "openai", "--auditor-model", "gpt-5.6-terra",
             "--generator-vendor", "anthropic",
             "--generator-model", "claude-sonnet-4-6"]


def init_project(tmp_path: Path, monkeypatch, name: str = "proj") -> Path:
    """Run the README's non-interactive `init` and chdir into the project."""
    from crossaudit.cli import main

    monkeypatch.chdir(tmp_path)
    assert main.main(["init", name, *INIT_ARGV]) == 0
    root = (tmp_path / name).resolve()
    monkeypatch.chdir(root)
    return root


def tree_digest(root: Path) -> dict[str, str]:
    """Every file under ``root`` (``.git`` and ``.crossaudit`` included) by
    content digest, plus every directory, so a created empty directory counts
    as a change too."""
    out: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            out[rel + "/"] = "dir"
        elif path.is_file():
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out
