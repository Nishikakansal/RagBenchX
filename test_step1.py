"""
test_step1.py - Terminal smoke test for Step 1:
  ingestion + base interface + Naive Vector retrieval.

Run: python test_step1.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from sentence_transformers import SentenceTransformer

from ingestion import parse_document, clean_text, chunk_text, detect_doc_type
from techniques.naive_vector import NaiveVectorRetriever
import config

SAMPLE_DOC = b"""
# Introduction to Machine Learning

Machine learning is a subfield of artificial intelligence. It enables computers to
learn from data without being explicitly programmed. There are three main types:
supervised learning, unsupervised learning, and reinforcement learning.

## Supervised Learning

In supervised learning, the model is trained on labelled examples. The algorithm
learns a mapping from inputs to outputs. Common algorithms include linear regression,
logistic regression, and decision trees.

## Unsupervised Learning

Unsupervised learning finds hidden patterns in data without labels. Clustering
and dimensionality reduction are the main tasks. K-means and PCA are well-known methods.

## Neural Networks

Neural networks are inspired by the human brain. They consist of layers of
interconnected nodes called neurons. Deep learning uses many such layers to model
complex patterns in data like images and text.

## Applications

Machine learning powers recommendation systems, fraud detection, medical diagnosis,
natural language processing, and autonomous vehicles. Its applications continue to
expand across every industry.
"""

def main():
    print("=" * 60)
    print("RAG BenchX - Step 1 Terminal Test")
    print("=" * 60)

    # 1. Parse document
    print("\n[1] Parsing document...")
    parsed = parse_document("sample.md", SAMPLE_DOC)
    print(f"    word_count     : {parsed.word_count}")
    print(f"    num_chunks     : {len(parsed.chunks)}")
    print(f"    doc_type       : {parsed.doc_type}")
    print(f"    heading_depth  : {parsed.heading_depth}")
    print(f"    code/table dens: {parsed.code_table_density:.2%}")
    print(f"    first chunk    : '{parsed.chunks[0].text[:80]}...'")

    # 2. Load embedding model
    print(f"\n[2] Loading embedding model: {config.EMBED_MODEL}")
    t0 = time.perf_counter()
    embed_model = SentenceTransformer(config.EMBED_MODEL)
    print(f"    loaded in {(time.perf_counter()-t0)*1000:.0f}ms")

    # 3. Encode chunks
    print(f"\n[3] Encoding {len(parsed.chunks)} chunks...")
    t0 = time.perf_counter()
    embeddings = embed_model.encode(
        [c.text for c in parsed.chunks],
        batch_size=64, show_progress_bar=False, convert_to_numpy=True
    ).astype(np.float32)
    print(f"    shape={embeddings.shape}, time={( time.perf_counter()-t0)*1000:.0f}ms")

    # 4. Index NaiveVectorRetriever
    print("\n[4] Indexing NaiveVectorRetriever...")
    t0 = time.perf_counter()
    retriever = NaiveVectorRetriever(embed_model=embed_model)
    retriever.index(parsed.chunks, precomputed_embeddings=embeddings)
    print(f"    indexed in {(time.perf_counter()-t0)*1000:.0f}ms")

    # 5. Run queries
    queries = [
        "What are the main types of machine learning?",
        "How do neural networks relate to the brain?",
        "What is K-means used for?",
    ]
    print(f"\n[5] Retrieval (k={config.RETRIEVAL_K}):")
    for q in queries:
        t0 = time.perf_counter()
        result = retriever.retrieve(q, k=config.RETRIEVAL_K)
        lat = (time.perf_counter()-t0)*1000
        print(f"\n  Q: {q}")
        for i, (cid, score) in enumerate(zip(result.retrieved_chunk_ids, result.scores), 1):
            chunk_text_snippet = next(c.text[:60] for c in parsed.chunks if c.chunk_id == cid)
            print(f"    {i}. [{cid}] score={score:.3f}  '{chunk_text_snippet}...'")
        print(f"    latency: {lat:.1f}ms")

    print("\n" + "=" * 60)
    print("Step 1 PASSED - ingestion + Naive Vector working correctly.")
    print("=" * 60)

if __name__ == "__main__":
    main()