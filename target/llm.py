"""Minimal client for Ollama's chat API.

One non-streamed call per question. Ollama reports token counts and durations; they are kept so
that the bench can log what each request costs, and so that day 3 can measure the machine's speed.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from target.config import Settings


@dataclass(frozen=True)
class Reply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    duration_s: float


def chat(system: str, user: str, settings: Settings) -> Reply:
    payload = {
        "model": settings.model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": settings.temperature, "num_ctx": settings.num_ctx},
    }
    response = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=settings.timeout_s)
    response.raise_for_status()
    data = response.json()
    return Reply(
        content=data["message"]["content"],
        prompt_tokens=data.get("prompt_eval_count", 0),
        completion_tokens=data.get("eval_count", 0),
        duration_s=data.get("total_duration", 0) / 1e9,
    )
