"""Test setup: make the corpus available in fixtures mode (CI), without downloading it.

Most tests build the retriever, which reads the built corpus (data/processed/chunks.jsonl, git
ignored). When it is absent, as in CI, seed it from a small committed sample so the tests run
offline. Locally, the real corpus is present and this does nothing.
"""

import shutil
from pathlib import Path

import pytest

from target.config import CHUNKS_PATH

SAMPLE = Path(__file__).parent / "fixtures" / "chunks_sample.jsonl"


@pytest.fixture(scope="session", autouse=True)
def seed_corpus():
    if not CHUNKS_PATH.exists() and SAMPLE.exists():
        CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SAMPLE, CHUNKS_PATH)
    yield
