"""The vendored Thinking Orbs engine is pinned, licensed, and served.

The console has no bundler, so the third-party engine is a file in the
package, inlined as a classic script before the console's own. Three things
must stay true and each has its own failure mode: the bytes must be the
reviewed bytes (a re-vendor or a hand edit is a drift the review must see),
the licence must travel with them, and the page must actually serve them
before the code that reads ``window.ThinkingOrbsEngine``.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "src/crossaudit/console/vendor/thinking_orbs_engine.js"
SCRIPT = ROOT / "scripts/vendor_thinking_orbs.py"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"

#: sha256 of the reviewed vendored file. Regenerating from a different
#: package version, or editing the file by hand, changes this on purpose.
PINNED_SHA256 = "aa0f86f7c6c82eecec6fd0276dab3f8efc9976811b2a93b63feb76df53280784"
PINNED_VERSION = "0.3.1"
PUBLISHED = ("resolvePreset", "MODE_DRAWS", "STATE_TO_MODE", "MODE_FRAMES",
             "paintFrame", "finalizeFrame")


def test_the_vendored_engine_is_the_pinned_bytes():
    digest = hashlib.sha256(VENDORED.read_bytes()).hexdigest()
    assert digest == PINNED_SHA256, (
        f"thinking_orbs_engine.js drifted (sha256 {digest}); if this is a "
        f"deliberate re-vendor, update PINNED_SHA256 and PINNED_VERSION together")


def test_the_header_names_the_package_version_and_licence():
    head = VENDORED.read_text(encoding="utf-8")[:2000]
    assert head.startswith("/*!")
    assert f"thinking-orbs {PINNED_VERSION}" in head
    assert "MIT License" in head
    assert "Copyright (c) 2026 Jakub Antalik" in head
    assert "Permission is hereby granted" in head
    assert "scripts/vendor_thinking_orbs.py" in head


def test_the_script_pins_the_same_version():
    source = SCRIPT.read_text(encoding="utf-8")
    assert f'PINNED_VERSION = "{PINNED_VERSION}"' in source


def test_the_file_is_an_iife_with_no_module_syntax_and_no_script_close():
    text = VENDORED.read_text(encoding="utf-8")
    assert re.search(r"^export\b", text, re.M) is None
    assert re.search(r"^import\b", text, re.M) is None
    assert "</script" not in text.lower()
    assert "root.ThinkingOrbsEngine = Object.freeze({" in text
    for name in PUBLISHED:
        assert re.search(rf"^  {name}: [\w$]+,?$", text, re.M), name


def test_the_notices_file_carries_the_mit_entry():
    notices = NOTICES.read_text(encoding="utf-8")
    assert f"## thinking-orbs {PINNED_VERSION}" in notices
    assert "Copyright (c) 2026 Jakub Antalik" in notices
    assert "src/crossaudit/console/vendor/thinking_orbs_engine.js" in notices


def test_the_page_serves_the_engine_inline_before_its_own_script():
    from crossaudit.console.page import PAGE

    engine_at = PAGE.index('<script id="thinking-orbs-engine">')
    own_at = PAGE.index("<script>")
    assert engine_at < own_at
    assert VENDORED.read_text(encoding="utf-8") in PAGE
    assert "<script src=" not in PAGE, "the console loads no remote code"


def test_the_package_ships_the_vendored_file():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"crossaudit.console" = ["vendor/*.js"]' in pyproject


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_engine_runs_under_node_and_publishes_the_states():
    probe = (
        f"require({str(VENDORED)!r});"
        "const E=globalThis.ThinkingOrbsEngine;"
        "const keys=Object.keys(E).sort();"
        "const states=Object.keys(E.STATE_TO_MODE).sort();"
        "const r=E.resolvePreset('composing',20);"
        "console.log(JSON.stringify({keys,states,mode:r.mode,"
        "draws:states.every(s=>typeof E.MODE_DRAWS[E.STATE_TO_MODE[s]]==='function'),"
        "frozen:Object.isFrozen(E)}));")
    out = subprocess.run(["node", "-e", probe], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    import json
    got = json.loads(out.stdout)
    assert got["keys"] == sorted(PUBLISHED)
    assert got["states"] == sorted(["working", "searching", "solving", "listening",
                                    "connecting", "weaving", "composing",
                                    "breathing", "shaping"])
    assert got["mode"] == "ribbon" and got["draws"] and got["frozen"]
