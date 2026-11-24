"""
test_techniques.py - Test each of the 4 remaining techniques one at a time.
Usage:
  python test_techniques.py bm25
  python test_techniques.py hybrid
  python test_techniques.py reranker
  python test_techniques.py parent
"""
import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from ingestion import Chunk, chunk_text
import config

SAMPLE_TEXT = """
Machine learning is a subfield of artificial intelligence that focuses on building systems that learn from data.
Supervised learning uses labeled datasets to train models for classification and regression tasks.
Unsupervised learning discovers hidden patterns, groupings, and structures in unlabeled data using clustering.
Reinforcement learning trains agents to make sequences of decisions by providing rewards or penalties.
Neural networks consist of interconnected layers of artificial nodes designed to recognize complex perceptual patterns.
Deep learning models with transformer architectures have transformed natural language processing and computer vision.
Cross-encoders jointly process query and document pairs to evaluate semantic relevance with high precision.
Keyword search algorithms like BM25 rely on term frequency and inverse document frequency to score matches.
Reciprocal Rank Fusion combines ranked lists from disparate retrieval systems without requiring score normalization.
Parent-document retrieval indexes smaller granular child passages while returning wider surrounding parent context.
"""

def get_test_chunks():
    # Use smaller chunk_size to create multiple distinct chunks
    return chunk_text(SAMPLE_TEXT.strip(), chunk_size=35, overlap=5)

def test_bm25():
    from techniques.bm25_retriever import BM25Retriever
    print("\n" + "=" * 60)
    print("Testing Technique: BM25 (rank_bm25)")
    print("=" * 60)
    chunks = get_test_chunks()
    print(f"Total chunks indexed: {len(chunks)}")
    
    retriever = BM25Retriever()
    t0 = time.perf_counter()
    retriever.index(chunks)
    idx_time = (time.perf_counter() - t0) * 1000
    print(f"Indexing completed in {idx_time:.2f} ms")

    query = "keyword search algorithms BM25 term frequency"
    t0 = time.perf_counter()
    result = retriever.retrieve(query, k=3)
    ret_time = (time.perf_counter() - t0) * 1000

    print(f"\nQuery: '{query}'")
    print(f"Retrieval latency: {ret_time:.2f} ms")
    for i, (cid, score) in enumerate(zip(result.retrieved_chunk_ids, result.scores), 1):
        txt = next(c.text for c in chunks if c.chunk_id == cid)
        print(f"  {i}. [{cid}] Score={score:.4f} | \"{txt[:70]}...\"")
    print("\nBM25 test PASSED successfully.")

def test_hybrid():
    from techniques.hybrid import HybridRetriever
    print("\n" + "=" * 60)
    print("Testing Technique: Hybrid (BM25 + Vector with RRF)")
    print("=" * 60)
    chunks = get_test_chunks()
    print(f"Total chunks indexed: {len(chunks)}")
    
    from sentence_transformers import SentenceTransformer
    embed_model = SentenceTransformer(config.EMBED_MODEL)
    texts = [c.text for c in chunks]
    embeddings = embed_model.encode(texts, convert_to_numpy=True).astype(np.float32)

    retriever = HybridRetriever(embed_model=embed_model)
    t0 = time.perf_counter()
    retriever.index(chunks, precomputed_embeddings=embeddings)
    idx_time = (time.perf_counter() - t0) * 1000
    print(f"Indexing completed in {idx_time:.2f} ms (reusing precomputed embeddings)")

    query = "combining ranking lists with reciprocal rank fusion"
    t0 = time.perf_counter()
    result = retriever.retrieve(query, k=3)
    ret_time = (time.perf_counter() - t0) * 1000

    print(f"\nQuery: '{query}'")
    print(f"Retrieval latency: {ret_time:.2f} ms")
    for i, (cid, score) in enumerate(zip(result.retrieved_chunk_ids, result.scores), 1):
        txt = next(c.text for c in chunks if c.chunk_id == cid)
        print(f"  {i}. [{cid}] RRF Score={score:.5f} | \"{txt[:70]}...\"")
    print("\nHybrid (BM25 + Vector) test PASSED successfully.")

def test_reranker():
    from techniques.reranker import RerankerRetriever
    print("\n" + "=" * 60)
    print("Testing Technique: Vector + Reranker (Cross-Encoder)")
    print("=" * 60)
    chunks = get_test_chunks()
    print(f"Total chunks indexed: {len(chunks)}")

    from sentence_transformers import SentenceTransformer, CrossEncoder
    embed_model = SentenceTransformer(config.EMBED_MODEL)
    cross_encoder = CrossEncoder(config.CROSS_ENCODER_MODEL)
    texts = [c.text for c in chunks]
    embeddings = embed_model.encode(texts, convert_to_numpy=True).astype(np.float32)

    retriever = RerankerRetriever(embed_model=embed_model, cross_encoder=cross_encoder)
    t0 = time.perf_counter()
    retriever.index(chunks, precomputed_embeddings=embeddings)
    idx_time = (time.perf_counter() - t0) * 1000
    print(f"Indexing completed in {idx_time:.2f} ms")

    query = "evaluating query and passage relevance using cross-encoders"
    t0 = time.perf_counter()
    result = retriever.retrieve(query, k=3)
    ret_time = (time.perf_counter() - t0) * 1000

    print(f"\nQuery: '{query}'")
    print(f"Retrieval latency: {ret_time:.2f} ms")
    for i, (cid, score) in enumerate(zip(result.retrieved_chunk_ids, result.scores), 1):
        txt = next(c.text for c in chunks if c.chunk_id == cid)
        print(f"  {i}. [{cid}] Cross-Encoder Logit={score:.4f} | \"{txt[:70]}...\"")
    print("\nVector + Reranker test PASSED successfully.")

def test_parent():
    from techniques.parent_document import ParentDocumentRetriever
    print("\n" + "=" * 60)
    print("Testing Technique: Parent-Document (Child Chunk Search -> Parent Return)")
    print("=" * 60)
    chunks = get_test_chunks()
    print(f"Parent chunks: {len(chunks)}")

    from sentence_transformers import SentenceTransformer
    embed_model = SentenceTransformer(config.EMBED_MODEL)
    retriever = ParentDocumentRetriever(embed_model=embed_model)
    t0 = time.perf_counter()
    retriever.index(chunks)
    idx_time = (time.perf_counter() - t0) * 1000
    print(f"Parent & child indexing completed in {idx_time:.2f} ms (indexed {len(retriever._child_chunks)} child chunks)")

    query = "rewards and penalties in reinforcement learning"
    t0 = time.perf_counter()
    result = retriever.retrieve(query, k=3)
    ret_time = (time.perf_counter() - t0) * 1000

    print(f"\nQuery: '{query}'")
    print(f"Retrieval latency: {ret_time:.2f} ms")
    for i, (cid, score) in enumerate(zip(result.retrieved_chunk_ids, result.scores), 1):
        txt = next(c.text for c in chunks if c.chunk_id == cid)
        print(f"  {i}. Returned Parent [{cid}] Score={score:.4f} | \"{txt[:70]}...\"")
    print("\nParent-Document test PASSED successfully.")

if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    if mode == "bm25":
        test_bm25()
    elif mode == "hybrid":
        test_hybrid()
    elif mode == "reranker":
        test_reranker()
    elif mode == "parent":
        test_parent()
    else:
        test_bm25()
        test_hybrid()
        test_reranker()
        test_parent()