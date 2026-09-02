"""Anthropic Messages API, over stdlib urllib."""
from __future__ import annotations

import json

from ..errors import ProviderDenial
from .base import (Reply, egress_check, read_key, request_json, request_stream,
                   sha256_text, vendor_message)
from .specs import capability_card
from .streaming import ChunkEmitter, SSELines

BUILTIN_ORIGIN = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


def _denial_text(exc: ProviderDenial) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return f"{exc.reason}\n{detail.get('detail', '')}".lower()


def _request(url: str, payload: dict, headers: dict, timeout: float, *,
             repair: bool = True):
    """POST once, repairing a rejected temperature only for unknown endpoints.

    A built-in, recognised model never reaches here with a temperature it does
    not accept — its capability card already decided that, so ``repair`` is
    False and the request is not gambled.  Custom endpoints keep the single
    retry: their capabilities are unknown, and a precise HTTP 400 about
    ``temperature`` is safe to repair because the provider processed no
    completion.  All other errors remain fail-closed.
    """
    try:
        return request_json(url, payload, headers, timeout=timeout)
    except ProviderDenial as exc:
        said = _denial_text(exc)
        rejected_temperature = (
            "temperature" in said
            and any(word in said for word in
                    ("deprecated", "unsupported", "not support", "only the default"))
        )
        if not repair or "temperature" not in payload or not rejected_temperature:
            raise
        retry = dict(payload)
        retry.pop("temperature", None)
        return request_json(url, retry, headers, timeout=timeout)


class _MessageStream:
    """Assemble one Messages-API SSE stream (D150, Anthropic half of D4).

    ``content_block_delta`` text deltas feed the shared coalescer; when the
    request enabled thinking, ``thinking_delta`` deltas feed a second coalescer
    whose chunks the caller keeps apart (``thinking_chunk``): summarised
    thinking is display-only and never part of the completion text, the
    response commitment, the auditor prompt or a committed file.
    """

    def __init__(self, on_chunk, on_thinking=None) -> None:
        self.text_emitter = ChunkEmitter(on_chunk)
        self.thinking_emitter = ChunkEmitter(on_thinking) if on_thinking else None
        self.lines = SSELines(self._event)
        self.parts: list[str] = []
        self.blocks: dict[int, str] = {}
        self.usage: dict = {}
        self.request_id: str | None = None
        self.done = False

    def feed(self, raw: bytes) -> None:
        self.lines.feed(raw)

    def idle(self) -> None:
        self.text_emitter.idle()
        if self.thinking_emitter is not None:
            self.thinking_emitter.idle()

    def _event(self, name: str, payload: str) -> None:
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
        kind = name or str(data.get("type") or "")
        if kind == "error" or data.get("error"):
            raise ProviderDenial(
                "provider stream failed: " + vendor_message(json.dumps(data)),
                category="response")
        if kind == "message_start":
            message = data.get("message") if isinstance(data.get("message"), dict) else {}
            if isinstance(message.get("id"), str):
                self.request_id = message["id"]
            if isinstance(message.get("usage"), dict):
                self.usage.update(message["usage"])
        elif kind == "content_block_start":
            block = data.get("content_block") if isinstance(
                data.get("content_block"), dict) else {}
            self.blocks[int(data.get("index", 0) or 0)] = str(block.get("type") or "")
        elif kind == "content_block_delta":
            delta = data.get("delta") if isinstance(data.get("delta"), dict) else {}
            delta_type = str(delta.get("type") or "")
            if delta_type == "text_delta":
                text = delta.get("text")
                if not isinstance(text, str):
                    raise ProviderDenial(
                        "provider returned non-text completion stream content",
                        category="response")
                self.parts.append(text)
                self.text_emitter.feed(text)
            elif delta_type == "thinking_delta":
                thought = delta.get("thinking")
                if isinstance(thought, str) and self.thinking_emitter is not None:
                    self.thinking_emitter.feed(thought)
            # signature_delta and input_json_delta carry nothing to show.
        elif kind == "message_delta":
            if isinstance(data.get("usage"), dict):
                self.usage.update(data["usage"])
        elif kind == "message_stop":
            self.done = True

    def finish(self) -> str:
        self.lines.finish()
        if not self.done:
            raise ProviderDenial(
                "provider completion stream ended without a terminal marker",
                category="response", retryable=True)
        return "".join(self.parts)

    def close(self, outcome: str) -> None:
        for emitter in (self.text_emitter, self.thinking_emitter):
            if emitter is not None and not emitter.finished:
                try:
                    emitter.finish(outcome)
                except Exception:      # noqa: BLE001 -- keep the provider failure
                    pass


def _stream(url: str, payload: dict, headers: dict, timeout: float, *,
            repair: bool, on_chunk, on_thinking) -> Reply:
    streamed = dict(payload, stream=True)
    parser = _MessageStream(on_chunk, on_thinking)

    def once(body: dict) -> str | None:
        return request_stream(url, body, headers, timeout=timeout,
                              on_bytes=parser.feed, on_idle=parser.idle)

    try:
        try:
            rid = once(streamed)
        except ProviderDenial as exc:
            said = _denial_text(exc)
            if (not repair or "temperature" not in streamed or "temperature" not in said
                    or not any(word in said for word in
                               ("deprecated", "unsupported", "not support",
                                "only the default"))):
                raise
            retry = dict(streamed)
            retry.pop("temperature", None)
            rid = once(retry)
        text = parser.finish()
        if not text.strip():
            raise ProviderDenial("Anthropic returned an empty completion")
        # Residual text is flushed before the explicit terminal event; only the
        # assembled text — never transport bytes or thinking — is committed.
        parser.close("complete")
        return Reply(text=text, request_id=rid or parser.request_id,
                     request_sha256=sha256_text(payload["system"] + "\n"
                                                + payload["messages"][0]["content"]),
                     response_sha256=sha256_text(text),
                     raw={"usage": parser.usage})
    except Exception:
        parser.close("aborted")
        raise


def complete(*, model: str, system: str, prompt: str, key_env: str,
             base_url: str | None = None, allow_custom: bool = False,
             max_tokens: int = 4096, timeout: float = 120.0,
             reasoning_effort: str | None = None,
             on_chunk=None, on_thinking=None) -> Reply:
    origin = (base_url or BUILTIN_ORIGIN).rstrip("/")
    url = f"{origin}/v1/messages"
    # Loopback HTTP is useful for explicitly authorised local-compatible
    # providers and end-to-end testing. It still fails the custom-origin check
    # unless the caller opted in, so a configured URL can never redirect a key
    # there by accident.
    egress_check(url, builtin_origin=BUILTIN_ORIGIN, allow_custom=allow_custom,
                 allow_insecure_localhost=True)
    card = capability_card("anthropic", model, official=(origin == BUILTIN_ORIGIN))
    payload = {
        "model": model,
        card.token_param: max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if card.temperature:
        payload["temperature"] = 0
    if reasoning_effort:
        payload["output_config"] = {"effort": reasoning_effort}
    headers = {"x-api-key": read_key(key_env), "anthropic-version": API_VERSION}
    if on_chunk is not None:
        return _stream(url, payload, headers, timeout, repair=card.compat_retry,
                       on_chunk=on_chunk, on_thinking=on_thinking)
    data, rid = _request(url, payload, headers, timeout, repair=card.compat_retry)
    try:
        text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise ProviderDenial(f"unexpected Anthropic response shape: {exc}") from exc
    if not text.strip():
        raise ProviderDenial("Anthropic returned an empty completion")
    return Reply(text=text, request_id=rid or data.get("id"),
                 request_sha256=sha256_text(system + "\n" + prompt),
                 response_sha256=sha256_text(text), raw={"usage": data.get("usage", {})})


#: Adapter capability (D150): the resilience layer streams through any adapter
#: that declares it, instead of naming one adapter.
complete.supports_streaming = True
