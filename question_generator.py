"""
question_generator.py - Generate evaluation questions via Groq API.

Makes ONE batched API call. Returns a list of dicts:
    {"question": str, "passage_id": str, "passage_text": str}
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import List

from groq import Groq
from dotenv import load_dotenv

from ingestion import Chunk
import config

load_dotenv()

_SYSTEM_PROMPT = """\
You are a question-generation assistant. Given document passages, produce
retrieval-style questions that can be answered from ONE specific passage.

Rules:
- Each question must be answerable ONLY from the paired passage.
- Paraphrase: do NOT copy exact phrases from the passage.
- Questions should be specific and diverse (factual, conceptual, inferential).
- Return ONLY valid JSON - no markdown, no explanation.

Output format (a JSON object with a questions array):
{
  "questions": [
    {"question": "...", "passage_id": "chunk_0001"},
    ...
  ]
}
"""


def _build_user_prompt(passages: List[Chunk]) -> str:
    lines = ["Generate exactly one question per passage below.\n"]
    for chunk in passages:
        lines.append(f"[{chunk.chunk_id}]\n{chunk.text}\n")
    lines.append(
        f"\nReturn a JSON object with a questions array containing {len(passages)} objects, "
        "each having keys question and passage_id."
    )
    return "\n".join(lines)


def _select_passages(chunks: List[Chunk], n: int, seed: int = config.RANDOM_SEED) -> List[Chunk]:
    """Pick n chunks spread evenly across the document."""
    rng = random.Random(seed)
    if len(chunks) <= n:
        return chunks
    step = len(chunks) / n
    indices = [int(i * step) for i in range(n)]
    jitter = max(1, int(step * 0.3))
    selected = []
    for idx in indices:
        j = rng.randint(-jitter, jitter)
        picked = max(0, min(len(chunks) - 1, idx + j))
        selected.append(chunks[picked])
    return selected


def _parse_response(raw: str, chunk_map: dict) -> List[dict]:
    """
    Parse Groq JSON response robustly.
    Handles: {"questions": [...]}, {"items": [...]}, or bare [...]
    """
    parsed = json.loads(raw)

    if isinstance(parsed, dict):
        arr = None
        if "questions" in parsed and isinstance(parsed["questions"], list):
            arr = parsed["questions"]
        else:
            for v in parsed.values():
                if isinstance(v, list):
                    arr = v
                    break
        if arr is None:
            raise ValueError(f"No list found in JSON response. Keys: {list(parsed.keys())}")
        parsed = arr

    if not isinstance(parsed, list):
        raise ValueError(f"Expected list, got {type(parsed)}")

    questions = []
    for item in parsed:
        pid = item.get("passage_id", "")
        q = item.get("question", "").strip()
        if not q:
            continue
        if pid not in chunk_map:
            continue
        questions.append({
            "question": q,
            "passage_id": pid,
            "passage_text": chunk_map[pid],
        })
    return questions


def generate_questions(
    chunks: List[Chunk],
    n: int = config.NUM_QUESTIONS,
    max_retries: int = 3,
) -> List[dict]:
    """
    Returns list of {"question": str, "passage_id": str, "passage_text": str}.
    Raises RuntimeError on repeated failure.
    Retries with exponential backoff: 2s, 4s, 8s.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set. Copy .env.example to .env and fill in your key."
        )

    client = Groq(api_key=api_key)
    passages = _select_passages(chunks, n)
    user_prompt = _build_user_prompt(passages)
    chunk_map = {c.chunk_id: c.text for c in chunks}

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[question_generator] Calling Groq ({config.GROQ_MODEL}), "
                  f"n={len(passages)}, attempt {attempt}/{max_retries}...")
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            questions = _parse_response(raw, chunk_map)

            if not questions:
                raise ValueError("No valid questions parsed from Groq response.")

            print(f"[question_generator] Success: {len(questions)} questions generated.")
            return questions

        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt
            print(f"[question_generator] Attempt {attempt} failed: {exc}. Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(
        f"Question generation failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )