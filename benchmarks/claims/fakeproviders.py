"""Two scripted fake model providers on 127.0.0.1 (stdlib only).

* ``OpenAIHandler`` speaks enough of the OpenAI chat-completions contract
  (``POST /v1/chat/completions``; JSON and ``stream: true`` SSE with ``data:``
  lines and a ``[DONE]`` terminator; ``choices[0].message.content`` /
  ``delta.content``; ``finish_reason``; ``usage``).
* ``AnthropicHandler`` speaks enough of the Messages contract
  (``POST /v1/messages``; JSON and SSE with ``message_start``,
  ``content_block_start``/``content_block_delta``/``content_block_stop``,
  ``message_delta`` carrying ``stop_reason`` and usage, ``message_stop``).

Neither server knows anything about CrossAudit beyond the reply *text*: a
``Scenario`` decides, per request, what to answer from the request's role
(read from the system prompt the product sends) and from how many requests of
that role came before (the "round"). Failures are a function of that count
only, so the product's retry/backoff layer cannot change what the fake does.

Every request's model, system prompt, user prompt and request-shape keys are
written to ``capture_dir`` so a claim can inspect exactly what the product
sent. Credentials are never written: only whether an auth header was present.
"""
from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# --------------------------------------------------------------- role reading
#: The first words of each system prompt the product sends, as read from
#: src/crossaudit/{generator.py, auditor/prompt.py, constitution.py, cli/talk.py}.
ROLE_PREFIXES = (
    ("generator", "You produce work for a supervised project"),
    ("auditor", "You are the Auditor in a CrossAudit loop"),
    ("amend", "You amend an existing rulebook"),
    ("distil", "You turn a person's description"),
    ("auditor_chat", "You are the independent Auditor in a supervised project"),
    ("generator_chat", "You are the Generator in a supervised project"),
)


def role_of(system: str) -> str:
    text = (system or "").lstrip()
    for role, prefix in ROLE_PREFIXES:
        if text.startswith(prefix):
            return role
    return "other"


def reply(text: str, finish: str = "stop") -> dict:
    """A completion. ``finish='length'`` means the provider cut it off."""
    return {"text": text, "finish": finish}


def http_error(status: int, message: str) -> dict:
    return {"http_status": status, "message": message}


# ------------------------------------------------------------ reply builders
FILE_OPEN = '<<<CROSSAUDIT-OUTPUT-FILE path="{path}">>>'
FILE_END = "<<<END-CROSSAUDIT-OUTPUT-FILE>>>"


def envelope(files: dict, summary: str = "benchmark increment", notes: str = "",
             drop_last_end: bool = False) -> str:
    """The generator reply format `generator.parse_work_reply` reads."""
    out = [f"SUMMARY: {summary}"]
    items = list(files.items())
    for i, (path, content) in enumerate(items):
        out.append(FILE_OPEN.format(path=path))
        out.append(content.rstrip("\n"))
        if not (drop_last_end and i == len(items) - 1):
            out.append(FILE_END)
    if not drop_last_end:
        out.append(f"NOTES: {notes}")
    return "\n".join(out) + ("\n" if not drop_last_end else "")


INC_DIR = "experiments/2026-10-21-bench"


def increment(value: float = 1.5, *, unit: str | None = "s",
              summary_line: str | None = None, extra: dict | None = None) -> dict:
    """A complete, rule-abiding science increment (passes `general` and `science`).

    metadata.yml declares code_version and one `path@rev` input that exists in
    scope; results.json carries quantities with unit and source matching that
    input and a converged block; SUMMARY.md agrees with the number. Setting
    ``unit=None`` drops the unit (the dcl-fail scenario, CA-DATA-001).
    """
    src = f"{INC_DIR}/bench.py@v1"
    quantity = {"name": "runtime", "value": value, "source": src}
    if unit is not None:
        quantity["unit"] = unit
    files = {
        f"{INC_DIR}/bench.py": "import time\n\nSEED = 7\nprint('runtime', %s)\n" % value,
        f"{INC_DIR}/metadata.yml": (
            "code_version: v1\n"
            "seed: 7\n"
            "command: python bench.py\n"
            f"inputs:\n  - {src}\n"),
        f"{INC_DIR}/results.json": json.dumps(
            {"quantities": [quantity], "convergence": {"converged": True}},
            indent=2) + "\n",
        f"{INC_DIR}/SUMMARY.md": (
            "# Benchmark\n\n"
            + (summary_line or f"The benchmark ran in {value} s with seed 7.")
            + "\n"),
    }
    files.update(extra or {})
    return files


RULE_RE = re.compile(r"^###\s+(CA-[A-Z]+-\d+)", re.M)
INC_FILE_RE = re.compile(r"^--- (.+?) ---$", re.M)


def rules_in(prompt: str) -> list[str]:
    block = prompt.split("<<<CONSTITUTION", 1)[-1].split("\nCONSTITUTION\n", 1)[0]
    found = RULE_RE.findall(block)
    seen: list[str] = []
    for rid in found:
        if rid not in seen:
            seen.append(rid)
    return seen


def first_artifact(prompt: str) -> str:
    inc = prompt.split("<<<INCREMENT", 1)[-1]
    paths = INC_FILE_RE.findall(inc)
    for p in paths:
        if p.endswith("SUMMARY.md"):
            return p
    return paths[0] if paths else "increment"


def audit_json(prompt: str, verdict: str, observation: str = "") -> str:
    """The auditor reply `auditor/validate.validate_reply` accepts."""
    rules = rules_in(prompt) or ["CA-CONTENT-001"]
    cite = "CA-CONTENT-001" if "CA-CONTENT-001" in rules else rules[0]
    findings = []
    if verdict == "BLOCKED":
        findings.append({"severity": "BLOCKER", "rule": cite,
                         "artifact": first_artifact(prompt),
                         "observation": observation or "blocking defect"})
    return json.dumps({"verdict": verdict, "sections_applied": rules,
                       "findings": findings})


# ----------------------------------------------------------------- scenarios
class Scenario:
    """Base scenario: the generator writes the clean increment, the auditor
    passes, amend adds one advisory rule. Subclasses override per role."""

    name = "clean"

    def respond(self, role: str, n: int, system: str, prompt: str) -> dict:
        fn = getattr(self, role, None) or self.other
        return fn(n, system, prompt)

    def generator(self, n, system, prompt):
        return reply(envelope(increment()))

    def auditor(self, n, system, prompt):
        return reply(audit_json(prompt, "PASS"))

    def amend(self, n, system, prompt):
        return reply(json.dumps({
            "intent": "every benchmark states its exact command and random seed",
            "changes": [{"action": "add", "id": "CA-BENCH-001", "was": "",
                         "now": "Every benchmark names the exact command and the "
                                "random seed it was run with.",
                         "severity": "ADVISORY", "title": "Command and seed stated",
                         "why": "the person asked for command and seed"}]}))

    def distil(self, n, system, prompt):
        return http_error(503, "distil not scripted")

    def other(self, n, system, prompt):
        return reply("Acknowledged.")


# --------------------------------------------------------------------- server
class _State:
    def __init__(self, scenario: Scenario, capture_dir: Path):
        self.scenario = scenario
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.counts: dict[str, int] = {}
        self.seq = 0
        self.log: list[dict] = []

    def next(self, role: str) -> tuple[int, int]:
        with self.lock:
            self.counts[role] = self.counts.get(role, 0) + 1
            self.seq += 1
            return self.seq, self.counts[role]


class _Handler(BaseHTTPRequestHandler):
    server_version = "fakeprovider/1"
    state: _State = None  # type: ignore[assignment]
    vendor = ""
    route = ""

    def log_message(self, *_a):  # quiet
        pass

    # ---- request
    def do_GET(self):  # noqa: N802
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            return self._json(400, {"error": {"message": "bad json"}})
        if self.path.rstrip("/") != self.route:
            return self._json(404, {"error": {"message": f"no route {self.path}"}})
        system, prompt = self.split(body)
        role = role_of(system)
        seq, n = self.state.next(role)
        try:
            out = self.state.scenario.respond(role, n, system, prompt)
        except Exception as exc:  # scenario bug: answer 599 and record it
            out = http_error(599, f"scenario error: {exc!r}")
        record = {
            "seq": seq, "time": time.time(), "server": self.vendor,
            "path": self.path, "role": role, "n": n,
            "model": body.get("model"), "stream": bool(body.get("stream")),
            "request_keys": sorted(body),
            "auth_header_present": bool(self.headers.get("authorization")
                                        or self.headers.get("x-api-key")),
            "system": system, "prompt": prompt,
            "response": out,
        }
        name = f"{seq:03d}-{self.vendor}-{role}-{n}.json"
        (self.state.capture_dir / name).write_text(
            json.dumps(record, indent=2), encoding="utf-8")
        with self.state.lock:
            self.state.log.append({k: v for k, v in record.items()
                                   if k not in ("system", "prompt")})
        if "http_status" in out:
            return self._json(out["http_status"],
                              {"error": {"type": "api_error",
                                         "message": out["message"]}})
        if body.get("stream"):
            self.stream(out)
        else:
            self._json(200, self.whole(body, out))

    # ---- helpers
    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.send_header("x-request-id", f"req_fake_{self.state.seq}")
        self.end_headers()
        self.wfile.write(data)

    def _sse_start(self) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("x-request-id", f"req_fake_{self.state.seq}")
        self.end_headers()

    @staticmethod
    def pieces(text: str, size: int = 400) -> list[str]:
        return [text[i:i + size] for i in range(0, len(text), size)] or [""]


class OpenAIHandler(_Handler):
    vendor = "openai"
    route = "/v1/chat/completions"

    def split(self, body):
        msgs = body.get("messages") or []
        system = next((m.get("content", "") for m in msgs if m.get("role") == "system"), "")
        prompt = next((m.get("content", "") for m in reversed(msgs)
                       if m.get("role") == "user"), "")
        return system, prompt

    def whole(self, body, out):
        return {"id": f"chatcmpl-fake{self.state.seq}", "object": "chat.completion",
                "model": body.get("model"),
                "choices": [{"index": 0, "message": {"role": "assistant",
                                                    "content": out["text"]},
                             "finish_reason": out["finish"]}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                          "total_tokens": 150}}

    def stream(self, out):
        self._sse_start()
        base = {"id": f"chatcmpl-fake{self.state.seq}", "object": "chat.completion.chunk"}
        first = dict(base, choices=[{"index": 0, "delta": {"role": "assistant",
                                                            "content": ""},
                                     "finish_reason": None}])
        self.wfile.write(f"data: {json.dumps(first)}\n\n".encode())
        for piece in self.pieces(out["text"]):
            chunk = dict(base, choices=[{"index": 0, "delta": {"content": piece},
                                         "finish_reason": None}])
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        last = dict(base, choices=[{"index": 0, "delta": {},
                                    "finish_reason": out["finish"]}],
                    usage={"prompt_tokens": 100, "completion_tokens": 50,
                           "total_tokens": 150})
        self.wfile.write(f"data: {json.dumps(last)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


class AnthropicHandler(_Handler):
    vendor = "anthropic"
    route = "/v1/messages"

    def split(self, body):
        system = body.get("system") or ""
        if isinstance(system, list):
            system = "".join(b.get("text", "") for b in system if isinstance(b, dict))
        msgs = body.get("messages") or []
        prompt = ""
        for m in reversed(msgs):
            if m.get("role") == "user":
                c = m.get("content")
                prompt = c if isinstance(c, str) else "".join(
                    b.get("text", "") for b in (c or []) if isinstance(b, dict))
                break
        return system, prompt

    @staticmethod
    def stop(out):
        return "max_tokens" if out["finish"] == "length" else "end_turn"

    def whole(self, body, out):
        return {"id": f"msg_fake{self.state.seq}", "type": "message",
                "role": "assistant", "model": body.get("model"),
                "content": [{"type": "text", "text": out["text"]}],
                "stop_reason": self.stop(out), "stop_sequence": None,
                "usage": {"input_tokens": 100, "output_tokens": 50}}

    def stream(self, out):
        self._sse_start()

        def ev(name, data):
            self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())

        ev("message_start", {"type": "message_start", "message": {
            "id": f"msg_fake{self.state.seq}", "type": "message", "role": "assistant",
            "content": [], "model": "fake", "stop_reason": None,
            "usage": {"input_tokens": 100, "output_tokens": 1}}})
        ev("content_block_start", {"type": "content_block_start", "index": 0,
                                   "content_block": {"type": "text", "text": ""}})
        for piece in self.pieces(out["text"]):
            ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                       "delta": {"type": "text_delta", "text": piece}})
        ev("content_block_stop", {"type": "content_block_stop", "index": 0})
        ev("message_delta", {"type": "message_delta",
                             "delta": {"stop_reason": self.stop(out),
                                       "stop_sequence": None},
                             "usage": {"output_tokens": 50}})
        ev("message_stop", {"type": "message_stop"})
        self.wfile.flush()


class FakeProviders:
    """Both servers, sharing one scenario and one capture directory."""

    def __init__(self, scenario: Scenario, capture_dir: Path):
        self.state = _State(scenario, capture_dir)
        self.servers: list[ThreadingHTTPServer] = []
        self.threads: list[threading.Thread] = []

    def _start(self, base: type) -> str:
        handler = type(base.__name__ + "Bound", (base,), {"state": self.state})
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        srv.daemon_threads = True
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.servers.append(srv)
        self.threads.append(t)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    def start(self) -> "FakeProviders":
        self.openai_url = self._start(OpenAIHandler)
        self.anthropic_url = self._start(AnthropicHandler)
        return self

    @property
    def openai_base(self) -> str:
        return self.openai_url + "/v1"

    @property
    def anthropic_base(self) -> str:
        return self.anthropic_url

    def set_scenario(self, scenario: Scenario) -> None:
        with self.state.lock:
            self.state.scenario = scenario
            self.state.counts = {}

    def requests(self, role: str | None = None) -> list[dict]:
        with self.state.lock:
            rows = list(self.state.log)
        return [r for r in rows if role is None or r["role"] == role]

    def captures(self, role: str | None = None) -> list[dict]:
        out = []
        for p in sorted(self.state.capture_dir.glob("*.json")):
            rec = json.loads(p.read_text(encoding="utf-8"))
            if role is None or rec.get("role") == role:
                rec["_file"] = str(p)
                out.append(rec)
        return out

    def stop(self) -> None:
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
