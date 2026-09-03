#!/usr/bin/env python3
"""Vendor the Thinking Orbs canvas engine, pinned.

The console has no bundler: page.py is one HTML document that inlines its
own script.  The ``thinking-orbs`` package ships its framework-agnostic
engine as an ES module (``dist/engine.es.js``); the browser cannot load an
ES module from an inline classic ``<script>``, so this turns the module into
an IIFE that publishes only the surface the console's wrapper needs on
``window.ThinkingOrbsEngine``.  Everything else in the file is the package's
code, byte for byte.

Usage::

    python scripts/vendor_thinking_orbs.py /path/to/unpacked/package

The unpacked package directory holds ``package.json``, ``LICENSE`` and
``dist/engine.es.js`` (``npm pack thinking-orbs@0.3.1`` then untar).  The
output is ``src/crossaudit/console/vendor/thinking_orbs_engine.js``; the
test ``tests/test_thinking_orbs_vendor.py`` pins its sha256 and version
header so any drift — a re-vendor, a hand edit — is visible in review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PACKAGE_NAME = "thinking-orbs"
PINNED_VERSION = "0.3.1"
#: The names the console wrapper reads off ``window.ThinkingOrbsEngine``.
EXPORTED = ("resolvePreset", "MODE_DRAWS", "STATE_TO_MODE", "MODE_FRAMES",
            "paintFrame", "finalizeFrame")
GLOBAL_NAME = "ThinkingOrbsEngine"
OUTPUT = Path(__file__).resolve().parent.parent / "src/crossaudit/console/vendor/thinking_orbs_engine.js"

_EXPORT_BLOCK = re.compile(r"\nexport \{\n(?P<body>(?:\s*[\w$]+ as \w+,?\n)+)\};\s*$")
_EXPORT_PAIR = re.compile(r"^\s*(?P<local>[\w$]+) as (?P<name>\w+),?$")
_COPYRIGHT = re.compile(r"^Copyright \(c\) .+$", re.M)


def build(package_dir: Path) -> str:
    meta = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    name, version, licence = meta.get("name"), meta.get("version"), meta.get("license")
    if name != PACKAGE_NAME:
        raise SystemExit(f"package.json names {name!r}, expected {PACKAGE_NAME!r}")
    if version != PINNED_VERSION:
        raise SystemExit(f"package.json is version {version!r}; this script pins "
                         f"{PINNED_VERSION!r} — bump PINNED_VERSION deliberately")
    if licence != "MIT":
        raise SystemExit(f"package.json declares licence {licence!r}, expected MIT")
    licence_text = (package_dir / "LICENSE").read_text(encoding="utf-8")
    copyright_line = _COPYRIGHT.search(licence_text)
    if not copyright_line or "MIT License" not in licence_text:
        raise SystemExit("LICENSE is not the MIT text with a copyright line")
    source = (package_dir / "dist/engine.es.js").read_text(encoding="utf-8")
    if "import " in source.split("\n", 1)[0] or re.search(r"^import\b", source, re.M):
        raise SystemExit("engine.es.js imports something; it is no longer self-contained")
    block = _EXPORT_BLOCK.search(source)
    if not block:
        raise SystemExit("engine.es.js has no trailing `export { ... };` block")
    exported: dict[str, str] = {}
    for line in block.group("body").strip("\n").split("\n"):
        pair = _EXPORT_PAIR.match(line)
        if not pair:
            raise SystemExit(f"unreadable export line: {line!r}")
        exported[pair.group("name")] = pair.group("local")
    missing = [n for n in EXPORTED if n not in exported]
    if missing:
        raise SystemExit(f"engine.es.js no longer exports {missing}")
    body = source[:block.start()].rstrip("\n")
    if re.search(r"^export\b", body, re.M):
        raise SystemExit("an `export` survived outside the trailing block")
    published = ",\n".join(f"  {n}: {exported[n]}" for n in EXPORTED)
    header = "\n".join([
        "/*!",
        f" * {PACKAGE_NAME} {version} — dist/engine.es.js, vendored for the CrossAudit console.",
        f" * npm package {PACKAGE_NAME} (the npmjs registry); no URL here, the console page reaches nowhere.",
        " *",
        " * The module body below is the package's build output, unchanged. Only the",
        " * trailing ES `export` block was replaced by the IIFE assignment at the end,",
        f" * which publishes {', '.join(EXPORTED)}",
        f" * on window.{GLOBAL_NAME}. Regenerate with scripts/vendor_thinking_orbs.py.",
        " *",
        " * MIT License",
        " *",
        f" * {copyright_line.group(0)}",
        " *",
    ] + [" * " + line if line else " *" for line in _permission_notice(licence_text)] + [" */"])
    out = "\n".join([
        header,
        "(function (root) {",
        '"use strict";',
        body,
        f"root.{GLOBAL_NAME} = Object.freeze({{",
        published,
        "});",
        "})(typeof window !== 'undefined' ? window : globalThis);",
        "",
    ])
    if "</script" in out.lower():
        raise SystemExit("the vendored file would close the inline <script>")
    return out


def _permission_notice(licence_text: str) -> list[str]:
    start = licence_text.index("Permission is hereby granted")
    return [line.rstrip() for line in licence_text[start:].strip().split("\n")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("package_dir", type=Path, help="unpacked thinking-orbs package")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    text = build(args.package_dir.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"wrote {args.out} ({len(text)} bytes) sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
