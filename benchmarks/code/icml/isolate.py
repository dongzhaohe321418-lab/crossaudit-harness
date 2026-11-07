"""OS-level isolation for auditors that run commands (E3 agentic, E5 execution).

Post hoc command filtering is not enough: an auditor with a shell can look for the clean source of an item
anywhere on the disk, and discarding those readings makes missingness depend on the item. Instead every
tool-using reading runs inside a macOS seatbelt profile that

- denies reading the user's home, the temporary directories and mounted volumes, except the reading's own
  work directory and the files the CLI itself needs (its install, its isolated login home);
- denies writing outside the work directory and the CLI's own state;
- denies all network except one loopback port, where an egress proxy admits CONNECT only to the vendor's
  API hosts. Commands inherit the proxy variables, so they can reach nothing else.

Seatbelt cannot be nested, so the CLI's own sandbox is turned off inside this one (Codex
danger-full-access; Claude without its sandbox settings). The command log is still kept and checked.

    python benchmarks/code/icml/isolate.py proxy     # run once, in the background, before the audits
"""
from __future__ import annotations

import os
import select
import socket
import sys
import tempfile
import threading
from pathlib import Path

HOME = Path.home().resolve()
PROXY_PORT = 18777
ALLOW_HOSTS = ("api.openai.com", "chatgpt.com", "ab.chatgpt.com", "api.anthropic.com", "statsig.anthropic.com",
               "claude.ai", "console.anthropic.com", "mcp-proxy.anthropic.com")
WORK_ROOT = Path("/private/tmp/caudit")
TMP = Path(tempfile.gettempdir()).resolve()
LOG = Path(__file__).resolve().parents[1] / "records" / "egress_proxy.log"

CLI_READ = {
    "codex": [HOME / ".codex" / "packages", HOME / ".local" / "bin"],
    "claude": [HOME / ".local" / "share" / "claude", HOME / ".local" / "bin", HOME / ".claude.json",
               HOME / "Library" / "Keychains"],
}
CLI_WRITE = {"codex": [], "claude": [HOME / ".claude.json", HOME / ".claude" / "debug", HOME / ".claude" / "statsig"]}


def workdir() -> Path:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="audit_", dir=WORK_ROOT)).resolve()
    (d / ".tmp").mkdir()
    return d


def _q(p: Path) -> str:
    return '"' + str(p).replace("\\", "\\\\").replace('"', '\\"') + '"'


def profile(kind: str, work: Path, extra_read: list[Path] = (), extra_write: list[Path] = ()) -> str:
    reads = [work, *CLI_READ[kind], *extra_read]
    writes = [work, *CLI_WRITE[kind], *extra_write]
    sub = lambda ps: " ".join(f"(subpath {_q(Path(p).resolve())})" for p in ps)
    anc = lambda ps: " ".join(f"(literal {_q(a)})" for a in sorted({a for p in ps for a in Path(p).resolve().parents}))
    return "\n".join([
        "(version 1)",
        "(allow default)",
        f"(deny file-read* (subpath {_q(HOME)}) (subpath {_q(TMP)}) (subpath \"/private/tmp\")"
        f" (subpath \"/Volumes\"))",
        # directory metadata on the path to an allowed file must stay readable for path resolution
        f"(allow file-read-metadata {anc(reads + writes)})",
        f"(allow file-read* {sub(reads)})",
        f"(deny file-write* (subpath {_q(HOME)}) (subpath {_q(TMP)}) (subpath \"/private/tmp\"))",
        f"(allow file-write* {sub(writes)})",
        "(deny network*)",
        f"(allow network-outbound (remote ip \"localhost:{PROXY_PORT}\"))",
        "(allow network-outbound (literal \"/private/var/run/mDNSResponder\"))",
    ])


def wrap(kind: str, cmd: list[str], work: Path, env: dict, extra_read=(), extra_write=()) -> tuple[list[str], dict]:
    """Return (argv, env) running cmd under the profile, with proxy variables and TMPDIR inside the work dir."""
    prof = profile(kind, work, list(extra_read), list(extra_write))
    url = f"http://127.0.0.1:{PROXY_PORT}"
    env = {**env, "HTTPS_PROXY": url, "HTTP_PROXY": url, "https_proxy": url, "http_proxy": url,
           "ALL_PROXY": url, "NO_PROXY": "", "TMPDIR": str(work / ".tmp"),
           "CLAUDE_CODE_TMPDIR": str(work / ".tmp"), "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1"}
    return ["sandbox-exec", "-p", prof, *cmd], env


def proxy_up() -> bool:
    try:
        socket.create_connection(("127.0.0.1", PROXY_PORT), timeout=2).close()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- egress proxy (CONNECT allowlist only)
def _allowed(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in ALLOW_HOSTS)


def _pipe(a: socket.socket, b: socket.socket) -> None:
    socks = [a, b]
    try:
        while True:
            r, _, _ = select.select(socks, [], [], 600)
            if not r:
                return
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except OSError:
        return
    finally:
        a.close()
        b.close()


def _handle(c: socket.socket, log) -> None:
    try:
        head = b""
        while b"\r\n\r\n" not in head and len(head) < 65536:
            chunk = c.recv(4096)
            if not chunk:
                return
            head += chunk
        line = head.split(b"\r\n", 1)[0].decode("latin-1")
        parts = line.split()
        method, target = (parts + ["", ""])[:2]
        host, _, port = target.rpartition(":") if method == "CONNECT" else (target, "", "")
        ok = method == "CONNECT" and port == "443" and _allowed(host)
        log.write(f"{'ALLOW' if ok else 'DENY'} {line}\n")
        log.flush()
        if not ok:
            c.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            c.close()
            return
        u = socket.create_connection((host, 443), timeout=30)
        c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        rest = head.split(b"\r\n\r\n", 1)[1]
        if rest:
            u.sendall(rest)
        _pipe(c, u)
    except OSError:
        c.close()


def serve() -> None:
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PROXY_PORT))
    s.listen(256)
    with LOG.open("a") as log:
        while True:
            c, _ = s.accept()
            threading.Thread(target=_handle, args=(c, log), daemon=True).start()


if __name__ == "__main__":
    if sys.argv[1:] == ["proxy"]:
        serve()
    else:
        print(__doc__)
