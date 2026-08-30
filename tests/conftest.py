"""Fixtures for the delivery tests: a real git science repo and a live config.

Everything runs against the installed package in a temporary directory. No test
touches the developer's home, the repository's own state, or the network.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.scaffold import read as read_template


#: Loopback and unix sockets are the suite's own servers and are always allowed.
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}


@pytest.fixture(autouse=True)
def _no_credentials_and_no_outbound_network(monkeypatch, tmp_path_factory):
    """No test may reach the developer's credentials or the open network.

    Both channels were open and both produced real defects.

    CREDENTIALS. `wizard.keys_file()` resolves `DEFAULT_KEYS_FILE`, computed
    from the real home at import, so setting `HOME` does not move it. Exactly
    one test file was sandboxing it; every other test could load the developer's
    real keys. A suite whose behaviour depends on whether the developer happens
    to have credentials is not a suite.

    NETWORK. With a key loaded, provider code makes live calls. Three
    consecutive full runs failed with three DIFFERENT tests in
    `test_projects_ui.py`, and one failure was `http.client.RemoteDisconnected`
    — not load, a real socket. A test that passes when the network is up and
    fails when it blinks is non-deterministic for a reason nobody was looking
    at, and re-running it in isolation "to confirm the flake" confirmed only
    that the network was up again.

    Loopback stays open, because the console tests serve on it.
    """
    import socket

    monkeypatch.setenv(
        "CROSSAUDIT_KEYS_FILE",
        str(tmp_path_factory.mktemp("keys") / "crossaudit-keys.env"))

    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else None
        if host is not None and str(host) not in _LOCAL_HOSTS:
            raise AssertionError(
                f"a test tried to open a network connection to {host!r}. Tests "
                f"must not reach the network: stub the provider, or use the "
                f"`replay` provider, which ships for exactly this.")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield


@pytest.fixture(autouse=True)
def _reset_progress_tracker():
    """The progress tracker is a process-global singleton. A test that leaves a
    run bound to it would otherwise bleed a live-progress view into the next
    module's snapshot (e.g. shadowing an HPC job's actor). Reset after each test
    so ordering cannot make one module's state leak into another's."""
    yield
    from crossaudit.console.progress import TRACKER

    TRACKER.clear()

GOOD_RESULTS = {
    "quantities": [
        {"name": "binding_energy", "value": -3.65, "unit": "kcal/mol",
         "source": "scripts/run_demo.py@a1b2c3d"},
        {"name": "distance", "value": 2.73, "unit": "angstrom",
         "source": "scripts/run_demo.py@a1b2c3d"},
    ],
    "convergence": {"converged": True, "achieved": 7.4e-07, "threshold": 1e-06},
}

BAD_RESULTS = {
    "quantities": [
        {"name": "binding_energy", "value": -3.65, "unit": "kcal/mol",
         "source": "legacy_fit.py@1692761"},
        {"name": "distance", "value": 2.73, "source": "scripts/run_demo.py@a1b2c3d"},
    ],
    "convergence": {"converged": False, "achieved": 7.4e-07, "threshold": 1e-06},
}

METADATA = "code_version: a1b2c3d\ninputs:\n  - scripts/run_demo.py@a1b2c3d\n"

CONFIG = """\
version: 1
science_repo: lab/science
constitution: AUDIT_RULES.md
max_rounds: 3
auditor:
  vendor: anthropic
  provider: replay
  model: claude-fable-5
  key_env: CROSSAUDIT_AUDITOR_KEY
generator:
  vendor: openai
isolation:
  minimum:
    parametric: true
    contextual: true
    permissive: false
ledger:
  dir: cycles
state:
  dir: .crossaudit
checks: [schema, units, convergence, provenance]
"""


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture()
def science(tmp_path: Path) -> Path:
    repo = tmp_path / "science"
    (repo / "experiments" / "demo").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    git("config", "user.email", "lab@example.invalid", cwd=repo)
    git("config", "user.name", "Lab", cwd=repo)
    (repo / "AUDIT_RULES.md").write_text(read_template("AUDIT_RULES.md"))
    (repo / "crossaudit.yml").write_text(CONFIG)
    (repo / ".gitignore").write_text(".crossaudit/\n")
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "bootstrap", cwd=repo)
    return repo


def write_increment(repo: Path, results: dict, summary: str, message: str) -> str:
    d = repo / "experiments" / "demo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "metadata.yml").write_text(METADATA)
    (d / "results.json").write_text(json.dumps(results, indent=1))
    (d / "SUMMARY.md").write_text(summary)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


@pytest.fixture()
def cfg(science: Path):
    return load(science / "crossaudit.yml")


@pytest.fixture()
def transcripts(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "transcripts"
    d.mkdir()
    monkeypatch.setenv("CROSSAUDIT_REPLAY_DIR", str(d))
    return d


def record_reply(transcripts: Path, cfg, sha: str, reply: dict, scope: str = "experiments"):
    """Record what the auditor will answer for this exact prompt."""
    import subprocess as sp

    from crossaudit.auditor import prompt as pm
    from crossaudit.dcl import run_checks
    from crossaudit.gitio import materialise
    from crossaudit.providers import replay

    files, notes = materialise(cfg.root, sha, scope)
    dcl = run_checks(files, cfg.checks, notes).as_dict()
    const = (cfg.root / cfg.constitution).read_text()
    cc = sp.run(["git", "log", "-1", "--format=%H", "--", cfg.constitution],
                cwd=str(cfg.root), capture_output=True, text=True).stdout.strip()
    prompt, _bounded, _sha = pm.build(const, cc, dcl, files)
    return replay.record(transcripts, system=pm.SYSTEM, prompt=prompt,
                         text=json.dumps(reply))


PASS_REPLY = {"verdict": "PASS",
              "sections_applied": ["CA-DATA-001", "CA-METH-002"],
              "findings": []}
