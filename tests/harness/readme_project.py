"""A project made the way the README makes one, for the README-flow tests.

The black-box acceptance run (benchmarks/claims) found gaps between README
sentences and the product by running the documented commands on a project the
documented command created. These helpers do the same in-process: the project
comes from the real `crossaudit init ... --no-console` with stdin not a
terminal (pytest's stdin is not one), never from a hand-written fixture, so a
test cannot pass on a shape `init` does not produce.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

INIT_ARGV = ["--no-console",
             "--auditor-vendor", "openai", "--auditor-model", "gpt-5.6-terra",
             "--generator-vendor", "anthropic",
             "--generator-model", "claude-sonnet-4-6"]


def init_project(tmp_path: Path, monkeypatch, name: str = "proj") -> Path:
    """Run the README's non-interactive `init` and chdir into the project."""
    from crossaudit.cli import main

    monkeypatch.chdir(tmp_path)
    assert main.main(["init", name, *INIT_ARGV]) == 0
    root = (tmp_path / name).resolve()
    monkeypatch.chdir(root)
    return root


def tree_digest(root: Path) -> dict[str, str]:
    """Every file under ``root`` (``.git`` and ``.crossaudit`` included) by
    content digest, plus every directory, so a created empty directory counts
    as a change too."""
    out: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            out[rel + "/"] = "dir"
        elif path.is_file():
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


# ------------------------------------------------------------ fake vendors
# The two vendors `init` configured (openai auditor, anthropic generator),
# stubbed at the transport (`request_json` / `request_stream`) so the real
# adapters, the resilience layer, the build loop and the audit all run. The
# role is read from the system prompt, as benchmarks/claims/fakeproviders.py
# does, so a scenario answers per role and per call count.
import json  # noqa: E402
import re  # noqa: E402

FILE_OPEN = '<<<CROSSAUDIT-OUTPUT-FILE path="{path}">>>'
FILE_END = "<<<END-CROSSAUDIT-OUTPUT-FILE>>>"
INC_DIR = "experiments/2026-10-21-bench"
ROLE_PREFIXES = (
    ("generator", "You produce work for a supervised project"),
    ("auditor", "You are the Auditor in a CrossAudit loop"),
    ("amend", "You amend an existing rulebook"),
)
_RULE_RE = re.compile(r"^###\s+(CA-[A-Z]+-\d+)", re.M)
_INC_FILE_RE = re.compile(r"^--- (.+?) ---$", re.M)


def role_of(system: str) -> str:
    text = (system or "").lstrip()
    for role, prefix in ROLE_PREFIXES:
        if text.startswith(prefix):
            return role
    return "other"


def increment_reply() -> str:
    """A complete increment that passes the `general` pack."""
    src = f"{INC_DIR}/bench.py@v1"
    files = {
        f"{INC_DIR}/bench.py": "SEED = 7\nprint('runtime', 1.5)\n",
        f"{INC_DIR}/metadata.yml": ("code_version: v1\nseed: 7\n"
                                    "command: python bench.py\n"
                                    f"inputs:\n  - {src}\n"),
        f"{INC_DIR}/results.json": json.dumps(
            {"quantities": [{"name": "runtime", "value": 1.5, "unit": "s",
                             "source": src}],
             "convergence": {"converged": True}}, indent=2) + "\n",
        f"{INC_DIR}/SUMMARY.md": "# Benchmark\n\nThe benchmark ran in 1.5 s with seed 7.\n",
    }
    out = ["SUMMARY: benchmark increment"]
    for path, content in files.items():
        out += [FILE_OPEN.format(path=path), content.rstrip("\n"), FILE_END]
    out.append("NOTES: ")
    return "\n".join(out) + "\n"


def audit_reply(prompt: str, verdict: str = "PASS") -> str:
    block = prompt.split("<<<CONSTITUTION", 1)[-1].split("\nCONSTITUTION\n", 1)[0]
    rules = list(dict.fromkeys(_RULE_RE.findall(block))) or ["CA-CONTENT-001"]
    findings = []
    if verdict == "BLOCKED":
        paths = _INC_FILE_RE.findall(prompt.split("<<<INCREMENT", 1)[-1])
        findings.append({"severity": "BLOCKER", "rule": rules[0],
                         "artifact": paths[0] if paths else "increment",
                         "observation": "blocking defect"})
    return json.dumps({"verdict": verdict, "sections_applied": rules,
                       "findings": findings})


class FakeVendors:
    """Answers per role; ``answer(role, n, prompt)`` returns text or raises.

    ``calls`` records (vendor, role) for every request that reached the
    transport, so a test can assert that nothing did.
    """

    def __init__(self, answer=None):
        self.answer = answer or self.clean
        self.calls: list[tuple[str, str]] = []
        self.counts: dict[str, int] = {}

    @staticmethod
    def clean(role: str, _n: int, prompt: str) -> str:
        if role == "generator":
            return increment_reply()
        if role == "auditor":
            return audit_reply(prompt, "PASS")
        return "Acknowledged."

    def _reply(self, vendor: str, system: str, prompt: str) -> str:
        role = role_of(system)
        self.calls.append((vendor, role))
        self.counts[role] = self.counts.get(role, 0) + 1
        return self.answer(role, self.counts[role], prompt)

    def install(self, monkeypatch) -> "FakeVendors":
        from crossaudit.providers import anthropic, openai_compat, resilience

        monkeypatch.setattr(resilience, "_sleep", lambda *_a: None)

        def text_of(content) -> str:
            if isinstance(content, str):
                return content
            return "".join(b.get("text", "") for b in content or []
                           if isinstance(b, dict))

        def split_openai(payload):
            msgs = payload.get("messages") or []
            system = next((m.get("content", "") for m in msgs
                           if m.get("role") == "system"), "")
            prompt = next((text_of(m.get("content")) for m in reversed(msgs)
                           if m.get("role") == "user"), "")
            return text_of(system), prompt

        def split_anthropic(payload):
            msgs = payload.get("messages") or []
            prompt = next((text_of(m.get("content")) for m in reversed(msgs)
                           if m.get("role") == "user"), "")
            return text_of(payload.get("system") or ""), prompt

        def openai_json(_url, payload, _headers, *, timeout):
            text = self._reply("openai", *split_openai(payload))
            return {"id": "c1", "choices": [{"index": 0, "message": {
                "role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}, "rid"

        def openai_stream(_url, payload, _headers, *, timeout, on_bytes, on_idle):
            text = self._reply("openai", *split_openai(payload))
            for row in ({"id": "c1", "choices": [{"index": 0, "delta": {
                            "role": "assistant", "content": text},
                            "finish_reason": None}]},
                        {"id": "c1", "choices": [{"index": 0, "delta": {},
                                                  "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}}):
                on_bytes(("data: " + json.dumps(row) + "\n\n").encode())
            on_bytes(b"data: [DONE]\n\n")
            return "rid"

        def anthropic_json(_url, payload, _headers, *, timeout):
            text = self._reply("anthropic", *split_anthropic(payload))
            return {"id": "m1", "content": [{"type": "text", "text": text}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 5}}, "rid"

        def anthropic_stream(_url, payload, _headers, *, timeout, on_bytes, on_idle):
            text = self._reply("anthropic", *split_anthropic(payload))

            def ev(name, data):
                on_bytes(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
            ev("message_start", {"type": "message_start", "message": {
                "id": "m1", "usage": {"input_tokens": 10}}})
            ev("content_block_start", {"type": "content_block_start", "index": 0,
                                       "content_block": {"type": "text", "text": ""}})
            ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                       "delta": {"type": "text_delta", "text": text}})
            ev("content_block_stop", {"type": "content_block_stop", "index": 0})
            ev("message_delta", {"type": "message_delta",
                                 "delta": {"stop_reason": "end_turn"},
                                 "usage": {"output_tokens": 5}})
            ev("message_stop", {"type": "message_stop"})
            return "rid"

        monkeypatch.setattr(openai_compat, "request_json", openai_json)
        monkeypatch.setattr(openai_compat, "request_stream", openai_stream)
        monkeypatch.setattr(anthropic, "request_json", anthropic_json)
        monkeypatch.setattr(anthropic, "request_stream", anthropic_stream)
        return self


def http_500(role: str, _n: int, _prompt: str) -> str:
    """Every call fails the way a vendor's HTTP 500 does at the transport."""
    from crossaudit.providers.base import _http_denial

    raise _http_denial(500, '{"error": {"message": "internal error"}}',
                       "https://vendor.invalid/v1")


def with_keys(monkeypatch) -> None:
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "test-credential-present")
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "test-credential-present")
