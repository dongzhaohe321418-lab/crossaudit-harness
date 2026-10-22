"""No child that is not a provider path inherits a provider key (D170, S1).

`app_keys.load_into_environment()` puts every Keychain key into `os.environ`
of the core process. Before D170 every child it launched -- Git, the GitHub
CLI, OpenSSH, the Codex app-server -- inherited all of them, while SECURITY.md
said keys were injected "only into the local core process". Each launch site
now passes `env=app_keys.child_env()`.

The behavioural tests below drive the real function at each launch site with
`subprocess.run` / `subprocess.Popen` replaced by a recorder, export dummy keys,
and assert over the `env=` the child would have received. The sweep at the end
is structural and says so: it parses `src/` and fails on any `subprocess.run`
or `subprocess.Popen` call without an `env=` keyword outside the four places
that deliberately build their own environment -- it exists so a NEW launch
site cannot silently inherit the keys, which no behavioural test of the old
sites would notice.

D10 mutations run by hand: `child_env` returning `dict(base)` -> every
behavioural test red; dropping `env=child_env()` from `gitio.git` -> the gitio
case and the structural sweep red; dropping the `_API_KEY` rule from
`provider_key_names` -> the OPENAI_API_KEY / ANTHROPIC_API_KEY assertions red.
"""
from __future__ import annotations

import ast
import io
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import app_keys

SRC = Path(__file__).resolve().parents[1] / "src" / "crossaudit"

DUMMY_KEYS = {
    "OPENAI_API_KEY": "sk-dummy-openai-must-not-reach-a-child",
    "ANTHROPIC_API_KEY": "sk-ant-dummy-must-not-reach-a-child",
    "CROSSAUDIT_AUDITOR_KEY": "dummy-auditor-key-must-not-reach-a-child",
}
KEPT = ("PATH", "HOME", "LANG")


class _FakePopen:
    def __init__(self, args, **kw):
        self.args = args
        text = kw.get("text") or kw.get("encoding") or kw.get("universal_newlines")
        empty = (lambda: io.StringIO("")) if text else (lambda: io.BytesIO(b""))
        self.stdin = empty() if kw.get("stdin") == subprocess.PIPE else None
        self.stdout = empty()
        self.stderr = empty()
        self.returncode = 0
        self.pid = 4242

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def communicate(self, input=None, timeout=None):
        return self.stdout.read(), self.stderr.read()

    def terminate(self):
        pass

    def kill(self):
        pass


@pytest.fixture
def launched(monkeypatch):
    """Export dummy keys and record the environment of every child launch."""
    for name, value in DUMMY_KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("HOME", "/home/someone")
    envs: list[dict | None] = []

    def fake_run(args, **kw):
        envs.append(kw.get("env"))
        text = kw.get("text") or kw.get("encoding")
        out = "" if text else b""
        return subprocess.CompletedProcess(args, 0, stdout=out, stderr=out)

    def fake_popen(args, **kw):
        envs.append(kw.get("env"))
        return _FakePopen(args, **kw)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    return envs


def _assert_clean(envs):
    assert envs, "the driver launched no child; the test exercised nothing"
    for env in envs:
        assert env is not None, "a child was launched with the full parent environment"
        leaked = sorted(set(env) & set(DUMMY_KEYS))
        assert not leaked, f"provider keys reached a child: {leaked}"
        for value in DUMMY_KEYS.values():
            assert value not in env.values()
        for name in KEPT:
            assert name in env, f"{name} was stripped too; children need it"


def _quiet(call):
    """Run a driver; output parsing may refuse the recorder's empty output."""
    try:
        call()
    except Exception:  # noqa: BLE001 -- only the launch is under test here
        pass


def _cfg(tmp_path):
    return SimpleNamespace(root=tmp_path, state_dir=".crossaudit",
                           ledger_dir="audit/ledger")


# ------------------------------------------------------------------ git


@pytest.mark.parametrize("site", [
    "git", "git_bytes", "is_repo", "entries", "_stream_blob", "is_ancestor",
    "commit_exists"])
def test_gitio_children_get_no_provider_key(site, launched, tmp_path):
    from crossaudit import gitio
    drivers = {
        "git": lambda: gitio.git("status", cwd=tmp_path),
        "git_bytes": lambda: gitio.git_bytes("cat-file", "blob", "x", cwd=tmp_path),
        "is_repo": lambda: gitio.is_repo(tmp_path),
        "entries": lambda: gitio.entries(tmp_path, "HEAD"),
        "_stream_blob": lambda: gitio._stream_blob(tmp_path, "abc", 10),
        "is_ancestor": lambda: gitio.is_ancestor(tmp_path, "a", "b"),
        "commit_exists": lambda: gitio.commit_exists(tmp_path, "a"),
    }
    _quiet(drivers[site])
    _assert_clean(launched)


@pytest.mark.parametrize("site", ["commits", "chat_map", "has_evidence",
                                  "owned_target", "remote_repo", "candidate_worktree"])
def test_other_git_children_get_no_provider_key(site, launched, tmp_path):
    from crossaudit import admission, document_export
    from crossaudit.broker import selfimprove
    from crossaudit.console import chats, streams
    drivers = {
        "commits": lambda: streams._commits(tmp_path, 5),
        "chat_map": lambda: streams._chat_map(tmp_path, 5),
        "has_evidence": lambda: chats._has_evidence(_cfg(tmp_path), "chat-1"),
        "owned_target": lambda: document_export._owned_target(tmp_path, "a.md"),
        "remote_repo": lambda: admission._remote_repo(tmp_path),
        "candidate_worktree": lambda: selfimprove.candidate_worktree(
            _cfg(tmp_path), "HEAD"),
    }
    _quiet(drivers[site])
    _assert_clean(launched)


def test_wizard_git_and_editor_children_get_no_provider_key(
        launched, tmp_path, monkeypatch):
    from crossaudit.cli import wizard
    monkeypatch.setattr(wizard.shutil, "which", lambda _name: "/usr/bin/gh")
    monkeypatch.setenv("EDITOR", "true")
    _quiet(wizard.gh_available)
    _quiet(lambda: wizard.prepare(tmp_path / "fresh"))
    _quiet(lambda: wizard.tracked_paths(tmp_path, ["a.md"]))
    _quiet(lambda: wizard.commit_setup(tmp_path, ["a.md"]))
    _quiet(lambda: wizard._open_in_editor(tmp_path / "a.md"))
    assert len(launched) >= 5
    _assert_clean(launched)


# ------------------------------------------------------------------ gh


def test_github_cli_children_get_no_provider_key(launched, tmp_path, monkeypatch):
    from crossaudit import admission
    from crossaudit.broker import tools_git
    from crossaudit.cli import pair
    monkeypatch.setattr(pair, "gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(admission.shutil, "which", lambda _name: "/usr/bin/gh")
    _quiet(lambda: pair._gh("api", "user"))
    _quiet(pair.github_scopes)
    _quiet(lambda: pair._exists("owner/repo"))
    _quiet(lambda: pair._git(tmp_path, "status"))
    _quiet(lambda: pair._sync_existing_main(tmp_path))
    _quiet(lambda: admission._gh("api", "user"))
    _quiet(lambda: tools_git.repo_create(_cfg(tmp_path), {"name": "r"}, None))
    assert len(launched) >= 7
    _assert_clean(launched)


def test_github_auth_status_child_gets_no_provider_key(launched, monkeypatch):
    from crossaudit.cli import pair
    monkeypatch.setattr(pair.shutil, "which", lambda _name: "/usr/bin/gh")
    monkeypatch.delenv("CROSSAUDIT_BUNDLED_GH", raising=False)
    _quiet(pair.gh)
    _assert_clean(launched)


def test_github_device_login_child_gets_no_provider_key(launched, monkeypatch):
    from crossaudit.console import projects
    monkeypatch.setattr(projects, "github_status", lambda force=False: {
        "connected": False, "owner": None, "detail": "not connected"})
    monkeypatch.setattr(projects.shutil, "which", lambda _name: "/usr/bin/gh")
    jobs = projects.GithubAuthJobs()
    jobs.start(lambda: None)
    assert jobs.wait(5)
    _assert_clean(launched)
    # The two variables this launch adds on purpose survive the scrub.
    assert launched[0]["GH_PROMPT_DISABLED"] == "1"
    assert launched[0]["BROWSER"] == "/usr/bin/false"


# ------------------------------------------------------------------ ssh


@pytest.mark.parametrize("site", ["expanded", "run", "stream", "send_file"])
def test_openssh_children_get_no_provider_key(site, launched, tmp_path):
    from crossaudit import hpc
    ssh = hpc.OpenSSH("/usr/bin/ssh")
    source = tmp_path / "input.dat"
    source.write_bytes(b"x")
    drivers = {
        "expanded": lambda: ssh.expanded("cluster"),
        "run": lambda: ssh.run("cluster", "true"),
        "stream": lambda: ssh.stream("cluster", "true"),
        "send_file": lambda: ssh.send_file("cluster", source, "/scratch/in/input.dat"),
    }
    _quiet(drivers[site])
    _assert_clean(launched)
    assert launched[0]["LC_ALL"] == "C"


# ------------------------------------------------------------------ codex


def test_codex_app_server_gets_no_provider_key(launched, monkeypatch):
    """The subscription runtime authenticates with its own ChatGPT login
    (stored under HOME / CODEX_HOME); it needs no provider key, and an
    OPENAI_API_KEY in its environment is exactly what could move it off the
    subscription."""
    from crossaudit.providers import codex_subscription
    monkeypatch.setenv("CODEX_HOME", "/home/someone/.codex")
    server = codex_subscription.CodexAppServer("/fake/codex")
    monkeypatch.setattr(server, "call", lambda *a, **k: {})
    monkeypatch.setattr(server, "notify", lambda *a, **k: None)
    server._start()
    _assert_clean(launched)
    assert launched[0]["CODEX_HOME"] == "/home/someone/.codex"


# ------------------------------------------------------------------ other local tools


def test_local_tool_children_get_no_provider_key(launched, monkeypatch):
    from crossaudit import app_doctor
    from crossaudit.runtime import processes
    monkeypatch.setattr(app_keys, "_security", lambda: "/usr/bin/security")
    _quiet(lambda: app_doctor._run("/usr/bin/git", "--version"))
    _quiet(lambda: app_keys.read("openai"))
    _quiet(lambda: app_keys.remove("mistral"))
    monkeypatch.setattr(processes, "Path", lambda _p: SimpleNamespace(
        is_file=lambda: False))
    _quiet(lambda: processes._start_marker(1))
    _quiet(lambda: processes.zombie(1))
    assert len(launched) >= 5
    _assert_clean(launched)


# ------------------------------------------------------------------ the helper


def _every_stripped_name():
    names = set(app_keys.PROVIDER_ENVS.values())
    names |= {app_keys.backup_env_for_vendor(v) for v in app_keys.PROVIDER_ENVS}
    names |= set(app_keys.ROLE_FALLBACKS.values())
    names |= {"CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY",
              "CROSSAUDIT_DEMO_KEY", "CROSSAUDIT_SOMETHING_NEW_KEY",
              "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
              "CODEX_API_KEY", "MISTRAL_API_KEY"}
    return sorted(names)


@pytest.mark.parametrize("name", _every_stripped_name())
def test_child_env_strips_every_provider_key_name(name):
    base = {"PATH": "/usr/bin", "HOME": "/h", "LANG": "C", name: "secret-value"}
    env = app_keys.child_env(base)
    assert name not in env
    assert env == {"PATH": "/usr/bin", "HOME": "/h", "LANG": "C"}


@pytest.mark.parametrize("name", [
    "GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "GIT_ASKPASS", "CODEX_HOME",
    "CROSSAUDIT_BUNDLED_CODEX", "CROSSAUDIT_KEYS_FILE", "KEYCHAIN", "API_KEY_HELP",
    "CROSSAUDIT_KEYS_DIR", "TERM", "LC_ALL"])
def test_child_env_keeps_what_git_gh_ssh_and_codex_need(name):
    base = {name: "value", "PATH": "/usr/bin"}
    assert app_keys.child_env(base) == base


def test_child_env_does_not_mutate_the_parent_environment(monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "kept-in-the-core")
    env = app_keys.child_env()
    assert "CROSSAUDIT_OPENAI_KEY" not in env
    import os
    assert os.environ["CROSSAUDIT_OPENAI_KEY"] == "kept-in-the-core"


def test_child_env_extra_is_applied_after_the_scrub():
    env = app_keys.child_env({"PATH": "/p", "OPENAI_API_KEY": "x"}, LC_ALL="C")
    assert env == {"PATH": "/p", "LC_ALL": "C"}


# ------------------------------------------------------------------ structural sweep

#: Launch sites that build their own environment on purpose, and why.
#:  * mcp.py -- a stdio MCP server gets `_stdio_environment()`, an allowlist of
#:    eight OS variables, narrower than child_env (its Keychain `security`
#:    calls are in a file another branch owns; see D170 "open").
#:  * broker/tools_command.py -- `run_check` gets `_scrubbed_env()`, which
#:    removes every *KEY*/*TOKEN*/*SECRET* name: narrower for that child.
#:  * console/daemon.py -- a project worker runs the providers itself; it must
#:    inherit the keys.
#:  * app.py -- the frozen app's bootstrap `git` calls; owned by another branch
#:    in this round and left for a follow-up (D170 "open").
EXEMPT = {"mcp.py", "broker/tools_command.py", "console/daemon.py", "app.py"}


def test_every_launch_site_outside_the_exemptions_passes_an_env():
    """Structural: a new subprocess call without `env=` fails here."""
    missing = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in EXEMPT:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in {"run", "Popen", "call", "check_call",
                                           "check_output"}):
                envs = [k for k in node.keywords if k.arg == "env"]
                if not envs or "child_env" not in ast.unparse(envs[0].value):
                    missing.append(f"{rel}:{node.lineno}")
    assert missing == [], f"launch sites without env=child_env(...): {missing}"
