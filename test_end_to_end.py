"""
test_end_to_end.py - End-to-end pipeline test for RAG BenchX.
Simulates what app.py does when a user uploads a file and clicks Run Benchmark.
"""
import time
import os
import sys
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, CrossEncoder

load_dotenv()

import config
from ingestion import parse_document
from techniques.naive_vector import NaiveVectorRetriever
from techniques.bm25_retriever import BM25Retriever
from techniques.hybrid import HybridRetriever
from techniques.reranker import RerankerRetriever
from techniques.parent_document import ParentDocumentRetriever
from question_generator import generate_questions
from evaluation import evaluate_technique
import viz

SAMPLE_DOC = b"""
# Neural Architecture Search and Optimization

Deep learning models have grown in size and complexity. Designing effective neural network architectures
often requires substantial domain expertise and trial-and-error experimentation.
Neural Architecture Search (NAS) automates the design of artificial neural networks.

## Reinforcement Learning for NAS

In early NAS formulations, a recurrent neural network serves as a controller that generates candidate architectures.
The child network is trained on a validation set, and its accuracy serves as the reward signal.
Policy gradient methods update the controller parameters to favor higher-performing architectures.

## Differentiable Architecture Search (DARTS)

DARTS continuous relaxes the discrete search space, allowing gradient descent to directly optimize architecture parameters.
This dramatically reduces search time from thousands of GPU hours to a few GPU hours.
However, DARTS can suffer from performance collapse when skip connections dominate the architecture.

## Model Compression and Pruning

Once an optimal architecture is discovered, deployment on edge hardware often demands compression.
Techniques like weight pruning remove redundant connections, while quantization reduces floating point precision.
Knowledge distillation transfers knowledge from a large teacher network to a compact student network.
"""

def main():
    print("=" * 60)
    print("RAG BenchX - Complete End-to-End Pipeline Verification")
    print("=" * 60)

    # 1. Parse document
    print("\n[Step 1] Ingesting and analyzing document...")
    parsed = parse_document("nas_guide.md", SAMPLE_DOC)
    print(f"  Doc Type: {parsed.doc_type}")
    print(f"  Word Count: {parsed.word_count}")
    print(f"  Chunks Created: {len(parsed.chunks)}")
    assert len(parsed.chunks) > 0, "No chunks created"

    # 2. Load models
    print("\n[Step 2] Loading embedding and cross-encoder models...")
    t0 = time.perf_counter()
    embed_model = SentenceTransformer(config.EMBED_MODEL)
    cross_encoder = CrossEncoder(config.CROSS_ENCODER_MODEL)
    print(f"  Models loaded in {(time.perf_counter() - t0):.2f}s")

    # 3. Precompute embeddings
    print("\n[Step 3] Precomputing shared chunk embeddings...")
    texts = [c.text for c in parsed.chunks]
    embeddings = embed_model.encode(
        texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True
    ).astype(np.float32)
    print(f"  Embeddings shape: {embeddings.shape}")

    # 4. Index all 5 techniques
    print("\n[Step 4] Indexing all 5 techniques...")
    retrievers_config = [
        ("Naive Vector", NaiveVectorRetriever(embed_model=embed_model), True),
        ("BM25", BM25Retriever(), False),
        ("Hybrid (BM25+Vector)", HybridRetriever(embed_model=embed_model), True),
        ("Vector + Reranker", RerankerRetriever(embed_model=embed_model, cross_encoder=cross_encoder), True),
        ("Parent-Document", ParentDocumentRetriever(embed_model=embed_model), False),
    ]

    indexed_retrievers = []
    for label, retriever, uses_emb in retrievers_config:
        t_start = time.perf_counter()
        if uses_emb:
            retriever.index(parsed.chunks, precomputed_embeddings=embeddings)
        else:
            retriever.index(parsed.chunks)
        idx_time = (time.perf_counter() - t_start) * 1000
        print(f"  Indexed '{label}' in {idx_time:.2f} ms")
        indexed_retrievers.append((retriever, idx_time))

    # 5. Question generation via Groq
    print("\n[Step 5] Generating evaluation questions via Groq API...")
    questions = generate_questions(parsed.chunks, n=min(5, len(parsed.chunks)))
    print(f"  Generated {len(questions)} evaluation questions:")
    for i, q in enumerate(questions, 1):
        print(f"    {i}. {q['question']} (target: {q['passage_id']})")

    # 6. Evaluate all techniques
    print("\n[Step 6] Running benchmark evaluation across all techniques...")
    all_metrics = []
    for retriever, idx_time in indexed_retrievers:
        metrics = evaluate_technique(retriever, questions, parsed.chunks, index_time_ms=idx_time)
        all_metrics.append(metrics)
        print(f"  -> {metrics.name:25s} | HitRate@{config.RETRIEVAL_K}: {metrics.hit_rate:.3f} | MRR: {metrics.mrr:.3f} | Latency: {metrics.avg_latency_ms:.1f}ms")

    # 7. Results & Recommendation
    print("\n[Step 7] Checking viz and recommendations...")
    df = viz.build_results_df(all_metrics)
    print("\nResults Table:")
    print(df.to_string(index=False))

    rec = viz.build_recommendation(all_metrics)
    print("\nRecommendation:")
    print(f"  Best Technique: {rec['best_name']}")
    print(f"  Best MRR: {rec['best_mrr']:.4f}")
    print(f"  Close call? {rec['close_call']}")
    print(f"  Explanation: {rec['explanation']}")

    # 8. Check Plotly figures build cleanly
    fig_q = viz.chart_quality(all_metrics)
    fig_l = viz.chart_latency(all_metrics)
    fig_s = viz.chart_scatter(all_metrics)
    assert fig_q is not None and fig_l is not None and fig_s is not None

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED: End-to-end pipeline is fully functional!")
    print("=" * 60)

if __name__ == "__main__":
    main()
