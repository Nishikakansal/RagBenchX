"""
techniques/hybrid.py - Hybrid BM25 + Vector retrieval via Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ingestion import Chunk
from techniques.base import BaseRetriever, RetrievalResult
from techniques.bm25_retriever import BM25Retriever
from techniques.naive_vector import NaiveVectorRetriever
import config

RRF_K = 60   # standard RRF constant


def _rrf_fuse(
    bm25_ids: List[str],
    vec_ids: List[str],
    all_ids: List[str],
    k_const: int = RRF_K,
) -> List[tuple]:
    """
    Combine two ranked lists using Reciprocal Rank Fusion.
    Returns list of (chunk_id, score) sorted descending.
    """
    scores: dict[str, float] = {cid: 0.0 for cid in all_ids}
    for rank, cid in enumerate(bm25_ids):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_const + rank + 1)
    for rank, cid in enumerate(vec_ids):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_const + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever(BaseRetriever):
    """BM25 + dense vector with RRF fusion."""

    def __init__(self, embed_model=None):
        self._bm25 = BM25Retriever()
        self._vector = NaiveVectorRetriever(embed_model=embed_model)
        self._chunks: List[Chunk] = []

    @property
    def name(self) -> str:
        return "Hybrid (BM25 + Vector)"

    def index(
        self,
        chunks: List[Chunk],
        precomputed_embeddings: Optional[np.ndarray] = None,
    ) -> None:
        self._chunks = chunks
        self._bm25.index(chunks)
        self._vector.index(chunks, precomputed_embeddings=precomputed_embeddings)

    def retrieve(self, query: str, k: int = config.RETRIEVAL_K) -> RetrievalResult:
        n = len(self._chunks)
        fetch_k = min(n, max(k * 4, 20))   # fetch more for better fusion coverage

        bm25_res = self._bm25.retrieve(query, k=fetch_k)
        vec_res = self._vector.retrieve(query, k=fetch_k)

        all_ids = [c.chunk_id for c in self._chunks]
        fused = _rrf_fuse(
            bm25_res.retrieved_chunk_ids,
            vec_res.retrieved_chunk_ids,
            all_ids,
        )[:k]

        return RetrievalResult(
            technique_name=self.name,
            query=query,
            retrieved_chunk_ids=[cid for cid, _ in fused],
            scores=[score for _, score in fused],
        )