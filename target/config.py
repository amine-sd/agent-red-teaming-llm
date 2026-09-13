"""Settings of the target application, overridable through environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHUNKS_PATH = DATA_DIR / "processed" / "chunks.jsonl"


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model: str = os.getenv("TARGET_MODEL", "qwen2.5:3b")
    # Provisional: the stability measure depends on it, to be fixed before day 13.
    temperature: float = float(os.getenv("TARGET_TEMPERATURE", "0.7"))
    num_ctx: int = int(os.getenv("TARGET_NUM_CTX", "4096"))
    top_k: int = int(os.getenv("TARGET_TOP_K", "3"))
    timeout_s: float = float(os.getenv("TARGET_TIMEOUT_S", "600"))
    chunks_path: Path = CHUNKS_PATH


settings = Settings()
