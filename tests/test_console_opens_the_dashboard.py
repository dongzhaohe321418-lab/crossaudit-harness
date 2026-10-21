"""`crossaudit console` opens the dashboard for a person at a terminal.

README "4. Watch the loop live": the command "starts a local background
server, opens the dashboard, and prints a tokenized localhost URL". The
acceptance run (claim C28) found the URL printed and no browser ever invoked,
and no flag to control it. The rule now (D172 ruling 6): open with
`webbrowser.open` when stdout is a terminal, unless `--no-open` or `--json`;
never from the foreground server process. These tests run the real CLI in a
subprocess whose stdout is a pseudo-terminal (or a pipe), with `BROWSER`
pointed at a script that only logs its argument, and stop the background
console afterwards.

D10 mutation (checked by hand): make `_should_open_browser` return False and
the terminal case goes red; make it return True and the pipe, --no-open and
--json cases go red.
"""
from __future__ import annotations

import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import init_project  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="pty does not exist on Windows")

SRC = Path(__file__).resolve().parents[1] / "src"
URL = re.compile(r"http://127\.0\.0\.1:\d+/\?t=[\w-]{16,}")


def _env(log: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith("_proxy") and k != "CROSSAUDIT_CONSOLE_CHILD"}
    env["PYTHONPATH"] = str(SRC)
    script = log.with_suffix(".sh")
    script.write_text(f'#!/bin/sh\nprintf "%s\\n" "$1" >> "{log}"\n')
    script.chmod(0o755)
    env["BROWSER"] = f"{script} %s"
    return env


def _crossaudit(root: Path, env: dict, *argv: str, tty: bool) -> str:
    cmd = [sys.executable, "-c",
           "import sys; from crossaudit.cli.main import main; sys.exit(main())",
           *argv]
    if not tty:
        proc = subprocess.run(cmd, cwd=root, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return proc.stdout
    import pty

    leader, follower = pty.openpty()
    proc = subprocess.Popen(cmd, cwd=root, env=env, stdin=subprocess.DEVNULL,
                            stdout=follower, stderr=subprocess.PIPE)
    os.close(follower)
    chunks = []
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready, _, _ = select.select([leader], [], [], 0.2)
        if ready:
            try:
                data = os.read(leader, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
        elif proc.poll() is not None:
            break
    proc.wait(timeout=30)
    os.close(leader)
    assert proc.returncode == 0, proc.stderr.read()
    return b"".join(chunks).decode("utf-8", "replace")


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = init_project(tmp_path, monkeypatch)
    log = tmp_path / "browser.log"
    env = _env(log)
    yield root, env, log
    subprocess.run([sys.executable, "-c",
                    "import sys; from crossaudit.cli.main import main; sys.exit(main())",
                    "console", "--stop"], cwd=root, env=env,
                   capture_output=True, timeout=60)


def test_at_a_terminal_the_tokenized_url_is_opened(project):
    root, env, log = project
    out = _crossaudit(root, env, "console", tty=True)
    printed = URL.search(out)
    assert printed, out
    assert log.read_text().split() == [printed.group(0)]
    assert "Opened in your browser." in out
    # Reattaching to the running console opens it again, and nothing else.
    out = _crossaudit(root, env, "console", tty=True)
    assert log.read_text().split() == [printed.group(0)] * 2


@pytest.mark.parametrize("argv,tty", [
    (["console"], False),
    (["console", "--no-open"], True),
    (["--json", "console"], True),
], ids=["not-a-terminal", "no-open", "json"])
def test_otherwise_no_browser_is_invoked(project, argv, tty):
    root, env, log = project
    out = _crossaudit(root, env, *argv, tty=tty)
    assert URL.search(out), out
    assert not log.exists()


def test_help_names_no_open(capsys):
    from crossaudit.cli import main

    with pytest.raises(SystemExit):
        main.main(["console", "--help"])
    out = capsys.readouterr().out
    assert "--no-open" in out and "terminal" in out
