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


def _is_local(host) -> bool:
    """Loopback by name or by address (127.0.0.0/8, ::1, ::ffff:127.x)."""
    import ipaddress

    text = str(host)
    if text.lower() in _LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def _peer_host(address):
    """The host of a socket address, or None for a unix socket / no address."""
    if isinstance(address, tuple) and address:
        return address[0]
    return None


@pytest.fixture(autouse=True)
def _sandboxed_keys_file_and_no_in_process_network(monkeypatch, tmp_path_factory):
    """Sandboxes the keys FILE and blocks IN-PROCESS outbound sockets.

    The old name was `_no_credentials_and_no_outbound_network`, which asserted a
    property this suite does not have. It was read as "the suite is hermetic" —
    by the engineering manager, in writing — and the name is what everything
    downstream reads. A narrower guard honestly named is worth more than a broad
    one that is wrong.

    WHAT IS COVERED
      * `CROSSAUDIT_KEYS_FILE` is moved to a temp path. `wizard.keys_file()`
        resolves `DEFAULT_KEYS_FILE` from the real home at import, so setting
        `HOME` does not move it; exactly one test file was sandboxing it and
        every other test could load the developer's real keys.
      * `socket.socket.connect`, `connect_ex`, `sendto` and `sendmsg` are
        refused for any non-loopback peer, FOR CALLS MADE IN THIS PROCESS
        through the Python `socket.socket` class (which `ssl`, `http.client`,
        `urllib`, `asyncio` and `socket.create_connection` all go through).
        With a key loaded, provider code makes live calls, and a test that
        passes when the network is up and fails when it blinks is
        non-deterministic for a reason nobody is looking at.
      * Loopback stays open — TCP and UDP — because the console tests serve
        on it.

    WHAT IS **NOT** COVERED, and both were measured rather than supposed
      * **A SUBPROCESS.** A Python-level patch cannot reach a child process. A
        census of 9,889 children in one full run found four invocations that
        genuinely leave the machine — `gh auth status` and `gh api user`, via
        `github_status()` → `pair._owner()` — from
        test_console_strings_by_execution.py. `git`, `gh` and `codex` are the
        known network-capable children; the 9,385 `git` calls were all local
        (no fetch, push, clone, ls-remote or pull).
      * **THE LOGIN KEYCHAIN.** `security find-generic-password` reads the
        developer's real keychain. This fixture moves the keys FILE; the
        keychain is a different channel and is not moved.
      * **DNS RESOLUTION.** `socket.getaddrinfo` (and `gethostbyname`) is not
        patched: a name lookup leaves the machine, in this process, before any
        socket is connected. `mcp.py` and `broker/tools_research.py` call
        `getaddrinfo`, so this is a product path, not a hypothetical.
      * **THE RAW `_socket.socket`.** The patch is on the Python class
        `socket.socket`; a caller that instantiates the C-level
        `_socket.socket` directly bypasses it (measured: a SYN to TEST-NET
        left the machine).

    Whether the suite should need the network at all is a decision, not a
    defect, and is held separately. This docstring exists so nobody concludes
    it has already been made.

    One correction to this file's own history: an earlier version of this
    docstring called a `RemoteDisconnected` failure "a real socket", which was
    read as evidence of egress. A recorder over `socket.connect` that was never
    torn down logged 290 connects in a full run and **every one was 127.0.0.1**.
    That failure was a local console server closing, not the open network.
    """
    import socket

    monkeypatch.setenv(
        "CROSSAUDIT_KEYS_FILE",
        str(tmp_path_factory.mktemp("keys") / "crossaudit-keys.env"))

    def refuse_unless_local(address):
        host = _peer_host(address)
        if host is not None and not _is_local(host):
            raise AssertionError(
                f"a test tried to open a network connection to {host!r}. Tests "
                f"must not reach the network: stub the provider, or use the "
                f"`replay` provider, which ships for exactly this.")

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_sendmsg = socket.socket.sendmsg

    def guarded_connect(self, address):
        refuse_unless_local(address)
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        refuse_unless_local(address)
        return real_connect_ex(self, address)

    def guarded_sendto(self, data, *rest):
        # sendto(data, address) or sendto(data, flags, address)
        if rest:
            refuse_unless_local(rest[-1])
        return real_sendto(self, data, *rest)

    def guarded_sendmsg(self, buffers, *rest):
        # sendmsg(buffers[, ancdata[, flags[, address]]])
        if len(rest) >= 3:
            refuse_unless_local(rest[2])
        return real_sendmsg(self, buffers, *rest)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket.socket, "sendmsg", guarded_sendmsg)
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


@pytest.fixture(autouse=True)
def _hermetic_credentials(monkeypatch):
    """The credential preflight must see the same world on every machine.

    It checks presence only (env variable, else the app's Keychain presence
    API). Without this, a suite passed on a laptop whose Keychain held an
    OpenAI key and failed on one that did not -- three CLI build tests
    reddened the night the key was removed. A test that wants the keyless
    world deletes these itself (tests/test_setup_preflight.py does).
    """
    for name in ("CROSSAUDIT_GENERATOR_KEY", "CROSSAUDIT_AUDITOR_KEY"):
        if not os.environ.get(name):
            monkeypatch.setenv(name, "test-credential-present")


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


# ------------------------------------------------------------- denial log
# Opt-in recorder for the refusals a run of the suite actually constructs,
# so `tests/fixtures/denial_reasons_runtime.jsonl` can be regenerated:
#   CROSSAUDIT_DENIAL_LOG=/path/to/log.jsonl pytest tests
# Off unless the variable is set; it patches nothing otherwise.
def _install_denial_log() -> None:
    import json
    import os

    path = os.environ.get("CROSSAUDIT_DENIAL_LOG")
    if not path:
        return
    from crossaudit import errors

    original = errors.Denial.__init__

    def recording(self, reason, *args, **kwargs):
        original(self, reason, *args, **kwargs)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"kind": type(self).__name__,
                                     "reason": str(reason)}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    errors.Denial.__init__ = recording


_install_denial_log()
