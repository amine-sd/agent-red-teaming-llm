"""Lexical retrieval with BM25 over the corpus chunks.

BM25 scores a chunk by the query words it contains, weighted by their rarity in the corpus and
normalized by the chunk's length. It needs no model and returns the same ranking on every run,
which keeps family 2's precondition ("the trapped document was retrieved") stable.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from rank_bm25 import BM25Okapi

from target.corpus import Chunk

# Compared after accents are stripped, hence "ou", "etre", "meme".
STOPWORDS = frozenset("""
a au aux avec ce ces cet cette dans de des du elle elles en et eux il ils je la le les leur leurs
lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses son sur
ta te tes toi ton tu un une vos votre vous est sont etre avoir ai as avons avez ont
comment quel quelle quels quelles quoi faut peut puis dois doit
""".split())


def tokenize(text: str) -> list[str]:
    """Lowercase, strip accents, split on non-alphanumerics, drop stopwords and a final plural "s"."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    words = [w for w in re.findall(r"[a-z0-9]+", text) if len(w) > 1 and w not in STOPWORDS]
    # Crude plural folding ("listes" -> "liste"); a real stemmer can come later if day 5 needs it.
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words]


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        tokenized = [tokenize(f"{c.title} {c.section} {c.text}") for c in chunks]
        self._bm25 = BM25Okapi(tokenized)
        self._vocab = [set(tokens) for tokens in tokenized]

    @classmethod
    def from_file(cls, path: Path) -> Retriever:
        with Path(path).open(encoding="utf-8") as f:
            return cls([Chunk(**json.loads(line)) for line in f])

    def search(self, query: str, k: int) -> list[Chunk]:
        """Return the k best chunks; chunks sharing no word with the query are never returned.

        The filter is on shared words, not on a positive score: BM25Okapi gives a word present in
        more than half of the chunks a negative weight, so a relevant chunk can score below zero.
        """
        tokens = tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        matching = [i for i in ranked if self._vocab[i].intersection(tokens)]
        return [self.chunks[i] for i in matching[:k]]
