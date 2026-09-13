"""Minimal client for Ollama's chat API, tools included.

One non-streamed call at a time. Ollama reports token counts and durations; they are kept so that
the bench can log what each request costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from target.config import Settings


@dataclass(frozen=True)
class Reply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    duration_s: float
    tool_calls: list[dict] = field(default_factory=list)  # as sent by Ollama: {"function": {...}}


def chat(messages: list[dict], settings: Settings, tools: list[dict] | None = None) -> Reply:
    payload = {
        "model": settings.model,
        "stream": False,
        "messages": messages,
        "keep_alive": settings.keep_alive,
        "options": {"temperature": settings.temperature, "num_ctx": settings.num_ctx},
    }
    if tools:
        payload["tools"] = tools
    response = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=settings.timeout_s)
    response.raise_for_status()
    data = response.json()
    message = data["message"]
    return Reply(
        content=message.get("content", ""),
        prompt_tokens=data.get("prompt_eval_count", 0),
        completion_tokens=data.get("eval_count", 0),
        duration_s=data.get("total_duration", 0) / 1e9,
        tool_calls=message.get("tool_calls") or [],
    )
