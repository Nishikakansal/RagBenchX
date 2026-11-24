"""
evaluation.py - Compute Hit Rate@k, Recall@k, MRR, and latency metrics.

All metrics are computed per-technique, per-query, then averaged.

Parent-Document special case:
    A hit is counted when the retrieved parent chunk_id contains the
    source passage text (substring match), OR when the chunk_id equals
    the source chunk_id.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional

from ingestion import Chunk
from techniques.base import BaseRetriever, RetrievalResult
import config


@dataclass
class QueryResult:
    question: str
    passage_id: str          # ground-truth chunk_id
    retrieved_ids: List[str]
    hit: bool                # True if passage_id in top-k
    reciprocal_rank: float   # 1/rank if found, else 0
    recall: float            # relevant found / total relevant (here 1 relevant)
    latency_ms: float


@dataclass
class TechniqueMetrics:
    name: str
    hit_rate: float
    recall: float
    mrr: float
    avg_latency_ms: float
    index_time_ms: float
    query_results: List[QueryResult] = field(default_factory=list)


# ── Hit detection ─────────────────────────────────────────────────────────────

def _is_hit(
    retrieved_ids: List[str],
    passage_id: str,
    chunk_map: Dict[str, str],
    passage_text: str,
    is_parent_doc: bool,
) -> tuple[bool, float]:
    """
    Returns (hit, reciprocal_rank).
    For Parent-Document: also checks if retrieved parent text contains passage_text.
    """
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid == passage_id:
            return True, 1.0 / rank
        if is_parent_doc:
            parent_text = chunk_map.get(cid, "")
            if passage_text and passage_text[:100].lower() in parent_text.lower():
                return True, 1.0 / rank
    return False, 0.0


# ── Main evaluation loop ──────────────────────────────────────────────────────

def evaluate_technique(
    retriever: BaseRetriever,
    questions: List[dict],
    chunks: List[Chunk],
    index_time_ms: float,
    k: int = config.RETRIEVAL_K,
) -> TechniqueMetrics:
    """
    Run all questions through `retriever.retrieve()` and compute metrics.

    questions: list of {"question": str, "passage_id": str, "passage_text": str}
    """
    chunk_map = {c.chunk_id: c.text for c in chunks}
    is_parent = "Parent" in retriever.name

    query_results: List[QueryResult] = []

    for q in questions:
        question = q["question"]
        passage_id = q["passage_id"]
        passage_text = q.get("passage_text", "")

        t0 = time.perf_counter()
        result: RetrievalResult = retriever.retrieve(question, k=k)
        latency_ms = (time.perf_counter() - t0) * 1000

        hit, rr = _is_hit(
            result.retrieved_chunk_ids,
            passage_id,
            chunk_map,
            passage_text,
            is_parent_doc=is_parent,
        )

        query_results.append(
            QueryResult(
                question=question,
                passage_id=passage_id,
                retrieved_ids=result.retrieved_chunk_ids,
                hit=hit,
                reciprocal_rank=rr,
                recall=1.0 if hit else 0.0,  # 1 relevant doc per question
                latency_ms=latency_ms,
            )
        )

    n = len(query_results)
    return TechniqueMetrics(
        name=retriever.name,
        hit_rate=sum(r.hit for r in query_results) / n,
        recall=sum(r.recall for r in query_results) / n,
        mrr=sum(r.reciprocal_rank for r in query_results) / n,
        avg_latency_ms=sum(r.latency_ms for r in query_results) / n,
        index_time_ms=index_time_ms,
        query_results=query_results,
    )


# ── Quick self-test (run: python evaluation.py) ───────────────────────────────

def _self_test():
    """
    Hand-checkable test for MRR and Hit Rate.

    3 questions:
      Q1: answer at rank 1 -> hit=T, rr=1.0
      Q2: answer at rank 3 -> hit=T, rr=0.333
      Q3: answer not found  -> hit=F, rr=0.0

    Expected: hit_rate = 2/3 = 0.667, MRR = (1+0.333+0)/3 = 0.444
    """
    from techniques.base import RetrievalResult

    questions_mock = [
        {"question": "Q1", "passage_id": "c1", "passage_text": ""},
        {"question": "Q2", "passage_id": "c3", "passage_text": ""},
        {"question": "Q3", "passage_id": "cx", "passage_text": ""},
    ]
    chunks_mock = [Chunk(f"c{i}", f"text {i}", i, i+1) for i in range(5)]

    class MockRetriever(BaseRetriever):
        name = "Mock"
        _answers = {
            "Q1": ["c1", "c2", "c3", "c4", "c5"],
            "Q2": ["c2", "c4", "c3", "c5", "c0"],
            "Q3": ["c0", "c1", "c2", "c3", "c4"],
        }
        def index(self, chunks, **kw): pass
        def retrieve(self, query, k=5):
            return RetrievalResult("Mock", query, self._answers[query], [1.0]*k)

    m = MockRetriever()
    metrics = evaluate_technique(m, questions_mock, chunks_mock, index_time_ms=0.0)

    expected_hr = 2 / 3
    expected_mrr = (1.0 + 1/3 + 0.0) / 3

    print(f"Hit Rate: {metrics.hit_rate:.4f}  (expected {expected_hr:.4f})")
    print(f"MRR:      {metrics.mrr:.4f}  (expected {expected_mrr:.4f})")

    tol = 1e-6
    assert abs(metrics.hit_rate - expected_hr) < tol, f"Hit Rate mismatch: {metrics.hit_rate}"
    assert abs(metrics.mrr - expected_mrr) < tol, f"MRR mismatch: {metrics.mrr}"
    print("All assertions passed!")


if __name__ == "__main__":
    _self_test()