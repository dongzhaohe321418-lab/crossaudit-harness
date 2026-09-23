"""Route `crossaudit.providers.anthropic.complete` through the Claude Code CLI (Amendment 1).

The product builds every prompt; only the transport changes. Each call runs in an empty working
directory with no tools, no MCP servers, no auto-memory and thinking off, and returns an object
with the fields the callers read: `text`, `raw` (with an Anthropic-shaped `usage`), plus the
CLI's reported `cost_usd`.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field


#: The API route sends no system prompt when the caller passes none; the CLI rejects an empty
#: one and would otherwise substitute its own agent prompt, so a fixed neutral line is sent.
NEUTRAL_SYSTEM = "You are a helpful assistant."


@dataclass
class CLIReply:
    text: str
    raw: dict = field(default_factory=dict)
    cost_usd: float | None = None
    request_id: str | None = None
    request_sha256: str = ""
    response_sha256: str = ""


def complete(*, model: str, system: str, prompt: str, key_env: str = "", base_url=None,
             allow_custom: bool = False, max_tokens: int = 4096, timeout: float = 600.0,
             reasoning_effort=None, on_chunk=None, on_thinking=None) -> CLIReply:
    env = dict(os.environ, MAX_THINKING_TOKENS="0", CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
               CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(max_tokens))
    env.pop("ANTHROPIC_API_KEY", None)          # the depleted API key must not be used
    with tempfile.TemporaryDirectory() as d:
        cp = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--system-prompt", system if (system or "").strip() else NEUTRAL_SYSTEM,
             "--tools", "", "--strict-mcp-config", "--output-format", "json"],
            cwd=d, env=env, capture_output=True, text=True, timeout=timeout)
    out = cp.stdout.strip()
    try:
        data = json.loads(out[out.index("{"):])
    except Exception as exc:                                              # noqa: BLE001
        raise RuntimeError(f"claude CLI: unparseable output (rc {cp.returncode}): "
                           f"{(cp.stderr or out)[-300:]}") from exc
    if data.get("is_error"):
        raise RuntimeError(f"claude CLI error: {str(data.get('result'))[:300]}")
    u = data.get("usage") or {}
    raw = {"usage": {"input_tokens": u.get("input_tokens", 0),
                     "output_tokens": u.get("output_tokens", 0),
                     "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
                     "cache_read_input_tokens": u.get("cache_read_input_tokens", 0)},
           "model": model, "cli_session": data.get("session_id")}
    raw["cli_cost_usd"] = data.get("total_cost_usd")
    text = data.get("result") or ""
    from crossaudit.providers.base import Reply
    import hashlib
    return Reply(text=text, request_id=data.get("session_id"),
                 request_sha256=hashlib.sha256((system + "\x00" + prompt).encode()).hexdigest(),
                 response_sha256=hashlib.sha256(text.encode()).hexdigest(), raw=raw)


def install() -> None:
    """Patch both the module attribute and the registry, which holds its own reference taken at
    import time; patching only the former would leave every audit on the depleted API."""
    from crossaudit.providers import anthropic, registry
    anthropic.complete = complete
    registry._PROVIDERS["anthropic"] = complete
    assert registry._PROVIDERS["anthropic"] is complete
