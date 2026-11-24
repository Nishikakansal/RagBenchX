"""
test_step3.py - Step 3: Test question generation via Groq API.

Runs two sub-tests:
  1. Unit: _parse_response() with mock JSON (no API needed)
  2. Integration: real Groq call with a small sample (needs .env with GROQ_API_KEY)

Usage:
  python test_step3.py          # both tests
  python test_step3.py unit     # unit test only (no API needed)
  python test_step3.py api      # integration test (needs key)
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from ingestion import chunk_text
from question_generator import _parse_response, _select_passages, generate_questions
import config

# ── Sample document ───────────────────────────────────────────────────────────
SAMPLE_TEXT = """
The transformer architecture introduced the attention mechanism as its core component.
It enables models to weigh the relevance of different tokens when processing sequences.
BERT is a bidirectional encoder trained using masked language modelling on large corpora.
GPT models use a unidirectional decoder trained autoregressively on next-token prediction.
Retrieval-Augmented Generation combines a dense retriever with a generative language model.
The retriever selects relevant passages from a knowledge base to ground the generator.
BM25 is a probabilistic keyword-based ranking function used in traditional search engines.
Cross-encoders jointly encode queries and documents to produce precise relevance scores.
Sentence transformers map text into dense vector spaces that preserve semantic similarity.
FAISS is a library for efficient similarity search and clustering of dense vectors.
"""


def test_unit():
    print("=" * 60)
    print("Test 1: Unit - _parse_response() with mock JSON")
    print("=" * 60)
    chunks = chunk_text(SAMPLE_TEXT.strip(), chunk_size=30, overlap=5)
    chunk_map = {c.chunk_id: c.text for c in chunks}
    valid_ids = list(chunk_map.keys())[:3]

    # Case A: expected {"questions": [...]}
    mock_a = json.dumps({
        "questions": [
            {"question": "What does the attention mechanism do?", "passage_id": valid_ids[0]},
            {"question": "How does BM25 rank documents?",         "passage_id": valid_ids[1]},
            {"question": "What are cross-encoders used for?",     "passage_id": valid_ids[2]},
            {"question": "This has a fake id",                    "passage_id": "chunk_9999"},
        ]
    })
    result_a = _parse_response(mock_a, chunk_map)
    assert len(result_a) == 3, f"Expected 3 (fake id skipped), got {len(result_a)}"
    assert all("question" in q and "passage_id" in q for q in result_a)
    print(f"  Case A (wrapped dict): {len(result_a)} questions parsed correctly (1 hallucinated id skipped)")

    # Case B: alternate key {"items": [...]}
    mock_b = json.dumps({
        "items": [
            {"question": "What does FAISS provide?", "passage_id": valid_ids[0]},
        ]
    })
    result_b = _parse_response(mock_b, chunk_map)
    assert len(result_b) == 1
    print(f"  Case B (alternate key): {len(result_b)} question parsed correctly")

    # Case C: passage selection - spread check
    chunks_large = chunk_text(SAMPLE_TEXT.strip(), chunk_size=15, overlap=2)
    selected = _select_passages(chunks_large, n=4, seed=config.RANDOM_SEED)
    assert len(selected) == 4
    positions = [c.start_word for c in selected]
    print(f"  Case C (passage spread): {len(selected)} passages selected at word positions {positions}")
    # Check they are spread (not all from the beginning)
    assert max(positions) > min(positions), "Passages should be spread, not all at position 0"

    print("\nUnit test PASSED.")


def test_api():
    print("\n" + "=" * 60)
    print("Test 2: Integration - Real Groq API call")
    print("=" * 60)

    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("GROQ_API_KEY"):
        print("SKIPPED: GROQ_API_KEY not set in .env")
        return

    chunks = chunk_text(SAMPLE_TEXT.strip(), chunk_size=30, overlap=5)
    print(f"Chunks prepared: {len(chunks)}")
    print(f"Requesting {min(5, len(chunks))} questions (small sample for speed)...")

    questions = generate_questions(chunks, n=min(5, len(chunks)))

    print(f"\nGenerated {len(questions)} questions:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. [passage: {q['passage_id']}]")
        print(f"     Q: {q['question']}")
        print(f"     Passage snippet: \"{q['passage_text'][:70]}...\"")

    assert len(questions) > 0, "No questions generated"
    assert all("question" in q for q in questions)
    assert all("passage_id" in q for q in questions)
    assert all("passage_text" in q for q in questions)

    # Verify no question is an exact copy of the passage
    for q in questions:
        snippet = q["passage_text"][:40].lower()
        assert snippet not in q["question"].lower(), \
            f"Question appears to copy passage verbatim: {q['question']}"

    print("\nIntegration test PASSED.")


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "both"
    if mode == "unit":
        test_unit()
    elif mode == "api":
        test_api()
    else:
        test_unit()
        test_api()
    print("\n" + "=" * 60)
    print("Step 3 test complete.")
    print("=" * 60)