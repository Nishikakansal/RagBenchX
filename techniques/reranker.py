"""
techniques/reranker.py - Vector retrieval followed by cross-encoder re-ranking.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
from sentence_transformers import CrossEncoder

from ingestion import Chunk
from techniques.base import BaseRetriever, RetrievalResult
from techniques.naive_vector import NaiveVectorRetriever
import config


class RerankerRetriever(BaseRetriever):
    """
    Stage 1: dense vector top-RERANKER_INITIAL_K candidates.
    Stage 2: cross-encoder scores all candidates, return top-k.
    """

    def __init__(self, embed_model=None, cross_encoder: Optional[CrossEncoder] = None):
        self._vector = NaiveVectorRetriever(embed_model=embed_model)
        self._cross_encoder = cross_encoder
        self._chunks: List[Chunk] = []
        self._chunk_map: dict[str, str] = {}   # chunk_id -> text

    @property
    def name(self) -> str:
        return "Vector + Reranker"

    def index(
        self,
        chunks: List[Chunk],
        precomputed_embeddings: Optional[np.ndarray] = None,
    ) -> None:
        self._chunks = chunks
        self._chunk_map = {c.chunk_id: c.text for c in chunks}
        self._vector.index(chunks, precomputed_embeddings=precomputed_embeddings)

    def retrieve(self, query: str, k: int = config.RETRIEVAL_K) -> RetrievalResult:
        if self._cross_encoder is None:
            raise RuntimeError("cross_encoder not provided.")

        initial_k = min(config.RERANKER_INITIAL_K, len(self._chunks))
        candidates = self._vector.retrieve(query, k=initial_k)

        pairs = [(query, self._chunk_map[cid]) for cid in candidates.retrieved_chunk_ids]
        ce_scores = self._cross_encoder.predict(pairs, show_progress_bar=False)

        ranked = sorted(
            zip(candidates.retrieved_chunk_ids, ce_scores.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )[:k]

        return RetrievalResult(
            technique_name=self.name,
            query=query,
            retrieved_chunk_ids=[cid for cid, _ in ranked],
            scores=[score for _, score in ranked],
        )