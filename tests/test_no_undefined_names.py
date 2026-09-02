"""No name in `src/` may be referenced without being defined or imported.

`cli/main.py` returned `EXIT_DENIED` on the invalid-signature path of
`verify --admit` for weeks. The name did not exist; the path raised NameError
instead of returning an exit code, and no test drove it. The release gate's
ruff step would have caught it, but the gate is a script nobody ran. So the
check moves into the suite, where it runs every time.

MUTATION (D64): add `return NO_SUCH_NAME` to any function under src/ and this
reddens naming the file and line. Verified by re-introducing `EXIT_DENIED`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"


def test_src_has_no_undefined_names():
    probe = subprocess.run([sys.executable, "-m", "ruff", "--version"],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.skip("ruff is not installed in this interpreter")
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F821,F822,F823",
         "--no-cache", str(SRC)],
        capture_output=True, text=True)
    assert result.returncode == 0, (
        "undefined names in src/ (a NameError waiting for a user):\n" + result.stdout)
