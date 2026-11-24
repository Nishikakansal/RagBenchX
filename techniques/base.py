"""
techniques/base.py - Abstract base class that every RAG technique must implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from ingestion import Chunk


@dataclass
class RetrievalResult:
    """One technique's answer for a single query."""
    technique_name: str
    query: str
    retrieved_chunk_ids: List[str]   # ordered, top-k
    scores: List[float]              # parallel to retrieved_chunk_ids


class BaseRetriever(ABC):
    """
    All RAG techniques share this interface.
    
    Workflow:
        retriever = SomeTechnique()
        retriever.index(chunks)
        result = retriever.retrieve("my query", k=5)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable technique name."""
        ...

    @abstractmethod
    def index(self, chunks: List[Chunk]) -> None:
        """
        Build whatever index the technique needs.
        Called once per document, before any retrieve() calls.
        """
        ...

    @abstractmethod
    def retrieve(self, query: str, k: int) -> RetrievalResult:
        """
        Return the top-k most relevant chunks for *query*.
        Must always return exactly k results (or fewer if corpus is smaller).
        """
        ...