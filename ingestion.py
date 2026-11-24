"""
ingestion.py - Document loading, cleaning, chunking, and doc-type detection.
"""
from __future__ import annotations

import io
import re
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

import config


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_id: str          # e.g. "chunk_042"
    text: str
    start_word: int        # position in original word stream
    end_word: int

@dataclass
class ParsedDoc:
    raw_text: str
    sampled_text: str      # capped at MAX_WORDS, spread across document
    chunks: List[Chunk]
    doc_type: str          # "technical" | "plain-text" | "long-hierarchical"
    word_count: int
    heading_depth: int
    code_table_density: float  # fraction of lines that look like code/table


# ── Loaders ──────────────────────────────────────────────────────────────────

def _load_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        t = page.extract_text() or ""
        pages.append(t)
    return "\n".join(pages)


def _load_text(data: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def load_document(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _load_pdf(data)
    elif ext in (".txt", ".md"):
        return _load_text(data)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF, TXT, or MD.")


# ── Cleaning ─────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Normalise whitespace, remove control characters, keep structure."""
    # Remove null bytes and other control chars except newline/tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    # Collapse runs of spaces (not newlines)
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse more than 3 consecutive newlines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


# ── Sampling ─────────────────────────────────────────────────────────────────

def sample_text(text: str, max_words: int = config.MAX_WORDS) -> str:
    """
    If the document exceeds max_words, take evenly-spaced windows spread
    across the whole text so every region is represented.
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    rng = random.Random(config.RANDOM_SEED)
    # Split into 10 bands, sample proportionally from each
    band_size = len(words) // 10
    words_per_band = max_words // 10
    sampled: List[str] = []
    for i in range(10):
        start = i * band_size
        end = start + band_size if i < 9 else len(words)
        band = words[start:end]
        if len(band) <= words_per_band:
            sampled.extend(band)
        else:
            # Take a contiguous window from a random offset inside the band
            offset = rng.randint(0, len(band) - words_per_band)
            sampled.extend(band[offset: offset + words_per_band])
    return " ".join(sampled)


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> List[Chunk]:
    """Word-level sliding-window chunker."""
    words = text.split()
    chunks: List[Chunk] = []
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(
            Chunk(
                chunk_id=f"chunk_{idx:04d}",
                text=" ".join(chunk_words),
                start_word=start,
                end_word=end,
            )
        )
        idx += 1
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── Doc-type detection ────────────────────────────────────────────────────────

def _heading_depth(text: str) -> int:
    """Max markdown heading level found (0 if none)."""
    depths = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s", text, re.MULTILINE)]
    return max(depths) if depths else 0


def _code_table_density(text: str) -> float:
    """Fraction of non-blank lines that look like code/table rows."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    hits = sum(
        1 for l in lines
        if l.startswith("    ")          # indented code block
        or l.startswith("\t")            # tab-indented
        or l.startswith("```")           # fenced code
        or re.match(r"^\s*\|", l)        # markdown table row
        or re.match(r"^\s*[>\-\*] ", l)  # blockquote / list (loosely)
    )
    return hits / len(lines)


def detect_doc_type(text: str) -> Tuple[str, int, float]:
    """
    Returns (doc_type_label, heading_depth, code_table_density).

    Rules (simple heuristics):
      - heading_depth >= 3 AND words > 2000              -> long-hierarchical
      - code_table_density >= 0.15 OR heading_depth >= 2 -> technical
      - else                                              -> plain-text
    """
    words = text.split()
    h_depth = _heading_depth(text)
    ct_density = _code_table_density(text)

    if h_depth >= 3 and len(words) > 2000:
        doc_type = "long-hierarchical"
    elif ct_density >= 0.15 or h_depth >= 2:
        doc_type = "technical"
    else:
        doc_type = "plain-text"

    return doc_type, h_depth, ct_density


# ── Main entry point ──────────────────────────────────────────────────────────

def parse_document(filename: str, data: bytes) -> ParsedDoc:
    """Full pipeline: load -> clean -> sample -> chunk -> classify."""
    raw = load_document(filename, data)
    cleaned = clean_text(raw)
    sampled = sample_text(cleaned)
    chunks = chunk_text(sampled)
    doc_type, h_depth, ct_density = detect_doc_type(cleaned)

    return ParsedDoc(
        raw_text=cleaned,
        sampled_text=sampled,
        chunks=chunks,
        doc_type=doc_type,
        word_count=len(cleaned.split()),
        heading_depth=h_depth,
        code_table_density=ct_density,
    )