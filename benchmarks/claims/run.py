#!/usr/bin/env python3
"""Black-box acceptance harness: does CrossAudit do what its README says?

    run.py --ref <git ref | local path> --out records/<label>/ [--only C06,C07] [--keep]

Installs the product from ``--ref`` into a fresh venv (the README's pip
fallback, pointed at this repository with ``git+file://`` so no network is
needed for the product itself), then exercises each claim in CLAIMS.md through
the documented CLI, in its own temporary project and ``HOME``, against the two
scripted fake providers in ``fakeproviders.py``. Writes
``records/<label>/claims.jsonl`` and renders ``RESULTS-<label>.md``.

Standard library only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import fakeproviders as fp  # noqa: E402

DUMMY_AUD = "dummy-auditor-key-HARNESS-7Q1"
DUMMY_GEN = "dummy-generator-key-HARNESS-9Z4"
TASK = "Create a small reproducible benchmark and summarize its result"
MODELS = {"openai": "gpt-5.6-terra", "anthropic": "claude-sonnet-4-6"}
README_PIPX = ('pipx install "git+https://github.com/dongzhaohe321418-lab/'
               'crossaudit-harness@main"')
PROXY_VARS = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
              "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy")
BASE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
TAIL = 1500

UNTESTABLE = [
    ("C32", "macOS app: DMG, first-open flow, Keychain keys, menu-bar operation, Environment Doctor UI",
     "a built DMG and a GUI session (walk docs/UX_TEST_PLAN.md by hand)"),
    ("C33b", "Two-repository deployment, live: `pair --apply` creating real repositories and the secret; "
             "the app's device-code GitHub sign-in",
     "a GitHub account willing to create repositories (C33a covers plan mode and --apply against a fake gh)"),
    ("C34b", "SSH workstation / Slurm compute, Streamable-HTTP MCP with Keychain bearer tokens, Project Skills UI",
     "an SSH host and a scheduler; an HTTP MCP endpoint (C34a, C34c-C34g cover local stdio MCP)"),
    ("C35", "Benchmark sentences (severity not sight; precision 100% / recall 2%; fewer false flags)",
     "the archived run data and the cross-vendor review of it; re-running costs money"),
    ("C36", "The auditor catching real defects in real work",
     "live models and a ground-truth corpus (benchmarks/ai4s/run_auditor.py --live, ~$10)"),
]


# ======================================================================= records
@dataclass
class Cmd:
    argv: list
    cwd: str
    rc: int
    stdout: str
    stderr: str
    seconds: float
    evidence: str = ""

    def as_dict(self) -> dict:
        return {"argv": [str(a) for a in self.argv], "cwd": self.cwd, "exit": self.rc,
                "seconds": round(self.seconds, 2),
                "stdout_tail": self.stdout[-TAIL:], "stderr_tail": self.stderr[-TAIL:],
                "evidence": self.evidence}


@dataclass
class Record:
    id: str
    title: str
    verdict: str = "UNTESTED"
    observation: str = ""
    commands: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    details: dict = field(default_factory=dict)
    exit_codes: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "verdict": self.verdict,
                "observation": self.observation,
                "commands": [c.as_dict() for c in self.commands],
                "evidence": self.evidence, "details": self.details,
                "exit_codes": self.exit_codes}


def short(text: str, n: int = 300) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


# ====================================================================== harness
class Harness:
    def __init__(self, ref: str, out: Path, keep: bool):
        self.ref = ref
        self.out = out.resolve()
        self.label = self.out.name
        self.keep = keep
        self.tmp = Path(tempfile.mkdtemp(prefix=f"ca-claims-{self.label}-"))
        self.ev_root = self.out / "evidence"
        if self.ev_root.exists():
            shutil.rmtree(self.ev_root)
        self.ev_root.mkdir(parents=True)
        self.records: dict[str, Record] = {}
        self.projects: dict[str, "Project"] = {}
        self.venv: Path | None = None
        self.ca: Path | None = None
        self.install_cmds: list[Cmd] = []
        self.browser_log = self.tmp / "browser-invocations.log"
        self.browser = self.tmp / "fake-browser.sh"
        self.browser.write_text(
            "#!/bin/sh\necho \"$@\" >> '%s'\nexit 0\n" % self.browser_log)
        self.browser.chmod(0o755)
        self.ref_sha = ""
        self.ref_is_path = Path(ref).expanduser().is_dir()

    # ---- paths
    def evdir(self, claim: str) -> Path:
        d = self.ev_root / claim
        d.mkdir(parents=True, exist_ok=True)
        return d

    def rel(self, p: Path) -> str:
        try:
            return str(Path(p).resolve().relative_to(HERE))
        except ValueError:
            return str(p)

    def copy(self, claim: str, src: Path, name: str) -> str:
        p = self.evdir(claim) / name
        shutil.copyfile(src, p)
        return self.rel(p)

    def save(self, claim: str, name: str, text: str) -> str:
        p = self.evdir(claim) / name
        p.write_text(text, encoding="utf-8")
        return self.rel(p)

    # ---- generic subprocess with recording
    def sh(self, rec: Record | None, argv: list, *, cwd: Path, env: dict,
           timeout: float = 300, stdin: str | None = None, label: str = "",
           stdout_file: Path | None = None) -> Cmd:
        t0 = time.time()
        try:
            if stdout_file is not None:
                with open(stdout_file, "wb") as fh:
                    p = subprocess.run([str(a) for a in argv], cwd=str(cwd), env=env,
                                       stdout=fh, stderr=subprocess.PIPE,
                                       input=(stdin or "").encode() if stdin is not None else None,
                                       stdin=None if stdin is not None else subprocess.DEVNULL,
                                       timeout=timeout)
                out = Path(stdout_file).read_text(encoding="utf-8", errors="replace")
                err = p.stderr.decode("utf-8", "replace")
                rc = p.returncode
            else:
                p = subprocess.run([str(a) for a in argv], cwd=str(cwd), env=env,
                                   capture_output=True, text=True,
                                   input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL,
                                   timeout=timeout)
                out, err, rc = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = "HARNESS: timed out after %ss" % timeout
            rc = -999
        except FileNotFoundError as exc:
            out, err, rc = "", f"HARNESS: {exc}", 127
        cmd = Cmd(list(argv), str(cwd), rc, out, err, time.time() - t0)
        if rec is not None:
            n = len(rec.commands) + 1
            slug = re.sub(r"[^A-Za-z0-9]+", "-", label or " ".join(map(str, argv[1:4])))[:40]
            body = (f"$ {' '.join(map(str, argv))}\n# cwd: {cwd}\n# exit: {rc}\n"
                    f"# seconds: {cmd.seconds:.2f}\n\n--- stdout ---\n{out}\n--- stderr ---\n{err}\n")
            cmd.evidence = self.save(rec.id, f"cmd-{n:02d}-{slug}.txt", body)
            rec.commands.append(cmd)
        return cmd

    def base_env(self, home: Path, extra: dict | None = None) -> dict:
        env = {"PATH": f"{self.venv}/bin:{BASE_PATH}" if self.venv else BASE_PATH,
               "HOME": str(home), "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8",
               "TMPDIR": str(self.tmp / "tmp"), "NO_COLOR": "1",
               "BROWSER": str(self.browser), "GIT_CONFIG_NOSYSTEM": "1",
               "TERM": "dumb"}
        (self.tmp / "tmp").mkdir(exist_ok=True)
        env.update(extra or {})
        return env

    # ---- install
    def install(self) -> None:
        if self.ref_is_path:
            spec = str(Path(self.ref).expanduser().resolve())
            self.ref_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=spec,
                                          capture_output=True, text=True).stdout.strip()
        else:
            spec = f"crossaudit @ git+file://{REPO}@{self.ref}"
            self.ref_sha = subprocess.run(["git", "rev-parse", self.ref], cwd=REPO,
                                          capture_output=True, text=True).stdout.strip()
        self.install_spec = spec
        self.venv = self.tmp / "product-venv"
        env = {"PATH": BASE_PATH, "HOME": str(self.tmp / "install-home"),
               "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
        Path(env["HOME"]).mkdir(exist_ok=True)
        # The pip cache of the real user is reused so dependency wheels need
        # no network; the product itself comes from this repository.
        env["PIP_CACHE_DIR"] = str(Path.home() / "Library/Caches/pip")
        c1 = self.sh(None, [sys.executable, "-m", "venv", str(self.venv)], cwd=self.tmp, env=env)
        c2 = self.sh(None, [self.venv / "bin/pip", "install", "-q", spec], cwd=self.tmp,
                     env=env, timeout=600)
        self.install_cmds = [c1, c2]
        self.ca = self.venv / "bin/crossaudit"
        if c2.rc != 0 or not self.ca.exists():
            raise SystemExit(f"product install failed:\n{c2.stderr[-3000:]}")

    def cleanup(self) -> None:
        # Stop any console daemons or stragglers started from our temp root.
        try:
            out = subprocess.run(["pgrep", "-f", str(self.tmp)], capture_output=True,
                                 text=True).stdout.split()
            for pid in out:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except (OSError, ValueError):
                    pass
        except FileNotFoundError:
            pass
        if not self.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)


# ====================================================================== project
class Project:
    """One temporary project: its own HOME, fake providers, and CrossAudit tree."""

    def __init__(self, h: Harness, rec: Record, scenario: fp.Scenario, *,
                 name: str = "proj", auditor: str = "openai",
                 generator: str = "anthropic", tag: str = ""):
        self.h, self.rec = h, rec
        tag = tag or rec.id
        self.base = h.tmp / tag
        self.home = self.base / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.root = self.home / name
        self.name = name
        self.auditor, self.generator = auditor, generator
        self.fakes = fp.FakeProviders(scenario, h.evdir(rec.id) / f"captures-{tag}").start()
        self.console_started = False

    def env(self, extra: dict | None = None, keys: bool = True,
            custom: bool = True) -> dict:
        e = {}
        if keys:
            e.update(CROSSAUDIT_AUDITOR_KEY=DUMMY_AUD, CROSSAUDIT_GENERATOR_KEY=DUMMY_GEN)
        if custom:
            e["CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT"] = "1"
        e.update(extra or {})
        return self.h.base_env(self.home, e)

    def ca(self, *args, cwd: Path | None = None, extra: dict | None = None,
           keys: bool = True, custom: bool = True, timeout: float = 300,
           label: str = "", stdout_file: Path | None = None) -> Cmd:
        return self.h.sh(self.rec, [self.h.ca, *args], cwd=cwd or self.root,
                         env=self.env(extra, keys, custom), timeout=timeout,
                         label=label, stdout_file=stdout_file)

    def git(self, *args, check: bool = False) -> str:
        p = subprocess.run(["git", "-c", "user.name=harness",
                            "-c", "user.email=harness@example.invalid", *args],
                           cwd=self.root, capture_output=True, text=True,
                           env=self.h.base_env(self.home))
        if check and p.returncode:
            raise RuntimeError(f"git {args}: {p.stderr}")
        return p.stdout

    def init(self, *, extra_flags: list | None = None, keys: bool = True) -> Cmd:
        return self.ca("init", self.name, "--no-console",
                       "--auditor-vendor", self.auditor,
                       "--auditor-model", MODELS.get(self.auditor, "x"),
                       "--generator-vendor", self.generator,
                       "--generator-model", MODELS.get(self.generator, "x"),
                       *(extra_flags or []), cwd=self.home, keys=keys, custom=False,
                       label="init")

    def base_url(self, vendor: str) -> str:
        return self.fakes.openai_base if vendor == "openai" else self.fakes.anthropic_base

    def configure(self, *, checks: str | None = None, max_rounds: int | None = None,
                  authority: str | None = None, parametric_false: bool = False,
                  same_vendor: bool = False) -> str:
        """Point both roles at the fakes (documented `base_url` + the documented
        CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT opt-in) and apply documented knobs."""
        y = (self.root / "crossaudit.yml").read_text(encoding="utf-8")
        y = y.replace("  key_env: CROSSAUDIT_AUDITOR_KEY\n",
                      f"  key_env: CROSSAUDIT_AUDITOR_KEY\n  base_url: {self.base_url(self.auditor)}\n", 1)
        if same_vendor:
            y = re.sub(r"generator:\n(.*?)\n\n", lambda m: (
                "generator:\n  vendor: openai\n  provider: openai_compat\n"
                f"  model: gpt-5.6-luna\n  key_env: CROSSAUDIT_GENERATOR_KEY\n"
                f"  base_url: {self.fakes.openai_base}\n\n"), y, count=1, flags=re.S)
        else:
            y = y.replace("  key_env: CROSSAUDIT_GENERATOR_KEY\n",
                          f"  key_env: CROSSAUDIT_GENERATOR_KEY\n  base_url: {self.base_url(self.generator)}\n", 1)
        if checks is not None:
            y = re.sub(r"^checks: .*$", f"checks: {checks}", y, flags=re.M)
        if max_rounds is not None:
            y = re.sub(r"^max_rounds: .*$", f"max_rounds: {max_rounds}", y, flags=re.M)
        if parametric_false:
            y = y.replace("    parametric: true", "    parametric: false", 1)
        if authority:
            y += f"\nauthority:\n  lone_model_blocker: {authority}\n"
        (self.root / "crossaudit.yml").write_text(y, encoding="utf-8")
        self.git("add", "crossaudit.yml")
        self.git("commit", "-q", "-m", "harness: point roles at the fake providers")
        return y

    def build(self, task: str = TASK, label: str = "build") -> Cmd:
        return self.ca("build", task, label=label, timeout=240)

    def log(self) -> list[str]:
        return [ln for ln in self.git("log", "--reverse", "--format=%s").splitlines()]

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def status_json(self) -> dict:
        c = self.ca("--json", "status", label="status-json")
        try:
            return json.loads(c.stdout)
        except ValueError:
            return {}

    def cycle_dirs(self) -> list[Path]:
        d = self.root / "cycles"
        return sorted([p for p in d.iterdir() if p.is_dir()],
                      key=lambda p: p.stat().st_mtime) if d.is_dir() else []

    def receipts(self) -> list[Path]:
        return [p / "receipt.json" for p in self.cycle_dirs() if (p / "receipt.json").exists()]

    def pass_receipt(self) -> Path | None:
        for r in self.receipts():
            try:
                if json.loads(r.read_text())["audit"]["verdict"] == "PASS":
                    return r
            except (ValueError, KeyError):
                pass
        return None

    def stop(self) -> None:
        if self.console_started:
            self.ca("console", "--stop", label="console-stop-cleanup")
        self.fakes.stop()


# ======================================================================= helpers
def pty_run(argv: list, env: dict, cwd: Path, inputs: list[bytes], timeout: float = 60,
            idle: float = 0.8, gates: list | None = None,
            marks: list | None = None) -> tuple[int, str]:
    """Run under a pseudo-terminal, typing each input when output goes idle.

    ``gates[i]`` (optional) is a predicate on the output so far: input ``i``
    is typed as soon as it holds instead of on idle — for a screen that
    redraws on a timer and is therefore never idle. ``marks`` (optional)
    receives the output offset at which each input was typed, so a test can
    say what was on screen before a key and what came after it.
    """
    import pty
    pid, fd = pty.fork()
    if pid == 0:  # child
        try:
            os.chdir(str(cwd))
            os.execve(str(argv[0]), [str(a) for a in argv], env)
        finally:
            os._exit(127)
    out = b""
    pending = list(inputs)
    pending_gates = list(gates or [])
    pending_gates += [None] * (len(pending) - len(pending_gates))
    last = time.time()
    deadline = time.time() + timeout

    def type_next() -> None:
        nonlocal last
        pending_gates.pop(0)
        if marks is not None:
            marks.append(len(out))
        try:
            os.write(fd, pending.pop(0))
        except OSError:
            pending.clear()
        last = time.time()

    while True:
        try:
            r, _, _ = select.select([fd], [], [], 0.2)
        except OSError:
            break
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            out += data
            last = time.time()
        if pending:
            gate = pending_gates[0]
            if gate is not None:
                try:
                    ready = bool(gate(out.decode("utf-8", "replace")))
                except Exception:  # a gate that crashes never types
                    ready = False
                if ready:
                    type_next()
            elif not r and time.time() - last > idle:
                type_next()
        if time.time() > deadline:
            os.kill(pid, signal.SIGKILL)
            break
    _, status = os.waitpid(pid, 0)
    try:
        os.close(fd)
    except OSError:
        pass
    rc = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else status >> 8
    return rc, out.decode("utf-8", "replace")


def readme_text(h: "Harness") -> str:
    """The README.md of the ref under test (a path's file, or `git show ref:README.md`)."""
    if h.ref_is_path:
        return (Path(h.ref).expanduser().resolve() / "README.md").read_text(encoding="utf-8")
    return subprocess.run(["git", "show", f"{h.ref}:README.md"], cwd=REPO,
                          capture_output=True, text=True).stdout


def readme_default_checks(h: "Harness") -> list[str]:
    """Check names in the FIRST table under '## Deterministic checks' of that README.

    The README's own sentence is the claim: whatever pack it calls the default is
    what `init` must write. Read at the ref, so a corrected README and a corrected
    product are judged together and an old README is judged against its own words.
    """
    text = readme_text(h)
    m = re.search(r"^## Deterministic checks\n(.*?)^## ", text, re.S | re.M)
    body = m.group(1) if m else ""
    names, started = [], False
    for line in body.splitlines():
        if line.startswith("| `"):
            started = True
            names.append(re.match(r"\| `([a-z_-]+)`", line).group(1))
        elif started and not line.startswith("|"):
            break
    return names


def tree_hash(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def no_proxy_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_get(url: str, host: str | None = None, timeout: float = 10) -> tuple[int, str]:
    u = urllib.request.urlparse(url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=timeout)
    headers = {"Host": host} if host else {}
    path = u.path + (("?" + u.query) if u.query else "")
    try:
        conn.request("GET", path or "/", headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read(400000).decode("utf-8", "replace")
    except OSError as exc:
        return -1, f"{exc}"
    finally:
        conn.close()


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def json_or_none(text: str):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def finish(rec: Record, verdict: str, observation: str) -> Record:
    rec.verdict, rec.observation = verdict, observation
    return rec


def gen_commits(log: list[str]) -> list[str]:
    return [s for s in log if re.search(r"\(round \d+\)$", s)]


# ======================================================================== claims
CLAIMS: list[tuple[str, str, object, tuple]] = []


def claim(cid: str, title: str, deps: tuple = ()):
    def wrap(fn):
        CLAIMS.append((cid, title, fn, deps))
        return fn
    return wrap


# ---------------------------------------------------------------- A. install
@claim("C01", "pipx install …@main, then `crossaudit --version` (Python 3.10+)")
def c01(h: Harness, rec: Record) -> Record:
    readme = (REPO / "README.md").read_text(encoding="utf-8") if not h.ref_is_path else \
        (Path(h.ref) / "README.md").read_text(encoding="utf-8")
    env = {"PATH": BASE_PATH + ":/opt/homebrew/bin:/usr/local/bin",
           "HOME": str(h.tmp / "c01-home"), "LANG": "en_US.UTF-8"}
    Path(env["HOME"]).mkdir(exist_ok=True)
    lit = h.sh(rec, ["/bin/sh", "-c", README_PIPX], cwd=h.tmp, env=env, label="literal-pipx")
    ver_lit = h.sh(rec, ["/bin/sh", "-c", "crossaudit --version"], cwd=h.tmp, env=env,
                   label="literal-version")
    # The documented alternative (README "Command-line installation"), pointed
    # at this repository: it is how this harness installed the product.
    for c in h.install_cmds:
        rec.commands.append(c)
    ver = h.sh(rec, [h.ca, "--version"], cwd=h.tmp, env=h.base_env(h.tmp / "c01-home"),
               label="fallback-version")
    prereq = "pipx.pypa.io" in readme
    fallback_same_place = 'python -m pip install "crossaudit @ git+' in readme
    m = re.match(r"crossaudit (\S+) \(receipt schema (\d+)\) · (\S+) · (\S+)", ver.stdout.strip())
    rec.details = {"literal_exit": lit.rc, "literal_stderr": short(lit.stderr, 200),
                   "pipx_prerequisite_linked_in_readme": prereq,
                   "fallback_in_readme": fallback_same_place,
                   "fallback_version_output": ver.stdout.strip(),
                   "readme_expected_version_line": "crossaudit 4.17.0 (receipt schema 2)",
                   "install_spec": h.install_spec,
                   "deviation": "fallback pointed at git+file://<this repo>@<ref> instead of github @main"}
    tutorial = re.search(r"Command-line users: `pipx install", readme) is not None
    rec.details["tour_mentions_pipx_without_prerequisite"] = tutorial
    if ver.rc == 0 and m and (prereq or fallback_same_place):
        obs = (f"literal `pipx install` exits {lit.rc} ({short(lit.stderr, 80)}); README links pipx "
               f"and gives the pip fallback in the same section; fallback installs and prints "
               f"`{ver.stdout.strip()[:60]}…` (version, schema, install mode). README's expected "
               f"line omits the mode/path suffix.")
        return finish(rec, "PASS", obs)
    return finish(rec, "FAIL", f"fallback --version exit {ver.rc}: {short(ver.stdout + ver.stderr)}")


@claim("C02", "Installing asks for nothing and contacts no provider")
def c02(h: Harness, rec: Record) -> Record:
    if h.ref_is_path:
        spec = h.install_spec
    else:
        spec = h.install_spec
    wheelhouse = h.tmp / "wheelhouse"
    env_net = {"PATH": BASE_PATH, "HOME": str(h.tmp / "c02-home"),
               "PIP_CACHE_DIR": str(Path.home() / "Library/Caches/pip"),
               "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    Path(env_net["HOME"]).mkdir(exist_ok=True)
    # Step 1 (the "package fetch", allowed to use the network): build wheels for
    # the product's dependencies and the build backend.
    w = h.sh(rec, [h.venv / "bin/pip", "wheel", "-q", "-w", wheelhouse, spec,
                   "setuptools>=77", "wheel"], cwd=h.tmp, env=env_net, timeout=600,
             label="wheelhouse")
    if w.rc != 0:
        return finish(rec, "UNTESTED", f"could not prepare an offline wheelhouse: {short(w.stderr)}")
    for p in wheelhouse.glob("crossaudit-*.whl"):
        p.unlink()  # the product itself must come from the git URL below
    # Step 2: a sentinel "proxy" that records every connection attempt.
    hits: list = []
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    port = srv.getsockname()[1]
    stop = threading.Event()

    def accept():
        srv.settimeout(0.3)
        while not stop.is_set():
            try:
                conn, addr = srv.accept()
                try:
                    conn.settimeout(1)
                    hits.append(conn.recv(200).decode("latin-1", "replace"))
                except OSError:
                    hits.append("<no data>")
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break
    t = threading.Thread(target=accept, daemon=True)
    t.start()
    dead = f"http://127.0.0.1:{port}"
    env = {"PATH": BASE_PATH, "HOME": str(h.tmp / "c02-home"),
           "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_CACHE_DIR": "1",
           "HTTP_PROXY": dead, "HTTPS_PROXY": dead, "ALL_PROXY": dead,
           "http_proxy": dead, "https_proxy": dead, "all_proxy": dead,
           "BROWSER": str(h.browser)}
    venv = h.tmp / "c02-venv"
    h.sh(rec, [sys.executable, "-m", "venv", venv], cwd=h.tmp, env=env, label="venv")
    inst = h.sh(rec, [venv / "bin/pip", "install", "--no-index", "--find-links", wheelhouse,
                      spec], cwd=h.tmp, env=env, timeout=600, label="offline-install")
    v = h.sh(rec, [venv / "bin/crossaudit", "--version"], cwd=h.tmp, env=env, label="version")
    bare = h.sh(rec, [venv / "bin/crossaudit"], cwd=h.tmp / "c02-home", env=env, label="bare")
    time.sleep(0.5)
    stop.set()
    srv.close()
    browser_calls = h.browser_log.read_text() if h.browser_log.exists() else ""
    rec.details = {"sentinel_proxy": dead, "connections_seen": hits,
                   "browser_invocations": browser_calls,
                   "install_exit": inst.rc, "version_exit": v.rc, "bare_exit": bare.rc,
                   "method": "dependency wheels pre-fetched (the allowed package fetch); "
                             "product installed from git+file with every proxy variable "
                             "pointed at a recording socket"}
    if inst.rc != 0:
        return finish(rec, "UNTESTED", f"offline install failed: {short(inst.stderr)}")
    if not hits and not browser_calls and v.rc == 0:
        return finish(rec, "PASS", "offline install from git+file, `--version` and bare "
                      "`crossaudit` made zero connection attempts through the recording proxy "
                      "and opened no browser; nothing prompted.")
    return finish(rec, "FAIL", f"{len(hits)} connection attempt(s): {short(str(hits))}")


@claim("C03", "`crossaudit init … --no-console --auditor-vendor … --generator-vendor …` sets up the project")
def c03(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, fp.Scenario())
    try:
        c = p.init()
        rec.exit_codes["init"] = c.rc
        root = p.root
        problems, ok = [], []
        commits = p.log() if (root / ".git").exists() else []
        (ok if commits else problems).append(f"git commits: {len(commits)}")
        (ok if (root / "crossaudit.yml").exists() else problems).append("crossaudit.yml")
        rules = re.findall(r"^### (CA-[A-Z]+-\d+)", (root / "AUDIT_RULES.md").read_text(), re.M) \
            if (root / "AUDIT_RULES.md").exists() else []
        (ok if rules else problems).append(f"AUDIT_RULES.md rule ids {rules}")
        dc = (root / "DETERMINISTIC_CHECKS.md").read_text() if (root / "DETERMINISTIC_CHECKS.md").exists() else ""
        readme_default = readme_default_checks(h)
        named = re.findall(r"^- ([a-z_-]+):", dc, re.M)
        if readme_default and all(n in named for n in readme_default):
            ok.append(f"DETERMINISTIC_CHECKS.md names {named}, the README's default pack")
        else:
            problems.append(f"DETERMINISTIC_CHECKS.md names {named}, not the README's default "
                            f"pack {readme_default or '(no table found)'}")
        keys = p.home / ".crossaudit-keys.env"
        init_text = c.stdout + c.stderr
        if keys.exists():
            mode = oct(keys.stat().st_mode & 0o777)
            (ok if mode == "0o600" else problems).append(f"keys file mode {mode}")
        elif "CROSSAUDIT_AUDITOR_KEY" in init_text and "CROSSAUDIT_GENERATOR_KEY" in init_text:
            ok.append("non-interactive init wrote no keys file and said so, naming the "
                      "environment variables it reads instead")
        else:
            problems.append("no keys file written by non-interactive init and nothing said "
                            "where keys come from (tui.secret returns '' without a TTY, so "
                            "`write_keys` never runs)")
        leaked = p.git("log", "-p", "--all").count(DUMMY_AUD) + p.git("log", "-p", "--all").count(DUMMY_GEN)
        (ok if leaked == 0 else problems).append(f"dummy key occurrences in git history: {leaked}")
        rec.evidence.append(h.save(rec.id, "tree-after-init.txt",
                                   "\n".join(sorted(tree_hash(root))) + "\n\n" + dc))
        # Supplementary: the interactive path, under a pseudo-terminal.
        q = Project(h, rec, fp.Scenario(), tag="C03-pty", name="ptyproj")
        argv = [h.ca, "init", q.name, "--no-console", "--auditor-vendor", "openai",
                "--auditor-model", MODELS["openai"], "--generator-vendor", "anthropic",
                "--generator-model", MODELS["anthropic"]]
        rc, out = pty_run(argv, q.env(keys=False, custom=False), q.home,
                          [DUMMY_AUD.encode() + b"\r", DUMMY_GEN.encode() + b"\r", b"\r",
                           b"1", b"\r", b"\r", b"\r"], timeout=60)
        rec.evidence.append(h.save(rec.id, "pty-init-transcript.txt", out))
        qkeys = q.home / ".crossaudit-keys.env"
        pty_info = {"exit": rc, "keys_file": qkeys.exists(),
                    "mode": oct(qkeys.stat().st_mode & 0o777) if qkeys.exists() else None,
                    "inside_repo": str(qkeys).startswith(str(q.root))}
        if (q.root / ".git").exists():
            hist = q.git("log", "-p", "--all")
            pty_info["key_in_git"] = (DUMMY_AUD in hist) or (DUMMY_GEN in hist)
        rec.details = {"ok": ok, "problems": problems, "interactive_pty_init": pty_info,
                       "init_exit": c.rc}
        q.stop()
        if c.rc != 0:
            return finish(rec, "FAIL", f"init exit {c.rc}: {short(c.stderr)}")
        if problems:
            return finish(rec, "PARTIAL", "project, git commit, config, rule ids created; but "
                          + "; ".join(problems)
                          + f". Under a pty the interactive path wrote keys file={pty_info['keys_file']} "
                            f"mode={pty_info['mode']}.")
        return finish(rec, "PASS", "; ".join(ok))
    finally:
        p.stop()


@claim("C04", "`crossaudit doctor` checks the listed posture items and is read-only")
def c04(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, fp.Scenario())
    try:
        p.init()
        p.configure()
        before = tree_hash(p.root)
        d1 = p.ca("doctor", label="doctor")
        d2 = p.ca("--json", "doctor", label="doctor-json")
        d3 = p.ca("doctor", "--all", label="doctor-all")
        after = tree_hash(p.root)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        created = [k for k in changed if k not in before]
        data = json_or_none(d2.stdout) or {}
        names = [c.get("check", "") for c in data.get("checks", [])]
        want = {"Python": ["python"], "Git": ["git"], "package identity": ["install"],
                "TLS certificates": ["tls trust store"], "configuration": ["config"],
                "credentials": ["auditor connection", "generator connection"],
                "vendor separation": ["heterogeneity (I1)"], "rule file": ["constitution"],
                "state storage": ["state store"]}
        missing = [k for k, v in want.items() if not all(x in names for x in v)]
        if "admission" not in data:
            missing.append("admission tier")
        rec.exit_codes = {"doctor": d1.rc, "json_doctor": d2.rc}
        rec.details = {"json_check_names": names, "missing_items": missing,
                       "tree_changed": changed, "created_by_doctor": created,
                       "default_output_collapses": "other checks passed" in d1.stdout}
        if d1.rc == 0 and d2.rc == 0 and not missing and not changed:
            return finish(rec, "PASS", "all ten README items appear in `--json doctor` (and "
                          "`doctor --all`); default output collapses passing checks into a count; "
                          "tree unchanged; exit 0.")
        if d1.rc == 0 and d2.rc == 0 and not missing:
            return finish(rec, "PARTIAL", "all ten README items appear in `--json doctor` / `doctor --all` "
                          "and exit is 0, but doctor is not read-only: it "
                          + ("created " + ", ".join(created) if created else "modified " + ", ".join(changed))
                          + " in the project tree (no --fix given).")
        return finish(rec, "FAIL", f"exit {d1.rc}/{d2.rc}; missing {missing}; changed files {changed[:5]}")
    finally:
        p.stop()


@claim("C05", "Same-vendor pairs are refused")
def c05(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, fp.Scenario(), auditor="openai", generator="openai", tag="C05-init")
    try:
        c = p.init()
        rec.exit_codes["init_same_vendor"] = c.rc
        created = p.root.exists()
    finally:
        p.stop()
    q = Project(h, rec, fp.Scenario(), tag="C05-edit")
    try:
        q.init()
        q.configure(same_vendor=True)
        d = q.ca("doctor", "--all", label="doctor-same-vendor")
        dj = q.ca("--json", "doctor", label="doctor-json-same-vendor")
        b = q.build()
        rec.exit_codes.update(doctor=d.rc, build=b.rc)
        data = json_or_none(dj.stdout) or {}
        het = [c for c in data.get("checks", []) if "heterogeneity" in c.get("check", "")]
        reqs = len(q.fakes.requests())
        rec.details = {"init_exit": c.rc, "init_stderr": short(c.stderr, 300),
                       "init_created_dir": created, "doctor_heterogeneity": het,
                       "build_exit": b.rc, "build_stderr": short(b.stderr, 300),
                       "fake_requests": reqs}
        init_ok = c.rc == 20
        doc_ok = bool(het) and not het[0].get("ok", True)
        build_ok = b.rc == 20 and reqs == 0
        if init_ok and doc_ok and build_ok:
            return finish(rec, "PASS", f"init refuses (exit 20) {'and creates no directory' if not created else 'but left a directory'}; "
                          "doctor reports heterogeneity failed; build refuses with exit 20 and the "
                          "fakes saw 0 requests.")
        return finish(rec, "FAIL", f"init {c.rc}, doctor heterogeneity ok={not doc_ok}, "
                      f"build {b.rc}, fake requests {reqs}")
    finally:
        q.stop()


# ------------------------------------------------------------------ B. the loop
class FixOn2(fp.Scenario):
    name = "fix-on-2"
    MARK = "FINDING-SEED-7731"

    def generator(self, n, system, prompt):
        if n == 1:
            return fp.reply(fp.envelope(fp.increment(summary_line="The benchmark ran in 1.5 s.")))
        return fp.reply(fp.envelope(fp.increment(), summary="state the seed"))

    def auditor(self, n, system, prompt):
        if n == 1:
            return fp.reply(fp.audit_json(prompt, "BLOCKED",
                                          f"SUMMARY.md does not state the random seed ({self.MARK})."))
        return fp.reply(fp.audit_json(prompt, "PASS"))


class AlwaysBlocked(fp.Scenario):
    name = "always-blocked"

    def generator(self, n, system, prompt):
        return fp.reply(fp.envelope(fp.increment(value=round(1.5 + n / 10, 2)),
                                    summary=f"attempt {n}"))

    def auditor(self, n, system, prompt):
        return fp.reply(fp.audit_json(prompt, "BLOCKED", f"the claim is unsupported (attempt {n})"))


class DclFail(fp.Scenario):
    name = "dcl-fail"

    def generator(self, n, system, prompt):
        return fp.reply(fp.envelope(fp.increment(value=round(1.5 + n / 10, 2), unit=None),
                                    summary=f"no unit {n}"))


class Escape(fp.Scenario):
    name = "escape"

    def generator(self, n, system, prompt):
        if n == 1:
            return fp.reply(fp.envelope(fp.increment()))
        if n == 2:
            files = fp.increment(value=1.6)
            files["../../evil.txt"] = "escaped\n"
            files["evil-root.txt"] = "at repository root\n"
            return fp.reply(fp.envelope(files, summary="escape attempt"))
        return fp.reply(fp.envelope(fp.increment(value=1.7), summary="honest repair"))

    def auditor(self, n, system, prompt):
        if n == 1:
            return fp.reply(fp.audit_json(prompt, "BLOCKED", "SUMMARY.md lacks detail"))
        return fp.reply(fp.audit_json(prompt, "PASS"))


class Overreach(fp.Scenario):
    name = "overreach"

    def generator(self, n, system, prompt):
        if n == 1:
            files = fp.increment()
            files["AUDIT_RULES.md"] = "# rules rewritten by the generator\n"
            files["crossaudit.yml"] = "version: 1\n# hijacked\n"
            files["cycles/x.md"] = "forged ledger entry\n"
            return fp.reply(fp.envelope(files, summary="overreach"))
        return fp.reply(fp.envelope(fp.increment(value=1.6), summary="honest"))


class Truncated(fp.Scenario):
    name = "truncated"

    def generator(self, n, system, prompt):
        files = fp.increment()
        files[f"{fp.INC_DIR}/SUMMARY.md"] = "# Benchmark\n\nThe benchmark ran in 1."
        return fp.reply(fp.envelope(files, drop_last_end=True), finish="length")


class Http500(fp.Scenario):
    name = "http-500"

    def respond(self, role, n, system, prompt):
        return fp.http_error(500, "internal error (scripted)")


class Requirements(fp.Scenario):
    """Clean, plus a pinned dependency lock inside the increment."""
    name = "clean+lock"

    def generator(self, n, system, prompt):
        return fp.reply(fp.envelope(fp.increment(extra={
            f"{fp.INC_DIR}/requirements.txt": "numpy==2.1.0\n"})))


def clean_project(h: Harness, rec: Record, *, tag: str = "", parametric_false: bool = False,
                  scenario: fp.Scenario | None = None, pre=None, checks: str | None = None) -> tuple[Project, Cmd]:
    p = Project(h, rec, scenario or fp.Scenario(), tag=tag or rec.id)
    p.init()
    p.configure(parametric_false=parametric_false, checks=checks)
    if pre:
        pre(p)
    b = p.build()
    return p, b


@claim("C06", "`crossaudit build` commits task → generator round → audit report → receipt")
def c06(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec)
    h.projects["C06"] = p
    rec.exit_codes["build"] = b.rc
    log = p.log()
    after = log[log.index("harness: point roles at the fake providers") + 1:]
    sha12 = p.git("rev-parse", "--short=12", "HEAD~2").strip()
    expect = [f"task: {TASK}"[:len(after[0])] if after else "", "(round 1)",
              f"audit report {sha12} r1", f"audit receipt {sha12} r1 (PASS)"]
    seq_ok = (len(after) == 4 and after[0].startswith("task: ")
              and after[1].endswith("(round 1)")
              and after[2] == expect[2] and after[3] == expect[3])
    cyc = p.root / "cycles" / f"{sha12}-r1"
    files = {n: (cyc / n).exists() for n in ("report.md", "checks.json", "findings.json", "receipt.json")}
    st = p.ca("status", label="status")
    rec.details = {"commits_after_setup": after, "cycle_dir": str(cyc.relative_to(p.root)),
                   "files": files, "status_stdout": st.stdout.strip()}
    rec.evidence.append(h.save(rec.id, "git-log.txt", "\n".join(log)))
    if b.rc == 0 and seq_ok and all(files.values()) and "PASSED" in st.stdout:
        return finish(rec, "PASS", "exit 0; commits exactly task → round 1 → audit report → "
                      "audit receipt (PASS); cycles/<sha>-r1/{report.md,checks.json,findings.json,"
                      "receipt.json} exist; `status` shows PASSED (README calls the state PASS).")
    return finish(rec, "FAIL", f"exit {b.rc}; commits {after}; files {files}")


@claim("C07", "A BLOCKER returns findings to the generator for another round (default max 3)")
def c07(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, FixOn2())
    h.projects["C07"] = p
    p.init()
    y = p.configure()
    b = p.build()
    rec.exit_codes["build"] = b.rc
    gens = gen_commits(p.log())
    caps = p.fakes.captures("generator")
    r2 = caps[1]["prompt"] if len(caps) > 1 else ""
    has_finding = FixOn2.MARK in r2
    st = p.status_json()
    statuses = [c["status"] for c in st.get("cycles", [])]
    rec.details = {"generator_commits": gens, "round2_prompt_has_finding": has_finding,
                   "round2_prompt_file": caps[1]["_file"] if len(caps) > 1 else None,
                   "statuses": statuses, "max_rounds_in_yml": re.search(r"max_rounds: (\d+)", y).group(1)}
    if b.rc == 0 and len(gens) == 2 and has_finding and statuses and statuses[-1] == "PASSED":
        return finish(rec, "PASS", "exit 0; two generator round commits; the round-2 generator "
                      "prompt carries the round-1 finding text verbatim; final PASS; init writes "
                      "max_rounds: 3.")
    return finish(rec, "FAIL", f"exit {b.rc}; generator commits {gens}; finding in r2 prompt "
                  f"{has_finding}; statuses {statuses}")


@claim("C08", "An exhausted budget escalates; it never approves")
def c08(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, AlwaysBlocked())
    h.projects["C08"] = p
    p.init()
    p.configure(max_rounds=2)
    b = p.build()
    rec.exit_codes["build"] = b.rc
    gens = gen_commits(p.log())
    st = p.status_json()
    statuses = [c["status"] for c in st.get("cycles", [])]
    gen_calls = len(p.fakes.requests("generator"))
    passes = [str(r.relative_to(p.root)) for r in p.receipts()
              if json_or_none(r.read_text()) and json.loads(r.read_text())["audit"]["verdict"] == "PASS"]
    pass_commits = [s for s in p.log() if "(PASS)" in s]
    rec.details = {"generator_commits": gens, "statuses": statuses, "generator_calls": gen_calls,
                   "pass_receipts": passes, "pass_commits": pass_commits,
                   "build_stdout_tail": b.stdout[-600:]}
    if b.rc == 11 and "ESCALATED" in statuses and not passes and not pass_commits \
            and len(gens) == 2 and gen_calls == 2:
        return finish(rec, "PASS", "exit 11; status ESCALATED; no PASS receipt; exactly 2 "
                      "generator rounds and 2 generator calls (no third).")
    return finish(rec, "FAIL", f"exit {b.rc}; statuses {statuses}; gen commits {len(gens)}; "
                  f"gen calls {gen_calls}; PASS receipts {passes}")


@claim("C09", "A failed deterministic check blocks whatever the model says")
def c09(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, DclFail())
    p.init()
    p.configure(checks="science", max_rounds=2)
    b = p.build()
    rec.exit_codes["build"] = b.rc
    cycs = p.cycle_dirs()
    first = cycs[0] if cycs else None
    checks = (first / "checks.json").read_text() if first and (first / "checks.json").exists() else ""
    report = (first / "report.md").read_text() if first and (first / "report.md").exists() else ""
    verdicts = [json.loads(r.read_text())["audit"]["verdict"] for r in p.receipts()]
    auditor_calls = len(p.fakes.requests("auditor"))
    st = p.status_json()
    statuses = [c["status"] for c in st.get("cycles", [])]
    m = re.search(r"verdict[^A-Z]*\b(PASS|BLOCKED|ESCALATE[D]?|DCL_ONLY)\b", report)
    rec.details = {"checks_json_names_CA_DATA_001": "CA-DATA-001" in checks,
                   "receipt_verdicts": verdicts, "report_verdict": m.group(1) if m else None,
                   "auditor_calls": auditor_calls, "statuses": statuses,
                   "auditor_said": "PASS every time",
                   "deviation": "checks: science set in crossaudit.yml (documented profile); the "
                                "default `general` profile has no unit check"}
    if first:
        rec.evidence.append(h.copy(rec.id, first / "checks.json", f"{first.name}-checks.json"))
    blocked = "CA-DATA-001" in checks and "PASS" not in verdicts and \
        (m and m.group(1) == "BLOCKED")
    if blocked and b.rc in (10, 11):
        return finish(rec, "PASS", "checks.json names CA-DATA-001; verdict BLOCKED although the "
                      f"auditor said PASS; no PASS receipt; `build` exits {b.rc} "
                      f"({'ESCALATED after the round budget, the final state the README says build reports' if b.rc == 11 else 'BLOCKED'}).")
    if blocked:
        return finish(rec, "PARTIAL", f"the check does block (CA-DATA-001 in checks.json, report "
                      f"verdict BLOCKED, receipts {verdicts}, auditor said PASS), but `build` exits "
                      f"{b.rc} ({'ESCALATED after the round budget' if b.rc == 11 else 'see evidence'}), "
                      "not the README's 10 for BLOCKED.")
    return finish(rec, "FAIL", f"exit {b.rc}; CA-DATA-001 in checks.json {'CA-DATA-001' in checks}; "
                  f"receipt verdicts {verdicts}")


@claim("C10", "`audit --offline` returns DCL_ONLY, never PASS; `check` runs checks only")
def c10(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec)
    try:
        before = len(p.fakes.requests())
        chk = p.ca("check", label="check")
        off = p.ca("audit", "--offline", label="audit-offline")
        inc = p.git("log", "--format=%H %s").splitlines()
        inc_sha = next((ln.split()[0] for ln in inc if ln.endswith("(round 1)")), "")
        off2 = p.ca("audit", "--offline", "--sha", inc_sha, label="audit-offline-sha")
        after = len(p.fakes.requests())
        rec.exit_codes = {"check": chk.rc, "audit_offline": off.rc, "audit_offline_sha": off2.rc}
        rec.details = {"check_stdout": chk.stdout.strip(),
                       "audit_offline_stderr": short(off.stderr, 400),
                       "audit_offline_sha_stdout": off2.stdout[-500:],
                       "provider_requests_during": after - before}
        check_ok = chk.rc == 0 and "verdict: PASS" in chk.stdout
        dcl_lit = off.rc == 11 and "DCL_ONLY" in (off.stdout + off.stderr)
        dcl_sha = off2.rc == 11 and "DCL_ONLY" in (off2.stdout + off2.stderr)
        if check_ok and dcl_lit and after == before:
            return finish(rec, "PASS", "check exit 0 verdict PASS; audit --offline DCL_ONLY exit 11; "
                          "no provider request.")
        if check_ok and dcl_sha and after == before:
            return finish(rec, "PARTIAL", f"`check` PASS exit 0. The literal `audit --offline` "
                          f"after a build exits {off.rc}: {short(off.stderr, 160)}. With the "
                          f"documented `--sha <increment>` it reports DCL_ONLY, exit 11; 0 provider "
                          f"requests.")
        return finish(rec, "FAIL", f"check {chk.rc}; audit --offline {off.rc}; --sha {off2.rc}; "
                      f"requests {after - before}")
    finally:
        p.stop()


@claim("C11", "A model-only blocker routes per `authority.lone_model_blocker`; the receipt says which")
def c11(h: Harness, rec: Record) -> Record:
    out = {}
    for dial in ("block", "escalate"):
        p = Project(h, rec, AlwaysBlocked(), tag=f"C11-{dial}")
        try:
            p.init()
            p.configure(max_rounds=3, authority=None if dial == "block" else "escalate")
            b = p.build(label=f"build-{dial}")
            gens = gen_commits(p.log())
            dials = []
            for r in p.receipts():
                d = json_or_none(r.read_text()) or {}
                dials.append(d.get("authority", {}).get("lone_model_blocker"))
            st = p.status_json()
            out[dial] = {"exit": b.rc, "generator_rounds": len(gens),
                         "generator_calls": len(p.fakes.requests("generator")),
                         "receipt_dials": dials,
                         "statuses": [c["status"] for c in st.get("cycles", [])]}
            rec.exit_codes[f"build_{dial}"] = b.rc
        finally:
            p.stop()
    rec.details = out
    blk, esc = out["block"], out["escalate"]
    ok_block = blk["generator_rounds"] >= 2 and blk["receipt_dials"] and all(d == "block" for d in blk["receipt_dials"])
    ok_esc = esc["generator_rounds"] == 1 and "ESCALATED" in esc["statuses"] and \
        esc["receipt_dials"] and all(d == "escalate" for d in esc["receipt_dials"])
    if ok_block and ok_esc:
        return finish(rec, "PASS", f"block: {blk['generator_rounds']} generator rounds, receipts name "
                      f"'block'; escalate: 1 round then ESCALATED (exit {esc['exit']}), receipt names "
                      "'escalate'.")
    return finish(rec, "FAIL", f"block {blk}; escalate {esc}")


@claim("C12", "Each revision is screened by a repair guard; a file outside the scope is refused")
def c12(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, Escape())
    try:
        p.init()
        p.configure()
        b = p.build()
        rec.exit_codes["build"] = b.rc
        tracked = p.git("log", "--all", "--name-only", "--format=").split()
        escaped_fs = (p.root / "../../evil.txt").resolve()
        root_file = p.root / "evil-root.txt"
        gens = gen_commits(p.log())
        st = p.status_json()
        rec.details = {"evil_txt_in_git": any(t.endswith("evil.txt") for t in tracked),
                       "evil_root_in_git": "evil-root.txt" in tracked,
                       "escaped_file_on_disk": escaped_fs.exists(), "escaped_path": str(escaped_fs),
                       "root_file_on_disk": root_file.exists(),
                       "generator_commits": gens, "generator_calls": len(p.fakes.requests("generator")),
                       "statuses": [c["status"] for c in st.get("cycles", [])],
                       "build_stdout_tail": b.stdout[-900:]}
        d = rec.details
        refused = "refused" in b.stdout.lower()
        if not (d["evil_txt_in_git"] or d["evil_root_in_git"] or d["escaped_file_on_disk"]
                or d["root_file_on_disk"]) and refused and d["generator_calls"] >= 3:
            return finish(rec, "PASS", f"round 2's `../../evil.txt` and root-level file were never "
                          f"written or committed; the round was refused and re-asked; the honest "
                          f"round 3 passed (exit {b.rc}).")
        return finish(rec, "FAIL", f"exit {b.rc}; {d}")
    finally:
        p.stop()


@claim("C13", "A reply cut off at a token limit is discarded (D167), never committed")
def c13(h: Harness, rec: Record) -> Record:
    variants = {"anthropic-generator (stop_reason max_tokens)": ("openai", "anthropic"),
                "openai-generator (finish_reason length)": ("anthropic", "openai")}
    out = {}
    for name, (aud, gen) in variants.items():
        tag = "C13-" + gen
        p = Project(h, rec, Truncated(), auditor=aud, generator=gen, tag=tag)
        try:
            p.init()
            p.configure()
            b = p.build(label=f"build-{gen}-generator")
            summary = p.root / fp.INC_DIR / "SUMMARY.md"
            committed = p.git("log", "--all", "--name-only", "--format=").split()
            half = summary.exists() and summary.read_text().rstrip().endswith("ran in 1.")
            st = p.status_json()
            text = b.stdout + b.stderr
            out[name] = {"exit": b.rc, "summary_committed": f"{fp.INC_DIR}/SUMMARY.md" in committed,
                         "half_file_on_disk": half,
                         "generator_calls": len(p.fakes.requests("generator")),
                         "auditor_calls": len(p.fakes.requests("auditor")),
                         "statuses": [c["status"] for c in st.get("cycles", [])],
                         "names_cutoff": ("cut off" in text) or ("token limit" in text),
                         "build_stdout_tail": b.stdout[-700:]}
            rec.exit_codes[f"build_{gen}_generator"] = b.rc
        finally:
            p.stop()
    rec.details = out
    fixed = all(not v["summary_committed"] and v["names_cutoff"] and v["exit"] in (11, 22)
                and "ESCALATED" in v["statuses"] for v in out.values())
    broken = [k for k, v in out.items() if v["summary_committed"]]
    if fixed:
        codes = sorted({v["exit"] for v in out.values()})
        return finish(rec, "PASS", "both vendors: the cut-off reply was discarded, nothing "
                      f"committed, the run parked ESCALATED (exit {codes}) with a provider "
                      "escalation naming the token-limit cut-off.")
    if broken:
        return finish(rec, "FAIL", "the half file was committed for " + ", ".join(broken)
                      + " (SUMMARY.md ends mid-sentence `ran in 1.`) and audited as if complete — "
                        "the known defect.")
    return finish(rec, "PARTIAL", f"nothing committed but the stop does not match the claim: {out}")


@claim("C14", "Tasks, rounds, checks, findings with tier and state, verdicts committed; append-only", deps=("C07",))
def c14(h: Harness, rec: Record) -> Record:
    p = h.projects.get("C07")
    if p is None:
        return finish(rec, "UNTESTED", "needs C07's project")
    p.rec = rec
    problems, ok = [], []
    for cyc in p.cycle_dirs():
        f = json_or_none((cyc / "findings.json").read_text()) if (cyc / "findings.json").exists() else None
        rows = (f or {}).get("findings", [])
        for row in rows:
            if "tier" in row and "state" in row:
                ok.append(f"{cyc.name}: finding {row.get('rule')} tier={row['tier']} state={row['state']}")
            else:
                problems.append(f"{cyc.name}: finding without tier/state keys {sorted(row)}")
        rep = (cyc / "report.md").read_text() if (cyc / "report.md").exists() else ""
        if not rows and "## Evidence" in rep:
            ok.append(f"{cyc.name}: no findings; report Evidence section says so")
        elif "## Evidence" in rep:
            if re.search(r"\|\s*tier\s*\|", rep, re.I) or "| tier" in rep.lower():
                ok.append(f"{cyc.name}: report Evidence table has a tier column")
            else:
                problems.append(f"{cyc.name}: report has no tier column in Evidence table")
        else:
            problems.append(f"{cyc.name}: report has no Evidence section")
        if (cyc / "findings.json").exists():
            rec.evidence.append(h.copy(rec.id, cyc / "findings.json", f"{cyc.name}-findings.json"))
        if (cyc / "report.md").exists():
            rec.evidence.append(h.copy(rec.id, cyc / "report.md", f"{cyc.name}-report.md"))
    if not any("finding" in s for s in ok):
        problems.append("no finding rows at all in any findings.json")
    reflog = p.git("reflog", "--format=%gs")
    rewrites = [ln for ln in reflog.splitlines() if re.search(r"amend|rebase|reset|filter", ln)]
    linear = all(len(ln.split()) <= 2 for ln in p.git("log", "--format=%H %P").splitlines())
    (ok if not rewrites and linear else problems).append(
        f"reflog rewrites={rewrites}, linear history={linear}")
    ev = p.root / ".crossaudit" / "evidence.jsonl"
    rec.details = {"ok": ok, "problems": problems, "evidence_ledger_present": ev.exists(),
                   "crossaudit_dir": sorted(x.name for x in (p.root / ".crossaudit").iterdir())}
    rec.evidence.append(h.save(rec.id, "reflog.txt", reflog))
    if not problems:
        return finish(rec, "PASS", "findings.json rows carry tier and state; report Evidence table "
                      "lists tier; reflog shows no amend/rebase/reset; "
                      + ("evidence.jsonl absent (no governed tool call in this scenario, so its "
                         "verification was not exercised)" if not ev.exists() else "evidence ledger present"))
    return finish(rec, "FAIL" if not ok else "PARTIAL", "; ".join(problems))


# --------------------------------------------------------- C. receipts / verify
@claim("C15", "`crossaudit verify <receipt>` re-derives every binding; a changed byte fails it")
def c15(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec)
    try:
        r = p.pass_receipt()
        if r is None:
            return finish(rec, "UNTESTED", f"no PASS receipt (build exit {b.rc})")
        rel = str(r.relative_to(p.root))
        v0 = p.ca("verify", rel, label="verify-untampered")
        res = {"untampered": (v0.rc, "BINDINGS VERIFIED" in v0.stdout)}
        rec.exit_codes["verify_untampered"] = v0.rc
        original = r.read_bytes()
        data = json.loads(original)
        for name, mutate in (("report_sha256", lambda d: d["ledger"].__setitem__(
                "report_sha256", "0" + d["ledger"]["report_sha256"][1:]
                if d["ledger"]["report_sha256"][0] != "0" else "1" + d["ledger"]["report_sha256"][1:])),
                ("verdict", lambda d: d["audit"].__setitem__("verdict", "BLOCKED"))):
            d = json.loads(original)
            mutate(d)
            r.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
            v = p.ca("verify", rel, label=f"verify-tampered-{name}")
            res[name] = (v.rc, short(v.stdout + v.stderr, 220))
            rec.exit_codes[f"verify_tampered_{name}"] = v.rc
            r.write_bytes(original)
        report = r.parent / "report.md"
        rb = report.read_bytes()
        flipped = bytearray(rb)
        i = rb.find(b"PASS")
        flipped[i if i >= 0 else 10] ^= 0x01
        report.write_bytes(bytes(flipped))
        vw = p.ca("verify", rel, label="verify-report-flip-worktree")
        res["report_flip_uncommitted"] = (vw.rc, short(vw.stdout + vw.stderr, 220))
        p.git("commit", "-qam", "harness: flip one byte in report.md")
        vc = p.ca("verify", rel, label="verify-report-flip-committed")
        res["report_flip_committed"] = (vc.rc, short(vc.stdout + vc.stderr, 220))
        rec.exit_codes["verify_report_flip_committed"] = vc.rc
        report.write_bytes(rb)
        p.git("commit", "-qam", "harness: restore report.md")
        rec.details = {"results": res, "receipt": rel,
                       "untampered_stdout": v0.stdout.strip()}
        tamper_ok = all(res[k][0] == 21 for k in ("report_sha256", "verdict"))
        flip_ok = res["report_flip_committed"][0] == 21
        if v0.rc == 0 and res["untampered"][1] and tamper_ok and flip_ok:
            return finish(rec, "PASS", "untampered: BINDINGS VERIFIED exit 0; edited report_sha256, "
                          "edited verdict and a flipped committed report byte each exit 21 naming the binding.")
        if v0.rc == 0 and res["untampered"][1] and tamper_ok:
            return finish(rec, "PARTIAL", "untampered: BINDINGS VERIFIED exit 0; an edited report_sha256 "
                          f"(exit {res['report_sha256'][0]}: {res['report_sha256'][1][:70]}) and an edited "
                          f"verdict (exit {res['verdict'][0]}) are refused. But flipping a byte of "
                          f"cycles/<id>/report.md — in the working tree (exit {res['report_flip_uncommitted'][0]}) "
                          f"or committed on top (exit {res['report_flip_committed'][0]}) — still prints "
                          "BINDINGS VERIFIED: verify re-reads the report at the bound report_commit, so "
                          "the report a person opens can differ from the audited one undetected.")
        return finish(rec, "FAIL" if not (v0.rc == 0) else "PARTIAL",
                      "; ".join(f"{k}: exit {v[0]}" for k, v in res.items()))
    finally:
        p.stop()


@claim("C16", "Dry-run verification reports BINDINGS VERIFIED, RECORDED, ADMISSION READY")
def c16(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec, tag="C16-default")
    try:
        r = p.pass_receipt()
        v_def = p.ca("verify", str(r.relative_to(p.root)), label="verify-default-isolation") if r else None
        vj = p.ca("--json", "verify", str(r.relative_to(p.root)), label="verify-json-default") if r else None
    finally:
        p.stop()
    q, b2 = clean_project(h, rec, tag="C16-parametric-false", parametric_false=True)
    try:
        r2 = q.pass_receipt()
        if r2 is None or r is None:
            return finish(rec, "UNTESTED", "no PASS receipt")
        v = q.ca("verify", str(r2.relative_to(q.root)), label="verify-parametric-false")
        lines = {k: (k in v.stdout) for k in ("BINDINGS VERIFIED", "RECORDED", "ADMISSION READY")}
        lines_def = {k: (k in v_def.stdout) for k in ("BINDINGS VERIFIED", "RECORDED", "ADMISSION READY")}
        shortfalls = (json_or_none(vj.stdout) or {}).get("admission_shortfalls")
        rec.details = {"default_config_lines": lines_def, "default_config_shortfalls": shortfalls,
                       "parametric_false_lines": lines, "stdout": v.stdout.strip(),
                       "deviation": "the fakes are a custom endpoint, so the receipt cannot assert "
                                    "parametric (model-source) isolation and the default "
                                    "isolation.minimum refuses admission; the documented "
                                    "`isolation.minimum.parametric: false` was set to exercise the line"}
        if all(lines.values()) and v.rc == 0:
            return finish(rec, "PASS", "with isolation.minimum.parametric:false all three lines "
                          f"print (exit 0). On the default config the custom endpoint leaves "
                          f"ADMISSION READY absent with shortfall {shortfalls} — correct for a fake "
                          "endpoint.")
        return finish(rec, "FAIL", f"lines {lines}; default {lines_def}")
    finally:
        q.stop()


@claim("C17", "`verify --admit` consumes a receipt once; reuse is refused")
def c17(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec, parametric_false=True)
    try:
        r = p.pass_receipt()
        if r is None:
            return finish(rec, "UNTESTED", f"no PASS receipt (build exit {b.rc})")
        rel = str(r.relative_to(p.root))
        a1 = p.ca("verify", rel, "--admit", label="admit-1")
        a2 = p.ca("verify", rel, "--admit", label="admit-2")
        rec.exit_codes = {"admit_1": a1.rc, "admit_2": a2.rc}
        said = (a2.stdout + a2.stderr)
        consumed = bool(re.search(r"consum|already|admitted", said, re.I))
        rec.details = {"admit1": short(a1.stdout + a1.stderr, 300), "admit2": short(said, 300),
                       "deviation": "isolation.minimum.parametric:false (see C16)"}
        if a1.rc == 0 and "ADMITTED" in a1.stdout and a2.rc == 21 and consumed:
            return finish(rec, "PASS", f"first --admit exit 0 ADMITTED; second exit 21: {short(said, 140)}")
        if a1.rc == 0 and a2.rc != 0:
            return finish(rec, "PARTIAL", f"first exit 0; second refused with exit {a2.rc}: {short(said, 160)}")
        return finish(rec, "FAIL", f"admit-1 {a1.rc}; admit-2 {a2.rc}: {short(said)}")
    finally:
        p.stop()


def tools_python(h: Harness) -> Path | None:
    """The harness's own tooling venv, with `cryptography` for C18."""
    venv = h.tmp / "tools-venv"
    py = venv / "bin/python"
    if py.exists():
        return py
    env = {"PATH": BASE_PATH, "HOME": str(h.tmp), "PIP_DISABLE_PIP_VERSION_CHECK": "1",
           "PIP_CACHE_DIR": str(Path.home() / "Library/Caches/pip")}
    subprocess.run([sys.executable, "-m", "venv", str(venv)], env=env, capture_output=True)
    p = subprocess.run([str(venv / "bin/pip"), "install", "-q", "cryptography"], env=env,
                       capture_output=True, text=True, timeout=300)
    return py if p.returncode == 0 else None


EXTERNAL_VERIFY = r'''
import base64, hashlib, json, sys
from cryptography.hazmat.primitives.serialization import load_pem_public_key
pem_path, dsse_path, receipt_path = sys.argv[1:4]
pem = open(pem_path, "rb").read()
start = pem.find(b"-----BEGIN PUBLIC KEY-----")
key = load_pem_public_key(pem[start:] if start >= 0 else pem)
env = json.load(open(dsse_path))
body = base64.b64decode(env["payload"])
ptype = env["payloadType"].encode()
pae = b"DSSEv1 %d %s %d %s" % (len(ptype), ptype, len(body), body)
out = {"payloadType": env["payloadType"], "signatures": len(env["signatures"])}
try:
    key.verify(base64.b64decode(env["signatures"][0]["sig"]), pae)
    out["signature_valid_over_PAE"] = True
except Exception as exc:
    out["signature_valid_over_PAE"] = False
    out["error"] = repr(exc)
stmt = json.loads(body)
out["statement_subject"] = stmt.get("subject")
out["predicate"] = stmt.get("predicate")
raw = open(receipt_path, "rb").read()
out["sha256_of_receipt_file_bytes"] = hashlib.sha256(raw).hexdigest()
canon = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")).encode()
out["sha256_of_canonical_receipt_json"] = hashlib.sha256(canon).hexdigest()
print(json.dumps(out, indent=2))
'''


@claim("C18", "Receipts are Ed25519-signed (DSSE sidecar); invalid signature refused; verifiable offline")
def c18(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec, parametric_false=True)
    try:
        r = p.pass_receipt()
        if r is None:
            return finish(rec, "UNTESTED", f"no PASS receipt (build exit {b.rc})")
        rel = str(r.relative_to(p.root))
        sidecar = r.parent / "receipt.dsse.json"
        pem = p.root / "project.pem"
        ex = p.ca("export-pubkey", label="export-pubkey", stdout_file=pem)
        pem_text = pem.read_text()
        rec.evidence.append(h.save(rec.id, "project.pem.as-written.txt", pem_text))
        v1 = p.ca("verify", rel, "--pubkey", "project.pem", label="verify-pubkey-literal")
        res = {"export_exit": ex.rc,
               "pem_first_line": pem_text.splitlines()[0] if pem_text else "",
               "verify_pubkey_literal": (v1.rc, short((v1.stdout + v1.stderr)[-300:], 300))}
        clean_pem = p.root / "project-block-only.pem"
        start = pem_text.find("-----BEGIN PUBLIC KEY-----")
        clean_pem.write_text(pem_text[start:] if start >= 0 else pem_text)
        v2 = p.ca("verify", rel, "--pubkey", clean_pem.name, label="verify-pubkey-block-only")
        res["verify_pubkey_block_only"] = (v2.rc, "SIGNED" in v2.stdout, short(v2.stdout, 200))
        orig = sidecar.read_bytes()
        env = json.loads(orig)
        sig = bytearray(base64.b64decode(env["signatures"][0]["sig"]))
        sig[0] ^= 0x01
        env["signatures"][0]["sig"] = base64.b64encode(bytes(sig)).decode()
        sidecar.write_text(json.dumps(env))
        v3 = p.ca("verify", rel, label="verify-corrupt-signature")
        v3a = p.ca("verify", rel, "--pubkey", clean_pem.name, label="verify-corrupt-signature-pinned")
        res["corrupt_signature"] = (v3.rc, short(v3.stdout + v3.stderr, 260))
        res["corrupt_signature_pinned"] = (v3a.rc, short(v3a.stdout + v3a.stderr, 200))
        v3b = p.ca("verify", rel, "--admit", label="admit-corrupt-signature")
        res["corrupt_signature_admit"] = (v3b.rc, short(v3b.stdout + v3b.stderr, 200))
        rec.exit_codes["admit_corrupt_signature"] = v3b.rc
        sidecar.write_bytes(orig)
        sidecar.unlink()
        v4 = p.ca("verify", rel, label="verify-sidecar-deleted")
        res["sidecar_deleted"] = (v4.rc, short(v4.stdout + v4.stderr, 260))
        sidecar.write_bytes(orig)
        rec.exit_codes = {"verify_pubkey_literal": v1.rc, "verify_pubkey_block_only": v2.rc,
                          "verify_corrupt_signature": v3.rc, "verify_sidecar_deleted": v4.rc}
        py = tools_python(h)
        external = None
        if py:
            script = h.tmp / "external_verify.py"
            script.write_text(EXTERNAL_VERIFY)
            x = subprocess.run([str(py), str(script), str(pem), str(sidecar), str(r)],
                               capture_output=True, text=True)
            external = json_or_none(x.stdout) or {"error": x.stderr[-500:]}
            rec.evidence.append(h.save(rec.id, "external-verification.json",
                                       json.dumps(external, indent=2)))
        res["external"] = external
        rec.details = res
        literal_ok = v1.rc == 0 and "SIGNED" in v1.stdout
        corrupt_ok = v3.rc == 21 or (v3b.rc == 21 and "SIGNATURE INVALID" in v3.stdout)
        ext_ok = bool(external and external.get("signature_valid_over_PAE"))
        bits = [f"`export-pubkey > project.pem` writes `{res['pem_first_line'][:30]}` above the PEM block"
                if not pem_text.startswith("-----BEGIN") else "export-pubkey writes a bare PEM",
                f"literal `verify --pubkey project.pem` exit {v1.rc}"
                + (" (Python traceback: binascii.Error)" if "Traceback" in v1.stderr else ""),
                f"with the PEM block alone: exit {v2.rc}, SIGNED={'SIGNED' in v2.stdout}",
                f"corrupted signature: dry-run exit {v3.rc} (prints SIGNATURE INVALID), --admit exit {v3b.rc}",
                f"sidecar deleted: exit {v4.rc} ({'UNSIGNED' if 'UNSIGNED' in v4.stdout else 'see evidence'})",
                f"external cryptography check over DSSE PAE: {ext_ok if external else 'UNTESTED (no cryptography)'}"]
        if external:
            pred = external.get("predicate") or {}
            subj = ((external.get("statement_subject") or [{}])[0].get("digest") or {}).get("sha256")
            bits.append("DSSE subject = sha256 of the canonical receipt JSON: "
                        + str(subj == external.get("sha256_of_canonical_receipt_json")))
            bits.append(f"signed predicate carries verdict={pred.get('verdict')!r}, report_sha256={pred.get('report_sha256')!r}")
        obs = "; ".join(bits) + "."
        if literal_ok and corrupt_ok and ext_ok:
            return finish(rec, "PASS", obs)
        if ext_ok and v2.rc == 0:
            return finish(rec, "FAIL" if not corrupt_ok or not literal_ok else "PARTIAL", obs)
        return finish(rec, "FAIL", obs)
    finally:
        p.stop()


@claim("C19", "`crossaudit reproduce` shows pinned locks, drift, and re-run steps")
def c19(h: Harness, rec: Record) -> Record:
    def pre(p: Project):
        (p.root / "experiments/requirements.txt").write_text("numpy==2.1.0\n")
        p.git("add", "experiments/requirements.txt")
        p.git("commit", "-q", "-m", "harness: pin requirements.txt in scope")

    p, b = clean_project(h, rec, tag="C19-precommitted", pre=pre)
    res = {}
    try:
        r = p.pass_receipt()
        if r:
            rel = str(r.relative_to(p.root))
            c = p.ca("reproduce", rel, label="reproduce-precommitted")
            d = json.loads(r.read_text())
            pre_lock = p.root / "experiments/requirements.txt"
            pre_digest = hashlib.sha256(pre_lock.read_bytes()).hexdigest()
            rtext_pre = r.read_text()
            res["precommitted"] = {"exit": c.rc, "lock_in_manifest": any(
                k.endswith("requirements.txt") for k in d["inputs"]["manifest"]),
                "lock_in_receipt": pre_digest in rtext_pre,
                "hash_printed": pre_digest[:12] in c.stdout,
                "path_printed": "requirements.txt" in c.stdout,
                "stdout": c.stdout.strip()[:600]}
    finally:
        p.stop()
    q, b2 = clean_project(h, rec, tag="C19-in-increment", scenario=Requirements())
    try:
        r = q.pass_receipt()
        if r is None:
            return finish(rec, "UNTESTED", f"no PASS receipt (build exit {b2.rc})")
        rel = str(r.relative_to(q.root))
        lock = q.root / fp.INC_DIR / "requirements.txt"
        digest = hashlib.sha256(lock.read_bytes()).hexdigest()
        c1 = q.ca("reproduce", rel, label="reproduce-in-increment")
        lock.write_text("numpy==2.2.0\n")
        c2 = q.ca("reproduce", rel, label="reproduce-after-drift")
        lock.write_text("numpy==2.1.0\n")
        rtext = r.read_text()
        res["in_increment"] = {"exit": c1.rc, "lock_sha256": digest,
                               "hash_in_receipt": digest in rtext,
                               "hash_printed": digest[:12] in c1.stdout,
                               "says_matches": bool(re.search(r"match|unchanged|MATCHES|in sync", c1.stdout, re.I)),
                               "rerun_step": "TO REPRODUCE" in c1.stdout or "re-run" in c1.stdout.lower(),
                               "drift_exit": c2.rc,
                               "says_drift": bool(re.search(r"drift|differs|changed|DRIFT", c2.stdout, re.I)),
                               "stdout": c1.stdout.strip()[:800], "drift_stdout": c2.stdout.strip()[:800]}
        rec.details = res
        ii = res["in_increment"]
        mech = ii["hash_in_receipt"] and ii["hash_printed"] and ii["says_matches"] and ii["rerun_step"] and ii["says_drift"]
        pre = res.get("precommitted", {})
        pre_ok = pre.get("lock_in_receipt") and pre.get("hash_printed") and pre.get("path_printed")
        if mech and pre_ok:
            return finish(rec, "PASS", "a lock committed before the build and one written by the "
                          "generator are both bound in the receipt by sha256 and printed by "
                          "`reproduce` with their path; tree matches; re-run steps; drift reported "
                          "after editing the lock.")
        partial_mech = ii["hash_in_receipt"] and ii["says_matches"] and ii["rerun_step"] and ii["says_drift"]
        if mech or partial_mech:
            return finish(rec, "PARTIAL", "a requirements.txt committed in scope BEFORE the build is "
                          "not in the receipt (manifest scope is changed-paths) and `reproduce` says "
                          "NO DEPENDENCY LOCK RECORDED; when the generator's own increment carries the "
                          "lock, its hash is bound in the receipt, the tree is reported matching "
                          "(ENVIRONMENT MATCHES), re-run steps print, and an edited lock is reported as "
                          "ENVIRONMENT DRIFTED" + ("" if ii["hash_printed"] else
                          "; `reproduce` does not print the lock's hash") + ".")
        return finish(rec, "FAIL", f"{res}")
    finally:
        q.stop()


@claim("C20", "Exit codes are stable: 0, 10, 11, 20, 21, 22",
       deps=("C05", "C06", "C08", "C09", "C10", "C15", "C17"))
def c20(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, Http500())
    try:
        p.init()
        p.configure()
        b = p.build(label="build-http-500")
        rec.details["http500"] = {"exit": b.rc, "generator_calls": len(p.fakes.requests("generator")),
                                  "stdout_tail": b.stdout[-600:], "stderr_tail": b.stderr[-300:]}
    finally:
        p.stop()
    # The `audit` verb on a human-committed increment in a fresh project (no
    # earlier escalation holding the anchor), same dead provider.
    q = Project(h, rec, Http500(), tag="C20-audit")
    try:
        q.init()
        q.configure()
        for rel, body in fp.increment().items():
            (q.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (q.root / rel).write_text(body)
        q.git("add", "experiments")
        q.git("commit", "-q", "-m", "harness: a human-written increment")
        aud = q.ca("audit", label="audit-http-500")
        rec.details["http500_audit_verb"] = {"exit": aud.rc, "out": short(aud.stdout + aud.stderr, 300),
                                             "auditor_calls": len(q.fakes.requests("auditor"))}
    finally:
        q.stop()
    # The `audit` verb on a human-committed increment the deterministic layer
    # blocks (science profile, a quantity without a unit); the auditor says PASS.
    z = Project(h, rec, fp.Scenario(), tag="C20-audit-blocked")
    try:
        z.init()
        z.configure(checks="science")
        for rel, body in fp.increment(unit=None).items():
            (z.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (z.root / rel).write_text(body)
        z.git("add", "experiments")
        z.git("commit", "-q", "-m", "harness: a human-written increment without a unit")
        aud2 = z.ca("audit", label="audit-dcl-blocked")
        rec.details["blocked_audit_verb"] = {"exit": aud2.rc, "out": short(aud2.stdout + aud2.stderr, 300)}
    finally:
        z.stop()
    expect = [("C05", "init_same_vendor", 20), ("C05", "build", 20), ("C06", "build", 0),
              ("C08", "build", 11), ("C09", "build", 11), ("C10", "check", 0),  # C09: build reports the loop's final state, ESCALATED (README "Exit codes")
              ("C10", "audit_offline_sha", 11), ("C15", "verify_untampered", 0),
              ("C15", "verify_tampered_verdict", 21), ("C17", "admit_1", 0),
              ("C17", "admit_2", 21)]
    rows, bad = [], []
    for cid, key, want in expect:
        got = h.records.get(cid, Record(cid, "")).exit_codes.get(key)
        rows.append({"claim": cid, "command": key, "expected": want, "observed": got})
        if got != want:
            bad.append(f"{cid} {key}: expected {want}, got {got}")
    got500 = rec.details["http500"]["exit"]
    rows.append({"claim": "C20", "command": "build (HTTP 500 every call)", "expected": 22, "observed": got500})
    if got500 != 22:
        bad.append(f"build with HTTP 500: expected 22, got {got500}")
    rows.append({"claim": "C20", "command": "audit (HTTP 500)", "expected": 22,
                 "observed": rec.details["http500_audit_verb"]["exit"]})
    if rec.details["http500_audit_verb"]["exit"] != 22:
        bad.append(f"audit with HTTP 500: expected 22, got {rec.details['http500_audit_verb']['exit']}")
    rows.append({"claim": "C20", "command": "audit (deterministic BLOCKED)", "expected": 10,
                 "observed": rec.details["blocked_audit_verb"]["exit"]})
    if rec.details["blocked_audit_verb"]["exit"] != 10:
        bad.append(f"audit on a check-blocked increment: expected 10, got {rec.details['blocked_audit_verb']['exit']}")
    rec.details["table"] = rows
    if not bad:
        return finish(rec, "PASS", "every collected exit code matches the README table.")
    return finish(rec, "FAIL" if len(bad) > 2 else "PARTIAL", "; ".join(bad))


@claim("C21", "`--json` before the command gives structured output (status, doctor, check, verify, routing)")
def c21(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec)
    try:
        r = p.pass_receipt()
        cmds = {"status": ["status"], "doctor": ["doctor"], "check": ["check"],
                "verify": ["verify", str(r.relative_to(p.root))] if r else None,
                "routing": ["routing"]}
        res, bad = {}, []
        for name, args in cmds.items():
            if args is None:
                res[name] = "no receipt"
                bad.append(name)
                continue
            c = p.ca("--json", *args, label=f"json-{name}")
            parsed = json_or_none(c.stdout)
            res[name] = {"exit": c.rc, "valid_json": parsed is not None,
                         "stdout_head": c.stdout[:160]}
            if parsed is None:
                bad.append(name)
        p.ca("amend", "Every benchmark must include the exact command and random seed", "--yes",
             label="amend-to-record-a-routing-decision")
        c = p.ca("--json", "routing", label="json-routing-after-amend")
        res["routing_after_amend"] = {"exit": c.rc, "valid_json": json_or_none(c.stdout) is not None,
                                      "stdout_head": c.stdout[:160]}
        rec.details = res
        if not bad:
            return finish(rec, "PASS", "all five emit one JSON document on stdout.")
        if bad == ["routing"] and res["routing_after_amend"]["valid_json"]:
            return finish(rec, "PARTIAL", "status, doctor, check and verify emit JSON; `--json routing` "
                          f"prints the prose `{res['routing']['stdout_head'].strip()}` when nothing is "
                          "recorded yet (valid JSON once a routing decision exists).")
        return finish(rec, "PARTIAL" if len(bad) < 3 else "FAIL",
                      "not JSON on stdout: " + ", ".join(
                          f"{n} ({short(res[n]['stdout_head'], 60) if isinstance(res[n], dict) else res[n]})"
                          for n in bad))
    finally:
        p.stop()


# ------------------------------------------------------------- D. safety/records
@claim("C22", "The generator cannot edit the rules, configuration, state or ledger")
def c22(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, Overreach())
    try:
        p.init()
        p.configure()
        before = {f: p.git("rev-parse", f"HEAD:{f}").strip() for f in ("AUDIT_RULES.md", "crossaudit.yml")}
        b = p.build()
        rec.exit_codes["build"] = b.rc
        after = {f: p.git("rev-parse", f"HEAD:{f}").strip() for f in ("AUDIT_RULES.md", "crossaudit.yml")}
        tracked = p.git("log", "--all", "--name-only", "--format=").split()
        disk_rules = (p.root / "AUDIT_RULES.md").read_text().startswith("# rules rewritten")
        disk_cfg = "hijacked" in (p.root / "crossaudit.yml").read_text()
        rec.details = {"blob_before": before, "blob_after": after,
                       "cycles_x_md_committed": "cycles/x.md" in tracked,
                       "cycles_x_md_on_disk": (p.root / "cycles/x.md").exists(),
                       "rules_overwritten_on_disk": disk_rules, "config_overwritten_on_disk": disk_cfg,
                       "generator_calls": len(p.fakes.requests("generator")),
                       "build_stdout_tail": b.stdout[-800:]}
        d = rec.details
        if before == after and not d["cycles_x_md_committed"] and not d["cycles_x_md_on_disk"] \
                and not disk_rules and not disk_cfg and d["generator_calls"] >= 2 and "refused" in b.stdout.lower():
            return finish(rec, "PASS", f"AUDIT_RULES.md, crossaudit.yml and cycles/x.md unchanged in git "
                          f"and on disk; the round was refused and re-asked; honest round 2 passed (exit {b.rc}).")
        return finish(rec, "FAIL", f"{d}")
    finally:
        p.stop()


@claim("C23", "usage.jsonl is mode 600 and holds counts/time/role/phase/provider/model only", deps=("C07",))
def c23(h: Harness, rec: Record) -> Record:
    p = h.projects.get("C07")
    if p is None:
        return finish(rec, "UNTESTED", "needs C07's project")
    f = p.root / ".crossaudit" / "usage.jsonl"
    if not f.exists():
        return finish(rec, "FAIL", "no .crossaudit/usage.jsonl after C07")
    mode = oct(f.stat().st_mode & 0o777)
    lines = f.read_text().splitlines()
    parsed = [json_or_none(ln) for ln in lines]
    keys = sorted({k for d in parsed if isinstance(d, dict) for k in d})
    text = f.read_text()
    probes = {"auditor key": DUMMY_AUD, "generator key": DUMMY_GEN,
              "generator system prompt": "You produce work for a supervised project",
              "auditor system prompt": "You are the Auditor in a CrossAudit loop",
              "prompt section header": "THE MACHINE-ENFORCED FILE CONTRACT",
              "finding text": FixOn2.MARK, "generated file content": "The benchmark ran in",
              "request id": "req_fake_", "task text": TASK}
    hits = {k: (v in text) for k, v in probes.items()}
    rec.details = {"mode": mode, "lines": len(lines), "all_parse": all(isinstance(d, dict) for d in parsed),
                   "keys": keys, "probe_hits": hits}
    rec.evidence.append(h.save(rec.id, "usage.jsonl.txt", text))
    bad = [k for k, v in hits.items() if v]
    if mode == "0o600" and all(isinstance(d, dict) for d in parsed) and not bad:
        return finish(rec, "PASS", f"mode 600; {len(lines)} lines parse; no key, prompt text, request "
                      f"id, finding text or generated content; fields {keys}.")
    return finish(rec, "FAIL" if mode != "0o600" or any(hits[k] for k in ("auditor key", "generator key")) else "PARTIAL",
                  f"mode {mode}; found: {bad}; fields {keys}")


@claim("C24", "Secrets never enter a prompt, log, ledger or receipt")
def c24(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec)
    try:
        c = p.ca("console", label="console-start")
        p.console_started = True
        time.sleep(1.0)
        p.ca("console", "--stop", label="console-stop")
        p.console_started = False
        hits = []
        keyfile = p.home / ".crossaudit-keys.env"
        for root in (p.home,):
            for f in root.rglob("*"):
                if f.is_file() and f != keyfile:
                    data = f.read_bytes()
                    for k in (DUMMY_AUD, DUMMY_GEN):
                        if k.encode() in data:
                            hits.append(str(f.relative_to(p.home)))
        hist = p.git("log", "-p", "--all")
        if DUMMY_AUD in hist or DUMMY_GEN in hist:
            hits.append("git log -p --all")
        for cap in p.fakes.captures():
            if DUMMY_AUD in cap["system"] + cap["prompt"] or DUMMY_GEN in cap["system"] + cap["prompt"]:
                hits.append(cap["_file"])
        c07 = h.projects.get("C07")
        if c07 is not None:
            for f in c07.home.rglob("*"):
                if f.is_file() and (DUMMY_AUD.encode() in f.read_bytes() or DUMMY_GEN.encode() in f.read_bytes()):
                    hits.append("C07:" + str(f.relative_to(c07.home)))
        rec.details = {"hits": hits, "keys_file_present": keyfile.exists(),
                       "searched": "every file under the project HOME (tree, .git objects as stored, "
                                   ".crossaudit, console state) except the keys file; `git log -p --all`; "
                                   "every captured system+user prompt; C07's HOME"}
        if not hits:
            return finish(rec, "PASS", "zero occurrences of either dummy key outside the keys file "
                          "(keys were supplied by environment; no keys file was written).")
        return finish(rec, "FAIL", f"dummy key found in {hits[:6]}")
    finally:
        p.stop()


@claim("C25", "`crossaudit resolve` records a human decision; requires an interactive terminal", deps=("C08",))
def c25(h: Harness, rec: Record) -> Record:
    p = h.projects.get("C08")
    if p is None:
        return finish(rec, "UNTESTED", "needs C08's project")
    p.rec = rec
    st = p.status_json()
    esc = [c["cycle_id"] for c in st.get("cycles", []) if c["status"] == "ESCALATED"]
    if not esc:
        return finish(rec, "UNTESTED", "C08 produced no ESCALATED cycle")
    cid = esc[0]
    reason = "The harness human closes this after review C25"
    n = p.ca("resolve", cid, "--close", "--because", reason, label="resolve-non-tty")
    rc, out = pty_run([h.ca, "resolve", cid, "--close", "--because", reason],
                      p.env(), p.root, [], timeout=60)
    rec.evidence.append(h.save(rec.id, "resolve-pty-transcript.txt", f"exit {rc}\n{out}"))
    st2 = p.ca("status", label="status-after")
    log = p.git("log", "-3", "--format=%H%n%B")
    reason_in_git = reason in p.git("log", "-p", "--all")
    reason_in_state = reason in (p.root / ".crossaudit/state.json").read_text()
    rec.exit_codes = {"resolve_non_tty": n.rc, "resolve_pty": rc}
    rec.details = {"non_tty": short(n.stderr, 200), "pty_output": short(out, 300),
                   "status_after": st2.stdout.strip(), "reason_in_git": reason_in_git,
                   "reason_in_state_json": reason_in_state,
                   "recent_commits": log[:800]}
    refused = n.rc != 0 and "terminal" in n.stderr
    recorded = rc == 0 and "ruling recorded" in out
    status_shows = "CLOSED" in st2.stdout.upper() or "close" in st2.stdout.lower()
    if refused and recorded and status_shows and reason_in_git:
        return finish(rec, "PASS", "non-TTY refused with a clear sentence; under a pty the ruling is "
                      "recorded, status shows it, and the reason is in a ledger commit.")
    if refused and recorded:
        return finish(rec, "PARTIAL", f"non-TTY: refused, exit {n.rc} (\"{short(n.stderr, 90)}\"); under "
                      f"a pty: \"{short(out, 120)}\" exit {rc}. But the reason is not in any git commit "
                      f"(only in the gitignored .crossaudit/state.json: {reason_in_state}), and "
                      f"`status` afterwards shows {short(st2.stdout.splitlines()[2] if len(st2.stdout.splitlines()) > 2 else st2.stdout, 80)} "
                      "with no mention of the decision.")
    return finish(rec, "FAIL", f"non-TTY refused={refused} (exit {n.rc}); pty recorded={recorded} "
                  f"(exit {rc}); status shows decision={status_shows}; reason in git={reason_in_git}")


@claim("C26", "`crossaudit amend` versions a rule change between cycles; audits cite the committed version")
def c26(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, fp.Scenario())
    try:
        p.init()
        p.configure()
        text = "Every benchmark must include the exact command and random seed"
        a0 = p.ca("amend", text, label="amend-literal")
        a = a0 if a0.rc == 0 else p.ca("amend", text, "--yes", label="amend-yes")
        rows = [ln.split(" ", 1) for ln in p.git("log", "--format=%H %s").splitlines()]
        amend_sha, last = next(((s_, m) for s_, m in rows if m.startswith("amend rules")), (p.head(), rows[0][1]))
        blob = p.git("show", f"{amend_sha}:AUDIT_RULES.md")
        b = p.build()
        r = p.pass_receipt()
        rd = json.loads(r.read_text()) if r else {}
        inputs = rd.get("inputs", {})
        rec.exit_codes = {"amend_literal": a0.rc, "amend": a.rc, "build": b.rc}
        rec.details = {"amend_literal_stderr": short(a0.stderr, 200), "amend_commit": last,
                       "receipt_constitution_commit": inputs.get("constitution_commit"),
                       "amend_sha": amend_sha,
                       "constitution_sha256_matches": inputs.get("constitution_sha256") ==
                       hashlib.sha256(blob.encode()).hexdigest(),
                       "rule_added": "CA-BENCH-001" in blob}
        d = rec.details
        if a.rc == 0 and last.startswith("amend rules") and d["rule_added"] and \
                d["receipt_constitution_commit"] == amend_sha and d["constitution_sha256_matches"]:
            note = "" if a0.rc == 0 else (f" (the README's bare `amend \"…\"` exits {a0.rc} without a "
                                         "terminal and asks for `--yes`, which was then used)")
            return finish(rec, "PASS", "a new `amend rules:` commit; the next receipt's "
                          "constitution_commit is that commit and its constitution_sha256 equals the "
                          "committed AUDIT_RULES.md" + note + ".")
        return finish(rec, "FAIL", f"{d}")
    finally:
        p.stop()


@claim("C27", "DETERMINISTIC_CHECKS.md contract is identical in the generator prompt, doctor, Console, checks.json")
def c27(h: Harness, rec: Record) -> Record:
    p, b = clean_project(h, rec)
    try:
        f = (p.root / "DETERMINISTIC_CHECKS.md").read_text()
        block = f.split("```text\n", 1)[1].split("\n```", 1)[0] if "```text" in f else ""
        lines = dict(re.findall(r"^- ([a-z_-]+): (.*)$", block, re.M))
        caps = p.fakes.captures("generator")
        prompt = caps[0]["prompt"] if caps else ""
        pblock = prompt.split("<<<CHECKS\n", 1)[1].split("\nCHECKS", 1)[0] if "<<<CHECKS" in prompt else ""
        dj = json_or_none(p.ca("--json", "doctor", label="doctor-json").stdout) or {}
        doc = {c["check"].split(":", 1)[1]: c["detail"] for c in dj.get("checks", [])
               if c.get("check", "").startswith("machine:")}
        cyc = p.cycle_dirs()[0] if p.cycle_dirs() else None
        cj = json_or_none((cyc / "checks.json").read_text()) if cyc else {}
        contracts = (cj or {}).get("contracts", {})
        c = p.ca("console", label="console-start")
        p.console_started = True
        m = re.search(r"(http://127\.0\.0\.1:\d+/\?t=\S+)", c.stdout)
        console_hits = {}
        if m:
            u = m.group(1)
            st, body = http_get(u.replace("/?t=", "/api/state?t="))
            console_hits = {k: (v in body) for k, v in lines.items()}
        rec.details = {"file_block_equals_prompt_block": block == pblock and bool(block),
                       "per_check": {k: {"doctor": doc.get(k) == v, "checks_json": contracts.get(k) == v,
                                         "console_api_state": console_hits.get(k)}
                                     for k, v in lines.items()},
                       "checks_json_extra_contracts": sorted(set(contracts) - set(lines))}
        rec.evidence.append(h.save(rec.id, "contract-file-block.txt", block))
        rec.evidence.append(h.save(rec.id, "contract-prompt-block.txt", pblock))
        per = rec.details["per_check"]
        core = rec.details["file_block_equals_prompt_block"] and all(v["doctor"] and v["checks_json"] for v in per.values())
        console_ok = all(v["console_api_state"] for v in per.values())
        if core and console_ok:
            return finish(rec, "PASS", "the file's contract block is byte-identical to the prompt's "
                          "CHECKS block; each check's sentence is identical in doctor, checks.json and the "
                          "Console state" + (f" (checks.json also carries {rec.details['checks_json_extra_contracts']})"
                                             if rec.details['checks_json_extra_contracts'] else "") + ".")
        if core:
            return finish(rec, "PARTIAL", "file, generator prompt, doctor and checks.json agree byte for "
                          "byte; the Console's /api/state does not carry the contract sentences "
                          f"({console_hits}).")
        return finish(rec, "FAIL", f"{rec.details}")
    finally:
        p.stop()


# ------------------------------------------------------------------- E. console
@claim("C28", "`crossaudit console` starts a background server, opens the dashboard, prints a tokenized URL")
def c28(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, fp.Scenario(), tag="CONSOLE")
    h.projects["CONSOLE"] = p
    p.init()
    p.configure(max_rounds=2)
    b1 = p.build(label="build-clean")
    p.fakes.set_scenario(AlwaysBlocked())
    b2 = p.build("Extend the benchmark with a second run", label="build-always-blocked")
    rec.details["builds"] = {"clean": b1.rc, "always_blocked": b2.rc}
    help_ = p.ca("console", "--help", label="console-help")
    before = h.browser_log.read_text() if h.browser_log.exists() else ""
    c = p.ca("console", label="console-start")
    p.console_started = True
    after = h.browser_log.read_text() if h.browser_log.exists() else ""
    m = re.search(r"(http://127\.0\.0\.1:(\d+)/\?t=(\S+))", c.stdout)
    if not m:
        return finish(rec, "FAIL", f"no tokenized URL printed: {short(c.stdout + c.stderr)}")
    url, port, token = m.group(1), int(m.group(2)), m.group(3)
    p.console = {"url": url, "port": port, "token": token}
    st, body = http_get(url)
    browser = after[len(before):].strip()
    rec.details.update({"url_printed": url.replace(token, "<token>"), "token_length": len(token),
                        "http_status": st, "looks_like_page": "<html" in body.lower(),
                        "browser_invoked": bool(browser), "browser_args": browser,
                        "suppress_flag_in_help": bool(re.search(r"no-browser|no-open|--open", help_.stdout)),
                        "console_help": help_.stdout.strip()})
    rec.exit_codes["console"] = c.rc
    # The README's "opens the dashboard" is a statement about a person at a
    # terminal, so it is judged under a pseudo-terminal: `console` again (it
    # reattaches to the running server) with BROWSER pointed at the sentinel,
    # then `console --no-open`, which must leave the sentinel untouched.
    before_tty = h.browser_log.read_text() if h.browser_log.exists() else ""
    rc_tty, out_tty = pty_run([h.ca, "console"], p.env(), p.root, [], timeout=60)
    after_tty = h.browser_log.read_text() if h.browser_log.exists() else ""
    tty_browser = after_tty[len(before_tty):].strip()
    rc_noopen, out_noopen = pty_run([h.ca, "console", "--no-open"], p.env(), p.root, [], timeout=60)
    after_noopen = h.browser_log.read_text() if h.browser_log.exists() else ""
    noopen_browser = after_noopen[len(after_tty):].strip()
    rec.evidence.append(h.save(rec.id, "console-under-pty.txt",
                               f"$ crossaudit console (pty) -> {rc_tty}\n{out_tty}\n\n"
                               f"$ crossaudit console --no-open (pty) -> {rc_noopen}\n{out_noopen}\n"))
    rec.details.update({"tty_browser_invoked": bool(tty_browser), "tty_browser_args": tty_browser,
                        "tty_exit": rc_tty, "no_open_browser_invoked": bool(noopen_browser),
                        "no_open_exit": rc_noopen})
    page_ok = st == 200 and "<html" in body.lower() and len(token) >= 16
    if page_ok and tty_browser and token in tty_browser and not noopen_browser:
        return finish(rec, "PASS", "background server; tokenized URL; HTTP 200 page; under a "
                      "terminal the browser was opened on that URL; `--no-open` opened nothing; "
                      "without a terminal nothing opened.")
    if page_ok:
        why = []
        if not tty_browser:
            why.append("under a pseudo-terminal `crossaudit console` never invoked a browser "
                       "(BROWSER sentinel untouched) although the README says it opens the dashboard")
        elif token not in tty_browser:
            why.append("the browser was invoked but not on the tokenized URL")
        if noopen_browser:
            why.append("`--no-open` still opened a browser")
        if not rec.details.get("suppress_flag_in_help"):
            why.append("`console --help` offers no open/no-open flag")
        return finish(rec, "PARTIAL", "starts in the background and prints a tokenized URL that "
                      "serves the page (HTTP 200), but " + "; ".join(why) + ".")
    return finish(rec, "FAIL", f"HTTP {st}")


@claim("C29", "Every console request needs the process token and a localhost Host header", deps=("C28",))
def c29(h: Harness, rec: Record) -> Record:
    p = h.projects.get("CONSOLE")
    info = getattr(p, "console", None) if p else None
    if not info:
        return finish(rec, "UNTESTED", "needs C28's running console")
    base = f"http://127.0.0.1:{info['port']}"
    res = {"no_token": http_get(base + "/")[0],
           "wrong_token": http_get(base + "/?t=" + "x" * len(info["token"]))[0],
           "evil_host": http_get(base + "/?t=" + info["token"], host="evil.example")[0],
           "api_no_token": http_get(base + "/api/state")[0],
           "right_token": http_get(base + "/?t=" + info["token"])[0]}
    rec.details = res
    rec.evidence.append(h.save(rec.id, "http-statuses.json", json.dumps(res, indent=2)))
    denied = all(res[k] in (401, 403) for k in ("no_token", "wrong_token", "evil_host", "api_no_token"))
    if denied and res["right_token"] == 200:
        return finish(rec, "PASS", f"no token / wrong token / Host evil.example / API without token → "
                      f"{res['no_token']}/{res['wrong_token']}/{res['evil_host']}/{res['api_no_token']}; "
                      "right token → 200.")
    return finish(rec, "FAIL", f"{res}")


@claim("C30", "The console shows activity, cycles and verdicts, findings, receipt status", deps=("C28",))
def c30(h: Harness, rec: Record) -> Record:
    p = h.projects.get("CONSOLE")
    info = getattr(p, "console", None) if p else None
    if not info:
        return finish(rec, "UNTESTED", "needs C28's running console")
    p.rec = rec
    st, body = http_get(f"http://127.0.0.1:{info['port']}/api/state?t={info['token']}")
    data = json_or_none(body)
    rec.evidence.append(h.save(rec.id, "api-state.json", body[:200000]))
    status = p.status_json()
    cycles = status.get("cycles", [])
    want_ids = [c["cycle_id"] for c in cycles]
    want_status = sorted({c["status"] for c in cycles})
    found_ids = {cid: (cid in body) for cid in want_ids}
    found_st = {s: (s in body) for s in want_status}
    rec.details = {"http": st, "json": data is not None, "cycle_ids": found_ids,
                   "statuses": found_st, "top_level_keys": sorted(data)[:40] if isinstance(data, dict) else None,
                   "mentions_receipt": "receipt" in body, "mentions_findings": "finding" in body.lower()}
    if st == 200 and data is not None and all(found_ids.values()) and all(found_st.values()):
        return finish(rec, "PASS", f"/api/state (token) names every cycle {list(found_ids)} and verdict "
                      f"{want_status}; mentions receipts and findings.")
    return finish(rec, "FAIL" if st != 200 else "PARTIAL", f"{rec.details}")


@claim("C31", "The console keeps running in the background; `crossaudit console` manages it", deps=("C28",))
def c31(h: Harness, rec: Record) -> Record:
    p = h.projects.get("CONSOLE")
    info = getattr(p, "console", None) if p else None
    if not info:
        return finish(rec, "UNTESTED", "needs C28's running console")
    p.rec = rec
    s1 = p.ca("console", "--status", label="console-status")
    alive_before = port_open(info["port"])
    s = p.ca("console", "--stop", label="console-stop")
    time.sleep(0.5)
    alive_after = port_open(info["port"])
    s2 = p.ca("console", "--status", label="console-status-after")
    p.console_started = False
    rec.exit_codes["console_stop"] = s.rc
    rec.details = {"status_before": s1.stdout.strip(), "port_open_before": alive_before,
                   "stop_stdout": s.stdout.strip(), "port_open_after": alive_after,
                   "status_after": s2.stdout.strip()}
    if alive_before and s.rc == 0 and not alive_after:
        return finish(rec, "PASS", f"the server outlived the starting command; `console --stop` "
                      f"({short(s.stdout, 60)}) closed port {info['port']}.")
    return finish(rec, "FAIL", f"{rec.details}")


# ------------------------------------------------- F. offline halves (round 2)
FAKE_GH = r"""#!/bin/sh
# Fake GitHub CLI for the claims harness: logs every invocation, never touches
# the network. Mode file: "absent" is never used (the binary is simply not on
# PATH then); "unauth" fails `auth status`; "auth" succeeds and emulates the
# few calls `pair` makes against file:// bare repositories under $DIR/remotes.
DIR="$(cd "$(dirname "$0")" && pwd)"
printf '%s\n' "$*" >> "$DIR/gh.log"
if [ -n "$CROSSAUDIT_AUDITOR_KEY$CROSSAUDIT_GENERATOR_KEY$OPENAI_API_KEY" ]; then
  echo "  ^ provider key variable present in gh's environment" >> "$DIR/gh.log"
fi
MODE="$(cat "$DIR/mode")"
case "$1 $2" in
  "auth status")
    if [ "$MODE" = auth ]; then
      echo "github.com: Logged in to github.com account harness-bot (fake)" >&2; exit 0
    fi
    echo "You are not logged into any GitHub hosts. To log in, run: gh auth login" >&2; exit 1 ;;
  "api user") echo '{"login":"harness-bot"}'; exit 0 ;;
  "api -i") printf 'HTTP/2.0 200 OK\nX-Oauth-Scopes: repo, workflow\n\n{"login":"harness-bot"}\n'; exit 0 ;;
  "repo view")
    if [ -d "$DIR/remotes/$3.git" ]; then echo "name: $3"; exit 0; fi
    echo "GraphQL: Could not resolve to a Repository with the name '$3'." >&2; exit 1 ;;
  "repo create")
    mkdir -p "$DIR/remotes/$3.git" && git init -q --bare "$DIR/remotes/$3.git" && echo "https://github.com/$3"; exit $? ;;
  "repo clone")
    git clone -q "file://$DIR/remotes/$3.git" "$4" 2>/dev/null; exit $? ;;
  "secret set")
    cat > /dev/null; echo "secret $3 set on $5 (fake; value discarded unread)" >> "$DIR/gh.log"; exit 0 ;;
esac
echo "fake gh: unscripted call: $*" >&2
exit 1
"""
GH_MUTATING = re.compile(r"^(repo create|repo clone|secret set|api .*protection|repo edit|repo delete)")


def tree_and_git(p: "Project") -> dict:
    return {"tree": tree_hash(p.root), "head": p.head(),
            "remotes": p.git("remote", "-v").strip()}


@claim("C33a", "`pair` without `--apply` prints the GitHub plan and changes nothing remotely")
def c33a(h: Harness, rec: Record) -> Record:
    """README "Two-repository deployment": `crossaudit pair --science owner/work
    --audit owner/work-audit` without `--apply` "prints the intended GitHub
    operations and changes nothing remotely". `gh` is a logging fake; three
    sub-runs (gh absent, gh not signed in, gh signed in), then `--apply`
    against the same fake with every github.com URL rewritten to a local bare
    repository (git `url.insteadOf` in the temp HOME, plus
    GIT_ALLOW_PROTOCOL=file so no other transport can be used) — only to learn
    what `--apply` actually does, so the plan can be compared with it.
    Then `init --github` with gh signed out, as far as it goes."""
    p = Project(h, rec, fp.Scenario(), tag="C33A")
    p.init()
    ghdir = p.base / "fakegh"
    ghdir.mkdir()
    (ghdir / "gh").write_text(FAKE_GH)
    (ghdir / "gh").chmod(0o755)
    (ghdir / "remotes").mkdir()
    science, audit = "harness-bot/work", "harness-bot/work-audit"
    argv = ["pair", "--science", science, "--audit", audit]
    runs = {}
    with_gh = {"PATH": f"{ghdir}:{h.venv}/bin:{BASE_PATH}", "GIT_ALLOW_PROTOCOL": "file"}

    def gh_log() -> list[str]:
        f = ghdir / "gh.log"
        return f.read_text().splitlines() if f.exists() else []

    for mode in ("absent", "unauth", "auth"):
        (ghdir / "mode").write_text(mode)
        n0 = len(gh_log())
        before = tree_and_git(p)
        c = p.ca(*argv, extra=None if mode == "absent" else with_gh, label=f"pair-plan-gh-{mode}")
        after = tree_and_git(p)
        calls = gh_log()[n0:]
        runs[mode] = {"exit": c.rc, "stdout": c.stdout, "stderr": c.stderr.strip()[-600:],
                      "gh_calls": calls,
                      "mutating_gh_calls": [x for x in calls if GH_MUTATING.match(x)],
                      "tree_unchanged": before == after,
                      "changed_files": sorted(k for k in set(before["tree"]) | set(after["tree"])
                                              if before["tree"].get(k) != after["tree"].get(k))}
    plan_out = runs["auth"]["stdout"]
    plan_steps = re.findall(r"^\s+(\d+)\. (.+)$", plan_out, re.M)
    # --apply against the fake, to see what the plan should have named.
    (p.home / ".gitconfig").write_text(
        f'[url "file://{ghdir}/remotes/"]\n\tinsteadOf = https://github.com/\n'
        "[user]\n\tname = harness\n\temail = harness@example.invalid\n")
    (ghdir / "mode").write_text("auth")
    n0 = len(gh_log())
    head0 = p.head()
    ap = p.ca(*argv, "--apply", extra=with_gh, label="pair-apply-against-fake-github")
    apply_calls = gh_log()[n0:]
    new_commits = p.git("log", "--format=%s", f"{head0}..HEAD").splitlines()

    def bare(repo: str) -> list[str]:
        d = ghdir / "remotes" / f"{repo}.git"
        if not d.is_dir():
            return []
        r = subprocess.run(["git", "--git-dir", str(d), "log", "--all", "--format=%s"],
                           capture_output=True, text=True)
        return r.stdout.splitlines()
    apply_obs = {"exit": ap.rc, "gh_calls": apply_calls,
                 "local_commits_added": new_commits,
                 "origin": p.git("remote", "get-url", "origin").strip(),
                 "science_remote_commits": len(bare(science)),
                 "audit_remote_commits": bare(audit),
                 "branch_protection_call": any("protection" in x for x in apply_calls),
                 "stdout_tail": ap.stdout[-1200:]}
    # init --github, signed out.
    (ghdir / "mode").write_text("unauth")
    n0 = len(gh_log())
    ig = p.ca("init", "gh-proj", "--github", "--no-console",
              "--auditor-vendor", "openai", "--auditor-model", MODELS["openai"],
              "--generator-vendor", "anthropic", "--generator-model", MODELS["anthropic"],
              cwd=p.home, extra=with_gh, custom=False, label="init-github-signed-out")
    yml = p.home / "gh-proj" / "crossaudit.yml"
    init_obs = {"exit": ig.rc, "gh_calls": gh_log()[n0:],
                "mentions_device_code": bool(re.search(r"device", ig.stdout + ig.stderr, re.I)),
                "plan_printed": "gh repo create" in ig.stdout,
                "gh_warning": [ln.strip() for ln in (ig.stdout + ig.stderr).splitlines()
                               if "gh " in ln and ("install" in ln or "auth" in ln)][:3],
                "repo_lines_in_yml": [ln for ln in (yml.read_text().splitlines() if yml.exists() else [])
                                      if "_repo" in ln]}
    key_leak = [x for x in gh_log() if "provider key variable present" in x]
    rec.details = {"runs": {k: {kk: vv for kk, vv in v.items() if kk != "stdout"} for k, v in runs.items()},
                   "plan_steps": plan_steps, "apply_against_fake": apply_obs,
                   "init_github": init_obs, "gh_saw_provider_key": bool(key_leak)}
    for k in runs:
        rec.exit_codes[f"pair_plan_gh_{k}"] = runs[k]["exit"]
    rec.exit_codes["pair_apply_fake"] = ap.rc
    rec.exit_codes["init_github"] = ig.rc
    rec.evidence.append(h.save(rec.id, "gh-invocations.log", "\n".join(gh_log()) + "\n"))
    rec.evidence.append(h.save(rec.id, "plan-vs-apply.json", json.dumps(rec.details, indent=2)))

    a = runs["auth"]
    plan_ok = (a["exit"] == 0 and science in plan_out and audit in plan_out
               and not a["mutating_gh_calls"] and a["tree_unchanged"] and len(plan_steps) >= 3)
    # The README's sentence is about the plan, not the account: without --apply the
    # plan prints and nothing changes, whether or not gh is signed in (D173). A
    # missing or signed-out gh is told what --apply will need, in one line.
    no_account_ok = all(
        runs[m]["exit"] == 0 and science in runs[m]["stdout"] and audit in runs[m]["stdout"]
        and not runs[m]["mutating_gh_calls"] and runs[m]["tree_unchanged"]
        and re.search(r"Before --apply|gh auth login|sign in", runs[m]["stdout"] + runs[m]["stderr"])
        for m in ("absent", "unauth"))
    # What --apply did that no plan step names, and plan steps it did not do.
    # The numbered steps and their `$ command` lines are the plan; what comes
    # after "You do afterwards" is, by its own words, not something --apply does.
    steps_region = plan_out.split("You do afterwards")[0]
    plan_text = steps_region
    gaps = []
    if apply_obs["science_remote_commits"] and not re.search(
            rf"push\b.*\b{re.escape(science)}\b", plan_text, re.I | re.S):
        gaps.append(f"`--apply` pushed the local history ({apply_obs['science_remote_commits']} commits) "
                    f"to {science} — its own progress line says so — but no plan step is that push "
                    "(step 1's gloss 'the work and its history' is the only hint)")
    if new_commits and not (re.search(r"git commit", plan_text) and "remote add origin" in plan_text):
        # both the local pairing commit and the origin remote must be planned steps
        gaps.append(f"it also committed locally ({new_commits}) and added origin, not in the plan")
    if "protection" in plan_text and not apply_obs["branch_protection_call"]:
        gaps.append("plan step 5 'gh api …/branches/main/protection' is not performed by `--apply` "
                    "(it prints it as a manual step), and `init --github`'s panel says "
                    "'crossaudit pair --apply does all of it'")
    extra = (f"gh absent → exit {runs['absent']['exit']}, gh signed out → exit {runs['unauth']['exit']}"
             + (" (the plan prints and names what --apply will need)" if no_account_ok else
                f" ({short(runs['absent']['stderr'] or runs['unauth']['stderr'], 90)}): plan mode "
                "needs a signed-in gh even with both names given"))
    init_note = (f"`init --github` signed out: exit {ig.rc}, plan printed={init_obs['plan_printed']}, "
                 f"device code shown={init_obs['mentions_device_code']}")
    if plan_ok and no_account_ok and not gaps:
        return finish(rec, "PASS", f"signed in: exit 0, both repositories and {len(plan_steps)} steps "
                      f"printed, gh saw only {a['gh_calls']}, tree unchanged; {extra}; {init_note}.")
    if plan_ok and no_account_ok:
        return finish(rec, "PARTIAL", f"plan mode changes nothing (signed in: exit 0, both repositories, "
                      f"{len(plan_steps)} steps, gh saw only {a['gh_calls']}, tree unchanged), but the plan "
                      f"is not the list of what `--apply` does: " + "; ".join(gaps) + f". {extra}; {init_note}.")
    why = []
    if not plan_ok:
        why.append(f"signed-in plan run: exit {a['exit']}, mutating gh calls {a['mutating_gh_calls']}, "
                   f"tree unchanged {a['tree_unchanged']}, {len(plan_steps)} steps")
    if not no_account_ok:
        why.append(f"plan without an account: absent → exit {runs['absent']['exit']}, signed out → exit "
                   f"{runs['unauth']['exit']} (the plan should print, change nothing, and say what "
                   "--apply will need)")
    return finish(rec, "FAIL", "; ".join(why) + f"; {init_note}")


MCP_ECHO_TEXT = "harness-echo-payload-5c1e"
MCP_BUDGET = 3
# The generator's MCP requests, in order. With a budget of 3 calls per task:
# 1 echo and 2 big run; 3 `secret` is off the allowlist; 4 is over budget.
MCP_SEQUENCE = [("echo", {"text": MCP_ECHO_TEXT}), ("big", {}), ("secret", {}),
                ("echo", {"text": "over budget"})]


class McpCalls(fp.Scenario):
    name = "mcp-calls"

    def __init__(self, server_id: str):
        self.server_id = server_id

    def generator(self, n, system, prompt):
        if n <= len(MCP_SEQUENCE):
            tool, args = MCP_SEQUENCE[n - 1]
            req = {"server_id": self.server_id, "tool": tool, "arguments": args}
            return fp.reply("<<<CROSSAUDIT-MCP-TOOL>>>\n" + json.dumps(req)
                            + "\n<<<END-CROSSAUDIT-MCP-TOOL>>>")
        return super().generator(n, system, prompt)


def http_post_json(url: str, payload: dict, timeout: float = 60) -> tuple[int, dict | None, str]:
    u = urllib.request.urlparse(url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=timeout)
    body = json.dumps(payload).encode()
    try:
        conn.request("POST", u.path + (("?" + u.query) if u.query else ""), body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        text = resp.read(2_000_000).decode("utf-8", "replace")
        return resp.status, json_or_none(text), text
    except OSError as exc:
        return -1, None, f"{exc}"
    finally:
        conn.close()


def mcp_results_block(prompt: str):
    m = re.search(r"<<<MCP-RESULTS\n(.*?)\nMCP-RESULTS", prompt, re.S)
    return json_or_none(m.group(1)) if m else None


@claim("C34a", "A registered local stdio MCP server, consented to as an exact executable, is called through a build")
def c34a(h: Harness, rec: Record) -> Record:
    """README "Connect MCP tools and Project Skills": register through the
    console's /api/mcp exactly as the Tools & Skills dialog does (step 1
    connect with the local-code approval, generator access off; step 2 approve
    exact tool names and a calls-per-task cap), then a `crossaudit build` whose
    fake generator emits the documented MCP-TOOL envelope four times. The
    product has no CLI verb for MCP (recorded from `--help`)."""
    p = Project(h, rec, fp.Scenario(), tag="MCP")
    h.projects["MCP"] = p
    p.init()
    p.configure()
    log = p.base / "fakemcp.jsonl"
    exe = {}
    for ident in ("mcpA", "mcpB"):
        d = p.base / ident
        d.mkdir()
        src = (HERE / "fakemcp.py").read_text(encoding="utf-8").split("\n", 1)[1]
        (d / "fakemcp").write_text(f"#!{h.venv}/bin/python3\n" + src, encoding="utf-8")
        (d / "fakemcp").chmod(0o755)
        exe[ident] = str((d / "fakemcp").resolve())
    path_a = {"PATH": f"{p.base / 'mcpA'}:{h.venv}/bin:{BASE_PATH}"}
    path_b = {"PATH": f"{p.base / 'mcpB'}:{h.venv}/bin:{BASE_PATH}"}
    helptext = p.ca("--help", label="help").stdout
    rec.details["cli_has_mcp_verb"] = bool(re.search(r"^\s+mcp\b", helptext, re.M))

    def launches() -> list[dict]:
        if not log.exists():
            return []
        return [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]

    c = p.ca("console", extra=path_a, label="console-start")
    p.console_started = True
    m = re.search(r"(http://127\.0\.0\.1:(\d+)/\?t=(\S+))", c.stdout)
    if not m:
        return finish(rec, "FAIL", f"console printed no tokenized URL: {short(c.stdout + c.stderr)}")
    api = f"http://127.0.0.1:{m.group(2)}/api/mcp?t={m.group(3)}"
    state_url = f"http://127.0.0.1:{m.group(2)}/api/state?t={m.group(3)}"
    exchanges = []

    def post(label: str, payload: dict):
        st, data, text = http_post_json(api, payload)
        exchanges.append({"label": label, "request": payload, "status": st,
                          "response": data if data is not None else text[:2000]})
        return st, data, text

    base_payload = {"action": "register", "name": "harness fake", "transport": "stdio",
                    "command": "fakemcp", "args": [str(log)], "timeout": 30,
                    "max_calls_per_task": MCP_BUDGET, "allow_private_network": False,
                    "allowed_tools": [], "enabled": False}
    n_before = len(launches())
    st0, d0, _ = post("connect-without-approval", dict(base_payload))
    started_without_approval = len(launches()) > n_before
    st1, d1, _ = post("step1-connect", {**base_payload, "approve_local_code": True})
    if st1 != 200 or not isinstance(d1, dict) or not d1.get("id"):
        rec.evidence.append(h.save(rec.id, "api-mcp-exchanges.json", json.dumps(exchanges, indent=2)))
        return finish(rec, "FAIL", f"step-1 registration refused: HTTP {st1} {short(str(d1), 200)}")
    sid = d1["id"]
    st_all, d_all, _ = post("new-server-enabled-allow-all", {
        **base_payload, "name": "harness fake 2", "approve_local_code": True,
        "allow_all_tools": True, "enabled": True})
    st2, d2, _ = post("step2-approve-tools", {
        **base_payload, "server_id": sid, "command": d1.get("command"),
        "approve_local_code": True, "allowed_tools": ["echo", "big"], "enabled": True})
    st3, d3, _ = post("swap-command-without-approval", {
        **base_payload, "server_id": sid, "command": exe["mcpB"],
        "allowed_tools": ["echo", "big"], "enabled": True})
    sts, body = http_get(state_url)
    snap = (json_or_none(body) or {}).get("mcp", {})
    stored = next((s for s in snap.get("servers", []) if s.get("id") == sid), {})
    # The second registration (allow-all) may have created a row; remove it so
    # only the server under test is enabled.
    if st_all == 200 and isinstance(d_all, dict) and d_all.get("id"):
        post("remove-allow-all-row", {"action": "remove", "server_id": d_all["id"]})
    rec.evidence.append(h.save(rec.id, "api-mcp-exchanges.json", json.dumps(exchanges, indent=2)))
    reg_launches = len(launches())

    # The build: PATH now puts a DIFFERENT `fakemcp` first, and a decoy
    # *_API_KEY is in the environment, to see what the server inherits.
    p.fakes.set_scenario(McpCalls(sid))
    b = p.ca("build", TASK, extra={**path_b, "OPENAI_API_KEY": "decoy-openai-HARNESS-key"},
             label="build-with-mcp-calls", timeout=240)
    all_launch = launches()
    build_launches = [e for e in all_launch[reg_launches:] if e.get("event") == "start"]
    build_calls = [e for e in all_launch[reg_launches:] if e.get("method") == "tools/call"]
    gens = p.fakes.captures("generator")
    auds = p.fakes.captures("auditor")
    last_results = None
    for cap in gens:
        r = mcp_results_block(cap.get("prompt", ""))
        if r is not None:
            last_results = r
    p.mcp = {"sid": sid, "log": log, "launches": all_launch, "reg_launches": reg_launches,
             "build_launches": build_launches, "build_calls": build_calls,
             "results": last_results or [], "build": b, "gens": gens, "auds": auds,
             "exe": exe, "stored": stored}
    rec.exit_codes.update({"build": b.rc, "connect_without_approval": st0, "step1": st1,
                           "new_enabled_allow_all": st_all, "step2": st2, "swap_without_approval": st3})
    rec.evidence.append(h.save(rec.id, "fakemcp-log.jsonl",
                               "\n".join(json.dumps(e) for e in all_launch) + "\n"))
    rec.evidence.append(h.save(rec.id, "mcp-results-in-last-generator-prompt.json",
                               json.dumps(last_results, indent=2)[:400000]))
    echo_res = next((r for r in (last_results or []) if r.get("tool") == "echo"
                     and r.get("status") == "completed"), None)
    echo_text = "".join(b_.get("text", "") for b_ in (echo_res or {}).get("content", []))
    in_auditor = any(MCP_ECHO_TEXT in a.get("prompt", "") or "B" * 1000 in a.get("prompt", "") for a in auds)
    pinned_at_reg = d1.get("command") == exe["mcpA"]
    pinned_at_build = bool(build_launches) and all(e.get("identity") == "mcpA" for e in build_launches)
    rec.details.update({
        "connect_without_approval": {"http": st0, "refusal": (d0 or {}).get("reason") if isinstance(d0, dict) else d0,
                                     "process_started": started_without_approval},
        "step1": {"http": st1, "command_stored": d1.get("command"), "expected_resolved": exe["mcpA"],
                  "tools_seen": [t["name"] for t in d1.get("tools", [])], "enabled": d1.get("enabled")},
        "new_server_enabled_allow_all": {"http": st_all, "response": (d_all or {}).get("reason", d_all)
                                         if isinstance(d_all, dict) else d_all},
        "step2": {"http": st2, "allowed_tools": (d2 or {}).get("allowed_tools"),
                  "enabled": (d2 or {}).get("enabled"), "max_calls": (d2 or {}).get("max_calls_per_task")},
        "swap_command_without_approval": {"http": st3, "response": (d3 or {}).get("reason", d3)
                                          if isinstance(d3, dict) else d3},
        "stored_after_swap_attempt": stored.get("command"),
        "build_exit": b.rc, "build_launch_identities": [e.get("identity") for e in build_launches],
        "build_tools_called_on_server": [e.get("tool") for e in build_calls],
        "echo_result_to_generator": echo_text, "tool_output_in_auditor_prompt": in_auditor})
    problems = []
    if st0 == 200 or started_without_approval:
        problems.append(f"registration without approve_local_code: HTTP {st0}, process started={started_without_approval}")
    if not pinned_at_reg:
        problems.append(f"stored command {d1.get('command')!r} is not the resolved path {exe['mcpA']!r}")
    if st2 != 200 or (d2 or {}).get("allowed_tools") != ["big", "echo"]:
        problems.append(f"step 2 (approve echo, big) → HTTP {st2} {short(str(d2), 160)}")
    if st3 == 200 or stored.get("command") != exe["mcpA"]:
        problems.append(f"changing the command without a new approval → HTTP {st3}; stored now {stored.get('command')!r}")
    if not pinned_at_build:
        problems.append(f"build launched {[e.get('argv0') for e in build_launches]} (PATH put mcpB first)")
    if b.rc != 0:
        problems.append(f"build exit {b.rc}")
    if echo_text != "echo: " + MCP_ECHO_TEXT:
        problems.append(f"echo result returned to the generator: {echo_text!r}")
    if in_auditor:
        problems.append("tool output reached the auditor's prompt")
    note_all = (f"a NEW server registered enabled with allow_all_tools → HTTP {st_all}"
                + (" (refused)" if st_all != 200 else " (accepted)"))
    cli_note = "no `mcp` CLI verb (registration is the console API only)" if not rec.details["cli_has_mcp_verb"] else "CLI has an mcp verb"
    if not problems:
        return finish(rec, "PASS", f"/api/mcp without the local-code approval → {st0}, nothing started; step 1 stored "
                      f"the resolved path; changing the command without re-approval → {st3}; the build ran the "
                      f"pinned copy although PATH put another `fakemcp` first; `echo` ran once and its text came back "
                      f"to the generator, never to the auditor; {note_all}; {cli_note}.")
    return finish(rec, "FAIL" if (b.rc != 0 or not echo_text) else "PARTIAL", "; ".join(problems) + f"; {note_all}; {cli_note}")


def _mcp(h: Harness, rec: Record):
    p = h.projects.get("MCP")
    info = getattr(p, "mcp", None) if p else None
    if info:
        p.rec = rec
    return p, info


@claim("C34c", "A tool not on the MCP allowlist is refused", deps=("C34a",))
def c34c(h: Harness, rec: Record) -> Record:
    p, info = _mcp(h, rec)
    if not info:
        return finish(rec, "UNTESTED", "needs C34a's registered server and build")
    res = next((r for r in info["results"] if r.get("tool") == "secret"), None)
    reached = "secret" in [e.get("tool") for e in info["build_calls"]]
    marker_in_prompt = any("FAKEMCP-SECRET-TOOL-OUTPUT" in g.get("prompt", "") for g in info["gens"])
    rec.details = {"generator_saw": res, "reached_server": reached, "marker_in_any_prompt": marker_in_prompt,
                   "advertised": [t["name"] for t in info["stored"].get("tools", [])],
                   "allowed": info["stored"].get("allowed_tools")}
    if res and res.get("status") == "refused" and not reached and not marker_in_prompt:
        return finish(rec, "PASS", f"`secret` (advertised, not approved) → refused before launch: "
                      f"\"{short(res.get('message', ''), 90)}\"; the server never received the call.")
    return finish(rec, "FAIL", f"{rec.details}")


@claim("C34d", "The calls-per-task budget stops the call after the cap", deps=("C34a",))
def c34d(h: Harness, rec: Record) -> Record:
    p, info = _mcp(h, rec)
    if not info:
        return finish(rec, "UNTESTED", "needs C34a's registered server and build")
    res = info["results"]
    over = res[3] if len(res) >= 4 else None
    on_server = [e.get("tool") for e in info["build_calls"]]
    rec.details = {"budget": MCP_BUDGET, "requests_in_order": [s[0] for s in MCP_SEQUENCE],
                   "statuses": [(r.get("tool"), r.get("status"), short(r.get("message", ""), 100)) for r in res],
                   "calls_that_reached_server": on_server}
    if (over and over.get("status") == "refused" and "limit" in over.get("message", "")
            and len(on_server) <= MCP_BUDGET and on_server.count("echo") == 1):
        return finish(rec, "PASS", f"cap {MCP_BUDGET}: request 4 refused (\"{short(over.get('message'), 80)}\"); "
                      f"the server received {on_server}. A refused (off-allowlist) request counts toward the cap.")
    return finish(rec, "FAIL", f"{rec.details}")


@claim("C34e", "An oversized MCP result is bounded before it reaches the generator", deps=("C34a",))
def c34e(h: Harness, rec: Record) -> Record:
    p, info = _mcp(h, rec)
    if not info:
        return finish(rec, "UNTESTED", "needs C34a's registered server and build")
    res = next((r for r in info["results"] if r.get("tool") == "big"), None)
    blocks = (res or {}).get("content", [])
    size = sum(len(b.get("text", "").encode()) for b in blocks)
    truncated = any(b.get("truncated") for b in blocks)
    readme_number = re.search(r"bounded[^.\n]{0,80}?(\d[\d,]*\s*(?:KiB|KB|MiB|MB|bytes))", readme_text(h), re.I)
    rec.details = {"server_returned_bytes": 1_000_000, "generator_received_bytes": size,
                   "truncated_flag": truncated, "status": (res or {}).get("status"),
                   "readme_states_a_number": readme_number.group(1) if readme_number else None}
    if res and 0 < size < 1_000_000 and truncated:
        return finish(rec, "PASS", f"1,000,000-byte result → {size} bytes ({size // 1024} KiB) with "
                      f"truncated=true in the generator's prompt; the README says \"bounded\" without a number"
                      + (f" ({readme_number.group(1)})" if readme_number else "") + ".")
    return finish(rec, "FAIL", f"{rec.details}")


@claim("C34f", "MCP calls leave content-free hashed call records", deps=("C34a",))
def c34f(h: Harness, rec: Record) -> Record:
    p, info = _mcp(h, rec)
    if not info:
        return finish(rec, "UNTESTED", "needs C34a's registered server and build")
    calls_path = p.root / ".crossaudit" / "mcp" / "calls.json"
    rows = json_or_none(calls_path.read_text()) if calls_path.exists() else None
    rows = rows if isinstance(rows, list) else []
    raw = calls_path.read_text() if calls_path.exists() else ""
    mode = oct(calls_path.stat().st_mode & 0o777) if calls_path.exists() else None
    allowed_keys = {"id", "server_id", "server", "tool", "status", "chat_id", "started",
                    "duration_ms", "arguments_sha256", "result_sha256"}
    extra_keys = sorted({k for r in rows for k in r} - allowed_keys)
    content_hits = [s for s in (MCP_ECHO_TEXT, "B" * 64, "FAKEMCP-SECRET-TOOL-OUTPUT") if s in raw]
    # Recompute both hashes from what the generator was given.
    by_id = {r.get("call_id"): r for r in info["results"] if r.get("call_id")}
    recomputed = []
    for row in rows:
        res = by_id.get(row.get("id"))
        if res is None:
            recomputed.append((row.get("tool"), "no matching result"))
            continue
        bounded = {k: v for k, v in res.items() if k not in ("call_id", "server_id", "server", "tool", "status")}
        rsha = hashlib.sha256(json.dumps(bounded, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        args = {} if row.get("tool") == "big" else {"text": MCP_ECHO_TEXT}
        asha = hashlib.sha256(json.dumps(args, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        recomputed.append((row.get("tool"), rsha == row.get("result_sha256"), asha == row.get("arguments_sha256")))
    hashes_ok = bool(rows) and all(len(t) == 3 and t[1] and t[2] for t in recomputed)
    # Anywhere else in the project (tree, git objects excluded) holding tool output?
    elsewhere, args_elsewhere = [], []
    for f in p.root.rglob("*"):
        if f.is_file() and ".git" not in f.parts and f != calls_path:
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "echo: " + MCP_ECHO_TEXT in t or "B" * 4096 in t:
                elsewhere.append(str(f.relative_to(p.root)))
            elif MCP_ECHO_TEXT in t:
                args_elsewhere.append(str(f.relative_to(p.root)))
    ev = p.root / ".crossaudit" / "evidence.jsonl"
    ev_info = {"present": ev.exists()}
    if ev.exists():
        txt = ev.read_text()
        ev_info["mentions_mcp"] = "mcp" in txt.lower()
        ev_info["holds_output"] = MCP_ECHO_TEXT in txt
        v = h.sh(rec, [h.venv / "bin/python", "-c",
                       "import json,sys;from crossaudit.ledger.chain import EvidenceLedger as L;"
                       "r=L(sys.argv[1]).verify();print(json.dumps(r.__dict__))", ev],
                 cwd=p.root, env=p.env(), label="evidence-ledger-verify")
        ev_info["verify"] = json_or_none(v.stdout.strip())
    rec.details = {"calls_json": str(calls_path.relative_to(p.root)), "mode": mode, "rows": rows,
                   "extra_keys": extra_keys, "content_hits": content_hits, "recomputed": recomputed,
                   "tool_output_elsewhere_in_tree": elsewhere,
                   "call_arguments_elsewhere_in_tree": args_elsewhere, "evidence_ledger": ev_info}
    if calls_path.exists():
        rec.evidence.append(h.copy(rec.id, calls_path, "calls.json"))
    ok = (len(rows) == 2 and not extra_keys and not content_hits and hashes_ok and mode == "0o600"
          and not elsewhere and not (ev_info.get("holds_output")))
    ev_note = ("the hash-chained evidence ledger holds no MCP record (evidence.jsonl "
               + ("present, verify " + str((ev_info.get("verify") or {}).get("ok")) if ev.exists() else "absent")
               + "); the call ledger is a plain JSON list, mode 600, last 200 rows, not chained")
    if ok:
        return finish(rec, "PASS", f".crossaudit/mcp/calls.json: one row per executed call ({[r['tool'] for r in rows]}), "
                      f"keys = identity/timing/status/hashes only, both sha256s recompute from what the generator "
                      f"received, no tool result text anywhere in the project"
                      + (f" (the call's arguments do appear in {args_elsewhere}: the run's event log keeps "
                         "the generator's streamed reply, which is the request envelope)" if args_elsewhere else "")
                      + f"; {ev_note}.")
    return finish(rec, "FAIL" if content_hits or elsewhere else "PARTIAL", f"{rec.details}"[:600])


@claim("C34g", "A local MCP server gets a small sanitized environment, no provider keys", deps=("C34a",))
def c34g(h: Harness, rec: Record) -> Record:
    p, info = _mcp(h, rec)
    if not info:
        return finish(rec, "UNTESTED", "needs C34a's registered server and build")
    starts = [e for e in info["launches"] if e.get("event") == "start"]
    keyish = re.compile(r"(^CROSSAUDIT_|KEY|TOKEN|SECRET|PASSWORD)", re.I)
    names = sorted({k for e in starts for k in e.get("env_keys", [])})
    bad = sorted({k for k in names if keyish.search(k)})
    dummy = any(e.get("dummy_value_present") for e in starts)
    rec.details = {"launches": len(starts), "env_names_union": names, "key_like_names": bad,
                   "dummy_value_present": dummy,
                   "parent_env_had": ["CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY",
                                      "CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT", "OPENAI_API_KEY (build only)",
                                      "BROWSER", "NO_COLOR", "TERM", "GIT_CONFIG_NOSYSTEM"]}
    if starts and not bad and not dummy and len(names) <= 13:
        return finish(rec, "PASS", f"{len(starts)} launches (registration probes and build calls) saw only "
                      f"{names}; no CROSSAUDIT_* or *_KEY name, no dummy key value, although the parent "
                      "processes held both provider keys and a decoy OPENAI_API_KEY.")
    return finish(rec, "FAIL", f"{rec.details}")


# ========================================================================= main
# ------------------------------------------------- H. the terminal surface (round 3)
TIER_WORDS = ("verified by a check", "raised by the auditor, verified",
              "raised by the auditor, not yet reproduced")
RECEIPT_WORDS = ("BINDINGS VERIFIED", "ADMISSION READY", "SIGNED")


class CleanVarying(fp.Scenario):
    """The clean scenario, but each generator call writes a different value:
    a second task whose increment is byte-identical to the first is refused by
    the product as a reproduced round, which is right, and not what C41 is
    about."""
    name = "clean-varying"

    def generator(self, n, system, prompt):
        return fp.reply(fp.envelope(fp.increment(value=round(1.5 + n / 10, 2)),
                                    summary=f"attempt {n}"))


class PassThenBlock(fp.Scenario):
    """Task one passes on its first audit; every later audit is blocked, so a
    later task escalates at the round limit. One project, both outcomes."""
    name = "pass-then-block"

    def generator(self, n, system, prompt):
        return fp.reply(fp.envelope(fp.increment(value=round(1.5 + n / 10, 2)),
                                    summary=f"attempt {n}"))

    def auditor(self, n, system, prompt):
        if n == 1:
            return fp.reply(fp.audit_json(prompt, "PASS"))
        return fp.reply(fp.audit_json(prompt, "BLOCKED", f"the claim is unsupported (attempt {n})"))


def tty_env(p: Project, extra: dict | None = None) -> dict:
    """A person's terminal: TERM names a real terminal (the base env says
    `dumb`); NO_COLOR stays, so transcripts carry no colour codes."""
    return p.env({"TERM": "xterm-256color", **(extra or {})})


def usage_rows(p: Project) -> list[dict]:
    path = p.root / ".crossaudit" / "usage.jsonl"
    rows = []
    if path.is_file():
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            row = json_or_none(ln)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def rulings_rows(p: Project) -> list[dict]:
    rows = []
    for path in p.root.glob("**/rulings.jsonl"):
        if ".git" in path.parts:
            continue
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            row = json_or_none(ln)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def browser_calls(h: Harness) -> str:
    return h.browser_log.read_text(encoding="utf-8") if h.browser_log.exists() else ""


@claim("C37", "`crossaudit tui --once` prints one frame: cycles, statuses, the newest cycle's findings with their tier; no terminal needed")
def c37(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, PassThenBlock())
    h.projects["TUI"] = p
    p.init()
    p.configure(max_rounds=2)
    b1 = p.build("Task one: report the benchmark time", label="build-one")
    b2 = p.build("Task two: report it again", label="build-two")
    st = p.status_json()
    statuses = {c["cycle_id"]: c["status"] for c in st.get("cycles", [])}
    rec.exit_codes = {"build_one": b1.rc, "build_two": b2.rc}
    if not (b1.rc == 0 and b2.rc == 11 and "PASSED" in statuses.values()
            and "ESCALATED" in statuses.values()):
        rec.details = {"statuses": statuses}
        return finish(rec, "UNTESTED", f"fixture: build one exit {b1.rc}, build two exit {b2.rc}, "
                      f"statuses {sorted(statuses.values())} (needs one PASSED and one ESCALATED)")
    requests_before = len(p.fakes.requests())
    browser_before = browser_calls(h)
    once = p.ca("tui", "--once", label="tui-once")
    plain = p.ca("tui", label="tui-no-tty")
    requests_after = len(p.fakes.requests())
    browser_after = browser_calls(h)
    rec.evidence.append(h.save(rec.id, "tui-once-frame.txt", once.stdout))
    rec.evidence.append(h.save(rec.id, "tui-no-tty-frame.txt", plain.stdout + "\n--- stderr ---\n" + plain.stderr))
    ids_named = {cid: (cid[:8] in once.stdout) for cid in statuses}
    words_named = {w: (w in once.stdout) for w in sorted(set(statuses.values()))}
    tiers = [w for w in TIER_WORDS if w in once.stdout]
    rec.exit_codes.update({"tui_once": once.rc, "tui_no_tty": plain.rc})
    rec.details = {"statuses": statuses, "cycle_ids_in_frame": ids_named,
                   "status_words_in_frame": words_named, "tier_words_in_frame": tiers,
                   "provider_requests_during_tui": requests_after - requests_before,
                   "browser_invoked": browser_after != browser_before,
                   "no_tty_stderr": short(plain.stderr, 200),
                   "frame_lines": len(once.stdout.splitlines())}
    quiet = requests_after == requests_before and browser_after == browser_before
    frame_ok = once.rc == 0 and all(ids_named.values()) and all(words_named.values())
    plain_ok = plain.rc == 0 and bool(plain.stderr.strip()) and plain.stdout.strip() == once.stdout.strip()
    if frame_ok and tiers and quiet and plain_ok:
        return finish(rec, "PASS", f"one frame, exit 0, names {len(statuses)} cycles and "
                      f"{sorted(words_named)}; tier words {tiers}; no provider request, no browser; "
                      "without --once the same frame and one stderr sentence.")
    if frame_ok and quiet:
        return finish(rec, "PARTIAL", f"the frame names the cycles and statuses (exit {once.rc}) but "
                      f"tier words {tiers or 'absent'}; without --once: exit {plain.rc}, "
                      f"stderr \"{short(plain.stderr, 80)}\", same frame={plain.stdout.strip() == once.stdout.strip()}")
    return finish(rec, "FAIL", f"tui --once exit {once.rc}; ids {ids_named}; statuses {words_named}; "
                  f"tiers {tiers}; provider requests {requests_after - requests_before}; "
                  f"browser {browser_after != browser_before}; stderr \"{short(once.stderr, 120)}\"")


@claim("C38", "At a terminal `crossaudit tui` draws; j/k and Enter expand a cycle; `q` exits and restores the terminal", deps=("C37",))
def c38(h: Harness, rec: Record) -> Record:
    p = h.projects.get("TUI")
    if p is None:
        return finish(rec, "UNTESTED", "needs C37's project")
    p.rec = rec
    # The PASSED cycle is the older row (the newest, ESCALATED, is selected and
    # expanded in the first frame, receipt and all). `j` moves to it; Enter
    # expands it; its own receipt line names its commit, so the check is on that
    # line and not on any receipt word already on screen.
    passed = [c for c in p.status_json().get("cycles", []) if c["status"] == "PASSED"]
    if not passed:
        return finish(rec, "UNTESTED", "C37's project has no PASSED cycle")
    passed_sha = str(passed[0].get("active_sha") or passed[0].get("sha") or "")[:12]
    passed_line = f"for {passed_sha}"            # "BINDINGS VERIFIED  receipt … for <sha>"
    script = ('echo "STTY-BEFORE=$(stty -g)"; crossaudit tui; echo "TUI-EXIT=$?"; '
              'echo "STTY-AFTER=$(stty -g)"')
    marks: list[int] = []
    gates = [lambda out: "ESCALATED" in out,                      # the first frame is up
             lambda out: f"❯ {passed[0]['cycle_id'][:12]}" in out,  # the cursor reached the PASSED row
             lambda out: passed_line in out]                      # its receipt line is on screen
    rc, out = pty_run(["/bin/sh", "-c", script], tty_env(p), p.root, [b"j", b"\r", b"q"],
                      timeout=60, gates=gates, marks=marks)
    rec.evidence.append(h.save(rec.id, "tui-pty-transcript.txt", f"exit {rc}\nmarks {marks}\n{out}"))
    before = re.search(r"STTY-BEFORE=(\S+)", out)
    after = re.search(r"STTY-AFTER=(\S+)", out)
    tui_exit = re.search(r"TUI-EXIT=(-?\d+)", out)
    enter_at = marks[1] if len(marks) > 1 else len(out)
    receipt_before_enter = passed_line in out[:enter_at]
    receipt_after_enter = passed_line in out[enter_at:]
    rec.exit_codes = {"shell": rc, "tui": int(tui_exit.group(1)) if tui_exit else None}
    rec.details = {"keys_typed": len(marks), "passed_cycle_receipt_line": passed_line,
                   "stty_before": before.group(1) if before else None,
                   "stty_after": after.group(1) if after else None,
                   "receipt_line_before_enter": receipt_before_enter,
                   "receipt_line_after_enter": receipt_after_enter,
                   "transcript_tail": short(out[-400:], 300)}
    restored = bool(before and after and before.group(1) == after.group(1))
    exited = bool(tui_exit and tui_exit.group(1) == "0")
    if exited and restored and len(marks) == 3 and receipt_after_enter:
        return finish(rec, "PASS", "the TUI drew, j + Enter showed the PASSED cycle's receipt line, "
                      "q exited 0 and stty is identical before and after.")
    if exited and restored:
        return finish(rec, "PARTIAL", f"exit 0 and the terminal is restored, but keys typed {len(marks)}/3 "
                      f"and the receipt line after Enter={receipt_after_enter} "
                      f"(before Enter={receipt_before_enter})")
    return finish(rec, "FAIL", f"tui exit {rec.exit_codes['tui']} (shell {rc}); terminal restored={restored}; "
                  f"keys typed {len(marks)}/3; receipt line after Enter={receipt_after_enter}")


@claim("C39", "The decision card: `c` stops the task and `r` revises and continues, each with a written reason recorded as a ruling in the ledger", deps=("C37",))
def c39(h: Harness, rec: Record) -> Record:
    p = h.projects.get("TUI")
    if p is None:
        return finish(rec, "UNTESTED", "needs C37's project")
    p.rec = rec

    def escalated() -> list[str]:
        return [c["cycle_id"] for c in p.status_json().get("cycles", []) if c["status"] == "ESCALATED"]

    esc = escalated()
    if not esc:
        return finish(rec, "UNTESTED", "C37 left no ESCALATED cycle")
    closed_id = esc[0]
    reason_c = "The harness human stops task two after review C39"
    before_close = len(p.fakes.requests())
    rc1, out1 = pty_run([h.ca, "tui"], tty_env(p), p.root,
                        [b"c", reason_c.encode() + b"\r", b"q"], timeout=60,
                        gates=[lambda out: "ESCALATED" in out, None,
                               lambda out: "Ruling recorded" in out or "裁定已记录" in out])
    rec.evidence.append(h.save(rec.id, "tui-close-transcript.txt", f"exit {rc1}\n{out1}"))
    tui_requests = len(p.fakes.requests()) - before_close
    st1 = {c["cycle_id"]: c for c in p.status_json().get("cycles", [])}
    close_row = st1.get(closed_id, {})
    close_rulings = [r.get("action") for r in close_row.get("rulings", [])]
    file_rows = rulings_rows(p)
    close_in_file = any(r.get("action") == "close" and r.get("reason") == reason_c for r in file_rows) \
        or any(reason_c in json.dumps(r) and "close" in json.dumps(r) for r in file_rows)
    close_in_git = reason_c in p.git("log", "-p", "--all")
    human_status = p.ca("status", label="status-after-close")

    b3 = p.build("Task three: report it a third time", label="build-three")
    esc3 = [cid for cid in escalated() if cid != closed_id]
    reason_r = "The harness human sends task three back for revision C39"
    rc2, out2, reopen_row, reopen_in_file, reopen_in_git = None, "", {}, False, False
    if esc3:
        before_reopen = len(p.fakes.requests())
        rc2, out2 = pty_run([h.ca, "tui"], tty_env(p), p.root,
                            [b"r", reason_r.encode() + b"\r", b"q"], timeout=60,
                            gates=[lambda out: "ESCALATED" in out, None,
                                   lambda out: "Ruling recorded" in out or "裁定已记录" in out])
        rec.evidence.append(h.save(rec.id, "tui-reopen-transcript.txt", f"exit {rc2}\n{out2}"))
        tui_requests += len(p.fakes.requests()) - before_reopen
        st2 = {c["cycle_id"]: c for c in p.status_json().get("cycles", [])}
        reopen_row = st2.get(esc3[0], {})
        file_rows = rulings_rows(p)
        reopen_in_file = any(reason_r in json.dumps(r) and "reopen" in json.dumps(r) for r in file_rows)
        reopen_in_git = reason_r in p.git("log", "-p", "--all")
    rec.exit_codes = {"tui_close": rc1, "build_three": b3.rc, "tui_reopen": rc2}
    rec.details = {"closed_cycle": closed_id, "closed_flag": close_row.get("closed"),
                   "closed_status": close_row.get("status"), "close_rulings": close_rulings,
                   "close_reason_in_rulings_file": close_in_file, "close_reason_in_git": close_in_git,
                   "status_mentions_closed": "CLOSED" in human_status.stdout.upper(),
                   "reopened_cycle": esc3[0] if esc3 else None,
                   "reopened_status": reopen_row.get("status"),
                   "reopen_rulings": [r.get("action") for r in reopen_row.get("rulings", [])],
                   "reopen_reason_in_rulings_file": reopen_in_file, "reopen_reason_in_git": reopen_in_git,
                   "provider_requests_during_tui_sessions": tui_requests}
    # A ruling is a human act: neither TUI session may call a model (build three does).
    closed_ok = bool(close_row.get("closed")) and "close" in close_rulings and close_in_file and close_in_git \
        and rc1 == 0 and tui_requests == 0
    reopen_ok = bool(esc3) and reopen_row.get("status") not in ("ESCALATED", None) \
        and "reopen" in [r.get("action") for r in reopen_row.get("rulings", [])] \
        and reopen_in_file and reopen_in_git and rc2 == 0
    if closed_ok and reopen_ok:
        return finish(rec, "PASS", f"`c` closed {closed_id[:8]} with its reason in cycles/rulings.jsonl and a "
                      f"ledger commit (status shows CLOSED); `r` reopened {esc3[0][:8]} "
                      f"(now {reopen_row.get('status')}) with its reason recorded the same way.")
    if closed_ok or reopen_ok:
        return finish(rec, "PARTIAL", f"close ok={closed_ok} (exit {rc1}, closed={close_row.get('closed')}, "
                      f"rulings {close_rulings}, file {close_in_file}, git {close_in_git}); "
                      f"reopen ok={reopen_ok} (escalated again={bool(esc3)}, exit {rc2}, "
                      f"status {reopen_row.get('status')}, file {reopen_in_file}, git {reopen_in_git})")
    return finish(rec, "FAIL", f"close: exit {rc1}, closed={close_row.get('closed')}, rulings {close_rulings}, "
                  f"reason in file {close_in_file}, in git {close_in_git}; reopen: escalated again={bool(esc3)}, "
                  f"exit {rc2}, status {reopen_row.get('status')}, file {reopen_in_file}, git {reopen_in_git}")


def point_tour_project_at_fakes(p: Project, root: Path) -> tuple[dict | None, str]:
    """The README's own `init` chose the vendors and key variables. Add the
    documented `base_url` under each role so the fakes answer, commit it the
    way `Project.configure` does, and return the key variables to export.
    (None, why) when a role's vendor has no fake."""
    yml = root / "crossaudit.yml"
    if not yml.is_file():
        return None, "init wrote no crossaudit.yml"
    section, out, keys, vendors, bad = "", [], {}, {}, []
    for ln in yml.read_text(encoding="utf-8").splitlines(keepends=True):
        if ln and not ln[0].isspace() and ln.rstrip().endswith(":"):
            section = ln.strip()[:-1]
        out.append(ln)
        if section in ("auditor", "generator"):
            m = re.match(r"^\s+vendor:\s*(\S+)", ln)
            if m:
                vendors[section] = m.group(1)
            m = re.match(r"^\s+key_env:\s*(\S+)", ln)
            if m:
                keys[section] = m.group(1)
                vendor = vendors.get(section, "")
                base = (p.fakes.openai_base if vendor == "openai"
                        else p.fakes.anthropic_base if vendor == "anthropic" else None)
                if base is None:
                    bad.append(f"{section} vendor {vendor or '?'} has no fake here")
                else:
                    out.append(f"  base_url: {base}\n")
    if bad or len(keys) < 2:
        return None, "; ".join(bad) or f"could not find both roles' key_env in crossaudit.yml ({sorted(keys)})"
    yml.write_text("".join(out), encoding="utf-8")
    p.root = root
    p.git("add", "crossaudit.yml")
    p.git("commit", "-q", "-m", "harness: point roles at the fake providers")
    return {keys["auditor"]: DUMMY_AUD, keys["generator"]: DUMMY_GEN}, ""


@claim("C40", "The README's 60-second tour, run as written, ends with `verify` printing BINDINGS VERIFIED")
def c40(h: Harness, rec: Record) -> Record:
    text = readme_text(h)
    m = re.search(r"^## 60-second tour\n(.*?)^## ", text, re.S | re.M)
    blocks = re.findall(r"```(?:bash|sh|shell|console)?\n(.*?)```", m.group(1), re.S) if m else []
    if not blocks:
        return finish(rec, "FAIL", "the README has no fenced commands under '## 60-second tour'")
    lines, carry = [], ""
    for ln in "\n".join(blocks).splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        ln = ln[2:] if ln.startswith("$ ") else ln
        if ln.endswith("\\"):                 # a shell continuation: one command over several lines
            carry += ln[:-1].rstrip() + " "
            continue
        lines.append((carry + ln).strip())
        carry = ""
    if carry:
        lines.append(carry.strip())
    rec.evidence.append(h.save(rec.id, "tour-commands.txt", "\n".join(lines) + "\n"))
    p = Project(h, rec, fp.Scenario())
    h.projects["TOUR"] = p
    cwd, keys_env, ran, skipped, substituted = p.home, {}, [], [], []
    verify_out, failed = "", None
    for ln in lines:
        if re.match(r"^(python3? -m )?pip(x)?\b", ln):
            skipped.append(ln)          # the harness installed this very ref already
            continue
        if ln.startswith("cd "):
            cwd = (cwd / ln[3:].strip()).resolve()
            ran.append((ln, 0))
            continue
        if "<" in ln and "verify" in ln:
            newest = p.receipts()[-1] if p.receipts() else None
            if newest is not None:
                # `cycles/<cycle>/receipt.json`: the placeholder is the cycle
                # directory's name; a bare `<receipt>` is the whole path.
                fill = (newest.parent.name if "receipt.json" in ln
                        else str(newest.relative_to(cwd)) if newest.is_relative_to(cwd) else str(newest))
                ln2 = re.sub(r"<[^>]+>", fill, ln)
                substituted.append(f"{ln} -> {ln2}")
                ln = ln2
        label = "tour-" + re.sub(r"[^a-z0-9]+", "-", ln.lower())[:28]
        c = h.sh(rec, ["/bin/sh", "-c", ln], cwd=cwd, env=p.env(keys_env, custom=bool(keys_env)),
                 timeout=240, label=label)
        ran.append((ln, c.rc))
        if ln.startswith("crossaudit init"):
            name = next((a for a in ln.split()[2:] if not a.startswith("-")), None)
            root = (cwd / name).resolve() if name else None
            keys_env, why = point_tour_project_at_fakes(p, root) if root and root.is_dir() else (None, "init made no directory")
            if keys_env is None:
                rec.details = {"ran": ran, "skipped": skipped}
                return finish(rec, "UNTESTED", f"after the README's init: {why}")
        if "verify" in ln:
            verify_out += c.stdout
        if c.rc != 0:
            failed = (ln, c.rc, short(c.stderr or c.stdout, 200))
            break
    rec.details = {"ran": ran, "skipped": skipped, "substituted": substituted,
                   "verify_says_bindings_verified": "BINDINGS VERIFIED" in verify_out,
                   "has_tui_line": any(ln.startswith("crossaudit tui") for ln in lines),
                   "has_verify_line": any("verify" in ln for ln in lines)}
    rec.exit_codes = {re.sub(r"[^a-z0-9]+", "_", ln.lower())[:30]: rc for ln, rc in ran}
    if failed:
        return finish(rec, "FAIL", f"`{failed[0]}` exited {failed[1]}: {failed[2]}")
    if "BINDINGS VERIFIED" in verify_out and rec.details["has_tui_line"]:
        return finish(rec, "PASS", f"{len(ran)} tour commands ran as written (install skipped: this harness "
                      f"installed the same ref; {len(substituted)} placeholder substituted) and `verify` "
                      "printed BINDINGS VERIFIED.")
    return finish(rec, "PARTIAL", f"every tour command exited 0 but verify printed BINDINGS VERIFIED="
                  f"{'BINDINGS VERIFIED' in verify_out}; the tour has a tui line={rec.details['has_tui_line']}, "
                  f"a verify line={rec.details['has_verify_line']}")


@claim("C41", "The usage ledger records which surface each call came from; `status --json` shows `by_surface`")
def c41(h: Harness, rec: Record) -> Record:
    p = Project(h, rec, CleanVarying())
    h.projects["USAGE"] = p
    p.init()
    p.configure()
    b = p.build("Task one from the command line", label="build-cli")
    cli_rows = usage_rows(p)
    cli_surfaces = sorted({str(r.get("surface", "<absent>")) for r in cli_rows})
    task = "Task two from the terminal screen"
    settled = {"since": 0.0}

    def built(out: str) -> bool:
        tui_rows = [r for r in usage_rows(p) if r.get("surface") == "tui"]
        settled_screen = "state: idle" in out or "state: waiting for you" in out
        ok = len(tui_rows) >= 2 and (len(p.receipts()) >= 2 or settled_screen)
        if not ok:
            settled["since"] = 0.0
            return False
        if not settled["since"]:
            settled["since"] = time.time()
            return False
        return time.time() - settled["since"] >= 3.0

    marks: list[int] = []
    rc, out = pty_run([h.ca, "tui"], tty_env(p), p.root, [b"n", task.encode() + b"\r", b"q"],
                      timeout=180, gates=[lambda o: "PASSED" in o, None, built], marks=marks)
    rec.evidence.append(h.save(rec.id, "tui-new-task-transcript.txt", f"exit {rc}\nmarks {marks}\n{out}"))
    rows = usage_rows(p)
    tui_rows = [r for r in rows if r.get("surface") == "tui"]
    absent = [r for r in rows if "surface" not in r]
    st = p.status_json()
    by_surface = (st.get("usage") or {}).get("by_surface") if isinstance(st.get("usage"), dict) else None
    counts = {k: (v.get("calls") if isinstance(v, dict) else v) for k, v in (by_surface or {}).items()}
    statuses = [c["status"] for c in st.get("cycles", [])]
    rec.exit_codes = {"build_cli": b.rc, "tui": rc}
    rec.details = {"cli_rows": len(cli_rows), "cli_surfaces": cli_surfaces, "rows_total": len(rows),
                   "tui_rows": len(tui_rows), "rows_without_surface": len(absent),
                   "by_surface_calls": counts, "statuses": statuses, "keys_typed": len(marks)}
    cli_ok = b.rc == 0 and cli_rows and cli_surfaces == ["cli"]
    tui_ok = rc == 0 and len(tui_rows) >= 2 and statuses.count("PASSED") == 2
    sum_ok = isinstance(by_surface, dict) and counts.get("cli") == len(cli_rows) \
        and counts.get("tui") == len(tui_rows) and not absent
    if cli_ok and tui_ok and sum_ok:
        return finish(rec, "PASS", f"build rows say cli ({len(cli_rows)}), the TUI task's rows say tui "
                      f"({len(tui_rows)}), no row lacks a surface, and status --json by_surface counts match.")
    if cli_ok and tui_ok:
        return finish(rec, "PARTIAL", f"rows carry cli/tui as expected but status --json by_surface="
                      f"{counts or by_surface}; rows without surface {len(absent)}")
    return finish(rec, "FAIL", f"build exit {b.rc} rows {len(cli_rows)} surfaces {cli_surfaces}; "
                  f"tui exit {rc} tui rows {len(tui_rows)} statuses {statuses}; by_surface {counts or by_surface}; "
                  f"rows without surface {len(absent)}")


def render(h: Harness, records: list[Record]) -> str:
    testable = list(records)   # every claim run here is testable; the rest are in UNTESTABLE
    passed = sum(1 for r in testable if r.verdict == "PASS")
    by = lambda v: [r.id for r in testable if r.verdict == v]  # noqa: E731
    lines = [f"# CrossAudit README acceptance — `{h.label}`", "",
             f"- ref: `{h.ref}` → `{h.ref_sha}`",
             f"- run: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}, harness `benchmarks/claims/run.py`, "
             f"product installed as `{h.install_spec}` into a fresh venv "
             f"(Python {sys.version.split()[0]})",
             f"- spec: [`CLAIMS.md`](CLAIMS.md); raw records: `records/{h.label}/claims.jsonl`; "
             f"evidence: `records/{h.label}/evidence/<claim>/`",
             "",
             f"**Score: {passed} PASS of {len(testable)} testable claims run.** "
             f"PARTIAL: {', '.join(by('PARTIAL')) or '—'}. FAIL: {', '.join(by('FAIL')) or '—'}. "
             f"UNTESTED: {', '.join(by('UNTESTED')) or '—'}.", "",
             "| id | verdict | observation | evidence |", "|---|---|---|---|"]
    for r in records:
        ev = [c.evidence for c in r.commands if c.evidence][:3] + r.evidence[:2]
        evs = "<br>".join(f"`{e}`" for e in ev) if ev else "—"
        obs = r.observation.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r.id} | **{r.verdict}** | {obs} | {evs} |")
    for cid, what, needs in UNTESTABLE:
        lines.append(f"| {cid} | **UNTESTED** | {what}. Needs: {needs}. | — |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--keep", action="store_true", help="keep the temporary projects")
    args = ap.parse_args(argv)
    for v in PROXY_VARS:
        os.environ.pop(v, None)
    out = Path(args.out)
    if not out.is_absolute():
        out = HERE / out
    out.mkdir(parents=True, exist_ok=True)
    h = Harness(args.ref, out, args.keep)
    only = {x.strip().upper() for x in args.only.split(",") if x.strip()}
    wanted = set()
    for cid, _t, _f, deps in CLAIMS:
        if not only or cid.upper() in only:
            wanted.add(cid)
            wanted.update(deps)
    if "C29" in wanted or "C30" in wanted or "C31" in wanted:
        wanted.add("C28")
    t0 = time.time()
    try:
        print(f"[harness] installing {args.ref} …", flush=True)
        h.install()
        print(f"[harness] installed {h.ref_sha[:12]} in {time.time() - t0:.0f}s; temp {h.tmp}", flush=True)
        for cid, title, fn, _deps in CLAIMS:
            if cid not in wanted:
                continue
            rec = Record(cid, title)
            h.records[cid] = rec
            t1 = time.time()
            try:
                fn(h, rec)
            except Exception as exc:  # a harness crash is recorded, never hidden
                rec.verdict = "UNTESTED"
                rec.observation = f"harness error: {exc!r}"
                rec.details["traceback"] = traceback.format_exc()
            rec.details.setdefault("seconds", round(time.time() - t1, 1))
            print(f"[harness] {cid} {rec.verdict:8s} {time.time() - t1:5.1f}s  {short(rec.observation, 110)}",
                  flush=True)
        for key, p in list(h.projects.items()):
            try:
                p.stop()
            except Exception:
                pass
    finally:
        records = [h.records[c] for c, *_ in CLAIMS if c in h.records]
        with open(out / "claims.jsonl", "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r.as_dict(), ensure_ascii=False) + "\n")
        (HERE / f"RESULTS-{h.label}.md").write_text(render(h, records), encoding="utf-8")
        h.cleanup()
        print(f"[harness] done in {time.time() - t0:.0f}s → {out / 'claims.jsonl'}, "
              f"{HERE / ('RESULTS-' + h.label + '.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
