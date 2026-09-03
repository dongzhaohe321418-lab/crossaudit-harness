"""OpenAI-compatible chat completions.

One adapter reaches OpenAI and every service that speaks the same route. The
compatibility promised is narrow and versioned: JSON or opt-in SSE chat
completions with a system and a user message. It is not a promise about any
provider's extensions, and `base_url` is opt-in precisely because "compatible"
says nothing about who is on the other end.
"""
from __future__ import annotations

import codecs
import json
from urllib.parse import urlparse

from ..errors import ProviderDenial
from .base import (Reply, egress_check, read_key, request_json, request_stream,
                   sha256_text, vendor_message)
from .specs import capability_card
from .streaming import (STREAM_CHUNK_BYTES, STREAM_FLUSH_SECONDS, ChunkEmitter,
                        take_prefix)

BUILTIN_ORIGIN = "https://api.openai.com"
BUILTIN_BASE = "https://api.openai.com/v1"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _api_base(value: str) -> str:
    """Normalise SDK-style base URLs without doubling a version segment."""
    value = value.rstrip("/")
    return value + "/v1" if not urlparse(value).path.rstrip("/") else value


def _denial_text(exc: ProviderDenial) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return f"{exc.reason}\n{detail.get('detail', '')}".lower()


def _repaired_payload(payload: dict, exc: ProviderDenial) -> dict | None:
    said = _denial_text(exc)
    retry = dict(payload)
    if ("temperature" in retry and "temperature" in said
            and any(word in said for word in
                    ("deprecated", "unsupported", "not support",
                     "only the default"))):
        retry.pop("temperature", None)
    elif ("max_tokens" in retry and "max_tokens" in said
          and "max_completion_tokens" in said):
        retry["max_completion_tokens"] = retry.pop("max_tokens")
    elif ("max_completion_tokens" in retry
          and "use 'max_tokens' instead" in said):
        retry["max_tokens"] = retry.pop("max_completion_tokens")
    else:
        return None
    return retry


def _request(url: str, payload: dict, headers: dict, timeout: float, *,
             repair: bool = True):
    """POST once, repairing a named request-control incompatibility.

    ``repair`` is False for a built-in provider's recognised model: its
    capability card already chose the token field and whether to send a
    temperature, so there is nothing to guess and no unsupported-parameter 400
    to recover from.  Custom endpoints keep the single send-reject-swap retry,
    which is the only sound way to reconcile an origin whose capabilities are
    not declared here.
    """
    try:
        return request_json(url, payload, headers, timeout=timeout)
    except ProviderDenial as exc:
        if not repair:
            raise
        retry = _repaired_payload(payload, exc)
        if retry is None:
            raise
        return request_json(url, retry, headers, timeout=timeout)


def _request_stream(url: str, payload: dict, headers: dict, timeout: float,
                    parser: "_ChatStream", *, repair: bool = True) -> str | None:
    try:
        return request_stream(
            url, payload, headers, timeout=timeout,
            on_bytes=parser.feed, on_idle=parser.idle)
    except ProviderDenial as exc:
        if not repair:
            raise
        retry = _repaired_payload(payload, exc)
        if retry is None:
            raise
        return request_stream(
            url, retry, headers, timeout=timeout,
            on_bytes=parser.feed, on_idle=parser.idle)


# The coalescer is shared with every streaming adapter (D4 contract, one copy).
_take_prefix = take_prefix
_ChunkEmitter = ChunkEmitter


class _ChatStream:
    """Incrementally decode and assemble OpenAI-compatible SSE data events."""

    def __init__(self, emitter: _ChunkEmitter, thinking: _ChunkEmitter | None = None) -> None:
        self.emitter = emitter
        self.thinking = thinking
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self.lines = ""
        self.data_lines: list[str] = []
        self.parts: list[str] = []
        self.usage: dict = {}
        self.request_id: str | None = None
        self.done = False

    def feed(self, raw: bytes) -> None:
        try:
            decoded = self.decoder.decode(raw, final=False)
        except UnicodeDecodeError as exc:
            raise ProviderDenial(
                f"provider returned invalid UTF-8 in completion stream: {exc}",
                category="response") from exc
        self._decoded(decoded)

    def idle(self) -> None:
        self.emitter.idle()

    def _decoded(self, value: str) -> None:
        self.lines += value
        while "\n" in self.lines:
            line, self.lines = self.lines.split("\n", 1)
            self._line(line.rstrip("\r"))

    def _line(self, line: str) -> None:
        if not line:
            if self.data_lines:
                self._event("\n".join(self.data_lines))
                self.data_lines.clear()
            return
        if line.startswith(":"):
            return
        if line.startswith("data:"):
            self.data_lines.append(line[5:].lstrip(" "))

    def _event(self, payload: str) -> None:
        if payload.strip() == "[DONE]":
            self.done = True
            return
        try:
            data = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ProviderDenial(
                f"provider returned malformed completion stream data: {exc}",
                category="response") from exc
        if not isinstance(data, dict):
            raise ProviderDenial(
                "provider returned a non-object completion stream event",
                category="response")
        if data.get("error"):
            raise ProviderDenial(
                "provider stream failed: " + vendor_message(json.dumps(data)),
                category="response")
        if isinstance(data.get("id"), str):
            self.request_id = data["id"]
        if isinstance(data.get("usage"), dict):
            self.usage = data["usage"]
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return
        first = choices[0]
        delta = first.get("delta") if isinstance(first, dict) else None
        # Reasoning-model extensions (``reasoning_content`` on DeepSeek and
        # compatible origins) are summarised thinking: display-only, kept
        # apart from the completion text and never committed.
        thought = (delta.get("reasoning_content") or delta.get("reasoning")
                   if isinstance(delta, dict) else None)
        if isinstance(thought, str) and thought and self.thinking is not None:
            self.thinking.feed(thought)
        content = delta.get("content") if isinstance(delta, dict) else None
        if content is None:
            return
        if not isinstance(content, str):
            raise ProviderDenial(
                "provider returned non-text completion stream content",
                category="response")
        self.parts.append(content)
        self.emitter.feed(content)

    def finish(self) -> str:
        try:
            self._decoded(self.decoder.decode(b"", final=True))
        except UnicodeDecodeError as exc:
            raise ProviderDenial(
                f"provider returned invalid UTF-8 in completion stream: {exc}",
                category="response") from exc
        if self.lines:
            self._line(self.lines.rstrip("\r"))
            self.lines = ""
        if self.data_lines:
            self._event("\n".join(self.data_lines))
            self.data_lines.clear()
        if not self.done:
            raise ProviderDenial(
                "provider completion stream ended without a terminal marker",
                category="response", retryable=True)
        return "".join(self.parts)


def complete(*, model: str, system: str, prompt: str, key_env: str,
             base_url: str | None = None, allow_custom: bool = False,
             max_tokens: int = 4096, timeout: float = 120.0,
             reasoning_effort: str | None = None,
             on_chunk=None, on_thinking=None,
             _builtin_base: str = BUILTIN_BASE,
             _extra_headers: dict[str, str] | None = None,
             _official_bases: tuple[str, ...] = (),
             _temperature: float | None = 0,
             _vendor: str = "openai") -> Reply:
    api_base = _api_base(base_url) if base_url else _builtin_base.rstrip("/")
    builtin_origin = _origin(_builtin_base)
    url = f"{api_base}/chat/completions"
    official = {_api_base(value) for value in (_official_bases or (_builtin_base,))}
    is_builtin = api_base in official
    trusted_origin = _origin(api_base) if is_builtin else builtin_origin
    egress_check(url, builtin_origin=trusted_origin,
                 allow_custom=allow_custom and not is_builtin,
                 allow_insecure_localhost=True)
    # One capability record decides the request shape. On a built-in origin a
    # recognised model sends exactly what it supports; a custom endpoint has no
    # card, so the family-based guess plus the send-reject-swap retry stand in.
    card = capability_card(_vendor, model, official=is_builtin)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    }
    # Modern reasoning models accept only their default temperature; the card
    # withholds the field for them. Models that do take one keep deterministic
    # temperature=0 (1.0 where a vendor mandates it).
    if card.temperature and _temperature is not None:
        payload["temperature"] = _temperature
    if reasoning_effort:
        # The caller supplies this only after provider/model capability
        # validation. An explicit choice is never silently removed on HTTP 400.
        payload["reasoning_effort"] = reasoning_effort
    payload[card.token_param] = max_tokens
    headers = {"authorization": f"Bearer {read_key(key_env)}",
               **(_extra_headers or {})}
    if on_chunk is not None:
        payload["stream"] = True
        # OpenAI emits usage only when explicitly requested. Other compatible
        # origins may include it without this extension, so do not claim the
        # extension outside the first official adapter.
        if _vendor == "openai" and is_builtin:
            payload["stream_options"] = {"include_usage": True}
        emitter = _ChunkEmitter(on_chunk)
        thinking = _ChunkEmitter(on_thinking) if on_thinking is not None else None
        parser = _ChatStream(emitter, thinking)
        try:
            header_rid = _request_stream(
                url, payload, headers, timeout, parser,
                repair=card.compat_retry)
            text = parser.finish()
            if not text.strip():
                raise ProviderDenial("provider returned an empty completion")
            # Residual decoded text is flushed before the explicit terminal
            # event. Only the assembled text — never transport/SSE bytes — is
            # committed by response_sha256.
            emitter.finish("complete")
            if thinking is not None:
                thinking.finish("complete")
            return Reply(
                text=text, request_id=header_rid or parser.request_id,
                request_sha256=sha256_text(system + "\n" + prompt),
                response_sha256=sha256_text(text), raw={"usage": parser.usage})
        except Exception:
            for open_stream in (emitter, thinking):
                if open_stream is not None and not open_stream.finished:
                    try:
                        open_stream.finish("aborted")
                    except Exception:
                        # Preserve the original provider/transport failure. A
                        # callback failure already prevents a successful reply
                        # and the run's liveness event supersedes the open draft.
                        pass
            raise
    data, rid = _request(url, payload, headers, timeout, repair=card.compat_retry)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderDenial(f"unexpected chat-completions response shape: {exc}") from exc
    if not text.strip():
        raise ProviderDenial("provider returned an empty completion")
    return Reply(text=text, request_id=rid or data.get("id"),
                 request_sha256=sha256_text(system + "\n" + prompt),
                 response_sha256=sha256_text(text), raw={"usage": data.get("usage", {})})


#: Adapter capability (D150): see registry.supports_streaming.
complete.supports_streaming = True
