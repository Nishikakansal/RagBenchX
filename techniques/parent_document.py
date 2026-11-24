"""
techniques/parent_document.py - Parent-Document retrieval.

Child chunks (small) are indexed for matching.
On hit, the larger parent window is returned to the caller.
A hit is counted if the parent window contains the source passage.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ingestion import Chunk, chunk_text
from techniques.base import BaseRetriever, RetrievalResult
from techniques.naive_vector import NaiveVectorRetriever
import config


class ParentDocumentRetriever(BaseRetriever):
    """
    Index small child chunks; return the containing parent chunk ids.
    """

    def __init__(self, embed_model=None):
        self._embed_model = embed_model
        self._child_retriever = NaiveVectorRetriever(embed_model=embed_model)
        self._child_chunks: List[Chunk] = []
        self._parent_chunks: List[Chunk] = []
        # Maps child_id -> parent_id
        self._child_to_parent: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "Parent-Document"

    def index(self, chunks: List[Chunk], **kwargs) -> None:
        """
        `chunks` are treated as PARENT chunks.
        We re-chunk each parent into smaller children and build the
        child vector index.
        """
        self._parent_chunks = chunks
        child_size = max(config.CHUNK_SIZE // 3, 50)   # ~100 words
        child_overlap = child_size // 5

        all_children: List[Chunk] = []
        for parent in chunks:
            children = chunk_text(
                parent.text,
                chunk_size=child_size,
                overlap=child_overlap,
            )
            for ci, child in enumerate(children):
                new_id = f"{parent.chunk_id}_c{ci:02d}"
                child.chunk_id = new_id
                self._child_to_parent[new_id] = parent.chunk_id
                all_children.append(child)

        self._child_chunks = all_children
        self._child_retriever.index(all_children)

    def retrieve(self, query: str, k: int = config.RETRIEVAL_K) -> RetrievalResult:
        # Fetch more children to ensure k distinct parents
        fetch_k = min(k * 4, len(self._child_chunks))
        child_res = self._child_retriever.retrieve(query, k=fetch_k)

        seen_parents: list[str] = []
        seen_set: set[str] = set()
        scores_out: list[float] = []

        for cid, score in zip(child_res.retrieved_chunk_ids, child_res.scores):
            pid = self._child_to_parent.get(cid, cid)
            if pid not in seen_set:
                seen_set.add(pid)
                seen_parents.append(pid)
                scores_out.append(score)
            if len(seen_parents) == k:
                break

        return RetrievalResult(
            technique_name=self.name,
            query=query,
            retrieved_chunk_ids=seen_parents,
            scores=scores_out,
        )