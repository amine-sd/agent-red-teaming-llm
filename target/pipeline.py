"""The target's answering pipeline, with its four guardrails switchable one by one.

It is kept apart from the HTTP layer so that the bench can call it in-process with a different set
of guardrails for each call. Every guardrail decision is written to `events`: that is what lets the
report attribute a failed attack to the guardrail that stopped it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from target.config import Settings
from target.corpus import Chunk
from target.guardrails import detect_injection, filter_output
from target.llm import Reply, chat
from target.prompts import CANARY, SYSTEM_PROMPT, build_user_message, format_excerpts
from target.retrieval import Retriever
from target.tools import TOOL_NAMES, TOOLS, WHITELIST, simulate

CITATION = re.compile(r"\[(F\d+)\]")
REFUSAL = "Je ne peux pas traiter cette demande."
MAX_TOOL_ROUNDS = 2  # each round costs one more model call, about 40 s on the reference machine


@dataclass
class ToolCall:
    name: str
    arguments: dict
    executed: bool
    blocked_by: str | None = None  # "tools" (whitelist), "unknown_tool" or "round_limit"


@dataclass
class Result:
    guardrails: list[str]
    answer: str = ""
    cited: list[dict] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)  # chunk ids found by the search, before the input filter
    tool_calls: list[ToolCall] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_s: float = 0.0


def run(question: str, settings: Settings, retriever: Retriever) -> Result:
    guards = settings.guardrails
    result = Result(guardrails=sorted(guards))

    if "input" in guards and (patterns := detect_injection(question)):
        result.events.append({"guardrail": "input", "action": "blocked_question", "patterns": patterns})
        result.answer = REFUSAL
        return result

    seen: dict[str, Chunk] = {}  # chunk id -> chunk actually given to the model

    def fetch(query: str) -> list[Chunk]:
        kept = _admit(_search(query, settings, retriever, result), guards, result)
        seen.update((c.chunk_id, c) for c in kept)
        return kept

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(question, fetch(question))},
    ]
    reply = _ask_model(messages, settings, result)
    for _ in range(MAX_TOOL_ROUNDS):
        if not reply.tool_calls:
            break
        messages.append({"role": "assistant", "content": reply.content, "tool_calls": reply.tool_calls})
        for call in reply.tool_calls:
            messages.append(_run_tool(call, guards, fetch, result))
        reply = _ask_model(messages, settings, result)
    for call in reply.tool_calls:  # still asking for tools once the round limit is reached
        name, arguments = _parse_call(call)
        result.tool_calls.append(ToolCall(name, arguments, executed=False, blocked_by="round_limit"))

    answer = reply.content
    if "output" in guards:
        context = question + "\n" + "\n".join(f"{c.title}\n{c.text}" for c in seen.values())
        check = filter_output(answer, SYSTEM_PROMPT, CANARY, context)
        answer = check.text
        result.events.extend(
            {"guardrail": "output", "action": "neutralized", "check": name, "count": count}
            for name, count in check.findings.items()
            if count
        )
    result.answer = answer

    by_fiche = {c.fiche_id: c for c in seen.values()}
    result.cited = [
        {"fiche_id": i, "title": by_fiche[i].title, "url": by_fiche[i].url}
        for i in dict.fromkeys(CITATION.findall(answer))
        if i in by_fiche
    ]
    return result


def _search(query: str, settings: Settings, retriever: Retriever, result: Result) -> list[Chunk]:
    """Search the index. With the scope limit on, internal documents are left out, and it is recorded."""
    if "scope" not in settings.guardrails:
        chunks = retriever.search(query, settings.top_k)
    else:
        chunks = retriever.search(query, settings.top_k, allow_internal=False)
        hidden = [c.chunk_id for c in retriever.search(query, settings.top_k) if c.scope == "internal"]
        if hidden:
            result.events.append({"guardrail": "scope", "action": "hid_internal", "chunk_ids": hidden})
    result.retrieved.extend(c.chunk_id for c in chunks)
    return chunks


def _admit(chunks: list[Chunk], guards: frozenset[str], result: Result) -> list[Chunk]:
    """Input filter on the extracts: an extract carrying injection phrasing never reaches the model."""
    if "input" not in guards:
        return chunks
    kept = []
    for c in chunks:
        if patterns := detect_injection(f"{c.title}\n{c.text}"):
            result.events.append(
                {"guardrail": "input", "action": "dropped_extract", "chunk_id": c.chunk_id, "patterns": patterns}
            )
        else:
            kept.append(c)
    return kept


def _parse_call(call: dict) -> tuple[str, dict]:
    function = call.get("function", {})
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):  # some models send the arguments as a JSON string
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw": arguments}
    return function.get("name", ""), arguments


def _run_tool(call: dict, guards: frozenset[str], fetch: Callable[[str], list[Chunk]], result: Result) -> dict:
    """Pass one tool call through the whitelist; return the tool message sent back to the model."""
    name, arguments = _parse_call(call)
    if name not in TOOL_NAMES:
        output, blocked_by = f"Erreur : l'outil {name} n'existe pas.", "unknown_tool"
    elif "tools" in guards and name not in WHITELIST:
        output, blocked_by = "Erreur : cet outil n'est pas autorisé.", "tools"
        result.events.append({"guardrail": "tools", "action": "blocked_tool", "tool": name})
    elif name == "search_fiches":
        output, blocked_by = format_excerpts(fetch(str(arguments.get("query", "")))), None
    else:
        output, blocked_by = simulate(name, arguments), None
    result.tool_calls.append(ToolCall(name, arguments, executed=blocked_by is None, blocked_by=blocked_by))
    return {"role": "tool", "content": output, "tool_name": name}


def _ask_model(messages: list[dict], settings: Settings, result: Result) -> Reply:
    reply = chat(messages, settings, tools=TOOLS)
    result.prompt_tokens += reply.prompt_tokens
    result.completion_tokens += reply.completion_tokens
    result.duration_s += reply.duration_s
    return reply
