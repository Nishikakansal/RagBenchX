"""
techniques/naive_vector.py - Naive dense vector retrieval with FAISS.

Embeddings are computed once externally (shared_embeddings) and injected
so that Naive, Hybrid, and Reranker all reuse the same vectors.
"""
from __future__ import annotations

import time
import numpy as np
from typing import List, Optional

import faiss

from ingestion import Chunk
from techniques.base import BaseRetriever, RetrievalResult
import config


class NaiveVectorRetriever(BaseRetriever):
    """
    Flat L2 FAISS index over chunk embeddings.
    Accepts pre-computed embeddings to avoid redundant encode() calls.
    """

    def __init__(self, embed_model=None):
        self._embed_model = embed_model
        self._chunks: List[Chunk] = []
        self._index: Optional[faiss.IndexFlatL2] = None
        self._embeddings: Optional[np.ndarray] = None

    @property
    def name(self) -> str:
        return "Naive Vector"

    def index(
        self,
        chunks: List[Chunk],
        precomputed_embeddings: Optional[np.ndarray] = None,
    ) -> None:
        """
        Build FAISS index.
        If precomputed_embeddings is provided it is used directly;
        otherwise the embed_model encodes the chunks.
        """
        self._chunks = chunks

        if precomputed_embeddings is not None:
            self._embeddings = precomputed_embeddings.astype(np.float32)
        else:
            if self._embed_model is None:
                raise ValueError("Provide either embed_model or precomputed_embeddings.")
            texts = [c.text for c in chunks]
            self._embeddings = self._embed_model.encode(
                texts,
                batch_size=64,
                show_progress_bar=False,
                convert_to_numpy=True,
            ).astype(np.float32)

        dim = self._embeddings.shape[1]
        self._index = faiss.IndexFlatL2(dim)
        self._index.add(self._embeddings)

    def retrieve(self, query: str, k: int = config.RETRIEVAL_K) -> RetrievalResult:
        if self._index is None:
            raise RuntimeError("Call index() before retrieve().")
        k_eff = min(k, len(self._chunks))
        q_vec = self._embed_model.encode(
            [query], show_progress_bar=False, convert_to_numpy=True
        ).astype(np.float32)
        distances, indices = self._index.search(q_vec, k_eff)
        ids = [self._chunks[i].chunk_id for i in indices[0]]
        scores = [float(-d) for d in distances[0]]   # negate: higher = better
        return RetrievalResult(
            technique_name=self.name,
            query=query,
            retrieved_chunk_ids=ids,
            scores=scores,
        )