"""HTTP API of the target application.

POST /ask runs the pipeline with the guardrails chosen at startup (TARGET_GUARDRAILS, all four by
default). The HTTP API cannot change them: a client must not be able to switch the defenses off.

Run: uvicorn target.app:app
"""

from dataclasses import asdict

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from target.config import settings
from target.corpus import load_chunks
from target.pipeline import run
from target.retrieval import Retriever

app = FastAPI(title="Assistant démarches, cible de red teaming")
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever(load_chunks(settings.chunks_path))
    return _retriever


class Question(BaseModel):
    question: str


class Source(BaseModel):
    fiche_id: str
    title: str
    url: str


class ToolCallOut(BaseModel):
    name: str
    arguments: dict
    executed: bool
    blocked_by: str | None


class Answer(BaseModel):
    answer: str
    cited: list[Source]  # fiches cited in the answer AND given to the model; invented ids are dropped
    retrieved: list[str]  # chunk ids found by the search, before the input filter
    tool_calls: list[ToolCallOut]
    events: list[dict]  # one entry per guardrail decision
    guardrails: list[str]  # guardrails active for this answer
    prompt_tokens: int
    completion_tokens: int
    duration_s: float


@app.post("/ask", response_model=Answer)
def ask(question: Question) -> Answer:
    try:
        result = run(question.question, settings, get_retriever())
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"model unavailable: {exc}") from exc
    return Answer.model_validate(asdict(result))
