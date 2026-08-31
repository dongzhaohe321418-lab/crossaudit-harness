"""Enumerate user-facing console strings BY EXECUTION, and publish the predicate.

A census by pattern is a floor by construction: a regex reports what its author
could imagine expressing, which is a fact about the pattern rather than about
the code. Only execution can claim completeness, and only over the paths it
actually drove — a smaller and honest claim.

THE PREDICATE. Every number this produces means exactly:

    shape   a JSON string value of three or more words matching SENTENCE,
            anywhere in a response body (nested dicts and lists included)
    files   whatever the running server produces; no file list is consulted
    method  real HTTP requests against `serve(cfg, port=0)` — the shipped
            server, not a fixture standing in for it
    paths   the ones listed in the result, and no others
    states  the fixture states listed in the result; `/api/state` on an empty
            project and on a populated one are different paths in every sense
            that matters, and the same endpoint returns different strings
    unit    DISTINCT values, not occurrences. The two differ and the difference
            is the two halves of the work: distinct values are catalogue
            entries, occurrences are code sites to key.

WHAT IT CANNOT CLAIM. Nothing about paths it did not drive. A string absent from
the output is either dead or unreached, and this cannot tell you which — that is
a finding to chase, not a zero to report.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

SENTENCE = re.compile(r"^[A-Z][A-Za-z0-9 ,'’\-—:;()\.]{9,}$")


def sentence_values(payload: object, out: set) -> None:
    if isinstance(payload, str):
        text = payload.strip()
        if SENTENCE.match(text) and len(text.split()) >= 3:
            out.add(text)
    elif isinstance(payload, dict):
        for value in payload.values():
            sentence_values(value, out)
    elif isinstance(payload, list):
        for value in payload:
            sentence_values(value, out)


def project(root: Path):
    from crossaudit.config import load

    (root / "cycles").mkdir(parents=True, exist_ok=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** x\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\nchecks: [parseable]\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    return load(root / "crossaudit.yml")


def drive(cfg, plan: list[tuple[str, bytes | None]]) -> tuple[set, list]:
    """Run the shipped server and record what each path produced."""
    from crossaudit.console.server import serve

    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    found: set = set()
    executed: list = []
    try:
        for path, body in plan:
            target = url.replace("/?t=", path + "?t=")
            request = urllib.request.Request(
                target, data=body, method="POST" if body is not None else "GET",
                headers={"content-type": "application/json"} if body else {})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    status, raw = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, raw = exc.code, exc.read()
            try:
                payload = json.loads(raw)
            except ValueError:
                executed.append((path, status, 0, "not json"))
                continue
            before = len(found)
            sentence_values(payload, found)
            executed.append((path, status, len(found) - before, ""))
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()
    return found, executed
