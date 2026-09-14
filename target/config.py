"""Settings of the target application, overridable through environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHUNKS_PATH = DATA_DIR / "processed" / "chunks.jsonl"

GUARDRAILS = ("input", "output", "tools", "scope")


def parse_guardrails(value: str) -> frozenset[str]:
    """Read "all", "none" or a comma-separated list such as "input,scope"."""
    value = value.strip().lower()
    if value in ("", "none"):
        return frozenset()
    if value == "all":
        return frozenset(GUARDRAILS)
    names = frozenset(name.strip() for name in value.split(",") if name.strip())
    if unknown := names - set(GUARDRAILS):
        raise ValueError(f"unknown guardrails {sorted(unknown)}, expected some of {GUARDRAILS}")
    return names


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model: str = os.getenv("TARGET_MODEL", "qwen2.5:3b")
    # 0.2 chosen at day 5: near-deterministic, so the benign reference and the defense-cost
    # measurement are stable; residual non-determinism is what day 13 measures.
    temperature: float = float(os.getenv("TARGET_TEMPERATURE", "0.2"))
    # 4096 holds 8 extracts (~2000 tokens). Higher (6144) overflowed the 3.7 GB of WSL RAM and made
    # inference thrash to disk, so day-5 queries ran 90 min each: keep the KV cache small.
    num_ctx: int = int(os.getenv("TARGET_NUM_CTX", "4096"))
    # Keeps the model loaded between calls: reloading it costs about 150 s on the reference machine.
    keep_alive: str = os.getenv("TARGET_KEEP_ALIVE", "30m")
    # 8 chosen at day 5: BM25 finds the right fiche for 52 % of benign questions at 3, 72 % at 8.
    top_k: int = int(os.getenv("TARGET_TOP_K", "8"))
    # A healthy query runs ~100 to 240 s here with 8 extracts; 420 s spares the heavy ones while
    # still failing fast if inference starts thrashing (which took 90 min per query at num_ctx 6144).
    timeout_s: float = float(os.getenv("TARGET_TIMEOUT_S", "420"))
    chunks_path: Path = CHUNKS_PATH
    # All four on by default, as a deployed application would be.
    guardrails: frozenset[str] = parse_guardrails(os.getenv("TARGET_GUARDRAILS", "all"))


settings = Settings()
