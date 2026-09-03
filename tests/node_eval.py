"""Run an assembled JavaScript program under node, from a file.

`node -e <program>` puts the whole program in one argv entry. Linux caps a
single entry at `MAX_ARG_STRLEN` (128 KiB) regardless of `ARG_MAX`, and the
programs these guards assemble — the shipped `page.py` script plus a DOM shim —
have grown past that. Every Linux runner raised

    OSError: [Errno 7] Argument list too long: '/usr/local/bin/node'

while macOS, which caps the total block rather than one entry, still passed. A
temporary file has no such cap and hands node byte-identical input.

The suffix is `.js`, not `.mjs`: `node -e` runs its argument as a sloppy-mode
CommonJS script, and these programs concatenate page functions that redeclare
names, which an ES module rejects outright.

The explicit `encoding`/`errors` also keep the CJK these guards assert on
readable on Windows, where `text=True` would otherwise decode through the
console code page.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def node_path() -> str | None:
    """The node executable, or None when it is not installed."""
    return shutil.which("node")


def run_node(js: str, executable: str | None = None) -> subprocess.CompletedProcess:
    """Run `js` under node and return the completed process."""
    exe = executable or node_path() or "node"
    handle, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(js)
        return subprocess.run([exe, path], text=True, capture_output=True,
                              encoding="utf-8", errors="replace")
    finally:
        os.unlink(path)
