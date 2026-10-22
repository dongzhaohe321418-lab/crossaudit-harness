"""`crossaudit pair`: the plan is the list of what `--apply` does (D173).

README, "Two-repository deployment": "Without `--apply`, `pair` prints the
intended GitHub operations and changes nothing remotely. Review the plan before
creating repositories or secrets."

The claims harness found that sentence untrue in two ways: `--apply` pushed
the local history, committed the pair and added an `origin` remote although no
plan step named them; and the plan's branch-protection step was never applied.

These tests run the real `pair` (through `main`, so exit codes are the CLI's)
with a fake `gh` and a recording `git` wrapper on PATH, every
`https://github.com/` URL rewritten to a local bare repository and no transport
but `file` allowed, so nothing reaches the network. They compare what was
EXECUTED (the wrappers' argv log) with what was PRINTED (the plan's `$ `
lines), one for one and in order — not the plan function against itself.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from crossaudit.cli import main as cli_main
from crossaudit.config import load

REAL_GIT = shutil.which("git")

FAKE_GH = r"""#!/bin/sh
# Logs argv (tab-separated) and never touches the network. MODE: auth|unauth.
DIR="$(cd "$(dirname "$0")" && pwd)"
{ printf 'gh'; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$LOG"
MODE="$(cat "$DIR/mode")"
case "$1 $2" in
  "auth status")
    if [ "$MODE" = auth ]; then echo "Logged in to github.com account harness-bot" >&2; exit 0; fi
    echo "You are not logged into any GitHub hosts. To log in, run: gh auth login" >&2; exit 1 ;;
  "api user") echo '{"login":"harness-bot"}'; exit 0 ;;
  "repo view")
    if [ -d "$REMOTES/$3.git" ]; then echo "name: $3"; exit 0; fi
    echo "GraphQL: Could not resolve to a Repository with the name '$3'." >&2; exit 1 ;;
  "repo create")
    mkdir -p "$REMOTES/$3.git" && "$REAL_GIT" init -q --bare "$REMOTES/$3.git"; exit $? ;;
  "repo clone")
    "$REAL_GIT" clone -q "file://$REMOTES/$3.git" "$4" 2>/dev/null; exit $? ;;
  "secret set")
    cat > "$DIR/secret-$3"; exit 0 ;;
esac
echo "fake gh: unscripted call: $*" >&2
exit 1
"""

FAKE_GIT = r"""#!/bin/sh
{ printf 'git'; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$LOG"
exec "$REAL_GIT" "$@"
"""

_GIT_WRITES = {"add", "commit", "push", "fetch", "merge", "checkout", "clone",
               "reset", "rm", "mv", "tag", "init", "switch", "rebase", "stash"}


def _mutations(log: Path, root: Path) -> list[list[str]]:
    """Every logged command that changes something, `-c k=v` options dropped
    and paths under the project shown relative to it (as the plan shows them)."""
    prefix = str(root) + os.sep
    out = []
    for line in log.read_text().splitlines() if log.exists() else []:
        tool, *rest = line.split("\t")
        while len(rest) >= 2 and rest[0] == "-c":
            rest = rest[2:]
        if tool == "git":
            sub = rest[0] if rest else ""
            writes = (sub in _GIT_WRITES
                      or (sub == "remote" and rest[1:2] in (["add"], ["set-url"],
                                                             ["remove"], ["rename"]))
                      or (sub == "config" and len(rest) > 2 and not any(
                          a.startswith("--get") or a in ("--list", "-l")
                          for a in rest)))
        else:
            writes = (rest[:2] in (["repo", "create"], ["repo", "clone"],
                                   ["repo", "edit"], ["repo", "delete"],
                                   ["secret", "set"])
                      or (rest[:1] == ["api"] and ("-X" in rest or any(
                          "protection" in a for a in rest))))
        if writes:
            out.append([tool] + [a[len(prefix):] if a.startswith(prefix) else a
                                 for a in rest])
    return out


def _printed_plan(stdout: str) -> list[dict]:
    """The numbered steps between the two headings, each with its `$ ` lines."""
    body = stdout.split("--apply does exactly this, in this order:", 1)[1]
    body = body.split("You do afterwards", 1)[0]
    steps: list[dict] = []
    for line in body.splitlines():
        text = line.strip()
        if re.match(r"^\d+\. ", text):
            steps.append({"says": text, "when": "", "ops": []})
        elif text.startswith("only if: "):
            steps[-1]["when"] = text
        elif text.startswith("$ "):
            steps[-1]["ops"].append(shlex.split(text[2:]))
    return steps


def _afterwards(stdout: str) -> str:
    return stdout.split("You do afterwards", 1)[1]


@pytest.fixture
def world(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    remotes = tmp_path / "remotes"
    remotes.mkdir()
    log = tmp_path / "commands.log"
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "git").write_text(FAKE_GIT)
    for name in ("gh", "git"):
        (bin_dir / name).chmod(0o755)
    (bin_dir / "mode").write_text("auth")
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = Tester\n\temail = tester@example.invalid\n"
        f"[url \"file://{remotes}/\"]\n\tinsteadOf = https://github.com/\n"
        "[init]\n\tdefaultBranch = main\n")
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
                 "ALL_PROXY", "all_proxy", "CROSSAUDIT_BUNDLED_GH",
                 "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("LOG", str(log))
    monkeypatch.setenv("REMOTES", str(remotes))
    monkeypatch.setenv("REAL_GIT", REAL_GIT)
    # Only the fakes and the system directories: a real `gh` elsewhere on the
    # developer's PATH must not answer for the fake (the wrapper calls git by
    # its absolute path).
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(bin_dir), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "test-auditor-key")

    root = tmp_path / "work"
    root.mkdir()
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** exact\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: owner/placeholder\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m, "
        "key_env: CROSSAUDIT_AUDITOR_KEY}\n"
        "generator: {vendor: anthropic, provider: anthropic, model: n, "
        "key_env: CROSSAUDIT_GENERATOR_KEY}\n")
    (root / "notes.md").write_text("the work\n")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["commit", "-q", "-m", "setup"]):
        subprocess.run([REAL_GIT, *args], cwd=root, check=True)
    log.write_text("")
    monkeypatch.chdir(root)

    class World:
        pass

    w = World()
    w.root, w.bin, w.remotes, w.log = root, bin_dir, remotes, log
    w.cfg_root = load().root

    def mode(value: str) -> None:
        if value == "absent":
            (bin_dir / "gh").unlink(missing_ok=True)
            if shutil.which("gh", path=os.environ["PATH"]):
                pytest.skip("a gh is installed in a system directory")
        else:
            (bin_dir / "mode").write_text(value)
    w.mode = mode

    def snapshot() -> tuple:
        git = lambda *a: subprocess.run([REAL_GIT, *a], cwd=root, capture_output=True,
                                        text=True).stdout
        return (git("rev-parse", "HEAD"), git("remote", "-v"),
                git("status", "--porcelain", "--ignored"),
                sorted(p.name for p in remotes.rglob("*.git")))
    w.snapshot = snapshot
    return w


PAIR = ["pair", "--science", "owner/work", "--audit", "owner/work-audit"]


def test_apply_performs_exactly_the_printed_operations_in_order(world, capsys):
    assert cli_main.main(PAIR + ["--apply"]) == 0
    out = capsys.readouterr().out
    plan = _printed_plan(out)

    # The plan names the three operations it used to leave out.
    every = [op for s in plan for op in s["ops"]]
    assert ["git", "commit", "-q", "-m", "crossaudit: record repository pair",
            "--", "crossaudit.yml"] in every
    assert ["git", "remote", "add", "origin", "https://github.com/owner/work.git"] in every
    assert ["git", "push", "-u", "origin", "HEAD:main"] in every
    # Fresh repositories: the one step that applies only to an adopted, existing
    # work repository runs none of its commands; every other step runs all of its.
    skipped = [s for s in plan if "already existed" in s["when"]]
    assert len(skipped) == 1 and "Merge the existing main" in skipped[0]["says"]
    expected = [op for s in plan if s not in skipped for op in s["ops"]]
    assert _mutations(world.log, world.cfg_root) == expected

    # Branch protection is printed as the person's, and never called.
    assert "branch protection" in _afterwards(out)
    assert not any("protection" in l for l in world.log.read_text().splitlines())

    # And it did what the steps say, against the local bare repositories.
    git = lambda cwd, *a: subprocess.run([REAL_GIT, *a], cwd=cwd, capture_output=True,
                                         text=True, check=True).stdout.strip()
    head = git(world.root, "rev-parse", "HEAD")
    assert git(world.remotes / "owner" / "work.git", "rev-parse", "main") == head
    assert git(world.root, "log", "-1", "--format=%s") == \
        "crossaudit: record repository pair"
    assert "audit_repo: owner/work-audit" in (world.root / "crossaudit.yml").read_text()
    assert git(world.remotes / "owner" / "work-audit.git", "ls-tree", "--name-only",
               "-r", "main").split() == ["AUDIT_RULES.md", "cycles/README.md"]
    assert (world.bin / "secret-CROSSAUDIT_AUDITOR_KEY").read_text() == "test-auditor-key"
    assert not (world.root / ".crossaudit" / "pair-staging").exists()


def test_a_rerun_adopts_and_runs_only_operations_its_plan_printed(world, capsys):
    assert cli_main.main(PAIR + ["--apply"]) == 0
    capsys.readouterr()
    world.log.write_text("")
    monkeypatch_key = os.environ.pop("CROSSAUDIT_AUDITOR_KEY")
    try:
        assert cli_main.main(PAIR + ["--apply"]) == 0
    finally:
        os.environ["CROSSAUDIT_AUDITOR_KEY"] = monkeypatch_key
    out = capsys.readouterr().out
    plan = _printed_plan(out)
    every = [op for s in plan for op in s["ops"]]

    # Nothing left to record, the remote exists, no key loaded: those steps are
    # gone from the plan rather than printed and skipped.
    assert not any(op[:2] == ["git", "commit"] and "record repository pair" in op
                   for op in every)
    assert not any(op[:3] == ["git", "remote", "add"] for op in every)
    assert not any(op[:3] == ["gh", "secret", "set"] for op in every)
    assert "gh secret set CROSSAUDIT_AUDITOR_KEY --repo owner/work-audit" in \
        _afterwards(out)

    done = _mutations(world.log, world.cfg_root)
    assert ["gh", "repo", "create", "owner/work", "--private"] not in done
    assert ["git", "fetch", "-q", "origin", "main"] in done
    # Every executed operation is a printed one, in the printed order.
    it = iter(every)
    assert all(any(op == want for want in it) for op in done), (done, every)
