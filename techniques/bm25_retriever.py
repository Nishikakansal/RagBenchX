"""
techniques/bm25_retriever.py - BM25 keyword retrieval using rank_bm25.
"""
from __future__ import annotations

import re
from typing import List

from rank_bm25 import BM25Okapi

from ingestion import Chunk
from techniques.base import BaseRetriever, RetrievalResult
import config


def _tokenize(text: str) -> List[str]:
    """Simple lowercase alphanumeric tokenizer."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever(BaseRetriever):

    def __init__(self):
        self._chunks: List[Chunk] = []
        self._bm25: BM25Okapi | None = None

    @property
    def name(self) -> str:
        return "BM25"

    def index(self, chunks: List[Chunk], **kwargs) -> None:
        self._chunks = chunks
        tokenized = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(tokenized)

    def retrieve(self, query: str, k: int = config.RETRIEVAL_K) -> RetrievalResult:
        if self._bm25 is None:
            raise RuntimeError("Call index() before retrieve().")
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        k_eff = min(k, len(self._chunks))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k_eff]
        return RetrievalResult(
            technique_name=self.name,
            query=query,
            retrieved_chunk_ids=[self._chunks[i].chunk_id for i in top_indices],
            scores=[float(scores[i]) for i in top_indices],
        )