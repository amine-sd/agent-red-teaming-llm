"""HTTP API of the target application. Day 3 version: no guardrail at all.

POST /ask retrieves the best excerpts, asks the model, and returns the answer with the fiches it
cites. The retrieved chunk ids are returned too: family 2's precondition is checked on them.

Run: uvicorn target.app:app
"""

import re

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from target.config import settings
from target.llm import chat
from target.prompts import SYSTEM_PROMPT, build_user_message
from target.retrieval import Retriever

CITATION = re.compile(r"\[(F\d+)\]")

app = FastAPI(title="Assistant démarches, cible de red teaming")
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever.from_file(settings.chunks_path)
    return _retriever


class Question(BaseModel):
    question: str


class Source(BaseModel):
    fiche_id: str
    title: str
    url: str


class Answer(BaseModel):
    answer: str
    cited: list[Source]  # fiches cited in the answer AND given to the model; invented ids are dropped
    retrieved: list[str]  # chunk ids given to the model
    prompt_tokens: int
    completion_tokens: int
    duration_s: float


@app.post("/ask", response_model=Answer)
def ask(question: Question) -> Answer:
    chunks = get_retriever().search(question.question, settings.top_k)
    try:
        reply = chat(SYSTEM_PROMPT, build_user_message(question.question, chunks), settings)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"model unavailable: {exc}") from exc

    in_context = {c.fiche_id: c for c in chunks}
    cited_ids = dict.fromkeys(CITATION.findall(reply.content))  # unique, in order of appearance
    cited = [
        Source(fiche_id=i, title=in_context[i].title, url=in_context[i].url)
        for i in cited_ids
        if i in in_context
    ]
    return Answer(
        answer=reply.content,
        cited=cited,
        retrieved=[c.chunk_id for c in chunks],
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        duration_s=reply.duration_s,
    )
